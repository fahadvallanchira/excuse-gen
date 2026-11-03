"""Upload each skill in skills/ and attach it to the matching specialist.

Reuses a skill that already exists with the same display title, and skips
attaching one that is already attached, so re-running is safe.

Usage:
    python upload_skills.py
"""

import json
import os
from pathlib import Path

from specialists import SKILL_TO_SPECIALIST

SPECIALIST_IDS_PATH = Path(".specialist_ids.json")
SKILL_IDS_PATH = Path(".skill_ids.json")


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")
    if not SPECIALIST_IDS_PATH.exists():
        raise SystemExit("Run create_specialists.py first.")

    from anthropic import Anthropic
    from anthropic.lib import files_from_dir

    specialist_ids = json.loads(SPECIALIST_IDS_PATH.read_text())
    client = Anthropic(default_headers={"anthropic-beta": "managed-agents-2026-04-01"})

    print("Checking for existing skills...")
    existing = {s.display_title: s.id for s in client.beta.skills.list(source="custom")}

    uploaded: dict[str, str] = {}
    for skill_name, specialist_key in SKILL_TO_SPECIALIST.items():
        skill_dir = Path("skills") / skill_name
        if not (skill_dir / "SKILL.md").exists():
            print(f"  Skipping {skill_name}: no SKILL.md found")
            continue

        title = skill_name.replace("-", " ").title()
        if title in existing:
            skill_id = existing[title]
            print(f"Reusing skill: {skill_name} ({skill_id})")
        else:
            print(f"Uploading skill: {skill_name}...")
            skill_id = client.beta.skills.create(
                display_title=title, files=files_from_dir(str(skill_dir))
            ).id
            print(f"  -> {skill_id}")
        uploaded[skill_name] = skill_id

        agent_id = specialist_ids[specialist_key]
        current = client.beta.agents.retrieve(agent_id)
        if any(s.get("skill_id") == skill_id for s in (current.skills or [])):
            print(f"  already attached to {specialist_key}")
            continue
        client.beta.agents.update(
            agent_id,
            version=current.version,
            skills=list(current.skills or [])
            + [{"type": "custom", "skill_id": skill_id, "version": "latest"}],
        )
        print(f"  attached to {specialist_key}")

    SKILL_IDS_PATH.write_text(json.dumps(uploaded, indent=2))
    print(f"\nUploaded and attached {len(uploaded)} skills.")


if __name__ == "__main__":
    main()
