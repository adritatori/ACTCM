# Incident replay plan (Phase 0, 17 Nov 2026)

Status: plan only. No data, label or site file has changed. Branch: `incident-replay`.

## Goal

Take three well-documented incidents, split each into dated steps with a quoted source, label each step with
an ATT&CK tactic and technique, and let a script compare every step with the 114 public side tasks.
Show the result as an interactive replay.

## The problem it targets

v0.1 found 4 of 15 tactics with zero tasks, but could not say why those tactics matter beyond "ATT&CK lists them".
This links the gaps (and the covered tactics) to things real agents did.

## What a negative result means

If few or no incident steps fall in the four zero-task tactics, the "reality gap" claim is not supported by
these three incidents. We say so on the site. It is still a valid finding. The prediction is committed
before any step is drafted (`docs/PILOT_PREDICTION.md`).

## Cost

$0. No paid service, no monitor run, no new runtime dependency. Time: seven phases, each ends with a stop.

## Baseline (commit `e898889`, run in the build sandbox, Python 3.13)

| Check | Result |
|---|---|
| `uv sync` | ok |
| `make validate` | pass (warnings only: techniques that sit in two tactics) |
| `make test` | 289 passed, 10 skipped |
| `make build`, `make site` | pass; `git status` clean afterwards (build is deterministic today) |
| CI on `main` (run 5, 6 Nov 2026) | success |
| Pages deploy on `main` (run 4, 6 Nov 2026) | success |
| `verify_site.py` on the live address | **not verified**: the sandbox network refuses `adritatori.github.io` |

The 10 skips: missing framework and source caches (3), nothing to compare for hidden or unlicensed sources (4),
publish-gate tests that only run under `make publish-check` (2), no unfinished upstream drafts (1).

## Files to add

| Phase | Files |
|---|---|
| 1 | `schema/incident.schema.json`, `data/incidents/_sources.yml`, `scripts/validate_incidents.py`, `scripts/evidence.py`, `tests/fixtures/synthetic_incidents.yml` (+ source fixtures), `tests/test_incidents.py`, `tests/test_evidence.py` |
| 2 | `docs/PILOT_PREDICTION.md`, `data/incidents/{hf-2026-07,anthropic-pypi-2026-07,aisi-2026-07}.yml` (final slugs follow the sources) |
| 3 | `scripts/coverage.py`, `tests/test_coverage.py`, `data/generated/incident_coverage.json`, `data/generated/activity.json` |
| 4 | `site/{incidents,coverage,explorer,contribute,review}.html`, `site/incidents/<slug>.html`, new JS modules in `site/assets/`, `tests/test_contrast.py`, new browser tests |
| 5 | `.github/ISSUE_TEMPLATE/{incident-new,incident-step,step-dispute,step-review}.yml`, `scripts/check_submission.py`, `.github/workflows/submission-check.yml`, `tests/test_submission.py` |

## Files to change

`data/status_tiers.yml` (add `step_tiers`, `never_say_for_evidence_checked`; nothing removed),
`tests/test_status.py`, `codebook/CODEBOOK.md` (S1 to S7 as v1.3-draft, marked "needs Tory's approval"),
`scripts/validate.py`, `scripts/build_site.py` (split into modules), `site/assets/style.css` and `app.js`,
`Makefile`, `.github/workflows/ci.yml` (run the new build steps), `scripts/{verify_site,link_check,site_check,site_numbers}.py/js`,
`tests/test_site.py`, `tests/test_docs.py`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/HANDOFF.md`,
`THIRD_PARTY_NOTICES.md`, `docs/screenshots/*` (replaced in Phase 4).

## Risks

| # | Risk | Plan |
|---|---|---|
| 1 | **Network.** The sandbox refuses `www.aisi.gov.uk`, `cdn.prod.website-files.com` (AISI PDF), `openai.com`, `swarms.wiki`, `adritatori.github.io`. `huggingface.co`, `www.anthropic.com`, `github.com` answer. | Ask Tory to allow the hosts. Without them, incident 3 cannot be read or evidence-checked here, and its steps stay Draft. |
| 2 | The Anthropic 9 Sep URL answers 308 and moves to `/research/alignment-assessment-cybersecurity-incidents`. | Register the final address; note the redirect. Content not yet read. |
| 3 | The redacted transcript is long (reported about 1,000 pages). | Read what the steps need; record `read_extent: partial` honestly. |
| 4 | Evidence matcher false positives (quote found only in nav or footer, or inside a different sentence). | Adversarial fixtures first (section 9 of the brief). |
| 5 | Step labels are AI drafts. The coverage verdict inherits every label error. | Sensitivity flag per step; limits shown on the pages; nothing above `evidence_checked`. |
| 6 | Prefilled issue links: GitHub's new-issue page needs a login, so a browser test from here may not be able to confirm the prefill renders. | Test URL building offline; say "not verified in a real browser" if so, with steps for Tory. |
| 7 | Moving the Explorer breaks old deep links such as `index.html#setting-vllm`. | Home stays at `index.html`; a small script forwards old `#setting-…` hashes to `explorer.html`. |
| 8 | Extras leak through the new join. | Join reads only `c.public_task_files()`; a fixture has a tactic covered only by extras. |
| 9 | Pre-existing mismatch: `counts.json` and the Navigator layers say codebook `1.1-draft`; `CODEBOOK.md` says v1.2. Hard-coded in `scripts/build.py` and `navigator.py`. | Not touched without a decision (see questions). |
| 10 | All three incidents are dated after the drafting model's training data. | Nothing is written from memory; every fact comes from a source read in this work. |

## Questions for Tory

1. **Blocking for Phase 2:** allow the five hosts in risk 1 (an approval card is sent with this report).
2. Not blocking: fix the codebook version string (risk 9) when S1 to S7 land, or leave it?
3. Not blocking: does any link you shared depend on `index.html#setting-…` Explorer addresses? Default is the forwarder in risk 7.
