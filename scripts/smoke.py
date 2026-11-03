"""Check the API key works and the workspace has Managed Agents access."""
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic(default_headers={"anthropic-beta": "managed-agents-2026-04-01"})

reply = client.messages.create(
    model="claude-haiku-5-5", max_tokens=256,
    messages=[{"role": "user", "content": "Say hello in five words."}],
)
print(next(b.text for b in reply.content if b.type == "text"))

try:
    client.beta.environments.list()
    print("managed agents access: ok")
except Exception as e:
    print(f"managed agents access: NOT AVAILABLE ({e})")
