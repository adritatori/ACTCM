#!/usr/bin/env python3
"""Inter-rater agreement for two label files.

  agreement.py ours.csv yours.csv [--column primary_tactic]

Each CSV needs an `id` column and the label column. Prints Cohen's kappa overall and per label
(one-vs-rest), the number of items, a confusion table, and the disagreement list.
Kappa is only computed over items present in BOTH files with a non-empty label.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict


def _pair(a: dict, b: dict):
    ids = sorted(k for k in a.keys() & b.keys() if a[k] not in (None, "") and b[k] not in (None, ""))
    return ids, [a[i] for i in ids], [b[i] for i in ids]


def kappa(x: list, y: list) -> dict:
    """Cohen's kappa for two equal-length label lists.

    kappa = (po - pe) / (1 - pe). If pe == 1 (both raters used one label only):
    kappa is 1.0 when they agree on everything and undefined (None) otherwise.
    """
    if len(x) != len(y):
        raise ValueError("label lists differ in length")
    n = len(x)
    if n == 0:
        return dict(n=0, po=None, pe=None, kappa=None)
    po = sum(1 for p, q in zip(x, y) if p == q) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum(cx[k] * cy[k] for k in cx.keys() | cy.keys()) / (n * n)
    if pe == 1:
        k = 1.0 if po == 1 else None
    else:
        k = (po - pe) / (1 - pe)
    return dict(n=n, po=po, pe=pe, kappa=k)


def per_label(x: list, y: list) -> dict:
    out = {}
    for lab in sorted(set(x) | set(y)):
        bx = [v == lab for v in x]
        by = [v == lab for v in y]
        r = kappa(bx, by)
        r.update(rater1=sum(bx), rater2=sum(by), both=sum(1 for p, q in zip(bx, by) if p and q))
        out[lab] = r
    return out


def confusion(x: list, y: list) -> dict:
    t = defaultdict(Counter)
    for p, q in zip(x, y):
        t[p][q] += 1
    return {k: dict(v) for k, v in sorted(t.items())}


def disagreements(ids, x, y):
    return [(i, p, q) for i, p, q in zip(ids, x, y) if p != q]


def read_csv(path: str, column: str) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if rows and ("id" not in rows[0] or column not in rows[0]):
        raise SystemExit(f"{path}: needs columns 'id' and {column!r}")
    out = {}
    for r in rows:
        key, val = (r["id"] or "").strip(), (r[column] or "").strip()
        if key in out and out[key] != val:
            raise SystemExit(f"{path}: id {key!r} appears twice with different labels")
        out[key] = val
    return out


def interpret(k) -> str:
    if k is None:
        return "undefined (one rater used a single label)"
    for hi, word in ((0.0, "no better than chance or worse"), (0.2, "slight"), (0.4, "fair"), (0.6, "moderate"),
                     (0.8, "substantial"), (1.01, "almost perfect")):
        if k <= hi or hi == 1.01:
            return word
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ours"); ap.add_argument("yours"); ap.add_argument("--column", default="primary_tactic")
    a = ap.parse_args()
    A, B = read_csv(a.ours, a.column), read_csv(a.yours, a.column)
    ids, x, y = _pair(A, B)
    k = kappa(x, y)
    print(f"items compared: {k['n']} (only in file 1: {len(A.keys() - B.keys())}, only in file 2: {len(B.keys() - A.keys())})")
    if k["n"]:
        print(f"observed agreement {k['po']:.3f}; chance agreement {k['pe']:.3f}; Cohen's kappa "
              f"{'n/a' if k['kappa'] is None else format(k['kappa'], '.3f')} ({interpret(k['kappa'])}, "
              "Landis & Koch wording)")
        print("\nper label (one-vs-rest):")
        for lab, r in per_label(x, y).items():
            print(f"  {lab:12} rater1={r['rater1']:3} rater2={r['rater2']:3} both={r['both']:3} kappa="
                  f"{'n/a' if r['kappa'] is None else format(r['kappa'], '.3f')}")
        print("\nconfusion (rows = file 1, columns = file 2):")
        for r1, row in confusion(x, y).items():
            print(f"  {r1}: {row}")
        print("\ndisagreements:")
        for i, p, q in disagreements(ids, x, y):
            print(f"  {i}: {p} vs {q}")


if __name__ == "__main__":
    main()
