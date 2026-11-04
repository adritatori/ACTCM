#!/usr/bin/env python3
"""Terminal tool for a human to review labels, one task at a time.

  uv run python scripts/review.py --queue start_here     # the "start here" list first
  uv run python scripts/review.py --queue sheet          # review_sheet.csv order (disagreements first)
  uv run python scripts/review.py --queue all
  uv run python scripts/review.py --only auto_workflow/aw_rce

For each task you see the goal, what the scorer checks, and the label. Then:
  y  agree. Status becomes `reviewed`, with your name, the date and a history entry.
  n  disagree. You give the new tactic (and technique), a reason, and the confidence.
     Status becomes `reviewed` with your label.
  s  skip. Nothing changes.
  q  quit. Everything you already decided is already saved.

This tool records a HUMAN decision. It refuses to run without an interactive terminal
(so a script or bot cannot use it), and it refuses a reviewer name that is not on the
list in scripts/labels.py. Progress is saved after every decision.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from datetime import date

import common as c
import frameworks as fwm
import labels as L

DEFAULT_REVIEWER = "Adrita Rahman Tory"
MAX_BAD_INPUTS = 5
SKIP_TIERS = {"reviewed", "adjudicated"}


class Quit(Exception):
    pass


# ----------------------------------------------------------------------------- display helpers
def source_text(task: dict, rel: str) -> str | None:
    """Read a file from the pinned source commit in the local cache. None if unavailable."""
    src = task["source"]
    d = c.CACHE / src["repo"].split("/")[1]
    if not d.exists():
        return None
    base = src["path"].rsplit("/docs/", 1)[0] if "/docs/" in src["path"] else src["path"].rsplit("/", 1)[0]
    try:
        return c.show(d, src["sha"], f"{base}/{rel}")
    except Exception:
        return None


def scorer_text(task: dict) -> str:
    for rel in ("docs/scoring_details.md", "docs/scorer.md", "scorer.md"):
        txt = source_text(task, rel)
        if txt and txt.strip():
            return txt.strip()
    return ""


def goal_text(task: dict) -> str:
    if task.get("goal_text"):
        return task["goal_text"]
    txt = source_text(task, "docs/goal.md") or source_text(task, "goal.md")
    if txt:  # local read for the reviewer only; nothing is copied into the repo
        return txt.strip()
    return f"[goal text not stored (no licence). Our summary: {task.get('our_summary') or 'none'}]"


def link(task: dict) -> str:
    s = task["source"]
    return f"https://github.com/{s['repo']}/blob/{s['sha']}/{s['path']}"


def tactic_name(fw: dict, tid) -> str:
    return next((t["name"] for t in fw["attack"]["tactics"] if t["id"] == tid), "?")


def tech_name(fw: dict, tech) -> str:
    return fw["attack"]["techniques"].get(tech, {}).get("name", "?") if tech else "none"


def trim(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n].rstrip() + f" ... [{len(s) - n} more characters]"


def render(task: dict, fw: dict, goal_fn=goal_text, scorer_fn=scorer_text, width: int = 70) -> str:
    lab = task.get("labels") or {}
    att = lab.get("attack") or {}
    steps = ", ".join(f"{s} {tactic_name(fw, s)}" for s in att.get("required_step_tactics") or []) or "none"
    alt = lab.get("alternative")
    alt_s = (f"{alt.get('tactic')} {tactic_name(fw, alt.get('tactic'))}"
             f"{' / ' + str(alt['technique']) if alt.get('technique') else ''}: {alt.get('reason')}") if alt else "none"
    atlas = (lab.get("atlas") or {}).get("technique") or "none"
    sc = scorer_fn(task)
    out = [
        "=" * width,
        f"{task.get('setting')}/{task.get('environment')}/{task.get('id')}   status: {task.get('label_status')}",
        f"upstream category: {task.get('upstream_category')}   failure type: {task.get('failure_type')}",
        f"source: {link(task)}",
        "-" * width, "GOAL", trim(goal_fn(task) or "[empty]", 900),
        "-" * width, "WHAT THE SCORER CHECKS", trim(sc, 900) if sc else "[no scorer description available]",
        "-" * width, "LABEL (draft)",
        f"  main tactic : {att.get('primary_tactic')} {tactic_name(fw, att.get('primary_tactic'))}",
        f"  technique   : {att.get('technique') or 'none (null)'} {tech_name(fw, att.get('technique'))}",
        f"  steps       : {steps}",
        f"  ATLAS       : {atlas}",
        f"  confidence  : {lab.get('confidence')}",
        f"  alternative : {alt_s}",
        f"  rationale   : {lab.get('rationale') or '[empty]'}",
        "=" * width,
    ]
    return "\n".join(out)


# ----------------------------------------------------------------------------- input helpers
def resolve_tactic(text: str, fw: dict):
    t = (text or "").strip()
    for x in fw["attack"]["tactics"]:
        if t.upper() == x["id"] or t.lower() == x["name"].lower():
            return x["id"]
    return None


def ask(prompt: str, input_fn, out, valid=None, allow_blank=False):
    """Prompt until valid. EOF or too many bad answers raise Quit (progress is already saved)."""
    bad = 0
    while True:
        try:
            raw = input_fn(prompt)
        except (EOFError, KeyboardInterrupt):
            raise Quit
        raw = (raw or "").strip()
        if raw == "" and allow_blank:
            return ""
        res = valid(raw) if valid else raw
        if res not in (None, False, "") or (res == "" and allow_blank):
            return res
        bad += 1
        out(f"  not understood: {raw!r}")
        if bad >= MAX_BAD_INPUTS:
            out("  too many unclear answers; stopping. Nothing was changed for this task.")
            raise Quit


def save_task(path, task: dict) -> None:
    """Write atomically so a crash or Ctrl-C cannot leave a half-written file."""
    text = c.dump_yaml(task)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


# ----------------------------------------------------------------------------- decisions
def decide_yes(task: dict, reviewer: str, today: str) -> None:
    L.set_status(task, "reviewed", reviewer, "confirmed label unchanged", "Human reviewer agreed with the draft.", today)
    task["reviewed_by"] = reviewer


def decide_no(task: dict, fw: dict, reviewer: str, today: str, input_fn, out) -> bool:
    """Collect a replacement label. Returns False if the reviewer cancelled (nothing changed)."""
    lab = task.get("labels") or {}
    old = (lab.get("attack") or {})
    new_p = ask("  new main tactic (ID or name, blank to cancel): ", input_fn, out,
                valid=lambda s: resolve_tactic(s, fw), allow_blank=True)
    if new_p == "":
        out("  cancelled; nothing changed.")
        return False

    def tech_ok(s):
        if s.lower() in ("null", "none"):
            return "NULL"
        if fwm.check_techniques(fw, "attack", [s.upper()]):
            out(f"  {s!r} is missing, revoked or deprecated in ATT&CK v{fw['attack']['version']}")
            return None
        info = fw["attack"]["techniques"][s.upper()]
        if new_p not in info["tactics"]:
            out(f"  {s.upper()} is not in {new_p} (it is in {info['tactics']})")
            return None
        return s.upper()
    tech = ask("  technique ID ('null' for none, blank to cancel): ", input_fn, out, valid=tech_ok, allow_blank=True)
    if tech == "":
        out("  cancelled; nothing changed.")
        return False
    tech = None if tech == "NULL" else tech
    reason = ask("  reason (required, one line): ", input_fn, out, valid=lambda s: s if len(s.strip()) >= 5 else None)
    conf = ask("  confidence [c = clear / a = ambiguous]: ", input_fn, out,
               valid=lambda s: {"c": "clear", "a": "ambiguous", "clear": "clear", "ambiguous": "ambiguous"}.get(s.lower()))
    alt = None
    if conf == "ambiguous":
        alt_t = ask("  alternative tactic (ID or name): ", input_fn, out, valid=lambda s: resolve_tactic(s, fw))
        alt_r = ask("  why is the alternative defensible: ", input_fn, out, valid=lambda s: s if len(s.strip()) >= 5 else None)
        alt = dict(tactic=alt_t, technique=None, reason=alt_r)
    change = (f"label changed: {old.get('primary_tactic')}/{old.get('technique')} -> {new_p}/{tech}")
    task["labels"]["attack"]["primary_tactic"] = new_p
    task["labels"]["attack"]["technique"] = tech
    task["labels"]["confidence"] = conf
    task["labels"]["alternative"] = alt
    task["labels"]["rationale"] = f"Human reviewer: {reason.strip()}"
    if task.get("cross_check"):
        task["cross_check"] = dict(task["cross_check"], invalidated_by_human_change=True)
    L.set_status(task, "reviewed", reviewer, change, reason.strip(), today)
    task["reviewed_by"] = reviewer
    task["labeled_by"] = reviewer
    return True


def run_session(queue: list, fw: dict, input_fn=input, out=print, reviewer: str = DEFAULT_REVIEWER,
                today: str | None = None, goal_fn=goal_text, scorer_fn=scorer_text, save=save_task,
                redo: bool = False) -> dict:
    """Review `queue` = [(path, task), ...] in order. Returns counts."""
    L.check_status_change("reviewed", reviewer)  # refuse a bot or unlisted name before showing anything
    today = today or date.today().isoformat()
    stats = dict(shown=0, agreed=0, changed=0, skipped=0, already=0, cancelled=0, quit=False)
    for i, (path, task) in enumerate(queue, 1):
        if task.get("label_status") in SKIP_TIERS and not redo:
            stats["already"] += 1
            continue
        if not task.get("labels"):
            out(f"[{i}/{len(queue)}] {task.get('id')}: no label to review; skipping.")
            stats["skipped"] += 1
            continue
        out(f"\n[{i}/{len(queue)}]")
        out(render(task, fw, goal_fn, scorer_fn))
        stats["shown"] += 1
        try:
            ans = ask("y = agree / n = disagree / s = skip / q = quit > ", input_fn, out,
                      valid=lambda s: {"y": "y", "yes": "y", "n": "n", "no": "n", "s": "s", "skip": "s",
                                       "q": "q", "quit": "q"}.get(s.lower()))
            if ans == "q":
                raise Quit
            if ans == "s":
                stats["skipped"] += 1
                continue
            if ans == "y":
                decide_yes(task, reviewer, today)
                save(path, task)
                stats["agreed"] += 1
                out("  saved: reviewed (agreed).")
            else:
                if decide_no(task, fw, reviewer, today, input_fn, out):
                    save(path, task)
                    stats["changed"] += 1
                    out("  saved: reviewed (label changed).")
                else:
                    stats["cancelled"] += 1
        except Quit:
            stats["quit"] = True
            break
    out(f"\nDone. shown {stats['shown']}, agreed {stats['agreed']}, changed {stats['changed']}, "
        f"skipped {stats['skipped']}, cancelled {stats['cancelled']}, already reviewed {stats['already']}"
        f"{', stopped early' if stats['quit'] else ''}.")
    return stats


# ----------------------------------------------------------------------------- queues
def build_queue(kind: str, only: str | None = None) -> list:
    tasks = L.load_tasks()
    if only:
        env, _, tid = only.partition("/")
        if (env, tid) not in tasks:
            raise SystemExit(f"no such task {only!r} (use environment/id)")
        return [tasks[(env, tid)]]
    if kind == "all":
        return list(tasks.values())
    csv_path = c.DATA / "generated" / ("start_here.csv" if kind == "start_here" else "review_sheet.csv")
    if not csv_path.exists():
        raise SystemExit(f"{csv_path} not found; run scripts/review_sheet.py first")
    order = []
    for r in csv.DictReader(open(csv_path, encoding="utf-8")):
        key = (r["environment"], r["id"])
        if key in tasks:
            order.append(tasks[key])
    return order


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queue", choices=["start_here", "sheet", "all"], default="start_here")
    ap.add_argument("--only", help="review one task: environment/id")
    ap.add_argument("--reviewer", default=DEFAULT_REVIEWER)
    ap.add_argument("--again", action="store_true", help="also show tasks that are already reviewed")
    a = ap.parse_args()
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("review.py records a HUMAN decision and needs an interactive terminal. "
              "Run it yourself; it will not run from a script or pipe.", file=sys.stderr)
        return 2
    try:
        L.check_status_change("reviewed", a.reviewer)
    except L.StatusError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    fw = fwm.load()
    run_session(build_queue(a.queue, a.only), fw, reviewer=a.reviewer, redo=a.again)
    return 0


if __name__ == "__main__":
    sys.exit(main())
