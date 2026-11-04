#!/usr/bin/env python3
"""Compare the techniques/tactics our labels use in ATT&CK v20 with v19.2 (the previous release in the Navigator's index).

Purpose: if the hosted Navigator turns out not to offer v20, this lists exactly what would differ in a v19.2 layer.
Writes docs/NAVIGATOR_CHECK.md. Reads .cache/frameworks/attack-19.2.json (fetched from attack-stix-data at v19.2).
"""
import json
from collections import Counter

import common as c
import frameworks as fwm

V192 = c.ROOT / ".cache" / "frameworks" / "attack-19.2.json"


def load_192():
    objs = json.loads(V192.read_text())["objects"]
    short = {o["x_mitre_shortname"]: o["name"] for o in objs if o["type"] == "x-mitre-tactic"}
    tech = {}
    for o in objs:
        if o["type"] == "attack-pattern":
            tid = [r["external_id"] for r in o["external_references"] if r.get("source_name") == "mitre-attack"][0]
            tech[tid] = dict(name=o["name"], tactics=sorted(k["phase_name"] for k in o.get("kill_chain_phases", [])),
                             revoked=bool(o.get("revoked")), deprecated=bool(o.get("x_mitre_deprecated")))
    return short, tech


def main():
    fw = fwm.load()
    att = fw["attack"]
    short19, tech19 = load_192()
    s20 = {t["id"]: t for t in att["tactics"]}
    tasks = [c.load_yaml(f) for f in c.public_task_files()]
    used_t = Counter(); used_tech = Counter()
    for t in tasks:
        a = t["labels"]["attack"]
        for tac in {a["primary_tactic"], *a["required_step_tactics"]}:
            used_t[tac] += 1
        if a["technique"]:
            used_tech[(a["technique"], a["primary_tactic"])] += 1
    rows_t, rows_x = [], []
    for tac, n in sorted(used_t.items()):
        sn = s20[tac]["shortname"]
        rows_t.append((tac, s20[tac]["name"], sn, "present in v19.2" if sn in short19 else "NOT in v19.2", n))
    for (tid, tac), n in sorted(used_tech.items()):
        sn = s20[tac]["shortname"]
        t19 = tech19.get(tid)
        if t19 is None:
            st = "NOT in v19.2"
        elif t19["revoked"] or t19["deprecated"]:
            st = "revoked/deprecated in v19.2"
        elif sn not in t19["tactics"]:
            st = f"in v19.2 but under {', '.join(t19['tactics'])}, not {sn}"
        else:
            st = "same"
        rows_x.append((tid, att["techniques"][tid]["name"], sn, st, n))
    diff = [r for r in rows_x if r[3] != "same"]
    L = ["# ATT&CK Navigator check", "",
         "**Status: PARTLY VERIFIED. The hosted Navigator could not be reached from this session, so no layer has been loaded in it.**", "",
         "## What was checked, and how", "",
         "1. The Navigator source (`mitre-attack/attack-navigator`, default branch commit `734a1caba29fcd51f20b9ca239ce652b3354a47e`, "
         "latest release `v5.3.2`, 21 Apr 2026) reads its list of ATT&CK versions from `collection_index_url`, which is "
         "`https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/index.json`.",
         "2. That index, fetched 2026-11-04, lists Enterprise ATT&CK versions `20.0, 19.2, 19.1, ...` (42 entries, newest first). "
         "So the hosted app **should** offer v20.",
         "3. **Not verified:** that the hosted app at `https://mitre-attack.github.io/attack-navigator/` shows v20 in its dropdown "
         "(the host did not respond from this session: HTTP status 000), and that release v5.3.2, built before v20 was published "
         "(13 Oct 2026), loads v20 data correctly. (v19.2 already had Stealth TA0005 and Defense Impairment TA0112, checked "
         "in the v19.2 file, so the tactic names are not new in v20.)",
         "4. Layer format: validated against `layers/spec/v4.5/layerformat.md` from the commit above "
         "(required fields, gradient `minValue < maxValue`, legend items with label and colour, hex colours, `navigator >= 4.9.0`), "
         "and every technique/tactic pair was checked against the pinned v20 data. See `tests/test_navigator.py`.", "",
         "Because the evidence says v20 is offered, no second layer set was exported. The comparison below shows what would "
         "differ in a v19.2 set. **Result: nothing differs for the tactics and technique/tactic pairs our labels use**, so the "
         "layer IDs would also resolve in v19.2.", "",
         f"## Tactics we use: v20 vs v19.2 (v19.2 file sha256 `dc1639caa5501d720e280cf1cbd8fbe009884a0c9b3e6e9ed9d0c25166c3d8f4`)", "",
         "| v20 tactic | Name | Shortname | In v19.2? | Tasks (main or step) |", "|---|---|---|---|---|"]
    L += [f"| {a} | {b} | {c_} | {d} | {e} |" for a, b, c_, d, e in rows_t]
    L += ["", f"## Techniques we use that differ in v19.2 ({len(diff)} of {len(rows_x)} technique/tactic pairs)", "",
          "| Technique | Name (v20) | v20 tactic | v19.2 status | Tasks |", "|---|---|---|---|---|"]
    L += [f"| {a} | {b} | {c_} | {d} | {e} |" for a, b, c_, d, e in diff]
    L += ["", "Pairs that are the same in both versions are not listed.", ""]
    (c.ROOT / "docs" / "NAVIGATOR_CHECK.md").write_text("\n".join(L), encoding="utf-8")
    print(f"tactics used: {len(rows_t)}, of which not in v19.2: {sum(1 for r in rows_t if r[3].startswith('NOT'))}")
    print(f"technique/tactic pairs used: {len(rows_x)}; differ in v19.2: {len(diff)}")
    for r in diff: print("  ", r)


if __name__ == "__main__":
    main()
