"""Notification system for Intelligence features."""

import logging
from typing import Any
from datetime import datetime, timedelta
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send email notifications for Intelligence events."""
    
    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        from_email: str = "noreply@bimcalc.com"
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
    
    async def send_high_risk_alert(
        self,
        recipients: list[str],
        item_data: dict[str, Any],
        risk_data: dict[str, Any]
    ):
        """Send alert when item becomes high-risk.
        
        Args:
            recipients: List of email addresses
            item_data: Item details (family, type, classification)
            risk_data: Risk assessment (score, level, recommendations)
        """
        subject = f"🚨 High Risk Alert: {item_data['family']} {item_data['type_name']}"
        
        # Build HTML email
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: #fee2e2; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .score {{ font-size: 48px; font-weight: bold; color: #991b1b; }}
                .details {{ background: #f7fafc; padding: 15px; border-radius: 4px; margin: 15px 0; }}
                .recommendation {{ padding: 10px; margin: 5px 0; background: #fffbeb; border-left: 4px solid #d97706; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #2563eb; color: white; text-decoration: none; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚨 High Risk Item Detected</h1>
                <div class="score">{risk_data['score']:.0f}</div>
                <p><strong>Risk Level:</strong> {risk_data['level']}</p>
            </div>
            
            <div class="details">
                <h2>Item Details</h2>
                <p><strong>Family:</strong> {item_data['family']}</p>
                <p><strong>Type:</strong> {item_data['type_name']}</p>
                <p><strong>Classification:</strong> {item_data.get('classification_code', 'N/A')}</p>
            </div>
            
            <h2>Risk Factors</h2>
            <div class="details">
                <p><strong>Document Coverage:</strong> {risk_data['factors']['doc_coverage']['status']}</p>
                <p><strong>Classification:</strong> {risk_data['factors']['classification']['status']}</p>
                <p><strong>Age:</strong> {risk_data['factors']['age']['status']}</p>
            </div>
            
            <h2>Recommended Actions</h2>
            {"".join(f'<div class="recommendation">{rec}</div>' for rec in risk_data['recommendations'])}
            
            <p style="margin-top: 30px;">
                <a href="http://localhost:8003/risk-dashboard" class="button">View Risk Dashboard</a>
            </p>
        </body>
        </html>
        """
        
        await self._send_email(recipients, subject, html)
    
    async def send_checklist_complete(
        self,
        recipients: list[str],
        item_data: dict[str, Any],
        checklist_data: dict[str, Any]
    ):
        """Send notification when checklist is completed.
        
        Args:
            recipients: List of email addresses
            item_data: Item details
            checklist_data: Checklist summary
        """
        subject = f"✅ Checklist Complete: {item_data['family']} {item_data['type_name']}"
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: #d1fae5; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .stats {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }}
                .stat {{ background: #f7fafc; padding: 15px; border-radius: 4px; text-align: center; }}
                .stat-value {{ font-size: 32px; font-weight: bold; color: #059669; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>✅ QA Checklist Completed</h1>
                <p>Great work! All checklist items have been completed.</p>
            </div>
            
            <div class="details">
                <h2>Item Details</h2>
                <p><strong>Family:</strong> {item_data['family']}</p>
                <p><strong>Type:</strong> {item_data['type_name']}</p>
            </div>
            
            <h2>Completion Summary</h2>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{len(checklist_data['items'])}</div>
                    <div>Items Completed</div>
                </div>
                <div class="stat">
                    <div class="stat-value">100%</div>
                    <div>Complete</div>
                </div>
            </div>
            
            <p style="margin-top: 20px; color: #666;">
                Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </p>
        </body>
        </html>
        """
        
        await self._send_email(recipients, subject, html)
    
    async def send_daily_digest(
        self,
        recipients: list[str],
        digest_data: dict[str, Any]
    ):
        """Send daily summary of QA activity.
        
        Args:
            recipients: List of email addresses
            digest_data: Summary stats
        """
        subject = f"📊 Daily QA Digest - {datetime.now().strftime('%Y-%m-%d')}"
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: #dbeafe; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0; }}
                .stat {{ background: #f7fafc; padding: 15px; border-radius: 4px; text-align: center; }}
                .stat-value {{ font-size: 32px; font-weight: bold; }}
                .high {{ color: #dc2626; }}
                .medium {{ color: #d97706; }}
                .good {{ color: #059669; }}
                .section {{ margin: 20px 0; padding: 15px; background: #f7fafc; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Daily QA Digest</h1>
                <p>{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
            
            <h2>Today's Activity</h2>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value high">{digest_data.get('new_high_risk', 0)}</div>
                    <div>New High-Risk Items</div>
                </div>
                <div class="stat">
                    <div class="stat-value good">{digest_data.get('checklists_completed', 0)}</div>
                    <div>Checklists Completed</div>
                </div>
                <div class="stat">
                    <div class="stat-value medium">{digest_data.get('checklists_generated', 0)}</div>
                    <div>Checklists Generated</div>
                </div>
            </div>
            
            <div class="section">
                <h2>Overall Status</h2>
                <p><strong>Total High-Risk Items:</strong> {digest_data.get('total_high_risk', 0)}</p>
                <p><strong>Compliance Rate:</strong> {digest_data.get('compliance_percent', 0):.1f}%</p>
                <p><strong>Active Checklists:</strong> {digest_data.get('active_checklists', 0)}</p>
            </div>
            
            {f'''
            <div class="section">
                <h2>⚠️ Items Needing Attention</h2>
                <ul>
                    {"".join(f"<li>{item['family']} - {item['type_name']} (Score: {item['score']})</li>" 
                             for item in digest_data.get('top_risks', [])[:5])}
                </ul>
            </div>
            ''' if digest_data.get('top_risks') else ''}
            
            <p style="margin-top: 30px;">
                <a href="http://localhost:8003/risk-dashboard" style="display: inline-block; padding: 12px 24px; background: #2563eb; color: white; text-decoration: none; border-radius: 4px;">
                    View Risk Dashboard
                </a>
            </p>
        </body>
        </html>
        """
        
        await self._send_email(recipients, subject, html)

    async def send_ingestion_failure_alert(
        self,
        recipients: list[str],
        filename: str,
        error_message: str,
        org_id: str
    ):
        """Send alert when ingestion fails.
        
        Args:
            recipients: List of email addresses
            filename: Name of file that failed
            error_message: Error details
            org_id: Organization ID
        """
        subject = f"❌ Ingestion Failed: {filename}"
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: #fee2e2; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .details {{ background: #f7fafc; padding: 15px; border-radius: 4px; margin: 15px 0; }}
                .error {{ background: #fef2f2; color: #991b1b; padding: 15px; border-left: 4px solid #dc2626; font-family: monospace; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>❌ Data Ingestion Failed</h1>
                <p>A critical error occurred during file processing.</p>
            </div>
            
            <div class="details">
                <p><strong>File:</strong> {filename}</p>
                <p><strong>Organization:</strong> {org_id}</p>
                <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            </div>
            
            <h2>Error Details</h2>
            <div class="error">
                {error_message}
            </div>
            
            <p style="margin-top: 30px;">
                Please investigate the system logs for more details.
            </p>
        </body>
        </html>
        """
        
        await self._send_email(recipients, subject, html)
    
    async def _send_email(self, recipients: list[str], subject: str, html: str):
        """Send HTML email via SMTP.
        
        Args:
            recipients: List of email addresses
            subject: Email subject
            html: HTML content
        """
        if not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP credentials not configured, skipping email")
            return
        
        try:
            message = MIMEMultipart('alternative')
            message['From'] = self.from_email
            message['To'] = ', '.join(recipients)
            message['Subject'] = subject
            
            html_part = MIMEText(html, 'html')
            message.attach(html_part)
            
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                use_tls=True
            )
            
            logger.info(f"Email sent to {len(recipients)} recipients: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise


class SlackNotifier:
    """Send Slack notifications for Intelligence events."""
    
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url
    
    async def post_high_risk_alert(self, item_data: dict, risk_data: dict):
        """Post high-risk alert to Slack.
        
        Args:
            item_data: Item details
            risk_data: Risk assessment
        """
        if not self.webhook_url:
            logger.warning("Slack webhook not configured, skipping notification")
            return
        
        import aiohttp
        
        # Build Slack message
        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚨 High Risk Item Alert"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Item:*\n{item_data['family']} {item_data['type_name']}"},
                        {"type": "mrkdwn", "text": f"*Risk Score:*\n*{risk_data['score']:.0f}* ({risk_data['level']})"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Recommendations:*\n" + "\n".join(f"• {rec}" for rec in risk_data['recommendations'][:3])
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Dashboard"},
                            "url": "http://localhost:8003/risk-dashboard",
                            "style": "danger"
                        }
                    ]
                }
            ]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=message) as response:
                    if response.status == 200:
                        logger.info("Slack notification sent successfully")
                    else:
                        logger.error(f"Slack notification failed: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    async def post_ingestion_failure_alert(self, filename: str, error_message: str, org_id: str):
        """Post ingestion failure alert to Slack.
        
        Args:
            filename: Name of file that failed
            error_message: Error details
            org_id: Organization ID
        """
        if not self.webhook_url:
            return
        
        import aiohttp
        
        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Ingestion Failed"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*File:*\n{filename}"},
                        {"type": "mrkdwn", "text": f"*Org:*\n{org_id}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:*\n```{error_message}```"
                    }
                }
            ]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=message) as response:
                    if response.status != 200:
                        logger.error(f"Slack notification failed: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")


# Configuration management
_email_notifier: EmailNotifier | None = None
_slack_notifier: SlackNotifier | None = None


def get_email_notifier() -> EmailNotifier:
    """Get or create email notifier instance."""
    global _email_notifier
    
    if _email_notifier is None:
        import os
        _email_notifier = EmailNotifier(
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            from_email=os.getenv("SMTP_FROM", "noreply@bimcalc.com")
        )
    
    return _email_notifier


def get_slack_notifier() -> SlackNotifier:
    """Get or create Slack notifier instance."""
    global _slack_notifier
    
    if _slack_notifier is None:
        import os
        _slack_notifier = SlackNotifier(
            webhook_url=os.getenv("SLACK_WEBHOOK_URL")
        )
    
    return _slack_notifier
