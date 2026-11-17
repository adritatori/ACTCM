#!/usr/bin/env python3
"""Check one GitHub issue that was opened with an ACTCM issue form, and say what it found.

Reads the issue from the event file GitHub Actions provides ($GITHUB_EVENT_PATH). Issue text is untrusted
input: it is parsed as data, shown back only inside code spans, and never reaches a shell or the repository.

What it checks: the form's required fields; that tactic and technique IDs exist in the pinned ATT&CK version and
fit together; word limits; that a cited source is an https address on a public host; that the quoted words are in
that source; that a step id does not collide.

What it never does: write to the repository, set a status, or approve anything. It posts ONE comment (a pass/fail
table and, when a new step passes, a snippet a maintainer can paste) and sets one label.

  check_submission.py           print the label and the comment
  check_submission.py --post    also post them to the issue (needs GITHUB_TOKEN with issues: write)
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import unicodedata
import urllib.request

import yaml

import common as c
import evidence as ev
import frameworks as fwm
import issue_forms as forms
import validate_incidents as vi

MARKER = "<!-- actcm-submission-check -->"
MAX_BODY = 20_000
MAX_SOURCES = 3
MAX_SHOWN = 120
LABELS = ["evidence-checked", "format-checked", "needs-fix"]
TPL = c.ROOT / ".github" / "ISSUE_TEMPLATE"
FETCH_WORDS = {
    "http_error": "the source answered with an error (HTTP {http_status})",
    "redirected_to_login": "the source redirects to a login page, so it cannot be read",
    "empty_page": "the source page is empty or has no readable article text",
    "too_big": "the source is too large to check (over 2 MB)",
    "pdf_unreadable": "the source is a PDF that could not be read",
    "network_error": "could not reach the source",
    "refused": "the source address is refused: {reason}",
}


def default_fetch(url: str) -> dict:
    return ev.fetch(url)


# ---------- reading the form ----------
def load_forms() -> dict:
    out = {}
    for fn in forms.FORMS:
        f = yaml.safe_load((TPL / fn).read_text(encoding="utf-8"))
        out[fn] = [dict(id=b["id"], label=b["attributes"]["label"], required=bool((b.get("validations") or {}).get("required")),
                        options=b["attributes"].get("options")) for b in f["body"] if "id" in b]
    return out


def clean(value: str) -> str:
    """Make a submitted value inert: no control or direction-changing characters, no backticks, no comment openers."""
    v = "".join(ch for ch in unicodedata.normalize("NFC", value or "") if ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cf", "Co", "Cs"))
    return v.replace("`", "'").replace("<!--", "<! --").replace("-->", "-- >").strip()


def parse_body(text: str) -> dict:
    """{heading: value} for an issue-form body ("### Heading" blocks). The first block with a heading wins."""
    out = {}
    for m in re.finditer(r"^### +(.+?) *\n(.*?)(?=^### |\Z)", text or "", re.S | re.M):
        head, val = m.group(1).strip(), m.group(2).strip()
        if head not in out:
            out[head] = "" if val == "_No response_" else clean(val)
    return out


def detect(blocks: dict, spec: dict) -> str | None:
    best, score = None, 0.0
    for fn, fields in spec.items():
        s = sum(1 for f in fields if f["label"] in blocks) / len(fields)
        if s > score:
            best, score = fn, s
        elif s == score:
            best = None
    return best if score >= 0.6 else None


def code(value) -> str:
    v = re.sub(r"\s+", " ", clean(str(value)))
    return "`" + (v[:MAX_SHOWN] + ("…" if len(v) > MAX_SHOWN else "")) + "`" if v else "(empty)"


# ---------- checks ----------
class Report:
    def __init__(self):
        self.rows, self.failed, self.quote_found = [], False, False

    def ok(self, what: str, note: str = "ok"):
        self.rows.append((what, "pass", note))

    def warn(self, what: str, note: str):
        self.rows.append((what, "note", note))

    def fail(self, what: str, note: str):
        self.rows.append((what, "FAIL", note)); self.failed = True


def incident_ids() -> dict:
    return {f.stem: f for f in vi.incident_files()}


def find_step(ref: str):
    m = re.fullmatch(r"([a-z0-9][a-z0-9-]*)/(s\d{2,3})", ref or "")
    if not m or m.group(1) not in incident_ids():
        return None
    inc = c.load_yaml(incident_ids()[m.group(1)])
    return next((s for s in inc["steps"] if s["id"] == m.group(2)), None)


def check_label(r: Report, fw: dict, tactic: str, technique: str, what: str = "Tactic and technique") -> bool:
    if not re.fullmatch(r"TA\d{4}", tactic or ""):
        r.fail(what, f"{code(tactic)} is not a tactic ID (it should look like TA0007)")
        return False
    if technique and not re.fullmatch(r"T\d{4}(\.\d{3})?", technique):
        r.fail(what, f"{code(technique)} is not a technique ID (it should look like T1611 or T1048.003)")
        return False
    errs = vi._check_technique(fw, tactic, technique or None, "label")
    if errs:
        r.fail(what, "; ".join(e.split(": ", 1)[1] for e in errs))
        return False
    r.ok(what, f"{tactic}" + (f" with {technique}" if technique else ", no technique") + f" exist in ATT&CK v{fw['attack']['version']} and fit together")
    return True


def check_source(r: Report, source: str, fetch, quote: str | None = None, what: str = "Source") -> None:
    reg = vi.load_sources()
    src = reg.get(source)
    url = src["url"] if src else source
    why = ev.url_problem(url, resolve=lambda h: [])            # shape of the address only; the fetcher resolves and re-checks
    if why and not src:
        r.fail(what, f"{code(source)}: {why}. Give an https address on a public host, or the id of a registered source")
        return
    res = fetch(url)
    if res.get("status") != "ok":
        msg = FETCH_WORDS.get(res.get("status"), "the source could not be read").format(http_status=res.get("http_status", "?"), reason=res.get("reason", "not allowed"))
        r.fail(what, f"{code(source)}: {msg}")
        return
    r.ok(what, f"{code(source)} was read" + (" (a registered source)" if src else " (not yet in the source registry)"))
    if quote is None:
        return
    text = ev.clip(res["text"], src) if src else res["text"]
    q = ev.find_quote(quote, text, full_text=res.get("full_text"))
    if q["status"] == "found":
        r.quote_found = True
        r.ok("Quote is in the source", "found by string match" + (" (with an elision)" if q.get("elided") else ""))
        if not q.get("whole_sentence"):
            r.warn("Quote in context", "the quote is part of a longer sentence; a reviewer should read the whole sentence")
    elif q["status"] == "not_in_article":
        r.fail("Quote is in the source", "not found in the article text (the words appear only in page furniture such as menus or footers)")
    else:
        r.fail("Quote is in the source", "not found in the text of the cited source")


def required(r: Report, fields: list, vals: dict) -> bool:
    missing = [f["label"] for f in fields if f["required"] and not vals.get(f["id"])]
    for f in fields:
        if f["options"] and vals.get(f["id"]) and vals[f["id"]] not in f["options"]:
            r.fail("Form fields", f"{code(f['label'])} must be one of the listed choices")
            return False
    if missing:
        r.fail("Form fields", "a required field is empty: " + ", ".join(code(m) for m in missing))
        return False
    r.ok("Form fields", "all required fields are filled in")
    return True


def check_incident_step(r: Report, v: dict, fw: dict, fetch, number: int) -> dict | None:
    incs = incident_ids()
    if v["incident_id"] not in incs:
        r.fail("Incident", f"{code(v['incident_id'])} is not a listed incident id")
        return None
    r.ok("Incident", f"{code(v['incident_id'])} is listed")
    inc = c.load_yaml(incs[v["incident_id"]])
    ids = {s["id"] for s in inc["steps"]}
    correcting = v["change"].startswith("Correct")
    sid = v.get("step_id") or ""
    if correcting:
        if sid not in ids:
            r.fail("Step id", f"{code(sid)} is not a step of this incident; a correction must name an existing step")
        else:
            r.ok("Step id", f"{code(sid)} exists")
    elif sid and sid in ids:
        r.fail("Step id", f"{code(sid)} already exists in this incident; leave the step id empty for a new step")
    else:
        sid = f"s{max(int(x[1:]) for x in ids) + 1:02d}" if ids else "s01"
        r.ok("Step id", f"no collision; the next free id is {code(sid)}")
    nw, nq = len(v["what_happened"].split()), len(v["quote"].split())
    (r.ok if nw <= vi.MAX_WHAT else r.fail)("Description length", f"{nw} words (the limit is {vi.MAX_WHAT})")
    (r.ok if nq <= vi.MAX_QUOTE else r.fail)("Quote length", f"{nq} words (the limit is {vi.MAX_QUOTE})")
    label_ok = check_label(r, fw, v["tactic"], v.get("technique", ""))
    if nq <= vi.MAX_QUOTE:
        check_source(r, v["source"], fetch, quote=v["quote"])
    if r.failed or not label_ok or not r.quote_found:
        return None
    order = v.get("order", "")
    who = f"submission #{number} (not checked by a human)"
    registered = v["source"] in vi.load_sources()
    return dict(id=sid, order=int(order) if order.isdigit() else "SET BY MAINTAINER", order_basis="unordered" if order.lower() == "unordered" else "stated",
                time=None, time_source_local=None, time_conflict=None, time_precision="unknown", phase="attack", what_happened=v["what_happened"],
                evidence=dict(source=v["source"] if registered else "REGISTER THIS SOURCE FIRST: " + v["source"], quote=v["quote"], locator=v.get("locator") or "SET BY MAINTAINER"),
                attack=dict(primary_tactic=v["tactic"], technique=v.get("technique") or None, confidence="clear", rationale=v["rationale"]),
                label_status="draft_needs_human_review", labeled_by=who, reviewed_by=None,
                history=[dict(date="SET BY MAINTAINER", who=who, change="initial draft from a public submission", reason="see the issue")])


def check_dispute(r: Report, v: dict, fw: dict) -> None:
    step = find_step(v["step_id"])
    (r.ok if step else r.fail)("Step", f"{code(v['step_id'])} " + ("exists" if step else "is not an existing step (use the form incident-id/s00)"))
    check_label(r, fw, v["proposed_tactic"], v.get("proposed_technique", ""), "Proposed label")
    if re.search(r"\bS[1-7]\b", v["rule"]):
        r.ok("Codebook rule", f"cites {code(v['rule'])}")
    else:
        r.fail("Codebook rule", "name the step rule that supports your label: S1 to S7")


def check_review(r: Report, v: dict, fw: dict) -> None:
    step = find_step(v["step_id"])
    (r.ok if step else r.fail)("Step", f"{code(v['step_id'])} " + ("exists" if step else "is not an existing step (use the form incident-id/s00)"))
    if v.get("own_tactic") or v.get("own_technique"):
        check_label(r, fw, v.get("own_tactic", ""), v.get("own_technique", ""), "Your own label")
    r.warn("Status", "this review does not change the step's status. Only a named human reviewer may do that, through a pull request")


def check_new_incident(r: Report, v: dict, fetch) -> None:
    n = len(v["summary"].split())
    (r.ok if n <= vi.MAX_SUMMARY else r.fail)("Summary length", f"{n} words (the limit is {vi.MAX_SUMMARY})")
    urls = [x.strip() for x in v["sources"].splitlines() if x.strip()]
    if not urls:
        r.fail("Sources", "give at least one https address")
    for i, u in enumerate(urls[:MAX_SOURCES], 1):
        check_source(r, u, fetch, what=f"Source {i}")
    if len(urls) > MAX_SOURCES:
        r.warn("Sources", f"only the first {MAX_SOURCES} sources were checked")


def check(event: dict, fetch=default_fetch) -> dict:
    """Check the issue in a GitHub `issues` event. Returns passed, label, template and the comment text."""
    issue = event.get("issue") or {}
    number = int(issue.get("number") or 0)
    text = issue.get("body") or ""
    r, template, snippet = Report(), None, None
    if len(text.encode("utf-8", "ignore")) > MAX_BODY:
        r.fail("Size", f"the issue text is too long to check (over {MAX_BODY // 1000} KB). Please shorten it")
    else:
        spec = load_forms()
        blocks = parse_body(text)
        template = detect(blocks, spec)
        if not template:
            r.fail("Form", "this issue was not opened with one of the ACTCM forms, so there is nothing to check. Please use a form from the Contribute page")
        else:
            fields = spec[template]
            vals = {f["id"]: blocks.get(f["label"], "") for f in fields}          # only the form's own fields are read
            if required(r, fields, vals):
                fw = fwm.load()
                if template == "incident-step.yml":
                    snippet = check_incident_step(r, vals, fw, fetch, number)
                elif template == "step-dispute.yml":
                    check_dispute(r, vals, fw)
                elif template == "step-review.yml":
                    check_review(r, vals, fw)
                else:
                    check_new_incident(r, vals, fetch)
    passed = not r.failed
    label = "needs-fix" if not passed else "evidence-checked" if r.quote_found and template == "incident-step.yml" else "format-checked"
    return dict(passed=passed, label=label, template=template, comment=render(r, passed, label, snippet))


def render(r: Report, passed: bool, label: str, snippet: dict | None) -> str:
    head = {"evidence-checked": "The script found the quoted words in the cited source, and the IDs and limits are in order.",
            "format-checked": "The form is complete and the IDs and addresses are in order.",
            "needs-fix": "Something needs fixing before a maintainer can use this. Edit the issue and the check runs again."}[label]
    lines = [MARKER, f"**Automatic check: {'passed' if passed else 'needs a fix'}.** {head}", "",
             "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c_.replace('|', '/')} |" for a, b, c_ in r.rows]
    lines += ["", "This check is a script. It matches text and looks up IDs. It does not judge whether the label is right, "
                  "it does not approve anything, and it never changes the data. A human maintainer decides and applies accepted changes through a pull request."]
    if snippet:
        body = yaml.safe_dump(snippet, sort_keys=False, allow_unicode=True, width=100).strip()
        lines += ["", "For the maintainer, a draft step to paste into the incident file (status: draft, no human check):", "", "```yaml", body, "```"]
    return "\n".join(lines)


# ---------- posting (only with --post) ----------
def _api(method: str, path: str, token: str, payload: dict | None = None):
    req = urllib.request.Request("https://api.github.com" + path, method=method, data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "actcm-submission-check",
                                          "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        if method == "DELETE" and e.code == 404:
            return None
        raise


def post(event: dict, result: dict, token: str) -> None:
    repo = event["repository"]["full_name"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("unexpected repository name")
    n = int(event["issue"]["number"])
    base = f"/repos/{repo}/issues/{n}"
    mine = [x for x in _api("GET", base + "/comments?per_page=100", token) or [] if MARKER in (x.get("body") or "") and (x.get("user") or {}).get("type") == "Bot"]
    if mine:
        _api("PATCH", f"/repos/{repo}/issues/comments/{int(mine[0]['id'])}", token, {"body": result["comment"]})
    else:
        _api("POST", base + "/comments", token, {"body": result["comment"]})
    for other in LABELS:
        if other != result["label"]:
            _api("DELETE", base + "/labels/" + other, token)
    _api("POST", base + "/labels", token, {"labels": [result["label"]]})


def main(argv: list[str]) -> int:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path:
        print("GITHUB_EVENT_PATH is not set: this script reads the issue from the GitHub Actions event file")
        return 2
    event = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    result = check(event, fetch=default_fetch)
    print("label:", result["label"])
    print(result["comment"])
    if "--post" in argv:
        post(event, result, os.environ["GITHUB_TOKEN"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
