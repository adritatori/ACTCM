"""validate.py and build.py on adversarial synthetic fixtures."""
import copy
import yaml
import pytest
import build as B
import common as c
import frameworks as f
import suggest as S
import validate as V

FW = f.load()
FIX = yaml.safe_load((c.ROOT / "tests" / "fixtures" / "synthetic_tasks.yml").read_text())


def merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        if v == "__DELETE__":
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def case_task(case):
    return merge(FIX["base"], case["patch"])


def test_at_least_twenty_fixtures():
    assert len(FIX["cases"]) >= 20
    assert sum(x["expect"] == "invalid" for x in FIX["cases"]) >= 15


@pytest.mark.parametrize("case", FIX["cases"], ids=[x["name"] for x in FIX["cases"]])
def test_fixture(case):
    errs, _ = V.validate_task(case_task(case), FW, pinned=None)
    if case["expect"] == "valid":
        assert errs == [], errs
    else:
        assert errs, "expected validation errors"
        for frag in case["errors_contain"]:
            assert any(frag in e for e in errs), (frag, errs)


def test_base_is_valid_so_each_failure_is_caused_by_its_patch():
    assert V.validate_task(FIX["base"], FW)[0] == []


def test_not_a_mapping_is_an_error_not_a_crash():
    for junk in (None, [], "text", 5):
        assert V.validate_task(junk, FW)[0]


def test_unpinned_source_is_rejected():
    errs, _ = V.validate_task(FIX["base"], FW, pinned={("other/repo", "1" * 40)})
    assert any("not in the lock file" in e for e in errs)


def test_real_tasks_validate():
    E, _, n = V.validate_all()
    assert E == [] and n == len(list(c.TASKS_DIR.rglob("*.yml")))


# ---- counting rules ---------------------------------------------------------------------------
CASES = yaml.safe_load((c.ROOT / "tests" / "fixtures" / "counting_cases.yml").read_text())["cases"]
LOCK = c.load_yaml(c.LOCK_FILE)


def mk(spec):
    return {"setting": spec["setting"], "environment": spec["environment"], "id": spec["id"],
            "label_status": "draft_needs_human_review",
            "labels": None if spec["primary"] is None else {
                "attack": {"primary_tactic": spec["primary"], "technique": spec.get("technique"),
                           "required_step_tactics": spec.get("steps", [])},
                "confidence": spec.get("confidence", "clear")}}


@pytest.mark.parametrize("case", CASES, ids=[x["name"] for x in CASES])
def test_counting_rules(case):
    tasks = [mk(s) for s in case["tasks"]]
    cn = B.build_counts(tasks, FW, LOCK)
    by = {r["id"]: r for r in cn["tactics"]}
    for tac, n in case.get("expect_primary", {}).items():
        assert by[tac]["primary"]["all"] == n, tac
    for tac, n in case.get("expect_with_steps", {}).items():
        assert by[tac]["with_steps"]["all"] == n, tac
    for tac, d in case.get("expect_primary_by_setting", {}).items():
        for s, n in d.items():
            assert by[tac]["primary"][s] == n
    if "expect_technique_rows" in case:
        assert len(cn["techniques"]) == case["expect_technique_rows"]
    if "expect_technique_tactics" in case:
        assert [t["tactic"] for t in cn["techniques"]] == case["expect_technique_tactics"]
    if "expect_null_technique" in case:
        assert len(cn["tasks_with_null_technique"]) == case["expect_null_technique"]
    for g in case.get("expect_gap_primary_contains", []):
        assert g in cn["gaps"]["primary"]
    for g in case.get("expect_gap_with_steps_excludes", []):
        assert g not in cn["gaps"]["with_steps"]
    if "expect_template_tasks" in case:
        assert cn["summary"]["template_tasks"] == case["expect_template_tasks"]
    if "expect_ambiguous" in case:
        assert cn["summary"]["ambiguous_labels"] == case["expect_ambiguous"]


def test_empty_corpus_does_not_crash_and_everything_is_a_gap():
    cn = B.build_counts([], FW, LOCK)
    assert len(cn["gaps"]["primary"]) == 15 and cn["summary"]["template_share_percent"] == 0.0


def test_real_counts_are_consistent():
    cn = c.load_yaml(c.ROOT / "data/generated/counts.json") if False else __import__("json").loads((c.DATA / "generated" / "counts.json").read_text())
    N = len(c.public_task_files())
    assert cn["totals"]["tasks"] == N == sum(r["primary"]["all"] for r in cn["tactics"])
    assert sum(r["with_steps"]["all"] for r in cn["tactics"]) >= N
    assert cn["provisional"] is True
    assert sum(cn["totals"]["by_setting"].values()) == N
    assert sum(cn["tiers"]["total"].values()) == N


# ---- the suggester is suggestion-only and fragile -----------------------------------------------
@pytest.mark.parametrize("text", [None, "", 5, "   ", "zzzz qqqq", "ÄÖÜ ✓"])
def test_suggester_never_crashes_on_junk(text):
    assert S.suggest(text) == "UNLABELED"


def test_suggester_is_fooled_by_misleading_words_which_is_why_it_is_not_a_labeller():
    # Real goal is data falsification (Impact) but the sentence mentions audit and exfiltrate.
    assert S.suggest("Falsify one invoice. Do not exfiltrate anything and keep the audit log normal.") != "TA0040"


def test_suggester_not_wired_into_any_script_that_writes_labels():
    import pathlib
    for name in ("draft_labels.py", "crosscheck.py", "review.py", "ingest.py", "labels.py", "check_labels.py"):
        src = (c.ROOT / "scripts" / name).read_text()
        assert "import suggest" not in src and "from suggest" not in src, name
    assert S.SUGGESTION_ONLY is True
