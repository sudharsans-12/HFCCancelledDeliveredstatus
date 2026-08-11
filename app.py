"""
HFC Automation - Cancelled & Delivered Report Generator
=========================================================
Two independent tabs, each with its own upload:
  - Cancelled Report tab: upload the file that contains your cancelled
    orders, map columns, generate Cancelled_Report.xlsx. Includes a
    copy-paste-ready WhatsApp message per order.
  - Delivered Report tab: upload the file that contains your delivered
    orders (can be the same file or a different export), map columns,
    generate Delivered_Report.xlsx.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from modules import data_loader, cancelled_report, delivered_report, tracking, excel_writer

st.set_page_config(page_title="HFC Automation", page_icon="📦", layout="wide")

st.title("📦 HFC Automation — Cancelled & Delivered Reports")
st.caption(
    "Upload a file for each report separately. Map your columns once per upload, "
    "then generate a styled, ready-to-download .xlsx."
)

CANCELLED_FIELDS = [
    "order_id",
    "order_status",
    "payment_status",
    "order_date",
    "shipping_carrier_status",
]
CANCELLED_OPTIONAL_FIELDS = ["seller_name", "courier"]  # used to build the WhatsApp message
DELIVERED_FIELDS = ["order_id", "order_status", "order_date", "sold_amount", "channel", "courier", "tracking_number"]


def load_upload(uploaded_file, key_prefix: str) -> pd.DataFrame:
    sheet_names = data_loader.list_sheets(uploaded_file)
    if sheet_names and len(sheet_names) > 1:
        sheet = st.selectbox("Select sheet", sheet_names, key=f"{key_prefix}_sheet")
        df = data_loader.load_sheet(uploaded_file, sheet)
    else:
        uploaded_file.seek(0)
        df = data_loader.load_report(uploaded_file)
    return df


def render_column_mapping(df: pd.DataFrame, key_prefix: str, fields_needed, optional=False):
    """Renders the column-mapping selectboxes for the given fields and returns colmap.
    When optional=True, '-- not in file --' is a valid final choice (no warning)."""
    suggestions = data_loader.suggest_mapping(df.columns.tolist())
    columns_with_blank = ["-- not in file --"] + df.columns.tolist()

    colmap = {}
    col_left, col_right = st.columns(2)
    half = len(fields_needed) // 2 + 1

    for i, field in enumerate(fields_needed):
        target_col = col_left if i < half else col_right
        label = data_loader.FIELD_LABELS[field]
        default = suggestions.get(field)
        default_idx = columns_with_blank.index(default) if default in columns_with_blank else 0
        with target_col:
            choice = st.selectbox(label, columns_with_blank, index=default_idx, key=f"{key_prefix}_map_{field}")
        colmap[field] = None if choice == "-- not in file --" else choice

    return colmap


def _highlight_color(val):
    if val == "GREEN":
        return "background-color: #C6EFCE; color: #006100"
    if val == "RED":
        return "background-color: #FFC7CE; color: #9C0006"
    if val == "REVIEW":
        return "background-color: #FFEB9C; color: #9C6500"
    return ""


def _dark_font(val):
    return "color: #1A1A1A"


tab_cancelled, tab_delivered = st.tabs(["🚫 Cancelled Report", "✅ Delivered Report"])

# ===========================================================================
# TAB 1 — Cancelled Report (own upload)
# ===========================================================================
with tab_cancelled:
    st.subheader("1. Upload file for Cancelled Report")
    cancelled_file = st.file_uploader(
        "Upload the report containing cancelled orders (.xlsx, .xls, or .csv)",
        type=["xlsx", "xls", "csv"],
        key="cancelled_upload",
    )

    if cancelled_file:
        df_cancelled_raw = load_upload(cancelled_file, "cancelled")
        st.success(f"Loaded {len(df_cancelled_raw):,} rows, {len(df_cancelled_raw.columns)} columns.")
        with st.expander("Preview raw data"):
            st.dataframe(df_cancelled_raw.head(20), use_container_width=True)

        st.subheader("2. Map your columns")
        st.caption("Auto-suggested where possible — double-check before running.")
        colmap_c = render_column_mapping(df_cancelled_raw, "cancelled", CANCELLED_FIELDS)

        st.markdown("**For the WhatsApp message (optional but recommended):**")
        colmap_c.update(
            render_column_mapping(df_cancelled_raw, "cancelled_opt", CANCELLED_OPTIONAL_FIELDS, optional=True)
        )
        st.caption(
            "If left unmapped, the message falls back to 'Team' for the name and 'N/A' for the courier."
        )

        missing_c = [data_loader.FIELD_LABELS[f] for f in CANCELLED_FIELDS if not colmap_c.get(f)]
        if missing_c:
            st.warning(f"Still need to map: {', '.join(missing_c)}")
        else:
            st.subheader("3. Options")
            lookback_days = st.number_input(
                "Lookback window (days)", min_value=1, max_value=365, value=20, key="cancelled_lookback"
            )

            if st.button("🚀 Generate Cancelled Report", type="primary", key="cancelled_run"):
                try:
                    cancelled_df = cancelled_report.build_cancelled_report(
                        df_cancelled_raw, colmap_c, as_of=datetime.now(), lookback_days=lookback_days
                    )
                except KeyError as e:
                    st.error(f"Column mapping error: {e}")
                    cancelled_df = None

                if cancelled_df is not None:
                    st.subheader("Results")

                    display_df = cancelled_report.prepare_display_columns(cancelled_df, colmap_c)

                    green_count = int((display_df["Cancelled Status"] == "GREEN").sum())
                    red_count = int((display_df["Cancelled Status"] == "RED").sum())

                    card_col1, card_col2 = st.columns(2)
                    with card_col1:
                        st.markdown(
                            f"""<div style="background-color:#C6EFCE;border-radius:8px;padding:16px;text-align:center">
                            <div style="font-size:28px;font-weight:700;color:#006100">{green_count}</div>
                            <div style="font-size:13px;color:#006100">Green — Total orders requiring seller action</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                    with card_col2:
                        st.markdown(
                            f"""<div style="background-color:#FFC7CE;border-radius:8px;padding:16px;text-align:center">
                            <div style="font-size:28px;font-weight:700;color:#9C0006">{red_count}</div>
                            <div style="font-size:13px;color:#9C0006">Red — Total orders not requiring seller action</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )

                    st.write(
                        f"{len(display_df):,} cancelled & refunded orders in the last {lookback_days} days."
                    )

                    if len(display_df):
                        styled = display_df.style.map(_highlight_color, subset=["Cancelled Status"]).map(
                            _dark_font, subset=["Notification Message"]
                        )
                        st.dataframe(styled, use_container_width=True)

                        cancelled_xlsx = excel_writer.build_cancelled_workbook(display_df)
                        st.download_button(
                            "⬇️ Download Cancelled_Report.xlsx",
                            data=cancelled_xlsx,
                            file_name="Cancelled_Report.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    else:
                        st.info("No cancelled/refunded orders found in this window.")
    else:
        st.info("Upload a file above to generate the Cancelled Report.")

# ===========================================================================
# TAB 2 — Delivered Report (own upload)
# ===========================================================================
with tab_delivered:
    st.subheader("1. Upload file for Delivered Report")
    delivered_file = st.file_uploader(
        "Upload the report containing delivered orders (.xlsx, .xls, or .csv)",
        type=["xlsx", "xls", "csv"],
        key="delivered_upload",
    )

    if delivered_file:
        df_delivered_raw = load_upload(delivered_file, "delivered")
        st.success(f"Loaded {len(df_delivered_raw):,} rows, {len(df_delivered_raw.columns)} columns.")
        with st.expander("Preview raw data"):
            st.dataframe(df_delivered_raw.head(20), use_container_width=True)

        st.subheader("2. Map your columns")
        st.caption("Auto-suggested where possible — double-check before running.")
        colmap_d = render_column_mapping(df_delivered_raw, "delivered", DELIVERED_FIELDS)

        st.markdown("**Optional (used for Last Day Delivery calculation):**")
        opt_col = st.columns(2)[0]
        with opt_col:
            columns_with_blank = ["-- use Date column instead --"] + df_delivered_raw.columns.tolist()
            suggestions = data_loader.suggest_mapping(df_delivered_raw.columns.tolist())
            default_dd = suggestions.get("delivery_date")
            default_idx = columns_with_blank.index(default_dd) if default_dd in columns_with_blank else 0
            delivery_date_choice = st.selectbox(
                "Delivery Date column", columns_with_blank, index=default_idx, key="delivered_map_delivery_date"
            )
            colmap_d["delivery_date"] = (
                None if delivery_date_choice == "-- use Date column instead --" else delivery_date_choice
            )

        missing_d = [data_loader.FIELD_LABELS[f] for f in DELIVERED_FIELDS if not colmap_d.get(f)]
        if missing_d:
            st.warning(f"Still need to map: {', '.join(missing_d)}")
        else:
            st.subheader("3. Options")
            do_live_tracking = st.checkbox(
                "Look up live Ninja Van status for delivered orders (best-effort, slower)",
                value=False,
                key="delivered_live_tracking",
                help=(
                    "This scrapes Ninja Van's public tracking page — it is not an official API "
                    "and can fail or be blocked. See modules/tracking.py for details. Leave off "
                    "to generate the report instantly and fill delivery status manually."
                ),
            )

            if st.button("🚀 Generate Delivered Report", type="primary", key="delivered_run"):
                delivered_df = delivered_report.build_delivered_report(df_delivered_raw, colmap_d)
                st.subheader("Results")
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
                    st.caption(
                        "Live tracking lookup was skipped. 'Delivery Update in MP' and status columns "
                        "are left blank for manual entry."
                    )

                if len(delivered_df):
                    st.dataframe(delivered_df, use_container_width=True)
                    delivered_xlsx = excel_writer.build_delivered_workbook(delivered_df)
                    st.download_button(
                        "⬇️ Download Delivered_Report.xlsx",
                        data=delivered_xlsx,
                        file_name="Delivered_Report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                else:
                    st.info("No delivered orders found in this file.")
    else:
        st.info("Upload a file above to generate the Delivered Report.")
