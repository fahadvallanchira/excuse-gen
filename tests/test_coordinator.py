import pytest

from coordinator import COORDINATOR_SYSTEM, build_coordinator_params

KEYS = ["fact_scout", "historian", "profiler", "storyteller", "critic"]
IDS = {k: f"agent_{k}" for k in KEYS}


def test_params_roster_has_all_five_in_order():
    ids = {k: IDS[k] for k in reversed(KEYS)}
    params = build_coordinator_params(ids)
    assert params["multiagent"] == {
        "type": "coordinator",
        "agents": [{"type": "agent", "id": f"agent_{k}"} for k in KEYS],
    }


def test_params_model_name_tools():
    params = build_coordinator_params(IDS)
    assert params["model"] == "claude-opus-5-5"
    assert params["name"] == "Excuse Director"
    assert params["tools"] == [{"type": "agent_toolset_20260401"}]
    assert params["system"] == COORDINATOR_SYSTEM


def test_missing_specialist_raises():
    ids = {k: v for k, v in IDS.items() if k != "critic"}
    with pytest.raises(KeyError):
        build_coordinator_params(ids)


def test_system_orders_parallel_delegation():
    for s in ["SINGLE message", "Fact Scout", "Historian", "Recipient Profiler", "Storyteller", "Critic"]:
        assert s in COORDINATOR_SYSTEM


def test_system_caps_revisions_and_pins_result_format():
    for s in ["at most 2", '"rounds"', '"believability"', '"holes"', '"verdict"', "only the JSON"]:
        assert s in COORDINATOR_SYSTEM


def test_system_forwards_documents_and_lowercases_verdict():
    assert "verbatim" in COORDINATOR_SYSTEM
    assert "lowercase" in COORDINATOR_SYSTEM


def test_no_forbidden_params():
    params = build_coordinator_params(IDS)
    for k in ("thinking", "budget_tokens", "temperature", "tool_choice"):
        assert k not in params
