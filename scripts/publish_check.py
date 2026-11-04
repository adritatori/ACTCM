#!/usr/bin/env python3
"""The publish gate. Run `make publish-check`. Exit code 0 means nothing blocks publishing; it does NOT publish.

Blocks publishing while:
  1. a `TODO(Tory)` marker is left in any file that would be public,
  2. the public export (scripts/export_public.py) contains anything that identifies a hidden setting,
  3. config/publish.yml has publish_extras true without the maintainers' permission being recorded.
Add --full to also run the tests and `make reproduce` inside the export (needs internet).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import common as c
import export_public as ex

MARK = re.compile(r"TODO\(Tory\)")
# files that talk ABOUT the marker are not left-over to-dos
EXEMPT = {"scripts/publish_check.py", "tests/test_publish_gate.py", "docs/OPEN_QUESTIONS.md", "docs/PUBLISH.md",
          "docs/EXTRAS_HIDING_PLAN.md", "docs/EXTRAS_EFFECT.md", "docs/RELEASE_CHECKLIST.md"}


def find_todos(root=None, files=None) -> list[str]:
    root = root or c.ROOT
    hits = []
    for p in files if files is not None else ex.tracked():
        if p in EXEMPT or p.startswith((".cache/", ".venv/", "docs/screenshots/")) or p.endswith((".png", ".pyc")):
            continue
        f = root / p
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if MARK.search(line):
                hits.append(f"{p}:{i}: {line.strip()[:110]}")
    return hits


def check(full: bool = False) -> list[str]:
    blockers = []
    todos = find_todos()
    blockers += [f"TODO left: {t}" for t in todos]
    if c.publish_extras():
        blockers.append("publish_extras is true: confirm the maintainers' permission is on record, then edit this check")
    n, _ = ex.export(ex.OUT_DEFAULT)
    blockers += [f"export leak: {p}" for p in ex.scan(ex.OUT_DEFAULT)]
    if full:
        env = dict(os.environ)
        for cmd in (["uv", "run", "pytest", "-q"], ["uv", "run", "python", "scripts/reproduce.py"]):
            r = subprocess.run(cmd, cwd=ex.OUT_DEFAULT, capture_output=True, text=True, env=env)
            if r.returncode != 0:
                blockers.append(f"`{' '.join(cmd)}` failed in the export:\n" + (r.stdout + r.stderr)[-600:])
    return blockers


def main() -> int:
    full = "--full" in sys.argv
    blockers = check(full)
    print("PUBLISH GATE")
    print(f"  TODO(Tory) markers left          : {len(find_todos())}")
    print(f"  publish_extras                   : {c.publish_extras()}")
    print(f"  export scan (hidden identifiers) : {'clean' if not [b for b in blockers if b.startswith('export leak')] else 'LEAKS'}")
    print(f"  tests and reproduce in the export: {'run' if full else 'not run (use --full)'}")
    if blockers:
        print(f"\nBLOCKED by {len(blockers)} item(s):")
        for b in blockers:
            print("  -", b)
        return 1
    print("\nPASS: nothing blocks publishing. Say \"publish\" to start Phase 9.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
