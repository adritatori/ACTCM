#!/usr/bin/env python3
"""Phase 3: compare our draft labels with the blind second rater and set the ai_cross_checked tier.

  crosscheck.py apply data/drafts/blind_pass_2026-11-04.yml

A task becomes `ai_cross_checked` only if ALL of these hold:
  1. our label is `clear`,
  2. the blind rater's label is `clear`,
  3. both chose the same primary tactic,
  4. the techniques agree: identical, same parent family (T1565.001 vs T1565), or both null.
Required steps and the ATLAS label are compared and recorded but do not block the tier.
Tasks whose upstream scorer is marked "planned, not yet implemented" are never promoted.
This is an AI-versus-AI check. It is not human review.
"""
from __future__ import annotations

import sys
from datetime import date

import common as c
import frameworks as fwm
import labels as L

BLIND_RATER = "claude_blind_2026-11-04"
CHECKER = "claude_crosscheck_2026-11-04"
NULLS = {None, "", "null", "none", "n/a", "na", "~"}


def norm_id(x):
    if x is None:
        return None
    s = str(x).strip()
    if s.lower() in NULLS:
        return None
    return s.split()[0].upper().rstrip(".,;")  # "AML.T0059 Erode ..." -> "AML.T0059"


def norm_conf(x):
    return str(x).strip().lower() if x is not None else None


def norm_steps(x) -> list:
    if x is None:
        return []
    if isinstance(x, str):
        x = [p for p in x.replace(";", ",").split(",")]
    return sorted({norm_id(s) for s in x if norm_id(s)})


def family(t):
    return t.split(".")[0] if t else None


def technique_match(a, b) -> str:
    a, b = norm_id(a), norm_id(b)
    if a is None and b is None:
        return "both_null"
    if a is None or b is None:
        return "one_null"
    if a == b:
        return "exact"
    if family(a) == family(b):
        return "family"
    return "differ"


def jaccard(a, b) -> float:
    a, b = set(norm_steps(a)), set(norm_steps(b))
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def compare(ours: dict | None, blind: dict | None) -> dict:
    """Pure comparison of two labels. `ours` is a task's `labels`; `blind` is a blind-file entry."""
    if not ours or not blind:
        return dict(comparable=False)
    oa = ours.get("attack") or {}
    return dict(
        comparable=True,
        agrees_tactic=norm_id(oa.get("primary_tactic")) == norm_id(blind.get("primary")) and norm_id(blind.get("primary")) is not None,
        technique_match=technique_match(oa.get("technique"), blind.get("technique")),
        steps_jaccard=round(jaccard(oa.get("required_step_tactics"), blind.get("steps")), 3),
        atlas_match=norm_id((ours.get("atlas") or {}).get("technique")) == norm_id(blind.get("atlas")),
        our_confidence=norm_conf(ours.get("confidence")),
        blind_confidence=norm_conf(blind.get("confidence")))


def qualifies(cmp: dict, task: dict | None = None) -> tuple[bool, str]:
    """`task` is optional so the label comparison can be tested alone; apply() always passes it."""
    if task is not None and task.get("scorer_status") == "planned_not_implemented":
        return False, "scorer is planned, not built; never promoted"
    if not cmp.get("comparable"):
        return False, "no blind label to compare"
    if cmp["our_confidence"] != "clear":
        return False, "our label is not clear"
    if cmp["blind_confidence"] != "clear":
        return False, "blind rater was not clear"
    if not cmp["agrees_tactic"]:
        return False, "primary tactic differs"
    if cmp["technique_match"] not in ("exact", "family", "both_null"):
        return False, f"technique {cmp['technique_match']}"
    return True, "same primary tactic and technique family, both clear"


def blind_entry_errors(e: dict, fw: dict) -> list[str]:
    errs = []
    tactics = {t["id"] for t in fw["attack"]["tactics"]}
    if norm_id(e.get("primary")) not in tactics:
        errs.append(f"primary {e.get('primary')!r} is not a v20 tactic ID")
    for s in norm_steps(e.get("steps")):
        if s not in tactics:
            errs.append(f"step {s!r} is not a tactic ID")
    t = norm_id(e.get("technique"))
    if t and fwm.check_techniques(fw, "attack", [t]):
        errs += fwm.check_techniques(fw, "attack", [t])
    a = norm_id(e.get("atlas"))
    if a and fwm.check_techniques(fw, "atlas", [a]):
        errs += fwm.check_techniques(fw, "atlas", [a])
    if norm_conf(e.get("confidence")) not in ("clear", "ambiguous"):
        errs.append(f"confidence {e.get('confidence')!r}")
    return errs


def load_blind(path, fw) -> tuple[dict, list[str]]:
    """Return ({key: entry}, problems). Duplicate keys and invalid entries are problems."""
    data = c.load_yaml(c.ROOT / path if not str(path).startswith("/") else __import__("pathlib").Path(path))
    out, problems = {}, []
    for e in data or []:
        k = e.get("key")
        if k in out:
            problems.append(f"duplicate key {k}")
            continue
        errs = blind_entry_errors(e, fw)
        if errs:
            problems.append(f"{k}: " + "; ".join(errs))
            e = dict(e, _invalid=True)
        out[k] = e
    return out, problems


def apply(path: str, today: str | None = None) -> dict:
    fw = fwm.load()
    blind, problems = load_blind(path, fw)
    tasks = L.load_tasks()
    today = today or date.today().isoformat()
    stats = dict(total=0, qualified=0, tactic_agree=0, no_blind=0, invalid_blind=0, promoted=0, demoted=0)
    for (env, tid), (f, t) in tasks.items():
        key = f"{env}/{tid}"
        e = blind.get(key)
        stats["total"] += 1
        if e is None or e.get("_invalid"):
            stats["no_blind" if e is None else "invalid_blind"] += 1
            cmp = dict(comparable=False)
        else:
            cmp = compare(t.get("labels"), e)
        ok, why = qualifies(cmp, t)
        stats["qualified"] += ok
        stats["tactic_agree"] += bool(cmp.get("agrees_tactic"))
        t["cross_check"] = dict(
            rater=BLIND_RATER, date=today, comparable=cmp.get("comparable", False),
            agrees_tactic=cmp.get("agrees_tactic"), technique_match=cmp.get("technique_match"),
            steps_jaccard=cmp.get("steps_jaccard"), atlas_match=cmp.get("atlas_match"),
            blind_confidence=cmp.get("blind_confidence"), qualified=ok, why=why,
            note="AI-versus-AI check. Not human review.")
        cur = t.get("label_status")
        if cur not in L.HUMAN_ONLY:  # never touch a human-set tier
            if ok and cur == "draft_needs_human_review":
                L.set_status(t, "ai_cross_checked", CHECKER, "blind second pass agreed", why, today)
                stats["promoted"] += 1
            elif not ok and cur == "ai_cross_checked":
                L.set_status(t, "draft_needs_human_review", CHECKER, "cross-check no longer holds", why, today)
                stats["demoted"] += 1
        c.dump_yaml(t, f)
    stats["problems"] = problems
    return stats


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "apply":
        sys.exit(__doc__)
    s = apply(sys.argv[2])
    print({k: v for k, v in s.items() if k != "problems"})
    for p in s["problems"]:
        print("PROBLEM", p)
