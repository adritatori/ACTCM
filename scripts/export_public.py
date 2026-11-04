#!/usr/bin/env python3
"""Build the PUBLIC tree in a separate directory. Nothing in the working tree is moved or deleted.

  export_public.py                 write .cache/public_export/ and scan it
  export_public.py --out DIR       write somewhere else
  export_public.py --scan-only     scan an existing export (or --out DIR) without rewriting it

How the hidden setting (config/publish.yml, publish_extras: false) is kept out of the public tree:
  1. DENY: whole files that are about the hidden setting are not copied.
  2. FILTER: a few mixed data files are copied with the hidden entries removed.
  3. PRIVATE BLOCKS: text between `` (or ``) is removed from the copy.
  4. SCAN: the finished export is searched for every identifier of the hidden setting (task IDs, environment names,
     repository names, commit SHAs, our summaries). Any hit is an error and the exit code is 1.
The first public commit must be made from this directory (a fresh history), never from this branch: the branch history
still contains the hidden files.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys

import common as c

OUT_DEFAULT = c.ROOT / ".cache" / "public_export"

# 1. whole files that are never public (decision records, one-off scripts, private working documents)
ALWAYS_DENY_PREFIXES = (".cache/", ".git/", ".venv/", "docs/screenshots/results.json")
ALWAYS_DENY_FILES = {
    "docs/MAINTAINER_PERMISSION_REQUEST.md", "docs/BLIND_PASS_REPORT.md", "docs/V1_1_COUNT_CHANGE.md", "docs/R6_PROPOSAL.md",
    "docs/EXTRAS_HIDING_PLAN.md", "docs/EXTRAS_EFFECT.md", "docs/RELEASE_CHECKLIST.md", "data/audits/v1_1_count_change.json",
    # one-off scripts that apply decisions to individual tasks, including tasks of the hidden setting
    "scripts/apply_v11_steps.py", "scripts/apply_decisions_v12.py", "scripts/count_change_doc.py", "scripts/extras_effect.py",
    "scripts/blind_report.py",
}
# files that are only left out while the hidden setting is hidden (publish_extras: false)
HIDDEN_ONLY_PREFIXES = ("data/tasks/linuxarena-extras/",)
HIDDEN_ONLY_FILES = {"data/summaries/extras.yml", "data/unfinished_upstream.yml"}
PRIVATE_BLOCK = re.compile(r"(?:|# private:end)\n?", re.S)
MARKER_LINES = re.compile(r"^[ \t]*(?:<!-- private:(?:start|end) -->|# private:(?:start|end))[ \t]*\n", re.M)
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".csv", ".txt", ".html", ".css", ".js", ".cff", ".toml", ".cfg", ""}


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=c.ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    files = sorted(p for p in out if p and (c.ROOT / p).is_file())
    if files:
        return files
    # not a git repository (for example an export directory inside another repository): walk the folder instead
    skip = (".cache", ".git", ".venv", "__pycache__", ".pytest_cache", "node_modules")
    return sorted(str(p.relative_to(c.ROOT)) for p in c.ROOT.rglob("*")
                  if p.is_file() and not any(part in skip for part in p.relative_to(c.ROOT).parts))


def hidden_identifiers() -> dict:
    """Everything that would identify the hidden setting, read from the private files that are present."""
    ids, envs, repos, shas, summaries = set(), set(), set(), set(), set()
    lock = c.load_yaml(c.LOCK_FILE)
    for s in lock["sources"]:
        if s["setting"] == c.HIDDEN_SETTING:
            envs.add(s["environment"]); repos.add(s["repo"]); shas.add(s["sha"])
    for m in lock["manifests"]:
        if m["setting"] == c.HIDDEN_SETTING:
            shas.add(m["sha"])      # the manifest repo's NAME is the setting's name, which the site says openly; its SHA is not needed
    for f in (c.TASKS_DIR / c.HIDDEN_SETTING).rglob("*.yml") if (c.TASKS_DIR / c.HIDDEN_SETTING).exists() else []:
        t = c.load_yaml(f)
        ids.add(t["id"])
        if t.get("our_summary"):
            summaries.add(t["our_summary"])
    unf = c.DATA / "unfinished_upstream.yml"
    if unf.exists():
        for u in c.load_yaml(unf)["tasks"]:
            if u["setting"] == c.HIDDEN_SETTING:
                ids.add(u["id"])
                if u.get("our_summary"):
                    summaries.add(u["our_summary"])
    return dict(ids=ids, envs=envs, repos=repos, shas=shas, summaries=summaries)


def filter_lock(text: str) -> str:
    lock = c.load_yaml(c.LOCK_FILE)
    out = c.public_lock(lock)
    return c.dump_yaml(out)


def filter_keyed_yaml(path: str, hidden_envs: set, key_of) -> str:
    import yaml
    data = yaml.safe_load((c.ROOT / path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = {k: v for k, v in data.items() if key_of(k) not in hidden_envs}
    else:
        data = [e for e in data if key_of(e["key"]) not in hidden_envs]
    return c.dump_yaml(data)


def transform(path: str, hid: dict) -> str | None:
    """Return the public content of `path`, or None to skip it."""
    if path in ALWAYS_DENY_FILES or path.startswith(ALWAYS_DENY_PREFIXES):
        return None
    hidden = not c.publish_extras()
    if hidden and (path in HIDDEN_ONLY_FILES or path.startswith(HIDDEN_ONLY_PREFIXES)):
        return None
    if not hidden:        # extras are public: keep their content, only drop the marker comment lines
        if (c.ROOT / path).suffix not in TEXT_SUFFIXES:
            return ""
        return MARKER_LINES.sub("", (c.ROOT / path).read_text(encoding="utf-8"))
    if path == "data/sources.lock.yml":
        return filter_lock((c.ROOT / path).read_text(encoding="utf-8"))
    if path == "data/drafts/new_tasks.yml":
        return "# Draft labels for the tasks not in the seed file (public settings only).\n" + filter_keyed_yaml(path, hid["envs"], lambda k: k.split("/")[0])
    if path.startswith("data/drafts/blind_pass_"):
        return "# Blind second pass (public settings only).\n" + filter_keyed_yaml(path, hid["envs"], lambda k: k.split("/")[0])
    if (c.ROOT / path).suffix not in TEXT_SUFFIXES:
        return ""            # binary: handled by the caller
    text = (c.ROOT / path).read_text(encoding="utf-8")
    return PRIVATE_BLOCK.sub("", text)


def export(out) -> tuple[int, list[str]]:
    hid = hidden_identifiers()
    if out.exists():
        shutil.rmtree(out)
    n, skipped = 0, []
    for path in tracked():
        content = transform(path, hid)
        if content is None:
            skipped.append(path); continue
        dest = out / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if content == "" and (c.ROOT / path).suffix not in TEXT_SUFFIXES:
            shutil.copy2(c.ROOT / path, dest)
        else:
            dest.write_text(content, encoding="utf-8")
        n += 1
    return n, skipped


def scan(out) -> list[str]:
    """Search the finished export for anything that identifies the hidden setting. Returns problems."""
    if c.publish_extras():
        return []            # nothing is hidden, so there is nothing to find
    hid = hidden_identifiers()
    needles = sorted(hid["ids"] | hid["envs"] | hid["repos"] | hid["shas"] | hid["summaries"], key=len, reverse=True)
    problems = []
    for p in sorted(out.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(out))
        if rel.startswith(f"data/tasks/{c.HIDDEN_SETTING}") or "extras" in p.name.lower() and p.suffix in (".yml", ".json", ".csv"):
            problems.append(f"{rel}: file belongs to the hidden setting")
        if p.suffix not in TEXT_SUFFIXES:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for n in needles:
            if n in text:
                problems.append(f"{rel}: contains {n[:60]!r}")
                break
        if p.suffix in (".yml", ".json", ".csv") and re.search(r'"setting": "linuxarena-extras"|^setting: linuxarena-extras', text, re.M):
            problems.append(f"{rel}: names the hidden setting as data")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT_DEFAULT)); ap.add_argument("--scan-only", action="store_true")
    a = ap.parse_args()
    out = c.Path(a.out) if hasattr(c, "Path") else __import__("pathlib").Path(a.out)
    if c.publish_extras():
        print("publish_extras is true: nothing is hidden, so there is nothing to strip (the export still excludes private files).")
    if not a.scan_only:
        n, skipped = export(out)
        print(f"exported {n} files to {out}; left out {len(skipped)} private files")
    problems = scan(out)
    for p in problems[:40]:
        print("LEAK", p)
    print(f"scan: {len(problems)} problems" if problems else "scan: clean, no identifier of the hidden setting found")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
