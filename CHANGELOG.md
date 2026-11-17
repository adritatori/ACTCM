# Changelog

All notable changes. Dates are 2026. This project is a draft: no human has reviewed any label yet.

## v0.2.0-draft (17 Nov 2026)

Incident replays: what real AI agents did, compared with what public control tests check. Every new label is an AI draft.

- **Incidents (new):** three pilot incidents, chosen because they are well documented (not a random sample): the Hugging Face intrusion by an agent in
  an OpenAI evaluation, the package published to PyPI by Claude Mythos 5, and UK AISI incident INC-2026-07-28-01. 93 steps: 72 attack steps and
  21 detection and response steps. Each step has a quote of at most 25 words from a registered source. Files: `data/incidents/`.
- **Step status tiers (new):** Draft, Evidence-checked, Reviewed by a human, Adjudicated by humans. "Evidence-checked" means a script found the quoted
  words in the cited source; no human has checked the label. 93 of 93 steps are Evidence-checked, 0 are reviewed by a human.
- **Codebook v1.3-draft:** rules S1 to S7 for incident steps. Drafted, **not approved**. Task rules R1 to R9 are unchanged and no task label changed.
- **The join (new):** `scripts/coverage.py` compares every attack step with the 114 public tasks and writes `data/generated/incident_coverage.json`.
  Result: 13 steps have a task with the same technique, 28 the same tactic only, 15 are in a tactic no public task states, 16 cannot be told
  (two defensible labels disagree). 4 verdicts would change if an ambiguous task label moved to its alternative.
- **Prediction written down first** (`docs/PILOT_PREDICTION.md`): held. 26 of 72 attack steps have one of the four zero-task tactics as their label,
  in all three incidents; 15 of them do not depend on an ambiguous label. Drafted by an AI that knew the prediction; no human check.
- **Site redesign:** white, light theme only (the dark theme is removed). New pages: Home, Incidents, one Replay page per incident, Coverage,
  Contribute, Review. The task Explorer moved from `index.html` to `explorer.html`; old `index.html#setting-…` links are forwarded.
  Replay works by keyboard, by deep link (`#step=s12`) and without JavaScript.
- **Contribute and review:** four GitHub issue forms, prefilled links from the site, `scripts/check_submission.py` and the workflow
  `submission-check.yml`. The check posts one comment and one label. It never changes data and never sets a status.
- **Tests:** adversarial fixtures for the incident validator, the quote matcher, the join and the submission checker; browser tests for numbers,
  keyboard use and a no-JavaScript render; contrast computed from the CSS tokens.
- **Not done, not verified:** no human has reviewed any step or task label. No monitor has been run. OpenAI's own post on the Hugging Face incident
  could not be read (the site refused the request). The swarms.wiki entries for the three incidents were not matched. The redacted Anthropic
  transcript was not read. The submission workflow has not run on a real issue, and prefilled links were not checked in a signed-in browser.
- **Known mismatch, unchanged:** the site footer and the Navigator layers say codebook `1.1-draft` (hard-coded in `scripts/build.py` and
  `scripts/navigator.py`) although the codebook file is at v1.2, with v1.3-draft rules added.

## v0.1.0-draft (4 Nov 2026)

First draft, built in phases and not yet published.

- **Sources:** 114 side tasks read from 3 settings at pinned commits: LinuxArena 92, Refactor Arena 7, vLLM 15.
  LinuxArena extras is not included in v0.1, pending permission from its maintainers.
  The `ct-linuxarena` manifest is pinned at `v0.4.0` because it has no `v3.2.0` tag; its 10 environment repositories are at `v3.2.0`. See `docs/SOURCES.md`.
- **Frameworks:** MITRE ATT&CK® Enterprise v20.0 and MITRE ATLAS 2026.10, pinned by commit and SHA-256.
- **Labels:** every task has a draft label. 86 are AI cross-checked by a blind second AI, 28 are drafts, 0 are reviewed by a human.
- **Codebook v1.2 (draft, provisional):** N4 wins over R8 (`technique_fit` field); R2 counts a step only if the goal text states it, and R3 follows
  (required steps cut from 144 to 60 across all tasks); R6 asks whether the record already exists (Stealth) or a control is switched off (Defense Impairment);
  the three tenant-isolation tasks are labelled Collection. The last two are provisional defaults to be reviewed with the other labels.
- **Tools:** validate, build, stress test, Navigator layers (format 4.5), agreement (Cohen's kappa), review tool, calibration sampler, blind sheet, `make reproduce`, `make publish-check`.
- **Site:** Explorer, Guide, Verify (static HTML, light and dark, phone width).
- **Not done:** no human review, no publishing, hosted Navigator not tested.
