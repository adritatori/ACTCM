#!/usr/bin/env python3
"""Pick tasks for labelling practice.

  sample.py --calibration              the 10 calibration tasks (fixed seed; same list for everyone)
  sample.py --calibration --reference  also print the reference labels and rationales (read AFTER you have labelled)

Calibration tasks are chosen from tasks that have a stored goal text (licensed sources), a `clear` label, status
`ai_cross_checked`, and no planned-only scorer. One per tactic where possible, at most one repeated-template task.
"""
from __future__ import annotations

import argparse
import random

import build as B
import common as c
import frameworks as fwm
import labels as L

SEED = 20261104


def pool() -> list[dict]:
    out = []
    for (env, tid), (f, t) in L.load_tasks(public_only=True).items():
        if (t.get("goal_text") and t["label_status"] == "ai_cross_checked" and t["labels"]["confidence"] == "clear"
                and t.get("scorer_status") != "planned_not_implemented"):
            out.append(t)
    return sorted(out, key=lambda t: (t["setting"], t["environment"], t["id"]))


def calibration(tasks: list[dict], n: int = 10, seed: int = SEED) -> list[dict]:
    """Deterministic. One task per main tactic first (tactics in matrix order), then fill; max one template task."""
    rnd = random.Random(seed)
    by = {}
    for t in tasks:
        by.setdefault(t["labels"]["attack"]["primary_tactic"], []).append(t)
    picked, used_template = [], False
    tactics = [x for x in sorted(by)]
    rnd.shuffle(tactics)
    for tac in tactics:
        if len(picked) >= n:
            break
        cands = [t for t in by[tac] if not (B.is_template(t["id"]) and used_template)]
        if not cands:
            continue
        t = rnd.choice(cands)
        used_template |= bool(B.is_template(t["id"]))
        picked.append(t)
    rest = [t for t in tasks if t not in picked and not (B.is_template(t["id"]) and used_template)]
    rnd.shuffle(rest)
    for t in rest:
        if len(picked) >= n:
            break
        used_template |= bool(B.is_template(t["id"]))
        picked.append(t)
    return sorted(picked, key=lambda t: (t["environment"], t["id"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibration", action="store_true", required=True)
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    ts = calibration(pool(), a.n, a.seed)
    fw = fwm.load(); nm = {x["id"]: x["name"] for x in fw["attack"]["tactics"]}
    print(f"calibration set: {len(ts)} tasks (seed {a.seed}). Label these WITHOUT looking at the reference.")
    for t in ts:
        print(f"  {t['environment']}/{t['id']}")
    if a.reference:
        print("\nREFERENCE LABELS (draft, not human-reviewed)")
        for t in ts:
            at = t["labels"]["attack"]
            print(f"\n{t['environment']}/{t['id']}\n  main tactic {at['primary_tactic']} {nm[at['primary_tactic']]}; technique {at['technique']}; "
                  f"steps {at['required_step_tactics'] or 'none'}; ATLAS {(t['labels'].get('atlas') or {}).get('technique') or 'none'}\n  rationale: {t['labels']['rationale']}")


if __name__ == "__main__":
    main()
