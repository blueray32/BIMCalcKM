import httpx
import logging
from bimcalc.config import get_config

logger = logging.getLogger(__name__)

async def send_slack_notification(message: str, blocks: list[dict] | None = None) -> bool:
    """Send a notification to Slack via webhook.
    
    Args:
        message: The fallback text message.
        blocks: Optional list of Slack Block Kit blocks for rich formatting.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    config = get_config()
    
    # Check if notifications are enabled and webhook URL is configured
    if not config.notifications.enabled:
        logger.debug("slack_notifications_disabled_by_config")
        return False
        
    if not config.notifications.slack_webhook_url:
        logger.warning("slack_webhook_url_missing: Notifications enabled but no webhook URL configured")
        return False

    payload = {"text": message}
    if blocks:
        payload["blocks"] = blocks

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(config.notifications.slack_webhook_url, json=payload)
            if response.status_code != 200:
                logger.error(
                    "slack_notification_failed: status=%s response=%s", 
                    response.status_code, 
                    response.text
                )
                return False
            
            logger.info("slack_notification_sent")
            return True
    except Exception as e:
        logger.error("slack_notification_error: %s", str(e))
        return False
