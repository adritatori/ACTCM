# Contributing

Thank you for helping. This project is a draft: every label is provisional and no human has reviewed any label yet.
Human reviews and well-argued disputes are the most useful contributions.

## Set up

```bash
git clone https://github.com/adritatori/actcm.git && cd actcm
uv sync                          # or: pip install -r requirements.txt
make test                        # tests (browser tests need node + playwright; they skip without them)
make validate                    # checks every task file
make reproduce                   # re-fetches the pinned sources and compares checksums (needs internet)
```

## Codebook first

Read [codebook/CODEBOOK.md](codebook/CODEBOOK.md) before you label or dispute anything. Every label follows rules R1 to R9 in order.
A label is changed by an argument from those rules, not by preference. If the rules are unclear, propose a change to the codebook (see below).

## How to dispute a label

1. Open the task's source link at the pinned commit. Read `goal.md`, then the scorer (`scorer.py`, `scorer.md` or `scoring_details.md`).
2. Write down what the scorer checks, in one sentence.
3. Apply R1 to R9 in order and write your label.
4. Open a **Label dispute** issue (template provided). Give the task ID, our label, your label, and your reasoning **rule by rule**.

A dispute is settled by adjudication: both raters give reasons, agree a final label, and record it in the task's `history`. If you cannot agree, the label becomes `ambiguous` and both are kept.

## Who may set a label status

`draft_needs_human_review` and `ai_cross_checked` may be set by scripts. **`reviewed` and `adjudicated` may only be set by a named human**
(listed in `scripts/labels.py`). Use `scripts/review.py` in your own terminal; it refuses to run without one. Never edit a status by hand to `reviewed`.
A pull request that does is rejected by `make validate`.

## Change the codebook

Open a pull request that changes `codebook/CODEBOOK.md`, bumps its version, adds a change-log entry, and lists the tasks the change affects.
Re-check those tasks and add a `history` entry to each. Counts and gaps must be re-run (`make build`, `make reproduce`).

## Add a new control setting

The setting must be public, with side tasks in files and a licence (or written permission). Follow section E of [docs/PROTOCOL.md](docs/PROTOCOL.md)
and open a pull request with the **New setting** template.

Do not copy goal text from a repository that has no licence. Store the task ID, a link, and a summary of 20 words or fewer in your own words.

## Writing rules

Short sentences. Define a term the first time it appears. No vague words ("various", "robust", "comprehensive") without a number behind them.
First mention of the framework is "MITRE ATT&CK®"; after that "ATT&CK". Never abbreviate or hyphenate the name, and never imply MITRE affiliation.
Every number on the site comes from a script, never from typing.

## Pull request checklist

The template at `.github/PULL_REQUEST_TEMPLATE.md` repeats this list.

- [ ] `make validate` passes
- [ ] `make test` passes
- [ ] `make reproduce` passes (or `make checksums` was run for a deliberate change, and the change is explained)
- [ ] No goal text was added for a source with no licence
- [ ] No status was set to `reviewed` or `adjudicated` by a script
- [ ] Label changes have a `history` entry with date, who, change and reason
- [ ] Codebook version bumped if a rule changed
