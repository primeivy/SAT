import time
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection


# ---------------------------
# GUARDS (auth + selection)
# ---------------------------
st.set_page_config(page_title="Exam • Prime Ivy", layout="wide")

if not st.session_state.get("authenticated", False):
    st.warning("Please log in to continue.")
    st.switch_page("SAT app.py")

if "selected_exam" not in st.session_state:
    st.warning("Please choose an exam first.")
    st.switch_page("pages/dashboard.py")


# ---------------------------
# CONFIG
# ---------------------------
URL = "https://docs.google.com/spreadsheets/d/1XLiSWYDUagXCsNbLKs_HE-BsaQzgFMw-M8FMU500f0M/edit?usp=sharing"

EXAM_CONFIG = {
    "sat_mock_v1": {
        "sheet_url": URL,
    }
}
exam_id = st.session_state.selected_exam
exam_title = st.session_state.get("selected_exam_title", "SAT Mock Exam")


# ---------------------------
# HELPERS
# ---------------------------
def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def normalize_image_url(url: str | None) -> str | None:
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url:
        return None

    # Google Drive file link -> direct view link
    if "drive.google.com/file/d/" in url:
        file_id = url.split("/file/d/")[1].split("/")[0]
        return f"https://drive.google.com/uc?export=view&id={file_id}"

    # GitHub blob -> raw
    if "github.com/" in url and "/blob/" in url:
        parts = url.split("github.com/")[1].split("/blob/")
        if len(parts) == 2:
            repo_part = parts[0]
            path_part = parts[1]
            return f"https://raw.githubusercontent.com/{repo_part}/{path_part}".replace("?raw=true", "")

    return url


def get_image_url(row, col="Image_URL") -> str | None:
    raw = row.get(col)
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if s == "" or s.lower() in ("nan", "none", "null", "0", "false"):
        return None
    return normalize_image_url(s)


def stop_question_timer():
    """Finalize time for the currently open question (if any)."""
    key = st.session_state.get("current_question_key")
    started = st.session_state.get("current_question_started_at")

    if key is None or started is None:
        return

    elapsed = max(0.0, time.time() - float(started))
    st.session_state.question_times[key] = st.session_state.question_times.get(key, 0.0) + elapsed

    st.session_state.current_question_key = None
    st.session_state.current_question_started_at = None


def start_question_timer(module_step: int, q_index: int):
    """Start timing for a question (safe: stops any previous timer first)."""
    stop_question_timer()
    st.session_state.current_question_key = (module_step, q_index)
    st.session_state.current_question_started_at = time.time()


def finalize_active_timer_safeguard():
    """Tiny safeguard: if a timer is running, stop it before leaving the page."""
    if st.session_state.get("current_question_key") is not None:
        stop_question_timer()


def get_question_type(row) -> str:
    qt = row.get("Question_Type", "MCQ")
    qt = str(qt).strip().upper() if qt is not None else "MCQ"
    return qt if qt in ("MCQ", "SPR") else "MCQ"


def set_module_timer(module_step: int):
    module_times = {1: 32, 2: 32, 3: 35, 4: 35}
    st.session_state.end_time = time.time() + (module_times[module_step] * 60)


@st.cache_data(ttl=60)
def load_data(sheet_url: str):
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(spreadsheet=sheet_url)


# ---------------------------
# TIME TRACKING (PER QUESTION)
# ---------------------------
def init_timing():
    if "question_times" not in st.session_state:
        st.session_state.question_times = {}  # {(module, q_index): seconds}
    if "current_question_key" not in st.session_state:
        st.session_state.current_question_key = None
    if "current_question_started_at" not in st.session_state:
        st.session_state.current_question_started_at = None


def stop_question_timer():
    key = st.session_state.get("current_question_key")
    started_at = st.session_state.get("current_question_started_at")
    if key is None or started_at is None:
        return

    elapsed = time.time() - started_at
    st.session_state.question_times[key] = st.session_state.question_times.get(key, 0.0) + elapsed

    st.session_state.current_question_key = None
    st.session_state.current_question_started_at = None


def start_question_timer(module: int, q_index: int):
    key = (module, q_index)

    # already timing this question
    if st.session_state.current_question_key == key and st.session_state.current_question_started_at is not None:
        return

    stop_question_timer()
    st.session_state.current_question_key = key
    st.session_state.current_question_started_at = time.time()


# ---------------------------
# CSS
# ---------------------------
st.markdown(
    """
<style>
.block-container { padding-top: 0.25rem !important; padding-bottom: 0rem !important; }
header { visibility: hidden; }
hr { margin-top: 1px !important; margin-bottom: 1px !important; opacity: 0.4; }
.passage-box {
    white-space: pre-wrap;
    background-color: #ffffff;
    padding: 20px;
    border-radius: 10px;
    border: 1px solid #e5e7eb;
    height: calc(100vh - 260px);
    max-height: 520px;
    overflow-y: auto;
    font-family: 'Georgia', serif;
    line-height: 1.65;
    color: #111827;
}
.sat-image {
    max-height: 350px;
    overflow: hidden;
    display: flex;
    justify-content: center;
    margin-bottom: 10px;
}
.sat-image img { max-height: 350px; width: auto; }
div[data-testid="stAppViewContainer"] div.stButton > button:not(div[data-testid="stPopoverBody"] button) {
    background-color: #6D28D9 !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 700 !important;
}
div[data-testid="stPopoverBody"] {
    width: 520px !important;
    padding: 0px !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
.pop-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px 16px 14px 16px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.12);
}
.pop-header {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    margin-bottom: 10px;
}
.pop-header .title {
    grid-column: 2;
    font-weight: 800;
    font-size: 18px;
    color: #111827;
    text-align: center;
}
.pop-header .fake-x {
    grid-column: 3;
    justify-self: end;
    font-size: 18px;
    color: #6b7280;
    line-height: 1;
    user-select: none;
}
.pop-divider { height: 1px; background: #e5e7eb; margin: 8px 0 12px 0; }
.legend {
    display: flex;
    gap: 18px;
    align-items: center;
    justify-content: center;
    margin-bottom: 12px;
    color: #374151;
    font-size: 13px;
    font-weight: 600;
}
.pop-grid-wrap { display:flex; justify-content:center; padding: 10px 0; }
.pop-grid-inner { width: 350px; max-width: 100%; margin: 0 auto; }
.pop-grid-inner div.stButton > button {
    background: #ffffff !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
    font-size: 10px !important;
    width: 32px !important;
    height: 32px !important;
    padding: 0px !important;
    margin: 0px !important;
    border: 1.5px dotted #9ca3af !important;
    color: #1d4ed8 !important;
}
div[data-testid="stPopoverBody"] [data-testid="column"] {
    padding-left: 1px !important;
    padding-right: 1px !important;
}
div[data-testid="stPopoverBody"] button[aria-label^="📍"] {
    border: 2.5px solid #111827 !important;
    color: #111827 !important;
}
div[data-testid="stPopoverBody"] button[aria-label^="🚩"] {
    background: #ef4444 !important;
    border: 2px solid #ef4444 !important;
    color: #ffffff !important;
}
.answered-outline div.stButton > button { border: 2px solid #2563eb !important; }
.pop-footer { display:flex; justify-content:center; width:100%; padding-top: 12px; }
.pop-footer .footer-wrap { width:100%; max-width: 300px; margin: 0 auto; }
.pop-footer .footer-wrap div.stButton > button {
    width: 100% !important;
    height: 42px !important;
    border-radius: 999px !important;
    background: #ffffff !important;
    border: 2px solid #2563eb !important;
    color: #2563eb !important;
    font-weight: 800 !important;
    font-size: 14px !important;
}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------
# LOAD QUESTIONS
# ---------------------------
sheet_url = EXAM_CONFIG.get(exam_id, {}).get("sheet_url", URL)
full_df = load_data(sheet_url)

module_mapping = {
    1: "Session 1 Module 1",
    2: "Session 1 Module 2",
    3: "Session 2 Module 1",
    4: "Session 2 Module 2",
}


# ---------------------------
# SESSION STATE (exam engine)
# ---------------------------
if "module_step" not in st.session_state:
    st.session_state.module_step = 1
if "on_break" not in st.session_state:
    st.session_state.on_break = False
if "break_end" not in st.session_state:
    st.session_state.break_end = None
if "viewing_review" not in st.session_state:
    st.session_state.viewing_review = False
if "finished_all" not in st.session_state:
    st.session_state.finished_all = False
if "q_index" not in st.session_state:
    st.session_state.q_index = 0
if "flags" not in st.session_state:
    st.session_state.flags = {}
if "responses" not in st.session_state:
    st.session_state.responses = {}
if "end_time" not in st.session_state:
    set_module_timer(st.session_state.module_step)

# init timing AFTER engine state is ready
init_timing()


# ---------------------------
# TOP BAR: back + exam title
# ---------------------------
top_l, top_r = st.columns([1, 1])

with top_l:
    if st.button("← Back to Dashboard"):
        finalize_active_timer_safeguard()
        st.switch_page("pages/dashboard.py")

with top_r:
    st.caption(f"Exam: **{exam_title}**")

st.divider()


# ---------------------------
# FINISH PAGE
# ---------------------------
if st.session_state.finished_all:
    stop_question_timer()
    st.success("Test completed!")
    if st.button("Go to Score Page", use_container_width=True):
        st.switch_page("pages/score.py")
    st.stop()


# ---------------------------
# BREAK PAGE (after module 2)
# ---------------------------
if st.session_state.on_break:
    stop_question_timer()

    st.markdown(
        '<style>div[data-testid="stAppViewContainer"]{background-color:#1a1a1a !important; color:white !important;}</style>',
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.write("## ")

        @st.fragment(run_every=1.0)
        def break_timer():
            rem = int((st.session_state.break_end or time.time()) - time.time())
            mins, secs = divmod(max(0, rem), 60)
            st.markdown(
                f"""
                <div style="border-radius: 15px; padding: 30px; text-align:center; border:1px solid #333; background: rgba(255,255,255,0.05);">
                    <p style="font-size:18px; color:white; margin:0;">Remaining Break Time</p>
                    <h1 style="font-size:72px; margin:0; color:white;">{mins:02d}:{secs:02d}</h1>
                </div>
                """,
                unsafe_allow_html=True,
            )

        break_timer()

        if st.button("Resume Testing Now", use_container_width=True):
            finalize_active_timer_safeguard()   # 🔐 finalize timing before state change

            st.session_state.on_break = False
            st.session_state.module_step = 3
            st.session_state.q_index = 0
            st.session_state.viewing_review = False
            set_module_timer(3)
            st.rerun()

    with col_right:
        st.markdown(
            """
            <div style="color:white; padding-top:30px;">
              <h1 style="font-size:34px; color:white;">Practice Test Break</h1>
              <hr style="border:0.5px solid #444;">
              <h3 style="color:white;">Take a Break: Do Not Close Your Device</h3>
              <ol>
                <li>Do not disturb students who are still testing.</li>
                <li>Do not exit the app or close your laptop.</li>
                <li>Do not access electronic devices.</li>
              </ol>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.stop()


# ---------------------------
# FILTER CURRENT MODULE
# ---------------------------
module = st.session_state.module_step
current_label = module_mapping[module]
df = full_df[full_df["Session"] == current_label].reset_index(drop=True)


# ---------------------------
# HEADER TIMER
# ---------------------------
@st.fragment(run_every=1.0)
def test_header():
    rem = int(st.session_state.end_time - time.time())
    mins, secs = divmod(max(0, rem), 60)

    if rem <= 0 and not st.session_state.viewing_review:
        stop_question_timer()
        st.session_state.viewing_review = True
        st.rerun()

    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    with c1:
        st.write(f"**{current_label}**")
    with c2:
        st.markdown(
            f"<div style='text-align:center; font-variant-numeric: tabular-nums;'>"
            f"<span style='font-size:22px; font-weight:800;'>⏱️ {mins:02d}:{secs:02d}</span></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.write("")

test_header()
st.divider()


# ---------------------------
# REVIEW PAGE
# ---------------------------
if st.session_state.viewing_review:
    stop_question_timer()

    st.subheader(f"Review: {current_label}")

    grid = st.columns(6)
    for i in range(len(df)):
        with grid[i % 6]:
            is_flg = st.session_state.flags.get(module, {}).get(i, False)
            resp = st.session_state.responses.get((module, i))
            is_ans = resp is not None and str(resp.get("value", "")).strip() != ""

            if is_flg and is_ans:
                label = f"🚩 Q{i+1} ▣"
            elif is_flg:
                label = f"🚩 Q{i+1}"
            elif is_ans:
                label = f"Q{i+1} ▣"
            else:
                label = f"Q{i+1} ▢"

            if st.button(label, key=f"rev_{module}_{i}", use_container_width=True):
                stop_question_timer()
                st.session_state.q_index = i
                st.session_state.viewing_review = False
                st.rerun()

    st.divider()

    if st.button("Submit Module", type="primary", use_container_width=True):
        finalize_active_timer_safeguard()

        if module == 2:
            st.session_state.on_break = True
            st.session_state.break_end = time.time() + (10 * 60)
            st.rerun()
        elif module < 4:
            st.session_state.module_step += 1
            st.session_state.q_index = 0
            st.session_state.viewing_review = False
            set_module_timer(st.session_state.module_step)
            st.rerun()
        else:
            st.session_state.finished_all = True
            st.session_state.viewing_review = False
            st.session_state.on_break = False
            st.session_state.exam_finished_at = time.time()
            st.switch_page("pages/score.py")


# ---------------------------
# QUESTION PAGE
# ---------------------------
else:
    # start timing for current question (only in question view)
    start_question_timer(module, st.session_state.q_index)

    q_data = df.iloc[st.session_state.q_index]
    l, r = st.columns([1, 1], gap="large")

    with l:
        has_table = False

        if "Table_Data" in q_data and pd.notna(q_data.get("Table_Data")):
            try:
                rows = [rr.split(",") for rr in str(q_data["Table_Data"]).split(";")]
                table_html = "<table style='width:100%; border-collapse: collapse; margin-bottom: 10px;'>"
                table_html += "<tr>" + "".join(
                    f"<th style='border:1px solid #e5e7eb; padding:6px; background:#f9fafb;'>{c.strip()}</th>"
                    for c in rows[0]
                ) + "</tr>"
                for row in rows[1:]:
                    table_html += "<tr>" + "".join(
                        f"<td style='border:1px solid #e5e7eb; padding:6px;'>{c.strip()}</td>" for c in row
                    ) + "</tr>"
                table_html += "</table>"
                st.markdown(table_html, unsafe_allow_html=True)
                has_table = True
            except Exception:
                pass

        img_url = get_image_url(q_data, col="Image_URL")
        has_img = bool(img_url)
        if img_url:
            st.markdown(
                f"""
                <div class="sat-image">
                    <img src="{img_url}" />
                </div>
                """,
                unsafe_allow_html=True,
            )

        passage_height = 550
        if has_img:
            passage_height -= 200
        if has_table:
            passage_height -= 110
        passage_height = max(240, passage_height)

        clean_content = normalize_text(q_data.get("Content", ""))
        st.markdown(
            f'<div class="passage-box" style="height:{passage_height}px;">{clean_content}</div>',
            unsafe_allow_html=True,
        )

    with r:
        curr_flags = st.session_state.flags.setdefault(module, {})
        is_flagged = st.checkbox(
            "🚩 Mark for Review",
            value=curr_flags.get(st.session_state.q_index, False),
            key=f"flag_{module}_{st.session_state.q_index}",
        )
        curr_flags[st.session_state.q_index] = is_flagged

        st.markdown(f"### Question {st.session_state.q_index + 1}")
        st.write(f"*{q_data.get('Prompt','')}*")

        q_index = st.session_state.q_index
        resp_key = (module, q_index)

        qtype = get_question_type(q_data)
        saved = st.session_state.responses.get(resp_key, {})
        saved_val = saved.get("value")

        if qtype == "MCQ":
            letters = ["A", "B", "C", "D"]
            labels = [
                f"A) {q_data.get('Option_A','')}",
                f"B) {q_data.get('Option_B','')}",
                f"C) {q_data.get('Option_C','')}",
                f"D) {q_data.get('Option_D','')}",
            ]
            saved_index = letters.index(saved_val) if saved_val in letters else None

            selected_label = st.radio(
                "Answer:",
                labels,
                index=saved_index,
                key=f"radio_{module}_{q_index}",
                label_visibility="collapsed",
            )

            if selected_label is not None:
                selected_letter = selected_label.split(")")[0]
                st.session_state.responses[resp_key] = {"type": "MCQ", "value": selected_letter}
            else:
                st.session_state.responses.pop(resp_key, None)

        else:
            val = st.text_input(
                "Answer:",
                value="" if saved_val is None else str(saved_val),
                placeholder="Enter your answer",
                key=f"spr_{module}_{q_index}",
                label_visibility="collapsed",
            ).strip()

            if val != "":
                st.session_state.responses[resp_key] = {"type": "SPR", "value": val}
            else:
                st.session_state.responses.pop(resp_key, None)

        st.write("---")
        b1, b2 = st.columns(2)

        with b1:
            if st.session_state.q_index > 0 and st.button("⬅️ Back", use_container_width=True):
                stop_question_timer()
                st.session_state.q_index -= 1
                st.rerun()

        with b2:
            label = "Review Module ➡️" if st.session_state.q_index == len(df) - 1 else "Next ➡️"
            if st.button(label, use_container_width=True):
                stop_question_timer()
                if st.session_state.q_index == len(df) - 1:
                    st.session_state.viewing_review = True
                else:
                    st.session_state.q_index += 1
                st.rerun()


# ---------------------------
# FOOTER NAV POPOVER
# ---------------------------
st.write("---")
_, f_mid, _ = st.columns([1, 1.6, 1])
with f_mid:
    current_mod_flags = st.session_state.flags.get(module, {})
    flag_status = "🚩 " if current_mod_flags.get(st.session_state.q_index) else ""

    with st.popover(f"{flag_status}Question {st.session_state.q_index + 1} of {len(df)}", use_container_width=True):
        st.markdown(
            f"""
            <div class="pop-card">
              <div class="pop-header">
                <div></div>
                <div class="title">{current_label}</div>
                <div class="fake-x">✕</div>
              </div>

              <div class="pop-divider"></div>

              <div class="legend">
                <div class="legend-item"><span style="font-size: 14px;">📍</span> Current</div>
                <div class="legend-item"><span style="font-size: 14px;">🚩</span> For Review</div>
              </div>

              <div class="pop-divider"></div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="pop-grid-wrap"><div class="pop-grid-inner">', unsafe_allow_html=True)

        cols = st.columns(10, gap="small")
        for i in range(len(df)):
            with cols[i % 10]:
                is_curr = (i == st.session_state.q_index)
                is_flg = current_mod_flags.get(i, False)
                resp = st.session_state.responses.get((module, i))
                is_ans = resp is not None and str(resp.get("value", "")).strip() != ""

                if is_curr:
                    label = f"📍{i+1}"
                elif is_flg:
                    label = f"🚩{i+1}"
                else:
                    label = str(i + 1)

                add_answered_outline = (is_ans and (not is_curr) and (not is_flg))
                if add_answered_outline:
                    st.markdown('<div class="answered-outline">', unsafe_allow_html=True)

                if st.button(label, key=f"nav_{module}_{i}"):
                    stop_question_timer()
                    st.session_state.q_index = i
                    st.session_state.viewing_review = False
                    st.rerun()

                if add_answered_outline:
                    st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div></div>", unsafe_allow_html=True)

        st.markdown('<div class="pop-footer"><div class="footer-wrap">', unsafe_allow_html=True)
        if st.button("Go to Review Page", key="goto_rev", use_container_width=True):
            stop_question_timer()
            st.session_state.viewing_review = True
            st.rerun()
        st.markdown("</div></div></div>", unsafe_allow_html=True)