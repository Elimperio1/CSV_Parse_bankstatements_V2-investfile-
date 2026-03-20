import streamlit as st
import pandas as pd
from io import BytesIO

st.title("Intercompany Loan Reconciliation Motherfuckers")
st.caption("Match intercompany loan transactions between two Sage or Pastel exports.")

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

def load_and_normalise(uploaded_file, fmt, company_label):
    try:
        raw = uploaded_file.read().decode("utf-8", errors="replace")
        uploaded_file.seek(0)
        first_line = raw.splitlines()[0].strip().lower()
        skip = 1 if first_line.startswith("sep=") else 0
        df = pd.read_csv(uploaded_file, dtype=str, skiprows=skip)
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


def reconcile(df_a, df_b, tolerance=3):
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

            if ra["debit"] > 0:
                amount       = ra["debit"]
                b_amount_col = "credit"
            elif ra["credit"] > 0:
                amount       = ra["credit"]
                b_amount_col = "debit"
            else:
                continue

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


def fmt_amount(v):
    return f"R {v:,.2f}" if v else "—"


def fmt_date(d):
    return d.strftime("%d/%m/%Y") if pd.notna(d) else "—"


def matches_to_df(matches, name_a, name_b):
    if not matches:
        return pd.DataFrame()
    rows = []
    for m in matches:
        rows.append({
            "Amount":                   fmt_amount(m["amount"]),
            f"{name_a} Date":           fmt_date(m["a_date"]),
            f"{name_a} Description":    m["a_description"],
            f"{name_a} Debit":          fmt_amount(m["a_debit"]),
            f"{name_a} Credit":         fmt_amount(m["a_credit"]),
            f"{name_b} Date":           fmt_date(m["b_date"]),
            f"{name_b} Description":    m["b_description"],
            f"{name_b} Debit":          fmt_amount(m["b_debit"]),
            f"{name_b} Credit":         fmt_amount(m["b_credit"]),
            "Day Difference":           m["day_diff"],
        })
    return pd.DataFrame(rows)


def unmatched_to_df(df, missing_in):
    rows = []
    for _, r in df.iterrows():
        if r["debit"] > 0:
            amount     = r["debit"]
            needs_type = "Credit"
        elif r["credit"] > 0:
            amount     = r["credit"]
            needs_type = "Debit"
        else:
            continue
        rows.append({
            "Date":            fmt_date(r["date"]),
            "Description":     r["description"],
            "Debit":           fmt_amount(r["debit"]),
            "Credit":          fmt_amount(r["credit"]),
            "Action Required": f"{missing_in} needs a {needs_type} of {fmt_amount(amount)} around {fmt_date(r['date'])}",
        })
    return pd.DataFrame(rows)


def to_excel(confirmed, uncertain, unmatched_a, unmatched_b, name_a, name_b):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        matches_to_df(confirmed, name_a, name_b).to_excel(writer, sheet_name="Confirmed Matches", index=False)
        matches_to_df(uncertain, name_a, name_b).to_excel(writer, sheet_name="Uncertain Matches", index=False)
        unmatched_to_df(unmatched_a, name_b).to_excel(writer, sheet_name=f"Unmatched {name_a[:20]}", index=False)
        unmatched_to_df(unmatched_b, name_a).to_excel(writer, sheet_name=f"Unmatched {name_b[:20]}", index=False)
    return buf.getvalue()


# ─────────────────────────────────────────────
#  STEP 1 — SETTINGS (sidebar, minimal)
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    date_tolerance = st.slider("Date tolerance (days)", min_value=0, max_value=7, value=3)

# ─────────────────────────────────────────────
#  STEP 1 — COMPANY INPUTS (main area)
# ─────────────────────────────────────────────
st.subheader("Step 1 — Company Details & Upload")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("####  Company A")
    name_a = st.text_input("Company name", value="Company A", key="name_a")
    fmt_a  = st.selectbox("Export format", list(FORMATS.keys()), key="fmt_a")
    file_a = st.file_uploader("Upload CSV", type="csv", key="file_a")

with col_b:
    st.markdown("####  Company B")
    name_b = st.text_input("Company name", value="Company B", key="name_b")
    fmt_b  = st.selectbox("Export format", list(FORMATS.keys()), key="fmt_b")
    file_b = st.file_uploader("Upload CSV", type="csv", key="file_b")

st.divider()

run_btn = st.button("▶ Run Reconciliation", type="primary", use_container_width=True)

# ─────────────────────────────────────────────
#  STEP 2 — RESULTS
# ─────────────────────────────────────────────
if not run_btn:
    st.info("Fill in company details, upload both CSVs above, then click **Run Reconciliation**.")
    st.stop()

if not file_a or not file_b:
    st.warning("Please upload a CSV for both companies before running.")
    st.stop()

with st.spinner("Loading files…"):
    df_a = load_and_normalise(file_a, fmt_a, name_a)
    df_b = load_and_normalise(file_b, fmt_b, name_b)

if df_a is None or df_b is None:
    st.stop()

with st.spinner("Matching transactions…"):
    confirmed, uncertain, unmatched_a, unmatched_b = reconcile(df_a, df_b, date_tolerance)

# ── Summary ────────────────────────────────────
st.subheader("Step 2 — Results")

c1, c2, c3, c4 = st.columns(4)
c1.metric(" Confirmed Matches",      len(confirmed))
c2.metric(" Uncertain Matches",      len(uncertain))
c3.metric(f" Unmatched in {name_a}", len(unmatched_a))
c4.metric(f"Unmatched in {name_b}", len(unmatched_b))

st.divider()

# ── Download ───────────────────────────────────
try:
    excel_bytes = to_excel(confirmed, uncertain, unmatched_a, unmatched_b, name_a, name_b)
    st.download_button(
        label="⬇️ Download Full Report (Excel)",
        data=excel_bytes,
        file_name="loan_reconciliation.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
except Exception as e:
    st.warning(f"Excel export unavailable: {e}. Make sure `openpyxl` is in your requirements.txt.")

st.divider()

# ── Tables ─────────────────────────────────────
with st.expander(f" Confirmed Matches  ({len(confirmed)})", expanded=True):
    if confirmed:
        st.dataframe(matches_to_df(confirmed, name_a, name_b), use_container_width=True, hide_index=True)
    else:
        st.write("No confirmed matches found.")

with st.expander(f"Uncertain Matches — review these  ({len(uncertain)})", expanded=True):
    if uncertain:
        df_unc = matches_to_df(uncertain, name_a, name_b)
        st.dataframe(
            df_unc.style.map(lambda v: "background-color: #fff3cd", subset=["Day Difference"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("No uncertain matches.")

with st.expander(f" Unmatched in {name_a}  ({len(unmatched_a)})", expanded=True):
    if not unmatched_a.empty:
        df_ua = unmatched_to_df(unmatched_a, name_b)
        st.dataframe(
            df_ua.style.map(lambda v: "background-color: #f8d7da", subset=["Action Required"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write(f"All {name_a} transactions matched. ")

with st.expander(f"Unmatched in {name_b}  ({len(unmatched_b)})", expanded=True):
    if not unmatched_b.empty:
        df_ub = unmatched_to_df(unmatched_b, name_a)
        st.dataframe(
            df_ub.style.map(lambda v: "background-color: #f8d7da", subset=["Action Required"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write(f"All {name_b} transactions matched. ")
