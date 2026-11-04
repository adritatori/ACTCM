#!/usr/bin/env python3
"""Phase 3: write draft labels into the task files.

  draft_labels.py seed   Convert seed/seed_labels_linuxarena_v3.2.0.csv (tactic names) to tactic IDs.
  draft_labels.py new    Apply data/drafts/new_tasks.yml (the 43 tasks not in the seed).
  draft_labels.py all    Both.

Every label written here is `draft_needs_human_review`, `labeled_by: claude_draft_<date>`.
Existing labels are replaced only for tasks named in the input; nothing is ever set to reviewed here.
"""
from __future__ import annotations

import csv
import re
import sys

import common as c
import frameworks as fwm
import labels as L

SEED = c.ROOT / "seed" / "seed_labels_linuxarena_v3.2.0.csv"
NEW = c.DATA / "drafts" / "new_tasks.yml"
DATE = "2026-11-04"
WHO = f"claude_draft_{DATE}"
R3 = {
    "rce": "Template task (R3): *_rce -> Initial Access T1190; no required steps.",
    "reverse_shell": "Template task (R3): *_reverse_shell -> Command and Control T1071; no required steps.",
    "run_malware_live": "Template task (R3): *_run_malware_live -> Execution T1059; steps Command and Control, Privilege Escalation.",
    "run_malware_delayed": "Template task (R3): *_run_malware_delayed -> Execution T1059; steps Initial Access, Command and Control, Privilege Escalation.",
}
SEED_RATIONALE = ("Seed label (4 Nov 2026 draft). Scorer not re-read for this rationale; "
                  "see the blind pass in review_sheet.csv.")


def parse_alt(text: str, names: dict):
    text = (text or "").strip()
    if not text:
        return None
    m = re.match(r"^(.*?)\s*(?:\((.*)\))?$", text)
    name, reason = m.group(1).strip(), (m.group(2) or "").strip()
    if name not in names:
        raise ValueError(f"unknown alternative tactic {name!r}")
    return dict(tactic=names[name], technique=None, reason=reason or "Seed draft gave no reason.")


def write(f, t, label, status, who, note) -> None:
    t["labels"] = label
    t["label_status"] = status
    t["labeled_by"] = who
    t["cross_check"] = None
    t["reviewed_by"] = None
    t["history"] = [dict(date=DATE, who=who, change=note, reason="Initial draft; not reviewed by a human.")]
    c.dump_yaml(t, f)


def cmd_seed(fw, tasks) -> int:
    names = L.tactic_ids(fw)
    n = 0
    for r in csv.DictReader(open(SEED, encoding="utf-8")):
        f, t = tasks[(r["environment"], r["side_task_id"])]
        suffix = next((k for k in R3 if r["side_task_id"].endswith("_" + k)), None)
        steps = [names[x] for x in r["attack_required_step_tactics"].split(";") if x]
        atlas = r["atlas_technique"].split()[0] if r["atlas_technique"] else None
        label = L.make_label(
            names[r["attack_primary_tactic"]], r["attack_technique_id"], steps, r["confidence"],
            R3[suffix] if suffix else SEED_RATIONALE, atlas, parse_alt(r["alternative_label"], names))
        write(f, t, label, "draft_needs_human_review", WHO, "Converted from seed CSV (tactic names to IDs).")
        n += 1
    return n


def cmd_new(fw, tasks) -> int:
    n = 0
    for key, d in c.load_yaml(NEW).items():
        env, tid = key.split("/")
        f, t = tasks[(env, tid)]
        label = L.make_label(d["primary"], d["technique"], d.get("steps", []), d["confidence"], d["rationale"],
                             d.get("atlas"), d.get("alternative"))
        write(f, t, label, "draft_needs_human_review", WHO, "Drafted from the codebook v1.0.")
        n += 1
    return n


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    fw = fwm.load()
    tasks = L.load_tasks()
    if cmd in ("seed", "all"):
        print("seed rows written:", cmd_seed(fw, tasks))
    if cmd in ("new", "all"):
        tasks = L.load_tasks()
        print("new drafts written:", cmd_new(fw, tasks))
