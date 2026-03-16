"""
tools/send_whatsapp_alert.py
Sends WhatsApp alert messages using the Twilio API.
Reads credentials from .env file.
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _build_whatsapp_message(alert_type: str, alert_data: dict, filename: str) -> str:
    """Compose a plain-text WhatsApp message for the given alert."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if alert_type == "alert_1":
        msg = (
            f"⚠ *ALERT: Low Unloading Speed*\n"
            f"─────────────────────\n"
            f"📄 Truck File: {filename}\n"
            f"🐦 Total Birds: {alert_data.get('total_birds', 'N/A'):,}\n"
            f"⏱ Total Time: {alert_data.get('total_minutes', 'N/A')} minutes\n"
            f"🚨 Speed: {alert_data.get('speed', 'N/A')} birds/min (threshold: 60)\n"
            f"🕐 Start: {alert_data.get('start_time', 'N/A')}\n"
            f"🕐 End: {alert_data.get('end_time', 'N/A')}\n"
            f"─────────────────────\n"
            f"⏰ Generated: {now}"
        )
    elif alert_type == "alert_2":
        msg = (
            f"⚠ *ALERT: Counting Break Detected*\n"
            f"─────────────────────\n"
            f"📄 Truck File: {filename}\n"
            f"🐦 Break At Count: {alert_data.get('bird_count', 'N/A'):,} birds\n"
            f"🕐 Break Start: {alert_data.get('break_start', 'N/A')}\n"
            f"🕐 Break End: {alert_data.get('break_end', 'N/A')}\n"
            f"⏱ Duration: {alert_data.get('duration_minutes', 'N/A')} min (threshold: 10 min)\n"
            f"─────────────────────\n"
            f"⏰ Generated: {now}"
        )
    elif alert_type == "alert_3":
        msg = (
            f"⚠ *ALERT: Excessive Wait Between Trucks*\n"
            f"─────────────────────\n"
            f"📄 Current Truck: {filename}\n"
            f"🕐 Prev Truck End: {alert_data.get('previous_truck_end', 'N/A')}\n"
            f"🕐 Curr Truck Start: {alert_data.get('new_truck_start', 'N/A')}\n"
            f"⏱ Gap: {alert_data.get('gap_minutes', 'N/A')} min (threshold: 20 min)\n"
            f"─────────────────────\n"
            f"⏰ Generated: {now}"
        )
    else:
        msg = f"⚠ *Bird Counter Alert ({alert_type})*\n{alert_data}\nGenerated: {now}"

    return msg


def send_whatsapp_alert(alert_type: str, alert_data: dict, filename: str) -> dict:
    """
    Send a WhatsApp message via Twilio API.

    Args:
        alert_type : "alert_1", "alert_2", or "alert_3"
        alert_data : dict returned by the corresponding check function
        filename   : original CSV filename being processed

    Returns:
        {"sent": bool, "error": str|None}
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "")
    to_number = os.getenv("WHATSAPP_RECIPIENT", "")

    if not account_sid or not auth_token:
        msg = "TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not configured."
        logger.error(msg)
        return {"sent": False, "error": msg}

    if not to_number:
        msg = "WHATSAPP_RECIPIENT not configured."
        logger.error(msg)
        return {"sent": False, "error": msg}

    try:
        from twilio.rest import Client
        from twilio.base.exceptions import TwilioRestException
    except ImportError:
        err = "twilio package not installed. Run: pip install twilio"
        logger.error(err)
        return {"sent": False, "error": err}

    message_body = _build_whatsapp_message(alert_type, alert_data, filename)

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=message_body,
            from_=from_number,
            to=to_number,
        )
        logger.info(
            f"WhatsApp sent ({alert_type}) to {to_number} — SID: {message.sid}"
        )
        return {"sent": True, "error": None}

    except TwilioRestException as e:
        err = f"Twilio API error: {e}"
        logger.error(err)
        return {"sent": False, "error": err}
    except Exception as e:
        err = f"Unexpected WhatsApp error: {e}"
        logger.error(err)
        return {"sent": False, "error": err}
