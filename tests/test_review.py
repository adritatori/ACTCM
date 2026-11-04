"""review.py on messy input: skip, junk, empty fields, quitting midway, EOF, bots."""
import copy
import subprocess
import sys

import pytest
import common as c
import frameworks as f
import labels as L
import review as rv

FW = f.load()
TORY = "Adrita Rahman Tory"


def mk(tid="t1", status="draft_needs_human_review", **lab):
    label = {"attack": {"primary_tactic": "TA0010", "technique": "T1048", "required_step_tactics": ["TA0006"]},
             "confidence": "clear", "alternative": None, "rationale": "scorer checks exfil"}
    label.update(lab)
    return {"id": tid, "setting": "vllm", "environment": "vllm", "label_status": status, "labels": label,
            "source": {"repo": "linuxarena/ct-vllm", "sha": "0" * 40, "path": f"x/{tid}/docs/goal.md"},
            "goal_text": "goal", "history": [], "reviewed_by": None, "cross_check": {"qualified": True}}


class Feed:
    def __init__(self, *answers):
        self.a = list(answers); self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if not self.a:
            raise EOFError
        x = self.a.pop(0)
        if x is KeyboardInterrupt:
            raise KeyboardInterrupt
        return x


def run(queue, *answers, **kw):
    saved, lines = {}, []
    stats = rv.run_session(queue, FW, input_fn=Feed(*answers), out=lines.append, reviewer=kw.pop("reviewer", TORY),
                           today="2026-11-05", goal_fn=lambda t: t.get("goal_text") or "",
                           scorer_fn=lambda t: "", save=lambda p, t: saved.__setitem__(p, copy.deepcopy(t)), **kw)
    return stats, saved, lines


def test_yes_sets_reviewed_with_name_date_history():
    t = mk(); s, saved, _ = run([("p1", t)], "y")
    assert s["agreed"] == 1 and t["label_status"] == "reviewed" and t["reviewed_by"] == TORY
    h = t["history"][-1]
    assert h["who"] == TORY and h["date"] == "2026-11-05" and "reviewed" in h["change"]
    assert "p1" in saved


def test_skip_changes_nothing():
    t = mk(); before = copy.deepcopy(t); s, saved, _ = run([("p", t)], "s")
    assert s["skipped"] == 1 and t == before and not saved


def test_quit_midway_saves_earlier_decisions_only():
    a, b, c3 = mk("a"), mk("b"), mk("c")
    s, saved, _ = run([("pa", a), ("pb", b), ("pc", c3)], "y", "q")
    assert s["quit"] and set(saved) == {"pa"} and b["label_status"] == "draft_needs_human_review"
    assert c3["label_status"] == "draft_needs_human_review"


def test_eof_and_ctrl_c_quit_safely():
    t = mk(); s, saved, _ = run([("p", t)])  # no answers -> EOFError
    assert s["quit"] and not saved and t["label_status"] == "draft_needs_human_review"
    t2 = mk(); s2, saved2, _ = run([("p", t2)], KeyboardInterrupt)
    assert s2["quit"] and not saved2


def test_junk_then_valid_answer():
    t = mk(); s, _, lines = run([("p", t)], "", "???", "maybe", "y")
    assert s["agreed"] == 1 and sum("not understood" in l for l in lines) == 3


def test_five_junk_answers_stop_without_change():
    t = mk(); s, saved, _ = run([("p", t)], "x1", "x2", "x3", "x4", "x5", "y")
    assert s["quit"] and not saved and t["label_status"] == "draft_needs_human_review"


def test_no_changes_to_label_on_yes():
    t = mk(); before = copy.deepcopy(t["labels"]); run([("p", t)], "y")
    assert t["labels"] == before


def test_no_new_label_with_validation_loops():
    t = mk()
    # bad tactic, tactic by name, revoked technique, technique from another tactic, valid technique,
    # too-short reason, real reason, clear
    revoked = next(k for k, v in FW["attack"]["techniques"].items() if v["revoked"])
    s, saved, lines = run([("p", t)], "n", "nonsense", "Impact", revoked, "T1048", "T1565.001", "x", "falsifies stored records", "c")
    assert s["changed"] == 1
    a = t["labels"]["attack"]
    assert a["primary_tactic"] == "TA0040" and a["technique"] == "T1565.001"
    assert t["label_status"] == "reviewed" and t["reviewed_by"] == TORY
    assert "falsifies" in t["labels"]["rationale"] and t["cross_check"]["invalidated_by_human_change"]
    assert any("revoked" in l or "missing" in l for l in lines) and any("is not in TA0040" in l for l in lines)
    assert "TA0010/T1048 -> TA0040/T1565.001" in t["history"][-1]["change"]


def test_no_with_null_technique_and_ambiguous_alternative():
    t = mk()
    s, _, _ = run([("p", t)], "n", "TA0003", "null", "no technique fits here", "a", "TA0040", "could be data change")
    assert t["labels"]["attack"]["technique"] is None and t["labels"]["confidence"] == "ambiguous"
    assert t["labels"]["alternative"]["tactic"] == "TA0040"


def test_no_cancelled_by_blank_leaves_task_untouched():
    t = mk(); before = copy.deepcopy(t)
    s, saved, _ = run([("p", t)], "n", "")
    assert s["cancelled"] == 1 and t == before and not saved
    t2 = mk(); b2 = copy.deepcopy(t2); s2, _, _ = run([("p", t2)], "n", "TA0040", "")
    assert s2["cancelled"] == 1 and t2 == b2


def test_no_then_eof_mid_way_changes_nothing():
    t = mk(); before = copy.deepcopy(t)
    s, saved, _ = run([("p", t)], "n", "TA0040", "T1565.001")  # EOF at the reason prompt
    assert s["quit"] and t == before and not saved


def test_empty_fields_do_not_crash_display():
    t = mk(); t["labels"] = {"attack": {"primary_tactic": None, "technique": None, "required_step_tactics": []},
                             "confidence": "clear"}
    t["goal_text"] = None
    s, _, lines = run([("p", t)], "s")
    assert s["shown"] == 1 and any("[empty]" in l for l in lines)
    t2 = mk(); t2["labels"] = None
    s2, _, lines2 = run([("p", t2)])
    assert s2["skipped"] == 1 and any("no label to review" in l for l in lines2)


def test_already_reviewed_is_not_shown_again_unless_asked():
    t = mk(status="reviewed"); s, _, _ = run([("p", t)], "y")
    assert s["already"] == 1 and s["shown"] == 0
    s2, _, _ = run([("p", t)], "s", redo=True)
    assert s2["shown"] == 1


@pytest.mark.parametrize("who", ["claude", "claude_draft_2026-11-04", "bot", "", "Someone Else", "AI"])
def test_non_human_or_unlisted_reviewer_is_refused_before_anything_is_shown(who):
    t = mk()
    with pytest.raises(L.StatusError):
        run([("p", t)], "y", reviewer=who)
    assert t["label_status"] == "draft_needs_human_review"


def test_real_save_is_atomic_and_readable(tmp_path):
    p = tmp_path / "t.yml"; t = mk()
    L.set_status(t, "reviewed", TORY, "x", "y", "2026-11-05"); rv.save_task(p, t)
    assert c.load_yaml(p)["label_status"] == "reviewed" and not list(tmp_path.glob("*.tmp"))


def test_script_refuses_to_run_without_a_terminal():
    r = subprocess.run([sys.executable, str(c.ROOT / "scripts" / "review.py"), "--queue", "all"],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert r.returncode == 2 and "interactive terminal" in r.stderr
