import yaml
import common as c
import labels as L


def cfg():
    return yaml.safe_load((c.DATA / "status_tiers.yml").read_text())


def test_tier_ids_match_code_and_order():
    assert [t["id"] for t in cfg()["tiers"]] == L.TIERS == ["draft_needs_human_review", "ai_cross_checked", "reviewed", "adjudicated"]


def test_ai_cross_checked_wording_never_claims_review():
    t = next(t for t in cfg()["tiers"] if t["id"] == "ai_cross_checked")
    plain = t["plain"].lower()
    assert "no human has checked" in plain
    for bad in cfg()["never_say_for_ai_cross_checked"]:
        assert bad not in plain and bad not in t["label"].lower()


def test_only_humans_listed_for_human_tiers():
    for t in cfg()["tiers"]:
        if t["id"] in L.HUMAN_ONLY:
            assert "human" in t["who_may_set"].lower()
        else:
            assert "human" not in t["who_may_set"].lower() or "only" not in t["who_may_set"].lower()


def test_step_tier_ids_match_code_and_order():
    assert [t["id"] for t in cfg()["step_tiers"]] == L.STEP_TIERS
    assert "ai_cross_checked" not in L.STEP_TIERS


def test_evidence_checked_wording_never_claims_review():
    t = next(t for t in cfg()["step_tiers"] if t["id"] == "evidence_checked")
    plain = t["plain"].lower()
    assert "no human has checked" in plain
    assert cfg()["never_say_for_evidence_checked"] == ["reviewed", "verified", "validated", "confirmed", "approved"]
    for bad in cfg()["never_say_for_evidence_checked"]:
        assert bad not in plain and bad not in t["label"].lower()
    assert "script only" in t["who_may_set"].lower()


def test_task_tier_never_say_list_is_unchanged():
    assert cfg()["never_say_for_ai_cross_checked"] == ["reviewed", "verified", "validated", "confirmed", "approved"]


def test_only_humans_listed_for_human_step_tiers():
    for t in cfg()["step_tiers"]:
        assert ("human" in t["who_may_set"].lower()) == (t["id"] in L.HUMAN_ONLY)
