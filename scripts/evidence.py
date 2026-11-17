#!/usr/bin/env python3
"""Evidence checker: is a step's quote really in the source it cites?

It answers one narrow question, by string matching. It does not judge whether the label is right.
A hit moves a step from Draft to Evidence-checked; a miss moves it back. It never touches a human tier.

  evidence.py fetch            fetch every registered source into .cache/incident_sources (network)
  evidence.py check            check every step's quote against the cached text (offline)
  evidence.py check --network  fetch first, then check
  evidence.py check --write    also update label_status and history in data/incidents/*.yml
  evidence.py hashes --write   store the content hash of each cached source in the registry

Safety: https only, no private or local addresses, no automatic redirects (each hop is re-checked), 2 MB and
10 s caps, one request per address. No source text is written into the repository (the cache is git-ignored).
"""
from __future__ import annotations

import hashlib
import html
import html.parser
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

import common as c

CACHE = c.ROOT / ".cache" / "incident_sources"
MAX_BYTES = 2_000_000
TIMEOUT = 10
MAX_WORDS = 25
MAX_REDIRECTS = 3
USER_AGENT = "ACTCM-evidence-check/0.2 (+https://github.com/adritatori/ACTCM; quote check, one request per page)"
SCRIPT_NAME = "evidence.py (script)"
_ALWAYS_SKIP = {"script", "style", "noscript", "template", "svg", "head"}
_CHROME = {"nav", "footer", "header", "aside", "form", "button"}
_BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "section", "article", "td", "th", "pre",
          "blockquote", "figcaption", "ul", "ol", "table", "main", "title", "dt", "dd", "summary", "details"}
_VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "area", "base", "col", "embed", "track"}
_TRANS = {ord(k): v for k, v in {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"', "«": '"', "»": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-", "…": "...", "­": "", "​": "",
    "‌": "", "‍": "", "﻿": "", "⁠": ""}.items()}
_LOGIN = re.compile(r"(^|[/?&=_.-])(login|log-in|signin|sign-in|sign_in|sso|auth|authorize|account/begin)([/?&=_.-]|$)", re.I)
_ELLIPSIS = re.compile(r"\s*(?:\[\s*\.\.\.\s*\]|\(\s*\.\.\.\s*\)|\.\.\.)\s*")


# ---------- text ----------
def normalise(text: str, keep_blocks: bool = False) -> str:
    """Lower case, entities decoded, curly quotes and odd dashes made plain, all white space (NBSP too) to one space."""
    t = html.unescape(text or "")
    t = unicodedata.normalize("NFKC", t).translate(_TRANS).lower()
    if keep_blocks:
        return "\n".join(x for x in (re.sub(r"\s+", " ", b).strip() for b in t.split("\n")) if x)
    return re.sub(r"\s+", " ", t).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


class _Extractor(html.parser.HTMLParser):
    def __init__(self, article_only: bool):
        super().__init__(convert_charrefs=True)
        self.skip = _ALWAYS_SKIP | (_CHROME if article_only else set())
        self.depth, self.out = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in self.skip and tag not in _VOID:
            self.depth += 1
        if tag in _BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.skip and self.depth:
            self.depth -= 1
        if tag in _BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.depth:
            self.out.append(data)


def pdf_to_text(raw: bytes) -> str | None:
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        res = subprocess.run([exe, "-enc", "UTF-8", "-", "-"], input=raw, capture_output=True, timeout=60)
    except (subprocess.SubprocessError, OSError):
        return None
    if res.returncode != 0:
        return None
    t = res.stdout.decode("utf-8", errors="ignore")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)          # words broken over a line end
    return re.sub(r"(?<!\n)\n(?!\n)", " ", t)       # single line breaks are layout, blank lines are paragraphs


def extract_text(raw: bytes, content_type: str = "text/html", article_only: bool = True) -> str:
    if "pdf" in (content_type or "").lower() or raw[:5] == b"%PDF-":
        return pdf_to_text(raw) or ""
    text = raw.decode("utf-8", errors="ignore")
    if "html" in (content_type or "html").lower() or "<html" in text[:2000].lower() or "<body" in text.lower():
        p = _Extractor(article_only)
        p.feed(text)
        text = "".join(p.out)
    return "\n".join(x for x in (re.sub(r"[ \t\xa0]+", " ", b).strip() for b in text.split("\n")) if x)


def _sentence_around(blocks: str, start: int, end: int) -> tuple[str, bool]:
    """The sentence that holds blocks[start:end], and whether the match is that whole sentence."""
    a = start
    while a > 0 and blocks[a - 1] != "\n" and not (blocks[a - 1] in " " and a >= 2 and blocks[a - 2] in ".!?"):
        a -= 1
    b = end
    while b < len(blocks) and blocks[b] != "\n" and not (blocks[b - 1] in ".!?" and blocks[b] == " "):
        b += 1
    sent = blocks[a:b].strip()
    strip = " \"'()[]"
    whole = sent.strip(strip).rstrip(".!?") == blocks[start:end].strip(strip).rstrip(".!?")
    return sent, whole


def _find_at_boundaries(needle: str, hay: str, start: int = 0) -> int:
    i = hay.find(needle, start)
    while i != -1:
        before = hay[i - 1] if i else " "
        after = hay[i + len(needle)] if i + len(needle) < len(hay) else " "
        if not (before.isalnum() and needle[0].isalnum()) and not (after.isalnum() and needle[-1].isalnum()):
            return i
        i = hay.find(needle, i + 1)
    return -1


def _locate(q: str, flat: str) -> tuple[int, int, bool] | None:
    i = _find_at_boundaries(q, flat)
    if i != -1:
        return i, i + len(q), False
    parts = [p for p in _ELLIPSIS.split(q) if p.strip(" .")]
    if len(parts) < 2:
        return None
    pos, first = 0, None
    for p in parts:
        i = _find_at_boundaries(p, flat, pos)
        if i == -1 or (first is not None and i - pos > 1500):
            return None
        first = i if first is None else first
        pos = i + len(p)
    return first, pos, True


def find_quote(quote: str, text: str, full_text: str | None = None) -> dict:
    """status: found | not_found | not_in_article | empty | too_long. Matching is on normalised text, at word edges."""
    q = normalise(quote).strip(" \"'")
    if not q.strip(" .[]()"):
        return {"status": "empty"}
    if len((quote or "").split()) > MAX_WORDS:
        return {"status": "too_long", "words": len(quote.split())}
    blocks = normalise(text, keep_blocks=True)
    hit = _locate(q, blocks.replace("\n", " "))
    if hit:
        sent, whole = _sentence_around(blocks, hit[0], hit[1])
        return {"status": "found", "elided": hit[2], "whole_sentence": whole and not hit[2], "sentence": sent[:400]}
    if full_text is not None and _locate(q, normalise(full_text)):
        return {"status": "not_in_article"}
    return {"status": "not_found"}


# ---------- fetching ----------
def _default_resolve(host: str) -> list[str]:
    try:
        return sorted({ai[4][0] for ai in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)})
    except OSError:
        if os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"):
            return []            # behind an egress proxy the name is resolved (and policed) by the proxy
        raise


def _is_public_ip(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    return a.is_global and not (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified)


def url_problem(url: str, resolve=_default_resolve) -> str | None:
    """None if the address may be fetched, else the reason it is refused."""
    try:
        u = urllib.parse.urlsplit(url or "")
        host = u.hostname
        _ = u.port
    except ValueError:
        return "not a valid address"
    if u.scheme != "https":
        return "only https addresses are fetched"
    if not host:
        return "no host name"
    if u.username or u.password:
        return "addresses with a user name or password are refused"
    if u.port not in (None, 443):
        return "only the default https port is fetched"
    host = host.lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
        return None if _is_public_ip(host) else "private or local address"
    except ValueError:
        pass
    if host == "localhost" or "." not in host or host.endswith((".local", ".internal", ".localhost", ".lan", ".home", ".corp", ".test", ".invalid")):
        return "private or local host name"
    try:
        ips = resolve(host)
    except OSError:
        return "host name does not resolve"
    if any(not _is_public_ip(ip) for ip in ips):
        return "host name resolves to a private or local address"
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _default_transport(url: str) -> tuple[int, dict, bytes]:
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.5"})
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, b""


def fetch(url: str, transport=None, resolve=None) -> dict:
    """Fetch one source. status: ok | refused | http_error | redirected_to_login | too_big | empty_page |
    pdf_unreadable | network_error. Text is returned, never stored in the repository."""
    transport, resolve = transport or _default_transport, resolve or _default_resolve
    cur = url
    for _hop in range(MAX_REDIRECTS + 1):
        why = url_problem(cur, resolve)
        if why:
            return {"status": "refused", "reason": why, "final_url": cur}
        try:
            code, headers, body = transport(cur)
        except Exception as e:  # noqa: BLE001  (any transport failure is reported, never raised)
            return {"status": "network_error", "reason": type(e).__name__, "final_url": cur}
        if code in (301, 302, 303, 307, 308):
            loc = headers.get("location")
            if not loc:
                return {"status": "http_error", "http_status": code, "final_url": cur}
            nxt = urllib.parse.urljoin(cur, loc)
            if _LOGIN.search(urllib.parse.urlsplit(nxt).path) or _LOGIN.search(urllib.parse.urlsplit(nxt).query[:80]):
                return {"status": "redirected_to_login", "final_url": nxt}
            cur = nxt
            continue
        if code != 200:
            return {"status": "http_error", "http_status": code, "final_url": cur}
        if len(body) > MAX_BYTES:
            return {"status": "too_big", "final_url": cur}
        ctype = headers.get("content-type", "")
        is_pdf = "pdf" in ctype.lower() or body[:5] == b"%PDF-"
        if is_pdf:
            text = pdf_to_text(body)
            if text is None:
                return {"status": "pdf_unreadable", "final_url": cur}
            full = text
        else:
            text, full = extract_text(body, ctype or "text/html"), extract_text(body, ctype or "text/html", article_only=False)
        if len(text.split()) < 5:
            return {"status": "empty_page", "final_url": cur}
        return {"status": "ok", "http_status": 200, "final_url": cur, "text": text, "full_text": full,
                "sha256": content_hash(text), "media_type": "pdf" if is_pdf else "html"}
    return {"status": "http_error", "reason": "too many redirects", "final_url": cur}


# ---------- steps ----------
def check_quote_against_source(quote: str, src: dict, text: str, full_text: str | None = None) -> dict:
    r = find_quote(quote, text, full_text=full_text)
    r["hash_drift"] = bool(src.get("content_sha256")) and src["content_sha256"] != content_hash(text)
    return r


def apply_result(step: dict, result: dict, today: str | None = None) -> bool:
    """Draft -> Evidence-checked on a hit; Evidence-checked -> Draft on a miss. Human tiers are never changed."""
    old = step["label_status"]
    new = {("draft_needs_human_review", True): "evidence_checked", ("evidence_checked", False): "draft_needs_human_review"}.get(
        (old, result["status"] == "found"))
    if new is None:
        return False
    step["label_status"] = new
    step.setdefault("history", []).append(dict(
        date=today or date.today().isoformat(), who=SCRIPT_NAME, change=f"status {old} -> {new}",
        reason="quote found in the cited source by string match; the label itself is not checked" if new == "evidence_checked"
        else f"quote no longer found in the cited source ({result['status']})"))
    return True


def clip(text: str, src: dict) -> str:
    """Keep only the article: drop what comes before `text_starts_at` and from `text_ends_before` on (for example
    a reader-comment section, which is not the publisher's text and changes daily)."""
    a, b = src.get("text_starts_at"), src.get("text_ends_before")
    if a and a in text:
        text = text[text.index(a):]
    if b and b in text:
        text = text[:text.index(b)]
    return text


def cached(source_id: str) -> tuple[str | None, str | None]:
    p, f = CACHE / f"{source_id}.txt", CACHE / f"{source_id}.full.txt"
    return (p.read_text(encoding="utf-8") if p.exists() else None, f.read_text(encoding="utf-8") if f.exists() else None)


def fetch_all(sources: dict) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    for sid, s in sorted(sources.items()):
        r = fetch(s["url"])
        out[sid] = r
        if r["status"] == "ok":
            r["text"] = clip(r["text"], s)
            r["sha256"] = content_hash(r["text"])
            (CACHE / f"{sid}.txt").write_text(r["text"], encoding="utf-8")
            (CACHE / f"{sid}.full.txt").write_text(r["full_text"], encoding="utf-8")
        print(f"{r['status']:<20} {sid:<28} {r.get('sha256', '')[:12]} {r.get('reason', r.get('http_status', ''))}")
    return out


def check_all(write: bool = False, today: str | None = None) -> list[dict]:
    import validate_incidents as vi
    sources, rows = vi.load_sources(), []
    for f in vi.incident_files():
        inc, changed = c.load_yaml(f), False
        for s in inc["steps"]:
            src = sources.get(s["evidence"]["source"])
            text, full = cached(s["evidence"]["source"]) if src else (None, None)
            r = {"status": "source_not_cached"} if text is None else check_quote_against_source(s["evidence"]["quote"], src, text, None)
            rows.append(dict(incident=inc["id"], step=s["id"], source=s["evidence"]["source"], **r))
            if write and text is not None:
                changed |= apply_result(s, r, today)
        if changed:
            c.dump_yaml(inc, f)
    return rows


def main(argv: list[str]) -> int:
    import validate_incidents as vi
    cmd = argv[0] if argv else "check"
    if cmd == "fetch" or "--network" in argv:
        fetch_all(vi.load_sources())
    if cmd == "hashes":
        reg = c.load_yaml(vi.SOURCES_FILE)
        for s in reg["sources"]:
            text, _ = cached(s["id"])
            h = content_hash(text) if text else None
            print(f"{s['id']:<28} {'no cache' if h is None else 'same' if h == s.get('content_sha256') else 'CHANGED' if s.get('content_sha256') else 'new'}")
            if "--write" in argv and h:
                s["content_sha256"] = h
        if "--write" in argv:
            head = "".join(x for x in vi.SOURCES_FILE.read_text(encoding="utf-8").splitlines(True) if x.startswith("#"))
            vi.SOURCES_FILE.write_text(head + c.dump_yaml(reg), encoding="utf-8")
    if cmd == "check":
        rows = check_all(write="--write" in argv)
        bad = [r for r in rows if r["status"] != "found"]
        for r in rows:
            flag = "" if r["status"] != "found" else ("  (elided)" if r.get("elided") else "") + ("  (part of a longer sentence)" if not r.get("whole_sentence") else "") + ("  (source text changed since registered)" if r.get("hash_drift") else "")
            print(f"{r['status']:<18} {r['incident']}/{r['step']}  [{r['source']}]{flag}")
        print(f"{len(rows) - len(bad)} of {len(rows)} quotes found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
