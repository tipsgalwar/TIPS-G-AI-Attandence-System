import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from abc import ABC, abstractmethod
from typing import Dict, Any
from loguru import logger

from src.config_loader import settings

from src.backend.services.email_service import email_service

class NotificationProvider(ABC):
    @abstractmethod
    def send(self, recipient: str, subject: str, message: str) -> bool:
        pass

class EmailProvider(NotificationProvider):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def send(self, recipient: str, subject: str, message: str) -> bool:
        return email_service._send_email(recipient, subject, message)


class WhatsAppProvider(NotificationProvider):
    def __init__(self, config: Dict[str, Any]):
        self.account_sid = config.get("account_sid")
        self.auth_token = config.get("auth_token")
        self.from_number = config.get("from_number")
        self.institution = config.get("institution_name", "TIPS-G Alwar")

    def send(self, recipient: str, subject: str, message: str) -> bool:
        if not settings.notifications.get("enable_whatsapp", True):
            logger.info("WhatsApp notifications are disabled globally.")
            return True

        if not self.account_sid or "ACXXXXXX" in self.account_sid:
            logger.info(f"[MOCK WHATSAPP] To: {recipient} | Message: {message}")
            return True

        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)
            
            # Format number if needed: Twilio requires whatsapp:+[country][number]
            to_formatted = recipient
            if not to_formatted.startswith("whatsapp:"):
                to_formatted = f"whatsapp:{recipient}"
                
            client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_formatted
            )
            logger.info(f"WhatsApp message sent to {recipient}")
            return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message to {recipient}: {e}")
            return False

class PushNotificationProvider(NotificationProvider):
    def __init__(self, config: Dict[str, Any]):
        self.cred_path = config.get("firebase_cred_path")

    def send(self, recipient: str, subject: str, message: str) -> bool:
        if not settings.notifications.get("enable_push", True):
            logger.info("Push notifications are disabled globally.")
            return True

        # In a real environment, firebase_admin SDK would be used.
        # We mock this for portability.
        logger.info(f"[MOCK PUSH] DeviceToken/UserId: {recipient} | Title: {subject} | Body: {message}")
        return True

class NotificationService:
    def __init__(self):
        conf = settings.notifications
        self.email_provider = EmailProvider(conf.get("email", {}))
        self.whatsapp_provider = WhatsAppProvider(conf.get("whatsapp", {}))
        self.push_provider = PushNotificationProvider(conf.get("push", {}))

    def send_email(self, email: str, subject: str, body: str) -> bool:
        return self.email_provider.send(email, subject, body)

    def send_whatsapp(self, phone: str, message: str) -> bool:
        return self.whatsapp_provider.send(phone, "", message)

    def send_push(self, recipient_token: str, title: str, body: str) -> bool:
        return self.push_provider.send(recipient_token, title, body)

    def broadcast_holiday(self, holiday_name: str, holiday_date_str: str, resume_date_str: str, recipients: list) -> int:
        """
        Sends holiday broadcasts via WhatsApp and Push to students, parents, and staff.
        recipients elements: {"role": "student/parent/staff", "phone": "...", "email": "...", "push_token": "..."}
        """
        sent_count = 0
        whatsapp_message = (
            f"Dear Student,\n\n"
            f"{self.whatsapp_provider.institution} will remain closed on {holiday_date_str} due to {holiday_name}.\n"
            f"Classes will resume on {resume_date_str}.\n\n"
            f"Regards,\n"
            f"TIPS-G Administration"
        )
        
        push_title = f"Holiday Announcement: {holiday_name}"
        push_body = f"TIPS-G will remain closed on {holiday_date_str}. Classes resume on {resume_date_str}."

        for rec in recipients:
            success = False
            # Send WhatsApp
            if rec.get("phone"):
                if self.send_whatsapp(rec["phone"], whatsapp_message):
                    success = True
            
            # Send Push Notification
            if rec.get("push_token"):
                if self.send_push(rec["push_token"], push_title, push_body):
                    success = True

            # Send Email Backup if WhatsApp/Push not available
            if not success and rec.get("email"):
                if self.send_email(rec["email"], push_title, whatsapp_message):
                    success = True
                    
            if success:
                sent_count += 1
                
        return sent_count

# Singleton service
notification_service = NotificationService()
