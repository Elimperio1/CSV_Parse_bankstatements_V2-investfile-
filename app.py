import streamlit as st
import anthropic
import base64
import hashlib
import json, csv, io, re, time
from datetime import datetime

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SA Bank → CSV",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CUSTOM CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Syne:wght@400;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Mono', monospace; background-color: #0a0a0a; color: #d0cdc6; }
.stApp { background-color: #0a0a0a; }
h1, h2, h3 { font-family: 'Syne', sans-serif; color: #ffffff; }
.main-header {
    background: linear-gradient(135deg, #0d1a0d 0%, #0a0a0a 100%);
    border-bottom: 1px solid #1a2a1a;
    padding: 24px 32px;
    margin: -1rem -1rem 2rem -1rem;
}
.header-title { font-family: 'Syne', sans-serif; font-size: 28px; color: #ffffff; margin: 0; letter-spacing: -0.5px; }
.header-sub { font-size: 11px; color: #4a6a4a; letter-spacing: 2px; text-transform: uppercase; margin-top: 4px; }
.stat-card { background: #0d0d0d; border: 1px solid #1a2a1a; border-radius: 8px; padding: 16px; text-align: center; }
.stat-number { font-size: 28px; color: #6ab86a; font-weight: 500; }
.stat-label { font-size: 10px; color: #4a4a4a; letter-spacing: 2px; text-transform: uppercase; margin-top: 4px; }
.cost-card { background: #0d0d0d; border: 1px solid #1a2a1a; border-radius: 8px; padding: 12px 16px; margin-top: 8px; }
.cost-label { font-size: 10px; color: #4a4a4a; letter-spacing: 2px; text-transform: uppercase; }
.cost-value { font-size: 15px; color: #6ab86a; font-weight: 500; margin-top: 2px; }
.cost-note { font-size: 10px; color: #2a4a2a; margin-top: 4px; }
.popia-notice {
    background: #0a0f1a; border: 1px solid #1a2a4a; border-radius: 8px;
    padding: 12px 16px; margin-bottom: 18px;
}
.popia-title { font-size: 10px; color: #4a7abf; letter-spacing: 2px; text-transform: uppercase; font-weight: 500; }
.popia-text { font-size: 11px; color: #3a5a7a; margin-top: 5px; line-height: 1.65; }
div[data-testid="stSidebar"] { background-color: #080808; border-right: 1px solid #1a1a1a; }
.stButton > button {
    background: #0d1a0d; color: #6ab86a; border: 1px solid #1a3a1a;
    border-radius: 6px; font-family: 'DM Mono', monospace;
    letter-spacing: 0.5px; transition: all 0.2s;
}
.stButton > button:hover { background: #1a3a1a; border-color: #4a9e4a; color: #ffffff; }
.stDownloadButton > button {
    background: #0070f3 !important; color: #ffffff !important;
    border: none !important; border-radius: 6px !important;
    font-family: 'DM Mono', monospace !important; width: 100%;
}
.bank-badge {
    display: inline-block; padding: 2px 10px; border-radius: 4px;
    font-size: 11px; font-weight: 500; letter-spacing: 1px; text-transform: uppercase;
}
[data-testid="stFileUploader"] section {
    min-height: 180px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px dashed #2a3a2a !important;
    border-radius: 10px !important;
    background: #0d0d0d !important;
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"] section:hover { border-color: #4a9e4a !important; }
[data-testid="stFileUploader"] section > div { padding: 32px 0; }
</style>
""", unsafe_allow_html=True)

# ─── COST CONSTANTS ───────────────────────────────────────────────────────────
# claude-sonnet-4-6 pricing (Anthropic published rates)
COST_USD_PER_M_INPUT  = 3.00   # $ per million input tokens
COST_USD_PER_M_OUTPUT = 15.00  # $ per million output tokens
# USD/ZAR 3-month average Dec 2025 – Feb 2026
USD_ZAR_RATE = 16.59

def calculate_cost(input_tokens: int, output_tokens: int):
    """Return (cost_usd, cost_zar) for a given token usage."""
    usd = (input_tokens / 1_000_000 * COST_USD_PER_M_INPUT) + \
          (output_tokens / 1_000_000 * COST_USD_PER_M_OUTPUT)
    return usd, usd * USD_ZAR_RATE

# ─── BANK PROMPTS (TEXT PDF) ──────────────────────────────────────────────────

PROMPTS = {

"Capitec": """You are a bank statement parser. Your ONLY output must be a valid JSON array. No explanation, no markdown, no code fences, no preamble, no postamble — just the raw JSON array starting with [ and ending with ].

TASK: Extract every transaction from this Capitec Business Account statement.

COLUMNS IN THE STATEMENT:
Post Date | Trans. Date | Description | Reference | Fees | Amount | Balance

Each object must have exactly these keys:
- "date": string DD/MM/YYYY — use Trans. Date (second date column), convert 2-digit year e.g. "01/06/25" → "01/06/2025"
- "details": string — combine Description and Reference as "Description - Reference", or just Description if no Reference
- "amount": number — the Amount column value as a signed number (negative = money out, positive = money in). Remove commas.
- "fee": number — the Fees column value as a negative number (e.g. -1.00), or 0 if the Fees column is empty for this row

AMOUNT SIGN: Amount column values already carry their sign (e.g. -521.02 is debit, +1203.69 is credit). Preserve the sign.

SPECIAL CASE — rows where Amount column is empty/zero but Fees column has a value (e.g. Monthly Service Fee, Notification Fee):
- Set "amount" to the fee value as a NEGATIVE number
- Set "fee" to 0
- Example: Monthly Service Fee with fee=-50.00, amount=empty → {"amount": -50.00, "fee": 0}

MASKED CARD ROWS (description like "******006073** **"):
- These are card/ATM transactions. Use Description as-is for details, combine with Reference: "******006073** ** - Payee Name"
- They have BOTH a fee (Fees column) AND an amount (Amount column) — output both normally

INTERNATIONAL POS rows:
- Have BOTH a fee (Fees column) AND an amount (Amount column) — output both normally

BACKDATED S/DEBIT rows:
- Have BOTH a fee (Fees column, typically -1.00) AND an amount (Amount column) — output both normally

SKIP:
- Balance brought forward line
- Interest Rate @ line
- Fee Total and VAT Total summary lines
- Any header or footer lines

Return ONLY the JSON array, nothing else.""",

"Investec": """You are a bank statement parser. Your ONLY output must be a valid JSON array. No explanation, no markdown, no code fences — just the raw JSON array starting with [ and ending with ].

TASK: Extract every transaction from the MAIN TRANSACTION TABLE of this Investec bank statement.
The main table has columns: Posted Date | Trans Date | Transaction Description | Debit | Credit | Balance

CRITICAL — the PDF has TWO sections that look like transaction tables:
1. The MAIN table (Posted Date, Trans Date, Description, Debit, Credit, Balance) — USE THIS ONE
2. A secondary "Online payments, deposits, fees and interest" summary table — IGNORE THIS ENTIRELY
3. A "Card transactions" summary table — IGNORE THIS ENTIRELY

Each object must have exactly these keys:
- "date": string DD/MM/YYYY — use Trans Date column (format "2 Feb 2026" → "02/02/2026")
- "details": string — the Transaction Description column value
- "amount": number — if Credit column has a value: POSITIVE. If Debit column has a value: NEGATIVE. Remove commas.

IMPORTANT SIGN RULES:
- Credits (money IN to the account) = POSITIVE: deposits, interest received, incoming transfers
- Debits (money OUT of the account) = NEGATIVE: payments, fees, outgoing transfers, card purchases
- "Cr Interest Adjustment" appears in the Debit column = NEGATIVE (it is interest being charged/adjusted out)
- "Credit interest" appears in the Credit column = POSITIVE

INCLUDE every row in the main table, even if the same description and amount appears multiple times on the same date (e.g. multiple "Electronic debit fee" rows on the same day are separate real transactions).

SKIP ONLY:
- "Balance brought forward" line
- "Closing Balance" line
- Any subtotal or total rows

Return ONLY the JSON array, nothing else.""",

"FNB": """You are a bank statement parser. Your ONLY output must be a valid JSON array. No explanation, no markdown, no code fences, no preamble, no postamble — just the raw JSON array starting with [ and ending with ].

TASK: Extract every transaction from this FNB Gold Business Account statement.

COLUMNS IN THE STATEMENT:
Date | Description | Amount | Balance | Accrued Bank Charges

Each object must have exactly these keys:
- "date": string DD/MM/YYYY — dates appear as "DD Mon" e.g. "01 Mar". Get the year from the statement period header line "Statement Period : DD Month YYYY to DD Month YYYY". Output as DD/MM/YYYY e.g. "01/03/2025".
- "details": string — use the full Description text. For rows prefixed with "#" (fee rows), strip the "#" e.g. "#Monthly Account Fee" → "Monthly Account Fee"
- "amount": number — if Amount ends with "Cr" it is POSITIVE (money in). If no suffix it is NEGATIVE (money out). Remove "Cr" suffix and all commas before converting. Example: "17,000.00Cr" → 17000.00, "23,600.00" → -23600.00

IGNORE completely:
- The Balance column
- The Accrued Bank Charges column — these are NOT separate transactions, do not output rows for them
- Opening Balance / Closing Balance lines
- Turnover for Statement Period section
- Any row where Amount is exactly 0.00 or missing

FEE ROWS (lines starting with "#" e.g. "#Monthly Account Fee", "#Service Fees"):
- These are normal debit rows — output ONE row each
- Amount has no "Cr" suffix so it is NEGATIVE
- Strip the "#" from details

Return ONLY the JSON array, nothing else.""",

"ABSA": """You are a bank statement parser. Extract ALL transactions from this ABSA bank statement.

Return ONLY a valid JSON array. No markdown, no code fences, no explanation.

SOURCE TABLE: Only extract from the main "Your transactions" table (columns: Date | Transaction Description | Charge | Debit Amount | Credit Amount | Balance). Pages show "Your transactions (continued)" — same table, keep extracting.

ABSA prints a small repeat summary box at the bottom of every page — it looks like 4 columns with the account number at the top and shows a few recent transactions again. IGNORE THIS ENTIRELY — it causes duplicates.

Also ignore:
- Account Summary section (Balance Brought Forward, Deposits, Sundry Credits totals)
- SERVICE FEE / MNTHLY ACCT FEE footer lines
- CHARGE legend (A = ADMINISTRATION C = CASH DEPOSIT etc.)
- Any row with no date, Bal Brought Forward

Each object must have exactly these keys:
- date (string DD/MM/YYYY — input like "3/09/2024" or "1/10/2024", normalise to DD/MM/YYYY)
- details (string — combine Transaction Description lines 1 and 2, separated by " - ". Strip spaces.)
- amount (number — Debit Amount = NEGATIVE, Credit Amount = POSITIVE. Remove commas. Ignore Charge column.)

Return ONLY the JSON array, nothing else.""",

"Nedbank": """You are a bank statement parser. Extract ALL transactions from this Nedbank bank statement.

Return ONLY a valid JSON array. No markdown, no code fences, no explanation.
Skip: BROUGHT FORWARD, CARRIED FORWARD, PROVISIONAL STATEMENT rows, any totals or summary rows.

Each object must have exactly these keys:
- date (string DD/MM/YYYY — input format is already DD/MM/YYYY)
- details (string — the Transactions column description)
- amount (number — if Debit column has value it is already negative (keep as negative), if Credit column has value it is positive. Remove commas from numbers.)

Return ONLY the JSON array, nothing else.""",

"Standard Bank": """You are a bank statement parser. Your ONLY output must be a valid JSON array. No explanation, no markdown, no code fences, no preamble, no postamble — just the raw JSON array starting with [ and ending with ].

TASK: Extract every transaction from this Standard Bank Private Banking Current Account statement.

Each object must have exactly these keys:
- "date": string DD/MM/YYYY
- "details": string
- "amount": number (negative = money out, positive = money in)

DATE RULES:
- Dates appear as "MM DD" e.g. "02 09" means February 9, "03 01" means March 1
- Find the statement year from the header line "Statement from DD Month YYYY to DD Month YYYY"
- Output format: DD/MM/YYYY e.g. "09/02/2024"
- If a transaction date falls before the statement start date, it belongs to the next year

DETAILS RULES:
- Each transaction has a main description line and sometimes a second reference line below it
- Combine both lines into one string separated by " - "
- Strip all leading/trailing whitespace

AMOUNT RULES:
- Debits: values ending with "-" e.g. "28,500.00-" → -28500.00 (NEGATIVE)
- Credits: plain values e.g. "1,500.00" → 1500.00 (POSITIVE)
- Balance column values like "177,552.74-" → IGNORE COMPLETELY (these are balances, not amounts)
- Fees marked "##" are already included in the Debits column — do NOT create extra rows for them
- Remove all commas from numbers

SKIP THESE ENTIRELY:
- BALANCE BROUGHT FORWARD line
- VAT Summary section (any rows mentioning Total VAT, VAT amount)
- Account Summary section (Balance at date of statement, etc.)
- Limit Structure section
- Any row with no date
- Any header or footer lines

Return ONLY the JSON array, nothing else.""",

"Discovery Invest": """You are a bank statement parser. Your ONLY output must be a valid JSON array. No explanation, no markdown, no code fences, no preamble, no postamble — just the raw JSON array starting with [ and ending with ].

TASK: Extract every transaction from this Discovery Invest statement.

THE TABLE HAS EXACTLY THESE COLUMNS (in order):
  Effective date | Transaction description | Transaction amount | Units | Fund name

CRITICAL: The "Units" column must be COMPLETELY IGNORED. Do not read or use any value from it.

Each object must have exactly these keys:
- "date": string DD/MM/YYYY — the Effective date column is already in DD/MM/YYYY format e.g. "15/09/2025". Output as-is.
- "details": string — the Transaction description column value, verbatim.
- "amount": number — the Transaction amount column. Strip the leading "R", remove all commas, preserve the sign.
  Examples:
    "R-0.20"       → -0.20
    "R-1,234.56"   → -1234.56
    "R1,234.56"    → 1234.56
    "R+1,234.56"   → 1234.56
    "R (1,234.56)" → -1234.56 (parentheses = negative)
- "reference": string — the Fund name column value, verbatim (e.g. "Allan Gray Balanced Fund").

AMOUNT SIGN RULES:
- Negative (fees, deductions): "R-0.20" → -0.20
- Positive (contributions, income): "R1,234.56" → 1234.56
- The sign is embedded immediately after the "R" prefix.
- If parentheses are used instead of a minus sign: "R(0.20)" → -0.20

SKIP THESE ROWS ENTIRELY:
- The column header row (Effective date / Transaction description / etc.)
- The reporting period header line ("Transaction details for the reporting period...")
- Any row where Transaction amount is blank, zero, or "R0.00"
- Any summary, subtotal, or total rows
- Any page header or footer lines

INCLUDE:
- Every individual transaction row, even if multiple rows share the same date and description (they will have different Fund names).
- Rows with very small amounts (e.g. "R-0.20") are real fee transactions — include them.

Return ONLY the JSON array, nothing else.""",
}

# ─── BANK PROMPTS (VISION / SCANNED PDF OVERRIDES) ───────────────────────────
# Only banks that need different instructions for vision mode are listed here.
# All others fall back to PROMPTS[bank].

PROMPTS_VISION = {

"FNB": """You are a bank statement parser reading a scanned image of an FNB bank statement. Your ONLY output must be a valid JSON array. No explanation, no markdown, no code fences, no preamble, no postamble — just the raw JSON array starting with [ and ending with ].

TASK: Extract every transaction from this FNB statement image.

THE TABLE HAS THESE COLUMNS IN ORDER (left to right):
  Column 1: Date          — e.g. "01 Dec", "02 Dec"
  Column 2: Type          — e.g. "Magtape Credit", "Internet Pmt To", "Send Money Dr"
  Column 3: Description   — narrative text, may be empty
  Column 4: Reference     — secondary reference text, may be empty
  Column 5: Amount        — THE ONLY COLUMN YOU EXTRACT A NUMBER FROM for the amount field
  Column 6: Balance       — IGNORE ENTIRELY — do not read any value from this column
  Column 7: Bank Charges  — IGNORE ENTIRELY — do not read any value from this column

AMOUNT SIGN RULES — READ COLUMN 5 ONLY:
- If the number in Column 5 is followed by "Cr" (e.g. "433.20 Cr", "1,265.40Cr", "957.60 Cr") → POSITIVE (money in). Remove "Cr" and commas.
- If the number in Column 5 has NO "Cr" suffix (e.g. "1,083.00", "500.00", "360.00") → NEGATIVE (money out). Remove commas.
- Column 6 (Balance) ALSO shows "Cr" on many rows — this is the running balance, not the transaction amount. NEVER use Column 6 for the amount field.
- Numbers that appear INSIDE the Description or Reference text (e.g. "Bis/Int 27 On True Tiering = 241.65", "Send 27829684592") are narrative text, NOT transaction amounts — ignore them completely for the amount field.

DATE RULES:
- Dates appear as "DD Mon" e.g. "01 Dec". Get the statement year from the header at the top of the page (e.g. "Statement Period : 01 December 2024 to 31 December 2024").
- Output format: DD/MM/YYYY e.g. "01/12/2024".

DETAILS RULES:
- Combine Column 2 + Column 3 + Column 4 into one string, separated by " - ", skipping any empty parts.
- Example: Type="Magtape Credit", Desc="ABSA Bank Mc03", Ref="" → "Magtape Credit - ABSA Bank Mc03"
- Example: Type="Internet Pmt To", Desc="Shapiro", Ref="P224" → "Internet Pmt To - Shapiro - P224"

SKIP:
- Opening Balance / Closing Balance rows
- Any header or footer rows
- Rows where the Amount column (Column 5) is empty or "0.00"

Each object must have exactly these keys:
- "date": string DD/MM/YYYY
- "details": string
- "amount": number

Return ONLY the JSON array, nothing else.""",
}

# ─── BANK CONFIG ──────────────────────────────────────────────────────────────

BANK_COLORS = {
    "Capitec":          "#007b5e",
    "Investec":         "#003366",
    "FNB":              "#cc0000",
    "ABSA":             "#cc0000",
    "Nedbank":          "#007b3e",
    "Standard Bank":    "#0033a0",
    "Discovery Invest": "#c8102e",
}

# Banks whose output includes a Reference (Fund Name) column in the CSV
BANKS_WITH_REFERENCE = {"Discovery Invest"}

BANK_LIST = [
    "Capitec", "Investec", "FNB", "ABSA",
    "Nedbank", "Standard Bank", "Discovery Invest",
]

# ─── BANK DETECTION ───────────────────────────────────────────────────────────

BANK_FILENAME_KEYWORDS = {
    "Capitec":          ["capitec"],
    "FNB":              ["fnb", "firstnational", "first_national"],
    "Standard Bank":    ["standardbank", "standard_bank", "stanbic", "stdbank"],
    "ABSA":             ["absa"],
    "Nedbank":          ["nedbank"],
    "Investec":         ["investec"],
    "Discovery Invest": ["discovery_invest", "discoveryinvest", "discovery"],
}

def detect_bank_from_filename(filename: str):
    name_lower = filename.lower().replace(" ", "_")
    for bank, keywords in BANK_FILENAME_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return bank
    return None

# ─── CORE UTILITIES ───────────────────────────────────────────────────────────

def get_client():
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
        if not api_key:
            return None
        return anthropic.Anthropic(api_key=api_key)
    except Exception:
        return None

def check_api_configured():
    try:
        return bool(st.secrets.get("ANTHROPIC_API_KEY", ""))
    except Exception:
        return False

def get_file_hash(file_bytes: bytes) -> str:
    """SHA-256 fingerprint for duplicate-file detection."""
    return hashlib.sha256(file_bytes).hexdigest()

def is_scanned_pdf(pdf_bytes: bytes) -> bool:
    """True if the PDF has no meaningful text layer (i.e. it is an image scan)."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return len(text.strip()) < 100
    except Exception:
        return True  # assume scanned if we cannot read it

def pdf_page_count(pdf_bytes: bytes) -> int:
    """Return the number of pages in a PDF, or 0 on failure."""
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 0

def slice_pdf_bytes(pdf_bytes: bytes, start_page: int, end_page: int) -> bytes:
    """
    Return a new PDF containing only pages start_page..end_page (1-indexed, inclusive).
    Clamps safely to the actual page count.
    """
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total = len(doc)
    s = max(0, min(start_page - 1, total - 1))
    e = max(s, min(total - 1, end_page - 1))
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=s, to_page=e)
    buf = new_doc.tobytes()
    new_doc.close()
    doc.close()
    return buf

def pdf_to_images_b64(pdf_bytes: bytes) -> list:
    """Convert every page of a PDF to a base64-encoded PNG (for vision mode)."""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        images.append(base64.standard_b64encode(png_bytes).decode("utf-8"))
    doc.close()
    return images

# ─── EXTRACTION — VISION MODE ─────────────────────────────────────────────────

def extract_transactions_vision(pdf_bytes, bank, stream_status=None):
    """Send PDF pages as images to Claude vision. Returns (rows, input_tokens, output_tokens)."""
    client = get_client()
    if not client:
        raise ValueError("No API key configured")

    prompt = PROMPTS_VISION.get(bank, PROMPTS[bank])
    images_b64 = pdf_to_images_b64(pdf_bytes)

    content_blocks = []
    for img_b64 in images_b64:
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": img_b64}
        })
    content_blocks.append({"type": "text", "text": prompt})

    raw = ""
    chunk_count = 0
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        messages=[{"role": "user", "content": content_blocks}]
    ) as stream:
        for text in stream.text_stream:
            raw += text
            chunk_count += 1
            if stream_status and chunk_count % 50 == 0:
                stream_status.caption(f"Receiving response (vision) — {chunk_count} chunks so far...")
        final_msg = stream.get_final_message()
        input_tokens  = final_msg.usage.input_tokens
        output_tokens = final_msg.usage.output_tokens

    if stream_status:
        stream_status.caption(
            f"Response complete — {input_tokens} input / {output_tokens} output tokens. Parsing..."
        )
    return _parse_raw_json(raw), input_tokens, output_tokens

# ─── EXTRACTION — TEXT PDF MODE ───────────────────────────────────────────────

def _parse_raw_json(raw: str) -> list:
    """Strip any accidental markdown fencing and parse the JSON array."""
    raw = raw.strip()
    raw = re.sub(r'^```json\s*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'^```\s*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'```\s*$', '', raw)
    start = raw.find('[')
    end   = raw.rfind(']')
    if start == -1 or end == -1:
        raise ValueError("No JSON array found in Claude response")
    return json.loads(raw[start:end + 1])

CHUNK_SIZE = 8  # pages per API call when splitting large PDFs

def split_pdf_bytes(pdf_bytes: bytes, chunk_size: int = CHUNK_SIZE) -> list:
    """Split a PDF into chunks of chunk_size pages. Returns [(page_start, page_end, bytes), ...]."""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    chunks = []
    for start in range(0, total_pages, chunk_size):
        end = min(start + chunk_size, total_pages)
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start, to_page=end - 1)
        buf = new_doc.tobytes()
        new_doc.close()
        chunks.append((start + 1, end, buf))
    doc.close()
    return chunks

def _call_claude_stream(pdf_b64: str, prompt: str, stream_status, chunk_label: str = ""):
    """Stream a single PDF (base64) through Claude. Returns (raw_text, input_tokens, output_tokens)."""
    client = get_client()
    raw = ""
    chunk_count = 0
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}
                },
                {"type": "text", "text": prompt}
            ]
        }]
    ) as stream:
        for text in stream.text_stream:
            raw += text
            chunk_count += 1
            if stream_status and chunk_count % 50 == 0:
                stream_status.caption(f"Receiving{chunk_label} — {chunk_count} chunks so far...")
        final_msg = stream.get_final_message()
        input_tokens  = final_msg.usage.input_tokens
        output_tokens = final_msg.usage.output_tokens
    return raw, input_tokens, output_tokens

def extract_transactions(pdf_bytes: bytes, bank: str, stream_status=None):
    """
    Extract transactions from a text-layer PDF.
    Automatically splits large PDFs into CHUNK_SIZE-page batches.
    Returns (rows, input_tokens, output_tokens).
    """
    client = get_client()
    if not client:
        raise ValueError("No API key configured")
    prompt = PROMPTS[bank]

    import fitz as _fitz
    _doc = _fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(_doc)
    _doc.close()

    if page_count <= CHUNK_SIZE:
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        raw, input_tokens, output_tokens = _call_claude_stream(pdf_b64, prompt, stream_status)
        if stream_status:
            stream_status.caption(
                f"Response complete — {input_tokens} input / {output_tokens} output tokens. Parsing..."
            )
        return _parse_raw_json(raw), input_tokens, output_tokens
    else:
        chunks = split_pdf_bytes(pdf_bytes, CHUNK_SIZE)
        all_rows     = []
        total_input  = 0
        total_output = 0
        for i, (page_start, page_end, chunk_bytes) in enumerate(chunks):
            chunk_label = f" chunk {i + 1}/{len(chunks)} (pages {page_start}–{page_end})"
            if stream_status:
                stream_status.caption(f"Processing{chunk_label}...")
            pdf_b64 = base64.standard_b64encode(chunk_bytes).decode("utf-8")
            raw, inp, out = _call_claude_stream(pdf_b64, prompt, stream_status, chunk_label)
            total_input  += inp
            total_output += out
            try:
                all_rows.extend(_parse_raw_json(raw))
            except Exception as e:
                if stream_status:
                    stream_status.caption(f"⚠ Warning: chunk {i + 1} parse error — {e}")
        if stream_status:
            stream_status.caption(
                f"All {len(chunks)} chunks done — "
                f"{total_input} input / {total_output} output tokens. Merging..."
            )
        return all_rows, total_input, total_output

# ─── ROW PROCESSING ───────────────────────────────────────────────────────────

def normalise_date(date_str: str) -> str:
    """Ensure date is always DD/MM/YYYY."""
    if not date_str:
        return date_str
    date_str = date_str.strip()
    if re.match(r'^\d{2}/\d{2}/\d{4}$', date_str):
        return date_str
    if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_str):
        parts = date_str.split('/')
        return f"{int(parts[0]):02d}/{int(parts[1]):02d}/{parts[2]}"
    if re.match(r'^\d{2}/\d{2}/\d{2}$', date_str):
        parts = date_str.split('/')
        return f"{parts[0]}/{parts[1]}/20{parts[2]}"
    return date_str

def build_rows(raw: list, bank: str) -> list:
    """
    Convert raw JSON objects from Claude into normalised row dicts.
    Every row carries a 'reference' key (empty string for banks that don't use it).
    Capitec fee amounts are split into separate Service Fee rows.
    """
    result = []
    for r in raw:
        date      = normalise_date(r.get('date', ''))
        details   = str(r.get('details', '')).strip()
        amount    = float(r.get('amount', 0) or 0)
        reference = str(r.get('reference', '')).strip()  # populated for Discovery Invest

        if bank == "Capitec":
            fee = float(r.get('fee', 0) or 0)
            result.append({'date': date, 'details': details, 'amount': amount, 'reference': ''})
            if fee != 0:
                result.append({'date': date, 'details': 'Service Fee', 'amount': fee, 'reference': ''})
        else:
            result.append({'date': date, 'details': details, 'amount': amount, 'reference': reference})
    return result

def deduplicate_rows(rows: list) -> list:
    """
    Remove exact duplicate rows (same date + details + amount + reference).
    Uses a set for O(n) performance — safe for large Discovery Invest histories.
    """
    if not rows:
        return rows
    seen   = set()
    result = []
    for r in rows:
        key = (
            r.get("date", ""),
            r.get("details", ""),
            str(r.get("amount", "")),
            r.get("reference", ""),
        )
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result

def rows_to_csv_bytes(rows: list) -> bytes:
    """
    Generate CSV bytes from processed rows.
    Automatically includes the 'Reference' column when any row has a non-empty reference
    (i.e. Discovery Invest rows). Pure bank rows get a 3-column CSV.
    Mixed sessions get a 4-column CSV with blank references for non-Discovery rows.
    """
    has_ref = any(r.get('reference', '') for r in rows)
    output  = io.StringIO()
    writer  = csv.writer(output)

    if has_ref:
        writer.writerow(['Date', 'Details', 'Amount', 'Reference'])
        for row in rows:
            writer.writerow([
                row['date'], row['details'], row['amount'], row.get('reference', '')
            ])
    else:
        writer.writerow(['Date', 'Details', 'Amount'])
        for row in rows:
            writer.writerow([row['date'], row['details'], row['amount']])

    return output.getvalue().encode('utf-8')

def get_month_key(date_str: str) -> str:
    if not date_str:
        return 'Unknown'
    parts = date_str.split('/')
    if len(parts) < 3:
        return 'Unknown'
    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    try:
        return f"{months[int(parts[1]) - 1]}_{parts[2]}"
    except Exception:
        return 'Unknown'

# ─── SESSION STATE ────────────────────────────────────────────────────────────

defaults = {
    'processed_files':      [],
    'all_rows':             [],
    'confirmed_bank':       None,
    'confirmed_files':      [],
    'history':              [],
    'cached_upload_bytes':  {},
    'uploader_key':         0,
    'session_input_tokens': 0,
    'session_output_tokens':0,
    'processed_hashes':     {},   # {sha256_hex: filename_that_was_processed}
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### SA Bank → CSV")
    st.markdown("---")

    st.markdown("**Select Bank**")
    selected_bank = st.selectbox(
        "Bank", BANK_LIST,
        label_visibility="collapsed", key="selected_bank"
    )
    st.markdown("---")

    st.markdown("**Output format**")
    if selected_bank in BANKS_WITH_REFERENCE:
        st.caption("Date · Details · Amount · Reference (Fund Name)")
    else:
        st.caption("Date · Details · Amount")
    st.caption("Signed amount: positive = money in, negative = money out")
    st.markdown("---")

    if selected_bank == "Capitec":
        st.markdown("**Capitec fee rows**")
        st.caption("Fees are automatically split into separate **Service Fee** rows.")
        st.markdown("---")

    if selected_bank == "Discovery Invest":
        st.markdown("**Discovery Invest**")
        st.caption("Columns extracted: Effective date · Description · Amount · Fund Name. Units column is stripped.")
        st.markdown("---")

    st.markdown("**Pastel tip**")
    st.caption("Date + Details + Amount maps directly into Pastel's import format.")
    st.markdown("---")

    if st.session_state.session_input_tokens > 0:
        s_usd, s_zar = calculate_cost(
            st.session_state.session_input_tokens,
            st.session_state.session_output_tokens
        )
        st.markdown("**Session Cost**")
        st.caption(f"${s_usd:.4f} USD")
        st.caption(f"R{s_zar:.4f} ZAR")
        st.caption(f"at R{USD_ZAR_RATE}/$ · Dec 25–Feb 26 avg")
        st.markdown("---")

# ─── HEADER ───────────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">
    <div class="header-title">SA Bank Statement → CSV</div>
    <div class="header-sub">
        Capitec · Investec · FNB · ABSA · Nedbank · Standard Bank · Discovery Invest · Powered by Claude AI
    </div>
</div>
""", unsafe_allow_html=True)

# ─── POPIA NOTICE ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="popia-notice">
    <div class="popia-title">⚖ POPIA / Data Privacy Notice</div>
    <div class="popia-text">
        Statements uploaded here are processed by Claude AI (Anthropic, USA) via encrypted API.
        <strong>No statement data is stored after your browser session ends.</strong>
        Anthropic's API operates under zero data retention — your data is not used for model training.<br>
        <strong>Do not upload client statements without their written consent for cross-border data processing (POPIA s.72).</strong>
        Operators must have a signed data processing agreement with clients before use.
    </div>
</div>
""", unsafe_allow_html=True)

# ─── API CHECK ────────────────────────────────────────────────────────────────

if not check_api_configured():
    st.error(
        "**API key not configured.** "
        "Add `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` or your Streamlit Cloud secrets."
    )
    st.stop()

# ─── STATS BAR ────────────────────────────────────────────────────────────────

if st.session_state.all_rows:
    total      = len(st.session_state.all_rows)
    fee_count  = sum(1 for r in st.session_state.all_rows if r['details'] == 'Service Fee')
    txn_count  = total - fee_count
    files_done = len(st.session_state.processed_files)
    s_usd, s_zar = calculate_cost(
        st.session_state.session_input_tokens,
        st.session_state.session_output_tokens
    )
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{files_done}</div><div class="stat-label">Files Processed</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{txn_count}</div><div class="stat-label">Transactions</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{fee_count}</div><div class="stat-label">Fee Rows</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{total}</div><div class="stat-label">Total Rows</div></div>', unsafe_allow_html=True)
    with col5:
        st.markdown(
            f'<div class="stat-card">'
            f'<div class="stat-number" style="font-size:18px;">R{s_zar:.3f}</div>'
            f'<div class="stat-label">Session Cost</div>'
            f'<div style="font-size:10px;color:#2a4a2a;margin-top:2px;">'
            f'${s_usd:.4f} · R{USD_ZAR_RATE}/$ avg'
            f'</div></div>',
            unsafe_allow_html=True
        )
    st.markdown("")

# ─── UPLOAD ───────────────────────────────────────────────────────────────────

st.markdown(f"#### Upload {selected_bank} Statements")
uploaded_files = st.file_uploader(
    f"Drop {selected_bank} PDF statements here",
    type=["pdf"],
    accept_multiple_files=True,
    label_visibility="collapsed",
    key=f"uploader_{st.session_state.uploader_key}"
)

# Cache bytes immediately so a bank-switch rerun doesn't lose the file content
if uploaded_files:
    for uf in uploaded_files:
        if uf.name not in st.session_state.cached_upload_bytes:
            st.session_state.cached_upload_bytes[uf.name] = uf.read()
    current_names = {uf.name for uf in uploaded_files}
    st.session_state.cached_upload_bytes = {
        k: v for k, v in st.session_state.cached_upload_bytes.items()
        if k in current_names
    }

# ─── STEP 2: EXTRACTION ───────────────────────────────────────────────────────

if st.session_state.confirmed_bank and st.session_state.confirmed_files:
    confirmed_bank   = st.session_state.confirmed_bank
    files_to_process = st.session_state.confirmed_files

    total_files = len(files_to_process)
    est_seconds = total_files * 25
    est_str     = f"{est_seconds // 60}m {est_seconds % 60}s" if est_seconds >= 60 else f"~{est_seconds}s"

    st.markdown(f"#### Extracting {total_files} file{'s' if total_files > 1 else ''} as {confirmed_bank}")
    progress      = st.progress(0)
    status        = st.empty()
    stream_status = st.empty()
    timing        = st.empty()
    start_all     = time.time()

    for i, file_data in enumerate(files_to_process):
        file_start   = time.time()
        elapsed      = time.time() - start_all
        avg_per_file = (elapsed / i) if i > 0 else 25
        est_remaining = int(avg_per_file * (total_files - i))
        est_rem_str  = (
            f"{est_remaining // 60}m {est_remaining % 60}s"
            if est_remaining >= 60 else f"{est_remaining}s"
        )
        eta_label = f"Est. remaining: {est_rem_str}" if i > 0 else f"Est. total: {est_str}"

        status.markdown(f"Processing **{file_data['name']}** ({i + 1}/{total_files})")
        stream_status.caption("Sending PDF to Claude...")
        timing.caption(eta_label)

        try:
            # ── Apply page range if the user trimmed it ───────────────────
            pdf_bytes  = file_data['bytes']
            ps         = file_data.get('page_start', 1)
            pe         = file_data.get('page_end', file_data.get('total_pages', 9999))
            tp         = file_data.get('total_pages', 0) or pdf_page_count(pdf_bytes)
            page_clipped = (ps > 1 or pe < tp)
            if page_clipped:
                pdf_bytes = slice_pdf_bytes(pdf_bytes, ps, pe)
                stream_status.caption(f"Trimmed to pages {ps}–{pe}. Sending to Claude...")

            # ── Scanned vs text-layer routing ────────────────────────────
            scanned = is_scanned_pdf(pdf_bytes)
            if scanned:
                status.markdown(
                    f"Processing **{file_data['name']}** ({i + 1}/{total_files}) "
                    f"— scanned PDF, using vision..."
                )
                stream_status.caption("Converting pages to images...")
                timing.caption(f"{eta_label}  |  Vision mode (~45s per file)")
                try:
                    raw, inp_tok, out_tok = extract_transactions_vision(
                        pdf_bytes, confirmed_bank, stream_status=stream_status
                    )
                    vision_used = True
                except Exception as ve:
                    raise ValueError(f"VISION_FAILED: {ve}")
            else:
                raw, inp_tok, out_tok = extract_transactions(
                    pdf_bytes, confirmed_bank, stream_status=stream_status
                )
                vision_used = False

            # ── Post-process rows ─────────────────────────────────────────
            rows     = build_rows(raw, confirmed_bank)
            rows     = deduplicate_rows(rows)
            fee_rows = sum(1 for r in rows if r['details'] == 'Service Fee')
            txn_rows = len(rows) - fee_rows

            # ── Sanity check: very few rows for a multi-page document ─────
            pages_processed  = (pe - ps + 1) if page_clipped else tp
            sanity_warn      = txn_rows < 5 and pages_processed > 2

            elapsed_file   = int(time.time() - file_start)
            cost_usd, cost_zar = calculate_cost(inp_tok, out_tok)

            st.session_state.session_input_tokens  += inp_tok
            st.session_state.session_output_tokens += out_tok

            # ── Register file hash as processed ──────────────────────────
            file_hash = get_file_hash(file_data['bytes'])
            st.session_state.processed_hashes[file_hash] = file_data['name']

            stream_status.caption(
                f"Done — {txn_rows} transactions in {elapsed_file}s  ·  "
                f"${cost_usd:.4f} / R{cost_zar:.4f}  ·  "
                f"{inp_tok} in / {out_tok} out tokens"
            )

            st.session_state.processed_files.append({
                'name':          file_data['name'],
                'bank':          confirmed_bank,
                'rows':          rows,
                'txn_count':     txn_rows,
                'fee_count':     fee_rows,
                'status':        'done',
                'vision':        vision_used,
                'elapsed':       elapsed_file,
                'input_tokens':  inp_tok,
                'output_tokens': out_tok,
                'cost_usd':      cost_usd,
                'cost_zar':      cost_zar,
                'sanity_warn':   sanity_warn,
                'page_range':    f"{ps}–{pe}" if page_clipped else None,
            })
            st.session_state.all_rows.extend(rows)

        except Exception as e:
            error_msg = str(e)
            stream_status.empty()
            if error_msg.startswith("VISION_FAILED"):
                detail = error_msg.replace("VISION_FAILED: ", "")
                st.error(
                    f"**{file_data['name']}** — vision extraction also failed. "
                    f"Scan quality may be too low.\n\nDetail: {detail}"
                )
            else:
                st.error(f"**{file_data['name']}** — {error_msg}")

            st.session_state.processed_files.append({
                'name':          file_data['name'],
                'bank':          confirmed_bank,
                'rows':          [],
                'status':        'error',
                'error':         error_msg,
                'input_tokens':  0,
                'output_tokens': 0,
                'cost_usd':      0.0,
                'cost_zar':      0.0,
                'sanity_warn':   False,
                'page_range':    None,
            })

        progress.progress((i + 1) / total_files)

    total_elapsed = int(time.time() - start_all)
    elapsed_str   = (
        f"{total_elapsed // 60}m {total_elapsed % 60}s"
        if total_elapsed >= 60 else f"{total_elapsed}s"
    )
    timing.caption(f"Done in {elapsed_str}")

    # ── Save to history (last 3 sessions) ────────────────────────────────
    import copy
    done_files = [f for f in st.session_state.processed_files if f['status'] == 'done']
    if done_files:
        st.session_state.history.insert(0, {
            'timestamp': datetime.now().strftime("%d %b %Y, %H:%M"),
            'bank':  confirmed_bank,
            'files': copy.deepcopy(done_files),
        })
        st.session_state.history = st.session_state.history[:3]

    # ── Reset transient state and rerun ──────────────────────────────────
    st.session_state.confirmed_bank         = None
    st.session_state.confirmed_files        = []
    st.session_state.cached_upload_bytes    = {}
    status.empty()
    stream_status.empty()
    progress.empty()
    st.rerun()

# ─── STEP 1: CONFIRMATION PANEL ───────────────────────────────────────────────

elif uploaded_files:
    already_processed = {f['name'] for f in st.session_state.processed_files}
    new_files = [f for f in uploaded_files if f.name not in already_processed]

    if new_files:
        st.markdown("---")
        st.markdown("#### Confirm before extracting")

        # ── Build per-file info ───────────────────────────────────────────
        file_meta    = []
        any_mismatch = False

        for f in new_files:
            fb = st.session_state.cached_upload_bytes.get(f.name, b'')

            detected = detect_bank_from_filename(f.name)
            if detected and detected != selected_bank:
                icon  = "⚠"
                note  = f"Filename suggests **{detected}** — you have **{selected_bank}** selected"
                any_mismatch = True
            else:
                icon  = "✓"
                note  = f"Will be processed as **{selected_bank}**"

            # Duplicate hash check
            dup_name = None
            if fb:
                h = get_file_hash(fb)
                dup_name = st.session_state.processed_hashes.get(h)

            # Page count
            n_pages = pdf_page_count(fb) if fb else 0
            n_pages = max(n_pages, 1)

            file_meta.append({
                'name':     f.name,
                'icon':     icon,
                'note':     note,
                'dup_name': dup_name,
                'pages':    n_pages,
                'bytes':    fb,
            })

        # ── Render file cards ─────────────────────────────────────────────
        for fm in file_meta:
            dup_html = ""
            if fm['dup_name']:
                dup_html = (
                    '<div style="color:#bf8a4a;font-size:10px;margin-top:3px;">'
                    '⚠ This exact file was already processed this session — '
                    're-processing will create duplicate rows in the combined CSV.'
                    '</div>'
                )
            st.markdown(
                f'<div style="background:#0d0d0d; border:1px solid #1a2a1a; border-radius:6px; '
                f'padding:10px 14px; margin-bottom:6px; display:flex; gap:12px; align-items:flex-start;">'
                f'<span style="font-size:17px;margin-top:2px">{fm["icon"]}</span>'
                f'<div style="flex:1">'
                f'<div style="color:#ffffff;font-size:13px">{fm["name"]}'
                f'<span style="color:#3a5a3a;font-size:10px;margin-left:10px;">{fm["pages"]} page{"s" if fm["pages"] != 1 else ""}</span>'
                f'</div>'
                f'<div style="color:#4a6a4a;font-size:11px;margin-top:2px">{fm["note"]}</div>'
                f'{dup_html}'
                f'</div></div>',
                unsafe_allow_html=True
            )

        if any_mismatch:
            st.warning(
                "One or more files may not match the selected bank. "
                "Processing with the wrong prompt wastes API tokens and gives bad results. "
                "Switch the bank in the sidebar, or confirm below to proceed anyway."
            )

        # ── Page range selector (only shown for large documents) ──────────
        max_pages = max(fm['pages'] for fm in file_meta)
        page_info = {fm['name']: fm['pages'] for fm in file_meta}

        page_start_val = 1
        page_end_val   = max_pages

        if max_pages > 8:
            with st.expander(
                f"📄 Page range — trim large documents "
                f"(largest file: {max_pages} pages, optional)"
            ):
                if len(file_meta) > 1:
                    for fname, n in page_info.items():
                        st.caption(f"{fname}: {n} page{'s' if n != 1 else ''}")
                col_ps, col_pe = st.columns(2)
                with col_ps:
                    page_start_val = st.number_input(
                        "Start page", min_value=1, max_value=max_pages,
                        value=1, step=1, key="page_start_input"
                    )
                with col_pe:
                    page_end_val = st.number_input(
                        "End page", min_value=1, max_value=max_pages,
                        value=max_pages, step=1, key="page_end_input"
                    )
                if page_start_val > page_end_val:
                    st.error("Start page must be ≤ end page.")
                else:
                    pages_in_range = page_end_val - page_start_val + 1
                    if pages_in_range < max_pages:
                        skip_pct = round((1 - pages_in_range / max_pages) * 100)
                        st.caption(
                            f"Will process pages {page_start_val}–{page_end_val} of each file "
                            f"(~{skip_pct}% fewer pages sent to API, lower cost)."
                        )
                    else:
                        st.caption("Full document will be processed (no trimming).")

        # ── Cost and POPIA reminders ──────────────────────────────────────
        st.info(
            "⚠️ **API cost notice:** Once processing begins, Anthropic charges per token processed. "
            "Costs are non-reversible if you close the tab mid-process. "
            "Estimated cost: ~$0.01–$0.05 per file depending on statement length."
        )

        st.markdown("")
        col_confirm, col_cancel = st.columns(2)

        with col_confirm:
            confirm_disabled = (page_start_val > page_end_val)
            if st.button(
                f"Confirm — process as {selected_bank}",
                use_container_width=True,
                disabled=confirm_disabled
            ):
                confirmed_file_list = []
                for fm in file_meta:
                    tp = fm['pages']
                    confirmed_file_list.append({
                        'name':        fm['name'],
                        'bytes':       fm['bytes'],
                        'page_start':  page_start_val,
                        'page_end':    min(page_end_val, tp),
                        'total_pages': tp,
                    })
                st.session_state.confirmed_bank  = selected_bank
                st.session_state.confirmed_files = confirmed_file_list
                st.rerun()

        with col_cancel:
            if st.button("✗ Cancel", use_container_width=True):
                st.session_state.confirmed_bank      = None
                st.session_state.confirmed_files     = []
                st.session_state.cached_upload_bytes = {}
                st.session_state.uploader_key       += 1
                st.rerun()

# ─── TABS ─────────────────────────────────────────────────────────────────────

tab_results, tab_history = st.tabs(["Results", "History"])

# ── Results tab ───────────────────────────────────────────────────────────────
with tab_results:
    if st.session_state.processed_files:
        col_hdr, col_clr = st.columns([4, 1])
        with col_hdr:
            st.markdown("#### Processed Files")
        with col_clr:
            if st.button("Clear files", use_container_width=True):
                st.session_state.processed_files       = []
                st.session_state.all_rows              = []
                st.session_state.session_input_tokens  = 0
                st.session_state.session_output_tokens = 0
                st.rerun()

        for idx, f in enumerate(st.session_state.processed_files):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                bank_label = f.get('bank', '')
                if f['status'] == 'done':
                    fee_info    = f" + {f['fee_count']} fee rows" if f['fee_count'] > 0 else ""
                    vision_tag  = " [vision]"   if f.get('vision')      else ""
                    page_tag    = f" [pp. {f['page_range']}]" if f.get('page_range') else ""
                    elapsed_tag = f" — {f['elapsed']}s"       if f.get('elapsed')    else ""
                    cost_tag    = (
                        f"  ·  ${f.get('cost_usd', 0):.4f} / R{f.get('cost_zar', 0):.4f}"
                        if f.get('cost_usd') else ""
                    )
                    st.success(
                        f"**{f['name']}** [{bank_label}]{vision_tag}{page_tag} — "
                        f"{f['txn_count']} transactions{fee_info} = {len(f['rows'])} total"
                        f"{elapsed_tag}{cost_tag}"
                    )
                    if f.get('sanity_warn'):
                        st.warning(
                            f"⚠ Only {f['txn_count']} rows extracted from a "
                            f"{f.get('total_pages', '?')}-page document. "
                            "This may mean the bank selection is wrong, the PDF is image-only "
                            "(try vision mode by selecting a scanned statement), "
                            "or the statement format has changed. "
                            "**Verify the downloaded CSV before importing.**"
                        )
                else:
                    st.error(f"**{f['name']}** [{bank_label}] — {f.get('error', 'Unknown error')}")
            with col_b:
                if f['status'] == 'done':
                    csv_bytes = rows_to_csv_bytes(f['rows'])
                    st.download_button(
                        "Download CSV",
                        data=csv_bytes,
                        file_name=f['name'].replace('.pdf', '.csv'),
                        mime='text/csv',
                        key=f"dl_{idx}_{f['name']}"
                    )

        if st.session_state.all_rows:
            # ── Session cost summary ───────────────────────────────────────
            if st.session_state.session_input_tokens > 0:
                s_usd, s_zar = calculate_cost(
                    st.session_state.session_input_tokens,
                    st.session_state.session_output_tokens
                )
                st.markdown(
                    f'<div class="cost-card">'
                    f'<div class="cost-label">Session API Cost</div>'
                    f'<div class="cost-value">${s_usd:.4f} USD &nbsp;·&nbsp; R{s_zar:.4f} ZAR</div>'
                    f'<div class="cost-note">'
                    f'{st.session_state.session_input_tokens:,} input tokens · '
                    f'{st.session_state.session_output_tokens:,} output tokens · '
                    f'at R{USD_ZAR_RATE}/$ (Dec 2025–Feb 2026 avg)'
                    f'</div></div>',
                    unsafe_allow_html=True
                )

            # ── Download section ───────────────────────────────────────────
            st.markdown("---")
            st.markdown("#### Download")
            col1, col2 = st.columns(2)
            with col1:
                all_csv = rows_to_csv_bytes(st.session_state.all_rows)
                st.download_button(
                    "Download All Combined",
                    data=all_csv,
                    file_name="sa_bank_all_transactions.csv",
                    mime='text/csv',
                    use_container_width=True
                )
            with col2:
                by_month = {}
                for row in st.session_state.all_rows:
                    m = get_month_key(row['date'])
                    by_month.setdefault(m, []).append(row)
                month_options  = sorted(by_month.keys())
                selected_month = st.selectbox(
                    "Download specific month:", ['All months'] + month_options
                )
                if selected_month != 'All months':
                    month_csv = rows_to_csv_bytes(by_month[selected_month])
                    st.download_button(
                        f"Download {selected_month}",
                        data=month_csv,
                        file_name=f"sa_bank_{selected_month}.csv",
                        mime='text/csv',
                        use_container_width=True
                    )

            # ── Preview table ──────────────────────────────────────────────
            st.markdown("---")
            st.markdown("#### Preview")
            preview_rows = st.session_state.all_rows[:50]
            has_ref      = any(r.get('reference', '') for r in preview_rows)
            table_data   = []
            for r in preview_rows:
                amt = r['amount']
                row_dict = {
                    'Date':    r['date'],
                    'Details': r['details'],
                    'Amount':  f"+{amt}" if isinstance(amt, (int, float)) and amt > 0 else str(amt),
                }
                if has_ref:
                    row_dict['Reference'] = r.get('reference', '')
                table_data.append(row_dict)
            if table_data:
                st.dataframe(table_data, use_container_width=True, height=400)
                if len(st.session_state.all_rows) > 50:
                    st.caption(
                        f"Showing first 50 of {len(st.session_state.all_rows)} rows. "
                        "Download CSV for the full set."
                    )

    elif not uploaded_files and not st.session_state.confirmed_files:
        banks_str = " · ".join(BANK_LIST)
        st.markdown(
            f'<div style="text-align:center; padding:60px 40px; color:#2a2a2a; '
            f'border:2px dashed #1a1a1a; border-radius:12px; margin-top:20px;">'
            f'<div style="font-size:16px;color:#444;margin-bottom:8px;margin-top:8px;">'
            f'Select your bank in the sidebar, then upload PDF statements</div>'
            f'<div style="font-size:12px;color:#333;">{banks_str}</div>'
            f'<div style="font-size:12px;margin-top:8px;">'
            f'Output: Date · Details · Amount (signed) · Pastel-ready</div>'
            f'</div>',
            unsafe_allow_html=True
        )

# ── History tab ───────────────────────────────────────────────────────────────
with tab_history:
    if not st.session_state.history:
        st.markdown(
            '<div style="text-align:center; padding:60px 40px; color:#2a2a2a; '
            'border:2px dashed #1a1a1a; border-radius:12px; margin-top:20px;">'
            '<div style="font-size:16px;color:#444;margin-bottom:8px;margin-top:8px;">'
            'No history yet — completed sessions will appear here</div>'
            '<div style="font-size:12px;color:#333;">Last 3 sessions are saved automatically</div>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        for hi, entry in enumerate(st.session_state.history):
            n_files = len(entry['files'])
            st.markdown(
                f"**{entry['timestamp']}** — {entry['bank']} — "
                f"{n_files} file{'s' if n_files > 1 else ''}"
            )
            for fi, f in enumerate(entry['files']):
                fee_info = (
                    f" + {f.get('fee_count', 0)} fee rows"
                    if f.get('fee_count', 0) > 0 else ""
                )
                cost_tag = (
                    f"  ·  ${f.get('cost_usd', 0):.4f} / R{f.get('cost_zar', 0):.4f}"
                    if f.get('cost_usd') else ""
                )
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(
                        f"&nbsp;&nbsp;&nbsp;{f['name']} — "
                        f"{f['txn_count']} transactions{fee_info}{cost_tag}"
                    )
                with col_b:
                    hist_csv = rows_to_csv_bytes(f['rows'])
                    st.download_button(
                        "Download CSV",
                        data=hist_csv,
                        file_name=f['name'].replace('.pdf', '.csv'),
                        mime='text/csv',
                        key=f"hist_{hi}_{fi}_{f['name']}"
                    )

            if n_files > 1:
                all_session_rows = []
                for f in entry['files']:
                    all_session_rows.extend(f['rows'])
                session_csv = rows_to_csv_bytes(all_session_rows)
                ts_safe = (
                    entry['timestamp']
                    .replace(', ', '_').replace(' ', '_').replace(':', '')
                )
                st.download_button(
                    "Download all from this session",
                    data=session_csv,
                    file_name=f"session_{ts_safe}.csv",
                    mime='text/csv',
                    key=f"hist_all_{hi}"
                )
            st.markdown("---")
