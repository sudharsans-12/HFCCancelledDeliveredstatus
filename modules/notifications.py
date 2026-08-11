"""
notifications.py
-----------------
Generates the seller-facing WhatsApp message for cancelled orders that need
shipment cancellation. The message format is fixed and exact — it is meant
to be copy-pasted directly into WhatsApp, so nothing else (explanations,
headings, extra text) is ever added around it.

Required format:

    Hi @~[Name] This order has been cancelled in the system. Kindly ensure
    that's not shipped. Thank you
    [Order Number] ( [Courier / Shipping Method] )

Example:

    Hi @~YiYen This order has been cancelled in the system. Kindly ensure
    that's not shipped. Thank you
    2608112TUYX42Y ( Seller's Own Fleet (West Malaysia) )

send_whatsapp / send_email below are optional integration hooks — nothing
sends automatically unless Twilio/SMTP secrets are configured. By default
the app only shows the message text for manual copy-paste.
"""

from email.mime.text import MIMEText
import smtplib

DEFAULT_NAME = "Team"
DEFAULT_COURIER = "N/A"


def build_whatsapp_message(name: str, order_number: str, courier: str) -> str:
    """Returns the exact WhatsApp message text — nothing else."""
    name = (str(name).strip() if name not in (None, "") else DEFAULT_NAME)
    courier = (str(courier).strip() if courier not in (None, "") else DEFAULT_COURIER)
    order_number = str(order_number).strip()

    return (
        f"Hi @~{name} This order has been cancelled in the system. "
        f"Kindly ensure that's not shipped. Thank you\n"
        f"{order_number} ( {courier} )"
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
