#!/usr/bin/env python3
"""Synthetic messy-data tests for review/agreement.py.

    python3 review/tests/test_agreement.py            # runs all cases and prints each output
    python3 review/tests/test_agreement.py -v         # also prints the full report of every case

Expected numbers are worked out by hand (textbook kappa examples), not by calling agreement.py.
"""
import contextlib
import csv
import io
import random
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import agreement as ag  # noqa: E402

VERBOSE = "-v" in sys.argv
_w = ag.Warnings()
UNIVERSE, AI = ag.load_universe(HERE.parent.parent / "data" / "tasks" / "linuxarena", _w)
ITEMS = sorted(UNIVERSE)
assert len(ITEMS) == 64, len(ITEMS)

COLS = ["labeler", "item_id", "kind", "environment", "task_ids", "tactic_id", "tactic_name", "certainty", "note", "status", "answered_at"]
TMP = Path(tempfile.mkdtemp(prefix="agr_"))


def write(name, who, labels, *, status="saved", extra_cols=(), raw=None, bom=False, crlf=False, ts=None, note=None):
    """labels: list of (item, tactic_id_or_text). Returns path."""
    p = TMP / name
    cols = COLS + list(extra_cols)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n" if crlf else "\n")
    w.writerow(cols)
    for n, (item, lab) in enumerate(labels):
        tid = lab
        row = {"labeler": who, "item_id": item, "tactic_id": tid, "tactic_name": "", "certainty": "sure",
               "note": (note or {}).get(item, ""), "status": status, "answered_at": (ts or {}).get(n, "")}
        w.writerow([row.get(c, "") for c in cols])
    p.write_text(("﻿" if bom else "") + buf.getvalue(), encoding="utf-8")
    return p


def run(*paths, extra=()):
    out, buf = [], io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = ag.main([str(p) for p in paths] + list(extra))
    text = buf.getvalue()
    if VERBOSE:
        print("\n" + "-" * 70 + "\n" + text)
    return code, text


def line(text, start):
    return next(l for l in text.splitlines() if l.strip().startswith(start))


Y, N = "TA0001", "TA0002"   # two tactics for the textbook example


def textbook():
    """50 items: both Y 20, A=Y/B=N 5, A=N/B=Y 10, both N 15.  po=.70 pe=.50 kappa=.40 (hand-computed)."""
    items = ITEMS[:50]
    A, B = [], []
    spec = [(Y, Y)] * 20 + [(Y, N)] * 5 + [(N, Y)] * 10 + [(N, N)] * 15
    for it, (a, b) in zip(items, spec):
        A.append((it, a)); B.append((it, b))
    return A, B


class Cases(unittest.TestCase):
    def test_01_clean_textbook(self):
        A, B = textbook()
        code, t = run(write("a.csv", "ann", A), write("b.csv", "bob", B), extra=["--out-dir", str(TMP / "o1")])
        self.assertEqual(code, 0)
        self.assertIn("raw agreement: 35/50 = 0.700", t)
        self.assertIn("Cohen's kappa: 0.400", t)
        self.assertIn("shared 50", t)
        self.assertTrue((TMP / "o1" / "disagreements.csv").exists())
        self.assertEqual(len((TMP / "o1" / "disagreements.csv").read_text().splitlines()) - 1, 30)  # 15 items x 2 people
        # per-tactic: Y: A chose 25, B chose 30, both 20, either 35 -> 0.57
        self.assertRegex(line(t, "Initial Access"), r"25\s+30\s+20\s+35\s+0\.57")

    def test_02_row_order_does_not_matter(self):
        A, B = textbook()
        B2 = B[:]; random.Random(1).shuffle(B2)
        code, t = run(write("a.csv", "ann", A), write("b.csv", "bob", B2))
        self.assertIn("raw agreement: 35/50 = 0.700", t); self.assertIn("Cohen's kappa: 0.400", t)

    def test_03_missing_rows(self):
        A, B = textbook()
        B_missing = B[:-10]                      # bob skipped the last 10 items (the 'both N' ones)
        code, t = run(write("a.csv", "ann", A), write("b.csv", "bob", B_missing))
        # shared 40: both Y 20, A=Y B=N 5, A=N B=Y 10, both N 5 -> po .625 ; pA(Y)=25/40 pB(Y)=30/40
        # pe = .625*.75 + .375*.25 = .46875+.09375 = .5625 ; kappa = (.625-.5625)/.4375 = 0.14286
        self.assertIn("shared 40", t); self.assertIn("only ann: 10", t)
        self.assertIn("raw agreement: 25/40 = 0.625", t); self.assertIn("Cohen's kappa: 0.143", t)

    def test_04_duplicates(self):
        A, B = textbook()
        dup = B + [B[0], B[1]]                           # identical duplicates
        code, t = run(write("a.csv", "ann", A), write("b.csv", "bob", dup))
        self.assertIn("raw agreement: 35/50 = 0.700", t)    # not 37/52: duplicates are not double counted
        self.assertIn("shared 50", t)
        # Conflicting duplicate. Item 0: ann=Y, bob first says Y, then (later timestamp) N. The later row must win -> 34/50.
        B2 = B + [(B[0][0], N)]
        ts = {0: "2026-01-01T10:00:00Z", len(B): "2026-01-02T10:00:00Z"}
        code, t = run(write("a.csv", "ann", A), write("b2.csv", "bob", B2, ts=ts))
        self.assertIn("appear more than once with DIFFERENT tactics", t)
        self.assertIn("raw agreement: 34/50 = 0.680", t)
        # Same, but the row that is LATER in the file carries the EARLIER timestamp: timestamp wins, not file order -> still N -> 34/50
        B3 = [(B[0][0], N)] + B[1:] + [(B[0][0], Y)]
        ts = {0: "2026-01-02T10:00:00Z", len(B3) - 1: "2026-01-01T10:00:00Z"}
        code, t = run(write("a.csv", "ann", A), write("b3.csv", "bob", B3, ts=ts))
        self.assertIn("raw agreement: 34/50 = 0.680", t); self.assertIn("DIFFERENT tactics", t)
        # No timestamps at all: the later row in the file wins (and it is warned about)
        B4 = B + [(B[0][0], N)]
        code, t = run(write("a.csv", "ann", A), write("b4.csv", "bob", B4))
        self.assertIn("raw agreement: 34/50 = 0.680", t); self.assertIn("DIFFERENT tactics", t)

    def test_05_labeler_always_one_tactic(self):
        A, B = textbook()
        const = [(it, Y) for it, _ in B]
        code, t = run(write("a.csv", "ann", A), write("b.csv", "bob", const))
        self.assertIn("Cohen's kappa: 0.000", t)               # po = pA(Y) = .5 = pe -> exactly 0
        self.assertIn("caution: bob used only", t)
        both_const = run(write("c.csv", "cat", [(it, Y) for it, _ in A]), write("d.csv", "dan", const))[1]
        self.assertIn("Cohen's kappa: n/a", both_const)         # undefined, NOT 1.0 and no crash
        self.assertIn("undefined: both labelers used one single tactic", both_const)
        self.assertIn("raw agreement: 50/50 = 1.000", both_const)

    def test_06_typos_and_name_forms(self):
        items = ITEMS[:12]
        a = [(i, "TA0001") for i in items]
        b = [(items[0], "Initial Acess"),        # typo -> Initial Access
             (items[1], "initial access"),       # case
             (items[2], "Initial-Access"),       # hyphen
             (items[3], " ta0001 "),             # id, lower case + spaces
             (items[4], "Defense Evasion"),      # legacy name, not in v20 -> must NOT be guessed
             (items[5], "Persistance"),          # typo of a different tactic
             (items[6], "banana"),               # junk
             (items[7], ""),                     # empty
             (items[8], "Initial Access"), (items[9], "Initial Access"), (items[10], "Initial Access"), (items[11], "Initial Access")]
        code, t = run(write("a.csv", "ann", a), write("b.csv", "bob", b))
        self.assertIn("'Initial Acess' read as Initial Access", t)
        self.assertIn("'Persistance' read as Persistence", t)
        self.assertIn("tactic 'Defense Evasion' not recognised", t)
        self.assertIn("tactic 'banana' not recognised", t)
        # shared = 12 - 3 invalid (Defense Evasion, banana, empty) = 9 ; agree = 8 (all but Persistance)
        self.assertIn("shared 9", t); self.assertIn("raw agreement: 8/9 = 0.889", t)

    def test_07_none_fits(self):
        items = ITEMS[:10]
        a = [(i, "NONE") for i in items[:4]] + [(i, "TA0001") for i in items[4:8]] + [(items[8], "TA0002"), (items[9], "TA0002")]
        b = [(items[0], "none fits"), (items[1], "None Fits"), (items[2], "NONE"), (items[3], "TA0001"),
             (items[4], "TA0001"), (items[5], "TA0001"), (items[6], "none"), (items[7], "TA0001"), (items[8], "TA0002"), (items[9], "TA0002")]
        code, t = run(write("a.csv", "ann", a), write("b.csv", "bob", b))
        # agree: items0,1,2 (NONE), 4,5 (TA0001), 7, 8, 9  = 8 ; disagree: 3 (NONE vs TA0001), 6 (TA0001 vs NONE)
        self.assertIn("raw agreement: 8/10 = 0.800", t)
        self.assertRegex(line(t, "none fits"), r"4\s+4\s+3\s+5")   # A chose NONE 4, B 4, both 3, either 5

    def test_08_empty_and_broken_files(self):
        A, B = textbook()
        good_a, good_b = write("a.csv", "ann", A), write("b.csv", "bob", B)
        empty = TMP / "empty.csv"; empty.write_text("")
        blank = TMP / "blank.csv"; blank.write_text("\n  \n")
        hdr = TMP / "hdr.csv"; hdr.write_text(",".join(COLS) + "\n")
        junk = TMP / "junk.csv"; junk.write_text("foo,bar\n1,2\n")
        missing = TMP / "nope.csv"
        # one good + empties -> must stop, not invent a number
        code, t = run(good_a, empty, hdr)
        self.assertEqual(code, 2); self.assertIn("NEED TWO LABELERS", t); self.assertNotIn("raw agreement:", t)
        self.assertIn("file is empty", t); self.assertIn("header only", t)
        # two good + all kinds of broken -> the good pair is unaffected and the broken ones are named
        code, t = run(good_a, good_b, empty, blank, hdr, junk, missing)
        self.assertEqual(code, 0); self.assertIn("Cohen's kappa: 0.400", t)
        self.assertIn("junk.csv: header lacks item_id", t); self.assertIn("nope.csv: cannot read", t)
        # all empty
        code, t = run(empty, blank)
        self.assertEqual(code, 2)

    def test_09_same_name_two_files_is_not_two_people(self):
        A, B = textbook()
        code, t = run(write("a.csv", "sam", A), write("b.csv", "sam", B))
        self.assertEqual(code, 2)                                   # merged into one person -> refuse
        self.assertIn("appears in 2 files", t); self.assertIn("NEED TWO LABELERS", t)

    def test_10_unknown_items_drafts_bom_crlf(self):
        A, B = textbook()
        B2 = B + [("fake_env/not_a_task", Y)]
        pa = write("a.csv", "ann", A, bom=True, crlf=True)          # Excel-style file
        pb = write("b.csv", "bob", B2, bom=True, crlf=True)
        code, t = run(pa, pb)
        self.assertIn("raw agreement: 35/50 = 0.700", t); self.assertIn("'fake_env/not_a_task' is not a known review item", t)
        # drafts are left out and counted
        pd = write("d.csv", "dan", B, status="draft")
        code, t = run(pa, pd)
        self.assertEqual(code, 2); self.assertIn("50 row(s) with status 'draft'", t)

    def test_11_three_labelers_and_partial_overlap(self):
        A, B = textbook()
        C = [(i, Y) for i, _ in B[:25]]                              # third person did only 25
        code, t = run(write("a.csv", "ann", A), write("b.csv", "bob", B), write("c.csv", "cat", C))
        self.assertIn("=== ann vs bob ===", t); self.assertIn("=== ann vs cat ===", t); self.assertIn("=== bob vs cat ===", t)
        self.assertEqual(t.count("shared 25"), 2)

    def test_12_owner_vs_ai(self):
        # owner picks the AI label on 10 items and a wrong one on 4; blind second labeler picks arbitrary
        items = ITEMS[:14]
        own = [(i, AI[i]["primary"]) for i in items[:10]] + [(i, "TA0043" if AI[i]["primary"] != "TA0043" else "TA0042") for i in items[10:]]
        pown = write("o.csv", "tory", own, extra_cols=["decision", "final_tactic_id", "final_tactic_name"], status="revealed")
        pb = write("b.csv", "bob", [(i, AI[i]["primary"]) for i in items])
        code, t = run(pown, pb)
        self.assertIn("owner = tory; items compared: 14 of 64", t)
        self.assertIn("raw agreement: 10/14 = 0.714", t.split("owner's blind picks vs AI labels")[1])
        # template group item uses the group's AI label
        g = "template/rce"
        pg = write("g.csv", "tory", [(g, "TA0001")], extra_cols=["decision"], status="revealed")
        pg2 = write("g2.csv", "bob", [(g, "TA0001")])
        code, t = run(pg, pg2)
        self.assertIn("raw agreement: 1/1 = 1.000", t.split("owner's blind picks vs AI labels")[1])

    def test_13_certainty_and_notes_in_disagreements(self):
        A, B = textbook()
        notes = {B[0][0]: "unsure, goal says 'erase'"}
        # force a disagreement on item 0 for bob
        B2 = [(B[0][0], N if A[0][1] == Y else Y)] + B[1:]
        code, t = run(write("a.csv", "ann", A), write("b.csv", "bob", B2, note=notes))
        self.assertIn("note: unsure, goal says 'erase'", t)


if __name__ == "__main__":
    unittest.main(argv=[a for a in sys.argv if a != "-v"], verbosity=2)
