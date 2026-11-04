#!/usr/bin/env python3
"""Phase 5: ATT&CK Navigator layers (layer format 4.5, domain enterprise-attack, ATT&CK v20).

One layer per setting and one combined. Score = number of tasks whose PRIMARY tactic and PRIMARY technique are that
pair (required steps carry no technique, so they are not in layers). Tasks with technique null cannot be placed on a
technique and are counted in the layer description. 0 = gap (untested), shown in light grey with the legend label.
Open-in-Navigator links use the documented #layerURL= parameter and only work after the repo is published.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from collections import defaultdict

import build as B
import common as c
import frameworks as fwm

OUT = c.DATA / "generated" / "navigator"
NAVIGATOR_VERSION = "5.3.2"        # newest release tag of mitre-attack/attack-navigator on 2026-11-04 (min required: 4.9.0)
LAYER_VERSION = "4.5"
REPO = c.config()["repository"]     # config/publish.yml; confirm before publishing
BRANCH = c.config().get("branch", "main")
NAV_BASE = "https://mitre-attack.github.io/attack-navigator/"
COLORS = {0: "#f2f2f2", 1: "#9ecae1", 2: "#4292c6", 5: "#08519c"}
LEGEND = [("0 tasks: gap (untested, not 'dangerous')", COLORS[0]), ("1 task", COLORS[1]), ("2 to 4 tasks", COLORS[2]),
          ("5 or more tasks", COLORS[5]), ("PROVISIONAL: draft labels, no human review yet", "#fff3b0")]
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def bucket_color(n: int) -> str:
    return COLORS[0] if n == 0 else COLORS[1] if n == 1 else COLORS[2] if n < 5 else COLORS[5]


def build_layer(tasks: list[dict], fw: dict, title: str, setting_note: str) -> dict:
    att = fw["attack"]
    short = {t["id"]: t["shortname"] for t in att["tactics"]}
    pair_tasks = defaultdict(list)
    null_n = 0
    for t in tasks:
        a = (t.get("labels") or {}).get("attack") or {}
        if not a.get("primary_tactic"):
            continue
        if a.get("technique"):
            pair_tasks[(a["technique"], a["primary_tactic"])].append(B.uid(t))
        else:
            null_n += 1
    active = {k: v for k, v in att["techniques"].items() if not v["revoked"] and not v["deprecated"]}
    parents_with_scored_sub = {k.split(".")[0] for (k, _tac) in pair_tasks if "." in k}
    techs = []
    for k in sorted(active):
        for tac in sorted(active[k]["tactics"], key=lambda x: short[x]):
            ids = pair_tasks.get((k, tac), [])
            e = dict(techniqueID=k, tactic=short[tac], score=len(ids), color=bucket_color(len(ids)), comment="", enabled=True)
            if ids:
                e["comment"] = f"{len(ids)} task(s): " + ", ".join(i.split("/", 2)[2] for i in sorted(ids))
            if k in parents_with_scored_sub and "." not in k:
                e["showSubtechniques"] = True
            techs.append(e)
    scored = sum(len(v) for v in pair_tasks.values())
    mx = max([len(v) for v in pair_tasks.values()] + [1])
    desc = (f"Side tasks in public AI control settings, mapped to MITRE ATT&CK® Enterprise v{att['version']}. {setting_note} "
            f"{len(tasks)} tasks; {scored} placed on a technique; {null_n} have no ATT&CK technique and are not shown here. "
            "A task count shows what is tested, not what is caught. A gap means untested, not dangerous and not undefended. "
            "PROVISIONAL: all labels are drafts and no human has reviewed them. "
            "Not affiliated with or endorsed by The MITRE Corporation.")
    return dict(
        name=title, versions=dict(attack=att["version"].split(".")[0], navigator=NAVIGATOR_VERSION, layer=LAYER_VERSION),
        domain="enterprise-attack", description=desc,
        sorting=3, layout=dict(layout="side", showID=True, showName=True, showAggregateScores=False,
                               countUnscored=False, aggregateFunction="sum", expandedSubtechniques="annotated"),
        hideDisabled=False, techniques=techs,
        gradient=dict(colors=[COLORS[0], COLORS[1], COLORS[5]], minValue=0, maxValue=mx if mx > 0 else 1),
        legendItems=[dict(label=l, color=col) for l, col in LEGEND],
        showTacticRowBackground=False, tacticRowBackground="#dddddd", selectTechniquesAcrossTactics=True,
        selectSubtechniquesWithParent=True, selectVisibleTechniques=False,
        metadata=[dict(name="Project", value="Agent Control Threat Coverage Matrix (ACTCM)"),
                  dict(name="Status", value="PROVISIONAL: draft labels"),
                  dict(name="Tasks", value=str(len(tasks))),
                  dict(name="ATT&CK version", value=att["version"]), dict(name="Codebook", value="1.1-draft")],
        links=[dict(label="ACTCM repository (private until published)", url=f"https://github.com/{REPO}")])


def validate_layer(L: dict, fw: dict | None = None) -> list[str]:
    """Check a layer against the format 4.5 rules in layers/spec/v4.5/layerformat.md. Returns error strings."""
    E = []
    def need(cond, msg):
        if not cond:
            E.append(msg)
    if not isinstance(L, dict):
        return ["layer is not an object"]
    need(isinstance(L.get("name"), str) and L["name"].strip(), "name is required")
    need(L.get("domain") in ("enterprise-attack", "mobile-attack", "ics-attack"), f"domain {L.get('domain')!r} invalid")
    v = L.get("versions")
    if v is not None:
        need(isinstance(v, dict), "versions must be an object")
        if isinstance(v, dict):
            need(v.get("layer") == "4.5", f"versions.layer must be '4.5', got {v.get('layer')!r}")
            nav = v.get("navigator")
            ok = isinstance(nav, str) and re.fullmatch(r"\d+\.\d+\.\d+", nav) and tuple(map(int, nav.split("."))) >= (4, 9, 0)
            need(ok, f"versions.navigator must be at least 4.9.0, got {nav!r}")
            need("attack" not in v or isinstance(v["attack"], str), "versions.attack must be a string")
    if "sorting" in L:
        need(L["sorting"] in (0, 1, 2, 3) and not isinstance(L["sorting"], bool), "sorting must be 0, 1, 2 or 3")
    lay = L.get("layout")
    need(lay is None or isinstance(lay, dict), "layout must be an object")
    if isinstance(lay, dict):
        need(lay.get("layout", "side") in ("side", "flat", "mini"), "layout.layout invalid")
        need(lay.get("aggregateFunction", "average") in ("average", "min", "max", "sum"), "layout.aggregateFunction invalid")
        need(lay.get("expandedSubtechniques", "none") in ("none", "all", "annotated"), "layout.expandedSubtechniques invalid")
    for flag in ("hideDisabled", "showTacticRowBackground", "selectTechniquesAcrossTactics",
                 "selectSubtechniquesWithParent", "selectVisibleTechniques"):
        need(flag not in L or isinstance(L[flag], bool), f"{flag} must be boolean")
    if "tacticRowBackground" in L:
        need(isinstance(L["tacticRowBackground"], str) and HEX.match(L["tacticRowBackground"]), "tacticRowBackground not #rrggbb")
    g = L.get("gradient")
    need(g is None or isinstance(g, dict), "gradient must be an object")
    if isinstance(g, dict):
        cols = g.get("colors")
        need(isinstance(cols, list) and len(cols) >= 2 and all(isinstance(x, str) and HEX.match(x) for x in cols),
             "gradient.colors needs at least 2 #rrggbb values")
        lo, hi = g.get("minValue"), g.get("maxValue")
        need(all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (lo, hi)), "gradient min/max must be numbers")
        if all(isinstance(x, (int, float)) for x in (lo, hi)):
            need(lo < hi, f"gradient maxValue ({hi}) must be greater than minValue ({lo})")
    for key in ("legendItems", "metadata", "links"):
        need(L.get(key) is None or isinstance(L.get(key), list), f"{key} must be a list")

    def items(key):
        v = L.get(key)
        return [x if isinstance(x, dict) else {} for x in v] if isinstance(v, list) else []
    for i, it in enumerate(items("legendItems")):
        need(isinstance(it, dict) and isinstance(it.get("label"), str) and it["label"].strip(), f"legendItems[{i}] needs a label")
        need(isinstance(it, dict) and isinstance(it.get("color"), str) and HEX.match(it.get("color", "")), f"legendItems[{i}] needs a #rrggbb color")
    for i, m in enumerate(items("metadata")):
        need(m.get("divider") is True or (isinstance(m.get("name"), str) and isinstance(m.get("value"), str)), f"metadata[{i}] needs string name and value")
    for i, k in enumerate(items("links")):
        need(k.get("divider") is True or (isinstance(k.get("label"), str) and isinstance(k.get("url"), str)
                                           and re.match(r"^[a-z][a-z0-9+.-]*://", k.get("url", ""))), f"links[{i}] needs label and a url with a protocol")
    techs = L.get("techniques")
    need(isinstance(techs, list) and techs, "techniques must be a non-empty list")
    seen = set()
    for i, t in enumerate(techs if isinstance(techs, list) else []):
        if not isinstance(t, dict):
            E.append(f"techniques[{i}]: not an object"); continue
        tid = t.get("techniqueID")
        if not (isinstance(tid, str) and re.fullmatch(r"T\d{4}(\.\d{3})?", tid)):
            E.append(f"techniques[{i}]: techniqueID {tid!r} invalid"); continue
        if "score" in t:
            need(isinstance(t["score"], (int, float)) and not isinstance(t["score"], bool), f"{tid}: score must be a number")
        if "color" in t:
            need(t["color"] == "" or HEX.match(str(t["color"])), f"{tid}: color {t['color']!r} not #rrggbb")
        need(isinstance(t.get("enabled", True), bool), f"{tid}: enabled must be boolean")
        need(isinstance(t.get("comment", ""), str), f"{tid}: comment must be a string")
        key = (tid, t.get("tactic"))
        need(key not in seen, f"{tid}/{t.get('tactic')}: duplicate entry")
        seen.add(key)
        if fw is not None:
            info = fw["attack"]["techniques"].get(tid)
            if info is None or info["revoked"] or info["deprecated"]:
                E.append(f"{tid}: not an active technique in ATT&CK v{fw['attack']['version']}")
            elif t.get("tactic") is not None:
                short = {x["shortname"]: x["id"] for x in fw["attack"]["tactics"]}
                if short.get(t["tactic"]) not in info["tactics"]:
                    E.append(f"{tid}: tactic {t['tactic']!r} is not one of its v{fw['attack']['version']} tactics")
    return E


def nav_link(filename: str) -> str:
    raw = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/data/generated/navigator/{filename}"
    return NAV_BASE + "#layerURL=" + urllib.parse.quote(raw, safe="")


def main() -> dict:
    fw = fwm.load()
    tasks = [c.load_yaml(f) for f in c.public_task_files()]
    tasks.sort(key=lambda t: (B.SETTINGS.index(t["setting"]), t["environment"], t["id"]))
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    links, report = [], {}
    sets = [("combined", tasks, "All settings in this release: " + ", ".join(B.SETTING_NAMES[x] for x in B.SETTINGS) + ".")] + [
        (s, [t for t in tasks if t["setting"] == s], f"Setting: {B.SETTING_NAMES[s]}.") for s in B.SETTINGS]
    for key, ts, note in sets:
        fname = f"actcm_{key}_attack_v{fw['attack']['version'].split('.')[0]}.json"
        layer = build_layer(ts, fw, f"ACTCM {key} (PROVISIONAL)", note)
        errs = validate_layer(layer, fw)
        scored = sum(t["score"] for t in layer["techniques"])
        (OUT / fname).write_text(json.dumps(layer, indent=1) + "\n", encoding="utf-8")
        report[key] = dict(file=fname, tasks=len(ts), entries=len(layer["techniques"]), score_sum=scored, errors=errs)
        links.append(dict(layer=key, file=fname, open_in_navigator=nav_link(fname),
                          status=("layer file is loaded from this repository" if c.config().get("published") else "works only after the repository is published")))
    (OUT / "links.json").write_text(json.dumps(links, indent=1) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    r = main()
    for k, v in r.items():
        print(f"{k:18} {v['file']:42} tasks {v['tasks']:>3} entries {v['entries']:>4} placed-on-technique {v['score_sum']:>3} errors {len(v['errors'])}")
        for e in v["errors"][:5]:
            print("   ", e)
