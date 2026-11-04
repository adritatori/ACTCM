#!/usr/bin/env python3
"""Check the R2 audit file against the task files and write docs/SEED_STEPS_R2_AUDIT.md.

Every seed step must appear in the audit exactly once (no step skipped), and the audit may not list a step
the task does not have. Seed labels are never changed here.
"""
import re
import sys
from collections import Counter

import common as c
import frameworks as fwm
import labels as L

AUDIT = c.DATA / "audits" / "seed_steps_r2.yml"
FAM = re.compile(r"_(rce|reverse_shell|run_malware_live|run_malware_delayed)$")


def verify() -> tuple[list[str], dict]:
    audit = c.load_yaml(AUDIT)
    problems, seen = [], Counter()
    tasks = {f"{e}/{i}": t for (e, i), (_, t) in L.load_tasks().items() if t["setting"] == "linuxarena"}
    for key, t in tasks.items():
        steps = t["labels"]["attack"]["required_step_tactics"]
        fam = FAM.search(t["id"])
        if fam:
            fs = audit["families"][fam.group(1)]["steps"]
            full = sorted(s["step"] for s in fs); kept_ = sorted(s["step"] for s in fs if s["verdict"] == "supported")
            if sorted(steps) not in (full, kept_):      # original steps, or the steps after the v1.1 removals
                problems.append(f"{key}: family steps {sorted(steps)} match neither audit {full} nor v1.1 {kept_}")
            continue
        ts_ = audit["tasks"].get(key, [])
        full = sorted(s["step"] for s in ts_); kept_ = sorted(s["step"] for s in ts_ if s["verdict"] == "supported")
        if sorted(steps) not in (full, kept_):
            problems.append(f"{key}: task steps {sorted(steps)} match neither audit {full} nor v1.1 {kept_}")
        seen.update(s["verdict"] for s in audit["tasks"].get(key, []))
    for key in audit["tasks"]:
        if key not in tasks:
            problems.append(f"{key}: in audit but not a LinuxArena task")
    fam_counts = Counter()
    for name, fam in audit["families"].items():
        for s in fam["steps"]:
            fam_counts[s["verdict"]] += fam["members"]
    return problems, dict(tasks=seen, families=fam_counts, audit=audit, tasks_map=tasks)


def write_md() -> None:
    problems, r = verify()
    if problems:
        sys.exit("\n".join(problems))
    fw = fwm.load()
    nm = {t["id"]: t["name"] for t in fw["attack"]["tactics"]}
    audit = r["audit"]
    lines = ["# R2 audit of the seed required steps", "",
             "Date: 2026-11-04. Generated from `data/audits/seed_steps_r2.yml` by `scripts/audit_steps.py`.",
             "**No seed label has been changed.** This is a list of proposals; Tory decides.", "",
             "R2: a required step counts only if the goal text explicitly requires it.", "",
             "- **supported**: the goal text states it.",
             "- **weak**: implied by the wording (for example the data taken is a credential, or the goal says "
             "\"introduce a vulnerability\") but not stated as a step.",
             "- **unsupported**: nothing in the goal text states or clearly implies it.", ""]
    t, f = r["tasks"], r["families"]
    total_t = sum(t.values())
    lines += ["## Counts", "",
              f"Non-template tasks: {len(audit['tasks'])} tasks have steps, {total_t} steps in all.", "",
              "| Verdict | Steps in non-template tasks | Steps in template tasks (counted per task) |", "|---|---|---|"]
    for v in ("supported", "weak", "unsupported"):
        lines.append(f"| {v} | {t.get(v, 0)} | {f.get(v, 0)} |")
    lines += ["", "## A. Proposed removals: unsupported steps (non-template tasks)", "",
              "| Task | Current step | Why the goal text does not support it |", "|---|---|---|"]
    for k, steps in audit["tasks"].items():
        for s in steps:
            if s["verdict"] == "unsupported":
                lines.append(f"| `{k}` | {s['step']} {nm[s['step']]} | {s['why']} |")
    lines += ["", "## B. Judgement calls: weak steps (non-template tasks)", "",
              "Remove these only if you read R2 as \"stated in the words\". If you read it as \"clearly implied\", keep them.", "",
              "| Task | Current step | What the goal says |", "|---|---|---|"]
    for k, steps in audit["tasks"].items():
        for s in steps:
            if s["verdict"] == "weak":
                lines.append(f"| `{k}` | {s['step']} {nm[s['step']]} | {s['why']} |")
    lines += ["", "## C. Template families (R3 sets these by rule)", "",
              "| Family | Tasks | Goal text | Step | Verdict | Note |", "|---|---|---|---|---|---|"]
    for name, fam in audit["families"].items():
        for s in fam["steps"]:
            lines.append(f"| `*_{name}` | {fam['members']} | {fam['goal']} | {s['step']} {nm[s['step']]} | {s['verdict']} | {s['why']} |")
    lines += ["", "## D. Supported steps (no action)", "", "| Task | Step | Goal text |", "|---|---|---|"]
    for k, steps in audit["tasks"].items():
        for s in steps:
            if s["verdict"] == "supported":
                lines.append(f"| `{k}` | {s['step']} {nm[s['step']]} | {s['why']} |")
    (c.ROOT / "docs" / "SEED_STEPS_R2_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("tasks verdicts:", dict(t), "| family verdicts (per task):", dict(f))


def write_proposal() -> None:
    """docs/CODEBOOK_V1_1_PROPOSAL.md: the final list of step removals for Tory to approve. Changes nothing."""
    problems, r = verify()
    if problems:
        sys.exit("\n".join(problems))
    fw = fwm.load()
    nm = {t["id"]: t["name"] for t in fw["attack"]["tactics"]}
    audit, tasks = r["audit"], r["tasks_map"]
    rm_t, rm_f = [], []
    for k, steps in audit["tasks"].items():
        for s in steps:
            if s["verdict"] in ("unsupported", "weak"):
                rm_t.append((k, s))
    kept = {k: [s["step"] for s in v if s["verdict"] == "supported"] for k, v in audit["tasks"].items()}
    cur_count, new_count, new_count_tpl = Counter(), Counter(), Counter()
    fam_of = {}
    for key, t in tasks.items():
        a = t["labels"]["attack"]
        fam = FAM.search(t["id"])
        cur = list(a["required_step_tactics"])
        new = [x["step"] for x in audit["families"][fam.group(1)]["steps"] if x["verdict"] == "supported"] if fam else kept.get(key, [])
        newt = cur if fam else kept.get(key, [])   # templates unchanged
        for tid in {a["primary_tactic"], *cur}: cur_count[tid] += 1
        for tid in {a["primary_tactic"], *newt}: new_count_tpl[tid] += 1
        for tid in {a["primary_tactic"], *new}: new_count[tid] += 1
    L_ = ["# Codebook v1.1 proposal: required steps (R2) and the final removal list",
          "", "**Nothing in this file has been applied.** Approve or edit, then I apply it with one history entry per task.", "",
          "## Rule text proposed for R2", "",
          "> **R2.** A required-step tactic is listed only if the goal text *states* it in words (for example \"when triggered remotely\" → Initial Access; \"with root privileges\" → Privilege Escalation; \"download\" → Command and Control).",
          "> A step that is only *implied* (the data taken is a credential; \"introduce a vulnerability\" suggests planting; the end goal itself needs the access) is not listed.",
          "", "## Counts", "",
          f"- Non-template tasks with steps: {len(audit['tasks'])}. Steps proposed for removal: **{len(rm_t)}** "
          f"({sum(s['verdict'] == 'unsupported' for _, s in rm_t)} unsupported + {sum(s['verdict'] == 'weak' for _, s in rm_t)} weak). Steps kept: {sum(len(v) for v in kept.values())}.",
          f"- Template tasks (R3): {sum(f['members'] for f in audit['families'].values())}. Decision B2 below affects "
          f"{sum(f['members'] * sum(x['verdict'] == 'weak' for x in f['steps']) for f in audit['families'].values())} steps.", "",
          "## A. Removals in non-template tasks (the final list)", "",
          "| Task | Step removed | Verdict | Why | Steps left |", "|---|---|---|---|---|"]
    for k, s in rm_t:
        left = ", ".join(nm[x] for x in kept[k]) or "none"
        L_.append(f"| `{k}` | {s['step']} {nm[s['step']]} | {s['verdict']} | {s['why']} | {left} |")
    L_ += ["", "## B2. Decision: template families (R3 fixes these steps by rule)", "",
           "Under \"stated only\", the weak steps below would also go. This changes R3, so it needs your separate yes or no.", "",
           "| Family | Tasks | Step | Verdict | If removed, steps left |", "|---|---|---|---|---|"]
    for name, f in audit["families"].items():
        left = ", ".join(nm[x["step"]] for x in f["steps"] if x["verdict"] == "supported") or "none"
        for x in f["steps"]:
            if x["verdict"] == "weak":
                L_.append(f"| `*_{name}` | {f['members']} | {x['step']} {nm[x['step']]} | weak | {left} |")
    L_ += ["", "## Effect on tasks-per-tactic when required steps are counted", "",
           "| Tactic | Now | After A only | After A + B2 |", "|---|---|---|---|"]
    for t in fw["attack"]["tactics"]:
        i = t["id"]
        L_.append(f"| {i} {t['name']} | {cur_count[i]} | {new_count_tpl[i]} | {new_count[i]} |")
    L_ += ["", "(LinuxArena tasks only; the other settings have no seed steps to remove.)", "",
           "Lateral Movement goes from 1 to 0 under A, so it becomes a gap in every counting mode.", ""]
    (c.ROOT / "docs" / "CODEBOOK_V1_1_PROPOSAL.md").write_text("\n".join(L_) + "\n", encoding="utf-8")
    print("removals:", len(rm_t), "| unsupported", sum(s['verdict'] == 'unsupported' for _, s in rm_t),
          "| weak", sum(s['verdict'] == 'weak' for _, s in rm_t))


if __name__ == "__main__":
    # The v1.1 removals were applied on 2026-11-04 (scripts/apply_v11_steps.py). The two documents are now a
    # historical record of what was proposed, so they are only regenerated if the removals have not been applied.
    problems, _ = verify()
    if problems:
        sys.exit("\n".join(problems))
    if (c.DATA / "audits" / "v1_1_count_change.json").exists():
        print("audit verified against task files (v1.1 removals applied); documents not regenerated")
    else:
        write_md()
        write_proposal()
