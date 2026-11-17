# Handoff (17 Nov 2026): incident replays, v0.2.0-draft

**Short version:** the branch `incident-replay` adds three incident replays, a coverage join, a redesigned site and a contribute-and-review flow.
It is in a pull request and is **not merged**: the live site still shows v0.1 until you merge. Every label is still an unreviewed draft.

## What the branch adds

| Part | What | Where |
|---|---|---|
| Incidents | 3 incidents, 93 steps (72 attack, 21 detection and response), each with a source quote | `data/incidents/` |
| The join | Each attack step compared with the 114 public tasks, by script | `scripts/coverage.py`, `data/generated/incident_coverage.json` |
| Site | Home, Incidents, Replay, Coverage, Tasks, Contribute, Review, Guide, Verify. White, light only | `scripts/build_site.py`, `scripts/site_incidents.py`, `site/` |
| Contribute | 4 issue forms, a checker, a workflow | `.github/ISSUE_TEMPLATE/`, `scripts/check_submission.py`, `.github/workflows/submission-check.yml` |

## Result (draft)

- 72 attack steps: 13 "same technique", 28 "same tactic only", 15 "never tested", 16 "can't tell".
- The prediction written down first held: 26 steps have one of the four zero-task tactics as their label, in all three incidents (15 without leaning on an ambiguous label).
- Caveat: the same AI that knew the prediction drafted the labels. No human has checked them.

## Not verified

- **No human has reviewed any step or task label.** 93 of 93 steps are "Evidence-checked": a script found the quote in the source. That is not a review of the label.
- OpenAI's post on the Hugging Face incident: both addresses answered 403. Stage 1 of that incident rests on Hugging Face's account.
- swarms.wiki entries: not matched (its entry pages load by script). The three incident files say so and link to nothing.
- The redacted Anthropic transcript: not read, not quoted (it asks not to be included in training data, and states no licence). Step order follows the September post.
- A press report of about 700 agents (Hugging Face incident): not read, not recorded.
- The submission workflow has not run on a real issue. Prefilled links were built and tested offline, not opened in a signed-in browser.
- External links: see `docs/LINK_CHECK.md` for what answered from the build session.

## What you still need to do

1. **Review the pull request**, then say `merge`. After the merge, GitHub Pages deploys by itself.
2. **Check the live site:** `python3 scripts/verify_site.py https://adritatori.github.io/ACTCM/`
3. **Approve or change codebook rules S1 to S7** (`codebook/CODEBOOK.md`, marked "needs Tory's approval").
4. **Review the step labels.** Start with the site's Review page. Start with the 15 "never tested" steps and the 23 ambiguous ones: they carry the result.
5. **Test the forms once:** open the Contribute page while signed in to GitHub, press "Open the GitHub form", and check the fields are filled in. Submit one test issue and check that the bot comments. If the fields are empty, tell me: the fallback is the plain form link.
6. **Email the swarms.wiki team** (you said you would), and send the three entry links if you want them shown.
7. **Open each external source link by hand** once.
8. **Decide** whether to fix the `1.1-draft` codebook string in the footer and Navigator layers (it is hard-coded; the file is at v1.2).
9. **Delete the GitHub token** mentioned below, if you have not yet.

---

# Earlier handoff (4 Nov 2026): v0.1.0-draft

**Short version:** the code, data and site for v0.1.0-draft are published. Every label is still an unreviewed draft.

## What is live

- **Repository:** <https://github.com/adritatori/ACTCM> (public). The files were added on top of the original upload commit with ordinary pushes (no force).
- **Site:** <https://adritatori.github.io/ACTCM/>. GitHub Pages builds it from this repository with `.github/workflows/pages.yml`, on every push to `main`. The first deployment came from commit `90c363d` and its status is `success`.
- **What the site shows:** Explorer, Guide and Verify. 114 side tasks (LinuxArena 92, Refactor Arena 7, vLLM 15) on MITRE ATT&CK® Enterprise v20.0 and ATLAS 2026.10, four Navigator layers, and CSV and JSON downloads. A draft warning is on every page. One line says: "LinuxArena extras is not included in v0.1, pending permission from its maintainers."
- **Checked:** CI passes (both jobs, including the real-browser job). `make reproduce` passes from a clean copy (144 files). `scripts/verify_site.py` passes 28 of 28 checks against the committed site files, the same files CI deployed. All 8 repository links return 200, and the 4 Navigator layer files return 200 and are valid layers (`docs/LINK_CHECK.md`).
- **Not checked by the person who built it:** the live address itself. The build sandbox cannot reach `github.io`. Run `python3 scripts/verify_site.py https://adritatori.github.io/ACTCM/` from your own computer.

## What is unreviewed

- **0 of 114 labels have been reviewed by a human.** 86 are "AI cross-checked" (a second AI agreed; that is AI-versus-AI, not human validation) and 28 are plain drafts. 20 are marked ambiguous.
- **Provisional defaults you approved, to review later:** the three tenant-isolation tasks are labelled Collection, and codebook v1.2 (R6) moved one task from Stealth to Defense Impairment.
- **Where to start:** `uv run python scripts/review.py --queue start_here` (20 tasks that are clear and cross-checked). It only runs in your own terminal.
- **Not verified:** 5 external links did not answer from the build session (two arXiv papers, the MITRE Terms of Use page, the CSA research note, the ZIRAN docs); the hosted ATT&CK Navigator app (only the layer files were tested); the LinuxArena paper's own wording of "safety"; Anthropic's LLM ATT&CK Navigator (found only in third-party write-ups).

## What is left

1. **Delete the GitHub token** you pasted into the chat (GitHub, Settings, Developer settings, Fine-grained tokens).
2. **Open the site** and run `verify_site.py` on the live address (above).
3. **Open each "Open in Navigator" link** in a browser and check that the layer loads.
4. **Review the labels**, starting with the start-here list. Only a named human can set `reviewed`.
5. **Run `make links`** on your computer to check the 5 unverified external links.
6. **LinuxArena extras:** not included until its maintainers give permission. To include it later, set `publish_extras: true` in `config/publish.yml`, rebuild, and publish again.
7. The blog has not been started, as instructed.

