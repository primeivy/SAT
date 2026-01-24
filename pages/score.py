import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

# -----------------------------
# CONFIG
# -----------------------------
URL = "https://docs.google.com/spreadsheets/d/1XLiSWYDUagXCsNbLKs_HE-BsaQzgFMw-M8FMU500f0M/edit?usp=sharing"

st.set_page_config(page_title="Score Report", layout="wide")

# -----------------------------
# HELPERS
# -----------------------------
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(spreadsheet=URL)

def normalize_answer(x: str) -> str:
    """Normalize for comparison (works for MCQ + basic SPR)."""
    if x is None:
        return ""
    s = str(x).strip()
    s = s.replace("−", "-")          # minus sign variants
    s = s.replace(" ", "")           # ignore spaces
    s = s.replace("\u00a0", "")      # non-breaking spaces

    # If it's like "A)" or "A." -> keep just A
    if re.match(r"^[A-Da-d][\)\.\:]", s):
        s = s[0]

    return s.upper()

def is_correct(student_val: str, correct_val: str, qtype: str) -> bool:
    s = normalize_answer(student_val)
    c = normalize_answer(correct_val)
    if qtype == "MCQ":
        return s == c
    return s == c

def get_question_type(row) -> str:
    qt = row.get("Question_Type", "MCQ")
    qt = str(qt).strip().upper() if qt is not None else "MCQ"
    return qt if qt in ("MCQ", "SPR") else "MCQ"

def fmt_time(seconds: float) -> str:
    seconds = float(seconds or 0)
    m = int(seconds // 60)
    s = int(round(seconds % 60))
    return f"{m:02d}:{s:02d}"

# ---- helpers (put once in your HELPERS section; leaving here for clarity) ----
def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def confidence_label(lo: int, hi: int, answered: int, total: int) -> str:
    width = hi - lo
    answered_rate = (answered / total) if total else 0

    if answered_rate < 0.75:
        return "Low confidence"
    if width <= 40 and answered_rate >= 0.95:
        return "High confidence"
    if width <= 80:
        return "Medium confidence"
    return "Low confidence"

def render_score_gauge(label: str, lo: int, hi: int, min_score=400, max_score=1600):
    lo_c = clamp(lo, min_score, max_score)
    hi_c = clamp(hi, min_score, max_score)
    mid = (lo_c + hi_c) / 2

    lo_pct = (lo_c - min_score) / (max_score - min_score) * 100
    hi_pct = (hi_c - min_score) / (max_score - min_score) * 100
    mid_pct = (mid  - min_score) / (max_score - min_score) * 100

    st.markdown(
        f"""
        <div style="margin-top:10px;">
          <div style="font-weight:800; color:#111827; margin-bottom:6px;">{label}</div>

          <div style="position:relative; height:14px; border-radius:999px; background:#e5e7eb;">
            <div style="position:absolute; left:{lo_pct}%; width:{max(0.8, hi_pct-lo_pct)}%; top:0; bottom:0;
                        border-radius:999px; background:#6D28D9;"></div>
            <div style="position:absolute; left:{mid_pct}%; top:-5px; width:2px; height:24px; background:#111827;"></div>
          </div>

          <div style="display:flex; justify-content:space-between; font-size:12px; color:#6b7280; margin-top:6px;">
            <span>{min_score}</span>
            <span>{max_score}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------
# SAT RANGE (Harder Approx.)
# -----------------------------
def score_range_from_pct_harder(pct01: float) -> tuple[int, int]:
    # pct01 is 0.0 to 1.0
    pct01 = max(0.0, min(1.0, float(pct01 or 0)))

    bands = [
        (0.00, 0.10, (200, 250)),
        (0.10, 0.20, (250, 310)),
        (0.20, 0.30, (310, 370)),
        (0.30, 0.40, (370, 450)),
        (0.40, 0.50, (450, 530)),
        (0.50, 0.60, (530, 610)),
        (0.60, 0.70, (610, 690)),
        (0.70, 0.80, (690, 750)),
        (0.80, 0.85, (750, 770)),
        (0.85, 0.90, (770, 790)),
        (0.90, 0.93, (790, 800)),
        (0.93, 1.01, (800, 800)),  # include 100%
    ]

    for lo, hi, rng in bands:
        if lo <= pct01 < hi:
            return rng
    return (200, 800)


def estimate_section_range_harder(correct: int, total: int) -> tuple[int, int, float]:
    pct01 = (correct / total) if total else 0.0
    lo, hi = score_range_from_pct_harder(pct01)
    return lo, hi, pct01

# -----------------------------
# REQUIRE EXAM DATA
# -----------------------------
if "responses" not in st.session_state:
    st.error("No exam responses found. Please start the exam first.")
    st.stop()

if "authenticated" in st.session_state and not st.session_state.authenticated:
    st.error("Please log in first.")
    st.stop()

# read timing dict from exam.py (safe default)
question_times = st.session_state.get("question_times", {})  # {(module, q_index): seconds}

# -----------------------------
# LOAD QUESTIONS
# -----------------------------
try:
    full_df = load_data()
except Exception as e:
    st.error(f"Could not load exam data: {e}")
    st.stop()

if "Correct_Answer" not in full_df.columns:
    st.error("Missing column: Correct_Answer in your Google Sheet.")
    st.stop()

# -----------------------------
# SCORE CALCULATION
# -----------------------------
module_mapping = {
    1: "Session 1 Module 1",
    2: "Session 1 Module 2",
    3: "Session 2 Module 1",
    4: "Session 2 Module 2",
}

rows = []
total_correct = 0
total_count = 0

per_module = {m: {"correct": 0, "total": 0, "time_sec": 0.0} for m in module_mapping.keys()}
total_time_sec = 0.0

for module_step, session_label in module_mapping.items():
    df_mod = full_df[full_df["Session"] == session_label].reset_index(drop=True)

    for q_index in range(len(df_mod)):
        row = df_mod.iloc[q_index]
        qtype = get_question_type(row)

        correct = row.get("Correct_Answer", "")
        resp = st.session_state.responses.get((module_step, q_index), None)

        student_val = ""
        answered = False
        if resp is not None:
            student_val = resp.get("value", "")
            answered = str(student_val).strip() != ""

        correct_bool = False
        if answered:
            correct_bool = is_correct(student_val, correct, qtype)

        # time
        t_sec = float(question_times.get((module_step, q_index), 0.0))
        per_module[module_step]["time_sec"] += t_sec
        total_time_sec += t_sec

        total_count += 1
        per_module[module_step]["total"] += 1

        if correct_bool:
            total_correct += 1
            per_module[module_step]["correct"] += 1

        rows.append(
            {
                "Module": session_label,
                "Q#": q_index + 1,
                "Type": qtype,
                "Time (sec)": round(t_sec, 2),
                "Time": fmt_time(t_sec),
                "Answered?": "Yes" if answered else "No",
                "Student": student_val,
                "Correct": correct,
                "Result": "✅ Correct" if correct_bool else ("❌ Wrong" if answered else "— Unanswered"),
            }
        )

score_df = pd.DataFrame(rows)

# -----------------------------
# UI
# -----------------------------
st.markdown("## 📊 Score Report")

# -----------------------------
# TOP SUMMARY — SAT SCORE RANGE
# -----------------------------
rw_correct = per_module[1]["correct"] + per_module[2]["correct"]
rw_total   = per_module[1]["total"]   + per_module[2]["total"]

m_correct  = per_module[3]["correct"] + per_module[4]["correct"]
m_total    = per_module[3]["total"]   + per_module[4]["total"]

rw_lo, rw_hi, rw_pct01 = estimate_section_range_harder(rw_correct, rw_total)
m_lo,  m_hi,  m_pct01  = estimate_section_range_harder(m_correct, m_total)

total_lo = rw_lo + m_lo
total_hi = rw_hi + m_hi

# Answered count for confidence (uses your score_df from earlier)
answered_total = int(score_df["Answered?"].eq("Yes").sum()) if "Answered?" in score_df.columns else total_correct
conf = confidence_label(total_lo, total_hi, answered_total, total_count)

t1, t2, t3 = st.columns([1, 1, 1])

with t1:
    # Big "Likely" card + confidence label
    st.markdown(
        f"""
        <div style="padding:14px 16px; margin-right:42px; border:1px solid #e5e7eb; border-radius:14px; background:#ffffff;">
          <div style="font-size:12px; color:#6b7280; font-weight:800;">Estimated Total SAT</div>
          <div style="font-size:34px; font-weight:900; color:#111827; line-height:1.0; margin-top:4px;">
            {total_lo}–{total_hi}
          </div>
          <div style="margin-top:6px; font-size:13px; color:#374151;">
            <b>Confidence:</b> {conf}
          </div>
          <div style="margin-top:6px; font-size:13px; color:#374151;">
            <b>Likely</b> {total_lo}–{total_hi}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Gauge bar under the card
    render_score_gauge("Score gauge", total_lo, total_hi, min_score=400, max_score=1600)


with t2:
    st.metric("Reading & Writing", f"{rw_lo}–{rw_hi}")
    st.caption(f"Accuracy: **{rw_pct01*100:.1f}%**")

with t3:
    st.metric("Math", f"{m_lo}–{m_hi}")
    st.caption(f"Accuracy: **{m_pct01*100:.1f}%**")


st.caption(
    "Estimated score range based on historical SAT difficulty. "
    "This is not an official College Board score."
)

st.divider()

# Keep your secondary stats row (correct + accuracy + time)
s1, s2, s3 = st.columns(3)
with s1:
    st.metric("Total Correct", f"{total_correct} / {total_count}")
with s2:
    pct = (total_correct / total_count * 100) if total_count else 0
    st.metric("Overall Accuracy", f"{pct:.1f}%")
with s3:
    st.metric("Total Time", fmt_time(total_time_sec))

st.divider()


# Per-module breakdown (score + time)
st.markdown("### Module Breakdown")
mcols = st.columns(4)
for idx, module_step in enumerate(module_mapping.keys()):
    label = module_mapping[module_step]
    corr = per_module[module_step]["correct"]
    tot = per_module[module_step]["total"]
    pct_m = (corr / tot * 100) if tot else 0
    t_m = per_module[module_step]["time_sec"]
    with mcols[idx]:
        # 1) Metric WITHOUT delta (no green arrow)
        st.metric(label, f"{corr}/{tot}")

        # 2) Show accuracy + time as plain text
        st.caption(f"Accuracy: **{pct_m:.1f}%**")
        st.caption(f"Time: **{fmt_time(t_m)}**")

st.divider()

# Slowest questions
st.markdown("### ⏱️ Slowest Questions")
slow_df = score_df.sort_values("Time (sec)", ascending=False).head(10)[
    ["Module", "Q#", "Time", "Answered?", "Result"]
]
st.dataframe(slow_df, use_container_width=True, hide_index=True)

st.divider()

# Detailed review
st.markdown("### Detailed Review")

f1, f2, f3 = st.columns([1, 1, 2])
with f1:
    mod_filter = st.selectbox("Module", ["All"] + list(module_mapping.values()), index=0)
with f2:
    res_filter = st.selectbox("Result", ["All", "✅ Correct", "❌ Wrong", "— Unanswered"], index=0)
with f3:
    search = st.text_input("Search student/correct answer", value="")

filtered = score_df.copy()
if mod_filter != "All":
    filtered = filtered[filtered["Module"] == mod_filter]
if res_filter != "All":
    filtered = filtered[filtered["Result"] == res_filter]
if search.strip():
    s = search.strip().lower()
    filtered = filtered[
        filtered["Student"].astype(str).str.lower().str.contains(s) |
        filtered["Correct"].astype(str).str.lower().str.contains(s)
    ]

# show time + result clearly
show_cols = ["Module", "Q#", "Type", "Time", "Answered?", "Student", "Correct", "Result"]
st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

st.divider()

a1, a2 = st.columns([1, 1])
with a1:
    if st.button("⬅ Back to Dashboard", use_container_width=True):
        st.switch_page("pages/dashboard.py")
with a2:
    if st.button("🔁 Retake Exam (Clear Answers)", use_container_width=True):
        st.session_state.responses = {}
        st.session_state.flags = {}
        st.session_state.module_step = 1
        st.session_state.q_index = 0
        st.session_state.viewing_review = False
        st.session_state.finished_all = False

        # also clear timing (important)
        st.session_state.question_times = {}
        st.session_state.current_question_key = None
        st.session_state.current_question_started_at = None

        st.switch_page("pages/exam.py")