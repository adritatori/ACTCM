#!/usr/bin/env python3
"""Fill the 'Result so far' block of README.md from data/generated/counts.json (no number is typed by hand)."""
import json

import common as c

START, END = "<!-- result:start -->", "<!-- result:end -->"
PIN = {"linuxarena": ("LinuxArena", "`linuxarena/ct-linuxarena` manifest and its 10 environment repos", "Manifest `v0.4.0`; every environment at `v3.2.0`"),
       "linuxarena-extras": ("LinuxArena extras", "`linuxarena/ct-linuxarena-extras` and 4 environment repos", "Manifest `v0.2.0`; environments by the `sha` in its lock file"),
       "refactor_arena": ("Refactor Arena", "`linuxarena/refactor_arena`", "`v3.2.0`"),
       "vllm": ("vLLM", "`linuxarena/ct-vllm`", "`v0.2.0`")}
EXTRAS_LINE = "**LinuxArena extras is not included in v0.1, pending permission from its maintainers.**"


def paragraph(cn: dict) -> str:
    s, by, t = cn["summary"], cn["totals"]["by_setting"], cn["tiers"]["total"]
    names = {x["id"]: x["name"] for x in cn["tactics"]}
    gp = ", ".join(names[g] for g in cn["gaps"]["primary"])
    parts = ", ".join(f"{x['name']} {by[x['id']]}" for x in cn["settings"])
    return (f"{s['tasks']} side tasks are counted ({parts}). Counting each task once, under its main tactic, {s['tactics_covered_primary']} of "
            f"{s['tactics_total']} ATT&CK tactics have at least one task, and {s['gap_tactics_primary']} have none: {gp}. "
            f"{s['template_tasks']} tasks ({s['template_share_percent']}%) are repeated templates, and {s['ambiguous_labels']} labels are marked ambiguous. "
            f"Label status: {t['draft_needs_human_review']} Draft, {t['ai_cross_checked']} AI cross-checked, {t['reviewed']} Reviewed by a human, {t['adjudicated']} Adjudicated by humans. "
            "These counts are provisional until the open decisions are settled, and they show what is tested, not what is caught.")


def fill(s: str, name: str, body: str) -> str:
    a, b = s.index(f"<!-- {name}:start -->") + len(f"<!-- {name}:start -->"), s.index(f"<!-- {name}:end -->")
    return s[:a] + "\n" + body.strip("\n") + "\n" + s[b:]


def scope(cn: dict) -> str:
    rows = ["Version 1 covers the settings below, each pinned by commit SHA (`data/sources.lock.yml`):", "",
            "| Setting | Source | Pin |", "|---|---|---|"]
    rows += [f"| {PIN[x['id']][0]} | {PIN[x['id']][1]} | {PIN[x['id']][2]} |" for x in cn["settings"]]
    if cn.get("extras_note"):
        rows += ["", EXTRAS_LINE]
    return "\n".join(rows)


def main() -> None:
    cn = json.loads((c.DATA / "generated" / "counts.json").read_text())
    p = c.ROOT / "README.md"
    s = p.read_text(encoding="utf-8")
    s = fill(s, "result", paragraph(cn))
    s = fill(s, "scope", scope(cn))
    unf = cn["totals"]["unfinished_upstream"]
    s = fill(s, "drafts", f"{unf} unfinished upstream drafts (`*_idea` folders) are excluded from all counts." if unf else "")
    s = fill(s, "extras-licence", "" if cn.get("extras_note") else
             "- The four LinuxArena extras environment repositories have no licence, so their goal text is **not** copied here. We store the task ID, a link, and a summary of 20 words or fewer written by us.")
    p.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    main()
