#!/usr/bin/env python3
"""Validate incident files (data/incidents/*.yml) and the source registry (data/incidents/_sources.yml).

Checks: JSON Schema; tactic and technique IDs against the pinned ATT&CK version (exists, not deprecated or
revoked, technique sits in the tactic given); word limits (quote 25, what_happened 40, summary 60); every cited
source is registered; step tiers and who may set them; UTC times and local-time conversion; no placeholder left.
Exit code 1 on any error. Warnings never fail the build.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta

import jsonschema

import common as c
import frameworks as fwm
import labels as L

INCIDENTS_DIR = c.DATA / "incidents"
SOURCES_FILE = INCIDENTS_DIR / "_sources.yml"
SCHEMA = json.loads((c.ROOT / "schema" / "incident.schema.json").read_text(encoding="utf-8"))
MAX_QUOTE, MAX_WHAT, MAX_SUMMARY = 25, 40, 60
SOURCE_REQUIRED = ["id", "url", "title", "publisher", "published", "accessed", "content_sha256", "read_extent"]
SOURCE_OPTIONAL = ["archive_url", "read_note", "supersedes", "superseded_by", "fetch_note", "media_type", "text_starts_at", "text_ends_before"]
ZONES = {"UTC": 0, "GMT": 0, "Z": 0, "BST": 1, "CET": 1, "CEST": 2, "EST": -5, "EDT": -4, "PST": -8, "PDT": -7}
_LOCAL = re.compile(r"(\d{1,2}):(\d{2})\s*(UTC\s*[+-]\s*\d{1,2}|[A-Z]{1,4})\b")
_PLACEHOLDER = re.compile(r"<[^<>\n]{1,60}>")
_TIMEISH = re.compile(r"\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2}")


def incident_files() -> list:
    return sorted(f for f in INCIDENTS_DIR.glob("*.yml") if not f.name.startswith("_"))


def load_sources() -> dict:
    return {s["id"]: s for s in (c.load_yaml(SOURCES_FILE) or {}).get("sources") or []}


def local_to_utc(local_date: str, local: str) -> str | None:
    """'2026-07-28', '12:23 BST' -> '2026-07-28T11:23Z'. None if the text has no clock time with a known zone."""
    m = _LOCAL.search(local or "")
    if not m:
        return None
    zone = m.group(3).replace(" ", "")
    if zone.startswith("UTC") and len(zone) > 3:
        off = int(zone[3:])
    elif zone in ZONES:
        off = ZONES[zone]
    else:
        return None
    t = datetime.strptime(local_date, "%Y-%m-%d") + timedelta(hours=int(m.group(1)), minutes=int(m.group(2))) - timedelta(hours=off)
    return t.strftime("%Y-%m-%dT%H:%MZ")


def validate_sources(sources: list) -> list[str]:
    errs, ids = [], set()
    for s in sources or []:
        sid = s.get("id", "?")
        for k in SOURCE_REQUIRED:
            if k not in s:
                errs.append(f"source {sid}: missing {k}")
        for k in s:
            if k not in SOURCE_REQUIRED + SOURCE_OPTIONAL:
                errs.append(f"source {sid}: unknown key {k!r} (no source text is stored in the registry)")
        if sid in ids:
            errs.append(f"source {sid}: duplicate id")
        ids.add(sid)
        for k in ("url", "archive_url"):
            if s.get(k) and not str(s[k]).startswith("https://"):
                errs.append(f"source {sid}: {k} must be https")
        if s.get("read_extent") not in ("full", "partial"):
            errs.append(f"source {sid}: read_extent must be full or partial")
        if s.get("read_extent") == "partial" and not s.get("read_note"):
            errs.append(f"source {sid}: read_extent partial needs a read_note saying what was read")
        h = s.get("content_sha256")
        if h is not None and not re.fullmatch(r"[0-9a-f]{64}", str(h)):
            errs.append(f"source {sid}: content_sha256 must be 64 hex characters or null")
    for s in sources or []:
        for k in ("supersedes", "superseded_by"):
            if s.get(k) and s[k] not in ids:
                errs.append(f"source {s.get('id')}: {k} points to unknown source {s[k]!r}")
    return errs


def _strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k != "quote":
                yield from _strings(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}/{i}")
    elif isinstance(obj, str):
        yield path, obj


def _check_technique(fw: dict, tactic: str, tech: str | None, where: str) -> list[str]:
    att = fw["attack"]
    errs = []
    if tactic not in {t["id"] for t in att["tactics"]}:
        return [f"{where}: tactic {tactic} is not in ATT&CK v{att['version']}"]
    if tech is None:
        return errs
    rec = att["techniques"].get(tech)
    if rec is None:
        errs.append(f"{where}: technique {tech} is not in ATT&CK v{att['version']}")
    elif rec.get("deprecated") or rec.get("revoked"):
        errs.append(f"{where}: technique {tech} is deprecated or revoked in ATT&CK v{att['version']}")
    elif tactic not in rec["tactics"]:
        errs.append(f"{where}: technique {tech} sits in {rec['tactics']}, not in {tactic}")
    return errs


def validate_incident(inc: dict, sources: dict, fw: dict) -> tuple[list[str], list[str]]:
    if not isinstance(inc, dict):
        return ["not a mapping"], []
    iid = inc.get("id", "?")
    errs, warns = [], []
    v = jsonschema.Draft202012Validator(SCHEMA)
    for e in sorted(v.iter_errors(inc), key=lambda e: list(map(str, e.path))):
        errs.append(f"{iid}: schema: {'/'.join(map(str, e.path)) or '(root)'}: {e.message[:140]}")
    if errs:
        return errs, warns
    for path, s in _strings(inc):
        if _PLACEHOLDER.search(s):
            errs.append(f"{iid}: placeholder left in {path}: {s[:40]!r}")
    if len(inc["summary"].split()) > MAX_SUMMARY:
        errs.append(f"{iid}: summary has {len(inc['summary'].split())} words (max {MAX_SUMMARY})")
    sw = inc["swarms_wiki"]
    if bool(sw["id"]) != bool(sw["url"]):
        errs.append(f"{iid}: swarms_wiki needs both id and url, or neither")
    for sid in inc["sources_used"]:
        if sid not in sources:
            errs.append(f"{iid}: sources_used names unknown source {sid!r}")
    for cl in inc["agent_count_claims"]:
        if cl["source"] not in sources:
            errs.append(f"{iid}: agent_count_claims names unknown source {cl['source']!r}")
    seen_ids, seen_orders = set(), {}
    for s in inc["steps"]:
        w = f"{iid}/{s['id']}"
        if s["id"] in seen_ids:
            errs.append(f"{w}: duplicate step id")
        seen_ids.add(s["id"])
        if s["order"] in seen_orders:
            errs.append(f"{w}: order {s['order']} is also used by {seen_orders[s['order']]}")
        seen_orders[s["order"]] = s["id"]
        ev = s["evidence"]
        if ev["source"] not in sources:
            errs.append(f"{w}: evidence source {ev['source']!r} is not in the registry")
        elif ev["source"] not in inc["sources_used"]:
            errs.append(f"{w}: evidence source {ev['source']!r} is not listed in sources_used")
        nq = len(ev["quote"].split())
        if nq > MAX_QUOTE:
            errs.append(f"{w}: quote has {nq} words (max {MAX_QUOTE})")
        if len(s["what_happened"].split()) > MAX_WHAT:
            errs.append(f"{w}: what_happened has {len(s['what_happened'].split())} words (max {MAX_WHAT})")
        # status tiers
        st = s["label_status"]
        if st not in L.STEP_TIERS:
            errs.append(f"{w}: {st!r} is not a step tier (allowed: {', '.join(L.STEP_TIERS)})")
        if st in L.HUMAN_ONLY:
            who = s["reviewed_by"]
            if not who:
                errs.append(f"{w}: status {st} needs reviewed_by (a named human)")
            elif L.looks_like_bot(who) or who not in L.HUMAN_REVIEWERS:
                errs.append(f"{w}: reviewed_by {who!r} is not a listed human reviewer")
        elif s["reviewed_by"] is not None:
            errs.append(f"{w}: reviewed_by is set but the status is {st}")
        if st == "evidence_checked":
            if not any("-> evidence_checked" in h["change"] and "script" in h["who"].lower() for h in s["history"]):
                errs.append(f"{w}: evidence_checked may be set by a script only (no script entry in history)")
            if nq == 0:
                errs.append(f"{w}: evidence_checked with an empty quote")
        elif nq == 0:
            warns.append(f"{w}: empty quote (the step stays a draft)")
        for h in s["history"]:
            if L.looks_like_bot(h["who"]) and any(x in h["change"] for x in ("-> reviewed", "-> adjudicated")):
                errs.append(f"{w}: history shows {h['who']!r} setting a status only a named human may set")
        # phase and label
        a = s.get("attack")
        if s["phase"] == "attack":
            if not a:
                errs.append(f"{w}: phase attack needs an attack label")
        elif a:
            errs.append(f"{w}: a {s['phase']} step must not carry an attack label (codebook S6)")
        if a:
            errs += _check_technique(fw, a["primary_tactic"], a["technique"], w)
            alt = a.get("alternative")
            if a["confidence"] == "ambiguous" and not alt:
                errs.append(f"{w}: ambiguous needs an alternative (codebook S4)")
            if alt:
                errs += _check_technique(fw, alt["tactic"], alt.get("technique"), w + " alternative")
                if alt["tactic"] == a["primary_tactic"]:
                    warns.append(f"{w}: alternative has the same tactic as the primary label")
        # times
        t, loc = s["time"], s.get("time_source_local")
        if loc and not t:
            errs.append(f"{w}: time_source_local is set but time (UTC) is null")
        if t and s["time_precision"] == "unknown":
            errs.append(f"{w}: time is set but time_precision is unknown")
        if not t and s["time_precision"] == "exact":
            errs.append(f"{w}: time_precision exact needs a time")
        if t and loc and "T" in t and _LOCAL.search(loc):
            d0 = datetime.strptime(t[:10], "%Y-%m-%d")
            cands = {local_to_utc((d0 + timedelta(days=k)).strftime("%Y-%m-%d"), loc) for k in (-1, 0, 1)}
            if t[:16] + "Z" not in cands and None not in cands:
                errs.append(f"{w}: time {t} does not match time_source_local {loc!r} converted to UTC (BST is UTC+1)")
        tc = s.get("time_conflict")
        if tc and len(_TIMEISH.findall(tc)) < 2:
            errs.append(f"{w}: time_conflict must cite both conflicting values")
    orders = sorted(seen_orders)
    if orders and orders != list(range(orders[0], orders[0] + len(orders))):
        warns.append(f"{iid}: gap in step order ({orders})")
    prev = None
    for s in sorted(inc["steps"], key=lambda s: s["order"]):
        if s["order_basis"] != "stated" or not s["time"]:
            continue
        if prev and s["time"] < prev[1] and len(s["time"]) == len(prev[1]):
            warns.append(f"{iid}/{s['id']}: time {s['time']} is earlier than {prev[0]} ({prev[1]}) which comes before it")
        prev = (s["id"], s["time"])
    return errs, warns


def validate_all() -> tuple[list[str], list[str], int]:
    fw = fwm.load()
    reg = (c.load_yaml(SOURCES_FILE) or {}).get("sources") or [] if SOURCES_FILE.exists() else []
    E = validate_sources(reg)
    sources = {s["id"]: s for s in reg if "id" in s}
    W, ids, n = [], {}, 0
    for f in incident_files():
        inc = c.load_yaml(f)
        e, w = validate_incident(inc, sources, fw)
        E += [f"{f.name}: {x}" for x in e]; W += w; n += 1
        if isinstance(inc, dict):
            if inc.get("id") != f.stem:
                E.append(f"{f.name}: id {inc.get('id')!r} must equal the file name")
            if inc.get("id") in ids:
                E.append(f"{f.name}: duplicate incident id")
            ids[inc.get("id")] = f.name
    return E, W, n


def main() -> int:
    E, W, n = validate_all()
    print(f"validated {n} incident files: {len(E)} errors, {len(W)} warnings")
    for x in E:
        print("ERROR", x)
    for x in W[:40]:
        print("warn ", x)
    return 1 if E else 0


if __name__ == "__main__":
    sys.exit(main())
