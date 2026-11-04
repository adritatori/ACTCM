"""Phase 8: community files, licences, notices, README numbers, and the disabled Pages workflow."""
import json
import re

import yaml

import build_readme as br
import common as c

R = c.ROOT
COUNTS = json.loads((c.DATA / "generated" / "counts.json").read_text())
DOCS = ["README.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md", "docs/PROTOCOL.md", "docs/SOURCES.md", "CHANGELOG.md", "docs/OPEN_QUESTIONS.md"]


def text(p):
    return (R / p).read_text(encoding="utf-8")


def test_required_files_exist():
    for p in ["README.md", "CONTRIBUTING.md", "CITATION.cff", "LICENSE", "LICENSE-DATA", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md", "docs/OPEN_QUESTIONS.md",
              "docs/PROTOCOL.md", ".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/label_dispute.md", ".github/ISSUE_TEMPLATE/new_setting.md",
              ".github/ISSUE_TEMPLATE/bug.md", ".github/workflows/ci.yml", ".github/workflows/pages.yml", "Makefile", "requirements.txt"]:
        assert (R / p).exists(), p


def test_first_mention_of_attack_is_mitre_attack_registered_in_every_doc():
    for p in DOCS + ["codebook/CODEBOOK.md", "LICENSE-DATA"]:
        t = text(p)
        m = re.search(r"ATT&CK", t)
        if not m:
            assert p not in ("README.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md", "docs/PROTOCOL.md", "codebook/CODEBOOK.md", "LICENSE-DATA"), p
            continue
        assert t[max(0, m.start() - 6):m.end() + 1] == "MITRE ATT&CK®", (p, t[max(0, m.start() - 20):m.end() + 5])


def test_no_misspelled_trademark_anywhere_in_docs_or_code():
    bad = ("ATTACK", "Att&ck", "ATT-CK", "Att&CK", "AT&CK", "ATT&CK(R)")
    for path in list(R.glob("*.md")) + list((R / "docs").glob("*.md")) + list((R / "codebook").glob("*.md")) + [R / "CITATION.cff", R / "LICENSE-DATA"]:
        t = path.read_text(encoding="utf-8")
        for b in bad:
            assert b not in t.replace("ATTACK1", ""), (path.name, b)


def test_readme_has_the_required_lines():
    t = text("README.md")
    assert "A task count shows what is *tested*, not what is *caught*." in t
    assert "A gap means \"untested\", not \"dangerous\" and not \"undefended\"." in t
    assert "Not affiliated with or endorsed by The MITRE Corporation." in t
    assert "© 2026 The MITRE Corporation. This work is reproduced and distributed with the permission of The MITRE Corporation." in t
    assert "v0.4.0" in t and "no such tag" in t and "docs/screenshots/index-1280-light.png" in t
    assert (R / "docs/screenshots/index-1280-light.png").exists()
    for s in ("Quick start", "How to verify", "Contribute", "Cite", "Licences"):
        assert s in t, s


def test_readme_result_block_matches_counts():
    t = text("README.md")
    a, b = t.index(br.START) + len(br.START), t.index(br.END)
    assert t[a:b].strip() == br.paragraph(COUNTS)
    tt = COUNTS["tiers"]["total"]
    assert f"{COUNTS['totals']['tasks']} side tasks" in t
    assert f"{tt['draft_needs_human_review']} Draft, {tt['ai_cross_checked']} AI cross-checked, {tt['reviewed']} Reviewed by a human, {tt['adjudicated']} Adjudicated by humans" in t


def test_contributing_covers_what_the_brief_asks():
    t = text("CONTRIBUTING.md")
    for s in ("Codebook first", "How to dispute a label", "Add a new control setting", "Pull request checklist", "Set up", "only be set by a named human"):
        assert s.lower() in t.lower(), s


def test_citation_cff():
    d = yaml.safe_load(text("CITATION.cff"))
    assert d["cff-version"] == "1.2.0" and d["version"] == "0.1.0-draft" and d["authors"][0] == {"given-names": "Adrita", "family-names": "Rahman Tory"}
    assert d["repository-code"] == "https://github.com/adritatori/actcm"
    assert "ATT&CK®" in d["abstract"] and "Not affiliated" in d["abstract"]


def test_licences():
    assert text("LICENSE").startswith("MIT License") and "Adrita Rahman Tory" in text("LICENSE")
    d = text("LICENSE-DATA")
    assert "CC BY 4.0" in d and "creativecommons.org/licenses/by/4.0" in d


def test_notices_contain_every_required_notice():
    t = text("THIRD_PARTY_NOTICES.md")
    lic = (c.DATA / "legal" / "attack_licence.txt").read_text(encoding="utf-8").strip()
    assert lic in t, "MITRE licence and disclaimers must be reproduced byte for byte"
    assert "© 2026 The MITRE Corporation. This work is reproduced and distributed with the permission of The MITRE Corporation." in t
    assert "attack.mitre.org/resources/legal-and-branding/terms-of-use" in t and "Not affiliated with or endorsed by The MITRE Corporation." in t
    assert "Apache License 2.0" in t and "Copyright 2021-2026 MITRE" in t and "no `NOTICE` file" in t
    assert t.count("Copyright (c) 2025 LinuxArena") >= 2 and "Permission is hereby granted, free of charge" in t
    lock = c.public_lock(c.load_yaml(c.LOCK_FILE))
    for s in lock["sources"]:
        assert s["sha"] in t, s["repo"]
    full = c.load_yaml(c.LOCK_FILE)
    hidden = [s for s in full["sources"] if s["setting"] == c.HIDDEN_SETTING]
    if c.publish_extras():
        assert "We do not copy their goal text" in t and all(s["repo"] in t for s in hidden)
    else:
        assert "not included in v0.1, pending permission" in t
        assert not any(s["repo"].split("/")[1] in t or s["sha"] in t for s in hidden), "a hidden source is named in the notices"
    assert "could not confirm with a licence file" in t


def test_pages_workflow_is_in_one_clean_state():
    """Either fully off (guard present) or on and manual-only (no guard). Never a half state, never started by a push or a schedule."""
    t = text(".github/workflows/pages.yml")
    d = yaml.safe_load(t)
    triggers = d.get("on") or d.get(True)
    assert set(triggers) <= {"workflow_dispatch", "push"}, "must not run on a schedule or pull request"
    guard = d["jobs"]["deploy"].get("if", True)
    if guard is False:
        assert "DISABLED" in t and set(triggers) == {"workflow_dispatch"}
    else:
        assert "DISABLED" not in t and "if: false" not in t
    assert "upload-pages-artifact" in t and "deploy-pages" in t and "path: site" in t


def test_ci_runs_validate_tests_build_and_does_not_publish():
    t = text(".github/workflows/ci.yml")
    d = yaml.safe_load(t)
    assert "scripts/validate.py" in t and "pytest" in t and "scripts/build.py" in t
    assert "deploy-pages" not in t and "upload-pages-artifact" not in t
    assert "pull_request" in (d.get("on") or d.get(True))


def test_issue_templates_have_required_headings():
    assert "rule by rule" in text(".github/ISSUE_TEMPLATE/label_dispute.md").lower()
    assert "licence" in text(".github/ISSUE_TEMPLATE/new_setting.md").lower()
    assert "make reproduce" in text(".github/ISSUE_TEMPLATE/bug.md")
    pr = text(".github/PULL_REQUEST_TEMPLATE.md")
    for s in ("make validate", "make test", "make reproduce", "reviewed", "history"):
        assert s in pr, s


def test_open_questions_lists_every_item_the_report_promises():
    t = text("docs/OPEN_QUESTIONS.md")
    for s in ("Tenant-isolation", "R6", "licence paragraph", "CITATION.cff", "LICENSE-DATA", "Hosted Navigator", "CI", "publish", "attack"):
        assert s.lower() in t.lower(), s
    if "private:start" in t:        # the private working copy; the public export has these blocks stripped
        assert "permission" in t.lower() and "export_public" in t


def test_changelog_starts_at_v0_1_0_draft():
    assert re.search(r"^## v0\.1\.0-draft", text("CHANGELOG.md"), re.M)


def test_protocol_has_all_six_parts_and_the_exact_output_block():
    t = text("docs/PROTOCOL.md")
    for h in ("## A. Reproduce the data", "## B. Check one label by hand", "## C. Full independent relabelling", "## D. Check the gaps", "## E. Add a new control setting", "## F. Known limits"):
        assert h in t, h
    assert "PASS: all N files match" in t and "make reproduce" in t and "scripts/sample.py --calibration" in t and "scripts/agreement.py" in t
    assert "at least 95%" in t and "our choice, not a standard" in t


def test_project_repo_logo_and_domain_names_have_no_mitre_or_attack():
    import tomllib
    names = [tomllib.loads(text("pyproject.toml"))["project"]["name"], yaml.safe_load(text("CITATION.cff"))["title"],
             text("README.md").splitlines()[0], yaml.safe_load(text("CITATION.cff"))["repository-code"],
             "Agent Control Threat Coverage Matrix", "ACTCM"]
    for n in names:
        assert not re.search(r"mitre|att&ck|attack", n, re.I), n
    assert not [p for p in R.rglob("*") if p.is_file() and ".cache" not in p.parts and ".git" not in p.parts and re.search(r"logo|favicon|brand", p.name, re.I)], "no logo files"
    html = (R / "site" / "index.html").read_text(encoding="utf-8")
    assert not re.search(r'<link[^>]+rel="(icon|shortcut icon)"', html), "no favicon that could copy someone else's mark"
    assert "mitre" not in (R / "site" / "assets" / "style.css").read_text().lower()


def test_license_data_embeds_the_legal_text_with_the_recorded_hash():
    import hashlib
    t = text("LICENSE-DATA")
    a = t.index("----- BEGIN CC BY 4.0 LEGAL TEXT -----\n") + len("----- BEGIN CC BY 4.0 LEGAL TEXT -----\n")
    b = t.index("----- END CC BY 4.0 LEGAL TEXT -----")
    body = t[a:b]
    rec = yaml.safe_load(text("data/legal/ccby4_source.yml"))
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == rec["sha256"] and len(body.encode("utf-8")) == rec["bytes"]
    assert body.startswith("Creative Commons Attribution 4.0 International") and body.rstrip().endswith("Creative Commons may be contacted at creativecommons.org.")
    assert "TODO" + "(Tory)" not in t


def test_disclaimers_equal_the_text_tory_read_on_the_terms_page():
    page = (c.DATA / "legal" / "attack_disclaimers_from_terms_page_2026-11-04.txt").read_text(encoding="utf-8")
    lic = (c.DATA / "legal" / "attack_licence.txt").read_text(encoding="utf-8").split("Disclaimers\n-----------\n")[1]
    norm = lambda s: [" ".join(p.split()) for p in s.strip().split("\n\n")]
    assert norm(page) == norm(lic) and len(norm(page)) == 2
