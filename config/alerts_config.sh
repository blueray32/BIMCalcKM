#!/bin/bash
# BIMCalc Alerts Configuration
# Configure notification channels for system alerts

# ===========================================
# Email Notifications
# ===========================================
ENABLE_EMAIL=false  # Set to true to enable email alerts

# Email settings (requires 'mail' or 'sendmail' command)
EMAIL_TO="your.email@example.com"
EMAIL_FROM="bimcalc@$(hostname)"

# For Gmail/SMTP (optional - requires additional setup)
# SMTP_HOST="smtp.gmail.com"
# SMTP_PORT="587"
# SMTP_USER="your.email@gmail.com"
# SMTP_PASSWORD="your-app-password"

# ===========================================
# Slack Notifications
# ===========================================
ENABLE_SLACK=false  # Set to true to enable Slack alerts

# Slack webhook URL
# Get from: https://api.slack.com/messaging/webhooks
SLACK_WEBHOOK_URL=""

# Slack channel (optional - webhook default used if not specified)
SLACK_CHANNEL="#bimcalc-alerts"

# ===========================================
# Generic Webhook
# ===========================================
ENABLE_WEBHOOK=false  # Set to true to enable webhook alerts

# Webhook URL (for PagerDuty, OpsGenie, custom endpoints, etc.)
WEBHOOK_URL=""

# Webhook authentication (optional)
# WEBHOOK_AUTH_HEADER="Authorization: Bearer your-token"

# ===========================================
# Alert Levels
# ===========================================
# Which levels trigger notifications?
ALERT_ON_CRITICAL=true   # Always alert on critical issues
ALERT_ON_WARNING=true    # Alert on warnings
ALERT_ON_INFO=false      # Don't alert on info messages

# ===========================================
# Alert Throttling
# ===========================================
# Prevent alert spam
MIN_ALERT_INTERVAL=3600  # Minimum seconds between alerts (1 hour)

# ===========================================
# Log Settings
# ===========================================
LOG_FILE="$(dirname "$0")/../logs/alerts.log"

# ===========================================
# Health Check Schedule
# ===========================================
# How often to run health checks
HEALTH_CHECK_INTERVAL="hourly"  # hourly, daily, or cron expression

# ===========================================
# Examples for Common Services
# ===========================================

# Example: Gmail with App Password
# 1. Go to https://myaccount.google.com/apppasswords
# 2. Create an app password
# 3. Configure:
#    ENABLE_EMAIL=true
#    EMAIL_TO="admin@company.com"
#    SMTP_USER="your.email@gmail.com"
#    SMTP_PASSWORD="your-app-password"

# Example: Slack
# 1. Go to https://api.slack.com/messaging/webhooks
# 2. Create incoming webhook
# 3. Copy webhook URL
# 4. Configure:
#    ENABLE_SLACK=true
#    SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Example: PagerDuty
# 1. Get Events API v2 integration key
# 2. Configure:
#    ENABLE_WEBHOOK=true
#    WEBHOOK_URL="https://events.pagerduty.com/v2/enqueue"
#    WEBHOOK_AUTH_HEADER="Authorization: Token token=your-integration-key"

# Example: Microsoft Teams
# 1. Add incoming webhook connector to channel
# 2. Copy webhook URL
# 3. Configure:
#    ENABLE_WEBHOOK=true
#    WEBHOOK_URL="https://outlook.office.com/webhook/..."

# ===========================================
# Quick Setup Examples
# ===========================================

# Uncomment one of these blocks to get started:

# --- Email Only ---
# ENABLE_EMAIL=true
# EMAIL_TO="admin@company.com"

# --- Slack Only ---
# ENABLE_SLACK=true
# SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# --- Both Email and Slack ---
# ENABLE_EMAIL=true
# EMAIL_TO="admin@company.com"
# ENABLE_SLACK=true
# SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

echo "✅ BIMCalc alerts configuration loaded"
echo "   Email: $ENABLE_EMAIL"
echo "   Slack: $ENABLE_SLACK"
echo "   Webhook: $ENABLE_WEBHOOK"
