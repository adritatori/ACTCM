#!/usr/bin/env python3
"""Build review_owner.html and review_blind.html from template.html.

Reads (never writes) data/tasks/linuxarena/*/*.yml. Scorer text is fetched from the
upstream commit pinned in each task file (source.repo + source.sha) and cached.
Writes only inside review/.

    python3 review/build_kit.py [--cache DIR]

Blind build rule: AI labels are injected ONLY into the owner file. Owner-only code is
removed from the blind file at build time (not hidden), and the build fails if a
forbidden word or any AI-derived string is found in the blind output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TASKS = ROOT / "data" / "tasks" / "linuxarena"

# 15 ATT&CK Enterprise v20.0 tactics, in matrix order. "def" is the first sentence of the
# MITRE tactic description, copied from enterprise-attack-20.0.json (sha256 81113ba9...5352,
# the file pinned in data/sources.lock.yml). "note" is the codebook rule where the codebook
# defines the tactic itself (CODEBOOK.md R6); it is the only place the codebook does.
TACTICS = [
    ("TA0043", "Reconnaissance", "The adversary is trying to gather information they can use to plan future operations."),
    ("TA0042", "Resource Development", "The adversary is trying to establish resources they can use to support operations."),
    ("TA0001", "Initial Access", "The adversary is trying to get into your network."),
    ("TA0002", "Execution", "The adversary is trying to run malicious code or instructions on a system."),
    ("TA0003", "Persistence", "The adversary is trying to maintain their foothold."),
    ("TA0004", "Privilege Escalation", "The adversary is trying to gain higher-level permissions."),
    ("TA0005", "Stealth", "The adversary is trying to hide and conceal their actions, appearing as normal behavior."),
    ("TA0112", "Defense Impairment", "The adversary is trying to break security mechanisms, pipelines, and tooling so defenders can’t see or trust what’s happening."),
    ("TA0006", "Credential Access", "The adversary is trying to steal account names and passwords."),
    ("TA0007", "Discovery", "The adversary is trying to figure out your environment."),
    ("TA0008", "Lateral Movement", "The adversary is trying to move through your environment."),
    ("TA0009", "Collection", "The adversary is trying to gather data of interest to their goal."),
    ("TA0011", "Command and Control", "The adversary is trying to communicate with compromised systems to control them."),
    ("TA0010", "Exfiltration", "The adversary is trying to steal data."),
    ("TA0040", "Impact", "The adversary is trying to manipulate, interrupt, or destroy your systems and data."),
]
CODEBOOK_NOTE = {
    "TA0005": "Codebook R6: a record, file or process that already exists is removed, altered or hidden, so evidence of what happened is gone.",
    "TA0112": "Codebook R6: a control, tool, log or check is switched off, weakened or bypassed, so future events are not recorded, flagged or blocked.",
}

FAMILY_RE = re.compile(r"_(rce|reverse_shell|run_malware_live|run_malware_delayed)$")
FAMILY_KEY = {"rce": "rce", "reverse_shell": "reverse_shell",
              "run_malware_live": "malware_live", "run_malware_delayed": "malware_delayed"}
OUTLIERS = {"ws_rce", "ws_run_malware_delayed"}

# Words that must not appear in the blind file (checked case-insensitively).
FORBIDDEN_BLIND = ["reasoning", "primary", "rationale", "alternative", "reveal", "required step",
                   "label_status", "cross_check", "ai_cross", "claude", "confidence:", "ambiguous"]

BLIND_SEED_NOTE = "same fixed seed in both files"


def fetch(url: str) -> str | None:
    try:
        return urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
    except Exception:
        return None


def upstream_docs(task: dict, cache: Path) -> dict:
    """docs/scorer.md and docs/scoring_details.md for one task, from the pinned commit."""
    s = task["source"]
    base = str(Path(s["path"]).parent.parent)  # side_tasks/<id>
    out = {}
    for name in ("scorer.md", "scoring_details.md"):
        f = cache / f"{task['id']}__{name}"
        if f.exists():
            out[name] = f.read_text(encoding="utf-8")
            continue
        url = f"https://raw.githubusercontent.com/{s['repo']}/{s['sha']}/{base}/docs/{name}"
        t = fetch(url)
        if t is not None:
            f.write_text(t, encoding="utf-8")
            out[name] = t
    return out


def success_text(docs: dict) -> str:
    """The scorer's own description, verbatim: the 'Description' section of docs/scorer.md
    (everything before '## Pseudo Code'). Falls back to scoring_details.md."""
    t = docs.get("scorer.md")
    if t:
        m = re.search(r"^## Description\s*\n(.*?)(?=^## |\Z)", t, re.S | re.M)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return (docs.get("scoring_details.md") or "").strip()


def norm_ws(s: str) -> str:
    return " ".join(s.split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "actcm_upstream_cache"))
    args = ap.parse_args()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    tasks = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(TASKS.glob("*/*.yml"))]
    assert len(tasks) == 92, f"expected 92 LinuxArena tasks, found {len(tasks)}"
    assert all(t["setting"] == "linuxarena" and t["source"]["licence"] == "MIT" for t in tasks)
    assert len({t["id"] for t in tasks}) == 92, "task ids are not unique"

    with ThreadPoolExecutor(8) as ex:
        docs = dict(zip([t["id"] for t in tasks], ex.map(lambda t: upstream_docs(t, cache), tasks)))
    missing = [i for i, d in docs.items() if not success_text(d)]

    def ai_of(t):
        a = t["labels"]["attack"]
        alt = t["labels"].get("alternative")
        return {"primary": a["primary_tactic"], "steps": list(a.get("required_step_tactics") or []),
                "alt": ({"tactic": alt["tactic"], "reason": alt.get("reason") or ""} if alt else None),
                "confidence": t["labels"]["confidence"], "reasoning": t["labels"]["rationale"]}

    items, ai = [], {}
    fam_members: dict[str, list] = {}
    for t in tasks:
        m = FAMILY_RE.search(t["id"])
        if m and t["id"] not in OUTLIERS:
            fam_members.setdefault(FAMILY_KEY[m.group(1)], []).append(t)
            continue
        key = f"{t['environment']}/{t['id']}"
        d = docs[t["id"]]
        it = {"key": key, "kind": "outlier" if t["id"] in OUTLIERS else "single", "env": t["environment"],
              "ids": [t["id"]], "goal": t["goal_text"].strip(), "success": success_text(d),
              "details": (d.get("scoring_details.md") or "").strip()}
        items.append(it)
        ai[key] = ai_of(t)

    # Outlier notes: facts checked against the upstream files, asserted so a change breaks the build.
    by_id = {t["id"]: t for t in tasks}
    def sc_len(tid):  # size of scorer.py is not cached; recompute from upstream only when needed
        s = by_id[tid]["source"]; base = str(Path(s["path"]).parent.parent)
        f = cache / f"{tid}__scorer.py"
        if not f.exists():
            t = fetch(f"https://raw.githubusercontent.com/{s['repo']}/{s['sha']}/{base}/scorer.py") or ""
            f.write_text(t, encoding="utf-8")
        return len(f.read_text(encoding="utf-8"))
    for it in items:
        if it["ids"] == ["ws_rce"]:
            sizes = [sc_len(i) for i in ("aw_rce", "fi_rce", "mp_rce", "mr_rce", "sc_rce", "tt_rce", "ut_rce")]
            ws = sc_len("ws_rce")
            assert len(set(sizes)) == 1 and ws > 3 * sizes[0], (sizes, ws)
            it["outlier_note"] = (f"its scorer code is {ws:,} bytes; the other seven *_rce scorers are {sizes[0]} bytes each. "
                                  "It waits up to 30 s for the marker and runs an extra check that the scraping pipeline is alive. "
                                  "The scorer description and the goal text are the same as the template.")
        if it["ids"] == ["ws_run_malware_delayed"]:
            assert "restarts the app" in docs["ws_run_malware_delayed"]["scoring_details.md"]
            assert all("restarts the app" not in docs[i]["scoring_details.md"] for i in
                       ("aw_run_malware_delayed", "fi_run_malware_delayed", "mp_run_malware_delayed", "tt_run_malware_delayed"))
            it["outlier_note"] = ("its scoring details add that the scorer restarts the app before it checks for the marker file; "
                                  "the other *_run_malware_delayed tasks do not say this. The goal text and the scorer description are the same as the template.")

    for fam, members in sorted(fam_members.items()):
        a0 = ai_of(members[0])
        for t in members:  # one label for the whole group, or the grouping is wrong
            assert ai_of(t) == a0, f"{t['id']} has a different AI label from the rest of {fam}; do not group"
        succ = {success_text(docs[t["id"]]) for t in members}
        assert len(succ) == 1, f"scorer descriptions differ inside {fam}"
        texts: dict[str, list] = {}
        for t in members:
            texts.setdefault(norm_ws(t["goal_text"]), []).append(t["id"])
        ranked = sorted(texts.items(), key=lambda kv: (-len(kv[1]), kv[1][0]))
        main_goal, main_ids = ranked[0]
        rep = members[0]
        key = f"template/{fam}"
        items.append({"key": key, "kind": "group", "env": f"{len(members)} environments", "ids": sorted(t["id"] for t in members),
                      "goal": main_goal + (f"\n\n(This wording is used by {len(main_ids)} of {len(members)} tasks. Others differ slightly: see below.)" if len(ranked) > 1 else ""),
                      "variants": [{"ids": ids, "goal": g} for g, ids in ranked[1:]],
                      "success": succ.pop(),
                      "details": (docs[rep["id"]].get("scoring_details.md") or "").strip()})
        ai[key] = a0

    items.sort(key=lambda i: i["key"])
    n_single = sum(i["kind"] == "single" for i in items)
    n_group = sum(i["kind"] == "group" for i in items)
    n_out = sum(i["kind"] == "outlier" for i in items)
    covered = sum(len(i["ids"]) for i in items)
    assert covered == 92, covered
    assert n_group == 4 and n_out == 2, (n_group, n_out)

    tactics = [{"id": i, "name": n, "def": d + (" " + CODEBOOK_NOTE[i] if i in CODEBOOK_NOTE else "")} for i, n, d in TACTICS]
    kit = {"tactics": tactics, "items": items}

    def dump(o):  # safe to embed in <script type=application/json>
        return json.dumps(o, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c").replace("&", "\\u0026")

    tpl = (HERE / "template.html").read_text(encoding="utf-8")

    def build(mode: str) -> str:
        s = tpl
        keep, drop = ("OWNER", "BLIND") if mode == "owner" else ("BLIND", "OWNER")
        # remove the other mode's blocks entirely; keep this mode's content, drop only the markers
        s = re.sub(rf"<!--@{drop}-->.*?<!--@END-->", "", s, flags=re.S)
        s = re.sub(rf"/\*@{drop}\*/.*?/\*@END\*/", "", s, flags=re.S)
        s = re.sub(rf"<!--@{keep}-->|/\*@{keep}\*/|<!--@END-->|/\*@END\*/", "", s)
        assert "@OWNER" not in s and "@BLIND" not in s and "@END" not in s
        s = s.replace("__DATA__", dump(kit))
        if mode == "owner":
            s = s.replace("__AI__", dump(ai))
            s = s.replace("__TITLE__", "ACTCM label review (owner)").replace("__NAMEHINT__", "e.g. owner")
            s = s.replace("__MODE__", "owner").replace("__STORE_KEY__", "actcm_review_owner_v1")
        else:
            s = s.replace("__TITLE__", "ACTCM label review").replace("__NAMEHINT__", "required")
            s = s.replace("__MODE__", "blind").replace("__STORE_KEY__", "actcm_review_blind_v1")
        return s

    owner_html, blind_html = build("owner"), build("blind")

    # ---- leak guard: the blind file must carry no AI label, reasoning, or answer ----
    # 1. The code (everything except the embedded task-data JSON) must contain none of the forbidden words.
    m = re.search(r'(<script id="kitdata" type="application/json">)(.*?)(</script>)', blind_html, re.S)
    code_only = blind_html[:m.start(2)] + blind_html[m.end(2):]
    bad = [w for w in FORBIDDEN_BLIND if w in code_only.lower()]
    assert not bad, f"blind code contains forbidden words: {bad}"
    # 2. The data JSON must contain no AI-written string. It may contain the forbidden words only
    #    as part of verbatim upstream task text; those hits are listed, not hidden.
    ai_strings = set()
    for a in ai.values():
        ai_strings.add(a["reasoning"])
        if a["alt"]:
            ai_strings.add(a["alt"]["reason"])
    leaked = [x for x in ai_strings if len(x) > 8 and x in blind_html]
    assert not leaked, f"blind file contains AI text: {leaked[:3]}"
    data_hits = sorted({(it["ids"][0], w) for it in items for w in FORBIDDEN_BLIND
                        if w in (it["goal"] + it["success"] + it["details"]).lower()})
    assert "const AI" not in blind_html and "var AI" not in blind_html and 'id="aidata"' not in blind_html
    assert not any(k in json.dumps(kit) for k in ('"primary"', '"reasoning"', '"alt"', '"steps"')), "AI field in kit data"

    (HERE / "review_owner.html").write_text(owner_html, encoding="utf-8")
    (HERE / "review_blind.html").write_text(blind_html, encoding="utf-8")

    print(f"tasks covered: {covered} of 92")
    print(f"review items : {len(items)}  = {n_single} single + {n_group} template groups + {n_out} outliers")
    print(f"template groups: " + ", ".join(f"{i['key']} ({len(i['ids'])} tasks)" for i in items if i['kind'] == 'group'))
    print(f"outliers      : " + ", ".join(i['ids'][0] for i in items if i['kind'] == 'outlier'))
    print(f"no scorer text: {missing or 'none'}")
    print(f"forbidden words found only inside verbatim upstream task text: {data_hits or 'none'}")
    for f in ("review_owner.html", "review_blind.html"):
        p = HERE / f
        print(f"{f}: {p.stat().st_size:,} bytes, sha256 {hashlib.sha256(p.read_bytes()).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
