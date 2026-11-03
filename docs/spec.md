# Excuse Generator Agent: Hackathon Build Plan

Stack: Python 3.11+, `anthropic` SDK (Claude API), Streamlit UI, SQLite for memory.
Target: a working demo in 4 to 6 hours with a team of 2 to 4.

## 1. What we are building

A user types what they need to get out of ("Friday 3pm status meeting", "dinner with Raj").
The agent:

1. Gathers context with tools (calendar, weather, past excuses).
2. Drafts an excuse at the chosen escalation level.
3. Runs a "skeptic" subagent that tries to poke holes and scores believability.
4. Revises until the skeptic is satisfied, or gives up after 2 rounds.
5. Shows the final excuse plus the skeptic's verdict in the UI.
6. Saves the excuse to memory so it is never reused on the same person.

Nothing is ever sent automatically. The UI has a "Copy" button and a "Mark as used" button.
That approval step is a feature, not a shortcut.

## 2. Architecture

```
┌────────────┐   prompt + level   ┌──────────────┐  tools   ┌──────────────────┐
│ Streamlit  │ ─────────────────► │ Excuse Agent │ ───────► │ calendar / weather│
│    UI      │                    │ (Opus 5.5)   │ ◄─────── │ / memory (sqlite) │
│            │ ◄───────────────── │              │          └──────────────────┘
│            │  excuse + verdict  └──────┬───────┘
└────────────┘                           │ draft
                                         ▼
                                  ┌──────────────┐
                                  │   Skeptic    │  structured JSON:
                                  │ (Haiku 5.5)  │  score, holes, verdict
                                  └──────────────┘
```

Two Claude roles:

- **Excuse Agent** on `claude-opus-5-5` with the SDK tool runner. It decides which tools to call.
- **Skeptic** on `claude-haiku-5-5` with structured output. It never sees the tools, only the excuse and the recipient. Cheap and fast, so we can loop.

## 3. Repo layout

```
exc-gen/              # repo root (github.com/fahadvallanchira/excuse-gen)
├── app.py            # Streamlit UI
├── agent.py          # generate_excuse(): tool runner + revision loop
├── skeptic.py        # critique(): structured-output call
├── tools.py          # @beta_tool functions: calendar, weather, memory
├── memory.py         # SQLite helpers (past excuses)
├── prompts.py        # system prompts, one per role
├── data/
│   └── calendar.json # fake calendar for the demo
├── requirements.txt  # anthropic, streamlit, pydantic, requests
└── .env.example      # ANTHROPIC_API_KEY=
```

## 4. Build phases

### Phase 0: Setup (20 min)

```bash
python -m venv .venv && source .venv/bin/activate
pip install anthropic streamlit pydantic requests
export ANTHROPIC_API_KEY=sk-ant-...
```

Smoke test: one `client.messages.create` call that returns "hello". Everyone on the team confirms their key works before splitting up.

### Phase 1: Tools (45 min)

`tools.py` uses the `@beta_tool` decorator. The docstring becomes the tool description, so write it for Claude, not for humans.

```python
from anthropic import beta_tool
import json, requests
from memory import past_excuses_for

@beta_tool
def get_calendar(date: str) -> str:
    """Return the user's calendar events for a date (YYYY-MM-DD).
    Use this to find real events that an excuse could reference or must avoid conflicting with.
    """
    events = json.load(open("data/calendar.json"))
    return json.dumps([e for e in events if e["date"] == date])

@beta_tool
def get_weather(city: str) -> str:
    """Return today's weather for a city. Useful for weather-based excuses."""
    # Open-Meteo needs no API key. Hardcode a few cities for the demo if short on time.
    r = requests.get("https://api.open-meteo.com/v1/forecast",
                     params={"latitude": 51.5, "longitude": -0.12, "current_weather": True})
    return r.text

@beta_tool
def recall_excuses(recipient: str) -> str:
    """Return excuses already used on this recipient, so the agent does not repeat them."""
    return json.dumps(past_excuses_for(recipient))
```

`memory.py` is a 20-line SQLite wrapper: `save_excuse(recipient, text, level)` and `past_excuses_for(recipient)`.

Owner: one person. Done when each tool runs standalone from a Python shell.

### Phase 2: Skeptic (45 min)

`skeptic.py` uses `client.messages.parse` with a Pydantic model so we never parse JSON by hand.

```python
from pydantic import BaseModel
import anthropic

class Verdict(BaseModel):
    believability: int          # 1 to 10
    holes: list[str]            # specific problems
    follow_up_question: str     # what a suspicious recipient would ask
    verdict: str                # "accept" or "revise"

client = anthropic.Anthropic()

def critique(excuse: str, recipient: str, context: str) -> Verdict:
    response = client.messages.parse(
        model="claude-haiku-5-5",
        max_tokens=2000,
        system=SKEPTIC_SYSTEM,   # "You are the suspicious recipient. Find holes."
        messages=[{"role": "user", "content":
            f"Recipient: {recipient}\nContext: {context}\nExcuse: {excuse}"}],
        output_format=Verdict,
    )
    return response.parsed_output
```

Owner: one person. Done when a hand-written bad excuse scores low and a good one scores high.

### Phase 3: Excuse Agent and revision loop (60 min)

`agent.py` runs the tool runner, then the critique loop.

```python
import anthropic
from tools import get_calendar, get_weather, recall_excuses
from skeptic import critique
from prompts import AGENT_SYSTEM

client = anthropic.Anthropic()

def draft(request: str, recipient: str, level: int, feedback: str | None = None) -> str:
    user = f"Escape: {request}\nRecipient: {recipient}\nLevel: {level}"
    if feedback:
        user += f"\nThe skeptic rejected the last draft. Fix these holes: {feedback}"
    runner = client.beta.messages.tool_runner(
        model="claude-opus-5-5",
        max_tokens=16000,
        system=AGENT_SYSTEM,
        tools=[get_calendar, get_weather, recall_excuses],
        messages=[{"role": "user", "content": user}],
    )
    final = runner.until_done()
    return next(b.text for b in final.content if b.type == "text")

def generate_excuse(request, recipient, level, max_rounds=2):
    history = []
    feedback = None
    for _ in range(max_rounds + 1):
        text = draft(request, recipient, level, feedback)
        verdict = critique(text, recipient, request)
        history.append((text, verdict))
        if verdict.verdict == "accept":
            break
        feedback = "; ".join(verdict.holes)
    return history   # UI shows every round, which is half the comedy
```

System prompt notes for `AGENT_SYSTEM`:

- Describe the four escalation levels explicitly.
- Tell it to call `recall_excuses` first, every time, and never reuse one.
- Tell it to prefer real calendar or weather facts over invented ones at levels 1 and 2.
- Ask for the excuse only as final output, no preamble, so the UI can show it cleanly.

Owner: one person. Done when `generate_excuse("Friday standup", "my manager", 2)` returns a history list from a Python shell.

### Phase 4: Streamlit UI (60 min)

`app.py` is a single page.

```python
import streamlit as st
from agent import generate_excuse
from memory import save_excuse

st.title("Excuse Generator")
request = st.text_input("What do you need to get out of?")
recipient = st.text_input("Who are you telling?")
level = st.slider("Escalation level", 1, 4, 2)

if st.button("Generate") and request:
    with st.spinner("Consulting the calendar, the weather, and your conscience..."):
        history = generate_excuse(request, recipient, level)
    for i, (text, verdict) in enumerate(history, 1):
        with st.expander(f"Round {i}: believability {verdict.believability}/10", expanded=(i == len(history))):
            st.write(text)
            if verdict.holes:
                st.caption("Skeptic found: " + "; ".join(verdict.holes))
    final_text = history[-1][0]
    st.code(final_text)                      # built-in copy button
    if st.button("Mark as used"):
        save_excuse(recipient, final_text, level)
        st.success("Saved. This one will never be used on them again.")
```

Run with `streamlit run app.py`.

Owner: one person, can start in parallel with Phase 3 using a stubbed `generate_excuse`.

### Phase 5: Polish and demo prep (45 min)

- Seed `data/calendar.json` with funny but plausible events for demo day.
- Pre-save two excuses in memory so the "never repeat" rule shows on stage.
- Add a level 4 "Pre-emptive" mode: scan next week's calendar and propose excuses for meetings it predicts you will want to skip.
- Add a believability sparkline across rounds if time allows.

## 5. Demo script (3 minutes)

1. Level 1 excuse for "team lunch". Skeptic accepts round one. Boring, fast.
2. Level 3 excuse for "Friday 3pm review with my manager". Show the agent calling the calendar and weather tools. Skeptic rejects round one, agent revises, round two passes. Open the expanders.
3. Click "Mark as used", then ask for another excuse for the same manager. Show it avoids the saved one.
4. Level 4: let it pre-emptively plan next week.

## 6. Risks and cuts

| Risk | Mitigation |
|---|---|
| Weather API flaky on venue wifi | Hardcode three cities in `get_weather` as fallback |
| Opus latency on stage | Set `output_config={"effort": "low"}` on the draft call for the demo |
| Skeptic too harsh, loops forever | `max_rounds=2` hard cap, always show last draft |
| Safety refusal on edgy prompts | Enable server-side fallbacks (`fallbacks="default"` with the `server-side-fallback-2026-07-01` beta) and check `stop_reason` |
| Team runs out of time | Cut Phase 5 first, then the weather tool. Calendar plus memory plus skeptic is the core |

## 7. Team split for 4 people

- Person A: tools and memory (Phase 1)
- Person B: skeptic (Phase 2), then prompt tuning
- Person C: agent loop (Phase 3)
- Person D: UI (Phase 4) against a stub, then integration
- Everyone: Phase 5 and demo rehearsal

## 8. Stretch ideas if you finish early

- Alibi Mode: two users, one shared story, the agent keeps both consistent.
- Honesty Slider: at zero it just tells the truth, which is the hardest excuse to write.
- Voice: pipe the final excuse through a TTS library and play it in the UI.
- Recipient personas: "strict manager", "chill friend", "suspicious partner" change the skeptic prompt.
