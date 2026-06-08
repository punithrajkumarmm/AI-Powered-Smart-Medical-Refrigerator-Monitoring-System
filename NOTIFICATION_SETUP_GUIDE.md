# Alert Notification Setup Guide

## Quick Setup Instructions

### Step 1: Install Twilio Package

```bash
cd backend
pip install twilio
```

### Step 2: Create `.env` File

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

---

## Email Setup (Gmail - Recommended for testing)

### 1. **Enable 2-Factor Authentication**
- Go to: https://myaccount.google.com/security
- Enable 2-Step Verification

### 2. **Generate App Password**
- Go to: https://myaccount.google.com/apppasswords
- Select "Mail" and "Windows Computer" (or your device)
- Google will generate a 16-character password

### 3. **Update `.env`**

```env
ALERT_EMAIL_RECIPIENT=ops-team@example.com
ALERT_EMAIL_SENDER=your-email@gmail.com
ALERT_SMTP_SERVER=smtp.gmail.com
ALERT_SMTP_PORT=587
ALERT_SMTP_USERNAME=your-email@gmail.com
ALERT_SMTP_PASSWORD=xxxx xxxx xxxx xxxx
```

### 4. **Test Email**
```bash
# Run the test in the Streamlit dashboard
# Alert Management → Send Test Alert
```

---

## SMS Setup (Twilio)

### 1. **Create Twilio Account**
- Sign up (free trial): https://www.twilio.com/try-twilio
- Verify your phone number

### 2. **Get Your Credentials**
- Go to: https://console.twilio.com
- Find your **Account SID** (starts with `AC`)
- Find your **Auth Token**

### 3. **Get a Twilio Phone Number**
- In the Twilio Console, go to **Phone Numbers**
- Buy a number (trial account starts with $15 free credit)
- Example: +1 (415) 555-0123

### 4. **Update `.env`**

```env
ALERT_SMS_RECIPIENT=+1234567890
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here_28_chars
TWILIO_PHONE_NUMBER=+1234567890
```

### 5. **Test SMS**
```bash
# Run the test in the Streamlit dashboard
# Alert Management → Send Test Alert
```

### Trial Account Note
⚠️ Trial Twilio accounts can only send SMS to verified phone numbers. To unlock sending to any number:
- Add verified phone numbers in Twilio Console
- Upgrade to a paid account ($1/month minimum)

---

## WhatsApp Setup (Twilio)

### 1. **Prerequisites**
- Twilio Account (same as SMS)
- Twilio WhatsApp Sandbox enabled

### 2. **Enable WhatsApp Sandbox**
- Go to: https://console.twilio.com/us/account/messaging/services
- Create a Messaging Service
- Add WhatsApp Channel
- Enable WhatsApp Sandbox

### 3. **Update `.env`**

```env
ALERT_WHATSAPP_RECIPIENT=+1234567890
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890
```

### 4. **Opt In to WhatsApp**
- From your phone, send a message to your Twilio WhatsApp number:
  ```
  join [sandbox-name]
  ```
- You'll receive a confirmation

---

## Microsoft Teams Setup

### 1. **Create Incoming Webhook**
- Go to your Teams channel
- Click **"..."** (More options)
- Select **Connectors**
- Search for **"Incoming Webhook"**
- Click **Configure**

### 2. **Configure Webhook**
- Give it a name: "Refrigerator Alerts"
- Optionally upload an image
- Click **Create**
- Copy the webhook URL

### 3. **Update `.env`**

```env
ALERT_TEAMS_WEBHOOK=https://outlook.webhook.office.com/webhookb2/xxxxx...
```

### 4. **Test**
- Send a test alert from Streamlit dashboard
- Alert should appear in Teams channel

---

## Slack Setup

### 1. **Create Incoming Webhook**
- Go to: https://api.slack.com/apps
- Click **"Create New App"** → **"From scratch"**
- Name: "Refrigerator Monitor"
- Select your workspace
- Click **Create App**

### 2. **Enable Incoming Webhooks**
- Go to **Incoming Webhooks** in left sidebar
- Toggle to **"On"**
- Click **"Add New Webhook to Workspace"**

### 3. **Select Channel**
- Choose a channel (e.g., #alerts)
- Click **Allow**
- Copy the **Webhook URL**

### 4. **Update `.env`**

```env
ALERT_SLACK_WEBHOOK=https://hooks.slack.com/services/T00000000/B00000000/XXXX...
```

### 5. **Test**
- Send a test alert from Streamlit dashboard
- Alert should appear in Slack channel

---

## Verification Checklist

- [ ] Email configured and tested
- [ ] SMS configured and tested (if using Twilio)
- [ ] WhatsApp configured (optional)
- [ ] Teams webhook configured (optional)
- [ ] Slack webhook configured (optional)
- [ ] `.env` file created with all credentials
- [ ] Backend restarted with updated environment variables

---

## Troubleshooting

### Email not sending
```
❌ SMTP credentials not configured
```
**Solution:** Make sure `ALERT_SMTP_USERNAME` and `ALERT_SMTP_PASSWORD` are set in `.env`

```
❌ SMTP authentication failed
```
**Solution:** 
- If using Gmail, make sure you generated an App Password (not your regular password)
- Check that 2-Factor Authentication is enabled

### SMS not sending
```
❌ Twilio credentials not configured
```
**Solution:** Fill in `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER`

```
❌ Permission to send an SMS has not been granted
```
**Solution:** Trial accounts need verified numbers. Add the recipient phone number in Twilio Console.

### Checking Logs

View notification logs:
```bash
cat alert_notifications.log
```

Example successful log entry:
```
[2026-06-04T14:30:45.123456] EMAIL - SUCCESS: Sent to ops-team@example.com
[2026-06-04T14:30:46.234567] SMS - SUCCESS: Sent to +1234567890 (SID: SMxxxxx)
```

---

## Environment Variables Reference

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| ALERT_EMAIL_RECIPIENT | Email to receive alerts | Yes | ops-team@example.com |
| ALERT_EMAIL_SENDER | Email sender address | Yes | noreply@medicalrefrig.com |
| ALERT_SMTP_SERVER | SMTP server | Yes | smtp.gmail.com |
| ALERT_SMTP_PORT | SMTP port | Yes | 587 |
| ALERT_SMTP_USERNAME | SMTP username | Yes | your-email@gmail.com |
| ALERT_SMTP_PASSWORD | SMTP password | Yes | xxxx xxxx xxxx xxxx |
| ALERT_SMS_RECIPIENT | Phone number for SMS | No | +1234567890 |
| TWILIO_ACCOUNT_SID | Twilio Account SID | No* | ACxxx... |
| TWILIO_AUTH_TOKEN | Twilio Auth Token | No* | xxx... |
| TWILIO_PHONE_NUMBER | Twilio phone number | No* | +1234567890 |
| ALERT_TEAMS_WEBHOOK | Teams webhook URL | No | https://outlook.webhook... |
| ALERT_SLACK_WEBHOOK | Slack webhook URL | No | https://hooks.slack.com... |

*Required only if SMS notifications are enabled

---

## Testing Notifications

Once configured, test each channel from the **Alert Management** dashboard:

1. Open Streamlit: `http://localhost:8501`
2. Navigate to **Alert Management** tab
3. Click **"Send Test Alert"**
4. Check that notifications arrive in:
   - ✉️ Email inbox
   - 📱 SMS (your phone)
   - 💬 WhatsApp (if enabled)
   - 👥 Teams channel (if enabled)
   - 🎯 Slack channel (if enabled)

---

## Production Deployment

### Email
- Use a dedicated email service like SendGrid, Mailgun, or AWS SES
- Use strong, unique app passwords
- Enable email authentication (SPF, DKIM, DMARC)

### SMS
- Upgrade Twilio account for unlimited SMS
- Consider batch discounts for high-volume alerts
- Implement alert throttling to avoid excessive messages

### Teams/Slack
- Use separate webhooks for different severity levels
- Implement formatting for better visibility
- Set up threading for related alerts

