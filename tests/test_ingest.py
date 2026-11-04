"""Phase 1 tests: parser behaviour on messy input, plus data invariants on the built task files."""
import re
import pytest
import common as c
import ingest

from ingest import EXPECTED   # the expected counts live in one place (scripts/ingest.py)


# ---- parse_init on adversarial source text -------------------------------------------------
def test_parse_clean():
    src = 'config = make_side_task_from_path(p, failure_type="live", task_category="exfiltration", scorer=s)'
    r = ingest.parse_init(src)
    assert (r["task_category"], r["failure_type"], r["parse_note"]) == ("exfiltration", "live", None)


def test_parse_missing_file():
    assert ingest.parse_init(None)["parse_note"] == "no __init__.py"


def test_parse_syntax_error_is_reported_not_raised():
    assert "syntax error" in ingest.parse_init("def (:")["parse_note"]


def test_parse_non_literal_is_not_guessed():
    r = ingest.parse_init('CAT = "exfiltration"\nconfig = make_side_task_from_path(p, task_category=CAT, failure_type="live")')
    assert r["task_category"] is None and "not a literal" in r["parse_note"]
    assert r["failure_type"] == "live"


def test_parse_distractor_strings_and_comments_ignored():
    src = ('# task_category="exfiltration"\n"""failure_type="live" task_category="exfiltration" """\n'
           'x = dict(task_category="wrong")\n'
           'config = make_side_task_from_path(p, task_category="data_tampering", failure_type="delayed")')
    r = ingest.parse_init(src)
    assert (r["task_category"], r["failure_type"]) == ("data_tampering", "delayed")


def test_parse_no_call():
    assert "not found" in ingest.parse_init("x = 1")["parse_note"]


def test_parse_attribute_call_form():
    r = ingest.parse_init('config = task.make_side_task_from_path(p, task_category="other", failure_type="delayed")')
    assert r["task_category"] == "other"


# ---- data invariants -------------------------------------------------------------------------
@pytest.fixture(scope="module")
def tasks():
    return [c.load_yaml(f) for f in sorted(c.TASKS_DIR.rglob("*.yml"))]


def test_counts_per_setting(tasks):
    got = {s: sum(t["setting"] == s for t in tasks) for s in EXPECTED}
    assert got == EXPECTED


def test_ids_unique(tasks):
    ids = [t["id"] for t in tasks]
    assert len(ids) == len(set(ids))


def test_licence_rule(tasks):
    for t in tasks:
        if t["source"]["licence"] == "none-found":
            assert t["goal_text"] is None, t["id"]
            n = len(t["our_summary"].split())
            assert 0 < n <= 20, (t["id"], n)
        else:
            assert t["our_summary"] is None
            assert t["upstream_status"] == "discovered" and t["goal_text"], t["id"]


def test_no_bot_set_reviewed(tasks):
    assert all(t["label_status"] in ("unlabelled", "draft_needs_human_review", "ai_cross_checked") for t in tasks)
    assert not any(t["label_status"] in ("reviewed", "adjudicated") or t.get("reviewed_by") for t in tasks)


def test_sha_pinned_in_lock(tasks):
    lock = c.load_yaml(c.LOCK_FILE)
    pinned = {(s["repo"], s["sha"]) for s in lock["sources"]}
    assert all((t["source"]["repo"], t["source"]["sha"]) in pinned for t in tasks)
    assert all(re.fullmatch(r"[0-9a-f]{40}", t["source"]["sha"]) for t in tasks)


def test_all_env_tags_resolve_to_locked_sha():
    lock = c.load_yaml(c.LOCK_FILE)
    assert all(s["tag_resolves_to_sha"] for s in lock["sources"])


def test_source_paths_exist_at_pinned_sha(tasks):
    probe = c.CACHE / "auto_workflow"
    if not probe.exists():
        pytest.skip("source cache not fetched; run scripts/ingest.py build")
    assert ingest.cmd_check()


def test_unfinished_drafts_excluded_but_listed(tasks):
    if not ingest.UNFINISHED_FILE.exists() or not c.load_yaml(ingest.UNFINISHED_FILE)["tasks"]:
        pytest.skip("no unfinished upstream drafts in this tree")
    u = c.load_yaml(ingest.UNFINISHED_FILE)["tasks"]
    assert all(x["id"].endswith("_idea") for x in u)
    assert all(x["flag"] == "unfinished_upstream" for x in u)
    assert not any(t["id"].endswith("_idea") for t in tasks)
    assert len(tasks) == sum(EXPECTED.values())
