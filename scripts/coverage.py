#!/usr/bin/env python3
"""The join: compare every incident attack step with the public side tasks.

Writes data/generated/incident_coverage.json and data/generated/activity.json. Deterministic: sorted keys, no
timestamps. Only public tasks are read (common.public_task_files), so a hidden setting can neither appear in the
output nor change a verdict.

Verdict for one (tactic, technique) pair:
  tested_technique    a public task has the same technique, compared at parent level (T1048.003 matches T1048)
  tested_tactic_only  a public task has this tactic as its end goal or as a stated required step, none shares the technique
  not_tested          no public task has this tactic as end goal or stated required step
A step marked ambiguous gets `unclear` when its primary and its alternative label give different verdicts.

verdict_stable is false when moving any one ambiguous task label to its recorded alternative (or all of them at
once) would change the step's verdict.

What this does NOT say: whether a monitor would catch the step (no monitor was run), or whether a task could
involve the tactic without stating it. Task labels record the end goal and the stated required steps only.
"""
from __future__ import annotations

import json
import sys

import common as c
import frameworks as fwm
import validate_incidents as vi

GEN = c.DATA / "generated"
OUT = GEN / "incident_coverage.json"
ACTIVITY = GEN / "activity.json"
VERDICTS = ["tested_technique", "tested_tactic_only", "not_tested", "unclear"]
VERDICT_LABELS = {"tested_technique": "Tested: same technique", "tested_tactic_only": "Tested: same tactic only",
                  "not_tested": "Never tested", "unclear": "Can't tell"}
PREDICTION_TACTICS = ["TA0043", "TA0042", "TA0007", "TA0008"]     # docs/PILOT_PREDICTION.md
LIMITS = [
    "Task labels record the end goal of a task, plus required steps its goal text states. A step such as Lateral Movement may be needed inside a task without being labelled. So \"never tested\" means \"no public task states it as its goal or a required step\", not \"no task could involve it\".",
    "Tasks and steps are different units. Do not read task counts and step counts as a ratio.",
    "The three incidents were chosen because they are well documented. They are not a random sample. Do not generalise from them.",
    "No monitor has been run. \"Tested\" does not mean \"caught\".",
    "All labels are drafts until a human reviews them.",
]


def parent(tech: str | None) -> str | None:
    return tech.split(".")[0] if tech else None


def load_public_tasks() -> list[dict]:
    out = []
    for f in c.public_task_files():
        t = c.load_yaml(f)
        lab = t.get("labels")
        if not lab:
            continue
        a, alt = lab["attack"], lab.get("alternative")
        out.append(dict(uid=f"{t['setting']}/{t['environment']}/{t['id']}", setting=t["setting"], primary=a["primary_tactic"],
                        technique=a["technique"], steps=list(a["required_step_tactics"]), confidence=lab["confidence"],
                        alternative=dict(tactic=alt["tactic"], technique=alt.get("technique")) if alt else None))
    return sorted(out, key=lambda t: t["uid"])


def judge_pair(tactic: str, technique: str | None, tasks: list[dict]) -> dict:
    p = parent(technique)
    tech = sorted(t["uid"] for t in tasks if p and parent(t["technique"]) == p)
    goal = sorted(t["uid"] for t in tasks if t["primary"] == tactic)
    step = sorted(t["uid"] for t in tasks if tactic in t["steps"])
    verdict = "tested_technique" if tech else "tested_tactic_only" if (goal or step) else "not_tested"
    return dict(verdict=verdict, technique_task_uids=tech, tactic_goal_task_uids=goal, tactic_step_task_uids=step)


def _flip(t: dict) -> dict:
    return dict(t, primary=t["alternative"]["tactic"], technique=t["alternative"].get("technique"))


def _verdict(a: dict, tasks: list[dict]) -> tuple[str, str, str | None]:
    v = judge_pair(a["primary_tactic"], a.get("technique"), tasks)["verdict"]
    alt = a.get("alternative")
    va = judge_pair(alt["tactic"], alt.get("technique"), tasks)["verdict"] if a.get("confidence") == "ambiguous" and alt else None
    return ("unclear" if va is not None and va != v else v), v, va


def judge_step(step: dict, tasks: list[dict]) -> dict | None:
    """Verdict and matching tasks for one step, or None if the step is not an attack step."""
    if step.get("phase") != "attack" or not step.get("attack"):
        return None
    a = step["attack"]
    base = judge_pair(a["primary_tactic"], a.get("technique"), tasks)
    verdict, vp, va = _verdict(a, tasks)
    amb = [i for i, t in enumerate(tasks) if t["confidence"] == "ambiguous" and t.get("alternative")]
    trials = [[_flip(t) if j == i else t for j, t in enumerate(tasks)] for i in amb]
    if amb:
        trials.append([_flip(t) if i in amb else t for i, t in enumerate(tasks)])
    changed_by = sorted({tasks[i]["uid"] for k, i in enumerate(amb) if _verdict(a, trials[k])[0] != verdict})
    stable = not changed_by and all(_verdict(a, tr)[0] == verdict for tr in trials)
    return dict(verdict=verdict, verdict_primary=vp, verdict_alternative=va, verdict_stable=stable,
                verdict_changed_by_task=changed_by, technique_task_uids=base["technique_task_uids"],
                tactic_goal_task_uids=base["tactic_goal_task_uids"], tactic_step_task_uids=base["tactic_step_task_uids"],
                tasks_tactic_as_goal=len(base["tactic_goal_task_uids"]), tasks_tactic_as_step=len(base["tactic_step_task_uids"]))


def _prediction(incidents: list[dict], tactic_rows: list[dict]) -> dict:
    zero = [t["id"] for t in tactic_rows if t["tasks_as_goal"] == 0 and t["tasks_as_step"] == 0]
    per, firm = {}, {}
    for inc in incidents:
        hits = [s for s in inc["steps"] if s["phase"] == "attack" and s["primary_tactic"] in PREDICTION_TACTICS]
        per[inc["id"]] = len(hits)
        firm[inc["id"]] = sum(1 for s in hits if not (s["alternative_tactic"] and s["alternative_tactic"] not in PREDICTION_TACTICS))
    total, n_inc, n_firm_inc = sum(per.values()), sum(1 for v in per.values() if v), sum(1 for v in firm.values() if v)
    result = "failed" if total <= 1 else "held" if n_firm_inc >= 2 else "partly_held"
    return dict(tactics=PREDICTION_TACTICS, tactics_with_zero_public_tasks_now=zero,
                still_zero_task_tactics=sorted(zero) == sorted(PREDICTION_TACTICS), steps_in_these_tactics=total,
                steps_by_incident=per, steps_not_resting_on_an_ambiguous_label=sum(firm.values()),
                steps_not_resting_on_an_ambiguous_label_by_incident=firm, incidents_with_such_steps=n_inc, result=result,
                rule="held: such steps in at least two incidents, not counting ambiguous steps whose alternative lies outside the four tactics; "
                     "partly_held: in one incident only, or only as such ambiguous steps; failed: one step or none in total.")


def build(tasks: list[dict] | None = None) -> dict:
    fw = fwm.load()["attack"]
    tasks = load_public_tasks() if tasks is None else tasks
    tname = {t["id"]: t["name"] for t in fw["tactics"]}
    sources = vi.load_sources()
    incidents = []
    for f in vi.incident_files():
        inc = c.load_yaml(f)
        steps = []
        for s in sorted(inc["steps"], key=lambda s: s["order"]):
            src = sources.get(s["evidence"]["source"], {})
            row = dict(id=s["id"], order=s["order"], order_basis=s["order_basis"], time=s["time"],
                       time_source_local=s.get("time_source_local"), time_conflict=s.get("time_conflict"),
                       time_precision=s["time_precision"], phase=s["phase"], what_happened=s["what_happened"],
                       real_target=s.get("real_target"), quote=s["evidence"]["quote"], locator=s["evidence"]["locator"],
                       source=s["evidence"]["source"], source_url=src.get("url"), source_title=src.get("title"),
                       source_publisher=src.get("publisher"), label_status=s["label_status"], labeled_by=s["labeled_by"],
                       reviewed_by=s["reviewed_by"], history=s["history"])
            j = judge_step(s, tasks)
            if j:
                a, alt = s["attack"], s["attack"].get("alternative")
                tech = fw["techniques"].get(a["technique"] or "", {})
                row.update(primary_tactic=a["primary_tactic"], primary_tactic_name=tname.get(a["primary_tactic"]),
                           technique=a["technique"], technique_name=tech.get("name"), confidence=a["confidence"],
                           rationale=a["rationale"], alternative_tactic=alt["tactic"] if alt else None,
                           alternative_tactic_name=tname.get(alt["tactic"]) if alt else None,
                           alternative_technique=alt.get("technique") if alt else None,
                           alternative_reason=alt["reason"] if alt else None, **j)
            steps.append(row)
        att = [s for s in steps if s["phase"] == "attack"]
        incidents.append(dict(
            id=inc["id"], title=inc["title"], developer=inc["developer"], incident_type=inc["incident_type"],
            incident_type_plain=inc["incident_type_plain"], dates=inc["dates"], swarms_wiki=inc["swarms_wiki"],
            summary=inc["summary"], notes=inc.get("notes", []), agent_count_claims=inc["agent_count_claims"],
            sources=[dict(id=sid, **{k: sources[sid].get(k) for k in ("url", "title", "publisher", "published", "accessed", "read_extent", "read_note", "supersedes", "superseded_by")})
                     for sid in inc["sources_used"]],
            total_steps=len(steps), attack_steps=len(att),
            detection_steps=sum(1 for s in steps if s["phase"] == "detection"), response_steps=sum(1 for s in steps if s["phase"] == "response"),
            verdict_counts={v: sum(1 for s in att if s["verdict"] == v) for v in VERDICTS},
            unstable_verdicts=sum(1 for s in att if not s["verdict_stable"]),
            ambiguous_steps=sum(1 for s in att if s["confidence"] == "ambiguous"),
            status_counts={k: sum(1 for s in steps if s["label_status"] == k) for k in ["draft_needs_human_review", "evidence_checked", "reviewed", "adjudicated"]},
            steps=steps))
    incidents.sort(key=lambda i: (i["dates"]["disclosed"], i["id"]))
    all_att = [(i["id"], s) for i in incidents for s in i["steps"] if s["phase"] == "attack"]
    tactic_rows = []
    for t in fw["tactics"]:
        mine = [(iid, s) for iid, s in all_att if s["primary_tactic"] == t["id"]]
        goal = sorted(x["uid"] for x in tasks if x["primary"] == t["id"])
        step = sorted(x["uid"] for x in tasks if t["id"] in x["steps"])
        tactic_rows.append(dict(
            id=t["id"], name=t["name"], tasks_as_goal=len(goal), tasks_as_step=len(step), goal_task_uids=goal, step_task_uids=step,
            incident_steps=len(mine), steps_by_verdict={v: sum(1 for _, s in mine if s["verdict"] == v) for v in VERDICTS},
            steps_never_tested=sum(1 for _, s in mine if s["verdict"] == "not_tested"),
            steps_by_incident={i["id"]: sum(1 for iid, _ in mine if iid == i["id"]) for i in incidents},
            step_refs=[dict(incident=iid, step=s["id"], verdict=s["verdict"], what_happened=s["what_happened"]) for iid, s in mine]))
    return dict(
        provisional=True, note="Draft. No human has reviewed any label yet.",
        versions=dict(attack=fw["version"], codebook_steps="1.3-draft"),
        verdicts=[dict(id=v, label=VERDICT_LABELS[v]) for v in VERDICTS], limits=LIMITS,
        totals=dict(incidents=len(incidents), steps=sum(i["total_steps"] for i in incidents), attack_steps=len(all_att),
                    detection_steps=sum(i["detection_steps"] for i in incidents), response_steps=sum(i["response_steps"] for i in incidents),
                    public_tasks=len(tasks), verdict_counts={v: sum(1 for _, s in all_att if s["verdict"] == v) for v in VERDICTS},
                    unstable_verdicts=sum(1 for _, s in all_att if not s["verdict_stable"]),
                    ambiguous_steps=sum(1 for _, s in all_att if s["confidence"] == "ambiguous"),
                    steps_with_null_technique=sum(1 for _, s in all_att if s["technique"] is None),
                    status_counts={k: sum(i["status_counts"][k] for i in incidents) for k in ["draft_needs_human_review", "evidence_checked", "reviewed", "adjudicated"]}),
        prediction=_prediction(incidents, tactic_rows), tactics=tactic_rows, incidents=incidents)


def build_activity() -> dict:
    groups = {}
    for f in vi.incident_files():
        inc = c.load_yaml(f)
        for s in inc["steps"]:
            for h in s["history"]:
                key = (h["date"], inc["id"], h["change"], h["who"])
                g = groups.setdefault(key, dict(date=h["date"], incident=inc["id"], incident_title=inc["title"], who=h["who"],
                                                change=h["change"], reason=h["reason"], steps=0, step_ids=[]))
                g["steps"] += 1
                g["step_ids"].append(s["id"])
    rows = sorted(groups.values(), key=lambda r: (r["date"], r["incident"], r["change"]), reverse=True)
    return dict(note="Built from the history fields in data/incidents/*.yml. Updates on each deploy.", entries=rows)


def build_matrix(cov: dict, tasks: list[dict] | None = None) -> dict:
    """Tactic by technique cells for the home page tool: how many public tasks and how many incident steps sit in each.
    Techniques are grouped at parent level. A cell is a `gap` when incidents show it and no public task has it."""
    fw = fwm.load()["attack"]
    tasks = load_public_tasks() if tasks is None else tasks
    out = []
    for t in cov["tactics"]:
        cells = {}
        def cell(tech):
            p = parent(tech)
            return cells.setdefault(p or "none", dict(key=f'{t["id"]}/{p or "none"}', technique=p, name=fw["techniques"].get(p or "", {}).get("name") or ("No technique given" if not p else p),
                                                         task_uids=[], step_refs=[]))
        for x in tasks:
            if x["primary"] == t["id"]:
                cell(x["technique"])["task_uids"].append(x["uid"])
        for inc in cov["incidents"]:
            for s in inc["steps"]:
                if s["phase"] == "attack" and s["primary_tactic"] == t["id"]:
                    cell(s["technique"])["step_refs"].append(dict(incident=inc["id"], incident_title=inc["title"], step=s["id"], verdict=s["verdict"],
                                                                 what_happened=s["what_happened"], source_url=s["source_url"]))
        rows = []
        for cl in cells.values():
            cl.update(tasks=len(cl["task_uids"]), steps=len(cl["step_refs"]), task_uids=sorted(cl["task_uids"]))
            cl["state"] = "gap" if cl["steps"] and not cl["tasks"] else "both" if cl["steps"] else "tests_only"
            rows.append(cl)
        rows.sort(key=lambda r: (-r["steps"], -r["tasks"], r["key"]))
        out.append(dict(id=t["id"], name=t["name"], tasks_as_goal=t["tasks_as_goal"], tasks_as_step=t["tasks_as_step"],
                        incident_steps=sum(r["steps"] for r in rows), cells=rows))
    allc = [r for t in out for r in t["cells"]]
    real = [r for r in allc if r["steps"]]
    return dict(note="A cell is one technique under one tactic (sub-techniques grouped under their parent). Draft: no human has reviewed any label yet.",
                totals=dict(cells=len(allc), cells_seen_in_incidents=len(real), cells_seen_and_tested=sum(1 for r in real if r["tasks"]),
                            cells_seen_not_tested=sum(1 for r in real if not r["tasks"]), cells_tests_only=sum(1 for r in allc if not r["steps"])),
                tactics=out)


def csv_safe(v) -> str:
    """A value for a CSV cell. A leading =, +, - or @ would be run as a formula by a spreadsheet, so it gets a quote in front."""
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "@") or (v[:1] == "-" and len(v) > 1 and not v[1].isdigit()) else v


def steps_csv(cov: dict) -> str:
    import csv
    import io
    cols = ["incident", "step", "order", "phase", "time_utc", "tactic_id", "tactic", "technique_id", "technique", "confidence", "verdict",
            "tasks_same_technique", "tasks_tactic_as_goal", "tasks_tactic_as_step", "label_status", "what_happened", "quote", "source", "source_url"]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for inc in cov["incidents"]:
        for s in inc["steps"]:
            a = s["phase"] == "attack"
            w.writerow([csv_safe(x) for x in (
                inc["id"], s["id"], s["order"], s["phase"], s["time"] or "", s.get("primary_tactic", ""), s.get("primary_tactic_name", ""), s.get("technique") or "",
                s.get("technique_name") or "", s.get("confidence", ""), s.get("verdict", ""), len(s["technique_task_uids"]) if a else "", s["tasks_tactic_as_goal"] if a else "",
                s["tasks_tactic_as_step"] if a else "", s["label_status"], s["what_happened"], s["quote"], s["source_publisher"], s["source_url"])])
    return buf.getvalue()


def incident_layer(cov: dict, tasks: list[dict] | None = None) -> dict:
    """An ATT&CK Navigator layer (format 4.5): incident steps per technique. Red = no public task has that technique."""
    fw = fwm.load()["attack"]
    tasks = load_public_tasks() if tasks is None else tasks
    short = {t["id"]: t["shortname"] for t in fw["tactics"]}
    tested = {parent(x["technique"]) for x in tasks if x["technique"]}
    by = {}
    for inc in cov["incidents"]:
        for s in inc["steps"]:
            if s["phase"] == "attack" and s["technique"]:
                by.setdefault((s["technique"], s["primary_tactic"]), []).append(f'{inc["id"]}/{s["id"]}')
    techs = [dict(techniqueID=k, tactic=short[tac], score=len(v), color="#b91c1c" if parent(k) not in tested else "#b45309",
                  comment=f"{len(v)} incident step(s): " + ", ".join(v) + (". No public side task has this technique." if parent(k) not in tested else ""), enabled=True)
             for (k, tac), v in sorted(by.items())]
    t = cov["totals"]
    return dict(
        name="ACTCM: real AI agent incident steps", versions=dict(attack=fw["version"].split(".")[0], navigator="5.1.0", layer="4.5"), domain="enterprise-attack",
        description=(f"Steps from {t['incidents']} documented incidents in which AI agents acted against real systems, placed on MITRE ATT&CK® Enterprise v{fw['version']}. "
                     f"{sum(len(v) for v in by.values())} of {t['attack_steps']} attack steps have a technique and are shown; the rest have none. "
                     "Red: no public AI control side task has that technique. Amber: some public task has it. Untested does not mean undefended, and no monitor has been run. "
                     "The incidents were chosen because they are well documented; they are not a random sample. Draft: all labels were drafted by an AI. No human has reviewed any label yet. "
                     "Not affiliated with or endorsed by The MITRE Corporation."),
        sorting=3, layout=dict(layout="side", showID=True, showName=True, showAggregateScores=False, countUnscored=False, aggregateFunction="sum", expandedSubtechniques="annotated"),
        hideDisabled=False, techniques=techs,
        legendItems=[dict(label="Seen in an incident, no public task has this technique", color="#b91c1c"), dict(label="Seen in an incident, a public task has this technique", color="#b45309")],
        showTacticRowBackground=False, tacticRowBackground="#dddddd", selectTechniquesAcrossTactics=True, selectSubtechniquesWithParent=True, selectVisibleTechniques=False,
        metadata=[dict(name="Project", value="Agent Control Threat Coverage Matrix (ACTCM)"), dict(name="Status", value="Draft: no human has reviewed any label"),
                  dict(name="ATT&CK version", value=fw["version"])],
        links=[dict(label="ACTCM repository", url=f"https://github.com/{c.config()['repository']}")])


def render(obj: dict) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    cov = build()
    OUT.write_text(render(cov), encoding="utf-8")
    ACTIVITY.write_text(render(build_activity()), encoding="utf-8")
    (GEN / "matrix.json").write_text(render(build_matrix(cov)), encoding="utf-8")
    (GEN / "incident_steps.csv").write_text(steps_csv(cov), encoding="utf-8")
    (GEN / "incident_layer.json").write_text(render(incident_layer(cov)), encoding="utf-8")
    t = cov["totals"]
    print(f"{t['incidents']} incidents, {t['attack_steps']} attack steps vs {t['public_tasks']} public tasks: {t['verdict_counts']}; "
          f"{t['unstable_verdicts']} verdicts not stable; prediction {cov['prediction']['result']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
