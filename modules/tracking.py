"""
tracking.py
-----------
Best-effort live lookup of Ninja Van shipment status.

IMPORTANT — read this before relying on it in production:
Ninja Van does not publish a public tracking API. This module tries to read
the same data their public tracking *page* uses, by requesting the page and
parsing any embedded JSON payload out of the HTML. That approach is
inherently fragile:
  - Ninja Van can change their page/markup at any time and silently break this.
  - Cloud IPs (including Streamlit Community Cloud) can be rate-limited or
    blocked by anti-bot protection, in which case every lookup fails.
  - There is no SLA or guarantee of accuracy.

For a production-grade version, ask your Ninja Van account manager about
their official Tracking/Order API (requires client_id/client_secret), or use
a paid aggregator (Track123, AfterShip, Tracktry all support Ninja Van) and
plug your API key into a similar fetch function.

Every lookup is wrapped in try/except so a failed or blocked request never
crashes the report generation — it just leaves that row's status as
"Lookup Failed - Check Manually".
"""

import re
import json
import time

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DELIVERED_PHRASES = [
    "successfully delivered to receiver",
    "delivered to receiver",
    "parcel delivered",
]

LOOKUP_FAILED = "Lookup Failed - Check Manually"
LOOKUP_SKIPPED = "Not Checked (lookup disabled)"


def _extract_json_blobs(html: str):
    blobs = []
    for match in re.finditer(
        r'<script[^>]+type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL
    ):
        try:
            blobs.append(json.loads(match.group(1)))
        except (json.JSONDecodeError, ValueError):
            continue
    return blobs


def _find_events_in_blob(blob):
    events = []

    def walk(node):
        if isinstance(node, dict):
            keys_lower = {k.lower(): k for k in node.keys()}
            has_desc = any(k in keys_lower for k in ("description", "status", "event", "process", "message"))
            has_time = any(k in keys_lower for k in ("date", "time", "datetime", "timestamp", "createdat"))
            if has_desc and has_time:
                events.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(blob)
    return events


def _normalise_event(ev: dict):
    keys_lower = {k.lower(): k for k in ev.keys()}
    desc_key = next((keys_lower[k] for k in ("description", "status", "event", "process", "message") if k in keys_lower), None)
    time_key = next((keys_lower[k] for k in ("date", "time", "datetime", "timestamp", "createdat") if k in keys_lower), None)
    desc = ev.get(desc_key) if desc_key else None
    ts = ev.get(time_key) if time_key else None
    return desc, ts


def fetch_tracking_status(tracking_number: str, timeout: int = 10) -> dict:
    if not tracking_number:
        return {"status": LOOKUP_FAILED, "last_event_time": "", "delivered": False, "error": "empty tracking number"}

    url = f"https://www.ninjavan.co/en-my/international/tracking?id={tracking_number}"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        html = resp.text

        blobs = _extract_json_blobs(html)
        all_events = []
        for blob in blobs:
            all_events.extend(_find_events_in_blob(blob))

        parsed = []
        for ev in all_events:
            desc, ts = _normalise_event(ev)
            if desc and ts:
                parsed.append((str(desc).strip(), str(ts).strip()))

        if not parsed:
            return {
                "status": LOOKUP_FAILED,
                "last_event_time": "",
                "delivered": False,
                "error": "no events found on page (page structure may have changed, or was blocked)",
            }

        latest_desc, latest_ts = parsed[-1]
        delivered = any(phrase in latest_desc.lower() for phrase in DELIVERED_PHRASES)

        return {
            "status": latest_desc,
            "last_event_time": latest_ts,
            "delivered": delivered,
            "error": None,
        }

    except requests.exceptions.RequestException as e:
        return {"status": LOOKUP_FAILED, "last_event_time": "", "delivered": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": LOOKUP_FAILED, "last_event_time": "", "delivered": False, "error": str(e)}


def enrich_delivered_report(df, tracking_col="Tracking Number", delay_seconds: float = 0.6, progress_callback=None):
    total = len(df)
    statuses = []
    times = []
    mp_updates = []

    for i, tn in enumerate(df[tracking_col].tolist()):
        result = fetch_tracking_status(tn)
        statuses.append(result["status"])
        times.append(result["last_event_time"])
        mp_updates.append("Delivery Update in MP" if result["delivered"] else result["status"])

        if progress_callback:
            progress_callback(i + 1, total)

        time.sleep(delay_seconds)

    df = df.copy()
    df["Latest Shipment Status"] = statuses
    df["Latest Update Date & Time"] = times
    df["Delivery Update in MP"] = mp_updates
    return df
