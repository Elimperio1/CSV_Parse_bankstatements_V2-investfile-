import streamlit as st
import anthropic
import base64
import hashlib
import json, csv, io, re, time
from datetime import datetime
from auth import require_login, show_sidebar_user, log_usage

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="El Imperio CSV Parser",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CUSTOM CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');

/* ── Base — white body matching logo background ───────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #f5f6f8;
    color: #1a2f5e;
}
.stApp { background-color: #f5f6f8; }
h1, h2, h3, h4 {
    font-family: 'Cormorant Garamond', serif;
    color: #1a2f5e;
}

/* ── Header — pure white so logo blends seamlessly ───────────────────── */
.eli-header {
    background: #ffffff;
    border-bottom: 3px solid #1a2f5e;
    padding: 18px 36px;
    margin: -1rem -1rem 2rem -1rem;
    display: flex;
    align-items: center;
    gap: 24px;
    box-shadow: 0 2px 12px rgba(26,47,94,0.08);
}
.eli-logo img  { height: 60px; width: auto; }
.eli-divider   { width: 1px; height: 52px; background: #8a9ab8; margin: 0 8px; opacity: 0.5; }
.eli-title-block { display: flex; flex-direction: column; justify-content: center; }
.eli-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 30px; font-weight: 700;
    color: #1a2f5e; margin: 0; letter-spacing: 0.5px;
}
.eli-subtitle {
    font-size: 10px; color: #8a9ab8;
    letter-spacing: 2.5px; text-transform: uppercase; margin-top: 4px;
}

/* ── Stat cards ──────────────────────────────────────────────────────── */
.stat-card {
    background: #ffffff;
    border: 1px solid #d0d8e8;
    border-top: 3px solid #1a2f5e;
    border-radius: 8px; padding: 16px; text-align: center;
    box-shadow: 0 2px 8px rgba(26,47,94,0.06);
}
.stat-number { font-size: 28px; color: #1a2f5e; font-weight: 700; }
.stat-label  { font-size: 10px; color: #8a9ab8; letter-spacing: 2px; text-transform: uppercase; margin-top: 4px; }

/* ── Cost card ───────────────────────────────────────────────────────── */
.cost-card {
    background: #ffffff; border: 1px solid #d0d8e8;
    border-left: 4px solid #1a2f5e;
    border-radius: 8px; padding: 12px 16px; margin-top: 8px;
    box-shadow: 0 2px 8px rgba(26,47,94,0.06);
}
.cost-label { font-size: 10px; color: #8a9ab8; letter-spacing: 2px; text-transform: uppercase; }
.cost-value { font-size: 15px; color: #1a2f5e; font-weight: 600; margin-top: 2px; }
.cost-note  { font-size: 10px; color: #8a9ab8; margin-top: 4px; }

/* ── POPIA notice ────────────────────────────────────────────────────── */
.popia-notice {
    background: #eef1f7;
    border: 1px solid #c0cce0;
    border-left: 4px solid #1a2f5e;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 18px;
}
.popia-title { font-size: 10px; color: #1a2f5e; letter-spacing: 2px; text-transform: uppercase; font-weight: 600; }
.popia-text  { font-size: 11px; color: #3a5080; margin-top: 5px; line-height: 1.65; }

/* ── Sidebar ─────────────────────────────────────────────────────────── */
div[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 2px solid #d0d8e8 !important;
}
div[data-testid="stSidebar"],
div[data-testid="stSidebar"] * { color: #1a2f5e !important; }
div[data-testid="stSidebar"] .stCaption,
div[data-testid="stSidebar"] .stCaption p,
div[data-testid="stSidebar"] small { color: #6a80a8 !important; }
div[data-testid="stSidebar"] hr    { border-color: #d0d8e8 !important; }

/* ── Browse files button inside uploader ─────────────────────────────── */
[data-testid="stFileUploader"] button,
[data-testid="stFileUploaderDropzone"] button {
    background: #1a2f5e !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    padding: 8px 20px !important;
}
[data-testid="stFileUploader"] button:hover,
[data-testid="stFileUploaderDropzone"] button:hover {
    background: #0f1f42 !important;
    color: #ffffff !important;
}
[data-testid="stFileUploader"] p,
[data-testid="stFileUploader"] span,
[data-testid="stFileUploader"] small { color: #6a80a8 !important; }

/* ── Selectbox / dropdowns — navy text on white ──────────────────────── */
div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border: 1px solid #b0bdd4 !important;
    border-radius: 6px !important;
}
div[data-baseweb="select"] span,
div[data-baseweb="select"] div,
div[data-baseweb="select"] input { color: #1a2f5e !important; }
div[data-baseweb="popover"],
div[data-baseweb="menu"]         { background-color: #ffffff !important; border: 1px solid #d0d8e8 !important; }
li[role="option"]                { background-color: #ffffff !important; color: #1a2f5e !important; }
li[role="option"]:hover          { background-color: #eef1f7 !important; }

/* ── Radio buttons ───────────────────────────────────────────────────── */
div[data-testid="stRadio"] label p { color: #1a2f5e !important; }
div[data-testid="stRadio"] p       { color: #1a2f5e !important; }

/* ── Number inputs ───────────────────────────────────────────────────── */
div[data-testid="stNumberInput"] input {
    background-color: #ffffff !important;
    color: #1a2f5e !important;
    border: 1px solid #b0bdd4 !important;
}
div[data-testid="stNumberInput"] label p { color: #1a2f5e !important; }

/* ── Expander ────────────────────────────────────────────────────────── */
div[data-testid="stExpander"] {
    background-color: #ffffff !important;
    border: 1px solid #d0d8e8 !important;
    border-radius: 8px !important;
}
div[data-testid="stExpander"] summary p { color: #1a2f5e !important; }
div[data-testid="stExpander"] p         { color: #1a2f5e !important; }

/* ── File uploader ───────────────────────────────────────────────────── */
[data-testid="stFileUploader"] section {
    min-height: 180px;
    display: flex; align-items: center; justify-content: center;
    border: 2px dashed #b0bdd4 !important;
    border-radius: 10px !important;
    background: #ffffff !important;
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"] section:hover { border-color: #1a2f5e !important; }
[data-testid="stFileUploader"] section > div { padding: 32px 0; }
[data-testid="stFileUploader"] label p       { color: #1a2f5e !important; }

/* ── Buttons ─────────────────────────────────────────────────────────── */
.stButton > button {
    background: #ffffff; color: #1a2f5e;
    border: 1.5px solid #1a2f5e;
    border-radius: 6px; font-family: 'Inter', sans-serif;
    font-size: 13px; font-weight: 500;
    letter-spacing: 0.3px; transition: all 0.2s;
}
.stButton > button:hover {
    background: #1a2f5e !important;
    color: #ffffff !important;
}
.stDownloadButton > button {
    background: #63eaff !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    width: 100%;
}
.stDownloadButton > button:hover {
    background: #0f1f42 !important;
}

/* ── Tabs ────────────────────────────────────────────────────────────── */
button[data-baseweb="tab"]                        { color: #8a9ab8 !important; font-family: 'Inter', sans-serif !important; }
button[data-baseweb="tab"][aria-selected="true"]  { color: #1a2f5e !important; border-bottom-color: #1a2f5e !important; }

/* ── Dataframe ───────────────────────────────────────────────────────── */
div[data-testid="stDataFrame"] { border: 1px solid #d0d8e8 !important; border-radius: 8px; }

/* ── General text ────────────────────────────────────────────────────── */
p, li, span, label               { color: #1a2f5e; }
.stCaption p                     { color: #6a80a8 !important; }
.stMarkdown p                    { color: #1a2f5e; }

/* ── Info / warning / success / error boxes ──────────────────────────── */
div[data-testid="stAlert"]       { border-radius: 8px !important; }

/* ── Section headings ────────────────────────────────────────────────── */
.stMarkdown h4 { color: #1a2f5e !important; font-family: 'Cormorant Garamond', serif !important; font-size: 20px !important; }
</style>
""", unsafe_allow_html=True)

# ─── COST CONSTANTS ───────────────────────────────────────────────────────────
COST_USD_PER_M_INPUT  = 3.00   
COST_USD_PER_M_OUTPUT = 15.00  
USD_ZAR_RATE = 16.59

def calculate_cost(input_tokens: int, output_tokens: int):
    """Return (cost_usd, cost_zar) for a given token usage."""
    usd = (input_tokens / 1_000_000 * COST_USD_PER_M_INPUT) + \
          (output_tokens / 1_000_000 * COST_USD_PER_M_OUTPUT)
    return usd, usd * USD_ZAR_RATE

# ─── BANK PROMPTS (TEXT PDF) ──────────────────────────────────────────────────
PROMPTS = {
    "Capitec": """You are a bank statement parser...""",
    "Investec": """You are a bank statement parser...""",
    "FNB": """You are a bank statement parser...""",
    "ABSA": """You are a bank statement parser...""",
    "Nedbank": """You are a bank statement parser...""",
    "Standard Bank": """You are a bank statement parser...""",
    "Discovery Invest": """You are a bank statement parser...""",
    "Discovery Invest - Payments": """You are a bank statement parser...""",
}

PROMPTS_VISION = {
    "FNB": """You are a bank statement parser reading a scanned image...""",
}

# ─── SESSION STATE ────────────────────────────────────────────────────────────
defaults = {
    'processed_files':       [],
    'all_rows':              [],
    'confirmed_bank':        None,
    'confirmed_files':       [],
    'history':               [],
    'cached_upload_bytes':   {},
    'uploader_key':          0,
    'session_input_tokens':  0,
    'session_output_tokens': 0,
    'processed_hashes':      {},
    'logged_in':             False,
    'user_email':            '',
    'user_name':             '',
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ─── LOGO + LOGIN GATE ────────────────────────────────────────────────────────
LOGO_B64 = "/9j/4AAQSkZJRgABAQEAYABgAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlBFRyB2ODApLCBxdWFsaXR5ID0gODIK/9sAQwAGBAQFBAQGBQUFBgYGBwkOCQkICAkSDQ0KDhUSFhYVEhQUFxohHBcYHxkUFB0nHR8iIyUlJRYcKSwoJCshJCUk/9sAQwEGBgYJCAkRCQkRJBgUGCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQk/8AAEQgBKQQAAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFB..." # Truncated for brevity
require_login(logo_b64=LOGO_B64)

# ─── HEADER ──────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="eli-header">
    <div class="eli-logo"><img src="data:image/png;base64,{LOGO_B64}"></div>
    <div class="eli-divider"></div>
    <div class="eli-title-block">
        <h1 class="eli-title">CSV Parser</h1>
        <div class="eli-subtitle">Transaction extraction engine</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    show_sidebar_user()
    st.markdown("### El Imperio")
    # ... rest of sidebar code ...

# ─── MAIN APP LOGIC ───────────────────────────────────────────────────────────
# ... [Other functions: detect_bank_from_filename, get_client, etc.] ...

# ─── EXTRACTION LOOP ──────────────────────────────────────────────────────────
# Inside the processing loop where files are handled:
# for file in files:
#     ...
#     st.session_state.processed_hashes[f_hash] = f_name
log_usage(
    email=st.session_state.user_email,
    bank=st.session_state.confirmed_bank,
    file_count=len(st.session_state.confirmed_files),
    input_tokens=st.session_state.session_input_tokens,
    output_tokens=st.session_state.session_output_tokens
)
