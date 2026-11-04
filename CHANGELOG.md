# Changelog

All notable changes. Dates are 2026. This project is a draft; nothing has been published.

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
