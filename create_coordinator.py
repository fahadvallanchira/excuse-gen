"""
Create the Excuse Director (coordinator) agent.

Reads the specialist IDs written by create_specialists.py and saves the
coordinator's ID to .coordinator_id. Re-running creates a new coordinator and
overwrites .coordinator_id; if you re-ran create_specialists.py, re-run this too.

Usage:
    python create_coordinator.py
"""

import json
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from coordinator import build_coordinator_params


def main() -> None:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    ids_path = Path(".specialist_ids.json")
    if not ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(ids_path.read_text())

    try:
        params = build_coordinator_params(specialist_ids)
    except KeyError as e:
        raise SystemExit(f"{ids_path} is missing specialist {e}. Re-run create_specialists.py.")

    client = Anthropic(default_headers={"anthropic-beta": "managed-agents-2026-04-01"})
    coordinator = client.beta.agents.create(**params)

    Path(".coordinator_id").write_text(coordinator.id)
    print(f"Coordinator created: {coordinator.id}")
    print(f"Roster: {list(specialist_ids.keys())}")


if __name__ == "__main__":
    main()
