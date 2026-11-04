# Handoff (4 Nov 2026)

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

