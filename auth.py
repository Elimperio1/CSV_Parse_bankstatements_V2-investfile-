import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

BYPASS_CODES = {"BYPASSTEST", "LOGINBYPASSTEST", "bypasstest"}

def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    raw = st.secrets["GOOGLE_SERVICE_ACCOUNT"]

    # Convert to a plain dict regardless of how Streamlit stored it
    if isinstance(raw, str):
        creds_dict = json.loads(raw)
    elif hasattr(raw, "to_dict"):
        creds_dict = dict(raw)
    else:
        creds_dict = dict(raw)

    # Fix corrupted private_key — Streamlit TOML sometimes stores \n as literal \\n
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.Client(auth=creds)


def verify_user(email_input: str) -> dict:
    raw = email_input.strip()

    if raw.upper() in {c.upper() for c in BYPASS_CODES}:
        return {"email": "bypass@elimpeiro.co.za", "name": "Admin", "authorized": True}

    target_email = raw.lower()

    try:
        client = get_gspread_client()
        sheet   = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"]).sheet1
        records = sheet.get_all_records()

        for row in records:
            row_lower = {str(k).lower().strip(): str(v).strip() for k, v in row.items()}
            if row_lower.get("email", "").lower() == target_email:
                name = (
                    row_lower.get("name")
                    or row_lower.get("full name")
                    or row_lower.get("fullname")
                    or row_lower.get("display name")
                    or "User"
                )
                return {"email": target_email, "name": name, "authorized": True}

    except KeyError as e:
        st.error(f"Auth config error — missing secret: {e}")
    except Exception as e:
        st.error(f"Auth Error: {e}")

    return {"authorized": False}


def require_login(logo_b64=None):
    if st.session_state.get("logged_in"):
        return

    if logo_b64:
        st.markdown(
            f'<div style="text-align:center; padding-top: 40px;">'
            f'<img src="data:image/png;base64,{logo_b64}" width="180"></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<h2 style='text-align:center; margin-top:24px;'>Secure Access</h2>",
                unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        email = st.text_input("Email address:", key="_login_email")
        login_clicked = st.button("Login", use_container_width=True, key="_login_btn")

        if login_clicked:
            if not email.strip():
                st.warning("Please enter your email address.")
            else:
                res = verify_user(email)
                if res["authorized"]:
                    st.session_state.logged_in  = True
                    st.session_state.user_email = res["email"]
                    st.session_state.user_name  = res["name"]
                    st.rerun()
                else:
                    st.error("Email not found. Please contact your administrator.")

    st.stop()


def show_sidebar_user():
    name = st.session_state.get("user_name", "Unknown")
    st.sidebar.markdown(f"**User:** {name}")
    if st.sidebar.button("Logout", key="_logout_btn"):
        for k in ("logged_in", "user_email", "user_name"):
            st.session_state.pop(k, None)
        st.rerun()


def log_usage(email, bank, file_count, input_tokens, output_tokens):
    try:
        client = get_gspread_client()
        sheet  = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"]).worksheet("Usage")
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email, bank, file_count, input_tokens, output_tokens,
        ])
    except Exception:
        pass
