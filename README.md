# SA Bank Statement → CSV

Extracts transactions from South African bank statement PDFs and exports them as
clean, signed-amount CSVs ready for Pastel or any accounting import.

Powered by **Claude AI (Anthropic)** via the Anthropic API.

---

## Supported Banks

| Bank | Notes |
|---|---|
| Capitec | Fee rows split into separate Service Fee lines |
| Investec | Main transaction table only; summary tables ignored |
| FNB | Text PDF and scanned (vision) modes |
| ABSA | Per-page repeat summary box automatically excluded |
| Nedbank | Debit/Credit column sign handling |
| Standard Bank | MM DD date format normalised automatically |
| Discovery Invest | Extracts Date · Description · Amount · Fund Name; Units column stripped |

---

## Output Format

**Standard banks:** `Date, Details, Amount`

**Discovery Invest:** `Date, Details, Amount, Reference` (Reference = Fund Name)

- Date: `DD/MM/YYYY`
- Amount: signed float — negative = money out, positive = money in
- Pastel-ready on import

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/sa-bank-csv.git
cd sa-bank-csv
pip install -r requirements.txt
```

### 2. Add your Anthropic API key

```bash
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml and paste your key
```

`.streamlit/secrets.toml`:
```toml
ANTHROPIC_API_KEY = "sk-ant-api03-..."
```

**Never commit `secrets.toml` to Git.** It is already in `.gitignore`.

### 3. Run

```bash
streamlit run app.py
```

---

## Deploying to Streamlit Cloud

1. Push the repo to GitHub (without `secrets.toml`).
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → select your repo.
3. Under **Advanced settings → Secrets**, paste:
   ```
   ANTHROPIC_API_KEY = "sk-ant-api03-..."
   ```
4. Deploy.

---

## Features

- **Multi-bank support** — one dropdown, one workflow
- **Scanned PDF detection** — automatically switches to vision (image) mode if no text layer found
- **Large PDF chunking** — statements over 8 pages are split and merged automatically
- **Page range selector** — trim large Discovery Invest histories to a specific page range before sending (reduces API cost)
- **Hash-based duplicate detection** — warns if the same file is uploaded again in the same session
- **Sanity warning** — alerts if very few rows were extracted relative to document size
- **Month-by-month download** — download a specific month's transactions without re-processing
- **Session cost tracking** — USD and ZAR cost shown per file and for the full session
- **History tab** — last 3 processing sessions saved for re-download during the browser session

---

## POPIA Compliance Notes

This application processes personal financial information. The following applies:

- **Cross-border transfer (s.72):** Statement content is sent to Anthropic's API servers in the USA. This constitutes a cross-border transfer of personal information under POPIA.
- **Operator responsibility:** If you process statements on behalf of clients, you must obtain written consent for this cross-border transfer before uploading any statement.
- **Data processing agreement:** Anthropic offers a DPA for API customers. Operators should sign this before use with client data.
- **No server-side storage:** This app holds data only in browser session state. All data is lost when the tab is closed. Do not add external logging or analytics that capture statement content.
- **Zero data retention:** Anthropic's API does not use your inputs for model training under zero-data-retention configuration. Confirm your API tier includes this before use with sensitive data.

This notice does not constitute legal advice. Consult a POPIA-qualified attorney for operator-specific compliance requirements.

---

## API Cost Estimates

Based on `claude-sonnet-4-6` pricing (as at March 2026):

| Statement type | Approx. cost (USD) |
|---|---|
| Single-month bank statement (2–4 pages) | $0.01–$0.02 |
| Multi-month statement (10–20 pages) | $0.03–$0.08 |
| Discovery Invest full history (50+ pages) | $0.15–$0.40 |

Scanned PDFs (vision mode) cost approximately 2–3× more than text PDFs.

Exchange rate used in-app: R16.59/$ (Dec 2025–Feb 2026 average). Update `USD_ZAR_RATE` in `app.py` periodically.

---

## Adding a New Bank

1. Add the bank name to `BANK_LIST`.
2. Add a prompt to `PROMPTS` — follow the same JSON-array-only contract.
3. Add filename detection keywords to `BANK_FILENAME_KEYWORDS`.
4. Add a colour to `BANK_COLORS`.
5. If the bank output needs a Reference column, add it to `BANKS_WITH_REFERENCE`.
6. Test against a real statement before deploying.
