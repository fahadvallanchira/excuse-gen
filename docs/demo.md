# Demo notes

## Before you start

Provision once per workspace, in this order (the ID files are gitignored):

```bash
python scripts/smoke.py          # key works + "managed agents access: ok"
python setup_environment.py && python create_specialists.py && python upload_skills.py && python create_coordinator.py
python scripts/seed_demo.py      # resets memory: two past excuses for "my manager"
streamlit run app.py
```

## Demo script (3 minutes)

1. **Level 1** for "team lunch". Watch five threads spawn; the Critic accepts round one.
2. **Level 3** for "Friday 3pm review with my manager". Narrate the live fan-out, open the rounds: the Critic rejects round one, the Storyteller fixes the holes, round two passes.
3. Click **Mark as used**, then ask again for the same manager. The Historian's list now bans the saved excuse.
4. **Level 4**: pre-emptive plan for next week's calendar.

Each step should finish in under 90 seconds. If slower, lower the Director to a faster model or cap Critic rounds.

## Fallbacks

- **Weather outage / venue wifi:** the Fact Scout says "weather unavailable" and continues; nothing to do.
- **Model IDs rejected by Managed Agents:** swap the three model constants (`DIRECTOR`/Opus in `coordinator.py`, and the Sonnet and Haiku IDs in `specialists.py`) for IDs your workspace accepts, then re-run `create_specialists.py` and `create_coordinator.py`.
- **No Managed Agents access:** `scripts/smoke.py` prints `NOT AVAILABLE`; request access for the workspace key before the demo.
- **Session hangs:** `run_swarm` raises `TimeoutError` after 300 seconds; just retry.
