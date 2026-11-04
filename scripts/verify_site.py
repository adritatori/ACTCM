#!/usr/bin/env python3
"""Check a running copy of the site (live or local). Standard library only, so it runs anywhere.

  python3 scripts/verify_site.py https://adritatori.github.io/ACTCM/
  python3 scripts/verify_site.py http://localhost:8000/

Checks: the three pages load; the draft warning, the one-line "extras not included" note and the footer lines are present;
the data files parse and agree with each other; the CSV and JSON downloads work; the four Navigator layer files are valid JSON;
the page scripts and styles load; nothing from a hidden setting is served. Exit code 1 if any check fails.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.error
import urllib.request

MITRE_LINE = "© 2026 The MITRE Corporation. This work is reproduced and distributed with the permission of The MITRE Corporation."
results: list[tuple[bool, str]] = []


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "actcm-verify-site"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:      # noqa: BLE001
        return 0, str(e).encode()


def check(ok: bool, what: str) -> None:
    results.append((bool(ok), what))
    print(("PASS  " if ok else "FAIL  ") + what)


def text_of(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&amp;", "&").replace("&ldquo;", "“").replace("&rdquo;", "”")
    return re.sub(r"\s+([,.;:])", r"\1", t)        # tags such as <em> leave a space before punctuation


def main(base: str) -> int:
    base = base.rstrip("/") + "/"
    pages = {"Explorer (home)": "index.html", "Guide": "guide.html", "Verify": "verify.html"}
    texts = {}
    for name, p in pages.items():
        code, body = get(base + p)
        check(code == 200 and len(body) > 2000, f"{name} loads ({p}): HTTP {code}, {len(body)} bytes")
        texts[p] = text_of(body.decode("utf-8", "ignore"))
        raw = body.decode("utf-8", "ignore")
        check("PROVISIONAL RESULTS" in texts[p] and "No human has reviewed any label yet." in texts[p], f"{name}: draft warning visible")
        check("Not affiliated with or endorsed by The MITRE Corporation." in texts[p] and MITRE_LINE in texts[p], f"{name}: MITRE lines in the footer")
        check("A task count shows what is tested, not what is caught." in texts[p], f"{name}: \"tested, not caught\" line")
    idx = texts["index.html"]
    check("not included in v0.1, pending permission" in idx and "LinuxArena extras" in idx, "Explorer: one-line note that LinuxArena extras is not included in v0.1")
    check("MITRE ATT&CK® matrix" in idx, "Explorer: heading says MITRE ATT&CK®")
    for asset in ("assets/app.js", "assets/style.css", "assets/img/explorer-1280-light.png", "assets/img/explorer-400-light.png"):
        code, body = get(base + asset)
        check(code == 200 and len(body) > 500, f"asset loads: {asset}")
    code, body = get(base + "data/counts.json")
    counts = json.loads(body) if code == 200 else {}
    check(code == 200 and counts.get("totals", {}).get("tasks"), f"data/counts.json loads: {counts.get('totals', {}).get('tasks')} tasks")
    n = counts.get("totals", {}).get("tasks")
    settings = [s["id"] for s in counts.get("settings", [])]
    check("linuxarena-extras" not in settings and not counts.get("totals", {}).get("by_setting", {}).get("linuxarena-extras"), f"counts.json lists settings {settings} (extras not among them)")
    code, body = get(base + "data/tasks.csv")
    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8", "ignore")))) if code == 200 else []
    check(code == 200 and len(rows) == n, f"CSV download works: {len(rows)} rows (counts.json says {n})")
    code, body = get(base + "data/tasks.json")
    tj = json.loads(body) if code == 200 else []
    check(code == 200 and len(tj) == n, f"JSON download works: {len(tj)} tasks")
    check(not any(r.get("setting") == "linuxarena-extras" for r in rows) and not any(t.get("setting") == "linuxarena-extras" for t in tj), "no task of a hidden setting in the CSV or JSON")
    for key in ["combined"] + settings:
        code, body = get(base + f"data/navigator/actcm_{key}_attack_v20.json")
        ok = False
        if code == 200:
            layer = json.loads(body)
            ok = layer.get("domain") == "enterprise-attack" and layer.get("versions", {}).get("layer") == "4.5" and len(layer.get("techniques", [])) > 100
        check(ok, f"Navigator layer loads and is a v4.5 layer: {key}")
    code, body = get(base + "data/status_tiers.json")
    check(code == 200 and "No human has checked it" in body.decode("utf-8", "ignore"), "status wording file loads and says no human has checked AI cross-checked labels")
    failed = [w for ok, w in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed" + ("" if not failed else f"; FAILED: {len(failed)}"))
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
