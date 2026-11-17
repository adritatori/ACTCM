"""Incident validator on made-up, messy cases (tests/fixtures/synthetic_incidents.yml) and on the real files."""
import copy

import pytest
import yaml

import common as c
import frameworks as fwm
import validate_incidents as vi

FX = yaml.safe_load((c.ROOT / "tests" / "fixtures" / "synthetic_incidents.yml").read_text(encoding="utf-8"))
FW = fwm.load()
SOURCES = {s["id"]: s for s in FX["sources"]}


def merge(base, patch):
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if v == "__DELETE__":
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def clean(obj):   # apply "__DELETE__" inside list items too
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items() if v != "__DELETE__"}
    if isinstance(obj, list):
        return [clean(x) for x in obj]
    return obj


@pytest.mark.parametrize("case", FX["cases"], ids=[x["name"] for x in FX["cases"]])
def test_synthetic_incident(case):
    inc = clean(merge(FX["base"], case["patch"]))
    errs, warns = vi.validate_incident(inc, SOURCES, FW)
    if case["expect"] == "valid":
        assert not errs, errs
    else:
        assert errs, "expected an error"
        if "error_has" in case:
            assert any(str(case["error_has"]).lower() in e.lower() for e in errs), errs
    if "warn_has" in case:
        assert any(case["warn_has"].lower() in w.lower() for w in warns), warns
    if "check_claims" in case:
        assert len(inc["agent_count_claims"]) == case["check_claims"]
        assert len({x["claim"] for x in inc["agent_count_claims"]}) == case["check_claims"]


def test_registry_fixture_is_valid():
    assert vi.validate_sources(FX["sources"]) == []


@pytest.mark.parametrize("case", FX["bad_registries"], ids=[x["name"] for x in FX["bad_registries"]])
def test_bad_registry(case):
    errs = vi.validate_sources([case["source"]])
    assert any(case["error_has"].lower() in e.lower() for e in errs), errs


def test_duplicate_source_ids():
    assert any("duplicate" in e for e in vi.validate_sources([FX["sources"][0], FX["sources"][0]]))


def test_bst_and_other_zones_convert_to_utc():
    assert vi.local_to_utc("2026-07-28", "12:23 BST") == "2026-07-28T11:23Z"
    assert vi.local_to_utc("2026-07-28", "00:30 BST") == "2026-07-27T23:30Z"     # crosses midnight
    assert vi.local_to_utc("2026-07-28", "02:28 UTC") == "2026-07-28T02:28Z"
    assert vi.local_to_utc("2026-07-28", "09:00 UTC+2") == "2026-07-28T07:00Z"
    assert vi.local_to_utc("2026-07-28", "around noon") is None                    # not parseable: no guess


def test_real_incident_files_validate():
    errs, warns, n = vi.validate_all()
    assert not errs, errs


def test_real_quotes_and_text_limits():
    for f in vi.incident_files():
        inc = c.load_yaml(f)
        assert len(inc["summary"].split()) <= 60
        for s in inc["steps"]:
            assert len(s["evidence"]["quote"].split()) <= 25, (f.name, s["id"])
            assert len(s["what_happened"].split()) <= 40, (f.name, s["id"])
            assert s["label_status"] in ("draft_needs_human_review", "evidence_checked"), "no human has reviewed steps yet"
            assert s["reviewed_by"] is None
