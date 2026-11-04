#!/usr/bin/env python3
"""Phase 3: build data/generated/review_sheet.csv, start_here.csv and status_counts.json.

review_sheet.csv puts the tasks a human should look at first at the top:
  1 blind rater disagrees on the main tactic
  2 blind rater disagrees on the technique
  3 our label is ambiguous (or the blind rater's is)
  4 new tasks (not in the 92-row seed)
  5 required steps or ATLAS label differ
  6 everything else
start_here.csv is the list a human can confirm first: clear, ai_cross_checked, spread across
tactics and settings, at most 2 repeated-template tasks, no planned-scorer task, and no task with a required
step that the R2 audit marked unsupported. It is not a claim that those labels are right.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict

import common as c
import crosscheck as cc
import frameworks as fwm
import labels as L

BLIND = c.DATA / "drafts" / "blind_pass_2026-11-04.yml"
SEED_IDS_FILE = c.ROOT / "seed" / "seed_labels_linuxarena_v3.2.0.csv"
TEMPLATE = re.compile(r"_(rce|reverse_shell|run_malware_live|run_malware_delayed)$")
SETTING_RANK = {"linuxarena": 0, "linuxarena-extras": 1, "refactor_arena": 2, "vllm": 3}
VISIBLE = c.visible_settings()
OUT = c.DATA / "generated"


def template_family(tid: str):
    m = TEMPLATE.search(tid)
    return m.group(1) if m else None


def select_start_here(cands: list[dict], n_min: int = 20, per_tactic: int = 2, max_template: int = 2) -> tuple[list[dict], dict]:
    """Pick a diverse list. Each cand: id, setting, environment, tactic. Deterministic.

    Rules: at most `max_template` tasks from the repeated template families (rce, reverse_shell, run_malware_*)
    in total, and never two from the same family; within a tactic
    prefer settings not yet used for that tactic, then the setting least used overall; round-robin across
    tactics, rarest tactic first. Raise the per-tactic cap until n_min is reached or candidates run out.
    """
    pool = defaultdict(list)
    for x in sorted(cands, key=lambda x: (SETTING_RANK.get(x["setting"], 9), x["environment"], x["id"])):
        pool[x["tactic"]].append(x)
    tactics = sorted(pool, key=lambda t: (len(pool[t]), t))
    picked, used_fam = [], set()
    per_t = Counter(); per_s = Counter(); per_ts = defaultdict(set)
    cap = per_tactic
    while True:
        progress = False
        for t in tactics:
            if per_t[t] >= cap:
                continue
            opts = [x for x in pool[t] if x not in picked and (template_family(x["id"]) is None or (
                template_family(x["id"]) not in used_fam and len(used_fam) < max_template))]
            if not opts:
                continue
            opts.sort(key=lambda x: (x["setting"] in per_ts[t], per_s[x["setting"]],
                                     SETTING_RANK.get(x["setting"], 9), x["environment"], x["id"]))
            x = opts[0]
            picked.append(x); per_t[t] += 1; per_s[x["setting"]] += 1; per_ts[t].add(x["setting"])
            if template_family(x["id"]):
                used_fam.add(template_family(x["id"]))
            progress = True
        if not progress or len(picked) >= n_min:
            break
        cap += 1
    diag = dict(n=len(picked), shortfall=max(0, n_min - len(picked)), by_tactic=dict(per_t), by_setting=dict(per_s))
    return picked, diag


def blind_row(b: dict | None, fw: dict) -> dict:
    if not b:
        return {}
    names = {t["id"]: t["name"] for t in fw["attack"]["tactics"]}
    alt = b.get("alternative")
    return dict(
        blind_primary=cc.norm_id(b.get("primary")), blind_primary_name=names.get(cc.norm_id(b.get("primary")), "?"),
        blind_technique=cc.norm_id(b.get("technique")) or "", blind_steps=";".join(cc.norm_steps(b.get("steps"))),
        blind_atlas=cc.norm_id(b.get("atlas")) or "", blind_confidence=cc.norm_conf(b.get("confidence")),
        blind_alternative=(f"{alt.get('tactic')}: {alt.get('reason')}" if isinstance(alt, dict) else ""),
        blind_rationale=b.get("rationale") or "")


def build() -> dict:
    fw = fwm.load()
    names = {t["id"]: t["name"] for t in fw["attack"]["tactics"]}
    blind = {}
    if BLIND.exists():
        blind, _ = cc.load_blind(str(BLIND), fw)
    seed_ids = {(r["environment"], r["side_task_id"]) for r in csv.DictReader(open(SEED_IDS_FILE, encoding="utf-8"))}
    rows = []
    for (env, tid), (f, t) in L.load_tasks(public_only=True).items():
        lab = t.get("labels") or {}
        att = lab.get("attack") or {}
        b = blind.get(f"{env}/{tid}")
        cmp = cc.compare(lab, b) if b and not b.get("_invalid") else {}
        alt = lab.get("alternative")
        is_new = (env, tid) not in seed_ids
        if cmp and not cmp["agrees_tactic"]:
            grp, why = 1, "BLIND RATER DISAGREES on main tactic"
        elif cmp and cmp["technique_match"] in ("differ", "one_null"):
            grp, why = 2, f"blind rater disagrees on technique ({cmp['technique_match']})"
        elif lab.get("confidence") == "ambiguous" or (cmp and cmp["blind_confidence"] == "ambiguous"):
            grp, why = 3, "ambiguous label"
        elif is_new:
            grp, why = 4, "new task (not in seed)"
        elif cmp and (cmp["steps_jaccard"] < 1 or not cmp["atlas_match"]):
            grp, why = 5, "required steps or ATLAS differ"
        else:
            grp, why = 6, "blind rater agrees"
        s = t["source"]
        row = dict(
            group=grp, why_listed=why, setting=t["setting"], environment=env, id=tid, status=t["label_status"],
            our_primary=att.get("primary_tactic"), our_primary_name=names.get(att.get("primary_tactic"), "?"),
            our_technique=att.get("technique") or "", our_steps=";".join(att.get("required_step_tactics") or []),
            our_atlas=(lab.get("atlas") or {}).get("technique") or "", our_confidence=lab.get("confidence"),
            our_alternative=(f"{alt.get('tactic')}: {alt.get('reason')}" if alt else ""),
            our_rationale=lab.get("rationale") or "",
            **{k: "" for k in ("blind_primary", "blind_primary_name", "blind_technique", "blind_steps", "blind_atlas",
                               "blind_confidence", "blind_alternative", "blind_rationale")},
            scorer_status=t.get("scorer_status", ""), tactic_agree=cmp.get("agrees_tactic", ""), technique_match=cmp.get("technique_match", ""),
            steps_jaccard=cmp.get("steps_jaccard", ""), is_new=is_new,
            source_link=f"https://github.com/{s['repo']}/blob/{s['sha']}/{s['path']}")
        row.update(blind_row(b if b and not b.get("_invalid") else None, fw))
        rows.append(row)
    rows.sort(key=lambda r: (r["group"], SETTING_RANK[r["setting"]], r["environment"], r["id"]))
    for i, r in enumerate(rows, 1):
        r["order"] = i
    cols = ["order"] + [k for k in rows[0] if k != "order"]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "review_sheet.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n"); w.writeheader(); w.writerows(rows)

    audit = c.load_yaml(c.DATA / "audits" / "seed_steps_r2.yml")["tasks"]
    contested = {k for k, v in audit.items() if any(x["verdict"] == "unsupported" for x in v)}
    cands = [dict(id=r["id"], setting=r["setting"], environment=r["environment"], tactic=r["our_primary"])
             for r in rows if r["status"] == "ai_cross_checked" and r["our_confidence"] == "clear"
             and r["scorer_status"] != "planned_not_implemented"
             and f"{r['environment']}/{r['id']}" not in contested]
    picks, diag = select_start_here(cands)
    by = {(r["environment"], r["id"]): r for r in rows}
    sh = []
    for i, x in enumerate(picks, 1):
        r = by[(x["environment"], x["id"])]
        sh.append(dict(order=i, setting=r["setting"], environment=r["environment"], id=r["id"],
                       tactic=f"{r['our_primary']} {r['our_primary_name']}", technique=r["our_technique"] or "null",
                       steps=r["our_steps"], atlas=r["our_atlas"], rationale=r["our_rationale"], source_link=r["source_link"]))
    if sh:
        with open(OUT / "start_here.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(sh[0]), lineterminator="\n"); w.writeheader(); w.writerows(sh)
    counts = status_counts(rows)
    (OUT / "status_counts.json").write_text(json.dumps(counts, indent=1) + "\n", encoding="utf-8")
    return dict(rows=len(rows), groups=dict(Counter(r["group"] for r in rows)), start_here=diag, counts=counts,
                candidates=len(cands))


def status_counts(rows: list[dict]) -> dict:
    tiers = L.TIERS + [L.UNLABELLED]
    tot = Counter(r["status"] for r in rows)
    by_setting = {s: Counter(r["status"] for r in rows if r["setting"] == s) for s in VISIBLE}
    return dict(total=len(rows), tiers={t: tot.get(t, 0) for t in tiers},
                by_setting={s: {t: v.get(t, 0) for t in tiers} for s, v in by_setting.items()},
                note="ai_cross_checked means a second AI agreed. No human has checked those labels.")


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=str))
