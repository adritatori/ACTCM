#!/usr/bin/env python3
"""Phase 2: pin ATT&CK Enterprise v20 and ATLAS 2026.10, and build lookup tables.

  frameworks.py fetch   Fetch both files at pinned commits, record SHA-256 in the lock file.
  frameworks.py build   Write data/generated/frameworks.json and print the tactic lists.
  frameworks.py all     fetch + build.

The source files are large and are NOT committed. They are re-fetched at a pinned commit and
their SHA-256 is compared with the lock file, so any change is caught.
"""
from __future__ import annotations

import hashlib
import json
import sys

import yaml

import common as c

FW_CACHE = c.ROOT / ".cache" / "frameworks"
OUT = c.DATA / "generated" / "frameworks.json"
ATTACK = dict(
    name="MITRE ATT&CK Enterprise", version="20.0", repo="mitre-attack/attack-stix-data", tag="v20.0",
    path="enterprise-attack/enterprise-attack-20.0.json",
    terms_of_use="https://attack.mitre.org/resources/legal-and-branding/terms-of-use/",
    licence_file="LICENSE.txt")
ATLAS = dict(
    name="MITRE ATLAS", version="2026.10", repo="mitre-atlas/atlas-data", tag="v6.1.0",
    path="dist/v6/ATLAS-2026.10.yaml", licence="Apache-2.0", licence_file="LICENSE")


def _fetch(spec: dict) -> dict:
    sha = c.resolve_tag(spec["repo"], spec["tag"])
    d = FW_CACHE / spec["repo"].split("/")[1]
    d.mkdir(parents=True, exist_ok=True)
    if not (d / ".git").exists():
        c.git("init", "-q", cwd=d)
        c.git("remote", "add", "origin", f"{c.GITHUB}/{spec['repo']}", cwd=d)
    c.git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", sha, cwd=d)
    if c.git("rev-parse", "FETCH_HEAD", cwd=d).strip() != sha:
        raise RuntimeError(f"{spec['repo']}: fetched commit differs from {sha}")
    data = c.show(d, sha, spec["path"])
    if data is None:
        raise RuntimeError(f"{spec['path']} not found at {sha}")
    raw = data.encode("utf-8")
    out = dict(spec, sha=sha, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    out["licence_text_first_line"] = (c.show(d, sha, spec["licence_file"]) or "").strip().splitlines()[0]
    (FW_CACHE / spec["path"].split("/")[-1]).write_bytes(raw)
    return out


def cmd_fetch() -> None:
    lock = c.load_yaml(c.LOCK_FILE)
    lock["frameworks"] = dict(attack=_fetch(ATTACK), atlas=_fetch(ATLAS))
    c.dump_yaml(lock, c.LOCK_FILE)
    for k, v in lock["frameworks"].items():
        print(f"{k}: {v['version']} {v['repo']}@{v['sha'][:10]} sha256={v['sha256']}")


def _load_verified(key: str, spec: dict):
    lock = c.load_yaml(c.LOCK_FILE)["frameworks"][key]
    f = FW_CACHE / spec["path"].split("/")[-1]
    raw = f.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != lock["sha256"]:
        raise RuntimeError(f"{key}: checksum mismatch: {got} != {lock['sha256']}")
    return raw


def _ext_id(o: dict) -> str | None:
    for r in o.get("external_references", []):
        if r.get("source_name") == "mitre-attack":
            return r.get("external_id")
    return None


def build_attack(raw: bytes) -> dict:
    objs = json.loads(raw)["objects"]
    coll = next(o for o in objs if o["type"] == "x-mitre-collection")
    tac = {o["id"]: o for o in objs if o["type"] == "x-mitre-tactic"}
    matrix = next(o for o in objs if o["type"] == "x-mitre-matrix")
    tactics = []
    short_to_id = {}
    for ref in matrix["tactic_refs"]:
        o = tac[ref]
        tactics.append(dict(id=_ext_id(o), name=o["name"], shortname=o["x_mitre_shortname"]))
        short_to_id[o["x_mitre_shortname"]] = _ext_id(o)
    techs = {}
    for o in objs:
        if o["type"] != "attack-pattern":
            continue
        tid = _ext_id(o)
        techs[tid] = dict(
            name=o["name"],
            tactics=sorted(short_to_id[k["phase_name"]] for k in o.get("kill_chain_phases", [])
                           if k["phase_name"] in short_to_id),
            is_subtechnique=bool(o.get("x_mitre_is_subtechnique")),
            deprecated=bool(o.get("x_mitre_deprecated")),
            revoked=bool(o.get("revoked")))
    return dict(version=coll["x_mitre_version"], tactics=tactics, techniques=dict(sorted(techs.items())))


def build_atlas(raw: bytes) -> dict:
    d = yaml.safe_load(raw)
    rel = d["relationships"]
    order = sorted((r["position"], r["target"]) for r in rel["ATLAS-matrix"]["sequences"])
    tactics = [dict(id=t, name=d["tactics"][t]["name"]) for _, t in order]
    techs = {}
    for tid, o in d["techniques"].items():
        own = sorted(r["target"] for r in rel.get(tid, {}).get("achieves", []))
        parent = next((r["target"] for r in rel.get(tid, {}).get("specializes", [])), None)
        techs[tid] = dict(name=o["name"], tactics=own, parent=parent, is_subtechnique=parent is not None,
                          maturity=o.get("maturity"), attack_reference=(o.get("attack-reference") or {}).get("id"))
    for t in techs.values():  # a sub-technique inherits its parent's tactics when it lists none
        if not t["tactics"] and t["parent"]:
            t["tactics"] = techs[t["parent"]]["tactics"]
            t["tactics_inherited"] = True
    return dict(version=d["collection"]["version"], format_version=d["format-version"],
                tactics=tactics, techniques=dict(sorted(techs.items())))


def cmd_build() -> dict:
    out = dict(attack=build_attack(_load_verified("attack", ATTACK)),
               atlas=build_atlas(_load_verified("atlas", ATLAS)))
    OUT.write_text(json.dumps(out, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    return out


def load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def check_techniques(fw: dict, framework: str, ids, strict_tactic: dict | None = None) -> list[str]:
    """Return a list of errors for technique IDs that are missing, revoked or deprecated."""
    errs = []
    techs = fw[framework]["techniques"]
    for i in ids:
        t = techs.get(i)
        if t is None:
            errs.append(f"{i}: not in {framework} {fw[framework]['version']}")
        elif t.get("revoked"):
            errs.append(f"{i}: revoked")
        elif t.get("deprecated"):
            errs.append(f"{i}: deprecated")
    return errs


def report(fw: dict) -> None:
    a, l = fw["attack"], fw["atlas"]
    print(f"\nATT&CK Enterprise v{a['version']}: {len(a['tactics'])} tactics, "
          f"{sum(1 for t in a['techniques'].values() if not t['is_subtechnique'])} techniques, "
          f"{sum(1 for t in a['techniques'].values() if t['is_subtechnique'])} sub-techniques "
          f"({sum(t['revoked'] for t in a['techniques'].values())} revoked, "
          f"{sum(t['deprecated'] for t in a['techniques'].values())} deprecated)")
    for i, t in enumerate(a["tactics"], 1):
        n = sum(1 for x in a["techniques"].values() if t["id"] in x["tactics"] and not x["revoked"] and not x["deprecated"])
        print(f"  {i:2}. {t['id']}  {t['name']:22} ({t['shortname']}) active techniques+subs: {n}")
    names = {t["name"] for t in a["tactics"]}
    ids = {t["id"]: t["name"] for t in a["tactics"]}
    print("  Stealth TA0005:", ids.get("TA0005") == "Stealth", "| Defense Impairment TA0112:",
          ids.get("TA0112") == "Defense Impairment", "| 'Defense Evasion' present:", "Defense Evasion" in names)
    ts = l["techniques"]
    print(f"\nATLAS {l['version']} (format {l['format_version']}): {len(l['tactics'])} tactics, "
          f"{sum(1 for t in ts.values() if not t['is_subtechnique'])} techniques + "
          f"{sum(1 for t in ts.values() if t['is_subtechnique'])} sub-techniques = {len(ts)} entries")
    for i, t in enumerate(l["tactics"], 1):
        n = sum(1 for x in ts.values() if t["id"] in x["tactics"])
        print(f"  {i:2}. {t['id']}  {t['name']:22} entries: {n}")
    print("  ATLAS entries with no tactic:", [k for k, v in ts.items() if not v["tactics"]] or "none")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("fetch", "all"):
        cmd_fetch()
    if cmd in ("build", "all"):
        report(cmd_build())
    if cmd not in ("fetch", "build", "all"):
        sys.exit(__doc__)
