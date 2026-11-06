#!/usr/bin/env python3
"""Agreement between labelers on the ACTCM review items.

    python3 review/agreement.py a.csv b.csv [c.csv ...] [--tasks-dir DIR] [--owner NAME] [--out-dir DIR]

Input: CSVs exported by review_blind.html / review_owner.html (columns item_id, tactic_id, ...).
Output (stdout): per pair of labelers: raw agreement, Cohen's kappa, per-tactic agreement,
confusion table; one list of disagreements; and the owner's blind picks versus the AI labels.

Design rule: bad input is never turned into a number silently. Every dropped, merged or
corrected row is counted and printed under WARNINGS. If fewer than two labelers have usable
rows the script stops with exit code 2.

Definitions used
  raw agreement      = items where both chose the same tactic / items both labelled.
  Cohen's kappa      = (po - pe) / (1 - pe). Undefined (printed as such) when pe = 1, i.e. both
                       labelers used one single tactic on every shared item.
  per-tactic agree   = items both gave this tactic / items where at least one gave it.
  'none fits'        counts as a 16th category.
  Only items BOTH labelers did are compared. Items done by one labeler are listed as missing.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import io
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# 15 ATT&CK Enterprise v20.0 tactics (same list as build_kit.py).
TACTICS = {
    "TA0043": "Reconnaissance", "TA0042": "Resource Development", "TA0001": "Initial Access",
    "TA0002": "Execution", "TA0003": "Persistence", "TA0004": "Privilege Escalation",
    "TA0005": "Stealth", "TA0112": "Defense Impairment", "TA0006": "Credential Access",
    "TA0007": "Discovery", "TA0008": "Lateral Movement", "TA0009": "Collection",
    "TA0011": "Command and Control", "TA0010": "Exfiltration", "TA0040": "Impact",
}
NONE = "NONE"
NONE_WORDS = {"none", "none fits", "nonefits", "none fit", "n a", "na", "no fit", "does not fit"}
OUTLIERS = {"ws_rce", "ws_run_malware_delayed"}
FAMILY_RE = re.compile(r"_(rce|reverse_shell|run_malware_live|run_malware_delayed)$")
FAMILY_KEY = {"rce": "rce", "reverse_shell": "reverse_shell",
              "run_malware_live": "malware_live", "run_malware_delayed": "malware_delayed"}


def squash(s: str) -> str:
    return " ".join(re.sub(r"[-_/]+", " ", s.strip().lower()).split())


NAME_LOOKUP = {squash(n): t for t, n in TACTICS.items()}
NAME_LOOKUP.update({squash(n).replace(" ", ""): t for t, n in TACTICS.items()})


class Warnings:
    def __init__(self):
        self.items: list[str] = []

    def add(self, msg: str):
        self.items.append(msg)


def normalize_tactic(raw: str):
    """-> (tactic id | NONE | None, how). how: exact | typo:<original> | invalid."""
    s = (raw or "").strip()
    if not s:
        return None, "empty"
    up = s.upper().replace(" ", "")
    if up in TACTICS:
        return up, "exact"
    if up == NONE:
        return NONE, "exact"
    q = squash(s)
    if q in NONE_WORDS:
        return NONE, "exact"
    if q in NAME_LOOKUP:
        return NAME_LOOKUP[q], "exact"
    close = difflib.get_close_matches(q, list(NAME_LOOKUP) + sorted(NONE_WORDS), n=2, cutoff=0.8)
    targets = {NONE if c in NONE_WORDS else NAME_LOOKUP[c] for c in close}
    if len(targets) == 1:
        return targets.pop(), f"typo:{s}"
    return None, "invalid"


def parse_ts(s: str):
    try:
        return datetime.fromisoformat((s or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def load_universe(tasks_dir: Path | None, warn: Warnings):
    """Valid item ids and the AI label for each. (None, None) if it cannot be built."""
    if tasks_dir is None or not tasks_dir.is_dir():
        warn.add(f"No tasks directory ({tasks_dir}): item ids are not validated and the owner-vs-AI comparison is skipped.")
        return None, None
    try:
        import yaml
    except ImportError:
        warn.add("PyYAML is not installed: item ids are not validated and the owner-vs-AI comparison is skipped.")
        return None, None
    ai, fam = {}, defaultdict(list)
    for p in sorted(tasks_dir.glob("*/*.yml")):
        t = yaml.safe_load(p.read_text(encoding="utf-8"))
        rec = {"primary": t["labels"]["attack"]["primary_tactic"],
               "alt": t["labels"].get("alternative"),
               "steps": t["labels"]["attack"].get("required_step_tactics") or [],
               "reasoning": t["labels"]["rationale"], "confidence": t["labels"]["confidence"]}
        m = FAMILY_RE.search(t["id"])
        if m and t["id"] not in OUTLIERS:
            fam[FAMILY_KEY[m.group(1)]].append(rec)
        else:
            ai[f"{t['environment']}/{t['id']}"] = rec
    for f, recs in fam.items():
        if len({r["primary"] for r in recs}) != 1:
            warn.add(f"AI labels differ inside template group {f}; its AI comparison uses the most common one.")
        ai[f"template/{f}"] = Counter(json.dumps(r, sort_keys=True) for r in recs).most_common(1)[0][0]
        ai[f"template/{f}"] = json.loads(ai[f"template/{f}"])
    return set(ai), ai


def read_csv_file(path: Path, warn: Warnings):
    """-> list of dict rows with normalised lower-case keys, or [] (with a warning)."""
    try:
        raw = path.read_bytes()
    except OSError as e:
        warn.add(f"{path.name}: cannot read ({e}); file ignored.")
        return []
    text = raw.decode("utf-8-sig", errors="replace")
    if not text.strip():
        warn.add(f"{path.name}: file is empty; ignored.")
        return []
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rd = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in rd if any(c.strip() for c in r)]
    if not rows:
        warn.add(f"{path.name}: no rows; ignored.")
        return []
    head = [h.strip().lower() for h in rows[0]]
    if "item_id" not in head or not ({"tactic_id", "tactic_name"} & set(head)):
        warn.add(f"{path.name}: header lacks item_id and tactic_id/tactic_name (found: {', '.join(head)}); file ignored.")
        return []
    out = []
    for n, r in enumerate(rows[1:], start=2):
        if len(r) != len(head):
            warn.add(f"{path.name} line {n}: {len(r)} fields, expected {len(head)}; row skipped.")
            continue
        d = {h: v.strip() for h, v in zip(head, r)}
        d["_line"], d["_file"] = n, path.name
        out.append(d)
    if not out:
        warn.add(f"{path.name}: header only, no data rows; ignored.")
    return out


def collect(paths, universe, warn: Warnings):
    """-> labelers: {name: {item: {tactic, cert, note, ts, line, file}}}, counters."""
    stats = Counter()
    labelers: dict[str, dict] = {}
    files_of = defaultdict(set)
    dup_conflicts = defaultdict(list)
    for path in paths:
        rows = read_csv_file(Path(path), warn)
        for d in rows:
            who = d.get("labeler", "").strip()
            if not who:
                who = Path(path).stem
                stats["no_labeler_name"] += 1
            item = d.get("item_id", "").strip()
            if universe is not None and item not in universe:
                stats["unknown_item"] += 1
                warn.add(f"{d['_file']} line {d['_line']}: item_id '{item}' is not a known review item; row skipped.")
                continue
            if d.get("status", "").lower() == "draft":
                stats["draft_rows"] += 1
                continue
            tid, how = normalize_tactic(d.get("tactic_id", ""))
            tname = ""
            if tid is None and d.get("tactic_name", ""):
                tid, how = normalize_tactic(d["tactic_name"])
            elif tid is not None and d.get("tactic_name", ""):
                n2, _ = normalize_tactic(d["tactic_name"])
                if n2 is not None and n2 != tid:
                    warn.add(f"{d['_file']} line {d['_line']} ({who}, {item}): tactic_id {d['tactic_id']} and tactic_name '{d['tactic_name']}' disagree; used the id.")
            if tid is None:
                stats["bad_tactic"] += 1
                warn.add(f"{d['_file']} line {d['_line']} ({who}, {item}): tactic '{d.get('tactic_id') or d.get('tactic_name')}' not recognised ({how}); row skipped, NOT counted as agreement or disagreement.")
                continue
            if how.startswith("typo:"):
                stats["typo_fixed"] += 1
                warn.add(f"{d['_file']} line {d['_line']} ({who}, {item}): '{how[5:]}' read as {TACTICS.get(tid, tid)}.")
            rec = {"tactic": tid, "cert": d.get("certainty", ""), "note": d.get("note", ""),
                   "ts": parse_ts(d.get("answered_at", "")), "line": d["_line"], "file": d["_file"]}
            files_of[who].add(d["_file"])
            cur = labelers.setdefault(who, {}).get(item)
            if cur is not None:
                stats["duplicate_rows"] += 1
                keep_new = (rec["ts"] and cur["ts"] and rec["ts"] >= cur["ts"]) or not (rec["ts"] and cur["ts"])
                if cur["tactic"] != rec["tactic"]:
                    dup_conflicts[who].append(item)
                if keep_new:  # later timestamp wins; with no timestamps, the later row wins
                    labelers[who][item] = rec
            else:
                labelers[who][item] = rec
    for who, items in dup_conflicts.items():
        warn.add(f"{who}: {len(items)} item(s) appear more than once with DIFFERENT tactics; the latest row was kept: {', '.join(sorted(set(items))[:8])}{' ...' if len(set(items)) > 8 else ''}")
    for who, fs in files_of.items():
        if len(fs) > 1:
            warn.add(f"Labeler '{who}' appears in {len(fs)} files ({', '.join(sorted(fs))}); rows were merged as ONE person. If these are two different people, ask one to use a different name.")
    if stats["no_labeler_name"]:
        warn.add(f"{stats['no_labeler_name']} row(s) had no labeler name; the file name was used.")
    if stats["draft_rows"]:
        warn.add(f"{stats['draft_rows']} row(s) with status 'draft' (picked but not saved/revealed) were left out.")
    return labelers, stats


def kappa_stats(pairs):
    """pairs: list of (a, b). -> dict(n, po, pe, kappa|None, why)"""
    n = len(pairs)
    if n == 0:
        return {"n": 0, "po": None, "pe": None, "kappa": None, "why": "no shared items"}
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in set(ca) | set(cb))
    if pe >= 1 - 1e-12:
        return {"n": n, "po": po, "pe": pe, "kappa": None,
                "why": "undefined: both labelers used one single tactic on every shared item"}
    return {"n": n, "po": po, "pe": pe, "kappa": (po - pe) / (1 - pe), "why": ""}


def per_tactic(pairs):
    cats = sorted({c for p in pairs for c in p}, key=lambda c: (c == NONE, c))
    rows = []
    for c in cats:
        a = sum(x == c for x, _ in pairs); b = sum(y == c for _, y in pairs)
        both = sum(x == c and y == c for x, y in pairs); either = sum(x == c or y == c for x, y in pairs)
        rows.append((c, a, b, both, either, both / either if either else None))
    return rows


def confusion(pairs):
    rows = sorted({a for a, _ in pairs}, key=lambda c: (c == NONE, c)); cols = sorted({b for _, b in pairs}, key=lambda c: (c == NONE, c))
    cnt = Counter(pairs)
    return rows, cols, cnt


def tname(c):
    return "none fits" if c == NONE else f"{TACTICS.get(c, c)} ({c})"


def fmt(x, d=3):
    return "n/a" if x is None else f"{x:.{d}f}"


def print_conf(rows, cols, cnt, la, lb, out):
    w = 7
    out.append(f"  rows = {la}, columns = {lb}")
    out.append("  " + " " * 8 + "".join(f"{c[:w - 1]:>{w}}" for c in cols) + f"{'total':>{w}}")
    for r in rows:
        out.append("  " + f"{r[:8]:<8}" + "".join(f"{(cnt[(r, c)] or '.'):>{w}}" for c in cols) + f"{sum(cnt[(r, c)] for c in cols):>{w}}")
    out.append("  " + f"{'total':<8}" + "".join(f"{sum(cnt[(r, c)] for r in rows):>{w}}" for c in cols))


def pair_report(la, lb, A, B, out, csvdir, disagreements):
    shared = sorted(set(A) & set(B))
    onlyA, onlyB = sorted(set(A) - set(B)), sorted(set(B) - set(A))
    out.append(f"\n=== {la} vs {lb} ===")
    out.append(f"items labelled: {la} {len(A)}, {lb} {len(B)}; shared {len(shared)}; only {la}: {len(onlyA)}; only {lb}: {len(onlyB)}")
    if not shared:
        out.append("No shared items, so no agreement can be computed.")
        return None
    pairs = [(A[i]["tactic"], B[i]["tactic"]) for i in shared]
    k = kappa_stats(pairs)
    out.append(f"raw agreement: {sum(a == b for a, b in pairs)}/{k['n']} = {k['po']:.3f}")
    out.append(f"Cohen's kappa: {fmt(k['kappa'])}" + (f"   ({k['why']})" if k["why"] else f"   (chance agreement pe = {k['pe']:.3f})"))
    if k["n"] < 10:
        out.append(f"  caution: only {k['n']} shared items; kappa is very unstable below about 10.")
    for who, D in ((la, A), (lb, B)):
        used = Counter(D[i]["tactic"] for i in shared)
        if len(used) == 1:
            out.append(f"  caution: {who} used only '{tname(next(iter(used)))}' on all {k['n']} shared items. Raw agreement then just measures how often the other person picked it; kappa is 0 or undefined by construction.")
    out.append("per-tactic agreement (both chose it / at least one chose it):")
    out.append(f"  {'tactic':<34}{la[:10]:>11}{lb[:10]:>11}{'both':>6}{'either':>8}{'agree':>8}")
    for c, a, b, both, either, r in per_tactic(pairs):
        out.append(f"  {tname(c):<34}{a:>11}{b:>11}{both:>6}{either:>8}{(f'{r:.2f}' if r is not None else 'n/a'):>8}")
    rows, cols, cnt = confusion(pairs)
    out.append("confusion table (counts of shared items):")
    print_conf(rows, cols, cnt, la, lb, out)
    if csvdir:
        with open(csvdir / f"confusion_{la}_vs_{lb}.csv".replace(" ", "_"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow([f"{la}\\{lb}"] + cols)
            for r in rows:
                w.writerow([r] + [cnt[(r, c)] for c in cols])
    for i in shared:
        if A[i]["tactic"] != B[i]["tactic"]:
            disagreements[i].update({la: A[i], lb: B[i]})
    return k


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csvs", nargs="+", help="two or more exported CSV files")
    ap.add_argument("--tasks-dir", default=str(Path(__file__).resolve().parent.parent / "data" / "tasks" / "linuxarena"),
                    help="folder with the task YAML files (for item-id checks and AI labels)")
    ap.add_argument("--owner", help="name of the owner (default: the labeler in a file that has a 'decision' column)")
    ap.add_argument("--out-dir", help="also write disagreements.csv and confusion tables here")
    a = ap.parse_args(argv)

    warn = Warnings()
    universe, ai = load_universe(Path(a.tasks_dir), warn)
    labelers, stats = collect(a.csvs, universe, warn)
    labelers = {k: v for k, v in labelers.items() if v}
    out: list[str] = []
    csvdir = Path(a.out_dir) if a.out_dir else None
    if csvdir:
        csvdir.mkdir(parents=True, exist_ok=True)

    out.append(f"Labelers with usable rows: {', '.join(f'{k} ({len(v)} items)' for k, v in labelers.items()) or 'none'}")
    owner = a.owner
    if not owner:
        for p in a.csvs:  # owner file = one that has a 'decision' column
            try:
                first = Path(p).read_text(encoding="utf-8-sig", errors="replace").splitlines()[0].lower()
            except Exception:
                continue
            if "decision" in first:
                names = {r.get("labeler", "").strip() or Path(p).stem for r in read_csv_file(Path(p), Warnings())}
                owner = next(iter(names & set(labelers)), None) if names else None
                break

    code = 0
    disagreements: dict[str, dict] = defaultdict(dict)
    if len(labelers) >= 2:
        for (la, A), (lb, B) in itertools.combinations(labelers.items(), 2):
            pair_report(la, lb, A, B, out, csvdir, disagreements)
        out.append("\n=== disagreements (all pairs; items where labelers chose different tactics) ===")
        if not disagreements:
            out.append("none")
        for i in sorted(disagreements):
            out.append(f"- {i}")
            for who, r in disagreements[i].items():
                out.append(f"    {who}: {tname(r['tactic'])}" + (f" [{r['cert']}]" if r["cert"] else "") + (f"  note: {r['note']}" if r["note"] else ""))
        if csvdir:
            with open(csvdir / "disagreements.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f); w.writerow(["item_id", "labeler", "tactic_id", "tactic_name", "certainty", "note"])
                for i in sorted(disagreements):
                    for who, r in disagreements[i].items():
                        w.writerow([i, who, r["tactic"], tname(r["tactic"]), r["cert"], r["note"]])
    else:
        out.append("\nNEED TWO LABELERS: fewer than two people have usable rows, so no agreement is computed. See WARNINGS.")
        code = 2

    # owner's blind picks versus the AI labels
    out.append("\n=== owner's blind picks vs AI labels ===")
    if not owner or owner not in labelers:
        out.append("Owner not found (no file with a 'decision' column and no --owner NAME). Skipped.")
    elif ai is None:
        out.append("AI labels unavailable (see WARNINGS). Skipped.")
    else:
        O = labelers[owner]
        pairs_items = sorted(i for i in O if i in ai)
        pairs = [(O[i]["tactic"], ai[i]["primary"]) for i in pairs_items]
        k = kappa_stats(pairs)
        out.append(f"owner = {owner}; items compared: {k['n']} of {len(ai)}; not yet done: {len(ai) - k['n']}")
        if k["n"]:
            out.append(f"raw agreement: {sum(x == y for x, y in pairs)}/{k['n']} = {k['po']:.3f}")
            out.append(f"Cohen's kappa: {fmt(k['kappa'])}" + (f"   ({k['why']})" if k["why"] else ""))
            out.append("per-tactic agreement (owner pick = AI primary):")
            out.append(f"  {'tactic':<34}{'owner':>8}{'AI':>6}{'both':>6}{'either':>8}{'agree':>8}")
            for c, x, y, both, either, r in per_tactic(pairs):
                out.append(f"  {tname(c):<34}{x:>8}{y:>6}{both:>6}{either:>8}{(f'{r:.2f}' if r is not None else 'n/a'):>8}")
            rows, cols, cnt = confusion(pairs)
            out.append("confusion table (rows = owner, columns = AI):")
            print_conf(rows, cols, cnt, "owner", "AI", out)
            out.append("disagreements with the AI:")
            n_dis = 0
            for i in pairs_items:
                if O[i]["tactic"] != ai[i]["primary"]:
                    n_dis += 1
                    alt = ai[i]["alt"]
                    out.append(f"- {i}: owner {tname(O[i]['tactic'])} [{O[i]['cert']}] vs AI {tname(ai[i]['primary'])} (AI {ai[i]['confidence']})"
                               + (f"; AI alternative {tname(alt['tactic'])}" if alt else "")
                               + (f"\n    owner note: {O[i]['note']}" if O[i]["note"] else ""))
            if not n_dis:
                out.append("none")
            out.append("Note: the AI labels were drafted by an AI; agreement here is not validation of either side.")

    if warn.items:
        out.append("\n=== WARNINGS (rows dropped, merged or corrected; read these before trusting the numbers) ===")
        out.extend(f"- {w}" for w in warn.items)
    else:
        out.append("\nWARNINGS: none")
    print("\n".join(out))
    return code


if __name__ == "__main__":
    sys.exit(main())
