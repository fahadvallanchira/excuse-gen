# Excuse Swarm: Tasks for 4 Developers + Integration

Spec: [docs/spec.md](docs/spec.md). Full plan: [docs/superpowers/plans/2026-11-03-excuse-swarm.md](docs/superpowers/plans/2026-11-03-excuse-swarm.md). Starter kit this is built on: https://github.com/rosscrooke/specialist-swarm (read its `README.md` and the `create_*.py` scripts once; the Managed Agents calls you need are copied from there).
Each task below is self-contained: exact tests, signatures and steps. Task numbers (Task 1 to 5) in the plan map to people A to E.

## How we work

1. Five independent tasks: **A, B, C, D** (build) and **E** (integration). Own files, own branch, own PR. No file is owned by two people.
2. Build against the **Frozen interfaces** below. If you import another person's module, do not wait: copy the matching file from **Stubs** into a scratch folder outside git (for example `/tmp/stubs/`) and run with `PYTHONPATH=/tmp/stubs:.`. Never commit stubs. Delete them once the real module is on `main`.
3. When your "Done when" passes, open a PR to `main`. PRs can merge in any order.
4. After A to D are merged, **E** runs end to end on `main`.
5. Everyone reads "Global Constraints" and "Review Focus" first.
6. Managed Agents is a research preview. Anyone who runs a real provisioning script needs a workspace API key with access (check with E's `scripts/smoke.py`).

Setup (everyone, from the repo root):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install anthropic streamlit pydantic pytest python-dotenv
export ANTHROPIC_API_KEY=sk-ant-...   # only for manual real-API steps, never for pytest
mkdir -p tests && touch tests/__init__.py   # include this empty file in your PR
```

## Ownership

| Task | Branch | Plan task | Files (only these) |
|---|---|---|---|
| **A** Memory and context | `dev-a` | Task 1 | `memory.py`, `context.py`, `data/calendar.json`, `data/.gitkeep`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `tests/test_memory.py`, `tests/test_context.py` |
| **B** Specialists and skills | `dev-b` | Task 2 | `specialists.py`, `create_specialists.py`, `upload_skills.py`, `skills/*/SKILL.md`, `tests/test_specialists.py` |
| **C** Coordinator and swarm client | `dev-c` | Task 3 | `schema.py`, `coordinator.py`, `swarm_client.py`, `create_coordinator.py`, `setup_environment.py`, `tests/test_schema.py`, `tests/test_coordinator.py`, `tests/test_swarm_client.py` |
| **D** Streamlit UI | `dev-d` | Task 4 | `app.py`, `tests/test_app.py` |
| **E** Integration and demo | `dev-e` | Task 5 | `tests/test_integration.py`, `scripts/seed_demo.py`, `scripts/smoke.py`, `docs/demo.md` |

`tests/__init__.py` is the one shared file: it is empty in every PR, so identical copies merge cleanly.

## Global Constraints

- Run every command from the repo root. Use a venv in the repo: `python3 -m venv .venv && source .venv/bin/activate && pip install anthropic streamlit pydantic pytest python-dotenv`.
- Model constants (spec section 3): Director `claude-opus-5-5`; Profiler, Storyteller, Critic `claude-sonnet-5-5`; Fact Scout, Historian `claude-haiku-5-5`. Define them as module constants in the file that uses them. No date suffixes.
- Managed Agents calls use a client built with `Anthropic(default_headers={"anthropic-beta": "managed-agents-2026-04-01"})`. Agents use `tools=[{"type": "agent_toolset_20260401"}]`.
- Never put `thinking`, `budget_tokens`, `temperature` or forced `tool_choice` in any API call.
- Every function that talks to the API takes a `client` parameter defaulting to `None` and builds the real client lazily, so importing a module never needs a key. No test calls the real API.
- Nothing is ever sent to a recipient. The only side effect is SQLite writes.
- Secrets come from `ANTHROPIC_API_KEY`. Never hardcode a key or commit `.env`. Generated ID files (`.environment_id`, `.specialist_ids.json`, `.skill_ids.json`, `.coordinator_id`, `.last_session_id`) are gitignored.
- Result contract (spec section 6): the Director's final message is one JSON object `{"rounds": [{"excuse", "believability", "holes", "verdict"}]}`; `verdict` is `accept` or `revise`; at most 3 rounds.
- Critic reply format (frozen, parsed by the Director): first line `VERDICT: ACCEPT` or `VERDICT: REVISE`, second line `SCORE: <1-10>`, then `HOLES:` followed by one `- ` bullet per hole (none if accepted). Accept means score 7 or more.

## Review Focus

1. **Blank request or recipient, or level outside 1 to 4.** `build_context` and `run_swarm` raise `ValueError` before any API call; the UI warns instead of calling. Tests in Tasks 1, 3, 4.
2. **Director returns prose or malformed JSON instead of the result object.** `parse_result` falls back to one unscored round holding the prose; empty output raises `ValueError`. Tests in Task 3.
3. **Stream ends without `session.status_idle`, or never ends.** `run_swarm` uses what it collected if the stream ends, raises `RuntimeError` if nothing was collected, and raises `TimeoutError` after `max_seconds`. Tests in Task 3.
4. **Recipient spelled differently across runs** ("My Manager " vs "my manager"). Memory normalises to lowercase, stripped; `build_context` uses the same normalisation. Tests in Task 1.
5. **Calendar file missing or corrupt, or no past excuses yet.** `build_context` still returns, with explicit "(calendar unavailable)" and "(none)" text so the specialists do not invent data. Weather outage is handled in the Fact Scout prompt. Tests in Tasks 1 and 2.

## Frozen interfaces

```python
# memory.py (Task 1)
DB_PATH = "data/excuses.db"
normalize(recipient: str) -> str                         # strip + lower
init_db(db_path: str = DB_PATH) -> None                  # also creates the parent dir
save_excuse(recipient: str, text: str, level: int, db_path: str = DB_PATH) -> None
past_excuses_for(recipient: str, db_path: str = DB_PATH) -> list[str]   # oldest first

# context.py (Task 1)
LEVELS: dict[int, str]                                   # keys 1..4, one-line descriptions
build_context(request: str, recipient: str, level: int, city: str = "London",
              today: date | None = None, calendar_path: str = "data/calendar.json",
              db_path: str = DB_PATH) -> str

# schema.py (Task 3)
class Round(BaseModel): excuse: str; believability: int; holes: list[str]; verdict: Literal["accept","revise"]
class SwarmResult(BaseModel): rounds: list[Round]        # property final_excuse -> str (last round)
parse_result(text: str) -> SwarmResult

# swarm_client.py (Task 3)
run_swarm(request, recipient, level, city="London", client=None, on_event=None,
          max_seconds: float = 300, clock=time.monotonic, ids_dir: str = ".") -> SwarmResult
# on_event(event: dict) with keys kind in {"thread_created","thread_running","delegate","reply","tool","message"}, agent: str, text: str

# specialists.py (Task 2)
SPECIALISTS: list[dict]            # keys: key, name, model, system   (5 entries: fact_scout, historian, profiler, storyteller, critic)
SKILL_TO_SPECIALIST: dict[str, str]
build_agent_params(spec: dict) -> dict

# coordinator.py (Task 3)
COORDINATOR_SYSTEM: str
build_coordinator_params(specialist_ids: dict[str, str]) -> dict
```

---

# Task A: Memory and context

Branch `dev-a`. **Depends on nobody.**

**Files:** Create `memory.py`, `context.py`, `data/calendar.json`, `data/.gitkeep`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`. Test: `tests/__init__.py`, `tests/test_memory.py`, `tests/test_context.py`.

**Interfaces:** Produces `memory.*` and `context.*` exactly as in Frozen interfaces. Consumes nothing.

- [ ] **Step 1: Scaffold files.** `requirements.txt` lists `anthropic streamlit pydantic pytest python-dotenv`, one per line. `.gitignore` lists `.venv/ .env data/excuses.db __pycache__/ .pytest_cache/ outputs/ .environment_id .specialist_ids.json .skill_ids.json .coordinator_id .last_session_id`. `.env.example` has `ANTHROPIC_API_KEY=sk-ant-...`. `README.md` is one paragraph: what the app does, install, `streamlit run app.py`, set `ANTHROPIC_API_KEY`, and a pointer to `setup.md`.
- [ ] **Step 2: Write `tests/test_memory.py`** with these tests (all use `tmp_path` DBs): `test_save_and_recall` (two saves for "my manager" return `["dentist","flood"]`), `test_recall_is_per_recipient`, `test_recipient_is_normalized` (save as `"  My Manager "`, recall `"my manager"`), `test_normalize`, `test_init_db_is_idempotent`, `test_init_db_creates_parent_dir` (db path `tmp_path/"sub"/"t.db"`).
- [ ] **Step 3: Run `pytest tests/test_memory.py -v`.** Expected: FAIL, `ModuleNotFoundError: No module named 'memory'`.
- [ ] **Step 4: Implement `memory.py`** with the Frozen signatures. Table `excuses(id INTEGER PRIMARY KEY, recipient TEXT, text TEXT, level INTEGER, created_at TEXT)`. `save_excuse` and `past_excuses_for` call `init_db` first. Order recall by `id`.
- [ ] **Step 5: Run `pytest tests/test_memory.py -v`.** Expected: 6 passed.
- [ ] **Step 6: Write `data/calendar.json`.** JSON list of at least 6 objects with `date` (`YYYY-MM-DD`), `time` (`HH:MM`), `title`, `attendees` (list), spread over 2026-11-03 to 2026-11-10; at least two obviously skippable ("Q4 synergy alignment", "Mandatory fun: trust falls"), at least one blameable ("Dentist", "Car service"), and one "Friday 3pm review" with "manager" on 2026-11-06.
- [ ] **Step 7: Write `tests/test_context.py`** with a `cal(tmp_path, events)` helper writing a calendar file. Tests:
  - `test_context_includes_request_recipient_level_city_and_today`: output contains the request, recipient, `Level: 2`, the level's `LEVELS[2]` text, `City: Paris`, and `Today: 2026-11-03` for `today=date(2026,11,3)`.
  - `test_context_lists_next_seven_days_only`: with `today=date(2026,11,3)`, events on 2026-11-03 and 2026-11-09 appear and one on 2026-11-10 does not (window is today through today + 6 days).
  - `test_context_lists_past_excuses_normalized`: save with `"  My Manager "`, build for `"my manager"`, text appears under a `DOCUMENT: past-excuses` header.
  - `test_context_no_history_says_none`: output has `(none)` under past-excuses.
  - `test_context_missing_calendar_does_not_raise`: nonexistent path gives `(calendar unavailable)`; a file containing `not json` gives the same.
  - `test_context_rejects_blank_and_bad_level`: parametrised over `("", "boss", 2)`, `("  ", "boss", 2)`, `("x", "", 2)`, `("x", "boss", 0)`, `("x", "boss", 5)`, each raises `ValueError`.
  - `test_levels_has_keys_1_to_4`.
- [ ] **Step 8: Run `pytest tests/test_context.py -v`.** Expected: FAIL, `ModuleNotFoundError: No module named 'context'`.
- [ ] **Step 9: Implement `context.py`.** `LEVELS` text (exact): 1 "Vague and low-risk. Something like 'something came up'. No details that could be checked."; 2 "Tied to one real fact from the calendar or weather. Short and believable."; 3 "A short saga with two or three supporting details that are internally consistent. Still plausible."; 4 "Pre-emptive. Look at the next seven days of calendar, pick the meetings the user will most want to skip, and propose one excuse per meeting." `build_context` returns documents joined by blank lines, each introduced by `=====  DOCUMENT: <name>  =====` (the kit's format): `request.md` (Today, Escape, Recipient, Level plus its description, City), `calendar.md` (one line per event `date time title (attendees)`, window today through today+6), `past-excuses.md` (one bullet per excuse, or `(none)`). Normalise the recipient with `memory.normalize` for lookup but print the original spelling in `request.md`. Catch `OSError` and `ValueError` (includes JSON errors) around calendar loading.
- [ ] **Step 10: Run `pytest -v`.** Expected: 17 passed (memory 6, context 11; the parametrised blank/level test counts as 5).
- [ ] **Step 11: Commit** `feat: memory, context builder, project scaffold`.

- [ ] **Open a PR to `main`.** `git push -u origin dev-a` and `gh pr create`. Do not edit files owned by anyone else.

---

# Task B: Specialists and skills

Branch `dev-b`. **Depends on nobody.** The Managed Agents calls in `create_specialists.py` and `upload_skills.py` are copied from the starter kit's files of the same names.

**Files:** Create `specialists.py`, `create_specialists.py`, `upload_skills.py`, `skills/fact-grounding/SKILL.md`, `skills/recipient-personas/SKILL.md`, `skills/excuse-playbook/SKILL.md`, `skills/believability-rubric/SKILL.md`. Test: `tests/test_specialists.py`.

**Interfaces:** Produces `SPECIALISTS`, `SKILL_TO_SPECIALIST`, `build_agent_params` (Frozen interfaces). Consumes nothing from other tasks. Writes `.specialist_ids.json` (`{"fact_scout": id, "historian": id, "profiler": id, "storyteller": id, "critic": id}`) and `.skill_ids.json` when run for real.

Model constants in `specialists.py`: `MODEL_FAST = "claude-haiku-5-5"`, `MODEL_SPECIALIST = "claude-sonnet-5-5"`.

- [ ] **Step 1: Write `tests/test_specialists.py`.**
  - `test_five_specialists_with_expected_keys`: keys in order `fact_scout, historian, profiler, storyteller, critic`; each has non-empty `name`, `model`, `system`.
  - `test_models`: `fact_scout` and `historian` use `claude-haiku-5-5`; the other three `claude-sonnet-5-5`.
  - `test_critic_reply_format_is_documented`: critic system contains `VERDICT: ACCEPT`, `VERDICT: REVISE`, `SCORE:`, `HOLES:` and `7`.
  - `test_fact_scout_handles_weather_outage_and_uses_open_meteo`: system contains `Open-Meteo` and `weather unavailable`.
  - `test_historian_bans_reuse`: system contains `never` (case-insensitive) and `past-excuses`.
  - `test_storyteller_mentions_all_four_levels`: system contains `Level 1` through `Level 4`.
  - `test_skill_mapping`: `SKILL_TO_SPECIALIST == {"fact-grounding":"fact_scout","recipient-personas":"profiler","excuse-playbook":"storyteller","believability-rubric":"critic"}`.
  - `test_every_skill_dir_has_valid_skill_md`: for each skill name, `skills/<name>/SKILL.md` exists, starts with `---`, frontmatter has `name: <dir name>` and a non-empty `description:` line, body is longer than 200 characters.
  - `test_build_agent_params`: returns dict with `name`, `model`, `system`, `tools == [{"type": "agent_toolset_20260401"}]`, and `metadata["role"] == spec["key"]`.
- [ ] **Step 2: Run `pytest tests/test_specialists.py -v`.** Expected: FAIL, `ModuleNotFoundError: No module named 'specialists'`.
- [ ] **Step 3: Write the four `SKILL.md` files.** Each starts with YAML frontmatter (`name`, `description`: when to trigger) and a body of at least 200 characters of real guidance:
  - `fact-grounding`: how to turn calendar lines and weather into usable facts, which facts are checkable by a recipient, how to cite `calendar.md` lines, Open-Meteo URL pattern `https://api.open-meteo.com/v1/forecast?latitude=<lat>&longitude=<lon>&current_weather=true` with lat/lon for london, new york, san francisco, bangalore, dubai.
  - `recipient-personas`: personas (strict manager, chill friend, suspicious partner, distant relative) with what each believes, tone and red flags.
  - `excuse-playbook`: the four levels with do/don't examples, first-person voice, no preamble, level 4 one-line-per-meeting format.
  - `believability-rubric`: score anchors 1 to 10, the checkable-detail test, too-convenient and rehearsed tells, accept at 7 or more.
- [ ] **Step 4: Implement `specialists.py`.** `SPECIALISTS` entries follow the kit's `create_specialists.py` shape. System prompts, one decision each:
  - Fact Scout: reads `calendar.md` and the `City` line, fetches current weather from Open-Meteo with web fetch, replies with at most 8 bullet facts; if weather cannot be fetched says `weather unavailable` and continues; never invents calendar events.
  - Historian: reads `past-excuses.md`, replies with the list to avoid and the themes already used (for example dentist, car); never suggests an excuse itself.
  - Profiler: reads `request.md`, replies with recipient type, tone, what they would believe, red flags, in at most 6 lines.
  - Storyteller: given facts, history, profile, level and optional critic holes, writes only the excuse in first person; follows the playbook skill; never reuses a banned excuse; level 4 returns one line per meeting prefixed with the meeting title and a colon.
  - Critic: plays the mildly suspicious recipient; replies only in the frozen format (first line `VERDICT: ACCEPT` or `VERDICT: REVISE`, `SCORE: n`, `HOLES:` bullets); accept at 7 or more.
  `build_agent_params(spec)` returns `name`, `model`, `system`, `tools=[{"type": "agent_toolset_20260401"}]`, `metadata={"project": "excuse-swarm", "role": spec["key"]}`.
- [ ] **Step 5: Run `pytest tests/test_specialists.py -v`.** Expected: 9 passed.
- [ ] **Step 6: Write `create_specialists.py` and `upload_skills.py`** adapted from the kit's files of the same names: iterate `SPECIALISTS`, call `client.beta.agents.create(**build_agent_params(spec))`, save `.specialist_ids.json`; `upload_skills.py` reuses existing skills by `display_title`, uploads with `files_from_dir`, attaches to the mapped specialist skipping duplicates, writes `.skill_ids.json`. Both read `ANTHROPIC_API_KEY`, exit with a clear message when missing, and put any real call under `main()` so importing is safe. Verify: `python -c "import create_specialists, upload_skills; print('ok')"` prints `ok` with no key set.
- [ ] **Step 7: Manual (needs a key and Managed Agents access):** run both scripts. Expected: five "Created ..." lines, then skills attached. Fix prompt wording only if the Critic's reply format is not followed (check in the console session view).
- [ ] **Step 8: Commit** `feat: specialist agents and skills`.

- [ ] **Open a PR to `main`.** `git push -u origin dev-b` and `gh pr create`. Do not edit files owned by anyone else.

---

# Task C: Result schema, coordinator, and swarm client

Branch `dev-c`. Imports `context.build_context` (Task A). **Use the `context.py` stub** from Stubs. Provisioning scripts are adapted from the kit's `create_coordinator.py` and `setup_environment.py`.

**Files:** Create `schema.py`, `coordinator.py`, `swarm_client.py`, `create_coordinator.py`, `setup_environment.py`. Test: `tests/test_schema.py`, `tests/test_coordinator.py`, `tests/test_swarm_client.py`.

**Interfaces:** Produces `schema.*`, `coordinator.*`, `swarm_client.run_swarm` (Frozen interfaces). Consumes `context.build_context` (Task 1; use a stub in isolation) and, at run time, `.coordinator_id` and `.environment_id` in `ids_dir`. `COORDINATOR_MODEL = "claude-opus-5-5"`.

- [ ] **Step 1: Write `tests/test_schema.py`.**
  - `test_parse_bare_json`: two-round JSON parses; `final_excuse` is the last round's excuse.
  - `test_parse_fenced_json`: the same JSON wrapped in a fenced `json` block.
  - `test_parse_json_with_prose_around_it`: text before and after the object still parses (first `{` to last `}`).
  - `test_prose_falls_back_to_single_round`: `"Sorry, my dentist moved my appointment."` gives one round with `believability == 0`, `holes == ["unparsed output"]`, `verdict == "revise"`, same excuse text.
  - `test_empty_raises`: `""` and `"   "` raise `ValueError`.
  - `test_bad_verdict_value_falls_back`: JSON with `"verdict": "maybe"` falls back to a single prose round.
  - `test_empty_rounds_falls_back`: `{"rounds": []}` falls back to a single prose round.
- [ ] **Step 2: Run `pytest tests/test_schema.py -v`.** Expected: FAIL, `ModuleNotFoundError: No module named 'schema'`.
- [ ] **Step 3: Implement `schema.py`.** `Round`, `SwarmResult` (property `final_excuse`), and `parse_result` using `json.loads` on the first `{` to last `}` slice and `SwarmResult.model_validate`; on any parse or validation failure or zero rounds return the prose fallback. Strip before checking emptiness.
- [ ] **Step 4: Run `pytest tests/test_schema.py -v`.** Expected: 7 passed.
- [ ] **Step 5: Write `tests/test_coordinator.py`.**
  - `test_params_roster_has_all_five_in_order`: with ids for the five keys, `params["multiagent"] == {"type":"coordinator","agents":[{"type":"agent","id":...}, ...]}` in key order `fact_scout, historian, profiler, storyteller, critic`.
  - `test_params_model_name_tools`: `model == "claude-opus-5-5"`, `name == "Excuse Director"`, `tools == [{"type":"agent_toolset_20260401"}]`.
  - `test_missing_specialist_raises`: dropping `critic` raises `KeyError`.
  - `test_system_orders_parallel_delegation`: system contains `SINGLE message`, `Fact Scout`, `Historian`, `Recipient Profiler`, `Storyteller`, `Critic`.
  - `test_system_caps_revisions_and_pins_result_format`: system contains `at most 2`, `"rounds"`, `"believability"`, `"holes"`, `"verdict"`, and `only the JSON`.
- [ ] **Step 6: Run `pytest tests/test_coordinator.py -v`.** Expected: FAIL, `ModuleNotFoundError: No module named 'coordinator'`.
- [ ] **Step 7: Implement `coordinator.py`.** `COORDINATOR_SYSTEM` follows the kit's coordinator prompt: roster, then the run order (1 read the request; 2 delegate to Fact Scout, Historian and Recipient Profiler in a SINGLE message; 3 give the Storyteller their outputs, the level and any banned excuses; 4 send the draft with the recipient to the Critic; 5 if REVISE send the holes back to the Storyteller and re-submit to the Critic, at most 2 revisions; 6 stop on ACCEPT or after the cap, always returning the last draft), then the output rule: reply with only the JSON object from the result contract, nothing else. `build_coordinator_params(ids)` indexes `ids` by the five keys (raises `KeyError`) and builds the dict as the kit does. `create_coordinator.py` and `setup_environment.py` are adapted from the kit (same file names; coordinator script reads `.specialist_ids.json`, writes `.coordinator_id`; environment script writes `.environment_id`, reusing it if present). Both are safe to import with no key.
- [ ] **Step 8: Run `pytest tests/test_coordinator.py -v`.** Expected: 5 passed.
- [ ] **Step 9: Write `tests/test_swarm_client.py`** with fakes: `FakeStream` (context manager, iterates scripted event objects built with `types.SimpleNamespace`), `FakeEvents` (`stream(session_id)` returns the stream, `send(session_id, events=...)` records the call), `FakeClient` exposing `beta.sessions.create(...)` (returns object with `id="sess_1"`) and `beta.sessions.events`. A fixture writes `.coordinator_id` and `.environment_id` into `tmp_path` and passes `ids_dir=str(tmp_path)`; calendar and memory paths do not matter because tests pass `context_fn` indirectly: monkeypatch `swarm_client.build_context` to return `"CTX"`. Tests:
  - `test_returns_parsed_result_and_sends_one_user_message`: events thread_created (agent_name `Fact Scout`), agent.message with JSON text, status_idle; result has the rounds; `events.send` called once with `type == "user.message"` and text containing `CTX`.
  - `test_session_created_with_ids`: `sessions.create` called with `agent` and `environment_id` equal to the file contents.
  - `test_on_event_receives_kinds_in_order`: scripted events thread_created, thread_status_running, thread_message_sent, thread_message_received, tool_use, agent.message, idle map to kinds `thread_created, thread_running, delegate, reply, tool, message`; each event dict has keys `kind`, `agent`, `text`.
  - `test_stream_end_without_idle_uses_collected_text`.
  - `test_no_output_raises_runtime_error`: idle with no agent.message raises `RuntimeError`.
  - `test_prose_output_falls_back`: agent.message with plain prose gives a one-round result.
  - `test_timeout_raises`: injected `clock` returning 0 then 1000 with `max_seconds=10` raises `TimeoutError`.
  - `test_blank_input_raises_before_any_client_call` (parametrised like Task 1; assert `sessions.create` never called).
  - `test_missing_id_files_raises_filenotfound_with_hint`: message mentions `create_coordinator.py`.
- [ ] **Step 10: Run `pytest tests/test_swarm_client.py -v`.** Expected: FAIL, `ModuleNotFoundError: No module named 'swarm_client'`.
- [ ] **Step 11: Implement `swarm_client.py`.** Validate input first (`ValueError`); read the two ID files from `ids_dir`; lazily build the client with the beta header; `sessions.create(agent=..., environment_id=..., title="Excuse request")`; open `events.stream(session.id)`, send the user message (task instructions: run the Excuse Desk process for the level, return only the result JSON, followed by `build_context(...)`), iterate events as in the kit's `run_deal_desk.py`, translate to `on_event` dicts, collect `agent.message` text blocks, break on `session.status_idle`, check the deadline before handling each event. Return `parse_result("".join(collected))`; raise `RuntimeError("swarm produced no output")` when nothing was collected. Import as `from context import build_context` so tests can monkeypatch it.
- [ ] **Step 12: Run `pytest tests/test_schema.py tests/test_coordinator.py tests/test_swarm_client.py -v`.** Expected: 7 + 5 + 13 = 25 passed (the parametrised blank-input test counts as 5).
- [ ] **Step 13: Manual (needs key and access):** `python setup_environment.py`, then after Task 2's scripts have run `python create_coordinator.py`. Expected: `Coordinator created: ...` and the roster of five keys.
- [ ] **Step 14: Commit** `feat: swarm client, coordinator and result schema`.

- [ ] **Open a PR to `main`.** `git push -u origin dev-c` and `gh pr create`. Do not edit files owned by anyone else.

---

# Task D: Streamlit UI

Branch `dev-d`. Imports `swarm_client.run_swarm`, `schema`, `memory.save_excuse`, `context.LEVELS`, none of which you build. **Use the stubs** `swarm_client.py`, `schema.py`, `memory.py`, `context.py` from Stubs. Run tests with `PYTHONPATH=/tmp/stubs:. pytest tests/test_app.py -v`.

**Files:** Create `app.py`. Test: `tests/test_app.py` (uses `streamlit.testing.v1.AppTest`).

**Interfaces:** Consumes `swarm_client.run_swarm`, `schema.SwarmResult`/`Round`, `memory.save_excuse`, `context.LEVELS`. Produces nothing. No Anthropic SDK import in `app.py`.

- [ ] **Step 1: Write `tests/test_app.py`.** Each test uses `monkeypatch` to replace `swarm_client.run_swarm` with a fake that records its calls in a list, calls `on_event` twice, and returns a two-round `SwarmResult` (round 1: believability 3, one hole, `revise`; round 2: believability 8, no holes, `accept`), and to replace `memory.save_excuse` with a fake that appends its arguments to a list. Patching happens before `AppTest.from_file("app.py").run()`, and `app.py` imports with `from swarm_client import run_swarm` and `from memory import save_excuse` at script run time, so the patched names are picked up. The same tests pass against stub modules or the real ones. Tests:
  - `test_blank_inputs_warn_and_do_not_call_swarm`: click Generate with empty fields; a warning containing `Fill in both fields.` exists and the fake's call list is empty.
  - `test_generate_shows_two_rounds_and_final_code`: fill request and recipient, click Generate; two expanders whose labels contain `Round 1: believability 3/10` and `Round 2: believability 8/10`; one code block whose value equals round 2's excuse.
  - `test_mark_as_used_saves_and_keeps_rounds`: after Generate, click "Mark as used"; the save fake received `("my manager", final_text, 2)`, a success message contains `Saved.`, and both expanders are still present.
  - `test_swarm_error_is_shown`: the fake raises `RuntimeError("boom")`; an error element contains `boom`.
  - `test_level_caption_follows_default_slider`: with no interaction the caption equals `LEVELS[2]`.
- [ ] **Step 2: Run `PYTHONPATH=/tmp/stubs:. pytest tests/test_app.py -v`.** Expected: FAIL, `app.py` not found.
- [ ] **Step 3: Implement `app.py`.** `st.title("Excuse Swarm")`; `st.text_input` for "What do you need to get out of?", "Who are you telling?", "City (for weather)" default "London"; `st.slider("Escalation level", 1, 4, 2)` then `st.caption(LEVELS[level])`; Generate button. Blank request or recipient: `st.warning("Fill in both fields.")`, no call. Otherwise inside `st.status("Briefing the swarm...", expanded=True)` call `run_swarm(..., on_event=cb)` where `cb` writes one line per event into the status container (for example `Fact Scout joined`, `Director → Critic`, `Critic replied`); wrap in `try/except Exception as e` showing `st.error(str(e))`. Store result, recipient and level in `st.session_state`; render from session state. One `st.expander(f"Round {i}: believability {r.believability}/10", expanded=(i == last))` per round with `st.write(excuse)` and, when holes exist, `st.caption("Critic found: " + "; ".join(holes))`. Then `st.code(final_excuse, language=None)` and a "Mark as used" button that calls `save_excuse(recipient, final_excuse, level)` using the stored values and shows `st.success("Saved. This one will never be used on them again.")`.
- [ ] **Step 4: Run `PYTHONPATH=/tmp/stubs:. pytest tests/test_app.py -v`.** Expected: 5 passed.
- [ ] **Step 5: Manual:** `PYTHONPATH=/tmp/stubs:. streamlit run app.py --server.headless true`; confirm the live status lines, copy icon on the code block, and rounds staying after "Mark as used".
- [ ] **Step 6: Commit** `feat: streamlit ui with live swarm feed`.

- [ ] **Open a PR to `main`.** `git push -u origin dev-d` and `gh pr create`. Do not edit files owned by anyone else.

---

# Task E: Integration, demo, and real-API checks

Branch `dev-e`. **Independent**: write everything now against the Frozen interfaces; it goes green once A to D are on `main`. Until then you can write and syntax-check the files and run pieces against the Stubs.

**Files:** Create `tests/test_integration.py`, `scripts/seed_demo.py`, `scripts/smoke.py`, `docs/demo.md`.

**Interfaces:** Consumes everything from Tasks 1 to 4 on `main`. Everything in this task can be written beforehand against the Frozen interfaces; it runs green after Tasks 1 to 4 merge.

- [ ] **Step 1: Write `scripts/smoke.py`:** build `anthropic.Anthropic()` with the Managed Agents beta header, call `client.messages.create(model="claude-haiku-5-5", max_tokens=256, messages=[{"role":"user","content":"Say hello in five words."}])` and print the first text block; then try `client.beta.environments.list()` inside `try/except Exception` and print `managed agents access: ok` or `managed agents access: NOT AVAILABLE (<error>)`. Expected output with a valid key and access: a greeting and `managed agents access: ok`.
- [ ] **Step 2: Write `scripts/seed_demo.py`:** delete `data/excuses.db` if present, save two excuses for `"my manager"` ("My dentist moved my appointment to 3pm." and "Our building's fire alarm test overran.", both level 2), print `seeded`.
- [ ] **Step 3: Write `docs/demo.md`:** the four demo steps from spec section 7, the provisioning order from spec section 5, and the fallbacks (weather outage: Fact Scout says unavailable and continues; model IDs rejected: swap the three constants).
- [ ] **Step 4: Write `tests/test_integration.py`** using real `memory`, `context`, `schema`, `swarm_client` and a fake Managed Agents client (reuse the fake-stream pattern from Task 3's tests, copied here because test files are not shared). Fixture: `monkeypatch.chdir(tmp_path)` (so relative `data/excuses.db` lands in a temp dir), ID files written there, calendar path passed via the repo root `Path(__file__).resolve().parent.parent / "data" / "calendar.json"`. Tests:
  - `test_session_message_contains_real_context`: after `save_excuse("  My Manager ", "dentist", 2)`, `run_swarm("Friday 3pm review", "my manager", 2, ...)` sends a user message containing `dentist`, `Friday 3pm review` and a calendar line from the seed file.
  - `test_revise_then_accept_flow_reaches_ui_shape`: fake Director JSON with two rounds gives `final_excuse` equal to round 2's excuse and `rounds[0].verdict == "revise"`.
  - `test_prose_director_output_still_returns_a_result`.
  - `test_seed_calendar_is_valid`: at least 6 events with keys `date, time, title, attendees`.
  - `test_seed_script_leaves_two_excuses`: run `scripts/seed_demo.py` via `subprocess` with `cwd=tmp_path` and `PYTHONPATH` set to the repo root; afterwards `past_excuses_for("my manager")` (cwd still `tmp_path`) has two entries.
  - `test_blank_recipient_never_creates_session`.
- [ ] **Step 5: Run `pytest -v` on `main` after Tasks 1 to 4 merge.** Expected: all green, 62 tests (memory 6, context 11, specialists 9, schema 7, coordinator 5, swarm client 13, app 5, integration 6).
- [ ] **Step 6: Real checks (manual, needs key and Managed Agents access):** `python scripts/smoke.py`. Then provision in order `python setup_environment.py && python create_specialists.py && python upload_skills.py && python create_coordinator.py`. If agent creation rejects a model ID, apply the model-ID fallback from spec section 8 in `specialists.py` and `coordinator.py` (the owners of those constants) and re-run.
- [ ] **Step 7: End-to-end:** `python scripts/seed_demo.py`, then `python -c "from swarm_client import run_swarm; r = run_swarm('Friday 3pm review','my manager',2, on_event=print); [print(x) for x in r.rounds]"`. Expected: thread events for the specialists, one to three rounds, and an excuse that differs from both seeded ones. Then `streamlit run app.py --server.headless true` and rehearse the four demo steps from `docs/demo.md`; each should finish in under 90 seconds. If slower, tell the Task 3 owner to lower the Director to a faster model or cap Critic rounds.
- [ ] **Step 8: Commit** `test: integration tests, smoke and seed scripts, demo notes`.

- [ ] **Open a PR to `main`.** `git push -u origin dev-e` and `gh pr create`. Do not edit files owned by anyone else.

---

# Stubs (scratch only, never commit)

Create the files you need in `/tmp/stubs/`.

```python
# /tmp/stubs/context.py       (needed by C and D)
from datetime import date
LEVELS = {1: "vague", 2: "one real fact", 3: "short saga", 4: "pre-emptive"}
def build_context(request, recipient, level, city="London", today=None, calendar_path="data/calendar.json", db_path="data/excuses.db"):
    if not request.strip() or not recipient.strip() or level not in LEVELS:
        raise ValueError("bad input")
    return "CTX"
```

```python
# /tmp/stubs/schema.py        (needed by D)
from typing import Literal
from pydantic import BaseModel

class Round(BaseModel):
    excuse: str
    believability: int
    holes: list[str]
    verdict: Literal["accept", "revise"]

class SwarmResult(BaseModel):
    rounds: list[Round]
    @property
    def final_excuse(self) -> str:
        return self.rounds[-1].excuse
```

```python
# /tmp/stubs/swarm_client.py  (needed by D)
from schema import Round, SwarmResult

def run_swarm(request, recipient, level, city="London", client=None, on_event=None, **kw):
    if on_event:
        on_event({"kind": "thread_created", "agent": "Fact Scout", "text": ""})
        on_event({"kind": "reply", "agent": "Critic", "text": ""})
    return SwarmResult(rounds=[
        Round(excuse="Something came up.", believability=3, holes=["vague"], verdict="revise"),
        Round(excuse="My dentist moved my appointment to 3pm.", believability=8, holes=[], verdict="accept"),
    ])
```

```python
# /tmp/stubs/memory.py        (needed by D)
_s = {}
def save_excuse(recipient, text, level, db_path=None):
    _s.setdefault(recipient.strip().lower(), []).append(text)
def past_excuses_for(recipient, db_path=None):
    return list(_s.get(recipient.strip().lower(), []))
```
