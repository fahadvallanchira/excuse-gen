# setup.md: Project setup and rules for coding agents

Read this file first, then [task.md](task.md). It tells you how to set the project up, which task you own, and the rules every change must follow. If you are a coding agent (Claude Code, Codex, Cursor, etc.) working for one developer, you only do **that developer's task**.

## What this project is

Excuse Generator. A Streamlit app: the user says what they want to get out of and who they are telling. An Opus agent (`claude-opus-5-5`) gathers context with tools (calendar, weather, past excuses) and drafts an excuse. A Haiku skeptic (`claude-haiku-5-5`) scores it and lists holes. The loop revises at most twice. Nothing is ever sent; the UI offers Copy and "Mark as used", which saves to SQLite.

Docs: [docs/spec.md](docs/spec.md) (design), [docs/superpowers/plans/2026-11-03-excuse-generator.md](docs/superpowers/plans/2026-11-03-excuse-generator.md) (exact code and tests), [task.md](task.md) (who builds what).

## 1. Find your task

Ask the developer which task they own if it is not already stated: **A, B, C, D or E** (see the table in [task.md](task.md)). Then:

- Work only on the files that task owns. Never edit another task's files.
- Work on the task's branch: `dev-a`, `dev-b`, `dev-c`, `dev-d` or `dev-e`.
- Follow the task's section in `task.md` step by step. Each section carries the exact code, tests and a "Done when" check.
- Do not wait for other tasks. Where your code imports a module someone else builds, use the stubs from the **Stubs** section of `task.md` (see step 4).

## 2. Set up the environment

Python 3.11 or newer is required. From the repo root:

```bash
git checkout main && git pull
git checkout -b dev-<a|b|c|d|e>          # your task's branch
python3 -m venv .venv
source .venv/bin/activate
pip install anthropic streamlit pydantic requests pytest
mkdir -p tests && touch tests/__init__.py   # makes pytest put the repo root on the import path
```

Verify:

```bash
python --version                 # 3.11+
python -c "import anthropic, streamlit, pydantic, requests, pytest; print('deps ok')"
```

## 3. API key

Real API calls need `ANTHROPIC_API_KEY` in the environment. Tests never need it.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

- Never hardcode a key. Never commit `.env`. `.env.example` holds the placeholder only.
- Only manual checks use the key: `scripts/smoke.py` (task E), the real-API run in task E, and the prompt tuning in task B.
- If a command fails with `AuthenticationError`, stop and tell the developer. Do not guess a key.

## 4. Stubs for modules you do not own

Create a scratch folder outside the repo and copy the stub files you need from the **Stubs** section of `task.md`:

```bash
mkdir -p /tmp/stubs
# write the needed stub files (tools.py, prompts.py, skeptic.py, agent.py, memory.py) into /tmp/stubs/
PYTHONPATH=/tmp/stubs:. pytest tests/test_<yours>.py -v
```

Never commit stubs. Once the real module is on `main`, `git pull`, delete the stub, and rerun your tests without `PYTHONPATH`.

## 5. Non-negotiable constraints

- Model IDs are exactly `claude-opus-5-5` (agent) and `claude-haiku-5-5` (skeptic). No date suffixes.
- No `thinking`, `budget_tokens`, `temperature`, or forced `tool_choice` in any API call. These return 400 on these models.
- Structured output: `client.messages.parse(..., output_format=Model)`, read `response.parsed_output`. Never parse JSON from text by hand.
- Every function that calls the Claude API takes a `client` parameter that defaults to a lazily created module-level client, so importing a module never needs a key and tests inject fakes.
- Tests never call the real API. Use fakes.
- Nothing is ever sent to a recipient. The only side effect is SQLite writes.
- Recipients are normalized (`strip().lower()`) in memory so the no-repeat rule survives different spellings.
- `weather_for` never raises. `draft` never raises on a missing text block (returns `DECLINED`). `generate_excuse` never loops past `max_rounds + 1` drafts.
- Do not change the frozen contracts in `task.md` without telling the developer, because the other tasks code against them.

## 6. Work loop for every step

1. Write the failing test from the task section.
2. Run it and see it fail for the expected reason.
3. Implement the minimum code to pass.
4. Run the test and see it pass.
5. Run your task's "Done when" commands before saying you are finished. Report the actual output, including failures.

Useful commands:

```bash
pytest tests/test_<yours>.py -v            # your tests only
pytest -v                                  # everything (only meaningful after A to D are merged)
streamlit run app.py --server.headless true   # UI (task D, E)
python scripts/smoke.py                    # one real API call (task E)
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

Task E starts after A to D are merged. Run `git checkout main && git pull`, delete any stubs, then do the E4 section of `task.md`: full `pytest -v`, seed script, one real-API run, the no-repeat check in the live app, and the four-step demo rehearsal. Report what passed and what did not.

## 9. When something is unclear

Prefer the plan in `docs/superpowers/plans/` for exact code. Prefer `task.md` for what you own. If the two disagree, `task.md` wins (it records fixes the plan lacks, for example that `init_db` creates the `data/` folder). If you are blocked, ask the developer; do not edit someone else's file to unblock yourself.
