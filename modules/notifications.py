"""
notifications.py
-----------------
Builds the seller-facing WhatsApp / Email notification text for cancelled
orders that need shipment cancellation, and (optionally) sends them if the
user has configured credentials in Streamlit secrets.

Nothing sends automatically unless secrets are present — by default this
module just returns the message text so it can be shown/copied/exported
from the app.

To enable actual sending, add to .streamlit/secrets.toml (never commit this
file):

    [twilio]
    account_sid = "..."
    auth_token = "..."
    whatsapp_from = "whatsapp:+14155238886"   # Twilio WhatsApp sandbox/number

    [smtp]
    host = "smtp.yourprovider.com"
    port = 587
    username = "..."
    password = "..."
    from_address = "ops@yourcompany.com"
"""

from email.mime.text import MIMEText
import smtplib


def build_message(order_id: str, carrier_status: str, urgency: str) -> str:
    if urgency == "RED":
        return (
            f"[ACTION REQUIRED] Order {order_id} is CANCELLED & REFUNDED but the "
            f"shipping carrier status is '{carrier_status}'. Please cancel this "
            f"shipment immediately to avoid a failed/returned delivery."
        )
    return (
        f"Order {order_id} is CANCELLED & REFUNDED. Carrier status is "
        f"'{carrier_status}'. Please cancel the shipment for this order."
    )


def send_whatsapp(to_number: str, message: str, secrets) -> tuple[bool, str]:
    """Send via Twilio WhatsApp API. Returns (success, info_or_error)."""
    try:
        from twilio.rest import Client
    except ImportError:
        return False, "twilio package not installed (add 'twilio' to requirements.txt)"

    try:
        cfg = secrets["twilio"]
        client = Client(cfg["account_sid"], cfg["auth_token"])
        msg = client.messages.create(
            from_=cfg["whatsapp_from"],
            body=message,
            to=f"whatsapp:{to_number}",
        )
        return True, msg.sid
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def send_email(to_address: str, subject: str, message: str, secrets) -> tuple[bool, str]:
    """Send via plain SMTP. Returns (success, info_or_error)."""
    try:
        cfg = secrets["smtp"]
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = cfg["from_address"]
        msg["To"] = to_address

        with smtplib.SMTP(cfg["host"], int(cfg["port"])) as server:
            server.starttls()
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["from_address"], [to_address], msg.as_string())
        return True, "sent"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
