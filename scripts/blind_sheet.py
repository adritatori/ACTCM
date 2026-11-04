#!/usr/bin/env python3
"""Export a sheet for independent labelling. It has goal text only and NO existing labels.

  blind_sheet.py                         all tasks, in a fixed shuffled order -> .cache/blind_sheet.csv
  blind_sheet.py --calibration           only the calibration tasks
  blind_sheet.py --ours ours.csv         write OUR labels (id + labels) to a file for scripts/agreement.py

For tasks whose source repo has no licence, goal text is not stored here: the sheet gives our short summary and the link;
read the goal at the link. The sheet never contains upstream category, tactic, technique, rationale or status.
"""
from __future__ import annotations

import argparse
import csv
import random

import common as c
import labels as L
import sample

OUT = c.ROOT / ".cache" / "blind_sheet.csv"      # not in data/generated: it is a per-person working file
SEED = 20261104
BLANK = ["primary_tactic", "technique", "required_step_tactics", "atlas_technique", "confidence", "alternative_tactic", "notes"]
HEAD = ["id", "setting", "environment", "goal_or_summary", "text_is_our_summary", "source_link"] + BLANK


def rows(tasks: list[dict]) -> list[dict]:
    out = []
    for t in tasks:
        s = t["source"]
        goal = t.get("goal_text")
        out.append(dict(id=t["id"], setting=t["setting"], environment=t["environment"],
                        goal_or_summary=goal if goal else (t.get("our_summary") or ""), text_is_our_summary=str(not goal).lower(),
                        source_link=f"https://github.com/{s['repo']}/blob/{s['sha']}/{s['path']}", **{k: "" for k in BLANK}))
    return out


def shuffled(items: list, seed: int = SEED) -> list:
    items = list(items); random.Random(seed).shuffle(items); return items


def write_sheet(path, tasks: list[dict]) -> int:
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEAD, lineterminator="\n"); w.writeheader(); w.writerows(rows(shuffled(tasks)))
    return len(tasks)


def write_ours(path, tasks: list[dict]) -> int:
    cols = ["id", "primary_tactic", "technique", "required_step_tactics", "atlas_technique", "confidence", "label_status"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n"); w.writeheader()
        for t in sorted(tasks, key=lambda t: t["id"]):
            a = t["labels"]["attack"]
            w.writerow(dict(id=t["id"], primary_tactic=a["primary_tactic"], technique=a["technique"] or "", required_step_tactics=";".join(a["required_step_tactics"]),
                            atlas_technique=(t["labels"].get("atlas") or {}).get("technique") or "", confidence=t["labels"]["confidence"], label_status=t["label_status"]))
    return len(tasks)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibration", action="store_true"); ap.add_argument("--ours"); ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    tasks = [t for _, (f, t) in L.load_tasks(public_only=True).items()]
    if a.calibration:
        tasks = sample.calibration(sample.pool())
    if a.ours:
        print(f"wrote {write_ours(a.ours, tasks)} of our labels to {a.ours}")
    else:
        print(f"wrote {write_sheet(a.out, tasks)} tasks to {a.out}")


if __name__ == "__main__":
    main()
