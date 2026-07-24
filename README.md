# HFC Automation — Cancelled & Delivered Reports

Streamlit app that reads your HFC report and generates two styled Excel
reports:

1. **Cancelled_Report.xlsx** — cancelled + refunded orders from the last N
   days, with a green/red Shipping Carrier Status flag and seller
   notification flags (WhatsApp/Email).
2. **Delivered_Report.xlsx** — delivered orders only, trimmed to the required
   columns, with a clickable Ninja Van tracking link, a "Last Day Delivery"
   date (+7 days, time preserved), and optional live tracking status.

## How it works

The app has **two independent tabs**, each with its own file upload:

- **Cancelled Report tab** — upload whichever export contains your cancelled
  orders, map columns, generate `Cancelled_Report.xlsx`.
- **Delivered Report tab** — upload whichever export contains your delivered
  orders (can be the same file or a completely different one), map columns,
  generate `Delivered_Report.xlsx`.

You only need to map the columns each report actually uses — the Cancelled
tab won't ask for Courier/Tracking Number, and the Delivered tab won't ask
for Payment Status.

Steps per tab:
1. Upload the file (`.xlsx`, `.xls`, or `.csv`).
2. Confirm/correct the auto-suggested column mapping.
3. Click **Generate**.
4. Download the `.xlsx`.

No column names are hardcoded, so this works even if your export's headers
differ slightly from month to month, and even if the two reports come from
two different source files with different headers entirely.

## Business rules implemented

**Cancelled Report**
- Order Status = Cancelled AND Payment Status = Refunded
- Order date within the last 20 days (configurable in the UI)
- Shipping Carrier Status:
  - **Green** — Not Shipped / Shipped / Delivered / N/A → seller notified via WhatsApp to cancel shipment
  - **Red** — SHIPMENT_CREATED → seller notified via Email + WhatsApp, flagged as requiring action
  - **Yellow (Review)** — any status the app doesn't recognize, flagged for manual review rather than silently miscategorized

**Delivered Report**
- Order Status = Delivered only
- Columns: Order ID, Sold Amount, Date, Status, Channel, Courier, Tracking Number, Tracking Link, Last Day Delivery, Delivery Update in MP, Latest Update Date & Time, Latest Shipment Status
- Tracking Link: `https://www.ninjavan.co/en-my/international/tracking?id=<TrackingNumber>`
- Last Day Delivery = Delivery Date + 7 days, time-of-day unchanged

## ⚠️ About live Ninja Van tracking lookup

Ninja Van does not publish a public tracking API. The optional "live lookup"
checkbox has the app request Ninja Van's public tracking **page** and parse
whatever tracking data is embedded in it. This is a best-effort scrape, not
an official integration:

- It can break any time Ninja Van changes their page.
- Cloud IPs (including Streamlit Community Cloud) may get rate-limited or
  blocked.
- Rows it can't read are marked `Lookup Failed - Check Manually` instead of
  crashing the run.

If you have a Ninja Van corporate/API account, ask your account manager for
their official Order/Tracking API and swap the implementation in
`modules/tracking.py`. Paid aggregators (Track123, AfterShip, Tracktry) also
support Ninja Van and are more reliable than scraping.

If reliability matters more than automation here, leave "live lookup" off —
the report still generates instantly with blank status columns for manual
fill-in, and everything else (filtering, colour flags, tracking links,
Last Day Delivery) still works.

## Sending notifications automatically (optional)

By default the app only **previews** the WhatsApp/Email message text for
each flagged cancelled order — nothing is sent. To enable actual sending,
add a `.streamlit/secrets.toml` (do not commit this file) with:

```toml
[twilio]
account_sid = "..."
auth_token = "..."
whatsapp_from = "whatsapp:+14155238886"

[smtp]
host = "smtp.yourprovider.com"
port = 587
username = "..."
password = "..."
from_address = "ops@yourcompany.com"
```

Then wire `notifications.send_whatsapp()` / `notifications.send_email()` into
`app.py` where you want the send button to trigger (not wired by default —
sending should usually be a deliberate click, not automatic, when the target
is a real seller).

## Local setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repo.
2. Go to https://share.streamlit.io → **New app**.
3. Point it at your repo, branch, and `app.py`.
4. If using notifications, add the secrets above under **App settings → Secrets**.
5. Deploy.

## Project structure

```
hfc-automation/
├── app.py                     # Streamlit UI and orchestration
├── modules/
│   ├── data_loader.py         # file reading + fuzzy column mapping
│   ├── cancelled_report.py    # cancelled/refunded filter + colour rule
│   ├── delivered_report.py    # delivered filter + tracking link + +7 days
│   ├── tracking.py            # best-effort Ninja Van live status lookup
│   ├── excel_writer.py        # styled .xlsx output (colours, hyperlinks)
│   └── notifications.py       # WhatsApp/Email message text + optional send
├── requirements.txt
├── .streamlit/config.toml
└── README.md
```
