"""A keyword tactic SUGGESTER. Suggestion only: its output is never written to a label field.

It reads only text (the goal text, or our short summary where goal text is not stored) and returns a tactic ID.
It exists to measure how fragile a naive keyword approach is (see stress_test.py). Ported from the seed file.
"""
import re

SUGGESTION_ONLY = True
RULES = [
    (r"reverse shell", "TA0011"),
    (r"remote code execution|\brce\b", "TA0001"),
    (r"(download|execute)s? .*malware|malicious binary|execute arbitrary|command injection|shell commands", "TA0002"),
    (r"exfiltrat|expose|leak|accessible to an? (external|unauthenticated)|unauthorized (parties|location)", "TA0010"),
    (r"ssh|authorized_keys|backdoor|persistent", "TA0003"),
    (r"escalate|admin role|full read/write|privilege", "TA0004"),
    (r"audit|history|evidence|without creating any tracking|no record|traces", "TA0005"),
    (r"bypass|allowlist|blacklist|access control|authentication", "TA0112"),
    (r"password|credential", "TA0006"),
    (r"delete|destroy|unrecoverable|corrupt|poison|pollute|misclassif|suppress|substitute|re-attribute|impersonat|inject", "TA0040"),
    (r"open redirect|redirect", "TA0001"),
    (r"read secret|discover the contents|capture|another team|tenant|persists", "TA0009"),
]


def suggest(text) -> str:
    """Return a tactic ID, or 'UNLABELED'. Never raises on odd input."""
    if not isinstance(text, str):
        return "UNLABELED"
    t = text.lower()
    for pat, tac in RULES:
        if re.search(pat, t):
            return tac
    return "UNLABELED"
