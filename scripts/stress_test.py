#!/usr/bin/env python3
"""Phase 4: does the coverage finding survive label noise, rewording and disagreement?

(1) Label perturbation, 5,000 runs, fixed seed: an ambiguous label flips to its alternative with p = 0.5;
    any task with required steps takes one of them as its main tactic with p = 0.25.
    Reported per gap tactic: the share of runs in which it STAYS at 0 tasks.
    A gap counts as ROBUST only if that share is >= 95%. This threshold is our choice, not a standard.
(2) The same, re-run with the ORIGINAL (pre-v1.1) required steps put back, to show how the R2 removals changed
    gap robustness. Nothing is changed in real files.
(3) Rewording robustness of the keyword SUGGESTER (suggestion only; never used as a label).

Writes data/generated/stress_results.json. All results are PROVISIONAL (see counts.json).
"""
from __future__ import annotations

import copy
import json
import random
import re
from collections import Counter

import agreement as ag
import build as B
import common as c
import frameworks as fwm
import suggest as S

N_RUNS = 5000
SEED = 20261104
P_FLIP, P_STEP = 0.5, 0.25
ROBUST = 0.95
SYN = {"exfiltrate": ["smuggle out", "send off-box", "ship"], "malware": ["a payload", "a binary blob"],
       "reverse shell": ["callback connection", "outbound interactive session"],
       "credential": ["login secret", "API key"], "delete": ["wipe", "purge"], "suppress": ["quietly drop", "mute"],
       "remote code execution": ["a way for outsiders to run their code"], "corrupt": ["subtly break"]}
DISTRACT = [" Make sure the audit log looks normal.", " Avoid triggering the monitor.",
            " Use the admin credentials if needed.", " Do this while refactoring the backup job."]


def simulate(tasks: list[dict], watch: list[str], runs: int = N_RUNS, seed: int = SEED,
             p_flip: float = P_FLIP, p_step: float = P_STEP) -> dict:
    """Return {tactic: share of runs where `tactic` has 0 tasks} for tactics in `watch`."""
    rnd = random.Random(seed)
    base = []
    for t in tasks:
        lab = t.get("labels") or {}
        a = lab.get("attack") or {}
        if not a.get("primary_tactic"):
            continue
        alt = lab.get("alternative")
        base.append((a["primary_tactic"], (alt or {}).get("tactic") if lab.get("confidence") == "ambiguous" else None,
                     list(a.get("required_step_tactics") or [])))
    stay = Counter()
    for _ in range(runs):
        got = set()
        for prim, alt, steps in base:
            choice = prim
            if alt and rnd.random() < p_flip:
                choice = alt
            if steps and rnd.random() < p_step:
                choice = rnd.choice(steps)
            got.add(choice)
        for g in watch:
            stay[g] += g not in got
    return {g: stay[g] / runs for g in watch}


REMOVED = re.compile(r"removed required step(?:\(s\)|s)? ((?:TA\d{4}(?:, )?)+)")


def restore_original_steps(tasks: list[dict]) -> list[dict]:
    """Copy of tasks with the PRE-v1.1 required steps put back. The removed steps are read from each task's own
    history entries ("removed required step(s) TA0006, TA0009 ..."). Real files are untouched."""
    out = []
    for t in tasks:
        t2 = copy.deepcopy(t)
        if t2.get("labels"):
            steps = t2["labels"]["attack"]["required_step_tactics"]
            for h in t.get("history") or []:
                m = REMOVED.search(h.get("change", ""))
                if m:
                    steps = steps + [x for x in m.group(1).split(", ") if x not in steps]
            t2["labels"]["attack"]["required_step_tactics"] = steps
        out.append(t2)
    return out


def perturb(text: str, rnd: random.Random) -> str:
    s = text
    for k_, vs in SYN.items():
        if k_ in s.lower() and rnd.random() < 0.7:
            s = re.sub(re.escape(k_), rnd.choice(vs), s, flags=re.I)
    if rnd.random() < 0.5:
        s += rnd.choice(DISTRACT)
    if rnd.random() < 0.3 and s:
        j = rnd.randrange(len(s)); s = s[:j] + s[j + 1:]
    return s


def suggester_robustness(tasks: list[dict], reps: int = 20, seed: int = 7) -> dict:
    rnd = random.Random(seed)
    rows = []
    for t in tasks:
        text = t.get("goal_text") or t.get("our_summary") or ""
        lab = t["labels"]
        rows.append((t["id"], text, lab["attack"]["primary_tactic"], (lab.get("alternative") or {}).get("tactic")))

    def ok(s, prim, alt):
        return s == prim or (alt is not None and s == alt)
    clean = [S.suggest(x[1]) for x in rows]
    exact = sum(s == r[2] for s, r in zip(clean, rows))
    with_alt = sum(ok(s, r[2], r[3]) for s, r in zip(clean, rows))
    kap = ag.kappa([r[2] for r in rows], clean)
    trials = []
    for _ in range(reps):
        trials.append(sum(ok(S.suggest(perturb(r[1], rnd)), r[2], r[3]) for r in rows) / len(rows))
    return dict(n=len(rows), exact=exact, exact_pct=round(100 * exact / len(rows), 1),
                with_alternative=with_alt, with_alternative_pct=round(100 * with_alt / len(rows), 1),
                kappa_vs_our_primary=round(kap["kappa"], 3), unlabeled=sum(s == "UNLABELED" for s in clean),
                reworded_mean_pct=round(100 * sum(trials) / reps, 1), reworded_min_pct=round(100 * min(trials), 1),
                reworded_max_pct=round(100 * max(trials), 1),
                note="SUGGESTION ONLY. These keyword suggestions are never written to a label.")


def main() -> dict:
    fw = fwm.load()
    tasks = [c.load_yaml(f) for f in c.public_task_files()]
    tasks.sort(key=lambda t: (t["setting"], t["environment"], t["id"]))
    cn = B.build_counts(tasks, fw, c.load_yaml(c.LOCK_FILE))
    gaps = cn["gaps"]["primary"]
    names = {t["id"]: t["name"] for t in fw["attack"]["tactics"]}
    cur = simulate(tasks, gaps)
    before = simulate(restore_original_steps(tasks), gaps)
    res = dict(
        provisional=True, runs=N_RUNS, seed=SEED, p_flip_ambiguous=P_FLIP, p_take_step=P_STEP,
        robust_threshold=ROBUST, threshold_note="Our choice, not a standard.",
        baseline_gaps_primary=gaps, baseline_gaps_with_steps=cn["gaps"]["with_steps"],
        gap_stays_zero=[dict(tactic=g, name=names[g], current_labels=round(cur[g], 4), robust_current=cur[g] >= ROBUST,
                             before_v1_1_original_steps=round(before[g], 4), robust_before=before[g] >= ROBUST) for g in gaps],
        suggester=suggester_robustness(tasks))
    (c.DATA / "generated" / "stress_results.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    return res


def report(r: dict) -> None:
    print(f"Label perturbation: {r['runs']} runs, seed {r['seed']}, flip p={r['p_flip_ambiguous']}, step p={r['p_take_step']}")
    print(f"{'gap tactic':30}{'stays 0 now':>13}{'before v1.1':>13}  robust now (>=95%)")
    for g in r["gap_stays_zero"]:
        print(f"{g['tactic']+' '+g['name']:30}{100*g['current_labels']:>12.1f}%{100*g['before_v1_1_original_steps']:>12.1f}%  {'YES' if g['robust_current'] else 'NO'}")
    s = r["suggester"]
    print(f"\nKeyword suggester (SUGGESTION ONLY), n={s['n']}: exact {s['exact_pct']}%, with alternative {s['with_alternative_pct']}%, "
          f"kappa {s['kappa_vs_our_primary']}, unlabeled {s['unlabeled']}; after rewording mean {s['reworded_mean_pct']}% "
          f"(min {s['reworded_min_pct']}%, max {s['reworded_max_pct']}%)")


if __name__ == "__main__":
    report(main())
