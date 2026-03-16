"""
tools/send_email_alert.py
Sends formatted HTML alert emails via SMTP.
Reads credentials from .env file.
"""

import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Message templates ────────────────────────────────────────────────────────

SUBJECTS = {
    "alert_1": "⚠ ALERT: Low Unloading Speed Detected",
    "alert_2": "⚠ ALERT: Counting Break Detected During Unloading",
    "alert_3": "⚠ ALERT: Excessive Wait Between Trucks",
}


def _build_html_body(alert_type: str, alert_data: dict, filename: str) -> str:
    """Compose a styled HTML email body for the given alert."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def row(label, value):
        return f"<tr><td style='padding:8px 12px;font-weight:bold;background:#f5f5f5;border:1px solid #ddd;'>{label}</td><td style='padding:8px 12px;border:1px solid #ddd;'>{value}</td></tr>"

    if alert_type == "alert_1":
        rows = "".join([
            row("Truck File", filename),
            row("Total Birds", f"{alert_data.get('total_birds', 'N/A'):,}"),
            row("Total Time", f"{alert_data.get('total_minutes', 'N/A')} minutes"),
            row("Speed", f"<strong style='color:#c0392b;'>{alert_data.get('speed', 'N/A')} birds/min</strong> (threshold: 60)"),
            row("Start Time", alert_data.get("start_time", "N/A")),
            row("End Time", alert_data.get("end_time", "N/A")),
        ])
        detail = "The truck is being unloaded too slowly. Immediate attention required."

    elif alert_type == "alert_2":
        rows = "".join([
            row("Truck File", filename),
            row("Break At Count", f"{alert_data.get('bird_count', 'N/A'):,} birds"),
            row("Break Start", alert_data.get("break_start", "N/A")),
            row("Break End", alert_data.get("break_end", "N/A")),
            row("Break Duration", f"<strong style='color:#c0392b;'>{alert_data.get('duration_minutes', 'N/A')} minutes</strong> (threshold: 10 min)"),
        ])
        detail = "The counting line stopped mid-unloading. Please investigate."

    elif alert_type == "alert_3":
        rows = "".join([
            row("Previous Truck End", alert_data.get("previous_truck_end", "N/A")),
            row("Current Truck File", filename),
            row("Current Truck Start", alert_data.get("new_truck_start", "N/A")),
            row("Gap Duration", f"<strong style='color:#c0392b;'>{alert_data.get('gap_minutes', 'N/A')} minutes</strong> (threshold: 20 min)"),
        ])
        detail = "Excessive idle time detected between consecutive trucks."

    else:
        rows = row("Data", str(alert_data))
        detail = "Unknown alert type."

    html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;">
      <div style="background:#e74c3c;padding:16px;border-radius:6px 6px 0 0;">
        <h2 style="color:#fff;margin:0;">⚠ Bird Counter Alert</h2>
      </div>
      <div style="border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 6px 6px;">
        <p style="font-size:15px;">{detail}</p>
        <table style="border-collapse:collapse;width:100%;margin-top:12px;">
          {rows}
          {row("Alert Generated", now)}
        </table>
        <p style="margin-top:20px;font-size:12px;color:#888;">
          This is an automated alert from the Bird Counter Monitoring System.
        </p>
      </div>
    </body></html>
    """
    return html


def send_email_alert(alert_type: str, alert_data: dict, filename: str) -> dict:
    """
    Send an HTML alert email via SMTP.

    Args:
        alert_type : "alert_1", "alert_2", or "alert_3"
        alert_data : dict returned by the corresponding check function
        filename   : original CSV filename being processed

    Returns:
        {"sent": bool, "error": str|None}
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_address = os.getenv("ALERT_EMAIL_FROM", "") or smtp_user
    recipients_raw = os.getenv("ALERT_EMAIL_TO", "")

    if not smtp_user or not smtp_password:
        msg = "SMTP_USER or SMTP_PASSWORD not configured."
        logger.error(msg)
        return {"sent": False, "error": msg}

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    if not recipients:
        msg = "ALERT_EMAIL_TO is empty — no recipients configured."
        logger.error(msg)
        return {"sent": False, "error": msg}

    subject = SUBJECTS.get(alert_type, "⚠ ALERT: Bird Counter Notification")
    html_body = _build_html_body(alert_type, alert_data, filename)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_address, recipients, msg.as_string())

        logger.info(f"Email sent ({alert_type}) to {recipients} for file {filename}")
        return {"sent": True, "error": None}

    except smtplib.SMTPAuthenticationError as e:
        err = f"SMTP authentication failed: {e}"
        logger.error(err)
        return {"sent": False, "error": err}
    except smtplib.SMTPConnectError as e:
        err = f"SMTP connection failed: {e}"
        logger.error(err)
        return {"sent": False, "error": err}
    except TimeoutError as e:
        err = f"SMTP timeout: {e}"
        logger.error(err)
        return {"sent": False, "error": err}
    except Exception as e:
        err = f"Unexpected email error: {e}"
        logger.error(err)
        return {"sent": False, "error": err}
