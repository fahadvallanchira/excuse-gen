# Excuse Generator Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Streamlit app where a user types what they want to get out of, and a Claude agent gathers context with tools, drafts an excuse, has a skeptic subagent critique it, revises, and shows every round.

**Architecture:** Two Claude roles. The Excuse Agent runs on `claude-opus-5-5` through the SDK tool runner with three tools (calendar, weather, memory). The Skeptic runs on `claude-haiku-5-5` through structured output and returns a Pydantic `Verdict`. A plain Python loop in `agent.py` drives draft, critique, revise, with a hard cap of two revisions. The UI never sends anything. It shows the result with a copy button and a "Mark as used" button that writes to SQLite.

**Tech Stack:** Python 3.11+, `anthropic` SDK, `streamlit`, `pydantic`, `requests`, `pytest`, SQLite via the standard library.

**Spec:** `docs/spec.md` (repo-relative)

## Global Constraints

- Project lives at the root of the git repo `/Users/fahadv/Documents/exc-gen/` (remote: `https://github.com/fahadvallanchira/excuse-gen.git`). Every command below runs from that directory.
- Use a venv inside the repo, created in Task 1: `source .venv/bin/activate` before any command.
- Model IDs are exactly `claude-opus-5-5` (agent) and `claude-haiku-5-5` (skeptic). Never append date suffixes.
- Never put `thinking`, `budget_tokens`, `temperature`, or forced `tool_choice` in any API call. These return 400 on these models.
- Parse structured output with `client.messages.parse(..., output_format=Model)` and read `response.parsed_output`. Never parse JSON from text by hand.
- Every function that calls the Claude API accepts a `client` parameter with a module-level default so tests can inject a fake. No test in this plan hits the real API.
- Nothing is ever sent to a recipient. The only side effects are SQLite writes.
- The repo already exists with an initial commit on `main`. Commit after each task. Commit messages end with the `Co-Authored-By` line your harness specifies, if any. Do not push unless asked.
- Secrets come from the `ANTHROPIC_API_KEY` environment variable. Never hardcode a key or commit `.env`.

## Review Focus

1. **Empty or whitespace-only request or recipient.** `generate_excuse` must raise `ValueError` rather than call the API, and the UI must not call it. Test pinned in Task 6.
2. **Skeptic never accepts.** The loop must stop after `max_rounds` revisions and return the last draft with its verdict, never loop forever or raise. Test pinned in Task 6.
3. **Agent response has no text block** (refusal, or `max_tokens` hit mid-tool-call). `draft` must return the fixed string `"The agent declined to produce an excuse. Try a lower level."` instead of raising `StopIteration`. Test pinned in Task 6.
4. **Recipient spelled differently across runs** ("My Manager" vs "my manager "). Memory must normalize to lowercase, stripped, so the no-repeat rule still works. Test pinned in Task 2.
5. **Unknown city or weather API down** on venue wifi. `weather_for` must return a usable string, never raise. Test pinned in Task 3.

---

## File Structure

```
exc-gen/                # repo root
├── LICENSE             # already present
├── docs/
│   ├── spec.md         # the design spec this plan implements
│   └── superpowers/plans/2026-11-03-excuse-generator.md   # this plan
├── app.py              # Streamlit UI only. Imports generate_excuse and save_excuse. No API calls.
├── agent.py            # draft() runs the tool runner; generate_excuse() runs the revise loop.
├── skeptic.py          # Verdict model and critique().
├── tools.py            # @beta_tool wrappers. Thin. Delegates to services.py.
├── services.py         # Pure functions: calendar_events, weather_for. Testable without the SDK.
├── memory.py           # SQLite: init_db, save_excuse, past_excuses_for.
├── prompts.py          # AGENT_SYSTEM, SKEPTIC_SYSTEM, LEVELS. Strings only.
├── data/
│   ├── calendar.json   # Seed calendar for the demo.
│   └── excuses.db      # Created at runtime by init_db. Gitignored.
├── scripts/
│   └── smoke.py        # One real API call. Manual check, not a test.
├── tests/
│   ├── test_memory.py
│   ├── test_services.py
│   ├── test_skeptic.py
│   └── test_agent.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

`tools.py` is separate from `services.py` so the pure logic is tested without importing the SDK decorator, and so the tool docstrings (which Claude reads) can be written for Claude while the service functions keep normal docstrings.

---

### Task 1: Project scaffold and API smoke test

**Files:**
- Create: `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `scripts/smoke.py`, `tests/__init__.py`, `data/.gitkeep`

**Interfaces:**
- Produces: a working venv with `anthropic`, `streamlit`, `pydantic`, `requests`, `pytest` installed.

- [ ] **Step 1: Create the folders and the venv**

```bash
cd /Users/fahadv/Documents/exc-gen
mkdir -p data scripts tests
touch tests/__init__.py data/.gitkeep
python3 -m venv .venv
source .venv/bin/activate
```

Expected: `python --version` prints 3.11 or newer.

- [ ] **Step 2: Write `requirements.txt`**

```
anthropic
streamlit
pydantic
requests
pytest
```

- [ ] **Step 3: Write `.gitignore`**

```
.venv/
.env
data/excuses.db
__pycache__/
.pytest_cache/
```

- [ ] **Step 4: Write `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 5: Install dependencies**

Run: `source .venv/bin/activate && pip install -r requirements.txt`
Expected: ends with `Successfully installed ...` listing `anthropic` and `streamlit`.

- [ ] **Step 6: Write `scripts/smoke.py`**

A script that builds `anthropic.Anthropic()`, calls `client.messages.create(model="claude-haiku-5-5", max_tokens=256, messages=[{"role": "user", "content": "Say hello in five words."}])`, and prints the text of the first block whose `.type == "text"`. Use Haiku here because it is the cheapest check that the key works.

- [ ] **Step 7: Run the smoke test**

Run: `export ANTHROPIC_API_KEY=... && python scripts/smoke.py`
Expected: one short greeting line printed. If `AuthenticationError`, the key is wrong. Stop and fix before continuing.

- [ ] **Step 8: Write a one-paragraph `README.md`**

State: what the app does (one sentence), how to install (`pip install -r requirements.txt`), how to run (`streamlit run app.py`), and that `ANTHROPIC_API_KEY` must be set.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "chore: scaffold project"
```

---

### Task 2: Memory (SQLite)

**Files:**
- Create: `memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Produces:
  - `DB_PATH: str = "data/excuses.db"` (module constant)
  - `init_db(db_path: str = DB_PATH) -> None` creates table `excuses(id INTEGER PRIMARY KEY, recipient TEXT, text TEXT, level INTEGER, created_at TEXT)` if missing.
  - `save_excuse(recipient: str, text: str, level: int, db_path: str = DB_PATH) -> None`
  - `past_excuses_for(recipient: str, db_path: str = DB_PATH) -> list[str]` returns texts, oldest first.
  - `normalize(recipient: str) -> str` returns `recipient.strip().lower()`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_memory.py
from memory import init_db, save_excuse, past_excuses_for, normalize

def test_save_and_recall(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    save_excuse("my manager", "dentist", 1, db_path=db)
    save_excuse("my manager", "flood", 2, db_path=db)
    assert past_excuses_for("my manager", db_path=db) == ["dentist", "flood"]

def test_recall_is_per_recipient(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    save_excuse("raj", "dentist", 1, db_path=db)
    assert past_excuses_for("my manager", db_path=db) == []

def test_recipient_is_normalized(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    save_excuse("  My Manager ", "dentist", 1, db_path=db)
    assert past_excuses_for("my manager", db_path=db) == ["dentist"]

def test_normalize():
    assert normalize("  My Manager ") == "my manager"

def test_init_db_is_idempotent(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    init_db(db)
    assert past_excuses_for("anyone", db_path=db) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'memory'`

- [ ] **Step 3: Implement `memory.py`**

Use `sqlite3` from the standard library. `save_excuse` and `past_excuses_for` both call `init_db(db_path)` first so callers never need to remember. Store `created_at` as `datetime.now().isoformat()`. Order recall by `id`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_memory.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add memory.py tests/test_memory.py
git commit -m "feat: sqlite memory for past excuses"
```

---

### Task 3: Calendar and weather services, seed data

**Files:**
- Create: `services.py`, `data/calendar.json`
- Test: `tests/test_services.py`

**Interfaces:**
- Produces:
  - `CALENDAR_PATH: str = "data/calendar.json"`
  - `calendar_events(date: str, path: str = CALENDAR_PATH) -> list[dict]` returns events whose `"date"` equals `date` (format `YYYY-MM-DD`).
  - `CITIES: dict[str, tuple[float, float]]` mapping lowercase city name to `(latitude, longitude)`. Must contain `"london"`, `"new york"`, `"san francisco"`, `"bangalore"`, `"dubai"`.
  - `weather_for(city: str, get=requests.get) -> str` returns a one-line human string like `"London: 12.3°C, weather code 61"`. Unknown city falls back to London and the string starts with `"Unknown city, using London: "`. Any exception from `get` returns `"Weather unavailable for {city}."`.

- [ ] **Step 1: Write `data/calendar.json`**

A JSON list of at least six objects with keys `date` (`YYYY-MM-DD`), `time` (`HH:MM`), `title`, `attendees` (list of strings). Spread them over the next seven days from today (2026-11-03). Make at least two of them obviously skippable ("Q4 synergy alignment", "Mandatory fun: trust falls") and at least one that an excuse could blame ("Dentist", "Car service").

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_services.py
import json
from services import calendar_events, weather_for, CITIES

def test_calendar_filters_by_date(tmp_path):
    p = tmp_path / "cal.json"
    p.write_text(json.dumps([
        {"date": "2026-11-05", "time": "15:00", "title": "Review", "attendees": ["manager"]},
        {"date": "2026-11-06", "time": "09:00", "title": "Standup", "attendees": []},
    ]))
    events = calendar_events("2026-11-05", path=str(p))
    assert [e["title"] for e in events] == ["Review"]

def test_calendar_empty_date(tmp_path):
    p = tmp_path / "cal.json"
    p.write_text("[]")
    assert calendar_events("2026-11-05", path=str(p)) == []

def test_seed_calendar_loads():
    events = calendar_events("1999-01-01")
    assert events == []  # proves the real file parses

def test_cities_present():
    for c in ["london", "new york", "san francisco", "bangalore", "dubai"]:
        assert c in CITIES

class FakeResp:
    def __init__(self, payload): self._p = payload
    def json(self): return self._p
    def raise_for_status(self): pass

def test_weather_known_city():
    fake = lambda url, params=None, timeout=None: FakeResp(
        {"current_weather": {"temperature": 12.3, "weathercode": 61}})
    assert weather_for("London", get=fake) == "London: 12.3°C, weather code 61"

def test_weather_unknown_city_falls_back_to_london():
    fake = lambda url, params=None, timeout=None: FakeResp(
        {"current_weather": {"temperature": 5.0, "weathercode": 0}})
    out = weather_for("Atlantis", get=fake)
    assert out.startswith("Unknown city, using London: ")

def test_weather_network_failure_does_not_raise():
    def boom(url, params=None, timeout=None): raise ConnectionError("no wifi")
    assert weather_for("London", get=boom) == "Weather unavailable for London."
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_services.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services'`

- [ ] **Step 4: Implement `services.py`**

`weather_for` calls `get("https://api.open-meteo.com/v1/forecast", params={"latitude": lat, "longitude": lon, "current_weather": True}, timeout=5)`. Read `resp.json()["current_weather"]["temperature"]` and `["weathercode"]`. Format the temperature with one decimal. Wrap the whole network section in `try/except Exception`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_services.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add services.py data/calendar.json tests/test_services.py
git commit -m "feat: calendar and weather services with seed data"
```

---

### Task 4: Tool wrappers and prompts

**Files:**
- Create: `tools.py`, `prompts.py`

**Interfaces:**
- Consumes: `services.calendar_events`, `services.weather_for`, `memory.past_excuses_for`.
- Produces:
  - `tools.get_calendar`, `tools.get_weather`, `tools.recall_excuses`: three objects created by `@beta_tool` from `anthropic`, each wrapping a function with the same name and signature `(arg: str) -> str`.
  - `tools.ALL_TOOLS: list` containing the three in that order.
  - `prompts.LEVELS: dict[int, str]` with keys 1 to 4.
  - `prompts.AGENT_SYSTEM: str`, `prompts.SKEPTIC_SYSTEM: str`.

- [ ] **Step 1: Write `tools.py`**

Three functions decorated with `@beta_tool` (import: `from anthropic import beta_tool`). Each returns a string: JSON via `json.dumps` for lists, the plain string for weather. Docstrings are what Claude sees, so use these exactly:

- `get_calendar(date: str) -> str`: `"""Return the user's calendar events for a date in YYYY-MM-DD format. Call this to find real events an excuse can reference, and to check what the user is supposedly skipping."""`
- `get_weather(city: str) -> str`: `"""Return current weather for a city as one line. Call this when a weather-related excuse might be plausible."""`
- `recall_excuses(recipient: str) -> str`: `"""Return a JSON list of excuses already used on this recipient. Always call this first and never reuse any of them."""`

End the file with `ALL_TOOLS = [get_calendar, get_weather, recall_excuses]`.

- [ ] **Step 2: Verify the tools import and have schemas**

Run: `python -c "import tools; print(len(tools.ALL_TOOLS))"`
Expected: `3`

- [ ] **Step 3: Write `prompts.py`**

`LEVELS` copy, exact:

```python
LEVELS = {
    1: "Vague and low-risk. Something like 'something came up'. No details that could be checked.",
    2: "Tied to one real fact from the calendar or weather. Short and believable.",
    3: "A short saga with two or three supporting details that are internally consistent. Still plausible.",
    4: "Pre-emptive. Look at the next seven days of calendar, pick the meetings the user will most want to skip, and propose one excuse per meeting.",
}
```

`AGENT_SYSTEM` must contain, in this order: a one-line role ("You write believable excuses on behalf of the user."), the rule "Always call recall_excuses first and never reuse any excuse it returns.", the rule "At levels 1 and 2, prefer real facts from get_calendar and get_weather over invented details.", the full `LEVELS` dict rendered as four lines, and the output rule "Reply with the excuse text only, written in first person as the user would send it. No preamble, no explanation, no options." For level 4, the output rule becomes one excuse per line prefixed with the meeting title and a colon. Build the string with an f-string so `LEVELS` is the single source of truth.

`SKEPTIC_SYSTEM`, exact:

```
You are the person receiving this excuse. You are mildly suspicious but fair.
Find concrete holes: contradictions, details that are easy to check and likely false, or anything that sounds rehearsed.
Score believability from 1 (obviously fake) to 10 (you would accept it without a second thought).
Return verdict "accept" if believability is 7 or higher, otherwise "revise".
```

- [ ] **Step 4: Verify prompts import**

Run: `python -c "import prompts; assert set(prompts.LEVELS) == {1,2,3,4}; assert 'recall_excuses' in prompts.AGENT_SYSTEM; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add tools.py prompts.py
git commit -m "feat: tool wrappers and system prompts"
```

---

### Task 5: Skeptic

**Files:**
- Create: `skeptic.py`
- Test: `tests/test_skeptic.py`

**Interfaces:**
- Consumes: `prompts.SKEPTIC_SYSTEM`.
- Produces:
  - `class Verdict(pydantic.BaseModel)` with fields `believability: int`, `holes: list[str]`, `follow_up_question: str`, `verdict: Literal["accept", "revise"]`.
  - `SKEPTIC_MODEL: str = "claude-haiku-5-5"`
  - `critique(excuse: str, recipient: str, context: str, client=None) -> Verdict`. When `client` is `None`, uses a module-level `anthropic.Anthropic()` created lazily on first use (so importing the module does not need a key).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_skeptic.py
from skeptic import Verdict, critique, SKEPTIC_MODEL

class FakeParsed:
    def __init__(self, v): self.parsed_output = v

class FakeMessages:
    def __init__(self, verdict):
        self.verdict = verdict
        self.calls = []
    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return FakeParsed(self.verdict)

class FakeClient:
    def __init__(self, verdict): self.messages = FakeMessages(verdict)

def test_critique_returns_verdict_from_client():
    v = Verdict(believability=3, holes=["no dentist opens at 11pm"],
                follow_up_question="Which dentist?", verdict="revise")
    client = FakeClient(v)
    out = critique("dentist at 11pm", "my manager", "Friday review", client=client)
    assert out is v

def test_critique_sends_expected_request():
    v = Verdict(believability=8, holes=[], follow_up_question="", verdict="accept")
    client = FakeClient(v)
    critique("car broke down", "raj", "dinner", client=client)
    call = client.messages.calls[0]
    assert call["model"] == SKEPTIC_MODEL == "claude-haiku-5-5"
    assert call["output_format"] is Verdict
    assert "raj" in call["messages"][0]["content"]
    assert "car broke down" in call["messages"][0]["content"]
    assert "dinner" in call["messages"][0]["content"]
    assert "thinking" not in call
    assert "temperature" not in call

def test_verdict_rejects_bad_verdict_value():
    import pytest
    with pytest.raises(Exception):
        Verdict(believability=5, holes=[], follow_up_question="", verdict="maybe")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_skeptic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'skeptic'`

- [ ] **Step 3: Implement `skeptic.py`**

`critique` builds the user content as `f"Recipient: {recipient}\nContext: {context}\nExcuse: {excuse}"` and calls `client.messages.parse(model=SKEPTIC_MODEL, max_tokens=2000, system=SKEPTIC_SYSTEM, messages=[{"role": "user", "content": content}], output_format=Verdict)`. Return `response.parsed_output`. No other parameters.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_skeptic.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add skeptic.py tests/test_skeptic.py
git commit -m "feat: skeptic subagent with structured verdict"
```

---

### Task 6: Excuse agent and revision loop

**Files:**
- Create: `agent.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: `tools.ALL_TOOLS`, `prompts.AGENT_SYSTEM`, `prompts.LEVELS`, `skeptic.critique`, `skeptic.Verdict`.
- Produces:
  - `AGENT_MODEL: str = "claude-opus-5-5"`
  - `DECLINED: str = "The agent declined to produce an excuse. Try a lower level."`
  - `draft(request: str, recipient: str, level: int, feedback: str | None = None, client=None) -> str`
  - `generate_excuse(request: str, recipient: str, level: int, max_rounds: int = 2, draft_fn=draft, critique_fn=critique) -> list[tuple[str, Verdict]]`. Raises `ValueError` on blank `request` or `recipient`, or `level` not in 1..4. Returns one `(text, verdict)` per round, at most `max_rounds + 1` entries.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_agent.py
import pytest
from skeptic import Verdict
from agent import generate_excuse, draft, DECLINED, AGENT_MODEL

def accept(): return Verdict(believability=8, holes=[], follow_up_question="", verdict="accept")
def revise(): return Verdict(believability=3, holes=["too vague"], follow_up_question="?", verdict="revise")

def test_stops_on_first_accept():
    drafts = iter(["excuse A"])
    hist = generate_excuse("standup", "manager", 1,
                           draft_fn=lambda *a, **k: next(drafts),
                           critique_fn=lambda *a, **k: accept())
    assert [t for t, _ in hist] == ["excuse A"]

def test_revises_then_accepts_and_passes_feedback():
    seen = []
    def fake_draft(request, recipient, level, feedback=None, client=None):
        seen.append(feedback); return f"draft{len(seen)}"
    verdicts = iter([revise(), accept()])
    hist = generate_excuse("standup", "manager", 2,
                           draft_fn=fake_draft, critique_fn=lambda *a, **k: next(verdicts))
    assert len(hist) == 2
    assert seen == [None, "too vague"]

def test_caps_at_max_rounds_when_never_accepted():
    n = {"i": 0}
    def fake_draft(*a, **k): n["i"] += 1; return f"d{n['i']}"
    hist = generate_excuse("standup", "manager", 3, max_rounds=2,
                           draft_fn=fake_draft, critique_fn=lambda *a, **k: revise())
    assert len(hist) == 3
    assert hist[-1][1].verdict == "revise"

@pytest.mark.parametrize("request_,recipient,level", [
    ("", "manager", 1), ("   ", "manager", 1), ("standup", "", 1),
    ("standup", "manager", 0), ("standup", "manager", 5),
])
def test_rejects_bad_input(request_, recipient, level):
    with pytest.raises(ValueError):
        generate_excuse(request_, recipient, level,
                        draft_fn=lambda *a, **k: "x", critique_fn=lambda *a, **k: accept())

class Block:
    def __init__(self, type_, text=None): self.type = type_; self.text = text

class FakeFinal:
    def __init__(self, blocks, stop_reason="end_turn"):
        self.content = blocks; self.stop_reason = stop_reason

class FakeRunner:
    def __init__(self, final): self._final = final
    def until_done(self): return self._final

class FakeBetaMessages:
    def __init__(self, final): self.final = final; self.calls = []
    def tool_runner(self, **kwargs): self.calls.append(kwargs); return FakeRunner(self.final)

class FakeClient:
    def __init__(self, final):
        self.beta = type("B", (), {})(); self.beta.messages = FakeBetaMessages(final)

def test_draft_returns_text_block():
    client = FakeClient(FakeFinal([Block("text", "I have a dentist appointment.")]))
    assert draft("review", "manager", 2, client=client) == "I have a dentist appointment."

def test_draft_sends_expected_request():
    client = FakeClient(FakeFinal([Block("text", "x")]))
    draft("review", "manager", 2, feedback="too vague", client=client)
    call = client.beta.messages.calls[0]
    assert call["model"] == AGENT_MODEL == "claude-opus-5-5"
    assert len(call["tools"]) == 3
    content = call["messages"][0]["content"]
    assert "review" in content and "manager" in content and "Level: 2" in content
    assert "too vague" in content
    assert "Today:" in content
    assert "thinking" not in call and "tool_choice" not in call

def test_draft_without_feedback_omits_feedback_line():
    client = FakeClient(FakeFinal([Block("text", "x")]))
    draft("review", "manager", 2, client=client)
    assert "skeptic rejected" not in client.beta.messages.calls[0]["messages"][0]["content"]

def test_draft_with_no_text_block_returns_declined():
    client = FakeClient(FakeFinal([Block("thinking")], stop_reason="refusal"))
    assert draft("review", "manager", 4, client=client) == DECLINED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent'`

- [ ] **Step 3: Implement `draft` in `agent.py`**

Build the user message as:

```
Today: {date.today().isoformat()}
Escape: {request}
Recipient: {recipient}
Level: {level}
```

and, only when `feedback` is truthy, append `\nThe skeptic rejected the last draft. Fix these holes: {feedback}`.

Call `client.beta.messages.tool_runner(model=AGENT_MODEL, max_tokens=16000, system=AGENT_SYSTEM, tools=ALL_TOOLS, messages=[{"role": "user", "content": user}])`, then `final = runner.until_done()`. Return the `.text` of the first block with `.type == "text"`, or `DECLINED` if there is none. Use `next(..., None)` so a missing block never raises.

`client=None` means use a lazily created module-level `anthropic.Anthropic()`, same pattern as `skeptic.py`.

- [ ] **Step 4: Implement `generate_excuse` in `agent.py`**

Validate first: `request.strip()` and `recipient.strip()` non-empty, `level in LEVELS`. Then loop `for _ in range(max_rounds + 1)`: call `draft_fn(request, recipient, level, feedback)`, then `critique_fn(text, recipient, request)`, append the pair, break on `verdict == "accept"`, else set `feedback = "; ".join(verdict.holes)`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_agent.py -v`
Expected: 12 passed (the parametrized test counts as 5)

- [ ] **Step 6: Run the whole suite**

Run: `pytest -v`
Expected: 27 passed

- [ ] **Step 7: Real API check (manual, costs a few cents)**

Run: `python -c "from agent import generate_excuse; h = generate_excuse('Friday 3pm review', 'my manager', 2); [print(i+1, v.believability, v.verdict, '\n', t, '\n') for i,(t,v) in enumerate(h)]"`
Expected: one to three rounds printed, each with a score and a first-person excuse. If every round prints `DECLINED`, check `stop_reason` by printing `final.stop_reason` inside `draft` temporarily.

- [ ] **Step 8: Commit**

```bash
git add agent.py tests/test_agent.py
git commit -m "feat: excuse agent with skeptic revision loop"
```

---

### Task 7: Streamlit UI

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `agent.generate_excuse`, `memory.save_excuse`, `prompts.LEVELS`.

- [ ] **Step 1: Write `app.py`**

Single page. Required elements and behavior:

- `st.title("Excuse Generator")`.
- `request = st.text_input("What do you need to get out of?")`.
- `recipient = st.text_input("Who are you telling?")`.
- `level = st.slider("Escalation level", 1, 4, 2)` followed by `st.caption(LEVELS[level])`.
- A "Generate" button. When clicked and both inputs are non-blank, call `generate_excuse` inside `st.spinner("Consulting the calendar, the weather, and your conscience...")` and store the result in `st.session_state["history"]`. Store the `recipient` and `level` used in `st.session_state` too. If either input is blank, `st.warning("Fill in both fields.")` and do not call the agent. Wrap the call in `try/except Exception as e` and show `st.error(str(e))`.
- Rendering reads from `st.session_state.get("history")`, not from the button's return value, so the page survives the re-run that any later button click triggers.
- For each round `i` (1-based), an `st.expander(f"Round {i}: believability {verdict.believability}/10", expanded=(i == last))` containing `st.write(text)` and, if `verdict.holes`, `st.caption("Skeptic found: " + "; ".join(verdict.holes))`.
- After the expanders, `st.code(final_text, language=None)` so the built-in copy button appears.
- A "Mark as used" button. On click, `save_excuse(recipient, final_text, level)` using the values stored in session state, then `st.success("Saved. This one will never be used on them again.")`.

Nothing in this file calls the Anthropic SDK directly.

- [ ] **Step 2: Verify it compiles without a key**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Run the app**

Run: `export ANTHROPIC_API_KEY=... && streamlit run app.py --server.headless true`
Expected: prints a `Local URL: http://localhost:8501`. Open it. Generate a level 2 excuse for "Friday 3pm review" to "my manager". Confirm: spinner shows, at least one expander appears, the code block has a copy icon, "Mark as used" shows the success message, and clicking "Mark as used" does not wipe the expanders.

- [ ] **Step 4: Confirm the no-repeat rule end to end**

Generate again for the same recipient. Expected: the new excuse differs from the saved one. Run `python -c "from memory import past_excuses_for; print(past_excuses_for('my manager'))"` and confirm the first excuse is listed.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: streamlit ui with approval step"
```

---

### Task 8: Demo preparation

**Files:**
- Create: `scripts/seed_demo.py`
- Modify: `README.md`

- [ ] **Step 1: Write `scripts/seed_demo.py`**

Deletes `data/excuses.db` if present, then saves two excuses for recipient `"my manager"`: `"My dentist moved my appointment to 3pm."` (level 2) and `"Our building's fire alarm test overran."` (level 2). Prints `seeded`.

- [ ] **Step 2: Run it**

Run: `python scripts/seed_demo.py && python -c "from memory import past_excuses_for; print(len(past_excuses_for('my manager')))"`
Expected: `seeded` then `2`

- [ ] **Step 3: Add the demo script to `README.md`**

Append a "Demo" section with these four steps, copied from the spec: level 1 for "team lunch"; level 3 for "Friday 3pm review with my manager" and open the expanders; "Mark as used" then regenerate to show no repeat; level 4 pre-emptive week plan. Note the fallback if wifi fails: weather returns "Weather unavailable" and the agent still works.

- [ ] **Step 4: Rehearse the four demo steps once in the running app**

Expected: each step completes in under 60 seconds. If a level 3 or 4 call takes longer than that, add `output_config={"effort": "low"}` to the `tool_runner` call in `agent.py` and rerun `pytest -v` (still 27 passed, since no test asserts on that key).

- [ ] **Step 5: Commit**

```bash
git add scripts/seed_demo.py README.md
git commit -m "chore: demo seed script and demo notes"
```

---

## Stretch (only after Task 8 is committed)

- **Recipient personas**: add `persona: str` to `critique` and prepend `f"Persona: {persona}\n"` to `SKEPTIC_SYSTEM`. UI gets a selectbox with "strict manager", "chill friend", "suspicious partner".
- **Honesty slider**: level 0 in `LEVELS` = "Tell the plain truth, politely." No other code changes.
- **Server-side refusal fallback**: add `betas=["server-side-fallback-2026-07-01"], fallbacks="default"` to the `tool_runner` call. If the installed SDK rejects either argument, drop both. Not in the core plan because the demo prompts should not trigger a refusal.
