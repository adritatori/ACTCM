#!/usr/bin/env python3
"""Check every external link on the site. Writes docs/LINK_CHECK.md.

Status per link: 200 = reachable now; PENDING = a repo link, marked 'works after publishing' on the page;
UNVERIFIED = the host did not answer from this session, so nothing can be said about the link.
"""
import re
import subprocess
import sys
import urllib.parse
from html.parser import HTMLParser

import common as c

SITE = c.ROOT / "site"
PAGES = ["index.html", "guide.html", "verify.html"]


class H(HTMLParser):
    def __init__(self):
        super().__init__(); self.h = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href", "").startswith("http"):
            self.h.append(a["href"])


def status(url: str) -> str:
    r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-L", "-m", "20", "-w", "%{http_code}", "-A", "ACTCM-link-check", url],
                       capture_output=True, text=True)
    return r.stdout.strip() or "000"


def live() -> int:
    """After publishing: the repository links and the five Navigator layer files must answer, and each layer must be valid JSON."""
    import datetime
    import json
    import urllib.request
    report = []
    links = json.loads((c.DATA / "generated" / "navigator" / "links.json").read_text())
    bad = 0
    for l in links:
        raw = urllib.parse.unquote(l["open_in_navigator"].split("#layerURL=")[1])
        try:
            with urllib.request.urlopen(raw, timeout=30) as r:
                layer = json.loads(r.read())
            ok = r.status == 200 and layer.get("domain") == "enterprise-attack"
        except Exception as e:      # noqa: BLE001
            ok, layer = False, {}
            print("  error:", raw, e)
        bad += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {l['layer']:18} {raw}")
        report.append(f"| Navigator layer `{l['layer']}` | {raw} | {'200 OK, valid layer' if ok else 'FAILED'} |")
    repo = "https://github.com/" + c.config()["repository"]
    s = status(repo)
    print(f"{'OK  ' if s == '200' else 'FAIL'} repository {repo} -> {s}")
    bad += s != "200"
    report.append(f"| Repository | {repo} | {s} |")
    doc = c.ROOT / "docs" / "LINK_CHECK.md"
    text = doc.read_text(encoding="utf-8") if doc.exists() else "# Link check\n"
    text = re.sub(r"\n## Live check.*\Z", "", text, flags=re.S).rstrip("\n")
    text += ("\n\n## Live check (`make links-live`), " + datetime.date.today().isoformat() + "\n\n| What | URL | Result |\n|---|---|---|\n" + "\n".join(report) +
             "\n\nThe hosted ATT&CK Navigator app itself is not tested by this script: open each \"Open in Navigator\" link in a browser and check that the layer loads.\n")
    doc.write_text(text + "", encoding="utf-8")
    print("The Navigator app itself must still be opened by hand with each 'Open in Navigator' link and checked in a browser.")
    return 1 if bad else 0


def main() -> dict:
    where = {}
    for fn in PAGES:
        p = H(); p.feed((SITE / fn).read_text(encoding="utf-8"))
        for u in p.h:
            where.setdefault(u.split("#")[0], set()).add(fn)
    rows = []
    for u in sorted(where):
        s = status(u)
        repo = ("github.com/" + c.config()["repository"]) in u
        verdict = "PENDING (marked 'works after publishing' on the page)" if repo and not c.config().get("published") else ("200 OK" if s == "200" else
                  "UNVERIFIED (host did not answer from this session)" if s in ("000", "") else f"HTTP {s}: CHECK")
        rows.append((u, s, verdict, ", ".join(sorted(where[u]))))
    L = ["# Link check", "", "Run by `scripts/link_check.py` (`make links`). Repository links are tested for real. Links to other sites that did not answer from the build session are marked UNVERIFIED, not passed; run `make links` from a machine with open internet to check them.", "",
         "| URL | HTTP status | Verdict | Pages |", "|---|---|---|---|"]
    L += [f"| {u} | {s} | {v} | {w} |" for u, s, v, w in rows]
    ok = sum(1 for r in rows if r[2] == "200 OK"); pend = sum(1 for r in rows if r[2].startswith("PENDING"))
    unv = sum(1 for r in rows if r[2].startswith("UNVERIFIED")); bad = sum(1 for r in rows if "CHECK" in r[2])
    L += ["", f"{len(rows)} external links: {ok} return 200, {pend} pending publication, {unv} unverified (host unreachable from the session), {bad} need checking.", ""]
    (c.ROOT / "docs" / "LINK_CHECK.md").write_text("\n".join(L), encoding="utf-8")
    print(L[-2]); [print(" ", r[2][:12], r[0]) for r in rows]
    return dict(ok=ok, pending=pend, unverified=unv, bad=bad)


if __name__ == "__main__":
    if "--live" in sys.argv:
        sys.exit(live())
    main()
