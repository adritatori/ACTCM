"""Layer validation on good and messy layers."""
import copy
import json
import pytest
import common as c
import frameworks as f
import navigator as N
import build as B

FW = f.load()
GOOD = json.loads((N.OUT / "actcm_combined_attack_v20.json").read_text())


def mutate(**kw):
    L = copy.deepcopy(GOOD)
    for k, v in kw.items():
        if v == "__DEL__":
            L.pop(k, None)
        else:
            L[k] = v
    return L


def test_all_layers_valid_and_complete():
    names = sorted(p.name for p in N.OUT.glob("actcm_*.json"))
    assert names == sorted(f"actcm_{k}_attack_v20.json" for k in ["combined"] + c.visible_settings())
    if not c.publish_extras():
        assert not any("extras" in n for n in names), "hidden setting must have no layer"
    for p in N.OUT.glob("actcm_*.json"):
        L = json.loads(p.read_text())
        assert N.validate_layer(L, FW) == [], p.name
        assert L["domain"] == "enterprise-attack" and L["versions"]["layer"] == "4.5" and L["versions"]["attack"] == "20"
        assert any("gap" in i["label"] for i in L["legendItems"])


def test_scores_match_build_counts():
    cn = json.loads((c.DATA / "generated" / "counts.json").read_text())
    L = json.loads((N.OUT / "actcm_combined_attack_v20.json").read_text())
    assert sum(t["score"] for t in L["techniques"]) == cn["totals"]["tasks"] - len(cn["tasks_with_null_technique"])
    scored = {(t["techniqueID"], t["tactic"]): t["score"] for t in L["techniques"] if t["score"]}
    short = {x["id"]: x["shortname"] for x in FW["attack"]["tactics"]}
    for r in cn["techniques"]:
        assert scored[(r["id"], short[r["tactic"]])] == r["count"]


def test_comment_lists_task_ids_for_scored_only():
    for t in GOOD["techniques"]:
        assert (t["comment"] != "") == (t["score"] > 0)


def test_no_platform_filter_that_could_hide_techniques():
    assert "filters" not in GOOD


@pytest.mark.parametrize("bad,frag", [
    (dict(gradient=dict(colors=["#000000", "#ffffff"], minValue=5, maxValue=5)), "must be greater than"),
    (dict(gradient=dict(colors=["#000000", "#ffffff"], minValue=9, maxValue=1)), "must be greater than"),
    (dict(gradient=dict(colors=["#000000"], minValue=0, maxValue=1)), "at least 2"),
    (dict(gradient=dict(colors=["red", "blue"], minValue=0, maxValue=1)), "at least 2"),
    (dict(gradient=dict(colors=["#000000", "#ffffff"], minValue="0", maxValue=1)), "numbers"),
    (dict(legendItems=[dict(label="x")]), "color"),
    (dict(legendItems=[dict(color="#ffffff")]), "label"),
    (dict(legendItems=[dict(label="x", color="white")]), "color"),
    (dict(name=""), "name is required"),
    (dict(name="__DEL__"), "name is required"),
    (dict(domain="enterprise"), "domain"),
    (dict(versions=dict(attack="20", navigator="4.8.0", layer="4.5")), "at least 4.9.0"),
    (dict(versions=dict(attack="20", navigator="5", layer="4.5")), "at least 4.9.0"),
    (dict(versions=dict(attack="20", navigator="5.3.2", layer="4.4")), "versions.layer"),
    (dict(techniques=[]), "non-empty"),
    (dict(techniques="T1048"), "non-empty"),
    (dict(techniques=[dict(techniqueID="T9999", tactic="exfiltration", score=1)]), "not an active technique"),
    (dict(techniques=[dict(techniqueID="T1048", tactic="impact", score=1)]), "not one of its"),
    (dict(techniques=[dict(techniqueID="1048", score=1)]), "invalid"),
    (dict(techniques=[dict(techniqueID="T1048", tactic="exfiltration", score="3")]), "score must be a number"),
    (dict(techniques=[dict(techniqueID="T1048", tactic="exfiltration", score=True)]), "score must be a number"),
    (dict(techniques=[dict(techniqueID="T1048", tactic="exfiltration", score=1, color="blue")]), "not #rrggbb"),
    (dict(techniques=[dict(techniqueID="T1048", tactic="exfiltration", score=1), dict(techniqueID="T1048", tactic="exfiltration", score=2)]), "duplicate"),
    (dict(sorting=7), "sorting"),
    (dict(layout=dict(layout="wide")), "layout.layout"),
    (dict(links=[dict(label="x", url="github.com/x")]), "protocol"),
    (dict(metadata=[dict(name="a", value=5)]), "string name and value"),
    (dict(hideDisabled="no"), "boolean"),
])
def test_bad_layers_are_caught(bad, frag):
    errs = N.validate_layer(mutate(**bad), FW)
    assert any(frag in e for e in errs), errs


def test_non_object_layer():
    assert N.validate_layer([], FW) and N.validate_layer(None, FW)


def test_empty_setting_still_valid_gradient():
    L = N.build_layer([], FW, "empty", "none")
    assert L["gradient"]["maxValue"] > L["gradient"]["minValue"]
    assert N.validate_layer(L, FW) == []
    assert all(t["score"] == 0 for t in L["techniques"])


def test_links_use_layerurl_parameter_and_are_marked_pending():
    links = json.loads((N.OUT / "links.json").read_text())
    assert len(links) == 1 + len(c.visible_settings())
    for l in links:
        assert "#layerURL=" in l["open_in_navigator"] and "raw.githubusercontent.com" in l["open_in_navigator"].replace("%2F", "/").replace("%3A", ":")
        assert ("loaded from this repository" if c.config().get("published") else "after the repository is published") in l["status"]


def test_description_carries_branding_and_warning():
    d = GOOD["description"]
    assert d.index("MITRE ATT&CK®") >= 0 and "Not affiliated with or endorsed by The MITRE Corporation." in d
    assert "tested, not what is caught" in d and "PROVISIONAL" in d


@pytest.mark.parametrize("junk", [dict(techniques=[5, None, "x"]), dict(legendItems="x"), dict(legendItems=[1]), dict(metadata=7),
                                  dict(links=[None]), dict(layout="side"), dict(gradient="red"), dict(versions="4.5")])
def test_wrong_types_give_errors_not_crashes(junk):
    assert N.validate_layer(mutate(**junk), FW)   # must report an error, not raise
