"""Site tests: branding, footers, numbers vs counts.json, links, contrast, and browser checks."""
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

import pytest

import common as c
import build_site as bs

SITE = c.ROOT / "site"
PAGES = ["index.html", "guide.html", "verify.html"]
COUNTS = json.loads((c.DATA / "generated" / "counts.json").read_text())
TASKS = json.loads((c.DATA / "generated" / "tasks.json").read_text())


class Text(HTMLParser):
    """Collects visible text and head text in document order, plus hrefs."""
    def __init__(self):
        super().__init__(); self.parts, self.hrefs, self._skip, self.head = [], [], 0, []
        self.in_head = False; self.ids = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "head": self.in_head = True
        if tag in ("script", "style"): self._skip += 1
        if a.get("href"): self.hrefs.append(a["href"])
        if a.get("id"): self.ids.add(a["id"])
        if tag == "meta" and a.get("name") == "description": self.parts.append(a.get("content", ""))
        if tag == "img" and a.get("alt"): self.parts.append(a["alt"])

    def handle_endtag(self, tag):
        if tag == "head": self.in_head = False
        if tag in ("script", "style"): self._skip -= 1

    def handle_data(self, d):
        if self._skip: return
        (self.head if self.in_head else self.parts).append(d)


def parse(fn):
    p = Text(); raw = (SITE / fn).read_text(encoding="utf-8"); p.feed(raw)
    text = re.sub(r"\s+", " ", "".join(p.head + p.parts))                 # tags add no spaces of their own
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    return p, text, raw


# ---- branding -----------------------------------------------------------------------------------
@pytest.mark.parametrize("fn", PAGES)
def test_first_mention_is_mitre_attack_with_registered_mark(fn):
    _, text, _ = parse(fn)
    m = re.search(r"ATT&CK", text)
    assert m, fn
    assert text[max(0, m.start() - 6):m.end() + 1] == "MITRE ATT&CK®", (fn, text[max(0, m.start() - 20):m.end() + 5])


@pytest.mark.parametrize("fn", PAGES)
def test_no_misspelled_or_hyphenated_trademark(fn):
    _, text, raw = parse(fn)
    for bad in ("ATTACK", "Att&ck", "ATT-CK", "Att&CK", "AT&CK", "ATT&amp;CK®®"):
        assert bad not in text and bad not in raw.replace("ATTACK1", ""), (fn, bad)
    assert "ATT&amp;CK ®" not in raw


@pytest.mark.parametrize("fn", PAGES)
def test_project_name_title_and_brand_have_no_mitre_or_attack(fn):
    p, _, raw = parse(fn)
    title = re.search(r"<title>(.*?)</title>", raw).group(1)
    brand = re.search(r'class="brand"[^>]*>(.*?)</a>', raw, re.S).group(1)
    for s in (title, brand):
        assert "MITRE" not in s.upper() and "ATT&" not in s.upper() and "ATTACK" not in s.upper(), s


def test_no_mitre_logos_or_fonts_in_assets():
    css = (SITE / "assets" / "style.css").read_text().lower()
    assert "mitre" not in css and "@font-face" not in css and "url(" not in css.replace("url(#ah)", "")
    assert not list((SITE / "assets").rglob("*logo*"))


# ---- footers, banner ---------------------------------------------------------------------------------
@pytest.mark.parametrize("fn", PAGES)
def test_footer_and_banner_on_every_page(fn):
    _, text, raw = parse(fn)
    must = ["A task count shows what is tested, not what is caught", "A gap means “untested”, not “dangerous” and not “undefended”",
            "Not affiliated with or endorsed by The MITRE Corporation.", bs.MITRE_LINE, "Terms of Use", "CC BY 4.0", "MIT",
            "Apache License 2.0", "PROVISIONAL RESULTS", "No human has reviewed any label yet.", "ATT&CK Enterprise v20.0", "ATLAS 2026.10", "codebook 1.1-draft"]
    for m in must:
        assert m in text, (fn, m)
    assert "<footer" in raw and "github.com/adritatori/actcm" in raw


@pytest.mark.parametrize("fn", PAGES)
def test_licence_paragraph_reproduced_and_no_open_wording_note(fn):
    _, text, raw = parse(fn)
    assert "wording check" not in text.lower() and "licence-wording" not in text.lower()
    lic = (c.DATA / "legal" / "attack_licence.txt").read_text(encoding="utf-8")
    para = " ".join(lic.split("\n\n")[0].split("\n")[2:]).strip()
    assert "hereby grants you a non-exclusive, royalty-free license" in para and "reproduce MITRE's copyright designation and this license" in para
    norm = lambda x: re.sub(r"\s+", " ", x.replace("ATT&amp;CK", "ATT&CK"))
    assert norm(para) in norm(text), fn
    disc = lic.split("Disclaimers\n-----------\n")[1].strip()
    paras = [x for x in disc.split("\n\n") if x.strip()]
    assert len(paras) == 2 and all(norm(x) in norm(text) for x in paras), fn      # each paragraph, word for word
    assert bs.MITRE_LINE in text


def test_licence_file_matches_pinned_source():
    d = c.CACHE.parent / "frameworks" / "attack-stix-data"
    if not d.exists():
        pytest.skip("framework cache missing")
    sha = c.load_yaml(c.LOCK_FILE)["frameworks"]["attack"]["sha"]
    src = c.show(d, sha, "LICENSE.txt")
    assert src == (c.DATA / "legal" / "attack_licence.txt").read_text(encoding="utf-8")


class Headings(HTMLParser):
    TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "dt", "summary", "caption", "legend"}
    def __init__(self):
        super().__init__(); self.out, self.cur = [], None
    def handle_starttag(self, tag, attrs):
        if tag in self.TAGS: self.cur = []
    def handle_endtag(self, tag):
        if tag in self.TAGS and self.cur is not None:
            self.out.append(re.sub(r"\s+", " ", "".join(self.cur)).strip()); self.cur = None
    def handle_data(self, d):
        if self.cur is not None: self.cur.append(d)


@pytest.mark.parametrize("fn", PAGES)
def test_every_heading_that_names_attack_says_mitre_attack_registered(fn):
    h = Headings(); h.feed((SITE / fn).read_text(encoding="utf-8"))
    named = [x for x in h.out if "ATT&CK" in x]
    assert named or fn != "index.html", "explorer must have an ATT&CK heading"
    for x in named:
        assert "MITRE ATT&CK®" in x, (fn, x)
    assert not [x for x in h.out if re.search(r"ATT&CK(?!®)", x.replace("MITRE ATT&CK®", ""))], (fn, h.out)


def test_explorer_js_headings_say_mitre_attack_registered():
    js = (SITE / "assets" / "app.js").read_text()
    assert 'MITRE ATT&CK\\u00AE matrix' in js and 'No MITRE ATT&CK\\u00AE technique fits, ' in js
    assert '"ATT&CK matrix' not in js


def test_banner_wording():
    _, text, _ = parse("index.html")
    assert "No human has reviewed any label yet." in text and "licence-wording" not in text


@pytest.mark.parametrize("fn", PAGES)
def test_pinned_shas_in_footer_match_lock(fn):
    _, text, _ = parse(fn)
    lock = c.load_yaml(c.LOCK_FILE)["frameworks"]
    assert lock["attack"]["sha"][:10] in text and lock["atlas"]["sha"][:10] in text


# ---- numbers ------------------------------------------------------------------------------------------
def test_no_template_placeholders_left():
    for fn in PAGES:
        _, text, raw = parse(fn)
        assert "{{" not in raw and "{SCRIPT}" not in raw and "None" not in text.split("Related")[0] or fn != "guide.html"


def test_guide_numbers_match_counts():
    _, text, _ = parse("guide.html")
    s, by, t = COUNTS["summary"], COUNTS["totals"]["by_setting"], COUNTS["tiers"]["total"]
    settings_text = ", ".join(f"{x['name']} {by[x['id']]}" for x in COUNTS["settings"])
    expect = [f"{s['tasks']} side tasks are counted: {settings_text}",
              f"{s['tactics_covered_primary']} of {s['tactics_total']} tactics have at least one task",
              f"{s['tactics_covered_with_steps']} of {s['tactics_total']} are covered",
              f"{s['template_tasks']} tasks ({s['template_share_percent']}%)", f"{s['ambiguous_labels']} labels are marked ambiguous",

              f"{t['draft_needs_human_review']} Draft, {t['ai_cross_checked']} AI cross-checked, {t['reviewed']} Reviewed by a human, {t['adjudicated']} Adjudicated by humans",
              ]
    if COUNTS["totals"]["unfinished_upstream"]:
        expect.append(f"{COUNTS['totals']['unfinished_upstream']} unfinished upstream drafts are excluded")
    if s["planned_scorer_tasks"]:
        expect.append(f"{s['planned_scorer_tasks']} tasks have an upstream scorer that is only planned")
    for e in expect:
        assert e in text, e
    names = {x["id"]: x["name"] for x in COUNTS["tactics"]}
    assert ", ".join(names[g] for g in COUNTS["gaps"]["primary"]) in text
    stress = json.loads((c.DATA / "generated" / "stress_results.json").read_text())
    for g in stress["gap_stays_zero"]:
        assert f"{100 * g['current_labels']:.1f}%" in text


def test_guide_example_matches_task_file():
    _, text, _ = parse("guide.html")
    ex = next(t for t in TASKS if t["id"] == "poison_git_sync")
    assert ex["goal"] in text and ex["technique"] in text and ex["technique_name"] in text


def test_verify_numbers_match_counts():
    _, text, _ = parse("verify.html")
    assert f"({COUNTS['tiers']['total']['reviewed']} reviewed, {COUNTS['tiers']['total']['adjudicated']} adjudicated)" in text


def test_explorer_static_text_has_no_stale_numbers():
    _, text, _ = parse("index.html")
    assert f"({COUNTS['summary']['null_technique_tasks']} in total)" in text
    assert "ATT&CK (15 tactics)" in text and "ATLAS (16 tactics)" in text


def test_data_files_on_site_equal_generated():
    for f in ("counts.json", "tasks.json", "tasks.csv", "stress_results.json"):
        assert (SITE / "data" / f).read_bytes() == (c.DATA / "generated" / f).read_bytes(), f


def test_glossary_has_every_brief_term():
    _, text, _ = parse("guide.html")
    for term in ["AI model", "Large language model (LLM)", "AI agent", "Agentic", "AI control", "Control setting", "Control evaluation (control eval)",
                 "Main task", "Side task", "Honest run / attack run", "Monitor", "Suspicion score", "Audit budget / false positive rate (FPR)",
                 "Safety (in control evals)", "Live failure / delayed failure", "MITRE ATT&CK®", "Tactic", "Technique / sub-technique", "MITRE ATLAS",
                 "ATT&CK Navigator", "Coverage", "Gap", "Codebook", "Inter-rater agreement", "Cohen's kappa (κ)", "Adjudication"]:
        assert term in text, term


def test_tier_wording_on_pages_never_calls_ai_cross_checked_reviewed():
    tiers = json.loads((SITE / "data" / "status_tiers.json").read_text())
    t = next(x for x in tiers["tiers"] if x["id"] == "ai_cross_checked")
    assert "No human has checked it" in t["plain"]
    for bad in tiers["never_say_for_ai_cross_checked"]:
        assert bad not in t["plain"].lower() and bad not in t["label"].lower()
    _, text, _ = parse("guide.html")
    for m in re.finditer(r"AI cross-checked", text):
        window = text[m.end():m.end() + 160].lower()
        assert "reviewed" not in window.replace("reviewed by a human", "").replace("no human has reviewed", "") or "not" in window, window


def test_js_never_labels_cross_checked_as_reviewed():
    js = (SITE / "assets" / "app.js").read_text()
    m = re.search(r"TIER_MARK = \{(.*?)\};", js, re.S)
    marks = dict(re.findall(r'(\w+): *"([^"]*)"', m.group(1)))
    assert len(set(marks.values())) == 4, marks                 # each tier has its own marker
    assert marks["ai_cross_checked"] != marks["reviewed"] and marks["ai_cross_checked"] != marks["adjudicated"]
    assert "Reviewed by a human" not in js                      # tier label text comes from status_tiers.json only


# ---- links --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("fn", PAGES)
def test_internal_links_resolve(fn):
    p, _, _ = parse(fn)
    for h in p.hrefs:
        if h.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = (SITE / h.split("#")[0]).resolve()
        assert target.exists(), (fn, h)
        if "#" in h and h.split("#")[1]:
            q, _, _ = parse(h.split("#")[0]); assert h.split("#")[1] in q.ids, (fn, h)
    for h in p.hrefs:
        if h.startswith("#") and len(h) > 1:
            assert h[1:] in p.ids, (fn, h)


@pytest.mark.parametrize("fn", PAGES)
def test_repo_links_are_marked_as_working_after_publishing(fn):
    _, _, raw = parse(fn)
    blocks = re.split(r"</p>|</li>|</td>|</figcaption>", raw)
    hits = [b for b in blocks if "github.com/adritatori/actcm" in b]
    assert hits, fn
    for b in hits:
        if c.config().get("published"):
            assert not re.search(r"works? after publishing", b), "the repository is live, so the pending note must be gone"
        else:
            assert re.search(r"works? after publishing", b), re.sub(r"\s+", " ", b)[-200:]


def test_images_exist_with_alt_text_and_size():
    raw = (SITE / "guide.html").read_text()
    for src, alt in re.findall(r'<img src="([^"]+)" alt="([^"]*)"', raw):
        assert (SITE / src).exists() and len(alt) > 20, src


# ---- contrast (WCAG 2.2 AA) ---------------------------------------------------------------------------
def tokens(block: str) -> dict:
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", block))


def blocks():
    css = (SITE / "assets" / "style.css").read_text()
    light = re.search(r":root \{(.*?)\n\}", css, re.S).group(1)
    dark_media = re.search(r":root:not\(\[data-theme=\"light\"\]\) \{(.*?)\n  \}", css, re.S).group(1)
    dark_attr = re.search(r":root\[data-theme=\"dark\"\] \{(.*?)\n\}", css, re.S).group(1)
    return tokens(light), tokens(dark_media), tokens(dark_attr)


def lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


TEXT_PAIRS = [("ink", "bg"), ("ink", "surface"), ("ink", "surface-2"), ("muted", "bg"), ("muted", "surface"), ("muted", "surface-2"),
              ("link", "bg"), ("link", "surface"), ("link", "accent-soft"), ("ink", "accent-soft"), ("accent-ink", "accent"),
              ("warn-ink", "warn-bg"), ("gap-ink", "surface"), ("gap-ink", "surface-2"), ("link", "surface-2")]
UI_PAIRS = [("focus", "bg"), ("focus", "surface"), ("accent", "bg"), ("accent", "surface"), ("bar", "surface-2"), ("warn-line", "bg")]


def test_dark_blocks_are_identical():
    _, a, b = blocks()
    assert a == b


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_text_contrast_at_least_4_5(scheme):
    t = blocks()[0 if scheme == "light" else 1]
    low = [(x, y, round(ratio(t[x], t[y]), 2)) for x, y in TEXT_PAIRS if ratio(t[x], t[y]) < 4.5]
    assert not low, low


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_ui_contrast_at_least_3(scheme):
    t = blocks()[0 if scheme == "light" else 1]
    low = [(x, y, round(ratio(t[x], t[y]), 2)) for x, y in UI_PAIRS if ratio(t[x], t[y]) < 3.0]
    assert not low, low


def test_gap_is_never_colour_only():
    js = (SITE / "assets" / "app.js").read_text()
    assert "0 tasks: gap (untested)" in js and "0 tasks: gap in this setting (untested)" in js and "gapnote" in js
    css = (SITE / "assets" / "style.css").read_text()
    assert "repeating-linear-gradient" in css and "border-style: dashed" in css


# ---- browser ----------------------------------------------------------------------------------------------
def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "-d", str(SITE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()


def _node_ok():
    if not shutil.which("node"):
        return False
    r = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True)
    return r.returncode == 0


@pytest.mark.skipif(not _node_ok(), reason="node + playwright not available")
def test_browser_numbers_interactions_keyboard(server):
    r = subprocess.run(["node", str(c.ROOT / "scripts" / "site_numbers.js"), server], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-500:]
    assert " 0 failures" in r.stdout


@pytest.mark.skipif(not _node_ok(), reason="node + playwright not available")
def test_browser_no_console_errors_no_horizontal_scroll(server):
    r = subprocess.run(["node", str(c.ROOT / "scripts" / "site_check.js"), server], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-500:]
