"""Tracks what each agent in the swarm is doing, from the events run_swarm emits.

Pure Python with no Streamlit import, so the logic is testable on its own. The UI
feeds every event to ActivityTracker.handle() and renders the state it holds.
"""

import re
from dataclasses import dataclass, field

AGENTS = ["Fact Scout", "Historian", "Recipient Profiler", "Storyteller", "Critic"]


@dataclass
class Exchange:
    """One brief from the Director and the agent's answer (an agent can have several)."""
    brief: str = ""
    reply: str = ""
    tools: list[str] = field(default_factory=list)


@dataclass
class AgentState:
    name: str
    status: str = "waiting"          # waiting | working | done
    started: float | None = None
    finished: float | None = None
    exchanges: list[Exchange] = field(default_factory=list)


class ActivityTracker:
    def __init__(self) -> None:
        self.agents: dict[str, AgentState] = {n: AgentState(n) for n in AGENTS}
        self.timeline: list[dict] = []
        self.last_t: float = 0.0

    # -- helpers ---------------------------------------------------------
    def _log(self, t: float, text: str) -> None:
        self.timeline.append({"t": t, "text": text})

    def _start(self, agent: AgentState, t: float) -> None:
        agent.status = "working"
        agent.finished = None
        if agent.started is None:
            agent.started = t

    def _current(self, agent: AgentState) -> Exchange:
        if not agent.exchanges:
            agent.exchanges.append(Exchange())
        return agent.exchanges[-1]

    # -- events ----------------------------------------------------------
    def handle(self, event: dict) -> None:
        kind = event.get("kind", "")
        name = event.get("agent", "") or ""
        text = event.get("text", "") or ""
        detail = event.get("detail", "") or ""
        t = float(event.get("t") or self.last_t)
        self.last_t = max(self.last_t, t)
        agent = self.agents.get(name)

        if kind == "thread_created":
            if agent:
                self._start(agent, t)
            self._log(t, f"{name} joined")
        elif kind == "thread_running":
            if agent:
                self._start(agent, t)
        elif kind == "thread_idle":
            if agent and agent.status == "working":
                agent.status, agent.finished = "done", t
        elif kind == "delegate":
            if agent:
                self._start(agent, t)
                agent.exchanges.append(Exchange(brief=text))
            self._log(t, f"Director → {name}")
        elif kind == "reply":
            if agent:
                self._current(agent).reply = text
                agent.status, agent.finished = "done", t
            self._log(t, f"{name} replied")
        elif kind == "tool":
            label = f"{text}: {detail}" if detail else text
            if agent:
                self._current(agent).tools.append(label)
            self._log(t, f"{name or 'Director'} used {text}")
        elif kind == "message":
            self._log(t, "Director returned the result")

    # -- read side -------------------------------------------------------
    def elapsed(self, name: str) -> float | None:
        a = self.agents[name]
        if a.started is None:
            return None
        end = a.finished if a.finished is not None else self.last_t
        return round(end - a.started, 2)


_VERDICT = re.compile(r"VERDICT:\s*(ACCEPT|REVISE)", re.I)
_SCORE = re.compile(r"SCORE:\s*(\d+)", re.I)


def parse_critic(text: str) -> dict | None:
    """Parse the Critic's fixed reply format, or return None if it does not match."""
    verdict = _VERDICT.search(text or "")
    if not verdict:
        return None
    score = _SCORE.search(text)
    holes: list[str] = []
    if "HOLES:" in text.upper():
        tail = text[text.upper().index("HOLES:") + len("HOLES:"):]
        holes = [ln.strip()[1:].strip() for ln in tail.splitlines() if ln.strip().startswith("-")]
    return {
        "verdict": verdict.group(1).upper(),
        "score": int(score.group(1)) if score else None,
        "holes": holes,
    }
