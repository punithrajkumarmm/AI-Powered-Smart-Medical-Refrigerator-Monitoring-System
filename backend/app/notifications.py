import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .schemas import AlertStatus, TelemetryReading

# Email Configuration
EMAIL_RECIPIENT = os.getenv("ALERT_EMAIL_RECIPIENT", "ops-team@example.com")
EMAIL_SENDER = os.getenv("ALERT_EMAIL_SENDER", "noreply@medicalrefrig.com")
SMTP_SERVER = os.getenv("ALERT_SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("ALERT_SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("ALERT_SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("ALERT_SMTP_PASSWORD", "")

# SMS Configuration
SMS_RECIPIENT = os.getenv("ALERT_SMS_RECIPIENT", "+10000000000")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# WhatsApp Configuration
WHATSAPP_RECIPIENT = os.getenv("ALERT_WHATSAPP_RECIPIENT", "+10000000000")

# Teams Configuration
TEAMS_WEBHOOK = os.getenv("ALERT_TEAMS_WEBHOOK", "")

# Slack Configuration
SLACK_WEBHOOK = os.getenv("ALERT_SLACK_WEBHOOK", "")

# Notification Log
NOTIFICATION_LOG = os.getenv("ALERT_NOTIFICATION_LOG", "alert_notifications.log")


def format_alert_message(reading: TelemetryReading, alert: AlertStatus) -> str:
    return (
        f"[{alert.triggered_at.isoformat()}] ALERT for {alert.device_id}: {alert.message} "
        f"(temp={reading.temperature_c}°C, humidity={reading.humidity_pct}%, door_open={reading.door_open}, power_ok={reading.power_ok})"
    )


def get_alert_level_color(alert: AlertStatus) -> str:
    """Return color code based on alert level"""
    level = alert.alert_level.upper()
    if "RED" in level or "CRITICAL" in level:
        return "#ef4444"  # Red
    elif "ORANGE" in level or "HIGH" in level:
        return "#f97316"  # Orange
    elif "YELLOW" in level or "WARNING" in level:
        return "#eab308"  # Yellow
    else:
        return "#10b981"  # Green


def send_email_alert(reading: TelemetryReading, alert: AlertStatus) -> dict:
    """Send alert via Email using SMTP"""
    try:
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            log_notification("EMAIL", "FAILED", "SMTP credentials not configured")
            return {"success": False, "error": "SMTP credentials not configured"}
        
        # Create email message
        message = MIMEMultipart("alternative")
        message["Subject"] = f"🚨 Refrigerator Alert: {alert.device_id}"
        message["From"] = EMAIL_SENDER
        message["To"] = EMAIL_RECIPIENT

        # Plain text version
        text = f"""
REFRIGERATOR ALERT NOTIFICATION

Device ID: {alert.device_id}
Alert Level: {alert.alert_level}
Message: {alert.message}

Current Status:
- Temperature: {reading.temperature_c}°C
- Humidity: {reading.humidity_pct}%
- Door Open: {'Yes' if reading.door_open else 'No'}
- Power OK: {'Yes' if reading.power_ok else 'No'}

Timestamp: {alert.triggered_at.isoformat()}

Please take appropriate action to resolve this issue.
        """

        # HTML version
        html = f"""
        <html>
            <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: #ef4444; color: white; padding: 20px; border-radius: 10px 10px 0 0;">
                        <h2 style="margin: 0;">🚨 Refrigerator Alert</h2>
                        <p style="margin: 10px 0 0 0;">{alert.device_id}</p>
                    </div>
                    <div style="background-color: #f5f5f5; padding: 20px; border-radius: 0 0 10px 10px;">
                        <p><strong>Alert Level:</strong> {alert.alert_level}</p>
                        <p><strong>Message:</strong> {alert.message}</p>
                        
                        <hr>
                        
                        <h3>Current Status:</h3>
                        <ul>
                            <li><strong>Temperature:</strong> {reading.temperature_c}°C</li>
                            <li><strong>Humidity:</strong> {reading.humidity_pct}%</li>
                            <li><strong>Door Open:</strong> {'Yes' if reading.door_open else 'No'}</li>
                            <li><strong>Power OK:</strong> {'Yes' if reading.power_ok else 'No'}</li>
                        </ul>
                        
                        <p><small>Time: {alert.triggered_at.isoformat()}</small></p>
                    </div>
                </div>
            </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)

        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
        
        log_notification("EMAIL", "SUCCESS", f"Sent to {EMAIL_RECIPIENT}")
        return {"success": True, "recipient": EMAIL_RECIPIENT}
        
    except Exception as e:
        error_msg = str(e)
        log_notification("EMAIL", "FAILED", error_msg)
        return {"success": False, "error": error_msg}


def send_sms_alert(reading: TelemetryReading, alert: AlertStatus) -> dict:
    """Send alert via SMS using Twilio"""
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
            log_notification("SMS", "FAILED", "Twilio credentials not configured")
            return {"success": False, "error": "Twilio credentials not configured"}
        
        from twilio.rest import Client
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message_text = (
            f"🚨 ALERT: {alert.device_id}\n"
            f"{alert.message}\n"
            f"Temp: {reading.temperature_c}°C | Humidity: {reading.humidity_pct}%\n"
            f"Time: {alert.triggered_at.isoformat()}"
        )
        
        message = client.messages.create(
            body=message_text,
            from_=TWILIO_PHONE_NUMBER,
            to=SMS_RECIPIENT
        )
        
        log_notification("SMS", "SUCCESS", f"Sent to {SMS_RECIPIENT} (SID: {message.sid})")
        return {"success": True, "recipient": SMS_RECIPIENT, "sid": message.sid}
        
    except ImportError:
        error_msg = "Twilio library not installed. Run: pip install twilio"
        log_notification("SMS", "FAILED", error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = str(e)
        log_notification("SMS", "FAILED", error_msg)
        return {"success": False, "error": error_msg}


def send_whatsapp_alert(reading: TelemetryReading, alert: AlertStatus) -> dict:
    """Send alert via WhatsApp using Twilio"""
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
            log_notification("WHATSAPP", "FAILED", "Twilio credentials not configured")
            return {"success": False, "error": "Twilio credentials not configured"}
        
        from twilio.rest import Client
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message_text = (
            f"🚨 ALERT: {alert.device_id}\n"
            f"{alert.message}\n"
            f"Temp: {reading.temperature_c}°C | Humidity: {reading.humidity_pct}%\n"
            f"Time: {alert.triggered_at.isoformat()}"
        )
        
        message = client.messages.create(
            body=message_text,
            from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
            to=f"whatsapp:{WHATSAPP_RECIPIENT}"
        )
        
        log_notification("WHATSAPP", "SUCCESS", f"Sent to {WHATSAPP_RECIPIENT}")
        return {"success": True, "recipient": WHATSAPP_RECIPIENT}
        
    except Exception as e:
        error_msg = str(e)
        log_notification("WHATSAPP", "FAILED", error_msg)
        return {"success": False, "error": error_msg}


def send_teams_alert(reading: TelemetryReading, alert: AlertStatus) -> dict:
    """Send alert via Microsoft Teams"""
    try:
        if not TEAMS_WEBHOOK:
            log_notification("TEAMS", "FAILED", "Teams webhook not configured")
            return {"success": False, "error": "Teams webhook not configured"}
        
        import urllib.request
        import json
        
        color = get_alert_level_color(alert)
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"Refrigerator Alert - {alert.device_id}",
            "themeColor": color.lstrip("#"),
            "sections": [
                {
                    "activityTitle": f"🚨 {alert.device_id} - Alert",
                    "activitySubtitle": alert.message,
                    "facts": [
                        {"name": "Alert Level", "value": alert.alert_level},
                        {"name": "Temperature", "value": f"{reading.temperature_c}°C"},
                        {"name": "Humidity", "value": f"{reading.humidity_pct}%"},
                        {"name": "Door Open", "value": "Yes" if reading.door_open else "No"},
                        {"name": "Power OK", "value": "Yes" if reading.power_ok else "No"},
                        {"name": "Timestamp", "value": alert.triggered_at.isoformat()},
                    ],
                    "markdown": True,
                }
            ],
        }
        
        req = urllib.request.Request(
            TEAMS_WEBHOOK,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                log_notification("TEAMS", "SUCCESS", "Message posted to Teams")
                return {"success": True}
        
        return {"success": False, "error": "Teams API returned non-200 status"}
        
    except Exception as e:
        error_msg = str(e)
        log_notification("TEAMS", "FAILED", error_msg)
        return {"success": False, "error": error_msg}


def send_slack_alert(reading: TelemetryReading, alert: AlertStatus) -> dict:
    """Send alert via Slack"""
    try:
        if not SLACK_WEBHOOK:
            log_notification("SLACK", "FAILED", "Slack webhook not configured")
            return {"success": False, "error": "Slack webhook not configured"}
        
        import urllib.request
        import json
        
        color = get_alert_level_color(alert)
        payload = {
            "text": f"🚨 Refrigerator Alert - {alert.device_id}",
            "attachments": [
                {
                    "color": color,
                    "title": alert.message,
                    "fields": [
                        {"title": "Device ID", "value": alert.device_id, "short": True},
                        {"title": "Alert Level", "value": alert.alert_level, "short": True},
                        {"title": "Temperature", "value": f"{reading.temperature_c}°C", "short": True},
                        {"title": "Humidity", "value": f"{reading.humidity_pct}%", "short": True},
                        {"title": "Door Open", "value": "Yes" if reading.door_open else "No", "short": True},
                        {"title": "Power OK", "value": "Yes" if reading.power_ok else "No", "short": True},
                        {"title": "Timestamp", "value": alert.triggered_at.isoformat(), "short": False},
                    ],
                }
            ],
        }
        
        req = urllib.request.Request(
            SLACK_WEBHOOK,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                log_notification("SLACK", "SUCCESS", "Message posted to Slack")
                return {"success": True}
        
        return {"success": False, "error": "Slack API returned non-200 status"}
        
    except Exception as e:
        error_msg = str(e)
        log_notification("SLACK", "FAILED", error_msg)
        return {"success": False, "error": error_msg}


def log_notification(channel: str, status: str, detail: str) -> None:
    """Log notification attempts to file"""
    try:
        with open(NOTIFICATION_LOG, "a", encoding="utf-8") as log_file:
            timestamp = datetime.now().isoformat()
            log_file.write(f"[{timestamp}] {channel} - {status}: {detail}\n")
    except Exception:
        pass  # Silent fail for logging


def notify_alert(
    reading: TelemetryReading,
    alert: AlertStatus,
    channels: dict[str, bool] | None = None,
) -> dict:
    """
    Send alert to configured notification channels
    
    Args:
        reading: Telemetry reading data
        alert: Alert status
        channels: Dict with notification channel preferences
                 Example: {"email": True, "sms": True, "whatsapp": False, "teams": False, "slack": False}
    
    Returns:
        Dictionary with results from each channel
    """
    if channels is None:
        channels = {"email": True, "sms": True, "whatsapp": False, "teams": False, "slack": False}
    
    result = {}
    
    if channels.get("email", True):
        result["email"] = send_email_alert(reading, alert)
    
    if channels.get("sms", True):
        result["sms"] = send_sms_alert(reading, alert)
    
    if channels.get("whatsapp", False):
        result["whatsapp"] = send_whatsapp_alert(reading, alert)
    
    if channels.get("teams", False):
        result["teams"] = send_teams_alert(reading, alert)
    
    if channels.get("slack", False):
        result["slack"] = send_slack_alert(reading, alert)
    
    return result
