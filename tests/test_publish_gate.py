"""The publish gate. The enforcing tests run only when PUBLISH_GATE=1 (make publish-check sets it);
the detector tests always run, so the gate cannot pass just because it is broken."""
import os

import pytest

import common as c
import export_public as ex
import publish_check as pc

GATE = os.environ.get("PUBLISH_GATE") == "1"
MARK = "TODO" + "(Tory)"          # written in two pieces so this file never trips its own scan


# ---- always on: the detector and the export mechanism work -------------------------------------------------
def test_find_todos_detects_a_marker_and_ignores_exempt_files(tmp_path):
    (tmp_path / "a.md").write_text(f"fine\n<!-- {MARK}: fill me -->\n")
    (tmp_path / "b.md").write_text("nothing here\n")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "publish_check.py").write_text(f"MARK = '{MARK}'\n")
    hits = pc.find_todos(tmp_path, ["a.md", "b.md", "scripts/publish_check.py", "missing.md"])
    assert len(hits) == 1 and hits[0].startswith("a.md:2:")


def test_find_todos_handles_binary_and_unicode(tmp_path):
    (tmp_path / "x.md").write_bytes(b"\xff\xfe\x00bad bytes")
    (tmp_path / "y.md").write_text("é ✓ ®\n")
    assert pc.find_todos(tmp_path, ["x.md", "y.md"]) == []


def test_todo_markers_exist_where_the_brief_says_until_filled():
    # these are the items Tory said she will fill; if one is filled the marker goes and this list should shrink
    need = {"CITATION.cff": 2, "LICENSE-DATA": 1, "config/publish.yml": 1}
    for path, n in need.items():
        have = (c.ROOT / path).read_text(encoding="utf-8").count(MARK)
        assert have <= n, path       # never more than expected
    hits = pc.find_todos()
    assert all(not h.startswith("tests/") for h in hits)


def test_private_block_stripping_and_scan_catch_a_leak(tmp_path):
    text = "keep\n\nafter\n"
    assert "secret" not in ex.PRIVATE_BLOCK.sub("", text) and "keep" in ex.PRIVATE_BLOCK.sub("", text)
    py = "a = 1\n\nc = 3\n"
    assert "b = 2" not in ex.PRIVATE_BLOCK.sub("", py) and "c = 3" in ex.PRIVATE_BLOCK.sub("", py)


def test_export_denies_hidden_files_and_filters_mixed_files(tmp_path):
    hid = ex.hidden_identifiers()
    if not hid["ids"]:
        pytest.skip("no hidden setting present in this tree")
    assert ex.transform("data/tasks/linuxarena-extras/x/y.yml", hid) is None
    assert ex.transform("data/summaries/extras.yml", hid) is None
    lock_out = ex.transform("data/sources.lock.yml", hid)
    assert not any(r in lock_out for r in hid["repos"]) and not any(s in lock_out for s in hid["shas"])


def test_scan_detects_a_planted_identifier(tmp_path):
    hid = ex.hidden_identifiers()
    if not hid["ids"]:
        pytest.skip("no hidden setting present in this tree")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text(f"mentions {sorted(hid['ids'])[0]} by mistake\n")
    assert ex.scan(tmp_path), "the scan must flag a hidden task id"


def test_the_real_export_is_clean(tmp_path):
    out = tmp_path / "exp"
    n, skipped = ex.export(out)
    assert n > 100
    assert ex.scan(out) == []
    if not c.publish_extras():
        assert not (out / "data" / "tasks" / "linuxarena-extras").exists()
        assert not list(out.rglob("*extras*.yml"))


# ---- enforcing: only when PUBLISH_GATE=1 -------------------------------------------------------------------------
@pytest.mark.skipif(not GATE, reason="publish gate: run `make publish-check` (sets PUBLISH_GATE=1)")
def test_gate_no_todo_left_in_public_files():
    assert pc.find_todos() == [], "fill every TODO(Tory) before publishing"


@pytest.mark.skipif(not GATE, reason="publish gate")
def test_gate_extras_hidden_and_export_clean(tmp_path):
    assert c.publish_extras() is False
    ex.export(tmp_path / "e")
    assert ex.scan(tmp_path / "e") == []
