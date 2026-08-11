"""
cancelled_report.py
--------------------
Builds the Cancelled Report:
  - Order Status = Cancelled
  - Payment Status = Refunded
  - Last N days only (default 20)
  - Shipping Carrier Status colour rule (Green / Red / Review)
  - Seller action / Email / WhatsApp notification flags

The WhatsApp Notification Message is NOT built here — the recipient name is
entered manually per-row in the app (via an editable table), so the message
is assembled in app.py once the user has ticked a row and typed a name.
"""

from datetime import datetime, timedelta

import pandas as pd

GREEN_STATUSES = {"not shipped", "shipped", "delivered", "n/a", "na", "not available"}
RED_STATUSES = {"shipment_created", "shipment created"}


def classify_carrier_status(raw_status: str) -> str:
    """Return 'GREEN', 'RED', or 'REVIEW' (unrecognised status)."""
    if raw_status is None or (isinstance(raw_status, float) and pd.isna(raw_status)):
        return "GREEN"  # blank / NaN is treated as N/A
    s = str(raw_status).strip().lower()
    if s in GREEN_STATUSES:
        return "GREEN"
    if s in RED_STATUSES:
        return "RED"
    return "REVIEW"


def build_cancelled_report(
    df: pd.DataFrame, colmap: dict, as_of: datetime = None, lookback_days: int = 20
) -> pd.DataFrame:
    """
    df: raw HFC report
    colmap: dict field_key -> actual column name in df (see data_loader.REQUIRED_FIELDS)
    as_of: reference "today" for the lookback window (defaults to now)
    lookback_days: how many days back from as_of to include (default 20 per spec)
    """
    as_of = as_of or datetime.now()
    cutoff = as_of - timedelta(days=lookback_days)

    work = df.copy()

    order_status_col = colmap["order_status"]
    payment_status_col = colmap["payment_status"]
    order_date_col = colmap["order_date"]
    carrier_status_col = colmap["shipping_carrier_status"]

    work["_order_date_parsed"] = pd.to_datetime(work[order_date_col], errors="coerce")

    mask = (
        work[order_status_col].astype(str).str.strip().str.lower().eq("cancelled")
        & work[payment_status_col].astype(str).str.strip().str.lower().eq("refunded")
        & work["_order_date_parsed"].notna()
        & (work["_order_date_parsed"] >= cutoff)
        & (work["_order_date_parsed"] <= as_of)
    )

    result = work.loc[mask].copy()

    result["Cancelled Status"] = result[carrier_status_col].apply(classify_carrier_status)
    result["Seller Action Required"] = result["Cancelled Status"].map(
        {"GREEN": "Yes", "RED": "Yes", "REVIEW": "Manual Review"}
    )
    result["WhatsApp Required"] = result["Cancelled Status"].map(
        {"GREEN": "Yes", "RED": "Yes", "REVIEW": "Yes"}
    )
    result["Email Required"] = result["Cancelled Status"].map(
        {"GREEN": "No", "RED": "Yes", "REVIEW": "Yes"}
    )

    result = result.drop(columns=["_order_date_parsed"])
    return result


EXPORT_COLUMNS = [
    "Order ID",
    "Date",
    "Status",
    "Payment Status",
    "Shipping Carrier Status (All)",
    "Cancelled Status",
    "Seller Action Required",
    "WhatsApp Required",
    "Email Required",
    "Notification Message",
]


def prepare_display_columns(result: pd.DataFrame, colmap: dict) -> pd.DataFrame:
    """
    Builds the fixed dashboard/export column set (minus Notification Message,
    which is assembled later once a name is entered per row). Also carries a
    hidden '_Courier' helper column (not displayed/exported directly) so the
    app can build the WhatsApp message without a second lookup.
    """
    out = pd.DataFrame()
    out["Order ID"] = result[colmap["order_id"]]
    out["Date"] = pd.to_datetime(result[colmap["order_date"]], errors="coerce")
    out["Status"] = result[colmap["order_status"]]
    out["Payment Status"] = result[colmap["payment_status"]]
    out["Shipping Carrier Status (All)"] = result[colmap["shipping_carrier_status"]]
    out["Cancelled Status"] = result["Cancelled Status"]
    out["Seller Action Required"] = result["Seller Action Required"]
    out["WhatsApp Required"] = result["WhatsApp Required"]
    out["Email Required"] = result["Email Required"]

    courier_col = colmap.get("courier")
    out["_Courier"] = result[courier_col] if courier_col and courier_col in result.columns else ""

    return out.reset_index(drop=True)
