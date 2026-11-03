import json

import pytest

from schema import parse_result

TWO_ROUNDS = {
    "rounds": [
        {"excuse": "Something came up.", "believability": 3, "holes": ["vague"], "verdict": "revise"},
        {"excuse": "My dentist moved my appointment to 3pm.", "believability": 8, "holes": [], "verdict": "accept"},
    ]
}


def test_parse_bare_json():
    r = parse_result(json.dumps(TWO_ROUNDS))
    assert len(r.rounds) == 2
    assert r.final_excuse == "My dentist moved my appointment to 3pm."


def test_parse_fenced_json():
    r = parse_result("```json\n" + json.dumps(TWO_ROUNDS) + "\n```")
    assert len(r.rounds) == 2


def test_parse_json_with_prose_around_it():
    r = parse_result("Here you go:\n" + json.dumps(TWO_ROUNDS) + "\nHope that helps.")
    assert r.rounds[1].verdict == "accept"


def test_prose_falls_back_to_single_round():
    text = "Sorry, my dentist moved my appointment."
    r = parse_result(text)
    assert len(r.rounds) == 1
    rd = r.rounds[0]
    assert (rd.excuse, rd.believability, rd.holes, rd.verdict) == (text, 0, ["unparsed output"], "revise")


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_raises(text):
    with pytest.raises(ValueError):
        parse_result(text)


def test_bad_verdict_value_falls_back():
    bad = {"rounds": [{"excuse": "x", "believability": 5, "holes": [], "verdict": "maybe"}]}
    r = parse_result(json.dumps(bad))
    assert r.rounds[0].holes == ["unparsed output"]


def test_empty_rounds_falls_back():
    r = parse_result('{"rounds": []}')
    assert len(r.rounds) == 1
    assert r.rounds[0].holes == ["unparsed output"]


def test_uppercase_verdict_and_string_score_are_normalised():
    data = {"rounds": [{"excuse": "x", "believability": "8", "holes": [], "verdict": "ACCEPT"}]}
    r = parse_result(json.dumps(data))
    assert r.rounds[0].verdict == "accept"
    assert r.rounds[0].believability == 8
