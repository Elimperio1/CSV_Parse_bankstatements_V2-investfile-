# auth.py
import json
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

GSHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ─── GOOGLE SHEETS CLIENT ─────────────────────────────────────────────────────

@st.cache_resource(ttl=300)
def get_gsheet_client():
    """Authenticated gspread client, cached for 5 minutes."""
    try:
        raw = st.secrets["GOOGLE_SERVICE_ACCOUNT"]
        info = json.loads(raw) if isinstance(raw, str) else dict(raw)
        creds = Credentials.from_service_account_info(info, scopes=GSHEET_SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None

def get_worksheet(tab_name: str):
    """Return a gspread worksheet by tab name, or None on failure."""
    try:
        client = get_gsheet_client()
        if not client:
            return None
        sheet = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"])
        return sheet.worksheet(tab_name)
    except Exception:
        return None

def get_authorised_users() -> dict:
    """
    Return {email_lower: name} for all active users.
    Falls back to empty dict if sheet is unreachable.
    """
    try:
        ws = get_worksheet("users")
        if not ws:
            return {}
        records = ws.get_all_records()
        return {
            r["email"].strip().lower(): r["name"].strip()
            for r in records
            if str(r.get("active", "")).upper() == "TRUE" and r.get("email")
        }
    except Exception:
        return {}

def log_usage(email: str, name: str, page: str, bank: str,
              filename: str, section: str, pages_processed: int,
              input_tokens: int, output_tokens: int,
              cost_usd: float, cost_zar: float):
    """
    Append one usage row to usage_log.
    Captures exactly what Anthropic billed for that API call.
    Silent on failure — never crashes the app.
    """
    try:
        ws = get_worksheet("usage_log")
        if not ws:
            return
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email,
            name,
            page,
            bank,
            filename,
            section,
            pages_processed,
            input_tokens,
            output_tokens,
            round(cost_usd, 6),
            round(cost_zar, 4),
        ], value_input_option="USER_ENTERED")
    except Exception:
        pass

# ─── LOGIN HELPERS ────────────────────────────────────────────────────────────

def init_auth_state():
    """Ensure auth keys exist in session state. Call at top of every page."""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in  = False
    if "user_email" not in st.session_state:
        st.session_state.user_email = ""
    if "user_name" not in st.session_state:
        st.session_state.user_name  = ""

def show_login_screen(logo_b64: str = ""):
    """Render login screen and block with st.stop() until authenticated."""
    if logo_b64:
        st.markdown(f"""
        <div class="eli-header">
            <div class="eli-logo">
                <img src="data:image/jpeg;base64,{logo_b64}" alt="El Imperio Logo" />
            </div>
            <div class="eli-divider"></div>
            <div class="eli-title-block">
                <div class="eli-title">El Imperio</div>
                <div class="eli-subtitle">Bank Statement Extractor · Powered by Claude AI</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Sign in to continue")
    st.caption("Use your El Imperio company email address.")

    email_input = st.text_input(
        "Company email",
        placeholder="yourname@elimpeiro.co.za",
        label_visibility="collapsed",
        key="login_email_input"
    ).strip().lower()

    if st.button("Continue", key="login_btn"):
        if not email_input:
            st.warning("Please enter your email address.")
        else:
            users = get_authorised_users()
            if email_input in users:
                st.session_state.logged_in  = True
                st.session_state.user_email = email_input
                st.session_state.user_name  = users[email_input]
                st.rerun()
            else:
                admin = st.secrets.get("ADMIN_EMAIL", "the administrator")
                st.error(
                    f"**{email_input}** is not registered.\n\n"
                    f"Please contact **{admin}** to request access. "
                    f"Once your email has been added you can sign in here."
                )
                # Log the access attempt so admin can see who needs adding
                log_usage(
                    email=email_input, name="UNREGISTERED",
                    page="login", bank="", filename="",
                    section="access_request", pages_processed=0,
                    input_tokens=0, output_tokens=0,
                    cost_usd=0.0, cost_zar=0.0,
                )
    st.stop()

def require_login(logo_b64: str = ""):
    """
    Call at the top of every page after CSS.
    If not logged in — shows login screen and stops.
    If already logged in — returns immediately, page renders normally.
    Session state is shared across pages so login only happens once per session.
    """
    init_auth_state()
    if not st.session_state.logged_in:
        show_login_screen(logo_b64)

def show_sidebar_user():
    """
    Call inside `with st.sidebar:` on every page.
    Shows logged-in user name, email, and sign-out button.
    """
    st.markdown(f"👤 **{st.session_state.get('user_name', '')}**")
    st.caption(st.session_state.get('user_email', ''))
    if st.button("Sign out", use_container_width=True, key="signout_btn"):
        st.session_state.logged_in  = False
        st.session_state.user_email = ""
        st.session_state.user_name  = ""
        st.rerun()
    st.markdown("---")
