import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    raw = st.secrets["GOOGLE_SERVICE_ACCOUNT"]

    # Stored as a JSON string (triple-quoted or single-line)
    if isinstance(raw, str):
        creds_dict = json.loads(raw)
    else:
        # Streamlit parsed it as a TOML table — convert to plain dict
        creds_dict = {k: v for k, v in raw.items()}

    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.Client(auth=creds)


def log_usage(email, bank, file_count, input_tokens, output_tokens, cost_usd=0.0, cost_zar=0.0):
    try:
        client      = get_gspread_client()
        spreadsheet = client.open_by_key(st.secrets["GOOGLE_SHEET_ID"])

        # Get or create the Usage worksheet
        try:
            sheet = spreadsheet.worksheet("Usage")
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title="Usage", rows=1000, cols=10)
            sheet.append_row(["Timestamp", "Email", "Bank", "Files", "Input Tokens", "Output Tokens", "Cost USD", "Cost ZAR"])

        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            email, bank, file_count, input_tokens, output_tokens,
            round(cost_usd, 6), round(cost_zar, 4),
        ])
    except Exception:
        pass
