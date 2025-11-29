"""Email notification service for BIMCalc.

Supports sending project reports and alerts via SMTP.
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import List, Dict, Any
import os

from jinja2 import Environment, FileSystemLoader


class EmailService:
    """Service for sending emails with template support."""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_user)
        
        # Setup Jinja2 for email templates
        template_dir = Path(__file__).parent / "templates"
        template_dir.mkdir(exist_ok=True)
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
    
    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_body: str,
        text_body: str | None = None,
        attachments: List[tuple[str, bytes]] | None = None
    ) -> bool:
        """Send an email with optional attachments.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject line
            html_body: HTML content of the email
            text_body: Plain text fallback (optional)
            attachments: List of (filename, file_bytes) tuples
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.smtp_user or not self.smtp_password:
            print("WARNING: SMTP credentials not configured. Email not sent.")
            print(f"Would send email to {to_emails} with subject: {subject}")
            return False
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = ", ".join(to_emails)
        
        # Add text and HTML parts
        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        # Add attachments if provided
        if attachments:
            for filename, file_bytes in attachments:
                attachment = MIMEApplication(file_bytes, Name=filename)
                attachment['Content-Disposition'] = f'attachment; filename="{filename}"'
                msg.attach(attachment)
        
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render an email template with the given context.
        
        Args:
            template_name: Name of the template file (e.g., "weekly_report.html")
            context: Dictionary of variables to pass to the template
            
        Returns:
            Rendered HTML string
        """
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)
    
    def send_weekly_report(
        self,
        to_emails: List[str],
        project_name: str,
        metrics: Dict[str, Any],
        report_file: bytes | None = None
    ) -> bool:
        """Send a weekly project summary report.
        
        Args:
            to_emails: Recipient email addresses
            project_name: Name of the project
            metrics: Dictionary containing project metrics
            report_file: Optional PDF report attachment
            
        Returns:
            True if sent successfully
        """
        context = {
            "project_name": project_name,
            "metrics": metrics
        }
        
        html_body = self.render_template("weekly_report.html", context)
        subject = f"Weekly Summary for {project_name}"
        
        attachments = []
        if report_file:
            attachments.append((f"{project_name}_weekly_report.pdf", report_file))
        
        return self.send_email(to_emails, subject, html_body, attachments=attachments)
    
    def send_alert(
        self,
        to_emails: List[str],
        alert_type: str,
        message: str,
        project_name: str
    ) -> bool:
        """Send an alert notification.
        
        Args:
            to_emails: Recipient email addresses
            alert_type: Type of alert (e.g., "risk", "budget", "compliance")
            message: Alert message
            project_name: Name of the project
            
        Returns:
            True if sent successfully
        """
        context = {
            "alert_type": alert_type,
            "message": message,
            "project_name": project_name
        }
        
        html_body = self.render_template("alert.html", context)
        subject = f"⚠️ Alert: {alert_type.title()} - {project_name}"
        
        return self.send_email(to_emails, subject, html_body)
