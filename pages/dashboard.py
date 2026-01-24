import streamlit as st

st.set_page_config(page_title="Dashboard • Prime Ivy", layout="wide")

# --------- AUTH GUARD ----------
# If user isn't authenticated, send them back to the login app
if not st.session_state.get("authenticated", False):
    st.warning("Please log in to continue.")
    st.switch_page("SAT app.py")

user = st.session_state.get("user_name", "student")

# --------- BASIC STYLING ----------
st.markdown(
    """
    <style>
    .block-container { padding-top: 0.8rem !important; }
    .card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.06);
        height: 100%;
    }
    .card h3 { margin: 0 0 6px 0; }
    .muted { color: #6b7280; margin-top: 0px; }
    .pill {
        display: inline-block;
        font-size: 12px;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid #e5e7eb;
        background: #f9fafb;
        margin-right: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------- HEADER ----------
c1, c2 = st.columns([3, 1])
with c1:
    st.title("Prime Ivy Portal")
    st.caption(f"Welcome, **{user}**")

with c2:
    st.write("")  # spacer
    if st.button("Log out", use_container_width=True):
        # Clear auth + any exam selection
        st.session_state.authenticated = False
        st.session_state.user_name = ""
        st.session_state.pop("selected_exam", None)
        st.session_state.pop("selected_exam_title", None)
        st.switch_page("SAT app.py")

st.divider()

# --------- EXAM LIST ----------
# You can add more exams later. The "id" is what exam.py will use.
EXAMS = [
    {
        "id": "sat_mock_v1",
        "title": "SAT Mock Exam (Full)",
        "desc": "Timed modules with break, review grid, and navigation popover.",
        "tags": ["Math + Reading", "Timed", "Break"],
    },
    # Example future option:
    # {
    #     "id": "sat_math_only",
    #     "title": "SAT Math Only",
    #     "desc": "Practice Math modules only (timed).",
    #     "tags": ["Math", "Timed"],
    # },
]

st.subheader("Choose a Mock Exam")

cols = st.columns(2)
for idx, exam in enumerate(EXAMS):
    with cols[idx % 2]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"### {exam['title']}")
        st.markdown(f"<p class='muted'>{exam['desc']}</p>", unsafe_allow_html=True)

        tags_html = "".join([f"<span class='pill'>{t}</span>" for t in exam.get("tags", [])])
        if tags_html:
            st.markdown(tags_html, unsafe_allow_html=True)

        st.write("")  # spacer

        if st.button("Start Exam", key=f"start_{exam['id']}", use_container_width=True):
            # Store selection for exam.py to use
            st.session_state.selected_exam = exam["id"]
            st.session_state.selected_exam_title = exam["title"]

            # OPTIONAL: reset test state when starting a new exam
            # (prevents student from resuming an old run unintentionally)
            for k in [
                "module_step", "on_break", "break_end", "viewing_review",
                "finished_all", "q_index", "flags", "responses", "answers",
                "end_time",
            ]:
                st.session_state.pop(k, None)

            st.switch_page("pages/exam.py")

        st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# --------- OPTIONAL: QUICK LINKS ----------
with st.expander("Troubleshooting"):
    st.write(
        """
- If the exam page says no exam is selected, return here and click **Start Exam** again.
- If you want “Resume Exam” behavior, we can store an active attempt flag and show a Resume button.
"""
    )