# Alert Management Feature Documentation

## Overview
The Alert Management System has been added to the Streamlit dashboard to provide comprehensive alert monitoring and multi-channel notifications for the medical refrigerator monitoring system.

## Alert Levels

The system uses a 4-level color-coded alert system:

### 🟢 **GREEN - Normal**
- Status: Device operating normally
- Temperature: Within normal range (2°C - 8°C)
- No action required

### 🟡 **YELLOW - Potential Issue**
- Status: Minor issues detected
- Temperature: Slightly above/below optimal range
- Recommended: Monitor closely

### 🟠 **ORANGE - High Risk**
- Status: Significant issues detected
- Temperature: Approaching unsafe range (7°C - 9°C)
- Action: Investigate and resolve within hours

### 🔴 **RED - Immediate Action**
- Status: Critical issues detected
- Temperature: Dangerous range (>10°C or <1°C)
- Vaccine Spoilage Risk: High
- Action: Immediate intervention required

## Notification Channels

### Supported Channels

1. **📧 Email**
   - Sends detailed alert emails to configured recipient
   - Best for: Permanent record, detailed information
   - Enabled by default

2. **💬 SMS**
   - Sends text message alerts
   - Best for: Quick notifications on-the-go
   - Enabled by default

3. **💚 WhatsApp**
   - Sends formatted alert messages via WhatsApp
   - Best for: Real-time notifications with formatting
   - Environment variable: `ALERT_WHATSAPP_RECIPIENT`

4. **🔵 Microsoft Teams**
   - Sends formatted cards to Teams channel
   - Best for: Team collaboration and tracking
   - Environment variable: `ALERT_TEAMS_WEBHOOK`
   - Requires webhook URL

5. **⚫ Slack**
   - Sends formatted messages to Slack channel
   - Best for: Integration with existing workflows
   - Environment variable: `ALERT_SLACK_WEBHOOK`
   - Requires webhook URL

## Configuration

### Environment Variables

```bash
# Email Configuration
ALERT_EMAIL_RECIPIENT=ops-team@example.com

# SMS Configuration
ALERT_SMS_RECIPIENT=+1-800-000-0000

# WhatsApp Configuration
ALERT_WHATSAPP_RECIPIENT=+1-800-000-0000

# Microsoft Teams Webhook
ALERT_TEAMS_WEBHOOK=https://outlook.webhook.office.com/webhookb2/...

# Slack Webhook
ALERT_SLACK_WEBHOOK=https://hooks.slack.com/services/T00000000/B00000000/XX...

# Notification Log File
ALERT_NOTIFICATION_LOG=alert_notifications.log
```

## Alert Management Interface

### Features in Streamlit Dashboard

#### 1. **Alert Level Quick Reference**
   - Visual color-coded cards showing all 4 alert levels
   - Helps operators understand alert severity at a glance

#### 2. **Alert Configuration**
   - Select specific refrigerator to monitor
   - Configure alert level thresholds
   - Choose notification channels

#### 3. **Active Alerts Tab**
   - **All Alerts**: Shows all active alerts
   - **Critical**: Filtered RED level alerts only
   - **Warnings**: Filtered ORANGE and YELLOW alerts
   - **Info**: GREEN status alerts

#### 4. **Alert Statistics**
   - Real-time count of alerts by severity level
   - Quick metrics for dashboard overview

#### 5. **Notification Settings**
   - Configure email recipient address
   - Configure SMS recipient number
   - Enable/disable channels

#### 6. **Test Alert System**
   - Send test alerts to verify configuration
   - View example alert format
   - Confirm all channels are working

## Example Alert Notification

```
ALERT

Refrigerator: REF005
Temperature: 9.4°C
Humidity: 65%
Vaccine Spoilage Risk: High
Alert Level: RED - Immediate Action
Status: 🔴 CRITICAL

Timestamp: 2024-12-04 14:30:45
Device ID: REF005

Notification sent via:
- 📧 Email
- 💬 SMS
- 💚 WhatsApp
- 🔵 Microsoft Teams
- ⚫ Slack
```

## Alert Detection Logic

### Temperature-Based Alerts

- **GREEN (Normal)**: 2°C - 8°C
- **YELLOW (Potential Issue)**: 1°C - 2°C or 8°C - 9°C
- **ORANGE (High Risk)**: 0°C - 1°C or 9°C - 10°C
- **RED (Immediate Action)**: Below 0°C or above 10°C

### Other Triggers

- Door left open for extended period
- Power loss detected
- Humidity out of range
- Compressor failure
- Sensor malfunction

## Integration with Backend

### Updated Endpoints

The backend now supports:

```python
GET /devices/{device_id}/alerts
# Returns list of active alerts for a device

GET /devices/alerts/all
# Returns all alerts across all devices

POST /devices/{device_id}/alerts/test
# Sends test alert notification
```

## Notifications Module

### Updated `notifications.py`

The notifications module now includes:

- `send_email_alert()` - Email notification
- `send_sms_alert()` - SMS notification
- `send_whatsapp_alert()` - WhatsApp notification
- `send_teams_alert()` - Microsoft Teams notification
- `send_slack_alert()` - Slack notification
- `notify_alert()` - Send to multiple channels
- `get_alert_level_color()` - Color mapping for alert levels

### Usage Example

```python
from backend.app.notifications import notify_alert
from backend.app.schemas import AlertStatus, TelemetryReading

reading = TelemetryReading(...)
alert = AlertStatus(
    device_id="REF005",
    alert_level="RED",
    message="Temperature exceeded safe range",
    triggered_at=datetime.now()
)

channels = {
    "email": True,
    "sms": True,
    "whatsapp": True,
    "teams": False,
    "slack": False
}

result = notify_alert(reading, alert, channels)
```

## Best Practices

1. **Enable Email by Default**: Critical alerts should always trigger emails
2. **Use SMS for High Priority**: Reserve SMS for RED level alerts
3. **Team Collaboration**: Use Teams for organizational workflows
4. **Audit Trail**: Monitor `alert_notifications.log` for compliance
5. **Test Regularly**: Use test alert feature to verify system functionality
6. **Escalation**: Configure escalation paths for RED level alerts

## Troubleshooting

### Alerts Not Showing
- Verify backend connection
- Check device ID configuration
- Confirm alert thresholds are set correctly

### Notifications Not Sending
- Verify environment variables are set
- Check network connectivity
- Review `alert_notifications.log` for errors
- Test webhook URLs for Teams/Slack

### Missing Channels
- Ensure webhook URLs are correctly configured
- Verify API access permissions
- Check rate limits on external services

## Future Enhancements

- Scheduled alert digests
- Custom alert rules builder
- Alert snoozing/suppression
- Historical alert analytics
- Integration with IFTTT
- Mobile app push notifications
