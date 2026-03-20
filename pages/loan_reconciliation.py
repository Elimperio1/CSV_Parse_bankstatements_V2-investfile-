import streamlit as st
import pandas as pd
from io import BytesIO

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Loan Reconciliation",
    page_icon="🔄",
    layout="wide",
)

st.title("🔄 Intercompany Loan Reconciliation")
st.caption("Upload one loan ledger per company. Matching is done on amount (exact) and date (±3 days).")

# ─────────────────────────────────────────────
#  FORMAT CONFIGS
# ─────────────────────────────────────────────
FORMATS = {
    "Sage":   {"date_col": "Account Date"},
    "Pastel": {"date_col": "Date"},
}

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def load_and_normalise(uploaded_file, fmt: str, company_label: str) -> pd.DataFrame | None:
    """
    Load a Sage or Pastel CSV and return a clean DataFrame with columns:
        date | description | debit | credit
    Skips header/metadata rows by filtering on rows that contain a valid DD/MM/YYYY date.
    """
    try:
        df = pd.read_csv(uploaded_file, dtype=str)
    except Exception as e:
        st.error(f"{company_label}: Could not read CSV — {e}")
        return None

    date_col = FORMATS[fmt]["date_col"]

    if date_col not in df.columns:
        st.error(
            f"{company_label}: Expected column **'{date_col}'** not found. "
            f"Available columns: {list(df.columns)}"
        )
        return None

    # Keep only rows that look like real transaction dates (DD/MM/YYYY)
    mask = df[date_col].str.strip().str.match(r"^\d{2}/\d{2}/\d{4}$", na=False)
    df = df[mask].copy()

    if df.empty:
        st.error(f"{company_label}: No valid transaction rows found after filtering.")
        return None

    df["date"]        = pd.to_datetime(df[date_col].str.strip(), format="%d/%m/%Y")
    df["description"] = df["Description"].fillna("").astype(str).str.strip()
    df["debit"]       = pd.to_numeric(df["Debit"].str.replace(",", ""), errors="coerce").fillna(0)
    df["credit"]      = pd.to_numeric(df["Credit"].str.replace(",", ""), errors="coerce").fillna(0)

    return df[["date", "description", "debit", "credit"]].reset_index(drop=True)


def reconcile(df_a: pd.DataFrame, df_b: pd.DataFrame, tolerance: int = 3):
    """
    Two-pass matching:
      Pass 1 — exact date + exact amount  → Confirmed match
      Pass 2 — ±tolerance days + exact amount → Uncertain match

    A Debit in A  ↔  Credit in B  (same amount)
    A Credit in A ↔  Debit in B   (same amount)

    Returns:
        confirmed  : list of match-dicts
        uncertain  : list of match-dicts
        unmatched_a: DataFrame of unmatched rows from A
        unmatched_b: DataFrame of unmatched rows from B
    """
    a = df_a.copy()
    b = df_b.copy()
    a["_used"] = False
    b["_used"] = False

    confirmed = []
    uncertain = []

    for pass_num in range(2):
        for i, ra in a.iterrows():
            if a.at[i, "_used"]:
                continue

            # What are we looking for in B?
            if ra["debit"] > 0:
                amount   = ra["debit"]
                b_amount_col = "credit"
            elif ra["credit"] > 0:
                amount   = ra["credit"]
                b_amount_col = "debit"
            else:
                continue  # zero row, skip

            candidates = []
            for j, rb in b.iterrows():
                if b.at[j, "_used"]:
                    continue
                if abs(rb[b_amount_col] - amount) < 0.005:
                    day_diff = abs((ra["date"] - rb["date"]).days)
                    if pass_num == 0 and day_diff == 0:
                        candidates.append((j, day_diff))
                    elif pass_num == 1 and 0 < day_diff <= tolerance:
                        candidates.append((j, day_diff))

            if candidates:
                # Prefer closest date; stable sort keeps first occurrence on ties
                candidates.sort(key=lambda x: x[1])
                j, day_diff = candidates[0]

                a.at[i, "_used"] = True
                b.at[j, "_used"] = True

                record = {
                    "amount":        amount,
                    "a_date":        ra["date"],
                    "a_description": ra["description"],
                    "a_debit":       ra["debit"],
                    "a_credit":      ra["credit"],
                    "b_date":        b.at[j, "date"],
                    "b_description": b.at[j, "description"],
                    "b_debit":       b.at[j, "debit"],
                    "b_credit":      b.at[j, "credit"],
                    "day_diff":      day_diff,
                }
                if pass_num == 0:
                    confirmed.append(record)
                else:
                    uncertain.append(record)

    unmatched_a = a[~a["_used"]].drop(columns=["_used"]).reset_index(drop=True)
    unmatched_b = b[~b["_used"]].drop(columns=["_used"]).reset_index(drop=True)

    return confirmed, uncertain, unmatched_a, unmatched_b


def fmt_amount(v: float) -> str:
    return f"R {v:,.2f}" if v else "—"


def fmt_date(d) -> str:
    return d.strftime("%d/%m/%Y") if pd.notna(d) else "—"


def matches_to_df(matches: list) -> pd.DataFrame:
    if not matches:
        return pd.DataFrame()
    rows = []
    for m in matches:
        rows.append({
            "Amount":          fmt_amount(m["amount"]),
            "A Date":          fmt_date(m["a_date"]),
            "A Description":   m["a_description"],
            "A Debit":         fmt_amount(m["a_debit"]),
            "A Credit":        fmt_amount(m["a_credit"]),
            "B Date":          fmt_date(m["b_date"]),
            "B Description":   m["b_description"],
            "B Debit":         fmt_amount(m["b_debit"]),
            "B Credit":        fmt_amount(m["b_credit"]),
            "Day Difference":  m["day_diff"],
        })
    return pd.DataFrame(rows)


def unmatched_to_df(df: pd.DataFrame, missing_in: str) -> pd.DataFrame:
    """Build the 'what the other side needs' table."""
    rows = []
    for _, r in df.iterrows():
        if r["debit"] > 0:
            amount     = r["debit"]
            needs_type = "Credit"
            needs_amt  = amount
        elif r["credit"] > 0:
            amount     = r["credit"]
            needs_type = "Debit"
            needs_amt  = amount
        else:
            continue
        rows.append({
            "Date":             fmt_date(r["date"]),
            "Description":      r["description"],
            "Debit":            fmt_amount(r["debit"]),
            "Credit":           fmt_amount(r["credit"]),
            "Action Required":  f"{missing_in} needs a {needs_type} of {fmt_amount(needs_amt)} around {fmt_date(r['date'])}",
        })
    return pd.DataFrame(rows)


def to_excel(confirmed, uncertain, unmatched_a, unmatched_b, name_a, name_b) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        matches_to_df(confirmed).to_excel(writer, sheet_name="Confirmed Matches", index=False)
        matches_to_df(uncertain).to_excel(writer, sheet_name="Uncertain Matches", index=False)
        unmatched_to_df(unmatched_a, name_b).to_excel(writer, sheet_name=f"Unmatched - {name_a}", index=False)
        unmatched_to_df(unmatched_b, name_a).to_excel(writer, sheet_name=f"Unmatched - {name_b}", index=False)
    return buf.getvalue()


# ─────────────────────────────────────────────
#  SIDEBAR — UPLOAD & SETTINGS
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    date_tolerance = st.slider("Date tolerance (days)", min_value=0, max_value=7, value=3)

    st.divider()
    st.subheader("Company A")
    name_a  = st.text_input("Label", value="Company A", key="name_a")
    fmt_a   = st.selectbox("Export format", list(FORMATS.keys()), key="fmt_a")
    file_a  = st.file_uploader("Upload CSV", type="csv", key="file_a")

    st.divider()
    st.subheader("Company B")
    name_b  = st.text_input("Label", value="Company B", key="name_b")
    fmt_b   = st.selectbox("Export format", list(FORMATS.keys()), key="fmt_b")
    file_b  = st.file_uploader("Upload CSV", type="csv", key="file_b")

    st.divider()
    run_btn = st.button("▶ Run Reconciliation", type="primary", use_container_width=True)

# ─────────────────────────────────────────────
#  MAIN — RESULTS
# ─────────────────────────────────────────────
if not run_btn:
    st.info("Upload both CSV files in the sidebar and click **Run Reconciliation** to begin.")
    st.stop()

# Validate uploads
if not file_a or not file_b:
    st.warning("Please upload a CSV for both companies before running.")
    st.stop()

# Load
with st.spinner("Loading files…"):
    df_a = load_and_normalise(file_a, fmt_a, name_a)
    df_b = load_and_normalise(file_b, fmt_b, name_b)

if df_a is None or df_b is None:
    st.stop()

# Reconcile
with st.spinner("Matching transactions…"):
    confirmed, uncertain, unmatched_a, unmatched_b = reconcile(df_a, df_b, date_tolerance)

# ── Summary strip ──────────────────────────────
total = len(confirmed) + len(uncertain) + len(unmatched_a) + len(unmatched_b)

c1, c2, c3, c4 = st.columns(4)
c1.metric("✅ Confirmed Matches",  len(confirmed))
c2.metric("⚠️ Uncertain Matches",  len(uncertain))
c3.metric(f"❌ Unmatched in {name_a}", len(unmatched_a))
c4.metric(f"❌ Unmatched in {name_b}", len(unmatched_b))

st.divider()

# ── Download button ────────────────────────────
excel_bytes = to_excel(confirmed, uncertain, unmatched_a, unmatched_b, name_a, name_b)
st.download_button(
    label="⬇️ Download Full Report (Excel)",
    data=excel_bytes,
    file_name="loan_reconciliation.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.divider()

# ── Confirmed Matches ──────────────────────────
with st.expander(f"✅ Confirmed Matches  ({len(confirmed)})", expanded=True):
    if confirmed:
        df_conf = matches_to_df(confirmed)
        st.dataframe(df_conf, use_container_width=True, hide_index=True)
    else:
        st.write("No confirmed matches found.")

# ── Uncertain Matches ──────────────────────────
with st.expander(f"⚠️ Uncertain Matches — review these  ({len(uncertain)})", expanded=True):
    if uncertain:
        df_unc = matches_to_df(uncertain)
        # Highlight day difference column
        st.dataframe(
            df_unc.style.applymap(
                lambda v: "background-color: #fff3cd",
                subset=["Day Difference"]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("No uncertain matches.")

# ── Unmatched A ────────────────────────────────
with st.expander(f"❌ Unmatched in {name_a}  ({len(unmatched_a)})", expanded=True):
    if not unmatched_a.empty:
        df_ua = unmatched_to_df(unmatched_a, name_b)
        st.dataframe(
            df_ua.style.applymap(
                lambda v: "background-color: #f8d7da",
                subset=["Action Required"]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write(f"All {name_a} transactions matched.")

# ── Unmatched B ────────────────────────────────
with st.expander(f"❌ Unmatched in {name_b}  ({len(unmatched_b)})", expanded=True):
    if not unmatched_b.empty:
        df_ub = unmatched_to_df(unmatched_b, name_a)
        st.dataframe(
            df_ub.style.applymap(
                lambda v: "background-color: #f8d7da",
                subset=["Action Required"]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write(f"All {name_b} transactions matched.")
