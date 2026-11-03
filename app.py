import streamlit as st

from context import LEVELS
from memory import save_excuse
from swarm_client import run_swarm

st.set_page_config(page_title="Excuse Swarm", page_icon="🐝", layout="centered")

st.markdown(
    """
    <style>
    .block-container { max-width: 760px; padding-top: 2.5rem; }
    .hero h1 { font-size: 2.6rem; margin-bottom: 0; letter-spacing: -0.02em; }
    .hero p { color: #6b7280; font-size: 1.05rem; margin-top: .25rem; }
    .pill { display:inline-block; padding: 2px 10px; border-radius: 999px;
            font-size: .78rem; font-weight: 600; margin-left: .5rem; }
    .pill.accept { background:#dcfce7; color:#166534; }
    .pill.revise { background:#fef3c7; color:#92400e; }
    .final-card { border: 1px solid rgba(124,58,237,.35); border-radius: 14px;
                  padding: 1rem 1.2rem .4rem; margin-top: 1.2rem;
                  background: linear-gradient(135deg, rgba(124,58,237,.08), rgba(236,72,153,.06)); }
    .final-card h3 { margin: 0 0 .5rem; }
    div.stButton > button[kind="primary"] { width: 100%; font-weight: 600; }
    .loader { display:flex; flex-direction:column; align-items:center; gap:.9rem;
              padding: 2rem 1rem; margin-top: 1rem; border-radius: 14px;
              border: 1px solid rgba(124,58,237,.25);
              background: linear-gradient(135deg, rgba(124,58,237,.07), rgba(236,72,153,.05)); }
    .loader .orbit { position:relative; width:64px; height:64px; }
    .loader .orbit span { position:absolute; inset:0; border-radius:50%;
              border: 3px solid transparent; border-top-color:#7c3aed;
              animation: spin 1.1s linear infinite; }
    .loader .orbit span:nth-child(2) { inset:9px; border-top-color:#ec4899;
              animation-duration: .8s; animation-direction: reverse; }
    .loader .orbit span:nth-child(3) { inset:18px; border-top-color:#f59e0b;
              animation-duration: 1.5s; }
    .loader .orbit b { position:absolute; inset:0; display:flex; align-items:center;
              justify-content:center; font-size:1.2rem; animation: pulse 1.4s ease-in-out infinite; }
    .loader .msg { font-weight:600; }
    .loader .sub { color:#6b7280; font-size:.85rem; margin-top:-.6rem; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes pulse { 0%,100% { transform: scale(.85); opacity:.7; } 50% { transform: scale(1.1); opacity:1; } }
    </style>
    <div class="hero">
      <h1>🐝 Excuse Swarm</h1>
      <p>A team of AI specialists scouts the facts, checks your history, and
      stress-tests the story, so your excuse actually holds up.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

EXAMPLES = [
    ("Friday 3pm review", "my manager"),
    ("Mandatory fun: trust falls", "my team lead"),
    ("Sunday lunch at the in-laws", "my partner"),
]


def _use_example(req: str, who: str) -> None:
    st.session_state["request_in"] = req
    st.session_state["recipient_in"] = who


st.caption("Try an example")
cols = st.columns(len(EXAMPLES))
for col, (req, who) in zip(cols, EXAMPLES):
    col.button(req, key=f"ex_{req}", on_click=_use_example, args=(req, who), use_container_width=True)

with st.container(border=True):
    request = st.text_input(
        "What do you need to get out of?",
        key="request_in",
        placeholder="e.g. Friday 3pm review",
    )
    recipient = st.text_input(
        "Who are you telling?",
        key="recipient_in",
        placeholder="e.g. my manager",
    )
    city = st.text_input("City (for weather)", value="London")
    level = st.slider("Escalation level", 1, 4, 2)
    st.caption(LEVELS[level])
    generate = st.button("Generate", type="primary")


def _describe(event: dict) -> str:
    agent = event.get("agent", "")
    kind = event.get("kind", "")
    if kind == "thread_created":
        return f"🟢 {agent} joined"
    if kind == "thread_running":
        return f"⚙️ {agent} is working"
    if kind == "delegate":
        return f"📨 Director → {agent}"
    if kind == "reply":
        return f"💬 {agent} replied"
    if kind == "tool":
        return f"🔧 {agent} used a tool"
    return f"{agent}: message" if agent else "message"


if generate:
    if not request.strip() or not recipient.strip():
        st.warning("Fill in both fields.")
    else:
        loader = st.empty()

        def show_loader(msg: str) -> None:
            loader.markdown(
                '<div class="loader"><div class="orbit"><span></span><span></span>'
                f'<span></span><b>🐝</b></div><div class="msg">{msg}</div>'
                '<div class="sub">Usually 30 to 90 seconds</div></div>',
                unsafe_allow_html=True,
            )

        try:
            show_loader("Crafting your excuse…")

            def cb(event: dict) -> None:
                show_loader(_describe(event))

            result = run_swarm(request, recipient, level, city=city, on_event=cb)
            loader.empty()
            st.session_state["result"] = result
            st.session_state["recipient"] = recipient
            st.session_state["level"] = level
            st.session_state.pop("saved", None)
        except Exception as e:
            loader.empty()
            st.session_state.pop("result", None)
            st.error(str(e))

result = st.session_state.get("result")
if result is not None:
    last = len(result.rounds)
    st.subheader("How it went")
    for i, r in enumerate(result.rounds, start=1):
        with st.expander(f"Round {i}: believability {r.believability}/10", expanded=(i == last)):
            st.markdown(
                f'<span class="pill {r.verdict}">{r.verdict.upper()}</span>',
                unsafe_allow_html=True,
            )
            st.progress(max(0, min(r.believability, 10)) / 10)
            st.write(r.excuse)
            if r.holes:
                st.caption("Critic found: " + "; ".join(r.holes))

    final = result.rounds[-1]
    st.markdown(
        f'<div class="final-card"><h3>✨ Your excuse '
        f'<span class="pill {final.verdict}">{final.believability}/10</span></h3></div>',
        unsafe_allow_html=True,
    )
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

st.divider()
st.caption("Nothing is ever sent to anyone. Excuses are only saved locally when you mark them as used.")
