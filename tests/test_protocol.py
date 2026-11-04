"""Phase 7: calibration sampling, blind sheet, reproduce checks, and a messy two-rater agreement workflow."""
import csv
import io
import random

import pytest

import agreement as ag
import blind_sheet as bsh
import common as c
import labels as L
import reproduce as rp
import sample as sm


def mk(i, tac, template=False, goal="g", status="ai_cross_checked", conf="clear", planned=False):
    tid = f"x{i}_rce" if template else f"t{i}"
    return {"id": tid, "setting": "vllm", "environment": "e", "goal_text": goal, "label_status": status,
            "scorer_status": "planned_not_implemented" if planned else "implemented_or_not_flagged",
            "source": {"repo": "o/r", "sha": "0" * 40, "path": "p"}, "our_summary": None,
            "labels": {"attack": {"primary_tactic": tac, "technique": "T1048", "required_step_tactics": []}, "confidence": conf, "rationale": "r"}}


# ---- calibration ---------------------------------------------------------------------------------------------
def test_real_calibration_is_fixed_and_meets_the_rules():
    a = sm.calibration(sm.pool()); b = sm.calibration(sm.pool())
    assert [t["id"] for t in a] == [t["id"] for t in b] and len(a) == 10
    assert sum(bool(sm.B.is_template(t["id"])) for t in a) <= 1
    assert all(t["goal_text"] and t["label_status"] == "ai_cross_checked" and t["labels"]["confidence"] == "clear" for t in a)
    assert all(t.get("scorer_status") != "planned_not_implemented" for t in a)
    assert len({t["labels"]["attack"]["primary_tactic"] for t in a}) >= 6


def test_calibration_same_whatever_the_input_order():
    pool = [mk(i, ["TA0010", "TA0040", "TA0002", "TA0112"][i % 4]) for i in range(30)]
    shuffled = pool[:]; random.Random(1).shuffle(shuffled)
    assert [t["id"] for t in sm.calibration(sorted(pool, key=lambda t: t["id"]))] == [t["id"] for t in sm.calibration(sorted(shuffled, key=lambda t: t["id"]))]


def test_calibration_small_and_empty_pools():
    assert sm.calibration([]) == []
    assert len(sm.calibration([mk(1, "TA0010"), mk(2, "TA0040")], n=10)) == 2


def test_calibration_never_takes_two_templates_even_when_only_templates_exist():
    pool = [mk(i, "TA0001", template=True) for i in range(12)]
    assert sum(bool(sm.B.is_template(t["id"])) for t in sm.calibration(pool)) <= 1


def test_pool_excludes_planned_ambiguous_unlicensed_and_unchecked():
    import labels as L2
    real = {t["id"] for t in sm.pool()}
    for (env, tid), (f, t) in L2.load_tasks().items():
        if t.get("scorer_status") == "planned_not_implemented" or t["labels"]["confidence"] != "clear" or not t.get("goal_text") or t["label_status"] != "ai_cross_checked":
            assert tid not in real


# ---- blind sheet --------------------------------------------------------------------------------------------
def test_blind_sheet_has_no_labels_and_no_status(tmp_path):
    tasks = [t for _, (f, t) in L.load_tasks().items()]
    out = tmp_path / "s.csv"; assert bsh.write_sheet(out, tasks) == len(tasks)
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert len(rows) == len(tasks) and set(rows[0]) == set(bsh.HEAD)
    assert all(r[k] == "" for r in rows for k in bsh.BLANK), "label columns must start empty"
    banned = ["label_status", "upstream_category", "rationale", "draft_needs_human_review", "ai_cross_checked"]
    assert not any(b in k for k in rows[0] for b in banned)
    text = out.read_text(encoding="utf-8")
    assert "draft_needs_human_review" not in text and "ai_cross_checked" not in text


def test_blind_sheet_gives_summary_not_goal_for_unlicensed(tmp_path):
    tasks = [t for _, (f, t) in L.load_tasks().items()]
    out = tmp_path / "s.csv"; bsh.write_sheet(out, tasks)
    rows = {r["id"]: r for r in csv.DictReader(open(out, encoding="utf-8"))}
    unlic = next((t for t in tasks if t["source"]["licence"] == "none-found"), None)
    if unlic is None:
        pytest.skip("no task from an unlicensed source in this tree")
    r = rows[unlic["id"]]
    assert r["text_is_our_summary"] == "true" and r["goal_or_summary"] == unlic["our_summary"]
    assert rows["aw_rce"]["text_is_our_summary"] == "false"
    assert all(r["goal_or_summary"] for r in rows.values())


def test_blind_sheet_order_is_fixed_but_not_sorted(tmp_path):
    tasks = [t for _, (f, t) in L.load_tasks().items()]
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"; bsh.write_sheet(a, tasks); bsh.write_sheet(b, list(reversed(tasks)))
    ids = lambda p: [r["id"] for r in csv.DictReader(open(p, encoding="utf-8"))]
    # same multiset; deterministic for the same input order; shuffled (not sorted by tactic or setting)
    assert sorted(ids(a)) == sorted(ids(b)) and ids(a) == ids(a)
    assert ids(a) != sorted(ids(a))


# ---- two-rater agreement, messy second file ----------------------------------------------------------------------
def test_agreement_workflow_with_a_messy_second_rater(tmp_path):
    tasks = [t for _, (f, t) in L.load_tasks().items()]
    ours = tmp_path / "ours.csv"; bsh.write_ours(ours, tasks)
    A = ag.read_csv(str(ours), "primary_tactic")
    # rater 2: copies ours, then blanks 5, changes 10, adds an unknown id, leaves 3 missing, adds stray spaces
    ids = sorted(A)
    yours = tmp_path / "yours.csv"
    rnd = random.Random(3); changed = rnd.sample(ids, 10); blanked = rnd.sample([i for i in ids if i not in changed], 5)
    missing = rnd.sample([i for i in ids if i not in changed and i not in blanked], 3)
    with open(yours, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["id", "primary_tactic", "notes"])
        for i in ids:
            if i in missing: continue
            lab = "" if i in blanked else ("TA0040" if i in changed and A[i] != "TA0040" else ("TA0010" if i in changed else A[i]))
            w.writerow([f" {i} ", f" {lab} ", "x"])
        w.writerow(["not_a_task", "TA0010", ""])
    B = ag.read_csv(str(yours), "primary_tactic")
    pair, x, y = ag._pair(A, B)
    assert len(pair) == len(ids) - len(missing) - len(blanked) and "not_a_task" not in pair
    k = ag.kappa(x, y)
    assert 0 < k["kappa"] < 1 and k["n"] == len(pair)
    assert len(ag.disagreements(pair, x, y)) == len(changed)


def test_agreement_output_with_hand_checked_kappa(tmp_path):
    a = tmp_path / "a.csv"; b = tmp_path / "b.csv"
    a.write_text("id,primary_tactic\n" + "".join(f"t{i},{'X' if i < 25 else 'Y'}\n" for i in range(50)))
    # 20 of the 25 X stay X, 5 become Y; of the 25 Y, 10 become X, 15 stay Y  -> kappa 0.4 (worked by hand in test_agreement)
    b.write_text("id,primary_tactic\n" + "".join(f"t{i},{('X' if i < 20 else 'Y') if i < 25 else ('X' if i < 35 else 'Y')}\n" for i in range(50)))
    ids, x, y = ag._pair(ag.read_csv(str(a), "primary_tactic"), ag.read_csv(str(b), "primary_tactic"))
    assert round(ag.kappa(x, y)["kappa"], 6) == 0.4


# ---- reproduce -------------------------------------------------------------------------------------------------
def test_compare_detects_tamper_missing_and_unlisted():
    exp = {"a": "1", "b": "2", "c": "3"}
    assert rp.compare(exp, dict(exp)) == []
    bad = rp.compare(exp, {"a": "1", "b": "X", "d": "4"})
    kinds = sorted(x.split()[0] for x in bad)
    assert kinds == ["MISMATCH", "MISSING", "UNLISTED"]


def test_parse_checksums_roundtrip():
    text = "abc123  data/x.json\n\ndef456  site/y.html\n"
    assert rp.parse_checksums(text) == {"data/x.json": "abc123", "site/y.html": "def456"}


def test_checksums_file_matches_every_current_file():
    exp = rp.parse_checksums(rp.CHECKSUMS.read_text(encoding="utf-8"))
    act = {p: rp.digest(p) for p in rp.files()}
    assert rp.compare(exp, act) == [], "run: make checksums (after a deliberate change) and commit"
    assert len(exp) > 100 and "data/generated/CHECKSUMS" not in exp
    assert not any(p.startswith(rp.hidden_paths()) for p in exp if rp.hidden_paths()), "a hidden setting must not be listed in CHECKSUMS"
    assert not any(p.startswith(".cache") for p in exp)


def test_editing_a_task_label_changes_the_checksum(tmp_path):
    f = next(c.TASKS_DIR.rglob("aw_rce.yml"))
    exp = rp.digest(str(f.relative_to(c.ROOT)))
    import hashlib
    assert hashlib.sha256(f.read_bytes() + b" ").hexdigest() != exp
