import streamlit as st
from streamlit_gsheets import GSheetsConnection
import time
import pandas as pd


# ---------- TEXT NORMALIZATION ----------
def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


# ---------- IMAGE URL NORMALIZATION ----------
def normalize_image_url(url: str | None) -> str | None:
    if not isinstance(url, str):
        return None

    url = url.strip()
    if not url:
        return None

    # Google Drive file link → direct view link
    if "drive.google.com/file/d/" in url:
        file_id = url.split("/file/d/")[1].split("/")[0]
        return f"https://drive.google.com/uc?export=view&id={file_id}"

    return url


# ---------- IMAGE URL EXTRACTION ----------
def get_image_url(row, col="Image_URL") -> str | None:
    raw = row.get(col)

    # None / NaN
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None

    s = str(raw).strip()

    # treat these as "no image"
    if s == "" or s.lower() in ("nan", "none", "null", "0", "false"):
        return None

    return normalize_image_url(s)

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Prime Ivy SAT Portal", layout="wide")

# --- 2. CSS (MAIN + POPOVER UI) ---
st.markdown(
    """
<style>
/* ---------- GLOBAL LAYOUT ---------- */
.block-container { padding-top: 0.25rem !important; padding-bottom: 0rem !important; }
header { visibility: hidden; }

/* ---------- HEADER TIGHTENING ---------- */
div[data-testid="column"] {
    padding-top: 0px !important;
    padding-bottom: 0px !important;
}

.stMarkdown p {
    line-height: 1.1 !important;
    margin-bottom: 0px !important;
}

/* ---------- SHRINK DIVIDER ---------- */
hr {
    margin-top: 1px !important;
    margin-bottom: 1px !important;
    opacity: 0.4;
}


/* Passage box (left) */
.passage-box {
    white-space: pre-wrap;
    background-color: #ffffff;
    padding: 20px;
    border-radius: 10px;
    border: 1px solid #e5e7eb;

    /* KEY CHANGE ↓ */
    height: calc(100vh - 260px);
    max-height: 520px;

    overflow-y: auto;
    font-family: 'Georgia', serif;
    line-height: 1.65;
    color: #111827;
}

/* Image wrapper (SAT-style) */
.sat-image {
    max-height: 350px;
    overflow: hidden;
    display: flex;
    justify-content: center;
    margin-bottom: 10px;
}

.sat-image img {
    max-height: 350px;
    width: auto;
}


/* Main buttons (NOT inside popover) */
div[data-testid="stAppViewContainer"] div.stButton > button:not(div[data-testid="stPopoverBody"] button) {
    background-color: #6D28D9 !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    font-weight: 700 !important;
}

/* ---------- POPOVER CONTAINER ---------- */
div[data-testid="stPopoverBody"] {
    width: 520px !important;
    padding: 0px !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* Inner card */
.pop-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px 16px 14px 16px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.12);
}

/* Header row */
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

/* Divider */
.pop-divider {
    height: 1px;
    background: #e5e7eb;
    margin: 8px 0 12px 0;
}

/* Legend row */
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
.legend-item {
    display: flex;
    gap: 8px;
    align-items: center;
    white-space: nowrap;
}
.legend-dot {
    width: 14px;
    height: 14px;
    border-radius: 4px;
    display: inline-block;
}
.legend-current { border: 2px solid #111827; background: #fff; }
.legend-unanswered { border: 2px dotted #9ca3af; background: #fff; }
.legend-review { background: #ef4444; border: 2px solid #ef4444; }

/* Tight spacing for columns inside popover */
div[data-testid="stPopoverBody"] [data-testid="column"] { padding: 0px !important; }

/* --- FIXED 10-COLUMN GRID USING REAL STREAMLIT COLUMNS --- */
.pop-grid-wrap {
    display: flex;
    justify-content: center;
    padding: 10px 0;
}
.pop-grid-inner {
    width: 350px;           /* 10*32 + 9*10 = 320 + 90 = 410; but we use Streamlit columns */
    max-width: 100%;
    margin: 0 auto;
}

/* Make ONLY the GRID buttons square (not the footer button) */
.pop-grid-inner div.stButton > button {
    background: #ffffff !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
    font-size: 10px !important;

    width: 32px !important;
    height: 32px !important;
    padding: 0px !important;
    margin: 0px !important;

    border: 1.5px dotted #9ca3af !important;   /* default: unanswered */
    color: #1d4ed8 !important;
}

/* Fix Streamlit column padding to pull boxes together */
div[data-testid="stPopoverBody"] [data-testid="column"] {
    padding-left: 1px !important;
    padding-right: 1px !important;
    flex: 0 1 auto !important; /* Prevents columns from growing too wide */
}

/* Ensure the pin/flag icon doesn't push the number down */
div[data-testid="stPopoverBody"] button div p {
    margin-bottom: 0px !important;
    line-height: 1 !important;
}

/* Remove extra padding around buttons to keep the 32px size exact */
div[data-testid="stPopoverBody"] div.stButton { 
    margin: 0px !important; 
    padding: 0px !important; 
}

/* Tighter vertical spacing between rows (Questions 1-10 vs 11-20) */
div[data-testid="stPopoverBody"] [data-testid="stVerticalBlock"] > div {
    gap: 6px !important; 
}

/* STATE styles driven by label prefix:
   - Current label starts with "📍"
   - Flag label starts with "🚩"
*/
div[data-testid="stPopoverBody"] button[aria-label^="📍"] {
    border: 2.5px solid #111827 !important;
    color: #111827 !important;
}
div[data-testid="stPopoverBody"] button[aria-label^="🚩"] {
    background: #ef4444 !important;
    border: 2px solid #ef4444 !important;
    color: #ffffff !important;
}

/* Answered (blue outline) is applied via an extra wrapper class on the column container */
.answered-outline div.stButton > button {
    border: 2px solid #2563eb !important;
}

/* Footer center button (FIXED: always centered) */
.pop-footer {
    display: flex;
    justify-content: center;
    width: 100%;
    padding-top: 12px;
}

.pop-footer .footer-wrap {
    width: 100%;
    max-width: 300px;          /* controls how wide the pill is */
    margin: 0 auto;
}

.pop-footer .footer-wrap > div {
    width: 100% !important;    /* stButton wrapper */
}

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

# --- 3. DATA LAYER ---
URL = "https://docs.google.com/spreadsheets/d/1XLiSWYDUagXCsNbLKs_HE-BsaQzgFMw-M8FMU500f0M/edit?usp=sharing"

@st.cache_data(ttl=60)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(spreadsheet=URL)

# --- QUESTION TYPE HELPER ---
def get_question_type(row) -> str:
    qt = row.get("Question_Type", "MCQ")
    qt = str(qt).strip().upper() if qt is not None else "MCQ"
    return qt if qt in ("MCQ", "SPR") else "MCQ"

def set_module_timer(module_step: int):
    module_times = {1: 32, 2: 32, 3: 35, 4: 35}
    st.session_state.end_time = time.time() + (module_times[module_step] * 60)

try:
    full_df = load_data()

    # --- 4. SESSION STATE INIT (ALL PAGES/FLOWS) ---
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
        st.session_state.flags = {}  # flags[module][q] = bool

    if "answers" not in st.session_state:
        st.session_state.answers = {}  # answers[(module, q)] = selected option string

    if "responses" not in st.session_state:
        st.session_state.responses = {}

    module_times = {1: 32, 2: 32, 3: 35, 4: 35}
    if "end_time" not in st.session_state:
        set_module_timer(st.session_state.module_step)

    module_mapping = {
        1: "Session 1 Module 1",
        2: "Session 1 Module 2",
        3: "Session 2 Module 1",
        4: "Session 2 Module 2",
    }

    # --- 5. COMPLETION PAGE ---
    if st.session_state.finished_all:
        st.markdown(
            '<style>div[data-testid="stAppViewContainer"]{background-color:#1e293b !important; color:white !important;}</style>',
            unsafe_allow_html=True,
        )
        st.balloons()
        _, center_col, _ = st.columns([1, 2, 1])
        with center_col:
            st.write("# ")
            st.markdown(
                """
                <div style="background-color: white; color: black; padding: 40px; border-radius: 15px; text-align: center; border: 1px solid #ddd;">
                    <h1 style="margin-bottom: 10px;">You're All Finished!</h1>
                    <div style="display: flex; align-items: center; justify-content: center; gap: 30px;">
                        <img src="https://cdn-icons-png.flaticon.com/512/3067/3067451.png" width="120">
                        <p style="font-size: 18px; text-align: left;">
                          Congratulations on completing your SAT practice test!<br/>
                          See your results on <b>ivyprime.org</b>.
                        </p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.write("## ")
            st.markdown('<div class="yellow-btn">', unsafe_allow_html=True)
            if st.button("View Your Score", use_container_width=True):
                st.switch_page("pages/score.py")
            st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # --- 6. BREAK PAGE (AFTER MODULE 2) ---
    if st.session_state.on_break:
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
                    <div class="timer-card">
                      <p style="font-size:20px; color:white;">Remaining Break Time:</p>
                      <h1 style="font-size:80px; margin:0; color:white;">{mins:02d}:{secs:02d}</h1>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            break_timer()

            st.markdown('<div class="resume-btn">', unsafe_allow_html=True)
            if st.button("Resume Testing Now", use_container_width=True):
                st.session_state.on_break = False
                st.session_state.module_step = 3
                st.session_state.q_index = 0
                st.session_state.viewing_review = False
                set_module_timer(3)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with col_right:
            st.markdown(
                """
                <div style="color:white; padding-top:50px;">
                  <h1 style="font-size:40px; color:white;">Practice Test Break</h1>
                  <hr style="border:0.5px solid #444;">
                  <h2 style="color:white;">Take a Break: Do Not Close Your Device</h2>
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

    # --- 7. FILTER CURRENT MODULE QUESTIONS ---
    module = st.session_state.module_step
    current_label = module_mapping[module]
    df = full_df[full_df["Session"] == current_label].reset_index(drop=True)

    # --- 8. HEADER (TIMER) ---
    @st.fragment(run_every=1.0)
    def test_header():
        # Safety Check: If end_time hasn't been set yet, exit the function
        if "end_time" not in st.session_state:
            return

        rem = int(st.session_state.end_time - time.time())
        mins, secs = divmod(max(0, rem), 60)

        # When module time ends -> force review page
        if rem <= 0 and not st.session_state.viewing_review:
            st.session_state.viewing_review = True
            st.rerun()

        c1, c2, c3 = st.columns([1.5, 1, 1.5])
        with c1:
            st.write(f"**{current_label}**")
        with c2:
            # Added tabular-nums to stop the clock from "jittering" or moving side to side
            st.markdown(
                f"<div style='text-align:center; font-variant-numeric: tabular-nums;'>"
                f"<span style='font-size:22px; font-weight:800;'>⏱️ {mins:02d}:{secs:02d}</span></div>",
                unsafe_allow_html=True,
            )
        with c3:
            # Streamlit buttons don't align right easily via div, so we use a sub-column trick
            _, btn_col = st.columns([1, 1])
            with btn_col:
                st.button("Directions", use_container_width=True)

    test_header()
    st.divider()

    # --- 9. REVIEW PAGE (PER MODULE) ---
    if st.session_state.viewing_review:
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
                    st.session_state.q_index = i
                    st.session_state.viewing_review = False
                    st.rerun()

        st.divider()

        if st.button("Submit Module", type="primary", use_container_width=True):
            # After module 2 -> 10 min break
            if module == 2:
                st.session_state.on_break = True
                st.session_state.break_end = time.time() + (10 * 60)
                st.rerun()

            # Advance to next module
            elif module < 4:
                st.session_state.module_step += 1
                st.session_state.q_index = 0
                st.session_state.viewing_review = False
                set_module_timer(st.session_state.module_step)
                st.rerun()

            # Finish all
            else:
                st.session_state.finished_all = True
                st.rerun()

    # --- 10. QUESTION PAGE ---
    else:
        q_data = df.iloc[st.session_state.q_index]
        l, r = st.columns([1, 1], gap="large")

        with l:
            has_table = False

            # --- 1) Optional: render table (if Table_Data exists) ---
            if "Table_Data" in q_data and pd.notna(q_data.get("Table_Data")):
                try:
                    rows = [rr.split(",") for rr in str(q_data["Table_Data"]).split(";")]
                    table_html = "<table class='sat-table'><tr>" + "".join(
                        f"<th>{c.strip()}</th>" for c in rows[0]
                    ) + "</tr>"
                    for row in rows[1:]:
                        table_html += "<tr>" + "".join(f"<td>{c.strip()}</td>" for c in row) + "</tr>"
                    table_html += "</table>"
                    st.markdown(table_html, unsafe_allow_html=True)
                    has_table = True
                except Exception:
                    pass

            # --- 2) Optional: render image (if Image_URL exists) ---
            img_url = get_image_url(q_data, col="Image_URL")
            has_img = bool(img_url)

            if img_url:
                st.markdown(
                    f"""
                    <div class="sat-image">
                        <img src="{img_url}" />
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # --- 3) Passage height adjustment ---
            # Base height when left side is empty except passage
            passage_height = 550

            # If we added elements above the passage, shrink it so footer stays visible
            if has_img:
                passage_height -= 200
            if has_table:
                passage_height -= 110

            # Keep it from getting too small
            passage_height = max(240, passage_height)

            # --- 4) Render passage ---
            clean_content = normalize_text(q_data["Content"])
            st.markdown(
                f'<div class="passage-box" style="height:{passage_height}px;">{clean_content}</div>',
                unsafe_allow_html=True
            )

        with r:
            # Flag handling
            curr_flags = st.session_state.flags.setdefault(module, {})
            is_flagged = st.checkbox(
                "🚩 Mark for Review",
                value=curr_flags.get(st.session_state.q_index, False),
                key=f"flag_{module}_{st.session_state.q_index}",
            )
            curr_flags[st.session_state.q_index] = is_flagged

            st.markdown(f"### Question {st.session_state.q_index + 1}")
            st.write(f"*{q_data['Prompt']}*")

            # -------------------------------
            # Answer UI (MCQ vs SPR)
            # -------------------------------
            q_index = st.session_state.q_index
            resp_key = (module, q_index)

            # Read type from sheet
            qtype = str(q_data.get("Question_Type", "MCQ")).strip().upper()
            if qtype not in ("MCQ", "SPR"):
                qtype = "MCQ"

            saved = st.session_state.responses.get(resp_key, {})
            saved_val = saved.get("value")  # "A"/"B"/"C"/"D" for MCQ, text for SPR

            if qtype == "MCQ":
                letters = ["A", "B", "C", "D"]
                labels = [
                    f"A) {q_data['Option_A']}",
                    f"B) {q_data['Option_B']}",
                    f"C) {q_data['Option_C']}",
                    f"D) {q_data['Option_D']}",
                ]

                # Restore selection
                saved_index = letters.index(saved_val) if saved_val in letters else None

                radio_key = f"radio_{module}_{q_index}"
                selected_label = st.radio(
                    "Answer:",
                    labels,
                    index=saved_index,
                    key=radio_key,
                    label_visibility="collapsed",
                )

                if selected_label is not None:
                    selected_letter = selected_label.split(")")[0]  # "A"/"B"/"C"/"D"
                    st.session_state.responses[resp_key] = {"type": "MCQ", "value": selected_letter}
                else:
                    st.session_state.responses.pop(resp_key, None)

            else:
                # SPR (grid-in)
                input_key = f"spr_{module}_{q_index}"
                val = st.text_input(
                    "Answer:",
                    value="" if saved_val is None else str(saved_val),
                    placeholder="Enter your answer",
                    key=input_key,
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
                    st.session_state.q_index -= 1
                    st.rerun()

            with b2:
                label = "Review Module ➡️" if st.session_state.q_index == len(df) - 1 else "Next ➡️"
                if st.button(label, use_container_width=True):
                    if st.session_state.q_index == len(df) - 1:
                        st.session_state.viewing_review = True
                    else:
                        st.session_state.q_index += 1
                    st.rerun()

    # --- 11. FOOTER NAVIGATION POPOVER ---
    st.write("---")
    _, f_mid, _ = st.columns([1, 1.6, 1])
    with f_mid:
        current_mod_flags = st.session_state.flags.get(st.session_state.module_step, {})
        flag_status = "🚩 " if current_mod_flags.get(st.session_state.q_index) else ""

        with st.popover(f"{flag_status}Question {st.session_state.q_index + 1} of {len(df)}", use_container_width=True):
            # Card header + legend
            st.markdown(
                f"""
                <div class="pop-card">
                  <div class="pop-header">
                    <div></div>
                    <div class="title">{current_label}: </div>
                    <div class="fake-x">✕</div>
                  </div>

                  <div class="pop-divider"></div>

                  <div class="legend">
                    <div class="legend-item">
                      <span style="font-size: 14px;">📍</span> Current
                    </div>
                    <div class="legend-item">
                      <span style="font-size: 14px;">🚩</span> For Review
                    </div>
                  </div>

                  <div class="pop-divider"></div>
                """,
                unsafe_allow_html=True,
            )

            # 10 per row using real Streamlit layout (this fixes the vertical stacking)
            st.markdown('<div class="pop-grid-wrap"><div class="pop-grid-inner">', unsafe_allow_html=True)

            # --- POP GRID (10 per row, SAT priority logic) ---
            module = st.session_state.module_step
            current_mod_flags = st.session_state.flags.get(module, {})

            cols = st.columns(10, gap="small")

            for i in range(len(df)):
                with cols[i % 10]:
                    # ----- SAT PRIORITY STATES -----
                    is_curr = (i == st.session_state.q_index)
                    is_flg  = current_mod_flags.get(i, False)
                    resp = st.session_state.responses.get((module, i))
                    is_ans = resp is not None and str(resp.get("value", "")).strip() != ""

                    # Priority: Current > For Review > Answered > Unanswered
                    if is_curr:
                        label = f"📍{i+1}"
                    elif is_flg:
                        label = f"🚩{i+1}"
                    else:
                        label = str(i + 1)

                    # Answered gets blue outline ONLY if it's not current/flagged
                    add_answered_outline = (is_ans and (not is_curr) and (not is_flg))

                    # Wrap button in a div that CSS can target
                    if add_answered_outline:
                        st.markdown('<div class="answered-outline">', unsafe_allow_html=True)

                    if st.button(label, key=f"nav_{module}_{i}"):
                        st.session_state.q_index = i
                        st.session_state.viewing_review = False
                        st.rerun()

                    if add_answered_outline:
                        st.markdown("</div>", unsafe_allow_html=True)
            
            # close grid wrapper HTML
            st.markdown("</div></div>", unsafe_allow_html=True)

            # Footer button centered
            st.markdown('<div class="pop-footer"><div class="footer-wrap">', unsafe_allow_html=True)
            if st.button("Go to Review Page", key="goto_rev", use_container_width=True):
                st.session_state.viewing_review = True
                st.rerun()
            st.markdown("</div></div></div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Application Error: {e}")