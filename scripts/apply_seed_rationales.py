#!/usr/bin/env python3
"""Replace the placeholder rationale on the seed tasks with a real one-line rationale (decision 7, 2026-11-04).
Non-template tasks: from data/drafts/seed_rationales.yml. Template tasks: the R3 text, updated for codebook v1.1.
Statuses are not touched. Idempotent."""
import re

import common as c
import labels as L

R3 = {
    "rce": "Template task (R3): *_rce -> Initial Access T1190; no required steps.",
    "reverse_shell": "Template task (R3): *_reverse_shell -> Command and Control T1071; no required steps.",
    "run_malware_live": "Template task (R3): *_run_malware_live -> Execution T1059; steps Command and Control, Privilege Escalation.",
    "run_malware_delayed": "Template task (R3): *_run_malware_delayed -> Execution T1059; steps Initial Access, Command and Control, Privilege Escalation.",
}
TEMPLATE = re.compile(r"_(rce|reverse_shell|run_malware_live|run_malware_delayed)$")


def main() -> None:
    seed = c.load_yaml(c.DATA / "drafts" / "seed_rationales.yml")
    n = 0
    for (env, tid), (f, t) in L.load_tasks().items():
        if t["setting"] != "linuxarena":
            continue
        m = TEMPLATE.search(tid)
        new = R3[m.group(1)] if m else seed.get(f"{env}/{tid}")
        if new is None:
            raise SystemExit(f"no rationale for {env}/{tid}")
        if t["labels"]["rationale"] == new:
            continue
        t["labels"]["rationale"] = new
        t["history"].append(dict(date="2026-11-04", who="claude_draft_2026-11-04", change="rationale rewritten (placeholder replaced by a one-line rationale)",
                                 reason="Tory's decision 7 (2026-11-04). Draft: not reviewed by a human."))
        c.dump_yaml(t, f); n += 1
    print("rationales updated:", n)


if __name__ == "__main__":
    main()
