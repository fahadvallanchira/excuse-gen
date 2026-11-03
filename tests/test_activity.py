from activity import AGENTS, ActivityTracker, parse_critic


def ev(kind, agent="", text="", t=0.0, detail=""):
    return {"kind": kind, "agent": agent, "text": text, "t": t, "detail": detail}


def test_new_tracker_has_five_waiting_agents():
    tr = ActivityTracker()
    assert AGENTS == ["Fact Scout", "Historian", "Recipient Profiler", "Storyteller", "Critic"]
    assert [a.name for a in tr.agents.values()] == AGENTS
    assert all(a.status == "waiting" for a in tr.agents.values())


def test_thread_created_marks_agent_working_with_start_time():
    tr = ActivityTracker()
    tr.handle(ev("thread_created", "Fact Scout", t=1.5))
    a = tr.agents["Fact Scout"]
    assert a.status == "working" and a.started == 1.5


def test_delegate_stores_brief_and_marks_working():
    tr = ActivityTracker()
    tr.handle(ev("delegate", "Critic", "vet this draft", t=2.0))
    a = tr.agents["Critic"]
    assert a.status == "working"
    assert a.exchanges[-1].brief == "vet this draft"


def test_reply_stores_text_and_marks_done_with_finish_time():
    tr = ActivityTracker()
    tr.handle(ev("delegate", "Historian", "list banned", t=1.0))
    tr.handle(ev("reply", "Historian", "BANNED: none", t=4.0))
    a = tr.agents["Historian"]
    assert a.status == "done" and a.finished == 4.0
    assert a.exchanges[-1].reply == "BANNED: none"


def test_second_delegate_starts_a_new_exchange_and_reopens_the_agent():
    tr = ActivityTracker()
    tr.handle(ev("delegate", "Storyteller", "draft", t=1.0))
    tr.handle(ev("reply", "Storyteller", "v1", t=3.0))
    tr.handle(ev("delegate", "Storyteller", "fix holes", t=5.0))
    a = tr.agents["Storyteller"]
    assert a.status == "working" and a.finished is None
    assert [x.brief for x in a.exchanges] == ["draft", "fix holes"]
    assert a.started == 1.0


def test_tool_event_is_attributed_to_its_agent():
    tr = ActivityTracker()
    tr.handle(ev("delegate", "Fact Scout", "weather?", t=1.0))
    tr.handle(ev("tool", "Fact Scout", "web_fetch", t=2.0, detail="https://api.open-meteo.com/x"))
    a = tr.agents["Fact Scout"]
    assert a.exchanges[-1].tools == ["web_fetch: https://api.open-meteo.com/x"]


def test_tool_by_director_goes_to_timeline_only():
    tr = ActivityTracker()
    tr.handle(ev("tool", "Director", "bash", t=1.0))
    assert all(not a.exchanges for a in tr.agents.values())
    assert any("Director used bash" in e["text"] for e in tr.timeline)


def test_unknown_agent_only_appears_in_timeline():
    tr = ActivityTracker()
    tr.handle(ev("reply", "Mystery Agent", "hi", t=1.0))
    assert "Mystery Agent" not in tr.agents
    assert any("Mystery Agent" in e["text"] for e in tr.timeline)


def test_thread_idle_marks_working_agent_done():
    tr = ActivityTracker()
    tr.handle(ev("thread_created", "Recipient Profiler", t=1.0))
    tr.handle(ev("thread_idle", "Recipient Profiler", t=6.0))
    a = tr.agents["Recipient Profiler"]
    assert a.status == "done" and a.finished == 6.0


def test_timeline_is_in_event_order_with_times():
    tr = ActivityTracker()
    tr.handle(ev("delegate", "Fact Scout", "go", t=1.0))
    tr.handle(ev("reply", "Fact Scout", "facts", t=3.0))
    assert [e["t"] for e in tr.timeline] == [1.0, 3.0]
    assert "Director → Fact Scout" in tr.timeline[0]["text"]
    assert "Fact Scout replied" in tr.timeline[1]["text"]


def test_elapsed_seconds():
    tr = ActivityTracker()
    assert tr.elapsed("Critic") is None
    tr.handle(ev("delegate", "Critic", "x", t=2.0))
    tr.handle(ev("tool", "Critic", "web_fetch", t=5.0))
    assert tr.elapsed("Critic") == 3.0          # still working: last event time minus start
    tr.handle(ev("reply", "Critic", "ok", t=9.0))
    assert tr.elapsed("Critic") == 7.0


def test_parse_critic_revise():
    out = parse_critic("VERDICT: REVISE\nSCORE: 3\nHOLES:\n- too vague\n- no dentist opens at 11pm")
    assert out == {"verdict": "REVISE", "score": 3, "holes": ["too vague", "no dentist opens at 11pm"]}


def test_parse_critic_accept_has_no_holes():
    out = parse_critic("VERDICT: ACCEPT\nSCORE: 8\nHOLES:\n")
    assert out == {"verdict": "ACCEPT", "score": 8, "holes": []}


def test_parse_critic_returns_none_for_other_text():
    assert parse_critic("Looks fine to me") is None
    assert parse_critic("") is None
