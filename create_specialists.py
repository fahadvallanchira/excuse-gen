"""Create the five specialist sub-agents for the Excuse Swarm.

Run once per workspace. Saves agent IDs to .specialist_ids.json so
create_coordinator.py can build the coordinator's roster.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python create_specialists.py
"""

import json
import os
from pathlib import Path

from specialists import SPECIALISTS, build_agent_params

IDS_PATH = Path(".specialist_ids.json")


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    from anthropic import Anthropic

    client = Anthropic(default_headers={"anthropic-beta": "managed-agents-2026-04-01"})

    ids: dict[str, str] = {}
    for spec in SPECIALISTS:
        agent = client.beta.agents.create(**build_agent_params(spec))
        ids[spec["key"]] = agent.id
        print(f"  Created {spec['name']:20s} -> {agent.id}")

    IDS_PATH.write_text(json.dumps(ids, indent=2))
    print(f"\nSaved {len(ids)} specialist IDs to {IDS_PATH}")
    print("Next: python upload_skills.py")


if __name__ == "__main__":
    main()
