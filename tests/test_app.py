from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import memory
import swarm_client
from context import LEVELS
from schema import Round, SwarmResult

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def fakes(monkeypatch):
    swarm_calls = []
    saved = []

    def fake_run_swarm(request, recipient, level, city="London", on_event=None, **kw):
        swarm_calls.append((request, recipient, level, city))
        if on_event:
            on_event({"kind": "thread_created", "agent": "Fact Scout", "text": ""})
            on_event({"kind": "reply", "agent": "Critic", "text": ""})
        return SwarmResult(
            rounds=[
                Round(excuse="Something came up.", believability=3, holes=["vague"], verdict="revise"),
                Round(excuse="My dentist moved my appointment to 3pm.", believability=8, holes=[], verdict="accept"),
            ]
        )

    def fake_save(recipient, text, level, db_path=None):
        saved.append((recipient, text, level))

    monkeypatch.setattr(swarm_client, "run_swarm", fake_run_swarm)
    monkeypatch.setattr(memory, "save_excuse", fake_save)
    return swarm_calls, saved


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def _filled(at):
    at.text_input[0].set_value("Friday 3pm review")
    at.text_input[1].set_value("my manager")
    return at


def test_blank_inputs_warn_and_do_not_call_swarm(fakes):
    swarm_calls, _ = fakes
    at = AppTest.from_file(APP).run()
    _button(at, "Generate").click().run()
    assert any("Fill in both fields." in w.value for w in at.warning)
    assert swarm_calls == []


def test_generate_shows_two_rounds_and_final_code(fakes):
    at = _filled(AppTest.from_file(APP).run())
    _button(at, "Generate").click().run()
    labels = [e.label for e in at.expander]
    assert any("Round 1: believability 3/10" in l for l in labels)
    assert any("Round 2: believability 8/10" in l for l in labels)
    assert len(at.code) == 1
    assert at.code[0].value == "My dentist moved my appointment to 3pm."


def test_mark_as_used_saves_and_keeps_rounds(fakes):
    _, saved = fakes
    at = _filled(AppTest.from_file(APP).run())
    _button(at, "Generate").click().run()
    _button(at, "Mark as used").click().run()
    assert saved == [("my manager", "My dentist moved my appointment to 3pm.", 2)]
    assert any("Saved." in s.value for s in at.success)
    labels = [e.label for e in at.expander]
    assert any("Round 1" in l for l in labels) and any("Round 2" in l for l in labels)


def test_swarm_error_is_shown(fakes, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(swarm_client, "run_swarm", boom)
    at = _filled(AppTest.from_file(APP).run())
    _button(at, "Generate").click().run()
    assert any("boom" in e.value for e in at.error)


def test_level_caption_follows_default_slider(fakes):
    at = AppTest.from_file(APP).run()
    assert LEVELS[2] in [c.value for c in at.caption]
