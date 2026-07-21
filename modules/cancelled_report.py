"""
cancelled_report.py
--------------------
Builds the Cancelled Report:
  - Order Status = Cancelled
  - Payment Status = Refunded
  - Last 20 days only
  - Shipping Carrier Status colour rule (Green / Red)
  - Seller action / Email / WhatsApp notification flags
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

    result["Carrier Status Color"] = result[carrier_status_col].apply(classify_carrier_status)
    result["Seller Action Required"] = result["Carrier Status Color"].map(
        {"GREEN": "Yes", "RED": "Yes", "REVIEW": "Manual Review"}
    )
    result["WhatsApp Required"] = result["Carrier Status Color"].map(
        {"GREEN": "Yes", "RED": "Yes", "REVIEW": "Yes"}
    )
    result["Email Required"] = result["Carrier Status Color"].map(
        {"GREEN": "No", "RED": "Yes", "REVIEW": "Yes"}
    )
    result["Notification Message"] = result.apply(
        lambda r: (
            "URGENT: Please cancel the shipment for this order immediately."
            if r["Carrier Status Color"] == "RED"
            else "Please cancel the shipment for this order."
            if r["Carrier Status Color"] == "GREEN"
            else "Carrier status unrecognised - please review manually."
        ),
        axis=1,
    )

    result = result.drop(columns=["_order_date_parsed"])
    return result
