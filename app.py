import streamlit as st

from activity import AGENTS, ActivityTracker, parse_critic
from context import LEVELS, random_reason
from memory import save_excuse
from swarm_client import run_swarm

st.title("Excuse Swarm")

request = st.text_input("What do you need to get out of?")
recipient = st.text_input("Who are you telling?")
level = st.slider("Escalation level", 1, 4, 2)
st.caption(LEVELS[level])


STATUS_COLOR = {"waiting": "gray", "working": "orange", "done": "green"}


def _time_suffix(tracker: ActivityTracker, name: str) -> str:
    secs = tracker.elapsed(name)
    return f" · {secs}s" if secs is not None else ""


def render_live(tracker: ActivityTracker, cards_box, log_box) -> None:
    """Redraw the five agent cards and the latest timeline lines while the swarm runs."""
    with cards_box.container():
        for col, name in zip(st.columns(len(AGENTS)), AGENTS):
            with col:
                st.markdown(f"**{name}**")
                status = tracker.agents[name].status
                st.markdown(f":{STATUS_COLOR[status]}[{status}]{_time_suffix(tracker, name)}")
    lines = [f"`{e['t']:>5.1f}s` {e['text']}" for e in tracker.timeline[-8:]]
    log_box.markdown("\n\n".join(lines) if lines else "Waiting for the swarm...")


def render_activity(tracker: ActivityTracker) -> None:
    """After the run: what each agent was asked, which tools it used, and what it answered."""
    st.subheader("What each agent did")
    for name in AGENTS:
        agent = tracker.agents[name]
        with st.expander(f"{name} · {agent.status}{_time_suffix(tracker, name)}"):
            if not agent.exchanges:
                st.caption("Not called in this run.")
            for n, ex in enumerate(agent.exchanges, start=1):
                if len(agent.exchanges) > 1:
                    st.markdown(f"**Round {n}**")
                if ex.brief:
                    st.markdown("**Brief from the Director**")
                    st.text(ex.brief)
                for tool in ex.tools:
                    st.caption(f"Tool: {tool}")
                if ex.reply:
                    st.markdown("**Reply**")
                    critic = parse_critic(ex.reply) if name == "Critic" else None
                    if critic:
                        score = f"{critic['score']}/10" if critic["score"] is not None else "no score"
                        st.markdown(f"Verdict: {critic['verdict']} · Score {score}")
                        for hole in critic["holes"]:
                            st.markdown(f"- {hole}")
                    else:
                        st.text(ex.reply)
    with st.expander("Full timeline"):
        for e in tracker.timeline:
            st.caption(f"{e['t']:.1f}s  {e['text']}")


if st.button("Generate"):
    if not request.strip() or not recipient.strip():
        st.warning("Fill in both fields.")
    else:
        reason = random_reason()
        st.caption(f"Reason theme: {reason}")
        tracker = ActivityTracker()
        st.session_state.pop("activity", None)
        try:
            with st.status("Briefing the swarm...", expanded=True) as status:
                cards_box = st.empty()
                log_box = st.empty()
                render_live(tracker, cards_box, log_box)

                def cb(event: dict) -> None:
                    tracker.handle(event)
                    render_live(tracker, cards_box, log_box)

                result = run_swarm(request, recipient, level, reason=reason, on_event=cb)
                status.update(label="Done", state="complete")
            st.session_state["result"] = result
            st.session_state["recipient"] = recipient
            st.session_state["level"] = level
            st.session_state.pop("saved", None)
        except Exception as e:
            st.session_state.pop("result", None)
            st.error(str(e))
        finally:
            st.session_state["activity"] = tracker

result = st.session_state.get("result")
if result is not None:
    last = len(result.rounds)
    for i, r in enumerate(result.rounds, start=1):
        with st.expander(f"Round {i}: believability {r.believability}/10", expanded=(i == last)):
            st.write(r.excuse)
            if r.holes:
                st.caption("Critic found: " + "; ".join(r.holes))

    st.code(result.final_excuse, language=None)

    if st.button("Mark as used"):
        save_excuse(
            st.session_state["recipient"],
            result.final_excuse,
            st.session_state["level"],
        )
        st.session_state["saved"] = True

    if st.session_state.get("saved"):
        st.success("Saved. This one will never be used on them again.")

activity = st.session_state.get("activity")
if activity is not None and activity.timeline:
    render_activity(activity)
