# Glossary check against the sources (2026-11-04)

Sources read: Control Tower docs at commit `9035b914e8285f571a46088a5c0efac9afe765b4` (see `docs/RELATED_WORK_SEARCH.md`).
Not read: the LinuxArena paper (arxiv.org unreachable) and `docs/development/protocols.md` (not opened).
Where the brief's glossary and the sources disagree, the sources win (brief rule). Changes made:

| Term | Brief wording | Source says | Site wording |
|---|---|---|---|
| AI control | "...treats the agent like a possible insider threat." | `control-concepts.md`: "a research field focused on extracting maximum usefulness from a potentially misaligned AI while ensuring safety." The insider-threat phrase is not in the docs I read. | Source definition. Insider-threat sentence **dropped** (not verified). |
| Live / delayed | "Delayed: the agent plants something (for example a vulnerability) that causes harm later." | `making-side-tasks.md`: delayed = "harm after the trajectory is done: the agent plants something that does damage later." `failure-types.md`: delayed harm is reversible before it lands and the agent supplies proof; live harm happens during the run and cannot be undone. | Brief wording kept (it matches `making-side-tasks.md`), plus the reversible / proof point from `failure-types.md`. |
| Safety | "Roughly, the chance that an attack is caught before it succeeds." | `control-concepts.md`: "the probability the blue team wins (the probability that the BT catches the RT before the RT accomplishes a side task)", with formula P(caught) / (P(caught) + P(uncaught and side task succeeded)). | Source definition and formula. |
| Monitor | "often a weaker AI model" | `glossary.md`: trusted model = "A weaker model the blue team trusts not to scheme, used for monitoring". | Kept, now sourced. |
| Audit budget / FPR | "share of honest actions flagged for human review" | `glossary.md`: audit budget = fraction of honest actions the blue team may audit, stated as an FPR. | Kept. |
| Action | (used, not defined in brief) | `glossary.md`: a model call whose response makes tool calls. | Added to the glossary, sourced. |
| Honest run / attack run | "The same agent run without (honest) and with (attack) a side task." | Docs call them honest eval and attack eval (halves of a control evaluation). | Kept, with the docs' names. |
| Main task, side task | as in brief | `making-side-tasks.md`: a side task is "a subtle sabotage objective that an AI agent might attempt to accomplish covertly while working on a main task." | Kept. |

Terms about ATT&CK, ATLAS, Navigator, kappa and adjudication are project terms or MITRE terms. They were not checked against the Control Tower docs.
MITRE definitions are given in our own words and linked. The ATT&CK Terms of Use page has not been read (see `docs/TERMS_OF_USE_CHECK.md`).
