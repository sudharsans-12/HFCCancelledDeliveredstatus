"""
delivered_report.py
--------------------
Builds the Delivered Report:
  - Order Status = Delivered
  - Keeps only the required columns
  - Adds Tracking Link, Last Day Delivery (+7 days, time preserved)
  - Adds placeholders for the live-tracking columns (filled in by tracking.py)
"""

import pandas as pd

OUTPUT_COLUMNS = [
    "Order ID",
    "Sold Amount",
    "Date",
    "Status",
    "Channel",
    "Courier",
    "Tracking Number",
]


def ninja_van_tracking_link(tracking_number: str) -> str:
    if not tracking_number or (isinstance(tracking_number, float) and pd.isna(tracking_number)):
        return ""
    tn = str(tracking_number).strip()
    if not tn:
        return ""
    return f"https://www.ninjavan.co/en-my/international/tracking?id={tn}"


def build_delivered_report(df: pd.DataFrame, colmap: dict) -> pd.DataFrame:
    """
    df: raw HFC report
    colmap: dict field_key -> actual column name in df
    """
    order_status_col = colmap["order_status"]

    work = df.copy()
    mask = work[order_status_col].astype(str).str.strip().str.lower().eq("delivered")
    filtered = work.loc[mask].copy()

    out = pd.DataFrame()
    out["Order ID"] = filtered[colmap["order_id"]]
    out["Sold Amount"] = filtered[colmap["sold_amount"]]
    out["Date"] = pd.to_datetime(filtered[colmap["order_date"]], errors="coerce")
    out["Status"] = filtered[order_status_col]
    out["Channel"] = filtered[colmap["channel"]]
    out["Courier"] = filtered[colmap["courier"]]
    out["Tracking Number"] = filtered[colmap["tracking_number"]]

    if colmap.get("delivery_date") and colmap["delivery_date"] in filtered.columns:
        delivery_dt = pd.to_datetime(filtered[colmap["delivery_date"]], errors="coerce")
        delivery_dt = delivery_dt.fillna(out["Date"])
    else:
        delivery_dt = out["Date"]

    out["Tracking Link"] = out["Tracking Number"].apply(ninja_van_tracking_link)
    out["Last Day Delivery"] = delivery_dt + pd.Timedelta(days=7)

    out["Delivery Update in MP"] = ""
    out["Latest Update Date & Time"] = ""
    out["Latest Shipment Status"] = ""

    out = out.reset_index(drop=True)
    return out
