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
