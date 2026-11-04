import math
import pytest
import agreement as ag


def test_kappa_worked_by_hand_two_classes():
    # 50 items: 20 yes/yes, 5 yes/no, 10 no/yes, 15 no/no.
    # po = 35/50 = 0.7. rater1 yes = 25/50 = 0.5, rater2 yes = 30/50 = 0.6.
    # pe = 0.5*0.6 + 0.5*0.4 = 0.5. kappa = (0.7 - 0.5) / (1 - 0.5) = 0.4.
    x = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15
    y = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    r = ag.kappa(x, y)
    assert r["n"] == 50 and math.isclose(r["po"], 0.7) and math.isclose(r["pe"], 0.5) and math.isclose(r["kappa"], 0.4)


def test_kappa_worked_by_hand_three_classes():
    # 10 items. rater1: A A A A B B B C C C ; rater2: A A A B B B C C C C
    # agreements: A:3, B:2 (items 5,6), C:3 (items 8,9,10)... positions 1-10:
    # r1: A A A A B B B C C C
    # r2: A A A B B B C C C C -> match at 1,2,3,5,6,8,9,10 = 8 of 10, po = 0.8
    # r1 counts A4 B3 C3; r2 counts A3 B3 C4. pe = (4*3 + 3*3 + 3*4)/100 = 33/100 = 0.33
    # kappa = (0.8-0.33)/(0.67) = 0.70149...
    x = list("AAAABBBCCC"); y = list("AAABBBCCCC")
    r = ag.kappa(x, y)
    assert math.isclose(r["po"], 0.8) and math.isclose(r["pe"], 0.33) and math.isclose(r["kappa"], 0.47 / 0.67)


def test_perfect_and_chance_and_worse():
    assert ag.kappa(list("ABAB"), list("ABAB"))["kappa"] == 1.0
    assert ag.kappa(list("AABB"), list("ABAB"))["kappa"] == 0.0
    assert ag.kappa(list("AABB"), list("BBAA"))["kappa"] == -1.0


def test_degenerate_single_label():
    assert ag.kappa(list("AAAA"), list("AAAA"))["kappa"] == 1.0   # pe == 1, full agreement
    assert ag.kappa(list("AAAA"), list("AAAB"))["pe"] < 1
    assert ag.kappa(list("AA"), list("AA"))["kappa"] == 1.0


def test_empty_and_mismatched():
    assert ag.kappa([], [])["kappa"] is None
    with pytest.raises(ValueError):
        ag.kappa(["a"], ["a", "b"])


def test_messy_pairing_ignores_missing_and_empty():
    a = {"t1": "X", "t2": "Y", "t3": "", "t4": "Z"}
    b = {"t1": "X", "t2": "X", "t3": "Q", "t5": "Z"}
    ids, x, y = ag._pair(a, b)
    assert ids == ["t1", "t2"] and ag.disagreements(ids, x, y) == [("t2", "Y", "X")]


def test_per_label_and_confusion():
    x, y = list("AABBC"), list("ABBBC")
    pl = ag.per_label(x, y)
    assert pl["A"]["rater1"] == 2 and pl["A"]["rater2"] == 1 and pl["A"]["both"] == 1
    assert ag.confusion(x, y)["A"] == {"A": 1, "B": 1}


def test_csv_duplicate_conflict_is_refused(tmp_path):
    p = tmp_path / "a.csv"; p.write_text("id,primary_tactic\nt1,A\nt1,B\n")
    with pytest.raises(SystemExit):
        ag.read_csv(str(p), "primary_tactic")


def test_csv_missing_column_is_refused(tmp_path):
    p = tmp_path / "a.csv"; p.write_text("id,other\nt1,A\n")
    with pytest.raises(SystemExit):
        ag.read_csv(str(p), "primary_tactic")
