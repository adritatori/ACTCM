# Contributing

Thank you for helping. This project is a draft: every label is provisional and no human has reviewed any label yet.
Human reviews and well-argued disputes are the most useful contributions. The review queue on the site lists every incident step that still needs one.

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

## Add an incident or a step

Incidents live in `data/incidents/<id>.yml`, one file each. Sources are registered in `data/incidents/_sources.yml`.
The step rules are S1 to S7 in the codebook (v1.3-draft, not yet approved).

The easy way is the site's **Contribute** page. It opens a GitHub form with some fields filled in. There are four forms:

| Form | Use it to |
|---|---|
| Propose a new incident | Suggest an incident that has a detailed public account |
| Add or correct an incident step | Add one step, or fix one, in a listed incident |
| Dispute a step label | Argue that a step's tactic or technique is wrong, citing a rule S1 to S7 |
| Review a step | Record that you checked a step's quote and label (public, so not a blind review) |

Rules for a step:

- **Quote:** at most 25 words, word for word, in quotation marks, with a link to the page.
- **Description:** your own words, at most 40 words, one distinct behaviour the source describes.
- **Detail:** stay at the level the source gives. Describe behaviour. No commands, payloads, passwords, internal host names
  or indicators of compromise. Do not name private individuals.
- **Label:** the tactic is what the step was *for* at that moment (S2). Give a technique only if the source gives enough detail (S5).
  If two tactics fit, say so: the step is marked ambiguous and both are kept (S4).
- Do not copy the text of a source into the repository, and do not copy text from other incident lists such as swarms.wiki. Link to them.

### What the automatic check does

When you submit a form, `.github/workflows/submission-check.yml` runs `scripts/check_submission.py`. It checks that:

1. the required fields are filled in;
2. the tactic and technique IDs exist in the pinned MITRE ATT&CK® v20.0 and fit together;
3. the quote has at most 25 words and the description at most 40;
4. the source is an `https` address on a public host;
5. the quoted words appear in the article text of that source (menus, footers and reader comments do not count);
6. the step id does not collide with an existing step.

It then posts **one comment** with a pass or fail table and sets one label: `evidence-checked` (a new step whose quote was found),
`format-checked` (the other forms) or `needs-fix`. Edit the issue and it runs again.

The check is a script. It matches text and looks up IDs. It does not judge whether a label is right. **It never changes the data and
never sets a status.** A human maintainer applies accepted submissions through a pull request.

### Step status tiers

| Status | Meaning | Who may set it |
|---|---|---|
| `draft_needs_human_review` | One AI drafted this step. No script check, no human check. | Claude or a script |
| `evidence_checked` | A script found the quoted words in the cited source. No human has checked the label. | A script only (`scripts/evidence.py`) |
| `reviewed` | One human checked this step. | A named human only |
| `adjudicated` | Two humans labelled it separately, compared, and recorded why. | Named humans only |

`make validate` rejects a step whose status is `reviewed` or `adjudicated` without a listed human in `reviewed_by`, and a step marked
`evidence_checked` that the script did not set.

### By pull request

```bash
uv run python scripts/evidence.py fetch            # fetch the registered sources into a local cache (not committed)
uv run python scripts/evidence.py check --write    # check every quote; sets or clears the script-set status
make validate && make build && make site           # coverage is recomputed by scripts/coverage.py, never by hand
```

### Licence of contributions

By contributing data or labels you agree that they are offered under the repository's data licence, CC BY 4.0
([LICENSE-DATA](LICENSE-DATA)). Code contributions are under the MIT licence ([LICENSE](LICENSE)). Quotes from sources stay
the work of their publishers; we keep them short and link to the source.

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
