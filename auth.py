import streamlit as st
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json

def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["GOOGLE_SERVICE_ACCOUNT"]
    if isinstance(creds_dict, str):
        creds_dict = json.loads(creds_dict)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

def verify_user(email_input):
    """Checks if email is in the allowed Google Sheet or matches the bypass code."""
    # 1. BYPASS CHECK
    if email_input.strip() == "LOGINBYPASSTEST":
        return {"email": "admin@elimpeiro.co.za", "name": "Admin Test User", "authorized": True}

    # 2. NORMALIZATION (Lowercase matching)
    target_email = email_input.strip().lower()

    try:
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"]).sheet1
        records = sheet.get_all_records()
        
        for row in records:
            # Lowercase keys and values for matching headings like 'email' or 'Email'
            row_lower = {str(k).lower(): str(v).lower() for k, v in row.items()}
            if row_lower.get('email') == target_email:
                return {
                    "email": target_email,
                    "name": row.get('Name', row.get('name', 'Authorized User')),
                    "authorized": True
                }
    except Exception as e:
        st.error(f"Auth Error: {e}")
    
    return {"authorized": False}

def require_login(logo_b64=None):
    if not st.session_state.get('logged_in'):
        if logo_b64:
            st.markdown(f'<div style="text-align:center; padding-top: 50px;"><img src="data:image/png;base64,{logo_b64}" width="200"></div>', unsafe_allow_html=True)
        
        st.markdown("<h2 style='text-align: center; color: #1a2f5e;'>Secure Access</h2>", unsafe_allow_html=True)
        
        # Center the login box
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            email = st.text_input("Enter your registered email address:")
            if st.button("Login", use_container_width=True):
                res = verify_user(email)
                if res["authorized"]:
                    st.session_state.logged_in = True
                    st.session_state.user_email = res["email"]
                    st.session_state.user_name = res["name"]
                    st.rerun()
                else:
                    st.error("Access denied. Please check your email or contact Admin.")
        st.stop()

def show_sidebar_user():
    st.sidebar.markdown(f"**Logged in as:** \n{st.session_state.user_name}")
    st.sidebar.caption(st.session_state.user_email)
    if st.sidebar.button("Logout", key="logout_btn"):
        st.session_state.logged_in = False
        st.rerun()

def log_usage(email, bank, file_count, input_tokens, output_tokens):
    """Logs activity to the 'Usage' tab of the Google Sheet."""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"]).worksheet("Usage")
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email, bank, file_count, input_tokens, output_tokens
        ])
    except:
        pass # Fail silently
