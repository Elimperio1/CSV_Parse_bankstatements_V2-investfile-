import streamlit as st
import anthropic
import base64
import hashlib
import json, csv, io, re, time
from datetime import datetime

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
    background: #a3c4c9 !important;
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

"Discovery Invest - Payments": """You are a bank statement parser. Your ONLY output must be a valid JSON array. No explanation, no markdown, no code fences, no preamble, no postamble — just the raw JSON array starting with [ and ending with ].

TASK: Extract every row from the Payment Summary table in this Discovery Invest statement.

THE TABLE HAS EXACTLY THESE COLUMNS (in order):
  Date | Description | Gross amount | Interest | Net payment

CRITICAL: You must ONLY extract from the "Payment Summary" table. Ignore any other tables on the same pages (e.g. Transaction details, Capital Gains, Portfolio summary).

Each object must have exactly these keys:
- "date": string DD/MM/YYYY — the Date column is already in DD/MM/YYYY format. Output as-is.
- "details": string — the Description column value, verbatim.
- "amount": number — use ONLY the Net payment column. Strip the leading "R", remove all spaces and commas.
  ALL amounts must be output as NEGATIVE numbers because these are withdrawals leaving the account.
  Examples:
    "R10 000.00" → -10000.00
    "R1 234.56"  → -1234.56
    "R0.00"      → skip this row (zero payment, see below)

AMOUNT RULES:
- Net payment values are always positive in the table (e.g. "R10 000.00") — output them ALL as NEGATIVE.
- Ignore the Gross amount column entirely.
- Ignore the Interest column entirely.

SKIP THESE ROWS ENTIRELY:
- The column header row (Date / Description / Gross amount / etc.)
- The "Payment summary as at..." header line
- Any row where Net payment is "R0.00", blank, or missing
- Any totals, subtotals, or summary rows at the bottom of the table
- Any page header or footer lines

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
    "Capitec":                     "#007b5e",
    "Investec":                    "#003366",
    "FNB":                         "#cc0000",
    "ABSA":                        "#cc0000",
    "Nedbank":                     "#007b3e",
    "Standard Bank":               "#0033a0",
    "Discovery Invest":            "#c8102e",
    "Discovery Invest - Payments": "#c8102e",
}

# Discovery banks that support section-type selection in the confirmation panel
DISCOVERY_BANKS = {"Discovery Invest"}

# Banks that always produce digital text-layer PDFs — never route to vision mode
FORCE_TEXT_MODE = {"Discovery Invest", "Discovery Invest - Payments"}

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
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
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
            break  # success — exit retry loop

        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "rate_limit" in err_str
            if is_rate_limit and attempt < max_retries:
                wait_secs = 65
                for remaining in range(wait_secs, 0, -1):
                    if stream_status:
                        stream_status.caption(
                            f"Rate limit hit (vision) — retrying in {remaining}s "
                            f"(attempt {attempt}/{max_retries})..."
                        )
                    time.sleep(1)
            else:
                raise

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
        preview = raw.strip()[:400] if raw.strip() else "(empty response)"
        raise ValueError(f"No JSON array found in Claude response. First 400 chars: {preview}")
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
    """Stream a single PDF (base64) through Claude. Returns (raw_text, input_tokens, output_tokens).
    Automatically retries up to 3 times on rate limit (429) errors with a 60s wait."""
    client = get_client()
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
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

        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "rate_limit" in err_str
            if is_rate_limit and attempt < max_retries:
                wait_secs = 65
                for remaining in range(wait_secs, 0, -1):
                    if stream_status:
                        stream_status.caption(
                            f"Rate limit hit{chunk_label} — retrying in {remaining}s "
                            f"(attempt {attempt}/{max_retries})..."
                        )
                    time.sleep(1)
            else:
                raise

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
        reference = str(r.get('reference', '')).strip()
        if reference:
            details = f"{details} / {reference}"

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
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Details', 'Amount'])
    for row in rows:
        writer.writerow([row['date'], row['details'], row['amount']])
    return output.getvalue().encode('utf-8')

def build_csv_filename(bank: str, section_label: str, rows: list) -> str:
    """
    Build a descriptive CSV filename from bank name, section type, and the
    date range of the extracted rows.
    e.g. Discovery_Invest_Transactions_15Sep2025_to_03Oct2025.csv
    """
    # Parse dates from rows
    parsed_dates = []
    for r in rows:
        d = r.get('date', '')
        if d:
            try:
                parts = d.split('/')
                parsed_dates.append(datetime(int(parts[2]), int(parts[1]), int(parts[0])))
            except Exception:
                pass

    if parsed_dates:
        min_d = min(parsed_dates).strftime("%d%b%Y")
        max_d = max(parsed_dates).strftime("%d%b%Y")
        date_range = f"{min_d}_to_{max_d}"
    else:
        date_range = "unknown_dates"

    # Sanitise bank name for use in a filename
    bank_safe    = bank.replace(" - Payments", "").replace(" ", "_")
    section_safe = section_label.replace(" ", "_") if section_label else ""

    if section_safe:
        return f"{bank_safe}_{section_safe}_{date_range}.csv"
    return f"{bank_safe}_{date_range}.csv"

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
    'processed_files':       [],
    'all_rows':              [],
    'confirmed_bank':        None,
    'confirmed_files':       [],
    'history':               [],
    'cached_upload_bytes':   {},
    'uploader_key':          0,
    'session_input_tokens':  0,
    'session_output_tokens': 0,
    'processed_hashes':      {},   # {sha256_hex: filename_that_was_processed}
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### El Imperio")
    st.markdown("#### CSV Parser")
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
        st.caption("Transaction Details: Date · Description · Amount · Fund Name. Units column stripped.")
        st.caption("Payment Summary: Date · Description · Net Payment (as negative withdrawal).")
        st.caption("Select the section type in the confirmation panel before processing.")
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

LOGO_B64 = "/9j/4AAQSkZJRgABAQEAYABgAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlBFRyB2ODApLCBxdWFsaXR5ID0gODIK/9sAQwAGBAQFBAQGBQUFBgYGBwkOCQkICAkSDQ0KDhUSFhYVEhQUFxohHBcYHxkUFB0nHR8iIyUlJRYcKSwoJCshJCUk/9sAQwEGBgYJCAkRCQkRJBgUGCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQk/8AAEQgBKQQAAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVEHYXETIjKBCBRCkaGxwQkjM1LwFWJy0QoWJDThJfEXGBkaJicoKSo1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uLj5OXm5+jp6vLz9PX29/j5+v/aAAwDAQACEQMRAD8A+qaKKKACiiigAooooAKKKKACiiigAoopDQAtZPiPX4PD2nPdyje5+WNB1Zq5/X/iRBpd7JZ2luLlojtkctgA+lc14v8AEkXifS7WaJWjeFyJYj2JHB+lAHaeD/GKeJUkimRYbuP5iq9GX1FdPmvFvBeox6PqkmoTsRDDEdwHVieAo/z2rp7b4rRtdhbixMduTjeGyVHrigD0Kio4JkuIkljbcjqGUjuDUlABRRmigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAQ1Vv9Ts9Kga4vrmG2hXq8rhQPzqtrviXSfDUMc+sahb2MMjbEknbapbGcZ6dAa+Q/jt8QLbx94oPl64y6LagJaQQqXD/3pWHQEnpnnAHSt8Ph5VZW6GVWpyI+nNR+MXgfTFiebX7VopH8sSREuitnGGI6fjXWwXcV1Ck8DpJDIodHU5Vge4NfnYN+i5kilS9sLyN4jwQr+zKejKcMPcA19P8A7Lvia78R/D3VfD00zPNpjGKB2JJWORTtH4EN+GK6MRglThzRZFKtzOzPR9L/ALF8Q6neWlrpMD2seTLct1dye361yHiTQB4c1eS3DZs7mJmjLdsDOPqCKueCfEaeGpLuzvYXGX3MB95SOD9celR+OvEdv4hEDW0bCKNmVGcYZuOePTkVwHQYum2D6rJZ6fbsPMuJCX9u38hXoOqaRpXhLS4pDpMV5ACEnkb/AFgz/FXC+EdTTR9XW7aMyBEPHfHfHvjNdP4u8c2WqaJLZ2aORcALucbcYOeB+FAHdaTPaz6dby2RBtig8vHYelc7P8V/B9trk2iS61At5ACZhzsix2ZugPtmub1zXbvwF8Gb/U8mO6ETeRngqznC/TGa+NYLq81aJdORgDJK080rMfnOM7mPtzXbhcJ7VOTehz1a3I7I/QnR/E2jeIEL6TqdpeqOvkyhsflWmDX5/wDgrXD4O8SWeqaPrhW4gkUsjoY47he6En1HQnjp0r7Z8KfEXw34yjgXSNUtri4ki81rdGy8Y77h2weKjEYWVHVaoqnV5jqKKKK5TYKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKAC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"

st.markdown(f"""
<div class="eli-header">
    <div class="eli-logo">
        <img src="data:image/jpeg;base64,{LOGO_B64}" alt="El Imperio Logo" />
    </div>
    <div class="eli-divider"></div>
    <div class="eli-title-block">
        <div class="eli-title">CSV Parser</div>
        <div class="eli-subtitle">Bank Statement Extractor · Powered by Claude AI</div>
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
            # Use effective_bank (may differ from confirmed_bank for Discovery sections)
            effective_bank = file_data.get('effective_bank', confirmed_bank)
            section_label  = file_data.get('section_label', '')

            # Discovery Invest PDFs are always digital — skip scanned detection
            scanned = False if effective_bank in FORCE_TEXT_MODE else is_scanned_pdf(pdf_bytes)
            if scanned:
                status.markdown(
                    f"Processing **{file_data['name']}** ({i + 1}/{total_files}) "
                    f"— scanned PDF, using vision..."
                )
                stream_status.caption("Converting pages to images...")
                timing.caption(f"{eta_label}  |  Vision mode (~45s per file)")
                try:
                    raw, inp_tok, out_tok = extract_transactions_vision(
                        pdf_bytes, effective_bank, stream_status=stream_status
                    )
                    vision_used = True
                except Exception as ve:
                    raise ValueError(f"VISION_FAILED: {ve}")
            else:
                raw, inp_tok, out_tok = extract_transactions(
                    pdf_bytes, effective_bank, stream_status=stream_status
                )
                vision_used = False

            # ── Post-process rows ─────────────────────────────────────────
            rows     = build_rows(raw, effective_bank)
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

            # ── Build descriptive CSV filename ────────────────────────────
            csv_filename = build_csv_filename(effective_bank, section_label, rows)

            stream_status.caption(
                f"Done — {txn_rows} transactions in {elapsed_file}s  ·  "
                f"${cost_usd:.4f} / R{cost_zar:.4f}  ·  "
                f"{inp_tok} in / {out_tok} out tokens"
            )

            st.session_state.processed_files.append({
                'name':           file_data['name'],
                'bank':           confirmed_bank,
                'effective_bank': effective_bank,
                'section_label':  section_label,
                'csv_filename':   csv_filename,
                'rows':           rows,
                'txn_count':      txn_rows,
                'fee_count':      fee_rows,
                'status':         'done',
                'vision':         vision_used,
                'elapsed':        elapsed_file,
                'input_tokens':   inp_tok,
                'output_tokens':  out_tok,
                'cost_usd':       cost_usd,
                'cost_zar':       cost_zar,
                'sanity_warn':    sanity_warn,
                'page_range':     f"{ps}–{pe}" if page_clipped else None,
                'total_pages':    tp,
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
                'name':           file_data['name'],
                'bank':           confirmed_bank,
                'effective_bank': file_data.get('effective_bank', confirmed_bank),
                'section_label':  file_data.get('section_label', ''),
                'csv_filename':   file_data['name'].replace('.pdf', '_error.csv'),
                'rows':           [],
                'status':         'error',
                'error':          error_msg,
                'input_tokens':   0,
                'output_tokens':  0,
                'cost_usd':       0.0,
                'cost_zar':       0.0,
                'sanity_warn':    False,
                'page_range':     None,
                'total_pages':    file_data.get('total_pages', 0),
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

        # ── Section type selector — Discovery Invest only ─────────────────
        section_label = ""
        effective_bank = selected_bank  # prompt key actually used

        if selected_bank in DISCOVERY_BANKS:
            st.markdown("**Which section of the PDF are you processing?**")
            section_choice = st.radio(
                "Section type",
                options=["Transaction Details", "Payment Summary"],
                index=0,
                horizontal=True,
                key="section_type_radio",
                label_visibility="collapsed",
                help=(
                    "Transaction Details → Effective date · Description · Amount · Fund Name  |  "
                    "Payment Summary → Date · Description · Net Payment (negative withdrawals)"
                )
            )
            section_label  = section_choice.replace(" ", "_")
            effective_bank = (
                "Discovery Invest - Payments"
                if section_choice == "Payment Summary"
                else "Discovery Invest"
            )
            if section_choice == "Payment Summary":
                st.caption(
                    "Net payment amounts will be saved as **negative** values "
                    "(withdrawals leaving the account). No Fund Name column."
                )
            else:
                st.caption(
                    "Transaction amounts use the sign in the statement. "
                    "Fund Name saved in the **Reference** column."
                )
            st.markdown("")


        max_pages = max(fm['pages'] for fm in file_meta)
        page_info = {fm['name']: fm['pages'] for fm in file_meta}

        # Discovery Invest: page range MANDATORY — blank defaults, confirm locked.
        # All other banks: optional expander, defaults to full document.
        discovery_mode = selected_bank in DISCOVERY_BANKS
        range_ready    = False  # will be set to True when conditions are met

        if discovery_mode:
            st.markdown("**Page range — required for Discovery Invest**")
            st.caption(
                f"This document has **{max_pages} pages**. "
                "Enter a start and end page before processing to avoid sending "
                "the entire document to the API (which causes a request-too-large error)."
            )
            col_ps, col_pe = st.columns(2)
            with col_ps:
                page_start_raw = st.number_input(
                    "Start page", min_value=1, max_value=max_pages,
                    value=None, step=1, key="page_start_input",
                    placeholder="e.g. 10"
                )
            with col_pe:
                page_end_raw = st.number_input(
                    "End page", min_value=1, max_value=max_pages,
                    value=None, step=1, key="page_end_input",
                    placeholder="e.g. 25"
                )

            page_start_val = int(page_start_raw) if page_start_raw is not None else None
            page_end_val   = int(page_end_raw)   if page_end_raw   is not None else None

            if page_start_val is None or page_end_val is None:
                st.warning("⚠ Enter both a start and end page to enable the Confirm button.")
                range_ready = False
            elif page_start_val > page_end_val:
                st.error("Start page must be ≤ end page.")
                range_ready = False
            else:
                pages_in_range = page_end_val - page_start_val + 1
                skip_pct = round((1 - pages_in_range / max_pages) * 100)
                st.caption(
                    f"Will process pages {page_start_val}–{page_end_val} "
                    f"({pages_in_range} page{'s' if pages_in_range != 1 else ''}, "
                    f"~{skip_pct}% of document)."
                )
                range_ready = True

        else:
            page_start_val = 1
            page_end_val   = max_pages
            range_ready    = True

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
                        range_ready = False
                    else:
                        pages_in_range = page_end_val - page_start_val + 1
                        if pages_in_range < max_pages:
                            skip_pct = round((1 - pages_in_range / max_pages) * 100)
                            st.caption(
                                f"Will process pages {page_start_val}–{page_end_val} "
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
            confirm_disabled = not range_ready
            if st.button(
                f"Confirm — process as {selected_bank}",
                use_container_width=True,
                disabled=confirm_disabled
            ):
                confirmed_file_list = []
                for fm in file_meta:
                    tp = fm['pages']
                    confirmed_file_list.append({
                        'name':          fm['name'],
                        'bytes':         fm['bytes'],
                        'page_start':    page_start_val,
                        'page_end':      min(page_end_val, tp),
                        'total_pages':   tp,
                        'effective_bank':effective_bank,
                        'section_label': section_label,
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
                    section_tag = (
                        f" [{f['section_label'].replace('_', ' ')}]"
                        if f.get('section_label') else ""
                    )
                    st.success(
                        f"**{f['name']}** [{bank_label}]{section_tag}{vision_tag}{page_tag} — "
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
                    dl_fname  = f.get('csv_filename') or f['name'].replace('.pdf', '.csv')
                    st.download_button(
                        "Download CSV",
                        data=csv_bytes,
                        file_name=dl_fname,
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
            table_data   = []
            for r in preview_rows:
                amt = r['amount']
                table_data.append({
                    'Date':    r['date'],
                    'Details': r['details'],
                    'Amount':  f"+{amt}" if isinstance(amt, (int, float)) and amt > 0 else str(amt),
                })
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
            f'Output: Date · Details · Amount (signed) · Pastel-ready  ·  El Imperio Accountants</div>'
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
                    hist_csv  = rows_to_csv_bytes(f['rows'])
                    hist_fname = f.get('csv_filename') or f['name'].replace('.pdf', '.csv')
                    st.download_button(
                        "Download CSV",
                        data=hist_csv,
                        file_name=hist_fname,
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
