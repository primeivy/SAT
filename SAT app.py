import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- GLOBAL CONFIG ---
st.set_page_config(page_title="Prime Ivy Portal", layout="wide")

URL = "https://docs.google.com/spreadsheets/d/1XLiSWYDUagXCsNbLKs_HE-BsaQzgFMw-M8FMU500f0M/edit?usp=sharing"

# --- AUTH STATE INIT ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# --- SHEETS HELPERS ---
def read_users(conn) -> pd.DataFrame:
    df = conn.read(spreadsheet=URL, worksheet="Users", ttl=0)
    if df is None or df.empty:
        return pd.DataFrame(columns=["Username", "Password"])

    # normalize colnames
    col_map = {c.strip().lower(): c for c in df.columns}
    ucol = col_map.get("username")
    pcol = col_map.get("password")

    if not ucol or not pcol:
        # force expected shape so error messages are clearer
        return pd.DataFrame(columns=["Username", "Password"])

    # rename to canonical
    df = df.rename(columns={ucol: "Username", pcol: "Password"})

    # drop blank rows
    df = df.dropna(subset=["Username", "Password"])
    df["Username"] = df["Username"].astype(str)
    df["Password"] = df["Password"].astype(str)
    return df


def write_users(conn, users_df: pd.DataFrame):
    # MUST write back full sheet
    conn.update(spreadsheet=URL, worksheet="Users", data=users_df)


def login_page():
    _, center, _ = st.columns([1, 1.5, 1])
    with center:
        st.image(
            "https://github.com/primeivy/SAT/blob/main/assets/images/College%20Counseling%20&%20Academic%20Mentorship.png?raw=true",
            width=200,
        )
        st.title("Prime Ivy Portal")

        tab1, tab2 = st.tabs(["Log In", "Create Account"])

        # -------------------------
        # TAB 1: LOGIN
        # -------------------------
        with tab1:
            user = st.text_input("Username", key="login_user")
            pw = st.text_input("Password", type="password", key="login_pw")

            if st.button("Log In", use_container_width=True):
                if not user or not pw:
                    st.error("Please enter both username and password")
                    return

                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    users_df = read_users(conn)

                    if users_df.empty:
                        st.error("User database is empty. Please create an account.")
                        return

                    # normalize for matching
                    users_df["Username_norm"] = users_df["Username"].astype(str).str.strip().str.lower()
                    users_df["Password_norm"] = users_df["Password"].astype(str).str.strip()

                    user_input = str(user).strip().lower()
                    pw_input = str(pw).strip()

                    match = users_df[
                        (users_df["Username_norm"] == user_input) &
                        (users_df["Password_norm"] == pw_input)
                    ]

                    if not match.empty:
                        st.session_state.authenticated = True
                        st.session_state.user_name = user_input
                        st.switch_page("pages/dashboard.py")
                    else:
                        st.error("Invalid username or password.")

                except Exception as e:
                    st.error(f"Login Error: {e}")

        # -------------------------
        # TAB 2: CREATE ACCOUNT
        # -------------------------
        with tab2:
            new_user = st.text_input("New Username", key="reg_user")
            new_pw = st.text_input("New Password", type="password", key="reg_pw")
            confirm_pw = st.text_input("Confirm Password", type="password", key="reg_confirm")

            if st.button("Sign Up", use_container_width=True):
                if not new_user or not new_pw or not confirm_pw:
                    st.error("Please fill in all fields")
                    return
                if new_pw != confirm_pw:
                    st.error("Passwords do not match")
                    return

                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    users_df = read_users(conn)

                    # if sheet is missing required columns
                    if "Username" not in users_df.columns or "Password" not in users_df.columns:
                        st.error("Users sheet must have columns: Username, Password")
                        return

                    new_user_clean = str(new_user).strip()
                    new_pw_clean = str(new_pw).strip()

                    # check duplicates (case-insensitive)
                    existing_norm = users_df["Username"].astype(str).str.strip().str.lower()
                    if (existing_norm == new_user_clean.lower()).any():
                        st.error("Username already exists. Please choose another.")
                        return

                    new_row = pd.DataFrame([{"Username": new_user_clean, "Password": new_pw_clean}])
                    updated = pd.concat([users_df[["Username", "Password"]], new_row], ignore_index=True)

                    write_users(conn, updated)

                    st.success("Account created successfully! You can now log in.")

                except Exception as e:
                    st.error(f"Error saving to Google Sheets: {e}")


# --- ROUTING ---
if st.session_state.authenticated:
    st.switch_page("pages/dashboard.py")
else:
    login_page()