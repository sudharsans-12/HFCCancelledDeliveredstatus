"""
data_loader.py
---------------
Reads the raw HFC report (xlsx or csv) uploaded by the user and provides
fuzzy column-name matching so the app can auto-suggest a mapping between
the columns required by the automation and whatever headers the source
report actually uses (these tend to drift between exports).
"""

import difflib
import io

import pandas as pd

# Fields the automation needs, and the header text we expect real reports
# to roughly use. The app lets the user override any of these via dropdown.
REQUIRED_FIELDS = {
    "order_id": ["Order ID", "OrderID", "Order No", "Order Number"],
    "order_status": ["Order Status", "Status"],
    "payment_status": ["Payment Status", "PaymentStatus"],
    "order_date": ["Order Date", "Date", "Created Date", "Order Creation Date"],
    "sold_amount": ["Sold Amount", "Amount", "Order Amount", "Total Amount", "Price"],
    "channel": ["Channel", "Marketplace", "Platform"],
    "courier": ["Courier", "Shipping Provider", "Logistics Provider", "Carrier", "Shipping Method"],
    "tracking_number": ["Tracking Number", "Tracking No", "AWB", "AWB Number", "Tracking"],
    "shipping_carrier_status": [
        "Shipping Carrier Status",
        "Carrier Status",
        "Shipment Status",
    ],
    "delivery_date": [
        "Delivery Date",
        "Delivered Date",
        "Delivered On",
        "Actual Delivery Date",
    ],
}

FIELD_LABELS = {
    "order_id": "Order ID",
    "order_status": "Order Status",
    "payment_status": "Payment Status",
    "order_date": "Order Date",
    "sold_amount": "Sold Amount",
    "channel": "Channel",
    "courier": "Courier / Shipping Method",
    "tracking_number": "Tracking Number",
    "shipping_carrier_status": "Shipping Carrier Status",
    "delivery_date": "Delivery Date (used for Last Day Delivery on delivered orders)",
}


def load_report(uploaded_file) -> pd.DataFrame:
    """Load an uploaded xlsx/xls/csv file into a DataFrame."""
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    buf = io.BytesIO(data)

    if name.endswith(".csv"):
        df = pd.read_csv(buf)
    else:
        df = pd.read_excel(buf)

    df.columns = [str(c).strip() for c in df.columns]
    return df


def list_sheets(uploaded_file):
    """Return sheet names for an Excel file, or None for CSV."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return None
    uploaded_file.seek(0)
    xls = pd.ExcelFile(io.BytesIO(uploaded_file.read()))
    uploaded_file.seek(0)
    return xls.sheet_names


def load_sheet(uploaded_file, sheet_name) -> pd.DataFrame:
    uploaded_file.seek(0)
    df = pd.read_excel(io.BytesIO(uploaded_file.read()), sheet_name=sheet_name)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def suggest_mapping(columns):
    """
    For each required field, guess the best-matching source column using
    fuzzy string matching over a list of likely header aliases.
    Returns dict field_key -> best guess column name (or None).
    """
    suggestions = {}
    lower_cols = {c.lower(): c for c in columns}

    for field, aliases in REQUIRED_FIELDS.items():
        best = None
        best_score = 0.0
        for alias in aliases:
            if alias.lower() in lower_cols:
                best = lower_cols[alias.lower()]
                best_score = 1.0
                break
            match = difflib.get_close_matches(alias.lower(), lower_cols.keys(), n=1, cutoff=0.6)
            if match:
                score = difflib.SequenceMatcher(None, alias.lower(), match[0]).ratio()
                if score > best_score:
                    best_score = score
                    best = lower_cols[match[0]]
        suggestions[field] = best
    return suggestions
