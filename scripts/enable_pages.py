#!/usr/bin/env python3
"""Make the Pages workflow runnable: remove its `if: false` guard. Used once, at publish time (Phase 9).

  enable_pages.py --dry-run     show what would change
  enable_pages.py               edit .github/workflows/pages.yml

Refuses to run while `make publish-check` would block, so it cannot be used to skip the gate.
"""
import sys

import common as c
import publish_check as pc

WF = c.ROOT / ".github" / "workflows" / "pages.yml"
GUARD = "    if: false\n"


def main() -> int:
    dry = "--dry-run" in sys.argv
    text = WF.read_text(encoding="utf-8")
    if GUARD not in text:
        print("pages.yml has no `if: false` guard: it is already enabled.")
        return 0
    blockers = pc.check()
    if blockers and not dry:
        print("Refusing: the publish gate is blocked:\n  - " + "\n  - ".join(blockers[:10]))
        return 1
    lines = text.replace(GUARD, "").split("\n")
    top = next(i for i, l in enumerate(lines) if l.startswith("name:"))
    new = "\n".join(["# Deploys the site to GitHub Pages. It is started by hand (workflow_dispatch) from the Actions tab.",
                     "# One-time setup in the repository: Settings > Pages > Source: GitHub Actions.",
                     "# It builds the site with scripts/build_site.py and publishes the site/ folder."] + lines[top:])
    print(("would remove" if dry else "removed") + " the `if: false` guard from .github/workflows/pages.yml")
    if not dry:
        WF.write_text(new, encoding="utf-8")
        print("Next: in the repository settings choose Pages > Source: GitHub Actions, then run the workflow once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
