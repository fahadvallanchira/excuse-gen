import json
from datetime import date

import pytest

import context
import memory


def cal(tmp_path, events):
    p = tmp_path / "cal.json"
    p.write_text(json.dumps(events))
    return str(p)


def ev(d, title="Thing"):
    return {"date": d, "time": "10:00", "title": title, "attendees": ["x"]}


def test_context_includes_request_recipient_level_city_and_today(tmp_path):
    out = context.build_context(
        "skip the offsite", "my manager", 2, city="Paris",
        today=date(2026, 11, 3), calendar_path=cal(tmp_path, []),
        db_path=str(tmp_path / "t.db"),
    )
    assert "skip the offsite" in out
    assert "my manager" in out
    assert "Level: 2" in out
    assert context.LEVELS[2] in out
    assert "City: Paris" in out
    assert "Today: 2026-11-03" in out


def test_context_lists_next_seven_days_only(tmp_path):
    events = [ev("2026-11-03", "Inside A"), ev("2026-11-09", "Inside B"), ev("2026-11-10", "Outside")]
    out = context.build_context(
        "x", "boss", 4, today=date(2026, 11, 3),
        calendar_path=cal(tmp_path, events), db_path=str(tmp_path / "t.db"),
    )
    assert "Inside A" in out and "Inside B" in out
    assert "Outside" not in out


def test_context_lists_past_excuses_normalized(tmp_path):
    p = str(tmp_path / "t.db")
    memory.save_excuse("  My Manager ", "my cat was ill", 1, p)
    out = context.build_context(
        "x", "my manager", 1, today=date(2026, 11, 3),
        calendar_path=cal(tmp_path, []), db_path=p,
    )
    assert "DOCUMENT: past-excuses" in out
    assert "my cat was ill" in out.split("DOCUMENT: past-excuses")[1]


def test_context_no_history_says_none(tmp_path):
    out = context.build_context(
        "x", "boss", 1, today=date(2026, 11, 3),
        calendar_path=cal(tmp_path, []), db_path=str(tmp_path / "t.db"),
    )
    assert "(none)" in out.split("DOCUMENT: past-excuses")[1]


def test_context_missing_calendar_does_not_raise(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    for path in (str(tmp_path / "nope.json"), str(bad)):
        out = context.build_context(
            "x", "boss", 1, today=date(2026, 11, 3),
            calendar_path=path, db_path=str(tmp_path / "t.db"),
        )
        assert "(calendar unavailable)" in out


@pytest.mark.parametrize("request_,recipient,level", [
    ("", "boss", 2), ("  ", "boss", 2), ("x", "", 2), ("x", "boss", 0), ("x", "boss", 5),
])
def test_context_rejects_blank_and_bad_level(tmp_path, request_, recipient, level):
    with pytest.raises(ValueError):
        context.build_context(request_, recipient, level, db_path=str(tmp_path / "t.db"))


def test_levels_has_keys_1_to_4():
    assert set(context.LEVELS) == {1, 2, 3, 4}
