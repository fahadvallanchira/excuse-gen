import re
from pathlib import Path

import pytest

from specialists import SPECIALISTS, SKILL_TO_SPECIALIST, build_agent_params

ROOT = Path(__file__).resolve().parent.parent
BY_KEY = {s["key"]: s for s in SPECIALISTS}


def test_five_specialists_with_expected_keys():
    assert [s["key"] for s in SPECIALISTS] == [
        "fact_scout", "historian", "profiler", "storyteller", "critic",
    ]
    for s in SPECIALISTS:
        assert s["name"] and s["model"] and s["system"]


def test_models():
    assert BY_KEY["fact_scout"]["model"] == "claude-haiku-5-5"
    assert BY_KEY["historian"]["model"] == "claude-haiku-5-5"
    for key in ("profiler", "storyteller", "critic"):
        assert BY_KEY[key]["model"] == "claude-sonnet-5-5"


def test_critic_reply_format_is_documented():
    system = BY_KEY["critic"]["system"]
    for needle in ("VERDICT: ACCEPT", "VERDICT: REVISE", "SCORE:", "HOLES:", "7"):
        assert needle in system


def test_fact_scout_handles_weather_outage_and_uses_open_meteo():
    system = BY_KEY["fact_scout"]["system"]
    assert "Open-Meteo" in system
    assert "weather unavailable" in system


def test_historian_bans_reuse():
    system = BY_KEY["historian"]["system"]
    assert "never" in system.lower()
    assert "past-excuses" in system


def test_storyteller_mentions_all_four_levels():
    system = BY_KEY["storyteller"]["system"]
    for n in range(1, 5):
        assert f"Level {n}" in system


def test_skill_mapping():
    assert SKILL_TO_SPECIALIST == {
        "fact-grounding": "fact_scout",
        "recipient-personas": "profiler",
        "excuse-playbook": "storyteller",
        "believability-rubric": "critic",
    }


@pytest.mark.parametrize("skill", sorted(SKILL_TO_SPECIALIST))
def test_every_skill_dir_has_valid_skill_md(skill):
    text = (ROOT / "skills" / skill / "SKILL.md").read_text()
    assert text.startswith("---")
    frontmatter = text.split("---")[1]
    assert re.search(rf"^name: {re.escape(skill)}$", frontmatter, re.M)
    assert re.search(r"^description: \S+", frontmatter, re.M)
    body = text.split("---", 2)[2]
    assert len(body) > 200


def test_build_agent_params():
    spec = BY_KEY["critic"]
    params = build_agent_params(spec)
    assert params["name"] == spec["name"]
    assert params["model"] == spec["model"]
    assert params["system"] == spec["system"]
    assert params["tools"] == [{"type": "agent_toolset_20260401"}]
    assert params["metadata"]["role"] == "critic"
