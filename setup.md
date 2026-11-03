# setup.md: Project setup and rules for coding agents

Read this file first, then [task.md](task.md). It tells you how to set the project up, which task you own, and the rules every change must follow. If you are a coding agent (Claude Code, Codex, Cursor, etc.) working for one developer, you only do **that developer's task**.

## What this project is

Excuse Swarm. A Streamlit app: the user says what they want to get out of, who they are telling, an escalation level and a random reason theme is picked for you. A Claude Managed Agents swarm built on the [specialist-swarm starter kit](https://github.com/rosscrooke/specialist-swarm) does the work: a coordinator (the Excuse Director) delegates in parallel to a Fact Scout, a Historian and a Recipient Profiler, has a Storyteller draft the excuse, and sends it to a Critic. The Director revises at most twice and returns one JSON result. The UI shows live thread activity, every round, a Copy button, and "Mark as used", which saves to SQLite. Nothing is ever sent.

Docs: [docs/spec.md](docs/spec.md) (design), [docs/superpowers/plans/2026-11-03-excuse-swarm.md](docs/superpowers/plans/2026-11-03-excuse-swarm.md) (exact tests and steps), [task.md](task.md) (who builds what), and the starter kit repo (Managed Agents API usage).

## 1. Find your task

Ask the developer which task they own if it is not already stated: **A, B, C, D or E** (see the table in [task.md](task.md)). Then:

- Work only on the files that task owns. Never edit another task's files.
- Work on the task's branch: `dev-a`, `dev-b`, `dev-c`, `dev-d` or `dev-e`.
- Follow the task's section in `task.md` step by step. Each section carries the exact tests, signatures and a "Done when" check.
- Do not wait for other tasks. Where your code imports a module someone else builds, use the stubs from the **Stubs** section of `task.md` (see step 4).

## 2. Set up the environment

Python 3.11 or newer is required. From the repo root:

```bash
git checkout main && git pull
git checkout -b dev-<a|b|c|d|e>          # your task's branch
python3 -m venv .venv
source .venv/bin/activate
pip install anthropic streamlit pydantic pytest python-dotenv
mkdir -p tests && touch tests/__init__.py   # makes pytest put the repo root on the import path
```

Verify:

```bash
python --version                 # 3.11+
python -c "import anthropic, streamlit, pydantic, pytest; print('deps ok')"
```

## 3. API key and Managed Agents access

Real API calls need `ANTHROPIC_API_KEY` in the environment. Tests never need it.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

- Managed Agents multi-agent is a **research preview**. The key must belong to a workspace that has been granted access. Task E's `scripts/smoke.py` reports `managed agents access: ok` or `NOT AVAILABLE`.
- Never hardcode a key. Never commit `.env`. `.env.example` holds the placeholder only.
- Manual real-API steps: Task B Step 7 (creates the specialist agents), Task C Step 13 (creates the environment and coordinator), Task E Steps 1, 6 and 7.
- If a command fails with `AuthenticationError` or an access error, stop and tell the developer. Do not guess a key.

Provisioning order for a workspace (once, run by whoever has access; see spec section 5):

```bash
python setup_environment.py && python create_specialists.py && python upload_skills.py && python create_coordinator.py
```

These write `.environment_id`, `.specialist_ids.json`, `.skill_ids.json` and `.coordinator_id`. They are gitignored; never commit them.

## 4. Stubs for modules you do not own

Create a scratch folder outside the repo and copy the stub files you need from the **Stubs** section of `task.md`:

```bash
mkdir -p /tmp/stubs
# write the needed stub files (context.py, schema.py, swarm_client.py, memory.py) into /tmp/stubs/
PYTHONPATH=/tmp/stubs:. pytest tests/test_<yours>.py -v
```

Never commit stubs. Once the real module is on `main`, `git pull`, delete the stub, and rerun your tests without `PYTHONPATH`.

## 5. Non-negotiable constraints

- Model IDs: Director `claude-opus-5-5`; Profiler, Storyteller, Critic `claude-sonnet-5-5`; Fact Scout, Historian `claude-haiku-5-5`. No date suffixes. If Managed Agents rejects them, the fallback is in spec section 8; do not change them on your own.
- Managed Agents client: `Anthropic(default_headers={"anthropic-beta": "managed-agents-2026-04-01"})`. Agents use `tools=[{"type": "agent_toolset_20260401"}]`.
- No `thinking`, `budget_tokens`, `temperature`, or forced `tool_choice` in any API call.
- Every function that talks to the API takes a `client` parameter defaulting to `None` and builds the real client lazily, so importing a module never needs a key and tests inject fakes.
- Tests never call the real API. Use fakes.
- The Director's final message is exactly one JSON object `{"rounds": [{"excuse", "believability", "holes", "verdict"}]}`. The Critic replies in the fixed format `VERDICT: ACCEPT|REVISE`, `SCORE: n`, `HOLES:` bullets. Do not change either format without telling the developer; other tasks parse them.
- Nothing is ever sent to a recipient. The only side effect is SQLite writes.
- Recipients are normalized (`strip().lower()`) in memory and context so the no-repeat rule survives different spellings.
- Failure behaviour is pinned by tests: blank input raises `ValueError` before any API call; a prose Director reply falls back to one unscored round; a stream that ends without idle uses what it collected; `max_seconds` raises `TimeoutError`; a missing calendar prints `(calendar unavailable)`.
- Do not change the frozen interfaces in `task.md` without telling the developer, because the other tasks code against them.

## 6. Work loop for every step

1. Write the failing test from the task section.
2. Run it and see it fail for the expected reason.
3. Implement the minimum code to pass.
4. Run the test and see it pass.
5. Run your task's "Done when" commands before saying you are finished. Report the actual output, including failures.

Useful commands:

```bash
pytest tests/test_<yours>.py -v                # your tests only
pytest -v                                      # everything (62 tests, only meaningful after A to D are merged)
streamlit run app.py --server.headless true    # UI (tasks D, E)
python scripts/smoke.py                        # key + Managed Agents access check (task E)
```

## 7. Finish: commit and PR

```bash
git add <only the files your task owns, plus tests/__init__.py>
git commit -m "<type>: <what you built>"
git push -u origin dev-<x>
```

Then open a PR to `main` (`gh pr create`). Do not push to `main` directly. Do not merge your own PR unless the developer says so. PRs from different tasks never touch the same files, so merge order does not matter.

Commit message types used here: `feat:`, `test:`, `docs:`, `chore:`.

## 8. Task E extra: integration

Task E starts after A to D are merged. Run `git checkout main && git pull`, delete any stubs, then do Steps 5 to 7 of Task E in `task.md`: full `pytest -v`, smoke check, provisioning, one real swarm run, and the four-step demo rehearsal. Report what passed and what did not.

## 9. When something is unclear

Prefer `task.md` for what you own and the plan in `docs/superpowers/plans/` for exact steps. If they disagree, `task.md` wins. For how the Managed Agents calls look, copy the pattern from the starter kit (`create_specialists.py`, `create_coordinator.py`, `upload_skills.py`, `setup_environment.py`, `run_deal_desk.py`). If you are blocked, ask the developer; do not edit someone else's file to unblock yourself.
