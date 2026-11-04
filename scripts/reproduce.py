#!/usr/bin/env python3
"""Reproduce every generated file from the pinned sources and compare with data/generated/CHECKSUMS.

  reproduce.py            fetch sources at their pinned commits, rebuild, compare checksums (exit 1 on any mismatch)
  reproduce.py --write    rebuild and (re)write CHECKSUMS. Maintainers only, after a deliberate change.

Nothing here changes a label. Labels, statuses and history live in data/tasks and are inputs; the rebuild keeps them.
"""
from __future__ import annotations

import hashlib
import sys

import build
import build_notices
import build_readme
import build_site
import common as c
import frameworks as fwm
import ingest
import navigator
import review_sheet
import stress_test

CHECKSUMS = c.DATA / "generated" / "CHECKSUMS"
GLOBS = ["README.md", "THIRD_PARTY_NOTICES.md", "docs/PROTOCOL.md", "data/tasks/**/*.yml", "data/unfinished_upstream.yml", "data/generated/*.json", "data/generated/*.csv", "data/generated/*.yml",
         "data/generated/navigator/*.json", "site/*.html", "site/data/*", "site/data/navigator/*.json"]
EXCLUDE = {"data/generated/CHECKSUMS"}


def hidden_paths() -> tuple[str, ...]:
    """Paths that belong to a hidden setting (config/publish.yml). They are never listed in CHECKSUMS."""
    if c.publish_extras():
        return ()
    return (f"data/tasks/{c.HIDDEN_SETTING}/", "data/unfinished_upstream.yml")


def files() -> list[str]:
    out = set()
    for g in GLOBS:
        out |= {str(p.relative_to(c.ROOT)) for p in c.ROOT.glob(g) if p.is_file()}
    return sorted(p for p in out - EXCLUDE if not p.startswith(hidden_paths()))


def digest(rel: str) -> str:
    return hashlib.sha256((c.ROOT / rel).read_bytes()).hexdigest()


def parse_checksums(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        if line.strip():
            h, _, p = line.partition("  ")
            out[p.strip()] = h.strip()
    return out


def compare(expected: dict, actual: dict) -> list[str]:
    bad = []
    for p in sorted(expected.keys() | actual.keys()):
        if p not in actual:
            bad.append(f"MISSING   {p}")
        elif p not in expected:
            bad.append(f"UNLISTED  {p}")
        elif expected[p] != actual[p]:
            bad.append(f"MISMATCH  {p}\n            expected {expected[p]}\n            got      {actual[p]}")
    return bad


def fetch_sources() -> int:
    lock = c.public_lock(c.load_yaml(c.LOCK_FILE))
    for s in lock["sources"]:
        c.fetch_at(s["repo"], s["sha"], s["repo"].split("/")[1])     # raises if the commit differs
    return len(lock["sources"])


def verify_frameworks() -> None:
    lock = c.load_yaml(c.LOCK_FILE)["frameworks"]
    for key, spec in (("attack", fwm.ATTACK), ("atlas", fwm.ATLAS)):
        got = fwm._fetch(spec)
        if got["sha"] != lock[key]["sha"] or got["sha256"] != lock[key]["sha256"]:
            sys.exit(f"{key}: fetched file differs from the pin (sha {got['sha']} sha256 {got['sha256']})")


def rebuild() -> None:
    ingest.cmd_build()
    fwm.cmd_build()
    build.main()
    navigator.main()
    stress_test.main()
    review_sheet.build()
    build_site.main()
    build_readme.main()
    build_notices.main()


def main() -> int:
    write = "--write" in sys.argv
    n = fetch_sources()
    print(f"[1/4] fetched {n} source repositories at their pinned commits ... ok")
    verify_frameworks()
    print("[2/4] fetched ATT&CK v20.0 and ATLAS 2026.10, SHA-256 match the lock file ... ok")
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        rebuild()
    print("[3/4] rebuilt tasks, tables, Navigator layers, stress test, review sheet and site ... ok")
    actual = {p: digest(p) for p in files()}
    if write:
        CHECKSUMS.write_text("".join(f"{h}  {p}\n" for p, h in sorted(actual.items())), encoding="utf-8")
        print(f"[4/4] wrote {len(actual)} checksums to data/generated/CHECKSUMS")
        return 0
    expected = parse_checksums(CHECKSUMS.read_text(encoding="utf-8"))
    print(f"[4/4] comparing {len(expected)} files with data/generated/CHECKSUMS")
    bad = compare(expected, actual)
    if bad:
        print("\n".join(bad))
        print(f"FAIL: {len(bad)} of {len(expected)} files differ")
        return 1
    print(f"PASS: all {len(expected)} files match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
