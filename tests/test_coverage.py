"""The coverage join on made-up messy cases, then against an independent recomputation on the real files."""
import json

import yaml

import common as c
import coverage as cov
import validate_incidents as vi

FX = yaml.safe_load((c.ROOT / "tests" / "fixtures" / "coverage_cases.yml").read_text(encoding="utf-8"))
PUBLIC = [t for t in FX["tasks"] if c.is_public_setting(t["setting"])]
GEN = c.DATA / "generated" / "incident_coverage.json"


def test_fixture_hides_the_extras_task():
    assert not c.publish_extras()
    assert [t["uid"] for t in PUBLIC] == ["syn/a", "syn/b", "syn/d", "syn/e", "syn/f"]


def test_synthetic_verdicts():
    for s in FX["steps"]:
        r = cov.judge_step(s, PUBLIC)
        if s["expect"] is None:
            assert r is None, s["id"]
            continue
        assert r["verdict"] == s["expect"], (s["id"], r)
        if "uids" in s:
            assert r["technique_task_uids"] == s["uids"], s["id"]
        if "n_goal" in s:
            assert (r["tasks_tactic_as_goal"], r["tasks_tactic_as_step"]) == (s["n_goal"], s["n_step"]), (s["id"], r)
        if "stable" in s:
            assert r["verdict_stable"] is s["stable"], (s["id"], r)


def test_goal_and_step_counts_are_never_merged():
    r = cov.judge_step(FX["steps"][2], PUBLIC)          # TA0006: 0 goals, 2 tasks state it as a step
    assert r["tasks_tactic_as_goal"] == 0 and r["tasks_tactic_as_step"] == 2
    assert r["tactic_goal_task_uids"] == [] and r["tactic_step_task_uids"] == ["syn/a", "syn/f"]   # syn/f once, though it repeats the tactic


def test_hidden_task_never_appears_even_as_a_match():
    out = json.dumps([cov.judge_step(s, PUBLIC) for s in FX["steps"]])
    assert "hidden/c" not in out
    with_hidden = cov.judge_step(FX["steps"][3], FX["tasks"])     # if extras were public the verdict would differ
    assert with_hidden["verdict"] == "tested_technique"


def test_unclear_keeps_both_verdicts():
    r = cov.judge_step(FX["steps"][6], PUBLIC)
    assert r["verdict"] == "unclear" and r["verdict_primary"] == "not_tested" and r["verdict_alternative"] == "tested_technique"


def test_parent_level():
    assert cov.parent("T1048.003") == "T1048" and cov.parent("T1048") == "T1048" and cov.parent(None) is None


# ---- real data ----
def _independent():
    """A second, deliberately plain implementation. Shares no code with coverage.py."""
    tasks = []
    for f in c.public_task_files():
        t = c.load_yaml(f)
        a = (t.get("labels") or {}).get("attack")
        if a:
            tasks.append((a["primary_tactic"], (a["technique"] or "").split(".")[0], set(a["required_step_tactics"])))
    out = {}
    for f in vi.incident_files():
        inc = c.load_yaml(f)
        for s in inc["steps"]:
            if s["phase"] != "attack":
                continue
            def one(tac, tech):
                tech = (tech or "").split(".")[0]
                if tech and any(t[1] == tech for t in tasks):
                    return "tested_technique"
                if any(t[0] == tac or tac in t[2] for t in tasks):
                    return "tested_tactic_only"
                return "not_tested"
            a = s["attack"]
            v = one(a["primary_tactic"], a["technique"])
            alt = a.get("alternative")
            if a["confidence"] == "ambiguous" and alt and one(alt["tactic"], alt.get("technique")) != v:
                v = "unclear"
            out[(inc["id"], s["id"])] = v
    return out


def test_generated_file_matches_an_independent_recomputation():
    gen = json.loads(GEN.read_text(encoding="utf-8"))
    mine = _independent()
    theirs = {(i["id"], s["id"]): s["verdict"] for i in gen["incidents"] for s in i["steps"] if s["phase"] == "attack"}
    assert mine == theirs
    for i in gen["incidents"]:
        counts = {v: sum(1 for k, x in mine.items() if k[0] == i["id"] and x == v) for v in cov.VERDICTS}
        assert i["verdict_counts"] == counts
        assert i["attack_steps"] == sum(counts.values())
    assert gen["totals"]["attack_steps"] == len(mine)
    assert gen["totals"]["verdict_counts"] == {v: sum(1 for x in mine.values() if x == v) for v in cov.VERDICTS}
    for row in gen["tactics"]:
        assert row["incident_steps"] == sum(row["steps_by_verdict"].values())


def test_generated_file_is_current_and_deterministic():
    a = cov.render(cov.build())
    assert a == cov.render(cov.build())
    assert a == GEN.read_text(encoding="utf-8"), "run `make build` and commit data/generated/incident_coverage.json"
    assert "generated_at" not in a and "linuxarena-extras" not in a


def test_tactic_table_matches_counts_json():
    gen = json.loads(GEN.read_text(encoding="utf-8"))
    cn = json.loads((c.DATA / "generated" / "counts.json").read_text(encoding="utf-8"))
    assert [t["id"] for t in gen["tactics"]] == [t["id"] for t in cn["tactics"]]
    for g, k in zip(gen["tactics"], cn["tactics"]):
        assert g["tasks_as_goal"] == k["primary"]["all"], g["id"]


def test_prediction_block_is_computed_not_typed():
    gen = json.loads(GEN.read_text(encoding="utf-8"))
    p = gen["prediction"]
    assert p["tactics"] == ["TA0043", "TA0042", "TA0007", "TA0008"]
    n = sum(1 for i in gen["incidents"] for s in i["steps"] if s["phase"] == "attack" and s["primary_tactic"] in p["tactics"])
    assert p["steps_in_these_tactics"] == n
    assert p["result"] in ("held", "partly_held", "failed")


def test_activity_feed_comes_from_history_fields():
    act = json.loads((c.DATA / "generated" / "activity.json").read_text(encoding="utf-8"))
    n = sum(len(s["history"]) for f in vi.incident_files() for s in c.load_yaml(f)["steps"])
    assert sum(r["steps"] for r in act["entries"]) == n
    assert act["entries"] == sorted(act["entries"], key=lambda r: (r["date"], r["incident"], r["change"]), reverse=True)
