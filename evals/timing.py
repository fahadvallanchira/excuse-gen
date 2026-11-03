"""Run one real swarm request and print a timeline plus per-phase durations.

Usage (needs ANTHROPIC_API_KEY and provisioned agents):
    PYTHONPATH=. python evals/timing.py "Friday 3pm review" "my manager" 2
"""

import sys

from swarm_client import run_swarm


def main() -> None:
    request, recipient, level = sys.argv[1], sys.argv[2], int(sys.argv[3])
    events: list[dict] = []
    result = run_swarm(request, recipient, level, on_event=events.append)
    total = events[-1]["t"] if events else 0.0

    print(f"{'t(s)':>7}  {'kind':<15} agent")
    for e in events:
        if e["kind"] != "thread_running":
            print(f"{e['t']:7.1f}  {e['kind']:<15} {e['agent']}")

    first = {}
    last_reply = {}
    for e in events:
        if e["kind"] == "delegate":
            first.setdefault(e["agent"], e["t"])
        if e["kind"] == "reply":
            last_reply[e["agent"]] = e["t"]
    print("\nfirst delegation -> last reply, per agent")
    for agent, t0 in first.items():
        print(f"  {agent:<20} {t0:6.1f} -> {last_reply.get(agent, float('nan')):6.1f}")
    print(f"\nrounds: {len(result.rounds)}   total: {total:.1f}s")


if __name__ == "__main__":
    main()
