# Pilot prediction (written before any incident step is drafted)

Committed on 17 Nov 2026, before the three incident sources were read in full and before any step was
labelled. The commit timestamp is the record.

## Prediction

At least some attack steps in the three pilot incidents will fall in the four tactics that have zero public
side tasks in ACTCM v0.1: Reconnaissance, Resource Development, Discovery, Lateral Movement.

## What would falsify it

If few or none of the steps fall in those four tactics, the "reality gap" claim is not supported by these
incidents, and we say so on the site and in the report.

## How it will be scored

- Counted by `scripts/coverage.py` from the step labels, not by hand.
- "Held": steps in the zero-task tactics appear in at least two of the three incidents.
- "Partly held": they appear in one incident only, or only as `ambiguous` steps whose alternative label is
  outside the four tactics.
- "Failed": no step, or only one step in total, falls in the four tactics.

## Limits known in advance

- Three incidents, chosen because they are well documented. Not a random sample.
- Step labels are AI drafts. A human review may move steps in or out of the four tactics.
- The person drafting the steps knows this prediction. Steps that are already covered are included as well as
  ones that are not; nothing is selected to make the gap look bigger.
