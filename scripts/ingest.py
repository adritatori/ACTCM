#!/usr/bin/env python3
"""Phase 1: source ingestion.

  ingest.py lock    Resolve tags to commit SHAs (network). Writes data/sources.lock.yml.
  ingest.py build   Fetch each repo at its locked SHA and write data/tasks/**.yml.
  ingest.py check   Verify every task's source path exists at its pinned SHA.
  ingest.py all     build + check.

Every file is read from the git object database at an explicit SHA, never from a branch
head or from a working tree. `build` never touches a SHA that is not in the lock file.
"""
from __future__ import annotations

import ast
import re
import sys
import tomllib
from collections import Counter, defaultdict
from datetime import date

import yaml

import common as c

MANIFESTS = [
    dict(setting="linuxarena", repo="linuxarena/ct-linuxarena", tag="v0.4.0",
         note="The brief asks for tag v3.2.0, but this repo has no v3.2.0 tag (tags: v0.1.0-v0.4.0). "
              "v3.2.0 is the tag of each ENV repo, set in this repo's envs.lock.yml. "
              "v0.4.0 is the newest tag and was the default-branch head on 2026-11-04."),
]
DIRECT = [
    dict(setting="refactor_arena", repo="linuxarena/refactor_arena", tag="v3.2.0",
         environment="refactor_arena", root="side_tasks"),
    dict(setting="vllm", repo="linuxarena/ct-vllm", tag="v0.2.0",
         environment="vllm", root="ct_vllm/side_tasks"),
]
# Counts expected from the sources (checked by `ingest.py build`).
EXPECTED = {"linuxarena": 92, "refactor_arena": 7, "vllm": 15}
UNFINISHED_FILE = c.DATA / "unfinished_upstream.yml"
SUMMARIES = c.DATA / "summaries" / "extras.yml"
MAX_SUMMARY_WORDS = 20
CURATED = ("labels", "label_status", "labeled_by", "reviewed_by", "history", "our_summary")


def detect_licence(d, sha: str) -> dict:
    top = c.ls_tree(d, sha)
    lic_files = [n for n in top if re.match(r"(?i)^(licen[cs]e|copying)", n)]
    if lic_files:
        text = c.show(d, sha, lic_files[0]) or ""
        first = text.strip().splitlines()[0].strip() if text.strip() else ""
        copy = next((l.strip() for l in text.splitlines() if l.strip().lower().startswith("copyright")), None)
        spdx = "MIT" if first.lower().startswith("mit licen") else "unrecognised"
        return dict(spdx=spdx, status="file", source=lic_files[0], copyright=copy)
    pyproj = c.show(d, sha, "pyproject.toml")
    if pyproj:
        lic = tomllib.loads(pyproj).get("project", {}).get("license")
        if isinstance(lic, dict):
            lic = lic.get("text") or lic.get("file")
        if lic:
            return dict(spdx=lic, status="declared-in-pyproject", source="pyproject.toml", copyright=None)
    return dict(spdx=None, status="none-found", source=None, copyright=None,
                top_level_files=top)


# ---------------------------------------------------------------- lock
def cmd_lock() -> None:
    manifests, sources = [], []
    for m in MANIFESTS:
        sha = c.resolve_tag(m["repo"], m["tag"])
        d = c.fetch_at(m["repo"], sha, m["repo"].split("/")[1])
        manifests.append(dict(setting=m["setting"], repo=m["repo"], tag=m["tag"], sha=sha, note=m["note"]))
        manifest = yaml.safe_load(c.show(d, sha, "envs.lock.yml"))
        org = manifest["org"]
        for env in manifest["envs"]:
            repo = f"{org}/{env['name']}"
            tag_sha = c.resolve_tag(repo, env["ref"])
            ed = c.fetch_at(repo, env["sha"], env["name"])
            sources.append(dict(
                setting=m["setting"], environment=env["name"], repo=repo, tag=env["ref"], sha=env["sha"],
                tag_resolves_to_sha=(tag_sha == env["sha"]), tag_sha=tag_sha,
                side_tasks_root="side_tasks", licence=detect_licence(ed, env["sha"])))
    for s in DIRECT:
        sha = c.resolve_tag(s["repo"], s["tag"])
        d = c.fetch_at(s["repo"], sha, s["repo"].split("/")[1])
        sources.append(dict(
            setting=s["setting"], environment=s["environment"], repo=s["repo"], tag=s["tag"], sha=sha,
            tag_resolves_to_sha=True, tag_sha=sha, side_tasks_root=s["root"], licence=detect_licence(d, sha)))
    prev = c.load_yaml(c.LOCK_FILE) if c.LOCK_FILE.exists() else {}
    lock = dict(
        generated=date.today().isoformat(),
        note="Every task is read from the commit in `sha` below, never from a branch head.",
        frameworks=prev.get("frameworks") or dict(attack=None, atlas=None),  # written by frameworks.py
        manifests=manifests, sources=sources)
    c.dump_yaml(lock, c.LOCK_FILE)
    print(f"wrote {c.LOCK_FILE.relative_to(c.ROOT)}: {len(sources)} source repos")
    for s in sources:
        flag = "" if s["tag_resolves_to_sha"] else "  <-- TAG DOES NOT MATCH SHA"
        print(f"  {s['setting']:18} {s['environment']:18} {s['tag']:7} {s['sha'][:10]} "
              f"{s['licence']['spdx'] or 'NO LICENCE'}{flag}")


# ---------------------------------------------------------------- build
def parse_init(src: str | None) -> dict:
    out = dict(task_category=None, failure_type=None, parse_note=None)
    if src is None:
        out["parse_note"] = "no __init__.py"
        return out
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        out["parse_note"] = f"syntax error: {e}"
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            if name == "make_side_task_from_path":
                for kw in node.keywords:
                    if kw.arg in ("task_category", "failure_type"):
                        if isinstance(kw.value, ast.Constant):
                            out[kw.arg] = kw.value.value
                        else:
                            out["parse_note"] = f"{kw.arg} is not a literal"
                return out
    out["parse_note"] = "make_side_task_from_path call not found"
    return out


def load_summaries() -> dict:
    return c.load_yaml(SUMMARIES) if SUMMARIES.exists() else {}


def cmd_build() -> dict:
    lock = c.load_yaml(c.LOCK_FILE)
    summaries = load_summaries()
    rows, problems = [], []
    for s in lock["sources"]:
        d = c.fetch_at(s["repo"], s["sha"], s["repo"].split("/")[1])
        root = s["side_tasks_root"]
        for name in c.ls_tree(d, s["sha"], root, dirs_only=True):
            if name.startswith("__"):
                continue
            base = f"{root}/{name}"
            init = parse_init(c.show(d, s["sha"], f"{base}/__init__.py"))
            goal_path = next((p for p in (f"{base}/docs/goal.md", f"{base}/goal.md")
                              if c.exists(d, s["sha"], p)), None)
            licensed = s["licence"]["spdx"] is not None
            has_init = c.exists(d, s["sha"], f"{base}/__init__.py")
            status = "discovered" if has_init else "idea_draft_not_discovered_upstream"
            if goal_path is None:
                path, goal_text = f"{base}/info.yml", None
                if not c.exists(d, s["sha"], path):
                    problems.append(f"{s['setting']}/{s['environment']}/{name}: no goal file and no info.yml")
            else:
                path = goal_path
                goal_text = c.show(d, s["sha"], goal_path).strip() if licensed else None
            planned = any(re.search(r"not yet implemented", c.show(d, s["sha"], f"{base}/{rel}") or "", re.I)
                          for rel in ("docs/scorer.md", "docs/scoring_details.md", "scorer.md"))
            rows.append(dict(scorer_planned=planned, 
                s=s, name=name, path=path, goal_text=goal_text, licensed=licensed,
                status=status, init=init, goal_path=goal_path))

    # Unfinished upstream drafts are kept out of tasks, counts and the matrix.
    unfinished = [r for r in rows if r["status"] != "discovered"]
    rows = [r for r in rows if r["status"] == "discovered"]
    unfinished_out = []
    for r in unfinished:
        s_ = r["s"]
        unfinished_out.append(dict(
            id=r["name"], setting=s_["setting"], environment=s_["environment"],
            flag="unfinished_upstream",
            reason="Folder name ends in _idea, has no __init__.py, and a note in its info.yml says task discovery "
                   "ignores it until it is finished. Excluded from all counts and the matrix.",
            source=dict(repo=s_["repo"], tag=s_["tag"], sha=s_["sha"], path=r["path"], licence="none-found"),
            our_summary=summaries.get(f"{s_['environment']}/{r['name']}"),
            excluded_by="Tory, 2026-11-04"))
    c.dump_yaml(dict(note="Not counted. Kept so the exclusion is visible and reversible.",
                     tasks=unfinished_out), UNFINISHED_FILE)

    # id uniqueness across ALL settings
    id_count = Counter(r["name"] for r in rows)
    dupes = {k: v for k, v in id_count.items() if v > 1}

    written = 0
    seen_files = set()
    for r in rows:
        s, name = r["s"], r["name"]
        tid = f"{s['setting']}/{name}" if name in dupes else name
        fname = tid.replace("/", "__") + ".yml"
        out = c.TASKS_DIR / s["setting"] / s["environment"] / fname
        seen_files.add(out)
        key = f"{s['environment']}/{name}"
        prev = c.load_yaml(out) if out.exists() else {}
        summary = summaries.get(key) or prev.get("our_summary")
        if not r["licensed"]:
            if not summary:
                problems.append(f"{key}: no licence and no our_summary yet")
            elif len(summary.split()) > MAX_SUMMARY_WORDS:
                problems.append(f"{key}: our_summary has {len(summary.split())} words (max {MAX_SUMMARY_WORDS})")
        task = dict(
            id=tid, setting=s["setting"], environment=s["environment"],
            source=dict(repo=s["repo"], tag=s["tag"], sha=s["sha"], path=r["path"],
                        licence=(s["licence"]["spdx"] or "none-found")),
            goal_text=r["goal_text"],
            our_summary=summary if not r["licensed"] else None,
            upstream_category=r["init"]["task_category"],
            failure_type=r["init"]["failure_type"],
            upstream_status=r["status"],
            scorer_status="planned_not_implemented" if r["scorer_planned"] else "implemented_or_not_flagged",
            labels=prev.get("labels"),
            label_status=prev.get("label_status", "unlabelled"),
            labeled_by=prev.get("labeled_by"),
            cross_check=prev.get("cross_check"),
            reviewed_by=prev.get("reviewed_by"),
            history=prev.get("history", []),
        )
        c.dump_yaml(task, out)
        written += 1

    # remove stale task files that no longer correspond to a source task
    stale = [p for p in c.TASKS_DIR.rglob("*.yml") if p not in seen_files]
    for p in stale:
        p.unlink()

    # report
    # The report is a generated public file: hidden settings (config/publish.yml) are left out of it entirely.
    rows = [r for r in rows if c.is_public_setting(r["s"]["setting"])]
    unfinished = [u for u in unfinished if c.is_public_setting(u["s"]["setting"])]
    expected_pub = {k: v for k, v in EXPECTED.items() if c.is_public_setting(k)}
    counts = defaultdict(lambda: defaultdict(int))
    for r in rows:
        counts[r["s"]["setting"]][r["s"]["environment"]] += 1
    report = dict(
        folder_count_incl_unfinished={k: v + sum(1 for u in unfinished if u["s"]["setting"] == k)
                                      for k, v in ((k, sum(e.values())) for k, e in counts.items())},
        unfinished_upstream=[f"{u['s']['environment']}/{u['name']}" for u in unfinished],
        counts={k: dict(sorted(v.items())) for k, v in counts.items()},
        totals={k: sum(v.values()) for k, v in counts.items()},
        total=len(rows), expected=expected_pub, duplicate_ids=dupes,
        no_goal_file=[f"{r['s']['environment']}/{r['name']}" for r in rows if r["goal_path"] is None],
        init_parse_notes=[f"{r['s']['environment']}/{r['name']}: {r['init']['parse_note']}"
                          for r in rows if r["init"]["parse_note"]],
        goal_file_kinds=dict(Counter(("docs/goal.md" if (r["goal_path"] or "").endswith("docs/goal.md")
                                      else "goal.md" if r["goal_path"] else "none") for r in rows)),
        goal_text_withheld_no_licence=sum(1 for r in rows if not r["licensed"]),
        problems=problems, stale_removed=len(stale))
    c.dump_yaml(report, c.DATA / "generated" / "ingest_report.yml")
    print_report(report, written)
    return report


def print_report(rep: dict, written: int) -> None:
    print(f"\nwrote {written} task files\n")
    print(f"{'setting':20}{'counted':>8}{'expected':>9}{'folders':>8}")
    for k, exp in rep["expected"].items():
        got = rep["totals"].get(k, 0)
        print(f"{k:20}{got:>8}{exp:>9}{rep['folder_count_incl_unfinished'].get(k, 0):>8}")
    print(f"{'TOTAL':20}{rep['total']:>8}{sum(rep['expected'].values()):>9}"
          f"{sum(rep['folder_count_incl_unfinished'].values()):>8}")
    print("unfinished upstream (excluded):", rep["unfinished_upstream"])
    print("\nper environment:")
    for k, envs in rep["counts"].items():
        for e, n in envs.items():
            print(f"  {k:18} {e:20} {n}")
    print("\nduplicate ids:", rep["duplicate_ids"] or "none")
    print("goal file kinds:", rep["goal_file_kinds"])
    print("no goal file:", rep["no_goal_file"] or "none")
    print("__init__.py parse notes:", rep["init_parse_notes"] or "none")
    print("goal text withheld (no licence):", rep["goal_text_withheld_no_licence"])
    print("problems:", rep["problems"] or "none")


# ---------------------------------------------------------------- check
def cmd_check() -> bool:
    lock = c.load_yaml(c.LOCK_FILE)
    pinned = {(s["repo"], s["sha"]) for s in lock["sources"]}
    ok, n = True, 0
    for f in sorted(c.TASKS_DIR.rglob("*.yml")):
        t = c.load_yaml(f)
        src = t["source"]
        n += 1
        if (src["repo"], src["sha"]) not in pinned:
            print(f"FAIL {f.name}: {src['repo']}@{src['sha']} not in lock"); ok = False; continue
        d = c.fetch_at(src["repo"], src["sha"], src["repo"].split("/")[1])
        if not c.exists(d, src["sha"], src["path"]):
            print(f"FAIL {f.name}: {src['path']} missing at {src['sha'][:10]}"); ok = False
        if src["licence"] == "none-found" and t["goal_text"] is not None:
            print(f"FAIL {f.name}: goal_text present for unlicensed source"); ok = False
        if t["goal_text"] is None and not t["our_summary"]:
            print(f"FAIL {f.name}: goal_text null and no our_summary"); ok = False
    print(f"checked {n} task files: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "lock":
        cmd_lock()
    elif cmd == "build":
        cmd_build()
    elif cmd == "check":
        sys.exit(0 if cmd_check() else 1)
    elif cmd == "all":
        cmd_build()
        sys.exit(0 if cmd_check() else 1)
    else:
        sys.exit(__doc__)
