#!/usr/bin/env python3
"""Phase 4: compute every number the site shows. Writes data/generated/{counts,tasks}.json and tasks.csv.

Counting rules (documented, tested):
  * "End goal only" (primary): a task counts once, under its primary tactic.
  * "End goal + required steps": a task counts once under each DISTINCT tactic in {primary} + steps.
    A step equal to the primary is not counted twice.
  * Technique counts use the primary tactic and primary technique only (steps carry no technique).
  * A task with technique null is counted in its tactic but in no technique row; it is listed separately.
  * A gap is a tactic with 0 tasks in that mode.
  * Tasks listed in data/unfinished_upstream.yml are not in data/tasks and are never counted.
All output is deterministic (sorted, no timestamps).
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict

import common as c
import frameworks as fwm
import labels as L

ALL_SETTINGS = ["linuxarena", "linuxarena-extras", "refactor_arena", "vllm"]
SETTINGS = c.visible_settings()          # config/publish.yml: the hidden setting is not counted anywhere public
SETTING_NAMES = {"linuxarena": "LinuxArena", "linuxarena-extras": "LinuxArena extras",
                 "refactor_arena": "Refactor Arena", "vllm": "vLLM"}
TEMPLATE = re.compile(r"_(rce|reverse_shell|run_malware_live|run_malware_delayed)$")
OUT = c.DATA / "generated"
HASH_NAMES = {"linuxarena": "linuxarena", "linuxarena-extras": "extras", "refactor_arena": "refactor", "vllm": "vllm"}
EXTRAS_NOTE = "LinuxArena extras is not included in v0.1, pending permission from its maintainers."
PROVISIONAL_NOTE = ("PROVISIONAL. No human has reviewed any label yet. Counts and gaps may still change: two decisions are open "
                    "(the three tenant-isolation tasks, and the line between Stealth and Defense Impairment).")


def is_template(tid: str):
    m = TEMPLATE.search(tid)
    return m.group(1) if m else None


def tactics_of(t: dict, with_steps: bool) -> set:
    a = (t.get("labels") or {}).get("attack") or {}
    if not a.get("primary_tactic"):
        return set()
    s = {a["primary_tactic"]}
    if with_steps:
        s |= set(a.get("required_step_tactics") or [])
    return s


def count_tactics(tasks: list[dict], with_steps: bool) -> dict:
    """{tactic: {"all": n, setting: n, ...}}"""
    out = defaultdict(Counter)
    for t in tasks:
        for tac in tactics_of(t, with_steps):
            out[tac]["all"] += 1
            out[tac][t["setting"]] += 1
    return out


def count_techniques(tasks: list[dict]) -> dict:
    """{(tactic, technique): {"all": n, setting: n, "ids": [...]}} for primary tactic + primary technique."""
    out = defaultdict(lambda: dict(all=0, ids=[]))
    for t in tasks:
        a = (t.get("labels") or {}).get("attack") or {}
        if a.get("primary_tactic") and a.get("technique"):
            r = out[(a["primary_tactic"], a["technique"])]
            r["all"] += 1
            r[t["setting"]] = r.get(t["setting"], 0) + 1
            r["ids"].append(uid(t))
    return out


def uid(t: dict) -> str:
    return f"{t['setting']}/{t['environment']}/{t['id']}"


def build_counts(tasks: list[dict], fw: dict, lock: dict, unfinished: int = 0, codebook: str = "1.1-draft") -> dict:
    att, atl = fw["attack"], fw["atlas"]
    tprim, tstep = count_tactics(tasks, False), count_tactics(tasks, True)
    tech = count_techniques(tasks)
    active = {k: v for k, v in att["techniques"].items() if not v["revoked"] and not v["deprecated"]}
    tactic_rows = []
    for tac in att["tactics"]:
        i = tac["id"]
        avail = [k for k, v in active.items() if i in v["tactics"]]
        used = sorted(k for (ti, k) in tech if ti == i)
        parents_avail = {k.split(".")[0] for k in avail}
        parents_used = {k.split(".")[0] for k in used}
        row = dict(id=i, name=tac["name"], shortname=tac["shortname"],
                   primary={s: tprim[i].get(s, 0) for s in ["all"] + SETTINGS},
                   with_steps={s: tstep[i].get(s, 0) for s in ["all"] + SETTINGS},
                   techniques_used=used, techniques_used_n=len(used),
                   techniques_available_n=len(avail), parents_available_n=len(parents_avail),
                   parents_used_n=len(parents_used),
                   gap_primary=tprim[i].get("all", 0) == 0, gap_with_steps=tstep[i].get("all", 0) == 0)
        tactic_rows.append(row)
    tech_rows = []
    for (ti, k), r in sorted(tech.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        tech_rows.append(dict(id=k, name=att["techniques"][k]["name"], tactic=ti, count=r["all"],
                              by_setting={s: r.get(s, 0) for s in SETTINGS}, task_uids=sorted(r["ids"]),
                              also_in_tactics=[x for x in att["techniques"][k]["tactics"] if x != ti]))
    null_t = sorted(uid(t) for t in tasks if (t.get("labels") or {}).get("attack", {}).get("technique") is None
                    and t.get("labels"))
    # ATLAS: a technique is shown under every ATLAS tactic it belongs to
    atl_by_tech = defaultdict(list)
    for t in tasks:
        a = ((t.get("labels") or {}).get("atlas") or {}).get("technique")
        if a:
            atl_by_tech[a].append(uid(t))
    atl_tech_rows = [dict(id=k, name=atl["techniques"][k]["name"], tactics=atl["techniques"][k]["tactics"],
                          count=len(v), task_uids=sorted(v)) for k, v in sorted(atl_by_tech.items())]
    atl_tactic_rows = []
    for tac in atl["tactics"]:
        n = sorted({u for r in atl_tech_rows if tac["id"] in r["tactics"] for u in r["task_uids"]})
        atl_tactic_rows.append(dict(id=tac["id"], name=tac["name"], tasks=len(n),
                                    techniques=[r["id"] for r in atl_tech_rows if tac["id"] in r["tactics"]]))
    def atlas_summary(sk):
        uids = {u for r in atl_tech_rows for u in r["task_uids"] if sk == "all" or u.startswith(sk + "/")}
        tacs = [tr["id"] for tr in atl_tactic_rows if any(
            u.startswith(sk + "/") or sk == "all" for r in atl_tech_rows if tr["id"] in r["tactics"] for u in r["task_uids"])]
        return dict(tasks_with_atlas_label=len(uids), tactics_with_task=len(tacs), tactics_total=len(atl_tactic_rows))
    atlas_by_setting = {sk: atlas_summary(sk) for sk in ["all"] + SETTINGS}
    n = len(tasks)
    tiers = Counter(t["label_status"] for t in tasks)
    by_setting = {s: sum(t["setting"] == s for t in tasks) for s in SETTINGS}
    by_env = {s: dict(sorted(Counter(t["environment"] for t in tasks if t["setting"] == s).items())) for s in SETTINGS}
    tier_by_setting = {s: {x: sum(1 for t in tasks if t["setting"] == s and t["label_status"] == x)
                           for x in L.TIERS + [L.UNLABELLED]} for s in SETTINGS}
    gaps_p = [r["id"] for r in tactic_rows if r["gap_primary"]]
    gaps_s = [r["id"] for r in tactic_rows if r["gap_with_steps"]]
    tmpl = [uid(t) for t in tasks if is_template(t["id"])]
    amb = [uid(t) for t in tasks if (t.get("labels") or {}).get("confidence") == "ambiguous"]
    planned = [uid(t) for t in tasks if t.get("scorer_status") == "planned_not_implemented"]
    return dict(
        provisional=True, provisional_note=PROVISIONAL_NOTE,
        settings=[dict(id=x, name=SETTING_NAMES[x], hash=HASH_NAMES[x]) for x in SETTINGS],
        extras_note=None if c.publish_extras() else EXTRAS_NOTE,
        versions=dict(attack=att["version"], atlas=atl["version"], codebook=codebook,
                      attack_sha=lock["frameworks"]["attack"]["sha"], atlas_sha=lock["frameworks"]["atlas"]["sha"],
                      attack_sha256=lock["frameworks"]["attack"]["sha256"], atlas_sha256=lock["frameworks"]["atlas"]["sha256"]),
        totals=dict(tasks=n, by_setting=by_setting, by_environment=by_env, unfinished_upstream=unfinished),
        tactics=tactic_rows, techniques=tech_rows, tasks_with_null_technique=null_t,
        atlas=dict(version=atl["version"], tasks_with_atlas_label=sum(len(v) for v in atl_by_tech.values()), summary_by_setting=atlas_by_setting,
                   tactics=atl_tactic_rows, techniques=atl_tech_rows),
        gaps=dict(primary=gaps_p, with_steps=gaps_s),
        summary=dict(
            tasks=n, tactics_total=len(att["tactics"]),
            tactics_covered_primary=len(att["tactics"]) - len(gaps_p), tactics_covered_with_steps=len(att["tactics"]) - len(gaps_s),
            gap_tactics_primary=len(gaps_p), gap_tactics_with_steps=len(gaps_s),
            template_tasks=len(tmpl), template_share_percent=round(100 * len(tmpl) / n, 1) if n else 0.0,
            ambiguous_labels=len(amb), planned_scorer_tasks=len(planned),
            null_technique_tasks=len(null_t), draft=tiers.get("draft_needs_human_review", 0),
            ai_cross_checked=tiers.get("ai_cross_checked", 0), reviewed=tiers.get("reviewed", 0),
            adjudicated=tiers.get("adjudicated", 0), unlabelled=tiers.get("unlabelled", 0)),
        tiers=dict(total={x: tiers.get(x, 0) for x in L.TIERS + [L.UNLABELLED]}, by_setting=tier_by_setting),
        summary_by_setting={"all": summarize(tasks, fw), **{st: summarize([t for t in tasks if t["setting"] == st], fw) for st in SETTINGS}},
        lists=dict(ambiguous=sorted(amb), planned_scorer=sorted(planned), templates=sorted(tmpl)))


def summarize(ts: list[dict], fw: dict) -> dict:
    """Summary-strip numbers for one subset of tasks (a setting, or all)."""
    n = len(ts)
    prim, step = count_tactics(ts, False), count_tactics(ts, True)
    ids = [x["id"] for x in fw["attack"]["tactics"]]
    gp = [i for i in ids if prim[i].get("all", 0) == 0]
    gs = [i for i in ids if step[i].get("all", 0) == 0]
    tiers = Counter(t["label_status"] for t in ts)
    tmpl = sum(1 for t in ts if is_template(t["id"]))
    return dict(
        tasks=n, tactics_total=len(ids), tactics_covered_primary=len(ids) - len(gp), tactics_covered_with_steps=len(ids) - len(gs),
        gap_tactics_primary=len(gp), gap_tactics_with_steps=len(gs), gap_ids_primary=gp, gap_ids_with_steps=gs,
        template_tasks=tmpl, template_share_percent=round(100 * tmpl / n, 1) if n else 0.0,
        ambiguous_labels=sum(1 for t in ts if (t.get("labels") or {}).get("confidence") == "ambiguous"),
        planned_scorer_tasks=sum(1 for t in ts if t.get("scorer_status") == "planned_not_implemented"),
        null_technique_tasks=sum(1 for t in ts if (t.get("labels") or {}).get("attack", {}).get("technique") is None and t.get("labels")),
        tiers={x: tiers.get(x, 0) for x in L.TIERS + [L.UNLABELLED]})


def task_record(t: dict, fw: dict) -> dict:
    lab = t.get("labels") or {}
    a = lab.get("attack") or {}
    s = t["source"]
    names = {x["id"]: x["name"] for x in fw["attack"]["tactics"]}
    alt = lab.get("alternative")
    cc = t.get("cross_check") or {}
    return dict(
        uid=uid(t), id=t["id"], setting=t["setting"], environment=t["environment"],
        goal=t.get("goal_text"), our_summary=t.get("our_summary"),
        upstream_category=t.get("upstream_category"), failure_type=t.get("failure_type"),
        source_repo=s["repo"], source_tag=s["tag"], source_sha=s["sha"], source_path=s["path"], source_licence=s["licence"],
        source_url=f"https://github.com/{s['repo']}/blob/{s['sha']}/{s['path']}",
        primary_tactic=a.get("primary_tactic"), primary_tactic_name=names.get(a.get("primary_tactic")),
        technique=a.get("technique"),
        technique_name=(fw["attack"]["techniques"].get(a.get("technique")) or {}).get("name"),
        technique_fit=lab.get("technique_fit"),
        step_tactics=a.get("required_step_tactics") or [],
        atlas_technique=(lab.get("atlas") or {}).get("technique"),
        confidence=lab.get("confidence"), alternative=alt, rationale=lab.get("rationale"),
        label_status=t["label_status"], labeled_by=t.get("labeled_by"), reviewed_by=t.get("reviewed_by"),
        scorer_status=t.get("scorer_status"), template_family=is_template(t["id"]),
        cross_check=dict(rater=cc.get("rater"), qualified=cc.get("qualified"), agrees_tactic=cc.get("agrees_tactic"),
                         technique_match=cc.get("technique_match")) if cc else None,
        history=t.get("history") or [])


CSV_COLS = ["uid", "setting", "environment", "id", "primary_tactic", "primary_tactic_name", "technique", "technique_name",
            "technique_fit", "step_tactics", "atlas_technique", "confidence", "label_status", "scorer_status",
            "upstream_category", "failure_type", "template_family", "source_url", "our_summary", "rationale"]


def main() -> dict:
    fw = fwm.load()
    lock = c.load_yaml(c.LOCK_FILE)
    tasks = [c.load_yaml(f) for f in c.public_task_files()]          # hidden settings never reach an output
    tasks.sort(key=lambda t: (SETTINGS.index(t["setting"]), t["environment"], t["id"]))
    unf = c.load_yaml(c.DATA / "unfinished_upstream.yml")["tasks"] if (c.DATA / "unfinished_upstream.yml").exists() else []
    unf = [u for u in unf if c.is_public_setting(u["setting"])]
    counts = build_counts(tasks, fw, lock, len(unf))
    recs = [task_record(t, fw) for t in tasks]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "counts.json").write_text(json.dumps(counts, indent=1) + "\n", encoding="utf-8")
    (OUT / "tasks.json").write_text(json.dumps(recs, indent=1) + "\n", encoding="utf-8")
    with open(OUT / "tasks.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in recs:
            row = dict(r); row["step_tactics"] = ";".join(r["step_tactics"])
            w.writerow(row)
    return counts


def report(cn: dict) -> None:
    print(f"tasks {cn['totals']['tasks']} (unfinished upstream, not counted: {cn['totals']['unfinished_upstream']})")
    print(f"{'tactic':32}{'primary':>8}{'+steps':>8}  techniques used / available")
    for r in cn["tactics"]:
        print(f"{r['id']+' '+r['name']:32}{r['primary']['all']:>8}{r['with_steps']['all']:>8}  "
              f"{r['techniques_used_n']} / {r['techniques_available_n']}{'   GAP' if r['gap_primary'] else ''}"
              f"{' (gap even with steps)' if r['gap_with_steps'] else ''}")
    print("gaps, end goal only :", cn["gaps"]["primary"])
    print("gaps, with steps    :", cn["gaps"]["with_steps"])
    print("summary:", cn["summary"])


if __name__ == "__main__":
    report(main())
