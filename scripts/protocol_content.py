"""The verification protocol, as data. Rendered to docs/PROTOCOL.md and site/verify.html by build_site.py.

Blocks: ("p", text) ("ol", [items]) ("ul", [items]) ("code", text) ("note", text).
Inline: `code`, **bold**, [text](url).
"""
from __future__ import annotations

import html
import re

import common as _c
REPO = "https://github.com/" + _c.config()["repository"]   # config/publish.yml


def sections(ctx: dict) -> list[dict]:
    t = ctx["tiers"]
    return [
        dict(id="intro", title="Before you start", blocks=[
            ("p", "This protocol is written so that anyone can repeat it exactly, without asking anyone. Each part is numbered. "
                  "You need Python 3.11 or newer and an internet connection (the sources are fetched from GitHub)."),
            ("note", "**Provisional.** Every label is a draft and no human has reviewed any label yet. "
                     f"Right now: {t['draft_needs_human_review']} Draft, {t['ai_cross_checked']} AI cross-checked, {t['reviewed']} Reviewed by a human, {t['adjudicated']} Adjudicated by humans."),
        ]),
        dict(id="a", title="A. Reproduce the data", blocks=[
            ("ol", [
                f"Clone this repository: `git clone {REPO}.git` and `cd actcm`. (This step works after publishing.)",
                "Install with one command: `uv sync`. If you use pip instead: `pip install -r requirements.txt`.",
                "Run `make reproduce`. With pip, run `make reproduce PY=python3`. It does four things: (1) fetches every source repository at its pinned commit and refuses to continue if a commit differs; "
                "(2) fetches the MITRE ATT&CK® v20.0 and ATLAS 2026.10 files and checks their SHA-256 against `data/sources.lock.yml`; "
                "(3) rebuilds the task files, tables, Navigator layers, stress test, review sheet and site; "
                "(4) compares the SHA-256 of every output file with `data/generated/CHECKSUMS`. It does not change any label.",
                "A pass looks exactly like this (N is the number of lines in `data/generated/CHECKSUMS`):",
            ]),
            ("code", f"[1/4] fetched {ctx['n_repos']} source repositories at their pinned commits ... ok\n"
                     "[2/4] fetched ATT&CK v20.0 and ATLAS 2026.10, SHA-256 match the lock file ... ok\n"
                     "[3/4] rebuilt tasks, tables, Navigator layers, stress test, review sheet and site ... ok\n"
                     "[4/4] comparing N files with data/generated/CHECKSUMS\n"
                     "PASS: all N files match"),
            ("p", "**What to do on a mismatch.** The last lines then list each file as `MISMATCH`, `MISSING` or `UNLISTED`, and the last line reads `FAIL: k of N files differ`."),
            ("ol", [
                "Run `git status`. If you edited a file in `data/` on purpose, that is the cause. A deliberate change to a label should be followed by `make checksums` and a pull request.",
                "If you changed nothing, run `git diff --stat`. The rebuild rewrites files, so this shows exactly which files changed and by how much.",
                "If step 1 of the output failed, the source repository no longer has that commit (a force-push or deletion). Open a **Bug** issue with the full output.",
                "If step 2 failed, the framework file changed upstream. Do not edit the lock file. Open a **Bug** issue with the full output.",
                "If only a few files differ and `git diff` shows differences you cannot explain, open a **Bug** issue and attach the `MISMATCH` lines.",
            ]),
        ]),
        dict(id="b", title="B. Check one label by hand (spot check)", blocks=[
            ("ol", [
                "Open the Explorer, click a task, and follow its link under \"Source at the pinned commit\". That link points at the exact commit, not a branch.",
                "Read `goal.md` first. Then read the scorer: `scorer.py`, `scorer.md` or `scoring_details.md` in the same folder. Write down in one sentence what the scorer checks."
                + (" For a source repository with no licence the goal text is not copied into this project: read it at the link." if ctx["show_extras"] else ""),
                f"Apply codebook rules R1 to R9 in order ([codebook]({REPO}/blob/main/codebook/CODEBOOK.md), works after publishing). Write your label (tactic ID, technique, required steps, ATLAS technique) **before** you look at ours.",
                "Compare with the label in the Explorer. If you disagree, open a **Label dispute** issue (the template is provided) and give your reasoning rule by rule.",
            ]),
        ]),
        dict(id="c", title="C. Full independent relabelling (how Tory and any contributor do it)", blocks=[
            ("ol", [
                "**Calibration.** Run `python scripts/sample.py --calibration`. It prints the same 10 tasks for everyone (fixed seed 20261104). "
                "Get a sheet for just those tasks with `python scripts/blind_sheet.py --calibration --out calibration.csv`, label them, then run `python scripts/sample.py --calibration --reference` "
                "to see the reference labels. For every task you missed, read the codebook rule named in its rationale.",
                "**Blind labelling.** Run `python scripts/blind_sheet.py`. It writes `.cache/blind_sheet.csv` with the goal text only and **no existing labels**. "
                "Fill in `primary_tactic` (a tactic ID such as TA0010), `technique`, `required_step_tactics` (separated by semicolons), `atlas_technique`, `confidence` and, if ambiguous, `alternative_tactic`. Label every task. Save the file as `yours.csv`.",
                "**Agreement.** Run `python scripts/blind_sheet.py --ours ours.csv`, then `python scripts/agreement.py ours.csv yours.csv`. Report Cohen's kappa overall and per tactic, and the number of items. "
                "In plain words: kappa is the agreement left after removing what two raters would agree on by luck. 1 means perfect agreement, 0 means no better than chance. "
                "The words \"moderate\" or \"almost perfect\" come from a common convention (Landis and Koch), not from a standard.",
                "**Adjudication.** For each disagreement, both raters write their reasons and agree a final label. Record it in the task's `history` with the date, who, the change and the reason. "
                "If you cannot agree, set the label to `ambiguous` and keep both (the second goes in `alternative`).",
                "**Codebook change control.** If a disagreement shows a rule is unclear, propose a change in a pull request, bump the codebook version, and re-check the tasks the rule affects.",
                "**Publish.** The status becomes `reviewed` (one human checked it) or `adjudicated` (two humans agreed). Only a named human may set either. "
                "To review as one human, run `uv run python scripts/review.py --queue start_here` in your own terminal; it will not run from a script. The site shows the counts for every status.",
            ]),
        ]),
        dict(id="d", title="D. Check the gaps", blocks=[
            ("ol", [
                "Run `python scripts/stress_test.py`. It prints, for each gap tactic, the share of 5,000 runs in which the tactic stays at zero tasks after labels are randomly flipped.",
                "A gap is reported as **robust** only if it stays at zero in at least 95% of runs. That threshold is our choice, not a standard.",
                "Read the result with care: the test only reshuffles labels we already have. A gap at 100% means nothing in our labels or alternatives points to that tactic. "
                "It does not show that a different labelling would find no tasks there.",
            ]),
        ]),
        dict(id="e", title="E. Add a new control setting", blocks=[
            ("ol", [
                "The setting must be public, with its side tasks in files, and a licence (or written permission to use its text).",
                "Add it to `data/sources.lock.yml`: add an entry in `scripts/ingest.py` and run `python scripts/ingest.py lock`. Write an ingest adapter if its folders differ from `side_tasks/<id>/docs/goal.md`.",
                "Label the tasks with the codebook. Run `make validate`, `make test` and `make reproduce`.",
                "Open a pull request with the **New setting** template.",
            ]),
        ]),
        dict(id="f", title="F. Known limits", blocks=[
            ("ul", [
                f"One AI drafted every label and a second AI checked them. **No human has reviewed any label yet** ({t['reviewed']} reviewed, {t['adjudicated']} adjudicated). Every label is a draft.",
                "Public tasks only. Held-out tasks may fill some gaps (for example, LinuxArena's withheld environments).",
                "MITRE ATT&CK® was built for human attackers. Some AI-specific goals fit loosely; those tasks have no technique (rule R9).",
                "Coverage is not detection. Per-tactic monitor detection rates need per-action monitor scores, which were not openly available on 4 Nov 2026.",
                f"{ctx['open_n']} decisions are still open ({ctx['open_text']}), so counts and gaps are provisional.",
            ]),
        ]),
    ]


# ---------------------------------------------------------------------------------------------- renderers
def _inline_html(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)


def to_html(secs: list[dict]) -> str:
    out = []
    for sec in secs:
        out.append(f'<h2 id="{sec["id"]}">{_inline_html(sec["title"])}</h2>')
        for kind, val in sec["blocks"]:
            if kind == "p":
                out.append(f"<p>{_inline_html(val)}</p>")
            elif kind == "note":
                out.append(f'<p class="callout">{_inline_html(val)}</p>')
            elif kind in ("ol", "ul"):
                out.append(f"<{kind}>" + "".join(f"<li>{_inline_html(i)}</li>" for i in val) + f"</{kind}>")
            elif kind == "code":
                out.append(f"<pre><code>{html.escape(val)}</code></pre>")
    return "\n".join(out)


def to_markdown(secs: list[dict]) -> str:
    out = ["# Verification protocol", "",
           "Generated from `scripts/protocol_content.py` by `scripts/build_site.py`. The same text is on the site's Verify page.", ""]
    for sec in secs:
        out += [f"## {sec['title']}", ""]
        for kind, val in sec["blocks"]:
            if kind == "p":
                out += [val, ""]
            elif kind == "note":
                out += [f"> {val}", ""]
            elif kind == "ol":
                out += [f"{i}. {x}" for i, x in enumerate(val, 1)] + [""]
            elif kind == "ul":
                out += [f"- {x}" for x in val] + [""]
            elif kind == "code":
                out += ["```", val, "```", ""]
    return "\n".join(out)
