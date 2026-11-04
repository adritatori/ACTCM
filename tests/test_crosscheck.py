"""Cross-check decision logic on clean and messy input."""
import pytest
import crosscheck as cc
import labels as L


def ours(p="TA0010", tech="T1048", steps=("TA0006",), conf="clear", atlas=None):
    d = {"attack": {"primary_tactic": p, "technique": tech, "required_step_tactics": list(steps)}, "confidence": conf}
    if atlas:
        d["atlas"] = {"technique": atlas}
    return d


def blind(primary="TA0010", technique="T1048", steps=("TA0006",), conf="clear", atlas=None):
    return {"primary": primary, "technique": technique, "steps": list(steps), "confidence": conf, "atlas": atlas}


def q(o, b):
    return cc.qualifies(cc.compare(o, b))[0]


def test_clean_agreement_qualifies():
    assert q(ours(), blind())


def test_noise_in_ids_still_matches():
    assert q(ours(), blind(primary=" ta0010 ", technique="t1048 ", conf=" Clear "))


def test_different_tactic_never_qualifies():
    assert not q(ours(), blind(primary="TA0040"))


def test_our_ambiguous_never_qualifies_even_if_blind_agrees():
    assert not q(ours(conf="ambiguous"), blind())


def test_blind_ambiguous_does_not_qualify():
    assert not q(ours(), blind(conf="ambiguous"))


def test_sub_technique_vs_parent_is_family_match():
    assert cc.technique_match("T1565.001", "T1565") == "family"
    assert q(ours("TA0040", "T1565.001", ()), blind("TA0040", "T1565", ()))


def test_sibling_subtechniques_are_family():
    assert cc.technique_match("T1565.001", "T1565.002") == "family"


def test_different_technique_same_tactic_blocks():
    assert not q(ours(), blind(technique="T1567"))


@pytest.mark.parametrize("nullish", [None, "", "null", "None", "N/A", "~"])
def test_null_strings_count_as_null(nullish):
    assert q(ours(tech=None), blind(technique=nullish))
    assert cc.technique_match(None, nullish) == "both_null"


def test_one_sided_null_blocks():
    assert not q(ours(tech=None), blind(technique="T1048"))
    assert not q(ours(), blind(technique=None))


def test_missing_blind_or_ours_blocks():
    assert not q(ours(), None)
    assert not q(None, blind())
    assert not q({}, blind())


def test_empty_primary_never_agrees_even_with_empty_ours():
    assert not q(ours(p=None), blind(primary=None))
    assert not q(ours(p=""), blind(primary=""))


def test_steps_and_atlas_do_not_block_but_are_recorded():
    cmp = cc.compare(ours(steps=("TA0006", "TA0003"), atlas="AML.T0025"), blind(steps=("TA0006",), atlas=None))
    assert cc.qualifies(cmp)[0] and cmp["steps_jaccard"] == 0.5 and cmp["atlas_match"] is False


def test_steps_string_forms():
    assert cc.norm_steps("TA0006; ta0003,TA0006") == ["TA0003", "TA0006"]
    assert cc.norm_steps(None) == [] and cc.jaccard([], None) == 1.0


def test_atlas_with_name_suffix_is_normalised():
    assert cc.norm_id("AML.T0059 Erode Dataset Integrity") == "AML.T0059"
    assert cc.compare(ours(atlas="AML.T0059"), blind(atlas="AML.T0059 Erode Dataset Integrity"))["atlas_match"]


def test_blind_entry_validation_catches_bad_ids():
    import frameworks as f
    fw = f.load()
    assert cc.blind_entry_errors(blind(), fw) == []
    bad = cc.blind_entry_errors(blind(primary="Exfiltration", technique="T9999", steps=("TA9",), conf="maybe", atlas="AML.T9"), fw)
    assert len(bad) >= 5
    assert cc.blind_entry_errors(blind(primary="TA0005", technique="T1070"), fw) == []


# ---- the tier guard
def test_bot_cannot_set_reviewed_or_adjudicated():
    for who in ["claude_draft_2026-11-04", "claude_crosscheck", "script", "AI", "", None, "Some Bot", "GPT-9"]:
        for st in ("reviewed", "adjudicated"):
            with pytest.raises(L.StatusError):
                L.check_status_change(st, who)


def test_unlisted_human_cannot_set_reviewed():
    with pytest.raises(L.StatusError):
        L.check_status_change("reviewed", "Jane Doe")


def test_listed_human_can_and_bot_can_set_cross_checked():
    L.check_status_change("reviewed", "Adrita Rahman Tory")
    L.check_status_change("ai_cross_checked", "claude_crosscheck_2026-11-04")
    with pytest.raises(L.StatusError):
        L.check_status_change("approved", "Adrita Rahman Tory")


def test_set_status_writes_history():
    t = {"label_status": "draft_needs_human_review", "history": []}
    L.set_status(t, "ai_cross_checked", "claude_crosscheck", "blind agreed", "same tactic", "2026-11-04")
    assert t["label_status"] == "ai_cross_checked" and t["history"][0]["who"] == "claude_crosscheck"


def test_planned_scorer_is_never_promoted_even_when_everything_agrees():
    cmp = cc.compare(ours(), blind())
    assert cc.qualifies(cmp)[0] is True
    ok, why = cc.qualifies(cmp, {"scorer_status": "planned_not_implemented"})
    assert ok is False and "planned" in why
    assert cc.qualifies(cmp, {"scorer_status": "implemented_or_not_flagged"})[0] is True
    assert cc.qualifies(cmp, {})[0] is True      # missing field must not block real tasks


def test_check_labels_rejects_cross_checked_planned_scorer():
    import check_labels as cl, frameworks as f
    t = {"id": "x", "label_status": "ai_cross_checked", "scorer_status": "planned_not_implemented", "cross_check": {"q": 1},
         "labels": {"attack": {"primary_tactic": "TA0010", "technique": "T1048", "required_step_tactics": []},
                    "confidence": "clear", "alternative": None, "rationale": "r"}}
    errs, _ = cl.check_task(t, f.load())
    assert any("planned, not built" in e for e in errs)
