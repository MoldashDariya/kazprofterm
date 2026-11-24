import json
import re

import numpy as np
import pytest

from kpt_exp import REF_CONDITIONS, analyze, run_judges, stimuli
from kpt_exp import simulate


@pytest.fixture(scope="module")
def data():
    terms, items = stimuli.load_terms(), stimuli.load_items()
    return terms, items, stimuli.build(items, terms)


def test_items_are_consistent_with_terms(data):
    terms, items, _ = data
    assert stimuli.check_items(items, terms) == []


def test_minimal_pairs_differ_only_in_the_term(data):
    _, _, rows = data
    by = {(r["item_id"], r["quality"], r["term_form"]): r for r in rows}
    for (iid, q, tf), r in by.items():
        if tf != "teacher":
            continue
        o = by[(iid, q, "official")]
        assert r["answer_text"].replace(r["term_text"], "<T>") == o["answer_text"].replace(o["term_text"], "<T>")
        assert r["answer_text"] != o["answer_text"]


def test_design_size(data):
    _, items, rows = data
    assert len(items) == 25
    assert len(rows) == 25 * 2 * 2


def test_rendered_prompts(data):
    terms, items, rows = data
    system, tpl = run_judges.load_prompt()
    it = {i["item_id"]: i for i in items}
    r = rows[0]
    item, t = it[r["item_id"]], terms[r["term_id"]]
    users = {ref: run_judges.render_user(tpl, item, t, ref, r["answer_text"]) for ref in REF_CONDITIONS}
    for u in users.values():
        assert "{{" not in u and "{OFF}" not in u and "{TERM}" not in u
        assert r["answer_text"] in u
    assert item["official"] in users["R_KK"]
    assert "accepted_term_variants" in users["R_KK_GLOSS"]
    assert "accepted_term_variants" not in users["R_KK"]
    assert t["kk"] in users["R_KK_GLOSS"].split("<<<ANSWER_START>>>")[0]
    assert item["question_en"] in users["R_EN"]
    # nothing about the experimental condition leaks into the request
    for u in users.values():
        assert "teacher" not in u and "official" not in u


VALID = {"relevance_1to5": 4, "correctness_1to5": 4, "completeness_1to5": 3, "terminology_1to5": 5,
         "overall_1to5": 4, "addressed_essential_points": [1, 2], "missed_essential_points": [3],
         "evidence": "Mentions points 1 and 2."}


def test_validation_accepts_valid():
    obj, err = run_judges.parse(json.dumps(VALID), [1, 2, 3])
    assert err is None


@pytest.mark.parametrize("mutate,expected", [
    (lambda o: o.update(overall_1to5=6), "overall_1to5"),
    (lambda o: o.update(overall_1to5=True), "overall_1to5"),
    (lambda o: o.update(missed_essential_points=[2, 3]), "points_partition"),
    (lambda o: o.update(missed_essential_points=[]), "points_partition"),
    (lambda o: o.pop("evidence"), "keys"),
    (lambda o: o.update(extra=1), "keys"),
])
def test_validation_rejects(mutate, expected):
    o = json.loads(json.dumps(VALID))
    mutate(o)
    _, err = run_judges.parse(json.dumps(o), [1, 2, 3])
    assert err == expected


def test_one_fence_is_stripped():
    _, err = run_judges.parse("```json\n" + json.dumps(VALID) + "\n```", [1, 2, 3])
    assert err is None
    _, err = run_judges.parse("Here it is: " + json.dumps(VALID), [1, 2, 3])
    assert err == "json"


def test_simulator_is_deterministic():
    p = simulate.DEFAULT
    a = simulate.judge_response("Q01", "full", "teacher", "R_KK", 1, 4, [1, 2, 3], p, seed=1)
    b = simulate.judge_response("Q01", "full", "teacher", "R_KK", 1, 4, [1, 2, 3], p, seed=1)
    assert a == b
    assert run_judges.validate(a, [1, 2, 3]) is None


def test_holm():
    adj = analyze.holm([0.01, 0.04, 0.03])
    assert np.allclose(adj, [0.03, 0.06, 0.06])


def test_tost():
    rng = np.random.default_rng(0)
    assert analyze.tost(rng.normal(0, 0.1, 50)) < 0.05
    assert analyze.tost(rng.normal(0.5, 0.1, 50)) > 0.05


def test_icc_perfect_agreement():
    import pandas as pd
    df = pd.DataFrame({"g": [1, 1, 2, 2, 3, 3], "v": [1, 1, 3, 3, 5, 5]})
    assert analyze.icc1(df, "v", "g") == pytest.approx(1.0)
