import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from memory import past_excuses_for, save_excuse
from swarm_client import run_swarm

ROOT = Path(__file__).resolve().parent.parent
CALENDAR = ROOT / "data" / "calendar.json"

RESULT = {"rounds": [
    {"excuse": "Something came up.", "believability": 3, "holes": ["vague"], "verdict": "revise"},
    {"excuse": "My dentist moved my appointment.", "believability": 8, "holes": [], "verdict": "accept"},
]}

IDLE = NS(type="session.status_idle")


def msg(t):
    return NS(type="agent.message", content=[NS(type="text", text=t)])


class FakeStream:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self.events)


class FakeClient:
    def __init__(self, events):
        self.created = []
        self.sent = []
        outer = self

        class Events:
            def stream(self, session_id):
                return FakeStream(events)

            def send(self, session_id, events):
                outer.sent.append(events)

        class Sessions:
            events = Events()

            def create(self, **kw):
                outer.created.append(kw)
                return NS(id="sess_1")

        self.beta = NS(sessions=Sessions())


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".coordinator_id").write_text("agent_dir\n")
    (tmp_path / ".environment_id").write_text("env_1\n")
    return tmp_path


def go(events, request="Friday 3pm review", recipient="my manager", level=2):
    client = FakeClient(events)
    result = run_swarm(request, recipient, level, client=client, ids_dir=".",
                       calendar_path=str(CALENDAR))
    return client, result


def test_session_message_contains_real_context(env):
    save_excuse("  My Manager ", "dentist", 2)
    client, _ = go([msg(json.dumps(RESULT)), IDLE])
    text = client.sent[0][0]["content"][0]["text"]
    assert "dentist" in text
    assert "Friday 3pm review" in text
    calendar_section = text.split("DOCUMENT: calendar.md")[1].split("DOCUMENT: past-excuses.md")[0]
    assert "(calendar unavailable)" not in calendar_section  # seed file was read


def test_revise_then_accept_flow_reaches_ui_shape(env):
    _, result = go([msg(json.dumps(RESULT)), IDLE])
    assert result.final_excuse == RESULT["rounds"][1]["excuse"]
    assert result.rounds[0].verdict == "revise"


def test_prose_director_output_still_returns_a_result(env):
    _, result = go([msg("Just tell them your cat is ill."), IDLE])
    assert len(result.rounds) == 1
    assert "cat is ill" in result.final_excuse


def test_seed_calendar_is_valid():
    events = json.loads(CALENDAR.read_text())
    assert len(events) >= 6
    for e in events:
        assert {"date", "time", "title", "attendees"} <= set(e)


def test_seed_script_leaves_two_excuses(env):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_demo.py")], cwd=env,
                   env={**os.environ, "PYTHONPATH": str(ROOT)}, check=True)
    assert len(past_excuses_for("my manager")) == 2


def test_blank_recipient_never_creates_session(env):
    client = FakeClient([IDLE])
    with pytest.raises(ValueError):
        run_swarm("x", "  ", 2, client=client, ids_dir=".")
    assert client.created == []
