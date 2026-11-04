"""Phase 2 tests: framework tables, pin integrity, and the technique validity check on messy input."""
import hashlib
import pytest
import common as c
import frameworks as f


@pytest.fixture(scope="module")
def fw():
    return f.load()


def test_attack_v20_tactics_in_matrix_order(fw):
    a = fw["attack"]
    assert a["version"] == "20.0"
    assert [t["id"] for t in a["tactics"]] == [
        "TA0043", "TA0042", "TA0001", "TA0002", "TA0003", "TA0004", "TA0005", "TA0112",
        "TA0006", "TA0007", "TA0008", "TA0009", "TA0011", "TA0010", "TA0040"]


def test_attack_v20_stealth_and_defense_impairment_no_defense_evasion(fw):
    names = {t["id"]: t["name"] for t in fw["attack"]["tactics"]}
    assert names["TA0005"] == "Stealth" and names["TA0112"] == "Defense Impairment"
    assert "Defense Evasion" not in names.values()


def test_atlas_2026_10_counts(fw):
    l = fw["atlas"]
    assert l["version"] == "2026.10" and len(l["tactics"]) == 16 and len(l["techniques"]) == 221
    assert all(t["tactics"] for t in l["techniques"].values())


def test_every_active_attack_technique_has_a_known_tactic(fw):
    ids = {t["id"] for t in fw["attack"]["tactics"]}
    for k, t in fw["attack"]["techniques"].items():
        if not t["revoked"] and not t["deprecated"]:
            assert t["tactics"] and set(t["tactics"]) <= ids, k


def test_pinned_files_match_lock_checksums():
    lock = c.load_yaml(c.LOCK_FILE)["frameworks"]
    for key, spec in (("attack", f.ATTACK), ("atlas", f.ATLAS)):
        p = f.FW_CACHE / spec["path"].split("/")[-1]
        if not p.exists():
            pytest.skip("framework cache missing; run scripts/frameworks.py fetch")
        assert hashlib.sha256(p.read_bytes()).hexdigest() == lock[key]["sha256"]


def test_lock_records_pins():
    lock = c.load_yaml(c.LOCK_FILE)["frameworks"]
    assert lock["attack"]["version"] == "20.0" and len(lock["attack"]["sha"]) == 40
    assert lock["atlas"]["version"] == "2026.10" and len(lock["atlas"]["sha"]) == 40
    assert lock["atlas"]["licence"] == "Apache-2.0"


# ---- the "technique must not be revoked, deprecated or missing" rule, on messy input -----------
def test_valid_techniques_pass(fw):
    assert f.check_techniques(fw, "attack", ["T1048", "T1070.003", "T1685"]) == []


def test_revoked_deprecated_missing_are_caught(fw):
    t = fw["attack"]["techniques"]
    revoked = next(k for k, v in t.items() if v["revoked"])
    deprecated = next(k for k, v in t.items() if v["deprecated"] and not v["revoked"])
    errs = f.check_techniques(fw, "attack", [revoked, deprecated, "T9999"])
    assert len(errs) == 3 and "revoked" in errs[0] and "deprecated" in errs[1] and "not in" in errs[2]


@pytest.mark.parametrize("bad", ["", " T1048", "t1048", "T1048 ", "T1048.", "TA0010", "T10480", "ATTACK1048",
                                 "T1048.99", None, "AML.T0000"])
def test_malformed_ids_are_never_accepted_silently(fw, bad):
    assert f.check_techniques(fw, "attack", [bad]), repr(bad)


def test_old_defense_evasion_era_ids_do_not_pass_as_atlas(fw):
    assert f.check_techniques(fw, "atlas", ["T1048"])  # an ATT&CK ID is not an ATLAS ID
    assert f.check_techniques(fw, "atlas", ["AML.T0000"]) == []


def test_labelled_tasks_use_valid_techniques(fw):
    bad = []
    for p in c.TASKS_DIR.rglob("*.yml"):
        t = c.load_yaml(p)
        lab = t.get("labels") or {}
        tech = (lab.get("attack") or {}).get("technique")
        if tech:
            bad += f.check_techniques(fw, "attack", [tech])
        atl = (lab.get("atlas") or {}).get("technique")
        if atl:
            bad += f.check_techniques(fw, "atlas", [atl])
    assert not bad, bad
