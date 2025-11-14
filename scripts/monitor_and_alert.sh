#!/bin/bash
# BIMCalc Monitoring with Alerts
# Runs health check and sends alerts if issues detected

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Run health check and capture output
HEALTH_OUTPUT=$(mktemp)
HEALTH_EXIT_CODE=0

"$SCRIPT_DIR/health_check.sh" > "$HEALTH_OUTPUT" 2>&1 || HEALTH_EXIT_CODE=$?

# Display health check output
cat "$HEALTH_OUTPUT"

# Send alerts based on exit code
case $HEALTH_EXIT_CODE in
    0)
        # Healthy - no alert needed
        echo "✅ System healthy - no alerts sent"
        ;;
    1)
        # Warning
        echo "⚠️  Warning detected - sending alert..."
        ISSUES=$(grep "⚠️ " "$HEALTH_OUTPUT" | head -5)
        "$SCRIPT_DIR/send_alert.sh" "WARNING" "BIMCalc System Warning" "$ISSUES"
        ;;
    2)
        # Critical
        echo "🚨 Critical issue detected - sending alert..."
        ISSUES=$(grep "❌" "$HEALTH_OUTPUT" | head -5)
        "$SCRIPT_DIR/send_alert.sh" "CRITICAL" "BIMCalc System Critical" "$ISSUES"
        ;;
    *)
        # Unknown
        echo "❓ Unknown status - sending alert..."
        "$SCRIPT_DIR/send_alert.sh" "WARNING" "BIMCalc Health Check Failed" "Exit code: $HEALTH_EXIT_CODE"
        ;;
esac

# Cleanup
rm "$HEALTH_OUTPUT"

exit $HEALTH_EXIT_CODE
