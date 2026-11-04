#!/usr/bin/env python3
"""Phase 4: validate every task file.

Checks: JSON Schema; tactic/technique IDs against the pinned frameworks (via check_labels); the licence
rule (no goal text for unlicensed sources, summaries <= 20 words); no human-only status set by a bot;
unique IDs; source repo+sha present in the lock file; unfinished-upstream tasks are not in data/tasks.
Exit code 1 on any error. Warnings never fail the build.
"""
from __future__ import annotations

import json
import sys

import jsonschema

import check_labels
import common as c
import frameworks as fwm
import labels as L

SCHEMA = json.loads((c.ROOT / "schema" / "task.schema.json").read_text(encoding="utf-8"))
MAX_SUMMARY_WORDS = 20


def validate_task(t: dict, fw: dict, pinned: set | None = None) -> tuple[list[str], list[str]]:
    tid = t.get("id", "?") if isinstance(t, dict) else "?"
    errs, warns = [], []
    if not isinstance(t, dict):
        return ["not a mapping"], []
    v = jsonschema.Draft202012Validator(SCHEMA)
    for e in sorted(v.iter_errors(t), key=lambda e: list(e.path)):
        errs.append(f"{tid}: schema: {'/'.join(map(str, e.path)) or '(root)'}: {e.message[:140]}")
    if errs:   # label checks assume the basic shape
        return errs, warns
    e2, w2 = check_labels.check_task(t, fw)
    errs += e2; warns += w2
    lic = t["source"]["licence"]
    if lic == "none-found":
        if t.get("goal_text") is not None:
            errs.append(f"{tid}: licence none-found but goal_text is stored")
        n = len((t.get("our_summary") or "").split())
        if not 0 < n <= MAX_SUMMARY_WORDS:
            errs.append(f"{tid}: our_summary has {n} words (need 1 to {MAX_SUMMARY_WORDS})")
    else:
        if t.get("our_summary"):
            warns.append(f"{tid}: licensed source but our_summary is set")
        if t.get("goal_text") in (None, "") and t.get("upstream_status", "discovered") == "discovered":
            errs.append(f"{tid}: licensed source but goal_text is empty")
    if t.get("upstream_status", "discovered") != "discovered":
        errs.append(f"{tid}: upstream_status {t.get('upstream_status')!r}: unfinished tasks belong in data/unfinished_upstream.yml")
    if pinned is not None and (t["source"]["repo"], t["source"]["sha"]) not in pinned:
        errs.append(f"{tid}: source {t['source']['repo']}@{t['source']['sha'][:10]} is not in the lock file")
    for h in t.get("history") or []:
        if h["who"] and L.looks_like_bot(h["who"]) and any(x in h["change"] for x in ("-> reviewed", "-> adjudicated")):
            errs.append(f"{tid}: history shows a bot ({h['who']}) setting a human-only status")
    return errs, warns


def validate_all(tasks_dir=None) -> tuple[list[str], list[str], int]:
    fw = fwm.load()
    lock = c.load_yaml(c.LOCK_FILE)
    pinned = {(s["repo"], s["sha"]) for s in lock["sources"]}
    E, W, ids, n = [], [], {}, 0
    for f in sorted((tasks_dir or c.TASKS_DIR).rglob("*.yml")):
        t = c.load_yaml(f)
        e, w = validate_task(t, fw, pinned)
        E += [f"{f.name}: {x}" for x in e]; W += w; n += 1
        if isinstance(t, dict):
            if t.get("id") in ids:
                E.append(f"{f.name}: duplicate id {t.get('id')!r} (also {ids[t['id']]})")
            ids[t.get("id")] = f.name
    unf = c.DATA / "unfinished_upstream.yml"
    if unf.exists():
        for u in c.load_yaml(unf)["tasks"]:
            if u["id"] in ids:
                E.append(f"unfinished task {u['id']} also appears in data/tasks")
    return E, W, n


def main() -> int:
    E, W, n = validate_all()
    print(f"validated {n} task files: {len(E)} errors, {len(W)} warnings")
    for x in E:
        print("ERROR", x)
    for x in W[:30]:
        print("warn ", x)
    return 1 if E else 0


if __name__ == "__main__":
    sys.exit(main())
