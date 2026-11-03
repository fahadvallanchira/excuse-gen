import json
from types import SimpleNamespace as NS

import pytest

import swarm_client
from swarm_client import run_swarm

RESULT = {"rounds": [
    {"excuse": "Something came up.", "believability": 3, "holes": ["vague"], "verdict": "revise"},
    {"excuse": "My dentist moved my appointment.", "believability": 8, "holes": [], "verdict": "accept"},
]}


def text_block(t):
    return NS(type="text", text=t)


def msg(t, **kw):
    return NS(type="agent.message", content=[text_block(t)], **kw)


IDLE = NS(type="session.status_idle")


class FakeStream:
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self.events)


class FakeEvents:
    def __init__(self, events):
        self.stream_obj = FakeStream(events)
        self.sent = []

    def stream(self, session_id):
        return self.stream_obj

    def send(self, session_id, events):
        self.sent.append((session_id, events))


class FakeClient:
    def __init__(self, events):
        self.created = []
        self.events = FakeEvents(events)
        outer = self

        class Sessions:
            events = outer.events

            def create(self, **kw):
                outer.created.append(kw)
                return NS(id="sess_1")

        self.beta = NS(sessions=Sessions())


@pytest.fixture
def ids(tmp_path, monkeypatch):
    (tmp_path / ".coordinator_id").write_text("agent_dir\n")
    (tmp_path / ".environment_id").write_text("env_1\n")
    monkeypatch.setattr(swarm_client, "build_context", lambda *a, **k: "CTX")
    return str(tmp_path)


def go(events, ids, **kw):
    client = FakeClient(events)
    return client, run_swarm("Friday review", "my manager", 2, client=client, ids_dir=ids, **kw)


def test_returns_parsed_result_and_sends_one_user_message(ids):
    client, result = go([NS(type="session.thread_created", agent_name="Fact Scout"),
                         msg(json.dumps(RESULT)), IDLE], ids)
    assert len(result.rounds) == 2
    assert len(client.events.sent) == 1
    ev = client.events.sent[0][1][0]
    assert ev["type"] == "user.message"
    assert "CTX" in ev["content"][0]["text"]


def test_session_created_with_ids(ids):
    client, _ = go([msg(json.dumps(RESULT)), IDLE], ids)
    assert client.created[0]["agent"] == "agent_dir"
    assert client.created[0]["environment_id"] == "env_1"


def test_on_event_receives_kinds_in_order(ids):
    seen = []
    go([NS(type="session.thread_created", agent_name="Fact Scout"),
        NS(type="session.thread_status_running", agent_name="Fact Scout"),
        NS(type="agent.thread_message_sent", to_agent_name="Critic", content=[text_block("vet")]),
        NS(type="agent.thread_message_received", from_agent_name="Critic", content=[text_block("ok")]),
        NS(type="agent.tool_use", name="web_fetch"),
        msg(json.dumps(RESULT)), IDLE], ids, on_event=seen.append)
    assert [e["kind"] for e in seen] == ["thread_created", "thread_running", "delegate", "reply", "tool", "message"]
    assert all({"kind", "agent", "text"} <= e.keys() for e in seen)
    assert seen[2]["agent"] == "Critic" and seen[3]["agent"] == "Critic"


def test_stream_end_without_idle_uses_collected_text(ids):
    _, result = go([msg(json.dumps(RESULT))], ids)
    assert len(result.rounds) == 2


def test_no_output_raises_runtime_error(ids):
    with pytest.raises(RuntimeError):
        go([IDLE], ids)


def test_prose_output_falls_back(ids):
    _, result = go([msg("My dentist moved my appointment."), IDLE], ids)
    assert len(result.rounds) == 1
    assert result.rounds[0].verdict == "revise"


def test_interim_chatter_before_json_still_parses(ids):
    _, result = go([msg("Delegating {now}."), msg(json.dumps(RESULT)), IDLE], ids)
    assert len(result.rounds) == 2


def test_sub_thread_messages_are_ignored(ids):
    _, result = go([msg("VERDICT: ACCEPT\nSCORE: 8", session_thread_id="thr_1"),
                    msg(json.dumps(RESULT)), IDLE], ids)
    assert len(result.rounds) == 2


def test_timeout_raises(ids):
    ticks = iter([0, 1000])
    client = FakeClient([msg(json.dumps(RESULT)), IDLE])
    with pytest.raises(TimeoutError):
        run_swarm("x", "boss", 2, client=client, ids_dir=ids, max_seconds=10, clock=lambda: next(ticks))


@pytest.mark.parametrize("request_,recipient,level", [
    ("", "boss", 2), ("  ", "boss", 2), ("x", "", 2), ("x", "boss", 0), ("x", "boss", 5)])
def test_blank_input_raises_before_any_client_call(ids, request_, recipient, level):
    client = FakeClient([])
    with pytest.raises(ValueError):
        run_swarm(request_, recipient, level, client=client, ids_dir=ids)
    assert client.created == []


def test_missing_id_files_raises_filenotfound_with_hint(tmp_path):
    with pytest.raises(FileNotFoundError, match="create_coordinator.py"):
        run_swarm("x", "boss", 2, client=FakeClient([]), ids_dir=str(tmp_path))


def test_on_event_errors_do_not_abort(ids):
    def boom(e):
        raise RuntimeError("ui")
    _, result = go([msg(json.dumps(RESULT)), IDLE], ids, on_event=boom)
    assert len(result.rounds) == 2


def test_calendar_and_db_paths_are_forwarded(ids, monkeypatch):
    got = {}
    monkeypatch.setattr(swarm_client, "build_context", lambda *a, **k: got.update(k) or "CTX")
    go([msg(json.dumps(RESULT)), IDLE], ids, calendar_path="cal.json", db_path="x.db")
    assert got["calendar_path"] == "cal.json" and got["db_path"] == "x.db"
