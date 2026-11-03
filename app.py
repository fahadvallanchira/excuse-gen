import streamlit as st

from context import LEVELS
from memory import save_excuse
from swarm_client import run_swarm

st.title("Excuse Swarm")

request = st.text_input("What do you need to get out of?")
recipient = st.text_input("Who are you telling?")
city = st.text_input("City (for weather)", value="London")
level = st.slider("Escalation level", 1, 4, 2)
st.caption(LEVELS[level])


def _describe(event: dict) -> str:
    agent = event.get("agent", "")
    kind = event.get("kind", "")
    if kind == "thread_created":
        return f"{agent} joined"
    if kind == "thread_running":
        return f"{agent} is working"
    if kind == "delegate":
        return f"Director → {agent}"
    if kind == "reply":
        return f"{agent} replied"
    if kind == "tool":
        return f"{agent} used a tool"
    return f"{agent}: message" if agent else "message"


if st.button("Generate"):
    if not request.strip() or not recipient.strip():
        st.warning("Fill in both fields.")
    else:
        try:
            with st.status("Briefing the swarm...", expanded=True) as status:

                def cb(event: dict) -> None:
                    status.write(_describe(event))

                result = run_swarm(request, recipient, level, city=city, on_event=cb)
                status.update(label="Done", state="complete")
            st.session_state["result"] = result
            st.session_state["recipient"] = recipient
            st.session_state["level"] = level
            st.session_state.pop("saved", None)
        except Exception as e:
            st.session_state.pop("result", None)
            st.error(str(e))

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
