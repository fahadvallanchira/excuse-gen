# Excuse Swarm: Spec

Built on the [specialist-swarm starter kit](https://github.com/rosscrooke/specialist-swarm): Claude Managed Agents multi-agent (coordinator + specialist sub-agents) with custom Skills. Stack: Python 3.11+, `anthropic` SDK, Streamlit, SQLite, pydantic.

The kit's Deal Desk (RFP in, branded proposal out) becomes an **Excuse Desk** (what you need to get out of in, a vetted excuse out). Same architecture: a coordinator fans work out to specialists in parallel, each with its own skill, then synthesises. We keep the kit's file shape (`create_*.py`, `skills/`, event-stream runner) and add a Streamlit front end and SQLite memory.

## 1. What we are building

A user types what they need to get out of ("Friday 3pm review"), who they are telling ("my manager"), an escalation level 1 to 4, and optionally a city. A coordinator agent (the **Excuse Director**) runs a swarm:

1. **Fact Scout** finds real facts: that week's calendar events and today's weather.
2. **Historian** reads the excuses already used on this recipient and lists what must not be reused.
3. **Recipient Profiler** says what this kind of person would believe and what tone suits them.
4. **Storyteller** drafts the excuse at the chosen level using its playbook skill.
5. **Critic** plays the suspicious recipient, scores believability 1 to 10 and lists holes.
6. The Director revises with the Storyteller until the Critic accepts, at most 2 revisions.
7. The Director returns one JSON result: every round with excuse, score, holes and verdict.

Steps 1 to 3 run in parallel (one message, three delegations). The Streamlit page shows the thread fan-out live, then every round, then the final excuse with a Copy button and "Mark as used". Nothing is ever sent automatically.

## 2. Architecture

```
Streamlit app.py ──► swarm_client.run_swarm() ──► Managed Agents session
   ▲   live events (thread spawned, reply, ...)        │
   │                                                    ▼
   │                                          Excuse Director (coordinator)
   │                    ┌──────────────┬────────────┬────┴───────┬──────────────┐
   │                    ▼              ▼            ▼            ▼              ▼
   │               Fact Scout     Historian     Profiler    Storyteller       Critic
   │               (web fetch,    (reads past   (skill:     (skill:           (skill:
   │                fact-         excuses)      recipient-   excuse-           believability-
   │                grounding)                  personas)    playbook)         rubric)
   │
   └── SwarmResult (pydantic) ◄── Director's final JSON
SQLite (memory.py): past excuses per recipient. The app inlines them into the session
message via context.build_context(); "Mark as used" writes new ones.
```

Context is inlined into the user message as documents, the way the kit inlines the RFP and past wins. Calendar events and past excuses come from our app. Weather is fetched by the Fact Scout with the agent toolset's web fetch from Open-Meteo.

## 3. Roles and models

| Agent | Job | Skill | Model |
|---|---|---|---|
| Excuse Director | orchestrates, synthesises, returns JSON | none | `claude-opus-5-5` |
| Fact Scout | calendar and weather facts | `fact-grounding` | `claude-haiku-5-5` |
| Historian | past excuses, repeat ban | none | `claude-haiku-5-5` |
| Recipient Profiler | tone and what this person believes | `recipient-personas` | `claude-sonnet-5-5` |
| Storyteller | drafts the excuse per level | `excuse-playbook` | `claude-sonnet-5-5` |
| Critic | scores and pokes holes | `believability-rubric` | `claude-sonnet-5-5` |

The starter kit uses `claude-opus-4-7`, `claude-sonnet-4-6` and `claude-haiku-4-5-20251001`. Managed Agents is a research preview, so the first real run must confirm the workspace accepts the Claude 5 IDs above. If it does not, swap the three constants for the kit's IDs; nothing else changes.

## 4. Escalation levels

1. Vague and low-risk ("something came up"). No checkable details.
2. Tied to one real fact from the calendar or weather. Short.
3. A short saga with two or three consistent supporting details.
4. Pre-emptive: scan the next seven days, pick the meetings the user most wants to skip, one excuse per meeting (one line per meeting, prefixed with the meeting title and a colon).

## 5. Repo layout

```
exc-gen/
├── app.py                     # Streamlit UI (live event feed, rounds, copy, Mark as used)
├── context.py                 # LEVELS, build_context(): inlines calendar + past excuses
├── memory.py                  # SQLite past excuses
├── schema.py                  # Round, SwarmResult, parse_result()
├── swarm_client.py            # run_swarm(): session, event stream, result parsing
├── specialists.py             # SPECIALISTS definitions, SKILL_TO_SPECIALIST
├── coordinator.py             # COORDINATOR_SYSTEM, build_coordinator_params()
├── create_specialists.py      # kit-style: creates 5 sub-agents -> .specialist_ids.json
├── upload_skills.py           # kit-style: uploads skills/, attaches to specialists
├── create_coordinator.py      # kit-style: creates Director -> .coordinator_id
├── setup_environment.py       # kit-style: cloud environment -> .environment_id
├── skills/                    # fact-grounding, recipient-personas, excuse-playbook, believability-rubric
├── data/calendar.json         # seed calendar
├── scripts/                   # smoke.py, seed_demo.py
├── tests/
└── docs/
```

Provisioning order (once per workspace): `setup_environment.py`, `create_specialists.py`, `upload_skills.py`, `create_coordinator.py`. The ID files (`.environment_id`, `.specialist_ids.json`, `.skill_ids.json`, `.coordinator_id`) are gitignored.

## 6. Result contract

The Director's last message is exactly one JSON object:

```json
{"rounds": [{"excuse": "...", "believability": 4, "holes": ["..."], "verdict": "revise"},
            {"excuse": "...", "believability": 8, "holes": [], "verdict": "accept"}]}
```

`verdict` is `accept` (Critic score 7 or more) or `revise`. At most 3 rounds. If the Director returns prose instead, the app falls back to showing it as a single unscored round.

## 7. Demo script (3 minutes)

1. Level 1 for "team lunch". Watch five threads spawn, the Critic accepts round one.
2. Level 3 for "Friday 3pm review with my manager". Narrate the live fan-out, open the rounds: Critic rejects round one, the Storyteller fixes the holes, round two passes.
3. "Mark as used", ask again for the same manager. The Historian's list now bans the saved excuse.
4. Level 4: pre-emptive plan for next week's calendar.

## 8. Risks and cuts

| Risk | Mitigation |
|---|---|
| Managed Agents is a research preview; workspace may lack access | Check access in the first 10 minutes (smoke script). Fallback: the old single-agent loop is described in git history |
| Claude 5 model IDs rejected in Managed Agents | Swap the three model constants for the kit's IDs |
| Director returns prose instead of JSON | `parse_result` fallback, pinned by a test |
| Session never goes idle | `run_swarm` has a `max_seconds` deadline |
| Weather unreachable on venue wifi | Fact Scout is told to say "weather unavailable" and continue |
| Team runs out of time | Cut level 4, then the Profiler. Fact Scout, Storyteller, Critic and memory are the core |

## 9. Stretch (from the kit's stretch goals)

- S3 Memory across deals: Memory tool so the Director learns which excuses landed.
- S9 Voting: three Critics (conservative, balanced, aggressive) and the Director takes the lowest score.
- S6 Notification: a specialist that posts progress to Slack.
- Always-on: a scheduled run that pre-drafts excuses for next week's calendar and queues them for approval.
