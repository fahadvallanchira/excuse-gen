# Excuse Generator: Tasks for 4 Developers + Integration

Spec: [docs/spec.md](docs/spec.md). Full plan: [docs/superpowers/plans/2026-11-03-excuse-generator.md](docs/superpowers/plans/2026-11-03-excuse-generator.md).
Every section below is self-contained: it carries the exact code, tests and steps its owner needs. Step and Task numbers inside copied text refer to the original plan; ignore them, follow the order inside your own section.

## How we work

1. Five independent tasks: **A, B, C, D** (build) and **E** (integration). Own files, own branch, own PR. No file is owned by two people.
2. Build against the **Contracts** below. If you import another person's module, do not wait: copy the matching file from **Stubs** into a scratch folder outside git (for example `/tmp/stubs/`) and run with `PYTHONPATH=/tmp/stubs:.`. Never commit stubs. Delete them once the real module is on `main`.
3. When your "Done when" passes, open a PR to `main`. PRs can merge in any order.
4. After A to D are merged, **E** runs end to end on `main`.
5. Everyone first reads "Global Constraints" and "Review Focus" below.

Setup (everyone, run from the repo root):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install anthropic streamlit pydantic requests pytest
export ANTHROPIC_API_KEY=sk-ant-...   # only needed for manual real-API checks, never for pytest
```

Everyone runs `mkdir -p tests && touch tests/__init__.py` and includes that empty file in their PR (it makes `pytest` put the repo root on the import path). Identical empty files merge cleanly.

## Global Constraints (from the plan)

- Project lives at the root of your local clone of the `excuse-gen` git repo. Every command below runs from that directory.
- Use a venv inside the repo, created in Task 1: `source .venv/bin/activate` before any command.
- Model IDs are exactly `claude-opus-5-5` (agent) and `claude-haiku-5-5` (skeptic). Never append date suffixes.
- Never put `thinking`, `budget_tokens`, `temperature`, or forced `tool_choice` in any API call. These return 400 on these models.
- Parse structured output with `client.messages.parse(..., output_format=Model)` and read `response.parsed_output`. Never parse JSON from text by hand.
- Every function that calls the Claude API accepts a `client` parameter with a module-level default so tests can inject a fake. No test in this plan hits the real API.
- Nothing is ever sent to a recipient. The only side effects are SQLite writes.
- The repo already exists with an initial commit on `main`. Commit after each task. Commit messages end with the `Co-Authored-By` line your harness specifies, if any. Do not push unless asked.
- Secrets come from the `ANTHROPIC_API_KEY` environment variable. Never hardcode a key or commit `.env`.

## Review Focus (from the plan)

1. **Empty or whitespace-only request or recipient.** `generate_excuse` must raise `ValueError` rather than call the API, and the UI must not call it. Test pinned in Task 6.
2. **Skeptic never accepts.** The loop must stop after `max_rounds` revisions and return the last draft with its verdict, never loop forever or raise. Test pinned in Task 6.
3. **Agent response has no text block** (refusal, or `max_tokens` hit mid-tool-call). `draft` must return the fixed string `"The agent declined to produce an excuse. Try a lower level."` instead of raising `StopIteration`. Test pinned in Task 6.
4. **Recipient spelled differently across runs** ("My Manager" vs "my manager "). Memory must normalize to lowercase, stripped, so the no-repeat rule still works. Test pinned in Task 2.
5. **Unknown city or weather API down** on venue wifi. `weather_for` must return a usable string, never raise. Test pinned in Task 3.

## Ownership

| Task | Branch | Files (only these) |
|---|---|---|
| **A** Tools and memory | `dev-a` | `memory.py`, `services.py`, `tools.py`, `data/calendar.json`, `data/.gitkeep`, `requirements.txt`, `.gitignore`, `.env.example`, `README.md`, `tests/test_memory.py`, `tests/test_services.py` |
| **B** Skeptic and prompts | `dev-b` | `prompts.py`, `skeptic.py`, `tests/test_skeptic.py` |
| **C** Agent loop | `dev-c` | `agent.py`, `tests/test_agent.py` |
| **D** UI | `dev-d` | `app.py` |
| **E** Integration and demo | `dev-e` | `tests/test_integration.py`, `scripts/seed_demo.py`, `scripts/smoke.py`, `docs/demo.md` |

## Contracts (frozen, change only by telling everyone)

```python
# memory.py (A)   recipient is stripped + lowercased; init_db also creates the parent dir
DB_PATH: str = "data/excuses.db"
normalize(recipient: str) -> str
init_db(db_path: str = DB_PATH) -> None
save_excuse(recipient: str, text: str, level: int, db_path: str = DB_PATH) -> None
past_excuses_for(recipient: str, db_path: str = DB_PATH) -> list[str]     # oldest first

# services.py (A)
CALENDAR_PATH: str = "data/calendar.json"
CITIES: dict[str, tuple[float, float]]
calendar_events(date: str, path: str = CALENDAR_PATH) -> list[dict]
weather_for(city: str, get=requests.get) -> str                          # never raises

# tools.py (A)    @beta_tool objects, each (arg: str) -> str
get_calendar, get_weather, recall_excuses
ALL_TOOLS: list = [get_calendar, get_weather, recall_excuses]

# prompts.py (B)
LEVELS: dict[int, str]          # keys 1..4
AGENT_SYSTEM: str
SKEPTIC_SYSTEM: str

# skeptic.py (B)
class Verdict(BaseModel): believability: int; holes: list[str]; follow_up_question: str; verdict: Literal["accept", "revise"]
SKEPTIC_MODEL: str = "claude-haiku-5-5"
critique(excuse: str, recipient: str, context: str, client=None) -> Verdict

# agent.py (C)
AGENT_MODEL: str = "claude-opus-5-5"
DECLINED: str = "The agent declined to produce an excuse. Try a lower level."
draft(request: str, recipient: str, level: int, feedback: str | None = None, client=None) -> str
generate_excuse(request, recipient, level, max_rounds: int = 2, draft_fn=draft, critique_fn=critique) -> list[tuple[str, Verdict]]
```

---

# Task A: Tools and memory

Branch `dev-a`. **Depends on nobody.** Produces `memory.py`, `services.py`, `tools.py`, seed calendar, project config.

## A1. Scaffold files you own

Do plan Task 1 steps below. (The smoke script and its run belong to Task E.) Do not create `scripts/smoke.py`.

- [ ] **Step 1: Create the folders and the venv**

```bash
# run from the repo root
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

- [ ] **Step 8: Write a one-paragraph `README.md`**

State: what the app does (one sentence), how to install (`pip install -r requirements.txt`), how to run (`streamlit run app.py`), and that `ANTHROPIC_API_KEY` must be set.

## A2. Memory (SQLite)

Extra requirement over the plan text: `init_db` must create the parent directory of `db_path` (`os.makedirs(os.path.dirname(db_path), exist_ok=True)` when the dirname is non-empty), so nobody needs the `data/` folder to exist first.

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


## A3. Calendar and weather services, seed data

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


## A4. Tool wrappers

- [ ] **Step 1: Write `tools.py`**

Three functions decorated with `@beta_tool` (import: `from anthropic import beta_tool`). Each returns a string: JSON via `json.dumps` for lists, the plain string for weather. Docstrings are what Claude sees, so use these exactly:

- `get_calendar(date: str) -> str`: `"""Return the user's calendar events for a date in YYYY-MM-DD format. Call this to find real events an excuse can reference, and to check what the user is supposedly skipping."""`
- `get_weather(city: str) -> str`: `"""Return current weather for a city as one line. Call this when a weather-related excuse might be plausible."""`
- `recall_excuses(recipient: str) -> str`: `"""Return a JSON list of excuses already used on this recipient. Always call this first and never reuse any of them."""`

End the file with `ALL_TOOLS = [get_calendar, get_weather, recall_excuses]`.

- [ ] **Step 2: Verify the tools import and have schemas**

Run: `python -c "import tools; print(len(tools.ALL_TOOLS))"`
Expected: `3`

Interfaces consumed: `services.calendar_events`, `services.weather_for`, `memory.past_excuses_for`.

### A "Done when"

- `pytest tests/test_memory.py tests/test_services.py -v` shows 12 passed (5 + 7).
- `python -c "import tools; print(len(tools.ALL_TOOLS))"` prints `3`.
- Each tool runs standalone from a Python shell (spec Phase 1), for example `python -c "from services import weather_for; print(weather_for(\"London\"))"`.

- [ ] **Commit and open a PR to `main`**

```bash
git checkout -b dev-a
git add requirements.txt .gitignore .env.example README.md data memory.py services.py tools.py tests
git commit -m "feat: memory, services, tools and project scaffold"
git push -u origin dev-a
```

Then open a PR. Do not edit files owned by anyone else.

---

# Task B: Skeptic and prompts

Branch `dev-b`. **Depends on nobody** (`skeptic.py` imports your own `prompts.py`; the Anthropic client is faked in tests).

## B1. Prompts

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

## B2. Skeptic

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


## B3. Tune with a real key (manual, a few cents)

Run `critique` on a hand-written bad excuse (for example `"I was abducted by aliens at 2pm, also my dentist called"`) and a good one (`"My dentist moved my appointment to 3pm and I cannot reschedule."`) with recipient `"my manager"`. The bad one must score low (about 4 or less) and the good one high (7 or more). If not, adjust the wording of `SKEPTIC_SYSTEM` only; keep the accept threshold at 7.

### B "Done when"

- `pytest tests/test_skeptic.py -v` shows 3 passed.
- `python -c "import prompts; assert set(prompts.LEVELS)=={1,2,3,4}; assert 'recall_excuses' in prompts.AGENT_SYSTEM; print('ok')"` prints `ok`.
- B3 bad/good check behaves.

- [ ] **Commit and open a PR to `main`**

```bash
git checkout -b dev-b
git add prompts.py skeptic.py tests/__init__.py tests/test_skeptic.py
git commit -m "feat: prompts and skeptic subagent with structured verdict"
git push -u origin dev-b
```

Then open a PR. Do not edit files owned by anyone else.

---

# Task C: Agent loop

Branch `dev-c`. Imports `tools.ALL_TOOLS`, `prompts.AGENT_SYSTEM`, `prompts.LEVELS`, `skeptic.critique`, `skeptic.Verdict`, none of which you build. **Use the stubs** `tools.py`, `prompts.py`, `skeptic.py` from the Stubs section in `/tmp/stubs/`, and run tests with `PYTHONPATH=/tmp/stubs:. pytest tests/test_agent.py -v`.

Skip plan Step 7 (real API check). It is in Task E.

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


### C "Done when"

- `PYTHONPATH=/tmp/stubs:. pytest tests/test_agent.py -v` shows 12 passed (the parametrized test counts as 5).
- `grep -nE "thinking|temperature|tool_choice|budget_tokens" agent.py` prints nothing.
- Importing `agent` needs no API key.

- [ ] **Commit and open a PR to `main`**

```bash
git checkout -b dev-c
git add agent.py tests/__init__.py tests/test_agent.py
git commit -m "feat: excuse agent with skeptic revision loop"
git push -u origin dev-c
```

Then open a PR. Do not edit files owned by anyone else.

---

# Task D: Streamlit UI

Branch `dev-d`. Imports `agent.generate_excuse`, `memory.save_excuse`, `prompts.LEVELS`, none of which you build. **Use the stubs** `agent.py`, `skeptic.py`, `memory.py`, `prompts.py` from the Stubs section in `/tmp/stubs/` and run with `PYTHONPATH=/tmp/stubs:. streamlit run app.py --server.headless true`.

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

- [ ] **Step 3: Run the app against the stubs (no API key needed)**

Run: `PYTHONPATH=/tmp/stubs:. streamlit run app.py --server.headless true`
Expected: prints a `Local URL: http://localhost:8501`. Open it. Generate a level 2 excuse for "Friday 3pm review" to "my manager". Confirm: spinner shows, two expanders appear, the code block has a copy icon, "Mark as used" shows the success message, and clicking "Mark as used" does not wipe the expanders.

Note: the stub `generate_excuse` returns two rounds, so you can check the expanders, the copy button, and that "Mark as used" does not wipe the rounds. The no-repeat check against the real memory and agent (plan Step 4) is in Task E.

### D "Done when"

- `python -c "import ast; ast.parse(open('app.py').read()); print('ok')"` prints `ok`.
- Running against stubs: spinner shows, two expanders appear (last one open), code block has a copy icon, "Mark as used" shows the success message and the rounds stay on screen, blank inputs show the warning and do not call the agent.
- `grep -n anthropic app.py` prints nothing.

- [ ] **Commit and open a PR to `main`**

```bash
git checkout -b dev-d
git add app.py
git commit -m "feat: streamlit ui with approval step"
git push -u origin dev-d
```

Then open a PR. Do not edit files owned by anyone else.

---

# Task E: Integration and demo

Branch `dev-e`. **Independent**: prepare everything now against the Contracts; nothing here needs A to D to exist when you write it. It goes green once A to D are on `main`. Until then you can write and syntax-check the files, and run pieces against the Stubs.

## E1. Smoke script (plan Task 1, smoke steps)

Write `scripts/smoke.py` and run it with your key to confirm the key works before anyone else needs it.

- [ ] **Step 6: Write `scripts/smoke.py`**

A script that builds `anthropic.Anthropic()`, calls `client.messages.create(model="claude-haiku-5-5", max_tokens=256, messages=[{"role": "user", "content": "Say hello in five words."}])`, and prints the text of the first block whose `.type == "text"`. Use Haiku here because it is the cheapest check that the key works.

- [ ] **Step 7: Run the smoke test**

Run: `export ANTHROPIC_API_KEY=... && python scripts/smoke.py`
Expected: one short greeting line printed. If `AuthenticationError`, the key is wrong. Stop and fix before continuing.

## E2. Seed script and demo notes (plan Task 8)

- [ ] **Step 1: Write `scripts/seed_demo.py`**

Deletes `data/excuses.db` if present, then saves two excuses for recipient `"my manager"`: `"My dentist moved my appointment to 3pm."` (level 2) and `"Our building's fire alarm test overran."` (level 2). Prints `seeded`.

- [ ] **Step 2: Run it (only after A is merged; until then just syntax-check the file)**

Run: `python scripts/seed_demo.py && python -c "from memory import past_excuses_for; print(len(past_excuses_for('my manager')))"`
Expected: `seeded` then `2`

Write `docs/demo.md` (instead of a README section, so Task A owns README alone):

A demo script with these four steps, copied from the spec: level 1 for "team lunch"; level 3 for "Friday 3pm review with my manager" and open the expanders; "Mark as used" then regenerate to show no repeat; level 4 pre-emptive week plan. Note the fallback if wifi fails: weather returns "Weather unavailable" and the agent still works.

## E3. Integration tests

Create `tests/test_integration.py`. It uses the real `tools`, `memory`, `agent`, `skeptic`, `services` modules wired together and **fake critique/draft functions or a fake Anthropic client** (no real API). `memory.DB_PATH` is bound as a default argument at definition time, so monkeypatching it does nothing. Instead use `monkeypatch.chdir(tmp_path)` in a fixture: the relative `data/excuses.db` then lands in the temp dir and `init_db` creates `data/` itself. Compute the repo root with `Path(__file__).resolve().parent.parent` for anything that must read repo files (calendar, scripts). Required cases:

1. **Revise then accept:** fake `draft_fn` and a fake skeptic client returning revise then accept. `generate_excuse` returns 2 rounds and round 2's feedback equals `"; ".join(holes)` of round 1.
2. **Never accepts:** skeptic always revises. `generate_excuse(..., max_rounds=2)` returns exactly 3 rounds, no exception, last verdict is `revise`.
3. **Memory reaches the agent:** after `memory.save_excuse("my manager", "dentist", 2)`, calling `json.loads(tools.recall_excuses("my manager"))` returns `["dentist"]`.
4. **Recipient spelling:** save with `"  My Manager "`, recall with `"my manager"` returns the saved excuse.
5. **Weather offline:** `services.weather_for("London", get=raising_fn)` returns `"Weather unavailable for London."`.
6. **Seed calendar sanity:** the repo's `data/calendar.json` (read via the repo root path) has at least 6 events and every event has `date`, `time`, `title`, `attendees`.
7. **Seed script:** run `scripts/seed_demo.py` as a subprocess with `cwd=tmp_path` and `PYTHONPATH=<repo root>`. Afterwards (still chdir'd to `tmp_path`) `past_excuses_for("my manager")` has exactly 2 entries.

Expected after A to D are merged: `pytest -v` shows 27 plus your integration tests, all passed.

## E4. Real-API and demo checks on `main` (manual)

Run: `python -c "from agent import generate_excuse; h = generate_excuse('Friday 3pm review', 'my manager', 2); [print(i+1, v.believability, v.verdict, '\n', t, '\n') for i,(t,v) in enumerate(h)]"`
Expected: one to three rounds printed, each with a score and a first-person excuse. If every round prints `DECLINED`, check `stop_reason` by printing `final.stop_reason` inside `draft` temporarily.

Then:

1. `python scripts/seed_demo.py && python -c "from memory import past_excuses_for; print(len(past_excuses_for('my manager')))"` prints `seeded` then `2`.
2. Start `streamlit run app.py --server.headless true`, generate a level 2 excuse for "Friday 3pm review" to "my manager". Confirm the new excuse differs from the two seeded ones.
3. Click "Mark as used", generate again for the same recipient, confirm the new excuse differs again, and `past_excuses_for("my manager")` now lists three.
4. Rehearse the four demo steps in `docs/demo.md`. Each must finish in under 60 seconds.
5. If level 3 or 4 is slower than 60 seconds, ask Task C owner to add `output_config={"effort": "low"}` to the `tool_runner` call and rerun `pytest -v`.

### E "Done when"

- `scripts/smoke.py` prints a greeting.
- `pytest -v` on `main` is fully green, including `tests/test_integration.py`.
- Steps E4.1 to E4.4 pass on `main`.

- [ ] **Commit and open a PR to `main`**

```bash
git checkout -b dev-e
git add tests/__init__.py tests/test_integration.py scripts docs/demo.md
git commit -m "test: integration tests, smoke and seed scripts, demo notes"
git push -u origin dev-e
```

Then open a PR. Do not edit files owned by anyone else.

---

# Stubs (scratch only, never commit)

Create the files you need in `/tmp/stubs/`.

```python
# /tmp/stubs/tools.py        (needed by C)
ALL_TOOLS = [object(), object(), object()]
```

```python
# /tmp/stubs/prompts.py      (needed by C, D)
LEVELS = {1: "vague", 2: "one real fact", 3: "short saga", 4: "pre-emptive"}
AGENT_SYSTEM = "stub system prompt mentioning recall_excuses"
SKEPTIC_SYSTEM = "stub"
```

```python
# /tmp/stubs/skeptic.py      (needed by C, D)
from typing import Literal
from pydantic import BaseModel

class Verdict(BaseModel):
    believability: int
    holes: list[str]
    follow_up_question: str
    verdict: Literal["accept", "revise"]

def critique(excuse, recipient, context, client=None):
    return Verdict(believability=5, holes=["too vague"], follow_up_question="?", verdict="revise")
```

```python
# /tmp/stubs/agent.py        (needed by D)
from skeptic import Verdict

def generate_excuse(request, recipient, level, max_rounds=2, draft_fn=None, critique_fn=None):
    if not request.strip() or not recipient.strip() or level not in (1, 2, 3, 4):
        raise ValueError("bad input")
    return [
        ("Something came up.", Verdict(believability=3, holes=["vague"], follow_up_question="?", verdict="revise")),
        ("My dentist moved my appointment to 3pm.", Verdict(believability=8, holes=[], follow_up_question="", verdict="accept")),
    ]
```

```python
# /tmp/stubs/memory.py       (needed by D)
_s = {}
def save_excuse(recipient, text, level, db_path=None):
    _s.setdefault(recipient.strip().lower(), []).append(text)
def past_excuses_for(recipient, db_path=None):
    return list(_s.get(recipient.strip().lower(), []))
```
