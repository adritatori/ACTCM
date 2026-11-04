"""Start-here selection on skewed, tiny and degenerate candidate pools."""
import review_sheet as rs


def cand(i, setting, tactic, env="e"):
    return dict(id=i, setting=setting, environment=env, tactic=tactic)


def test_spreads_across_tactics_and_settings():
    pool = [cand(f"a{i}", "linuxarena", "TA0010", f"env{i}") for i in range(30)]       # one huge tactic
    pool += [cand("b1", "vllm", "TA0112"), cand("b2", "refactor_arena", "TA0112"),
             cand("c1", "linuxarena-extras", "TA0040"), cand("c2", "vllm", "TA0040"),
             cand("d1", "vllm", "TA0003"), cand("e1", "linuxarena", "TA0005"), cand("e2", "linuxarena", "TA0005", "x")]
    picks, diag = rs.select_start_here(pool, n_min=20)
    assert diag["n"] >= 12
    assert {p["tactic"] for p in picks} == {"TA0010", "TA0112", "TA0040", "TA0003", "TA0005"}
    first_round = [p["tactic"] for p in picks[:5]]
    assert len(set(first_round)) == 5, "first picks should cover different tactics"


def test_template_families_are_not_repeated():
    pool = [cand("aw_rce", "linuxarena", "TA0001", "aw"), cand("fi_rce", "linuxarena", "TA0001", "fi"),
            cand("ws_rce", "linuxarena", "TA0001", "ws"), cand("other", "vllm", "TA0001")]
    picks, _ = rs.select_start_here(pool, n_min=4, per_tactic=4)
    assert sum(rs.template_family(p["id"]) == "rce" for p in picks) == 1


def test_fewer_candidates_than_requested_reports_shortfall():
    picks, diag = rs.select_start_here([cand("x", "vllm", "TA0010")], n_min=20)
    assert len(picks) == 1 and diag["shortfall"] == 19


def test_empty_pool():
    picks, diag = rs.select_start_here([], n_min=20)
    assert picks == [] and diag["shortfall"] == 20


def test_deterministic_regardless_of_input_order():
    pool = [cand(f"t{i}", s, t, f"e{i}") for i, (s, t) in enumerate(
        [("vllm", "TA0010"), ("linuxarena", "TA0010"), ("vllm", "TA0112"), ("linuxarena", "TA0112")] * 6)]
    a, _ = rs.select_start_here(pool, n_min=8)
    b, _ = rs.select_start_here(list(reversed(pool)), n_min=8)
    assert [x["id"] for x in a] == [x["id"] for x in b]


def test_cap_is_raised_to_reach_minimum():
    pool = [cand(f"a{i}", "vllm" if i % 2 else "linuxarena", "TA0010", f"e{i}") for i in range(10)] + \
           [cand(f"b{i}", "vllm", "TA0040", f"f{i}") for i in range(10)]
    picks, diag = rs.select_start_here(pool, n_min=12, per_tactic=2)
    assert diag["n"] >= 12 and diag["shortfall"] == 0


def test_at_most_two_template_tasks_in_total():
    pool = [cand(f"{p}_{fam}", "linuxarena", t, p) for p in ("aw", "fi", "ws", "tt", "mp") for fam, t in
            (("rce", "TA0001"), ("reverse_shell", "TA0011"), ("run_malware_live", "TA0002"), ("run_malware_delayed", "TA0002"))]
    pool += [cand(f"x{i}", "vllm", "TA0010", f"e{i}") for i in range(10)]
    picks, _ = rs.select_start_here(pool, n_min=12, per_tactic=3)
    assert sum(rs.template_family(p["id"]) is not None for p in picks) <= 2


def test_pool_of_only_templates_gives_at_most_two():
    pool = [cand(f"{p}_rce", "linuxarena", "TA0001", p) for p in ("aw", "fi", "ws", "tt", "mp")]
    picks, diag = rs.select_start_here(pool, n_min=20, per_tactic=5)
    assert len(picks) == 1 and diag["shortfall"] == 19   # same family twice is also refused


def test_real_start_here_list_meets_the_brief():
    import csv
    import common as c
    import labels as L
    rows = list(csv.DictReader(open(c.DATA / "generated" / "start_here.csv")))
    tasks = {(e, i): t for (e, i), (_, t) in L.load_tasks().items()}
    assert len(rows) >= 20
    assert sum(rs.template_family(r["id"]) is not None for r in rows) <= 2
    assert len({r["tactic"] for r in rows}) >= 6 and len({r["setting"] for r in rows}) == len(c.visible_settings())
    assert all(c.is_public_setting(r["setting"]) for r in rows), "start-here must not list a hidden setting"
    audit = c.load_yaml(c.DATA / "audits" / "seed_steps_r2.yml")["tasks"]
    for r in rows:
        t = tasks[(r["environment"], r["id"])]
        assert t["label_status"] == "ai_cross_checked" and t["labels"]["confidence"] == "clear"
        assert t.get("scorer_status") != "planned_not_implemented"
        assert not any(x["verdict"] == "unsupported" for x in audit.get(f"{r['environment']}/{r['id']}", []))
