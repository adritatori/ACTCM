"""Label validity checks (reused by validate.py in Phase 4).

Errors fail the build. Warnings do not (a technique that sits in several tactics is a warning).
"""
from __future__ import annotations

import sys

import common as c
import frameworks as fwm
import labels as L

CONFIDENCE = {"clear", "ambiguous"}


def check_task(t: dict, fw: dict) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    tid = t.get("id", "?")
    att = fw["attack"]
    tactic_set = {x["id"] for x in att["tactics"]}
    status = t.get("label_status")
    lab = t.get("labels")
    if status not in L.TIERS and status != L.UNLABELLED:
        errs.append(f"{tid}: unknown label_status {status!r}")
    if lab is None:
        if status != L.UNLABELLED:
            errs.append(f"{tid}: status {status!r} but no labels")
        return errs, warns
    a = (lab.get("attack") or {})
    p = a.get("primary_tactic")
    if p not in tactic_set:
        errs.append(f"{tid}: primary_tactic {p!r} is not an ATT&CK v{att['version']} tactic ID")
    steps = a.get("required_step_tactics")
    if not isinstance(steps, list):
        errs.append(f"{tid}: required_step_tactics must be a list")
        steps = []
    for s in steps:
        if s not in tactic_set:
            errs.append(f"{tid}: required step {s!r} is not a tactic ID")
    if p in steps:
        warns.append(f"{tid}: primary tactic {p} is also listed as a required step")
    if len(set(steps)) != len(steps):
        warns.append(f"{tid}: duplicate required steps")
    tech = a.get("technique")
    if tech is not None:
        errs += [f"{tid}: {e}" for e in fwm.check_techniques(fw, "attack", [tech])]
        info = att["techniques"].get(tech)
        if info and p in tactic_set:
            if p not in info["tactics"]:
                errs.append(f"{tid}: technique {tech} is not in tactic {p} in v{att['version']} (it is in {info['tactics']})")
            elif len(info["tactics"]) > 1:
                warns.append(f"{tid}: technique {tech} sits in {len(info['tactics'])} tactics {info['tactics']}")
    elif not (lab.get("rationale") or "").strip():
        errs.append(f"{tid}: technique is null (R9) but no rationale explains why")
    atl = (lab.get("atlas") or {}).get("technique")
    if atl is not None:
        errs += [f"{tid}: {e}" for e in fwm.check_techniques(fw, "atlas", [atl])]
    conf = lab.get("confidence")
    if conf not in CONFIDENCE:
        errs.append(f"{tid}: confidence {conf!r} must be clear or ambiguous")
    fit = lab.get("technique_fit")
    if fit is not None and fit not in ("specific", "parent_only", "none"):
        errs.append(f"{tid}: technique_fit {fit!r} must be specific, parent_only or none")
    if tech is None and fit not in (None, "none"):
        errs.append(f"{tid}: technique is null but technique_fit is {fit!r}")
    if tech is not None and fit == "none":
        errs.append(f"{tid}: technique_fit none but a technique is set")
    alt = lab.get("alternative")
    if conf == "ambiguous":
        if not isinstance(alt, dict) or alt.get("tactic") not in tactic_set or not (alt.get("reason") or "").strip():
            errs.append(f"{tid}: ambiguous label needs an alternative with a valid tactic and a reason")
        elif alt["tactic"] == p and alt.get("technique") in (None, tech):
            warns.append(f"{tid}: alternative equals the primary label")
        elif alt.get("technique") is not None:
            errs += [f"{tid}: alternative {e}" for e in fwm.check_techniques(fw, "attack", [alt["technique"]])]
    elif alt:
        warns.append(f"{tid}: clear label carries an alternative")
    if not (lab.get("rationale") or "").strip():
        errs.append(f"{tid}: empty rationale")
    # bot guard: reviewed/adjudicated need a listed human and no bot in labeled history
    if status in L.HUMAN_ONLY:
        if t.get("reviewed_by") not in L.HUMAN_REVIEWERS:
            errs.append(f"{tid}: status {status} but reviewed_by {t.get('reviewed_by')!r} is not a listed human")
        if not any(h.get("who") in L.HUMAN_REVIEWERS and status in str(h.get("change", ""))
                   for h in t.get("history") or []):
            errs.append(f"{tid}: status {status} has no history entry by a listed human")
    elif t.get("reviewed_by"):
        errs.append(f"{tid}: reviewed_by set but status is {status}")
    if status == "ai_cross_checked" and conf != "clear":
        errs.append(f"{tid}: ai_cross_checked requires a clear label")
    if status == "ai_cross_checked" and t.get("scorer_status") == "planned_not_implemented":
        errs.append(f"{tid}: ai_cross_checked but the upstream scorer is planned, not built")
    if status == "ai_cross_checked" and not t.get("cross_check"):
        errs.append(f"{tid}: ai_cross_checked without a cross_check record")
    return errs, warns


def main() -> int:
    fw = fwm.load()
    E, W, n = [], [], 0
    for f in sorted(c.TASKS_DIR.rglob("*.yml")):
        e, w = check_task(c.load_yaml(f), fw)
        E += e; W += w; n += 1
    print(f"checked {n} task files: {len(E)} errors, {len(W)} warnings")
    for x in E:
        print("ERROR", x)
    for x in W:
        print("warn ", x)
    return 1 if E else 0


if __name__ == "__main__":
    sys.exit(main())
