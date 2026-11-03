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

    def fake_run_swarm(request, recipient, level, reason=None, on_event=None, **kw):
        swarm_calls.append((request, recipient, level, reason))
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


# ---- agent activity view ---------------------------------------------------

ACTIVITY_EVENTS = [
    {"kind": "thread_created", "agent": "Fact Scout", "text": "", "detail": "", "t": 0.5},
    {"kind": "delegate", "agent": "Fact Scout", "text": "Find facts for the Friday review", "detail": "", "t": 0.6},
    {"kind": "tool", "agent": "Fact Scout", "text": "web_fetch", "detail": "https://api.open-meteo.com/v1/forecast", "t": 2.0},
    {"kind": "reply", "agent": "Fact Scout", "text": "[calendar] Dentist at 3pm", "detail": "", "t": 4.5},
    {"kind": "delegate", "agent": "Critic", "text": "Vet: Something came up.", "detail": "", "t": 6.0},
    {"kind": "reply", "agent": "Critic", "text": "VERDICT: REVISE\nSCORE: 3\nHOLES:\n- too vague", "detail": "", "t": 8.0},
]


@pytest.fixture
def rich(monkeypatch):
    state = {"fail": False}

    def fake_run_swarm(request, recipient, level, reason=None, on_event=None, **kw):
        for e in ACTIVITY_EVENTS:
            on_event(dict(e))
        if state["fail"]:
            raise RuntimeError("boom")
        return SwarmResult(rounds=[
            Round(excuse="Something came up.", believability=3, holes=["vague"], verdict="revise"),
            Round(excuse="My dentist moved my appointment to 3pm.", believability=8, holes=[], verdict="accept"),
        ])

    monkeypatch.setattr(swarm_client, "run_swarm", fake_run_swarm)
    monkeypatch.setattr(memory, "save_excuse", lambda *a, **k: None)
    return state


def _texts(at):
    return [e.value for e in list(at.markdown) + list(at.caption) + list(at.text)]


def _run(at):
    _filled(at)
    _button(at, "Generate").click().run()
    return at


def test_activity_has_one_expander_per_agent_with_status_and_time(rich):
    at = _run(AppTest.from_file(APP).run())
    labels = [e.label for e in at.expander]
    assert any(l.startswith("Fact Scout") and "done" in l and "4.0s" in l for l in labels)
    assert any(l.startswith("Critic") and "done" in l for l in labels)
    assert any(l.startswith("Storyteller") and "waiting" in l for l in labels)


def test_agent_expander_shows_brief_reply_and_tool(rich):
    at = _run(AppTest.from_file(APP).run())
    texts = _texts(at)
    assert any("Find facts for the Friday review" in t for t in texts)
    assert any("[calendar] Dentist at 3pm" in t for t in texts)
    assert any("web_fetch" in t and "open-meteo" in t for t in texts)


def test_critic_reply_is_shown_as_verdict_score_and_holes(rich):
    at = _run(AppTest.from_file(APP).run())
    texts = _texts(at)
    assert any("Verdict: REVISE" in t and "3/10" in t for t in texts)
    assert any("too vague" in t for t in texts)


def test_full_timeline_lists_events_in_order(rich):
    at = _run(AppTest.from_file(APP).run())
    assert any(e.label == "Full timeline" for e in at.expander)
    timeline = "\n".join(t for t in _texts(at) if "Director → Fact Scout" in t or "Critic replied" in t)
    assert timeline.index("Director → Fact Scout") < timeline.index("Critic replied")


def test_activity_is_kept_when_the_swarm_fails(rich):
    rich["fail"] = True
    at = _run(AppTest.from_file(APP).run())
    assert any("boom" in e.value for e in at.error)
    assert any(e.label.startswith("Fact Scout") for e in at.expander)


def test_activity_survives_mark_as_used(rich):
    at = _run(AppTest.from_file(APP).run())
    _button(at, "Mark as used").click().run()
    assert any(e.label.startswith("Fact Scout") for e in at.expander)
