"""
Create the cloud Environment that the Excuse Desk sessions run in.

Safe to run multiple times: if `.environment_id` already exists, it is reused.

Usage:
    python setup_environment.py
"""

import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    env_path = Path(".environment_id")
    if env_path.exists():
        print(f"Environment already exists: {env_path.read_text().strip()}")
        print("(remove .environment_id if you want to provision a new one)")
        return

    client = Anthropic(default_headers={"anthropic-beta": "managed-agents-2026-04-01"})
    environment = client.beta.environments.create(
        name="excuse-swarm-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    env_path.write_text(environment.id)
    print(f"Environment created: {environment.id}")


if __name__ == "__main__":
    main()
