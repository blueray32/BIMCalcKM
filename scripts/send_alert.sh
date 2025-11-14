#!/bin/bash
# BIMCalc Alert Notification Script
# Supports: Email, Slack, Webhook, and Log

ALERT_LEVEL="$1"  # INFO, WARNING, CRITICAL
ALERT_MESSAGE="$2"
ALERT_DETAILS="${3:-}"

# Load configuration
CONFIG_FILE="$(dirname "$0")/../config/alerts_config.sh"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Defaults
ENABLE_EMAIL=${ENABLE_EMAIL:-false}
ENABLE_SLACK=${ENABLE_SLACK:-false}
ENABLE_WEBHOOK=${ENABLE_WEBHOOK:-false}
LOG_FILE="${LOG_FILE:-$(dirname "$0")/../logs/alerts.log}"

# Timestamp
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Log to file (always)
mkdir -p "$(dirname "$LOG_FILE")"
echo "[$TIMESTAMP] [$ALERT_LEVEL] $ALERT_MESSAGE" >> "$LOG_FILE"
if [ -n "$ALERT_DETAILS" ]; then
    echo "  Details: $ALERT_DETAILS" >> "$LOG_FILE"
fi

# Console output
echo "========================================="
echo "BIMCalc Alert"
echo "========================================="
echo "Time:    $TIMESTAMP"
echo "Level:   $ALERT_LEVEL"
echo "Message: $ALERT_MESSAGE"
if [ -n "$ALERT_DETAILS" ]; then
    echo "Details: $ALERT_DETAILS"
fi
echo ""

# Choose emoji based on level
case "$ALERT_LEVEL" in
    CRITICAL)
        EMOJI="🚨"
        COLOR="#ff0000"
        ;;
    WARNING)
        EMOJI="⚠️"
        COLOR="#ffaa00"
        ;;
    INFO)
        EMOJI="ℹ️"
        COLOR="#0099ff"
        ;;
    SUCCESS)
        EMOJI="✅"
        COLOR="#00ff00"
        ;;
    *)
        EMOJI="📢"
        COLOR="#999999"
        ;;
esac

# Send Email Alert
if [ "$ENABLE_EMAIL" = "true" ]; then
    echo "📧 Sending email alert..."

    SUBJECT="$EMOJI BIMCalc Alert: $ALERT_LEVEL - $ALERT_MESSAGE"
    BODY="BIMCalc Alert

Time: $TIMESTAMP
Level: $ALERT_LEVEL
Message: $ALERT_MESSAGE

$ALERT_DETAILS

---
BIMCalc Monitoring System
"

    if command -v mail >/dev/null 2>&1; then
        echo "$BODY" | mail -s "$SUBJECT" "${EMAIL_TO:-admin@example.com}"
        echo "✅ Email sent to ${EMAIL_TO:-admin@example.com}"
    elif command -v sendmail >/dev/null 2>&1; then
        echo -e "Subject: $SUBJECT\n\n$BODY" | sendmail "${EMAIL_TO:-admin@example.com}"
        echo "✅ Email sent via sendmail"
    else
        echo "⚠️  Email command not available (install 'mail' or 'sendmail')"
    fi
fi

# Send Slack Alert
if [ "$ENABLE_SLACK" = "true" ] && [ -n "$SLACK_WEBHOOK_URL" ]; then
    echo "💬 Sending Slack alert..."

    SLACK_PAYLOAD=$(cat <<EOF
{
    "text": "$EMOJI *BIMCalc Alert: $ALERT_LEVEL*",
    "attachments": [
        {
            "color": "$COLOR",
            "fields": [
                {
                    "title": "Message",
                    "value": "$ALERT_MESSAGE",
                    "short": false
                },
                {
                    "title": "Time",
                    "value": "$TIMESTAMP",
                    "short": true
                },
                {
                    "title": "Level",
                    "value": "$ALERT_LEVEL",
                    "short": true
                }
            ],
            "footer": "BIMCalc Monitoring"
        }
    ]
}
EOF
)

    if curl -X POST -H 'Content-type: application/json' \
        --data "$SLACK_PAYLOAD" \
        "$SLACK_WEBHOOK_URL" >/dev/null 2>&1; then
        echo "✅ Slack notification sent"
    else
        echo "❌ Failed to send Slack notification"
    fi
fi

# Send Generic Webhook Alert
if [ "$ENABLE_WEBHOOK" = "true" ] && [ -n "$WEBHOOK_URL" ]; then
    echo "🔔 Sending webhook alert..."

    WEBHOOK_PAYLOAD=$(cat <<EOF
{
    "timestamp": "$TIMESTAMP",
    "level": "$ALERT_LEVEL",
    "message": "$ALERT_MESSAGE",
    "details": "$ALERT_DETAILS",
    "system": "BIMCalc"
}
EOF
)

    if curl -X POST -H 'Content-type: application/json' \
        --data "$WEBHOOK_PAYLOAD" \
        "$WEBHOOK_URL" >/dev/null 2>&1; then
        echo "✅ Webhook notification sent"
    else
        echo "❌ Failed to send webhook notification"
    fi
fi

echo "Alert logged to: $LOG_FILE"
echo ""
