"""No upstream text from unlicensed sources (the four extras envs) may appear in our files.

Compares every run of 6 consecutive words in the upstream goal/scorer text with everything we publish.
"""
import re
import pytest
import common as c


def words(s):
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def test_no_six_word_overlap_with_unlicensed_upstream_text():
    lock = c.load_yaml(c.LOCK_FILE)
    ours = []
    for root in ("data", "docs", "codebook", "README.md"):
        p = c.ROOT / root
        files = [p] if p.is_file() else [x for x in p.rglob("*") if x.is_file() and x.suffix in (".yml", ".yaml", ".md", ".csv", ".json")]
        for f in files:
            ours += words(f.read_text(encoding="utf-8", errors="ignore"))
    ours_set = {" ".join(ours[i:i + 6]) for i in range(len(ours) - 5)}
    checked = 0
    all_hits = []
    for s in lock["sources"]:
        if s["licence"]["spdx"]:
            continue
        d = c.CACHE / s["repo"].split("/")[1]
        if not d.exists():
            pytest.skip("source cache not fetched")
        for n in c.ls_tree(d, s["sha"], s["side_tasks_root"], dirs_only=True):
            for rel in ("docs/goal.md", "docs/scoring_details.md", "docs/scorer.md", "info.yml", "requirements.md"):
                t = c.show(d, s["sha"], f"{s['side_tasks_root']}/{n}/{rel}")
                if not t:
                    continue
                w = words(t)
                hits = [" ".join(w[i:i + 6]) for i in range(len(w) - 5) if " ".join(w[i:i + 6]) in ours_set]
                if hits:
                    all_hits.append(f"{s['environment']}/{n}/{rel}: {hits[:2]}")
                checked += 1
    assert not all_hits, all_hits
    if checked == 0:
        pytest.skip("no source without a licence in this tree, so there is nothing to compare")
