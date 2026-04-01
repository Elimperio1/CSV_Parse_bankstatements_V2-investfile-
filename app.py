import streamlit as st
import anthropic
import base64
import hashlib
import json, csv, io, re, time
from datetime import datetime
# SURGICAL CHANGE 1: Auth imports
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

/* ── Selectbox / dropdowns ─────────────────────────────────────────── */
div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    border: 1px solid #b0bdd4 !important;
    border-radius: 6px !important;
}
div[data-baseweb="select"] span,
div[data-baseweb="select"] div,
div[data-baseweb="select"] input { color: #1a2f5e !important; }

/* ── Buttons ─────────────────────────────────────────────────────────── */
.stButton > button {
    background: #ffffff; color: #1a2f5e;
    border: 1.5px solid #1a2f5e;
    border-radius: 6px; font-family: 'Inter', sans-serif;
    font-size: 13px; font-weight: 500;
}
.stButton > button:hover {
    background: #1a2f5e !important;
    color: #ffffff !important;
}
.stDownloadButton > button {
    background: #63eaff !important;
    color: #ffffff !important;
    border: none !important;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)

# ─── COST CONSTANTS ───────────────────────────────────────────────────────────
COST_USD_PER_M_INPUT  = 3.00   
COST_USD_PER_M_OUTPUT = 15.00  
USD_ZAR_RATE = 16.59

def calculate_cost(input_tokens: int, output_tokens: int):
    usd = (input_tokens / 1_000_000 * COST_USD_PER_M_INPUT) + \
          (output_tokens / 1_000_000 * COST_USD_PER_M_OUTPUT)
    return usd, usd * USD_ZAR_RATE

# ─── BANK PROMPTS (TRUNCATED IN PROMPT BUT KEPT FULL IN YOUR CODE) ───────────
PROMPTS = {
    "Capitec": """You are a bank statement parser. Extract Date, Description, Amount, and Balance.""",
    "Investec": """You are a bank statement parser. Extract Date, Description, Amount, and Balance.""",
    "FNB": """You are a bank statement parser. Extract Date, Description, Amount, and Balance.""",
    "ABSA": """You are a bank statement parser. Extract Date, Description, Amount, and Balance.""",
    "Nedbank": """You are a bank statement parser. Extract Date, Description, Amount, and Balance.""",
    "Standard Bank": """You are a bank statement parser. Extract Date, Description, Amount, and Balance.""",
    "Discovery Invest": """You are a bank statement parser. Extract Date, Description, Amount, and Balance.""",
    "Discovery Invest - Payments": """You are a bank statement parser. Extract Date, Description, Amount, and Balance.""",
}

PROMPTS_VISION = {
    "FNB": """You are a bank statement parser reading a scanned image...""",
}

# ─── SESSION STATE ────────────────────────────────────────────────────────────
# SURGICAL CHANGE 2: Auth keys added to defaults
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
# SURGICAL CHANGE 3: Define Logo and Gate
LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAA..." # (Place your full base64 string here)

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
    # SURGICAL CHANGE 4: User info in sidebar
    show_sidebar_user()
    
    st.markdown("### El Imperio")
    bank_options = list(PROMPTS.keys())
    selected_bank = st.selectbox("Select Bank Template", bank_options)
    
    st.markdown("---")
    st.markdown("#### Stats (Current Session)")
    total_files = len(st.session_state.processed_files)
    total_txns = sum(f['txn_count'] for f in st.session_state.processed_files)
    
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{total_files}</div>
        <div class="stat-label">Files Parsed</div>
    </div>
    <div style="margin-top:12px;"></div>
    <div class="stat-card">
        <div class="stat-number">{total_txns}</div>
        <div class="stat-label">Total Transactions</div>
    </div>
    """, unsafe_allow_html=True)

# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────────────

def rows_to_csv_bytes(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["Date", "Description", "Amount", "Balance"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode('utf-8')

def detect_bank_from_filename(filename):
    fn = filename.lower()
    for b in PROMPTS.keys():
        if b.lower() in fn:
            return b
    return None

# ─── MAIN UI ──────────────────────────────────────────────────────────────────

st.markdown("""
<div class="popia-notice">
    <div class="popia-title">POPIA & Data Privacy Notice</div>
    <div class="popia-text">
        This tool processes bank statements using Anthropic's Claude 3.5 Sonnet. 
        Data is processed in-memory and not stored permanently on our servers. 
        Ensure you have consent to process personal financial information.
    </div>
</div>
""", unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "Drop PDF bank statements here", 
    type=['pdf'], 
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}"
)

if uploaded_files:
    # Auto-detect bank if possible
    detected = detect_bank_from_filename(uploaded_files[0].name)
    if detected and not st.session_state.confirmed_bank:
        st.session_state.confirmed_bank = detected

    col1, col2 = st.columns([1, 1])
    with col1:
        st.session_state.confirmed_bank = st.selectbox(
            "Confirm Bank Template", 
            list(PROMPTS.keys()), 
            index=list(PROMPTS.keys()).index(st.session_state.confirmed_bank) if st.session_state.confirmed_bank else 0
        )
    
    if st.button("Process & Extract"):
        client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.read()
            f_hash = hashlib.md5(file_bytes).hexdigest()
            
            if f_hash in st.session_state.processed_hashes:
                st.warning(f"File {uploaded_file.name} already processed.")
                continue
                
            with st.spinner(f"Extracting {uploaded_file.name}..."):
                # Call Claude API
                message = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4096,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPTS[st.session_state.confirmed_bank]},
                            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(file_bytes).decode('utf-8')}}
                        ]
                    }]
                )
                
                # Logic to parse message.content and add to session state...
                # (Assuming standard extraction logic here)
                st.session_state.processed_hashes[f_hash] = uploaded_file.name

        # SURGICAL CHANGE 5: Log usage after processing loop
        log_usage(
            email=st.session_state.user_email,
            bank=st.session_state.confirmed_bank,
            file_count=len(uploaded_files),
            input_tokens=st.session_state.session_input_tokens,
            output_tokens=st.session_state.session_output_tokens
        )
        st.success("Processing complete!")
        st.rerun()

# ─── HISTORY ──────────────────────────────────────────────────────────────────
if st.session_state.processed_files:
    st.markdown("### Processed Files")
    for f in st.session_state.processed_files:
        st.write(f"{f['name']} - {f['txn_count']} transactions")
