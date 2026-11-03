import json
import time
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from context import build_context
from schema import SwarmResult, parse_result

BETA_HEADER = {"anthropic-beta": "managed-agents-2026-04-01"}

USER_INSTRUCTIONS = (
    "A request has just landed. Please run the standard Excuse Desk process for the "
    "requested level: gather facts, history and the recipient profile in parallel, "
    "draft, have the Critic vet it, and revise if needed. Return only the result "
    "JSON object, nothing else.\n\n"
)


def _make_client() -> Anthropic:
    load_dotenv()
    return Anthropic(default_headers=BETA_HEADER)


def _read_id(ids_dir: str, name: str, hint: str) -> str:
    path = Path(ids_dir) / name
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run {hint} first.")
    return path.read_text().strip()


def _blocks_text(content) -> str:
    if not content:
        return ""
    if isinstance(content, str):
        return content
    return "".join(b.text for b in content if getattr(b, "type", None) == "text")


def _summarize_input(data) -> str:
    """One short line describing a tool call's input (a URL, a query, a command)."""
    if not data:
        return ""
    if isinstance(data, dict):
        for key in ("url", "query", "command", "path", "file_path"):
            if data.get(key):
                return str(data[key])[:300]
        return json.dumps(data, default=str)[:300]
    return str(data)[:300]


def _ev(kind: str, agent: str, text: str = "", detail: str = "") -> dict:
    return {"kind": kind, "agent": agent, "text": text, "detail": detail}


def _thread_agent(event, threads: dict) -> str:
    """Name of the agent whose thread produced this event ('Director' when it has no thread)."""
    thread_id = getattr(event, "session_thread_id", None)
    if thread_id is None:
        return "Director"
    return threads.get(thread_id, "")


def _translate(event, threads: dict | None = None) -> dict | None:
    threads = {} if threads is None else threads
    t = event.type
    if t in ("session.thread_created", "session.thread_status_running", "session.thread_status_idle"):
        name = getattr(event, "agent_name", "?")
        thread_id = getattr(event, "session_thread_id", None)
        if thread_id is not None:
            threads[thread_id] = name
        kind = {"session.thread_created": "thread_created",
                "session.thread_status_running": "thread_running",
                "session.thread_status_idle": "thread_idle"}[t]
        return _ev(kind, name)
    if t == "agent.thread_message_sent":
        return _ev("delegate", getattr(event, "to_agent_name", "?"),
                   _blocks_text(getattr(event, "content", None)))
    if t == "agent.thread_message_received":
        return _ev("reply", getattr(event, "from_agent_name", "?"),
                   _blocks_text(getattr(event, "content", None)))
    if t == "agent.tool_use":
        return _ev("tool", _thread_agent(event, threads), getattr(event, "name", "?"),
                   _summarize_input(getattr(event, "input", None)))
    if t == "agent.message":
        return _ev("message", _thread_agent(event, threads), _blocks_text(event.content))
    return None


def _best_result(messages: list[str]) -> SwarmResult:
    joined = parse_result("".join(messages))
    if joined.rounds[0].holes != ["unparsed output"] or len(messages) == 1:
        return joined
    # Interim chatter around the JSON can break the joined parse; try the last message alone.
    last = parse_result(messages[-1])
    return last if last.rounds[0].holes != ["unparsed output"] else joined


def run_swarm(request, recipient, level, city="London", client=None, on_event=None,
              max_seconds: float = 300, clock=time.monotonic, ids_dir: str = ".",
              calendar_path=None, db_path=None) -> SwarmResult:
    if not request.strip() or not recipient.strip() or level not in (1, 2, 3, 4):
        raise ValueError("request and recipient must be non-blank and level must be 1 to 4")

    coordinator_id = _read_id(ids_dir, ".coordinator_id", "create_coordinator.py")
    environment_id = _read_id(ids_dir, ".environment_id", "setup_environment.py")

    extra = {}
    if calendar_path is not None:
        extra["calendar_path"] = calendar_path
    if db_path is not None:
        extra["db_path"] = db_path
    context = build_context(request, recipient, level, city=city, **extra)

    client = client or _make_client()
    session = client.beta.sessions.create(
        agent=coordinator_id, environment_id=environment_id, title="Excuse request",
    )
    try:
        (Path(ids_dir) / ".last_session_id").write_text(session.id)
    except OSError:
        pass

    messages: list[str] = []
    threads: dict[str, str] = {}
    start = clock()

    def emit(ev: dict) -> None:
        if on_event is None:
            return
        ev["t"] = round(float(clock() - start), 2)
        try:
            on_event(ev)
        except Exception:
            pass  # a UI callback error must not kill the run

    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[{"type": "user.message",
                     "content": [{"type": "text", "text": USER_INSTRUCTIONS + context}]}],
        )
        for event in stream:
            if clock() - start > max_seconds:
                try:
                    client.beta.sessions.events.send(session.id, events=[{"type": "user.interrupt"}])
                except Exception:
                    pass
                raise TimeoutError(f"swarm did not finish within {max_seconds} seconds")
            translated = _translate(event, threads)
            if translated:
                emit(translated)
            if event.type == "agent.message" and not getattr(event, "session_thread_id", None):
                text = _blocks_text(event.content)
                if text.strip():
                    messages.append(text)
            elif event.type == "session.status_idle":
                break

    if not messages:
        raise RuntimeError("swarm produced no output")
    return _best_result(messages)
