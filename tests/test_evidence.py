"""Quote matcher and fetcher on messy, adversarial input. No network: the fetcher gets a fake transport."""
import pytest

import common as c
import evidence as ev

HTML = (c.ROOT / "tests" / "fixtures" / "sources" / "article.html").read_bytes()
TEXT = ev.extract_text(HTML, "text/html")


def status(q, text=TEXT, full=None):
    return ev.find_quote(q, text, full_text=full)["status"]


@pytest.mark.parametrize("q", [
    "enumerated reachable services",                           # NBSP and entity in the source
    "“enumerated reachable services”",                          # curly quotes in the quote
    "ENUMERATED   Reachable\nservices",                         # case, spaces, line break
    "found a package mirror... it then asked for more access",  # ellipsis char in source, dots in quote
    "found a package mirror… it then asked for more access",
    "It tried again & succeeded.",                              # &amp;
    "The team's on-call engineer - paged late - shut the proxy down.",   # curly apostrophe, odd hyphen, em dash
    "The agent did not escape the sandbox on its first attempt.",        # inline tag inside the sentence
])
def test_found_despite_typography(q):
    assert status(q) == "found"


def test_elided_quote_parts_in_order():
    r = ev.find_quote("enumerated reachable services [...] asked for more access", TEXT)
    assert r["status"] == "found" and r["elided"] is True
    assert status("asked for more access [...] enumerated reachable services") == "not_found"   # wrong order


@pytest.mark.parametrize("q,why", [
    ("the agent exfiltrated the weights", "not in the source at all"),
    ("gent did not escape the sand", "cuts words in half"),
    ("the agent sent the weights to a server", "only inside a script tag"),
    ("x", "one letter that occurs inside words"),
])
def test_not_found(q, why):
    assert status(q) == "not_found", why


@pytest.mark.parametrize("q", ["Our mission is to keep every sandbox sealed", "All sandboxes are sealed at night",
                               "Agents that never sleep, tested daily", "the agent deleted every backup"])
def test_quote_only_in_navigation_or_footer(q):
    full = ev.extract_text(HTML, "text/html", article_only=False)
    assert status(q, full=full) == "not_in_article"


def test_empty_and_too_long():
    assert status("") == "empty" and status("   ") == "empty" and status("...") == "empty"
    assert status(" ".join(["word"] * 26)) == "too_long"
    assert ev.find_quote(" ".join(["word"] * 25), TEXT)["status"] == "not_found"   # 25 is allowed, just absent


def test_substring_of_a_longer_different_sentence_is_flagged():
    # The words are there, but they are a fragment of a sentence that says the opposite.
    r = ev.find_quote("credentials were taken from the build server", TEXT)
    assert r["status"] == "found" and r["whole_sentence"] is False
    assert r["sentence"].lower().startswith("no credentials")
    r2 = ev.find_quote("Investigators later said the agent escaped twice.", TEXT)
    assert r2["whole_sentence"] is True


def test_normalise_is_idempotent_and_hash_is_stable():
    n = ev.normalise(TEXT)
    assert ev.normalise(n) == n
    assert ev.content_hash(TEXT) == ev.content_hash(TEXT.replace(" ", "  ").replace("’", "'"))
    assert ev.content_hash(TEXT) != ev.content_hash(TEXT + " One more sentence.")


def fake(routes):
    def transport(url):
        return routes[url]
    return transport


OK = (200, {"content-type": "text/html; charset=utf-8"}, HTML)


def test_fetch_ok():
    r = ev.fetch("https://example.org/post", transport=fake({"https://example.org/post": OK}), resolve=lambda h: ["93.184.216.34"])
    assert r["status"] == "ok" and "enumerated" in r["text"]


@pytest.mark.parametrize("code", [404, 500, 403])
def test_fetch_http_errors(code):
    r = ev.fetch("https://example.org/x", transport=fake({"https://example.org/x": (code, {}, b"nope")}), resolve=lambda h: ["93.184.216.34"])
    assert r["status"] == "http_error" and r["http_status"] == code and not r.get("text")


def test_fetch_redirect_to_login_is_not_the_source():
    routes = {"https://example.org/x": (302, {"location": "https://example.org/login?next=/x"}, b""),
              "https://example.org/login?next=/x": OK}
    r = ev.fetch("https://example.org/x", transport=fake(routes), resolve=lambda h: ["93.184.216.34"])
    assert r["status"] == "redirected_to_login"


def test_fetch_follows_a_plain_same_site_redirect():
    routes = {"https://example.org/news/x": (308, {"location": "/research/x"}, b""), "https://example.org/research/x": OK}
    r = ev.fetch("https://example.org/news/x", transport=fake(routes), resolve=lambda h: ["93.184.216.34"])
    assert r["status"] == "ok" and r["final_url"] == "https://example.org/research/x"


def test_fetch_redirect_to_private_address_is_refused():
    routes = {"https://example.org/x": (302, {"location": "https://169.254.169.254/latest/meta-data"}, b"")}
    r = ev.fetch("https://example.org/x", transport=fake(routes), resolve=lambda h: ["93.184.216.34"])
    assert r["status"] == "refused"


@pytest.mark.parametrize("url", ["http://example.org/x", "ftp://example.org/x", "file:///etc/passwd", "https://127.0.0.1/x",
                                 "https://10.0.0.8/x", "https://192.168.1.1/", "https://[::1]/x", "https://localhost/x",
                                 "https://169.254.169.254/", "https://user:pw@example.org/x", "https://db.internal/x", "not a url", ""])
def test_fetch_refuses_bad_urls(url):
    called = []
    r = ev.fetch(url, transport=lambda u: called.append(u) or OK, resolve=lambda h: ["93.184.216.34"])
    assert r["status"] == "refused" and not called


def test_fetch_refuses_a_public_name_that_resolves_to_a_private_address():
    called = []
    r = ev.fetch("https://sneaky.example.org/x", transport=lambda u: called.append(u) or OK, resolve=lambda h: ["10.1.2.3"])
    assert r["status"] == "refused" and not called


def test_fetch_empty_page_and_too_big():
    r = ev.fetch("https://example.org/e", transport=fake({"https://example.org/e": (200, {"content-type": "text/html"}, b"<html><body><nav>menu</nav></body></html>")}), resolve=lambda h: ["93.184.216.34"])
    assert r["status"] == "empty_page"
    big = (200, {"content-type": "text/html"}, b"a" * (ev.MAX_BYTES + 1))
    assert ev.fetch("https://example.org/b", transport=fake({"https://example.org/b": big}), resolve=lambda h: ["93.184.216.34"])["status"] == "too_big"


def test_fetch_pdf_uses_the_pdf_reader_or_says_it_cannot():
    pdf = (200, {"content-type": "application/pdf"}, b"%PDF-1.5 not a real pdf")
    r = ev.fetch("https://example.org/r.pdf", transport=fake({"https://example.org/r.pdf": pdf}), resolve=lambda h: ["93.184.216.34"])
    assert r["status"] in ("pdf_unreadable", "empty_page")     # never "ok" for bytes that hold no text


def test_check_step_reports_hash_drift_but_still_checks_the_quote():
    src = {"id": "syn", "url": "https://example.org/post", "content_sha256": "0" * 64}
    r = ev.check_quote_against_source("enumerated reachable services", src, text=TEXT)
    assert r["status"] == "found" and r["hash_drift"] is True
    src["content_sha256"] = ev.content_hash(TEXT)
    assert ev.check_quote_against_source("enumerated reachable services", src, text=TEXT)["hash_drift"] is False


def test_apply_results_only_moves_between_the_two_script_tiers():
    step = {"id": "s01", "label_status": "draft_needs_human_review", "history": [], "reviewed_by": None}
    assert ev.apply_result(step, {"status": "found"}, today="2026-01-05") is True
    assert step["label_status"] == "evidence_checked" and "script" in step["history"][-1]["who"]
    assert ev.apply_result(step, {"status": "not_found"}, today="2026-01-06") is True     # quote vanished: back to draft
    assert step["label_status"] == "draft_needs_human_review"
    human = {"id": "s02", "label_status": "reviewed", "history": [], "reviewed_by": "A Human"}
    assert ev.apply_result(human, {"status": "not_found"}, today="2026-01-06") is False   # never touches a human tier
    assert human["label_status"] == "reviewed"


def test_clip_drops_reader_comments_and_page_chrome():
    text = "Upvote 518\nThe article starts here.\nThe agent escaped.\nCommunity\nsomeone: the agent was framed"
    src = {"text_starts_at": "The article starts here.", "text_ends_before": "Community"}
    out = ev.clip(text, src)
    assert out.startswith("The article starts here.") and "framed" not in out and "Upvote" not in out
    assert ev.find_quote("the agent was framed", out)["status"] == "not_found"      # a comment is not the source
    assert ev.clip(text, {}) == text and ev.clip(text, {"text_ends_before": "no such marker"}) == text
