"""GitHub issue forms: the field ids each form has, and prefilled links to them.

GitHub fills a form field from a URL query parameter named after the field's `id`. The ids below must match
.github/ISSUE_TEMPLATE/*.yml (tests/test_submission.py checks that). An issue never changes data by itself.
"""
from __future__ import annotations

import urllib.parse

import common as c

REPO = c.config()["repository"]
MAX_URL = 8000
FORMS = {
    "incident-new.yml": ["incident_title", "developer", "disclosed", "sources", "summary", "why"],
    "incident-step.yml": ["incident_id", "change", "step_id", "order", "what_happened", "quote", "source", "locator", "tactic", "technique", "rationale"],
    "step-dispute.yml": ["step_id", "current_label", "proposed_tactic", "proposed_technique", "rule", "argument"],
    "step-review.yml": ["step_id", "current_label", "decision", "own_tactic", "own_technique", "reason"],
}


def issue_url(template: str, title: str | None = None, **fields: str) -> str:
    """A link that opens the form with some fields filled in. Unknown field ids are an error, not silently dropped."""
    bad = [k for k in fields if k not in FORMS[template]]
    if bad:
        raise KeyError(f"{template} has no field {bad}")
    q = [("template", template)] + ([("title", title)] if title else []) + [(k, str(v)) for k, v in fields.items() if v not in (None, "")]
    url = f"https://github.com/{REPO}/issues/new?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
    if len(url) > MAX_URL:        # keep the template, drop the prefill: a long link may be cut by the browser or by GitHub
        url = f"https://github.com/{REPO}/issues/new?" + urllib.parse.urlencode([("template", template)])
    return url
