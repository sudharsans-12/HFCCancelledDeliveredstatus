"""
HFC Automation - Cancelled & Delivered Report Generator
=========================================================
Streamlit app that:
  1. Reads the HFC report (xlsx/csv)
  2. Lets the user map their columns onto the fields the automation needs
  3. Generates the Cancelled Report (green/red carrier-status rule,
     notification flags)
  4. Generates the Delivered Report (tracking link, +7 day last-day-delivery,
     optional live Ninja Van status lookup)
  5. Provides styled .xlsx downloads for both
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from modules import data_loader, cancelled_report, delivered_report, tracking, excel_writer, notifications

st.set_page_config(page_title="HFC Automation", page_icon="📦", layout="wide")

st.title("📦 HFC Automation — Cancelled & Delivered Reports")
st.caption(
    "Upload the HFC report, map your columns once, and generate both reports "
    "with carrier-status flags, tracking links, and (optional) live Ninja Van status."
)

# ---------------------------------------------------------------------------
# 1. Upload
# ---------------------------------------------------------------------------
uploaded_file = st.file_uploader("Upload HFC report (.xlsx, .xls, or .csv)", type=["xlsx", "xls", "csv"])

if not uploaded_file:
    st.info("Upload a file to get started.")
    st.stop()

sheet_names = data_loader.list_sheets(uploaded_file)
if sheet_names and len(sheet_names) > 1:
    sheet = st.selectbox("Select sheet", sheet_names)
    df_raw = data_loader.load_sheet(uploaded_file, sheet)
else:
    uploaded_file.seek(0)
    df_raw = data_loader.load_report(uploaded_file)

st.success(f"Loaded {len(df_raw):,} rows, {len(df_raw.columns)} columns.")
with st.expander("Preview raw data"):
    st.dataframe(df_raw.head(20), use_container_width=True)

# ---------------------------------------------------------------------------
# 2. Column mapping
# ---------------------------------------------------------------------------
st.subheader("1. Map your columns")
st.caption("Auto-suggested where possible — double-check before running.")

suggestions = data_loader.suggest_mapping(df_raw.columns.tolist())
columns_with_blank = ["-- not in file --"] + df_raw.columns.tolist()

colmap = {}
col_left, col_right = st.columns(2)
fields = list(data_loader.REQUIRED_FIELDS.keys())
half = len(fields) // 2 + 1

for i, field in enumerate(fields):
    target_col = col_left if i < half else col_right
    label = data_loader.FIELD_LABELS[field]
    default = suggestions.get(field)
    default_idx = columns_with_blank.index(default) if default in columns_with_blank else 0
    with target_col:
        choice = st.selectbox(label, columns_with_blank, index=default_idx, key=f"map_{field}")
    colmap[field] = None if choice == "-- not in file --" else choice

required_for_run = ["order_id", "order_status", "payment_status", "order_date", "shipping_carrier_status"]
missing = [data_loader.FIELD_LABELS[f] for f in required_for_run if not colmap.get(f)]
if missing:
    st.warning(f"Still need to map: {', '.join(missing)}")
    st.stop()

# ---------------------------------------------------------------------------
# 3. Options
# ---------------------------------------------------------------------------
st.subheader("2. Options")
opt_col1, opt_col2 = st.columns(2)
with opt_col1:
    lookback_days = st.number_input("Cancelled report lookback window (days)", min_value=1, max_value=365, value=20)
with opt_col2:
    do_live_tracking = st.checkbox(
        "Look up live Ninja Van status for delivered orders (best-effort, slower)",
        value=False,
        help=(
            "This scrapes Ninja Van's public tracking page — it is not an official API "
            "and can fail or be blocked. See modules/tracking.py for details. Leave off "
            "to generate reports instantly and fill delivery status manually."
        ),
    )

run = st.button("🚀 Generate Reports", type="primary")

if not run:
    st.stop()

# ---------------------------------------------------------------------------
# 4. Cancelled report
# ---------------------------------------------------------------------------
st.subheader("Cancelled Report")
try:
    cancelled_df = cancelled_report.build_cancelled_report(
        df_raw, colmap, as_of=datetime.now(), lookback_days=lookback_days
    )
except KeyError as e:
    st.error(f"Column mapping error: {e}")
    st.stop()

st.write(f"{len(cancelled_df):,} cancelled & refunded orders in the last {lookback_days} days.")

def _highlight_color(val):
    if val == "GREEN":
        return "background-color: #C6EFCE; color: #006100"
    if val == "RED":
        return "background-color: #FFC7CE; color: #9C0006"
    if val == "REVIEW":
        return "background-color: #FFEB9C; color: #9C6500"
    return ""

if len(cancelled_df):
    st.dataframe(
        cancelled_df.style.map(_highlight_color, subset=["Carrier Status Color"]),
        use_container_width=True,
    )
else:
    st.info("No cancelled/refunded orders found in this window.")

# Notification previews
if len(cancelled_df):
    with st.expander("Preview seller notification messages"):
        preview = cancelled_df.apply(
            lambda r: notifications.build_message(
                r[colmap["order_id"]], r[colmap["shipping_carrier_status"]], r["Carrier Status Color"]
            ),
            axis=1,
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "Order ID": cancelled_df[colmap["order_id"]],
                    "WhatsApp Required": cancelled_df["WhatsApp Required"],
                    "Email Required": cancelled_df["Email Required"],
                    "Message": preview,
                }
            ),
            use_container_width=True,
        )
        st.caption(
            "Messages are generated for review/export only. To send automatically, "
            "configure Twilio (WhatsApp) and SMTP (Email) credentials in "
            "`.streamlit/secrets.toml` — see modules/notifications.py."
        )

cancelled_xlsx = excel_writer.build_cancelled_workbook(cancelled_df) if len(cancelled_df) else None

# ---------------------------------------------------------------------------
# 5. Delivered report
# ---------------------------------------------------------------------------
st.subheader("Delivered Report")
delivered_df = delivered_report.build_delivered_report(df_raw, colmap)
st.write(f"{len(delivered_df):,} delivered orders found.")

if len(delivered_df) and do_live_tracking:
    progress = st.progress(0, text="Looking up live tracking status...")

    def _cb(i, total):
        progress.progress(i / total, text=f"Looking up live tracking status... ({i}/{total})")

    with st.spinner("Querying Ninja Van tracking pages — this can take a while for large files."):
        delivered_df = tracking.enrich_delivered_report(delivered_df, progress_callback=_cb)
    progress.empty()
    st.caption(
        "Live lookup complete. Rows showing 'Lookup Failed - Check Manually' could not "
        "be read from Ninja Van's tracking page (blocked, rate-limited, or page changed) "
        "— check those manually."
    )
elif len(delivered_df):
    st.caption("Live tracking lookup was skipped. 'Delivery Update in MP' and status columns are left blank for manual entry.")

if len(delivered_df):
    st.dataframe(delivered_df, use_container_width=True)
else:
    st.info("No delivered orders found in this file.")

delivered_xlsx = excel_writer.build_delivered_workbook(delivered_df) if len(delivered_df) else None

# ---------------------------------------------------------------------------
# 6. Downloads
# ---------------------------------------------------------------------------
st.subheader("3. Download")
dl_col1, dl_col2 = st.columns(2)
with dl_col1:
    if cancelled_xlsx:
        st.download_button(
            "⬇️ Download Cancelled_Report.xlsx",
            data=cancelled_xlsx,
            file_name="Cancelled_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.button("⬇️ Download Cancelled_Report.xlsx", disabled=True)
with dl_col2:
    if delivered_xlsx:
        st.download_button(
            "⬇️ Download Delivered_Report.xlsx",
            data=delivered_xlsx,
            file_name="Delivered_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.button("⬇️ Download Delivered_Report.xlsx", disabled=True)
