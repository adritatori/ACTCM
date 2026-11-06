# How to review (one page)

You will read 64 short attack descriptions and pick **one** label for each. It takes about 5 short sessions of 15 items. You can stop any time.

## What you are labelling

Each item is a **side task**: a hidden bad goal given to an AI agent in a test. Your job is to say which **ATT&CK tactic** it is.

**A tactic is the attacker's *goal*** (the "why"), for example "steal data" or "get into the network". There are 15 to choose from, each with a one-line definition on screen. A **technique** is the *how*. You do not need techniques.

## The one rule

> **Label the attacker's END goal, not the steps.**

The end goal is **what the scorer checks** (shown on screen under "What the scorer checks").
Many tasks need several steps. Ignore the steps. Ask: *"When this attack has fully worked, what has the attacker achieved?"*

Example: "corrupt the workflow data so runs fail". The method is changing a service. The end goal is damaged data. Pick **Impact**.

## If you are unsure

1. Pick your **best guess** anyway. Do not skip.
2. Click **Unsure** (key `U`).
3. Write one line in the note: which words in the goal made it hard, and what your second choice was.
4. If none of the 15 fits at all, pick **None fits** (key `X`) and say why in the note.

"Unsure" is useful data, not a failure. Do not look anything up that shows how the task was labelled before. Do not discuss answers with the other labeler until both files are sent.

## Using the page

1. Double-click `review_blind.html` (use Chrome, Edge or Firefox; not a private window).
2. Type your name, press Enter. Use the same name every time.
3. For each item: pick a tactic, pick Sure/Unsure, add a note if you want, press **Save and next** (or Enter).
4. After 15 items you get a **break screen**. Take the break.
5. **Next unreviewed** jumps to the next item you have not finished.

Keys: tactics are `1`-`9`, `0`, `Q W E R T`; `X` = none fits; `S` / `U` = sure / unsure; `N` = next unreviewed; arrows = back / skip; `?` = help.

## Saving and sending

Your progress is saved in your browser on **this computer only**. Clear the browser data and it is gone. So:

1. Click **Export CSV** at every break and when you finish. A file like `actcm_blind_yourname_2026-11-06.csv` is downloaded.
2. Send that **CSV file** (not the HTML) to the person who sent you this kit.
3. To carry on later or on another computer, open the page and click **Import CSV**.

A template item (for example "reverse shell") counts **once** for all the environments that share it. A few items are marked "Outlier" because their scorer differs slightly; label them like any other item.

## For the project owner

Use `review_owner.html`. Pick first, then press Reveal to see the AI label. Your pick is locked at that moment. Then choose keep mine / take AI's / discuss later. When both files are in, run:

```bash
python3 review/agreement.py owner.csv second_labeler.csv --out-dir review/out
```

The report ends with a **WARNINGS** list. Read it before trusting the numbers.
