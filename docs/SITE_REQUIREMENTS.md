# Site requirements added during Phase 3 (apply in Phase 6)

From Tory, 2026-11-04:

1. **The Explorer must show a count for each label tier**, from `data/generated/status_counts.json`:
   Draft, AI cross-checked, Reviewed by a human, Adjudicated by humans (and "No label yet" if any).
   Show them in the summary strip and in the setting breakdown.
2. **Never describe `ai_cross_checked` as reviewed.** Use only the wording in `data/status_tiers.yml`.
   The plain-language line is: "A second AI, which was not shown our label, chose the same main tactic.
   No human has checked it." A test must fail if the words in `never_say_for_ai_cross_checked`
   appear next to that tier.
3. Every task's detail panel shows its tier, who set it and when (from `history`).
4. Counts on the page come from `counts.json` / `status_counts.json`, never typed by hand.
