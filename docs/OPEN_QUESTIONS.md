# Open questions for Tory

Everything below needs a decision or an action from you. Nothing has been pushed or published.

## Applied as provisional defaults (you will review them later with the other labels)

1. **Tenant-isolation tasks.** Option 1 is applied: Collection for `file_indexing/authentication_bypass`, `auto_workflow/hijack_cross_team_workflows` and
   `media_processing/access_other_teams_media`. Each stays `ambiguous`, with the old tactic as the alternative, and has a history entry.
   Follow-on to ask separately: the same reading would move `file_indexing/access_secret_files_you_dont_own` to Collection.
2. **R6 (Stealth vs Defense Impairment), codebook v1.2.** Applied as drafted. One label changed: `media_processing/submit_untracked_job` (Stealth to Defense Impairment).
3. **R2 (required steps stated in the goal text).** Applied everywhere, including the four new tasks that had weak steps.

## Things only you can do or confirm

6. **MITRE ATT&CK® licence paragraph.** The paragraph and disclaimers on every page and in `THIRD_PARTY_NOTICES.md` come from MITRE's `LICENSE.txt` in `attack-stix-data`.
   I compared them with the paragraph you pasted from the Terms of Use page and found two wording differences, and I could not compare the disclaimers.
   See `docs/TERMS_OF_USE_CHECK.md`. Please paste the disclaimers section, or tell me which wording is on the page.
7. **TODO items left for you** (each is marked `TODO(Tory)` in the file, and `make publish-check` fails while any is left):
   the `CITATION.cff` name fields, the repository name (`config/publish.yml`, README, CONTRIBUTING, `CITATION.cff`), and the CC BY 4.0 legal text in `LICENSE-DATA`.
8. **Review the labels.** 0 of them are reviewed. Start with `uv run python scripts/review.py --queue start_here` in your own terminal.

## Known gaps, not blocking

9. **External links.** 5 external links did not answer from the build session and are unverified (`docs/LINK_CHECK.md`). Run `make links` from your own machine.
10. **Hosted Navigator.** Not tested: the host was unreachable. Evidence that it offers v20 is in `docs/NAVIGATOR_CHECK.md`. Test the "Open in Navigator" links after publishing (`make links-live`).
11. **CI.** The workflows were written but never run (no GitHub Actions in the build session). Check the first run after publishing.
12. **Refactor Arena and ct-vllm** declare MIT in `pyproject.toml` but have no `LICENSE` file, so there is no copyright line to reproduce. We treat them as MIT on that declaration.
13. **`ct-linuxarena` pin.** Pinned at `v0.4.0` because no `v3.2.0` tag exists. Checked: its file lists 10 environments at `v3.2.0`, and the count is 92 (`docs/SOURCES.md`).
14. **File names containing lowercase "attack"** (11 tracked files: the Navigator layers and the licence copy) are left as they are, by your decision. The branding rule covers the project name, repository name, logo and domain, and none of them contains "ATT&CK", "MITRE" or "attack".
16. **LinuxArena paper** was not read (arXiv unreachable). The glossary uses the Control Tower docs. Anthropic's LLM ATT&CK Navigator is "not verified" in the Guide.
17. **Publishing.** Rule 8: nothing is pushed or published until you say "publish". `docs/PUBLISH.md` describes the single step.
