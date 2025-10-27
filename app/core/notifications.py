"""Notification manager for sending alerts via multiple channels."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiohttp

from app.models.endpoint import Endpoint
from app.models.check_result import CheckResult
from app.models.notification_log import NotificationLog
from app.config import NotificationsConfig
from app.utils.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class NotificationManager:
    """
    Manager for sending notifications through multiple channels.
    
    Supports email, webhooks, and Telegram notifications with cooldown
    mechanism to prevent spam.
    """
    
    def __init__(self, config: NotificationsConfig):
        """
        Initialize notification manager.
        
        Args:
            config: Notifications configuration
        """
        self.config = config
        self.last_notification_times: Dict[int, datetime] = {}
        
        logger.info(
            "Notification manager initialized",
            extra={
                "email_enabled": config.email.enabled,
                "webhook_enabled": config.webhook.enabled,
                "telegram_enabled": config.telegram.enabled,
                "cooldown_seconds": config.cooldown_seconds
            }
        )
    
    def _is_cooldown_active(self, endpoint_id: int) -> bool:
        """
        Check if notification cooldown is active for an endpoint.
        
        Args:
            endpoint_id: Endpoint ID
            
        Returns:
            bool: True if cooldown is active
        """
        if endpoint_id not in self.last_notification_times:
            return False
        
        last_time = self.last_notification_times[endpoint_id]
        cooldown_delta = timedelta(seconds=self.config.cooldown_seconds)
        
        return datetime.utcnow() - last_time < cooldown_delta
    
    def _update_cooldown(self, endpoint_id: int) -> None:
        """Update last notification time for an endpoint."""
        self.last_notification_times[endpoint_id] = datetime.utcnow()
    
    def _format_message(
        self,
        template: str,
        endpoint: Endpoint,
        result: CheckResult
    ) -> str:
        """
        Format notification message from template.
        
        Args:
            template: Message template with placeholders
            endpoint: Endpoint that failed
            result: Check result
            
        Returns:
            str: Formatted message
        """
        return template.format(
            endpoint_name=endpoint.name,
            url=endpoint.url,
            error=result.error_message or "Unknown error",
            status_code=result.status_code or "N/A",
            timestamp=result.checked_at.isoformat(),
            response_time=result.response_time or "N/A"
        )
    
    async def send_email(
        self,
        subject: str,
        body: str,
        db: AsyncSession
    ) -> bool:
        """
        Send email notification.
        
        Args:
            subject: Email subject
            body: Email body
            db: Database session
            
        Returns:
            bool: True if sent successfully
        """
        if not self.config.email.enabled:
            logger.debug("Email notifications disabled")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{self.config.email.from_name} <{self.config.email.from_addr}>"
            msg['To'] = ', '.join(self.config.email.to_addrs)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            await aiosmtplib.send(
                msg,
                hostname=self.config.email.smtp_host,
                port=self.config.email.smtp_port,
                username=self.config.email.smtp_user,
                password=self.config.email.smtp_password,
                use_tls=self.config.email.smtp_use_tls
            )
            
            logger.info(
                "Email notification sent",
                extra={
                    "to": self.config.email.to_addrs,
                    "subject": subject
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to send email notification",
                extra={"error": str(e)}
            )
            return False
    
    async def send_webhook(
        self,
        payload: Dict[str, Any],
        db: AsyncSession
    ) -> bool:
        """
        Send webhook notification.
        
        Args:
            payload: Webhook payload
            db: Database session
            
        Returns:
            bool: True if sent successfully
        """
        if not self.config.webhook.enabled:
            logger.debug("Webhook notifications disabled")
            return False
        
        for attempt in range(self.config.webhook.retry_count):
            try:
                timeout = aiohttp.ClientTimeout(total=self.config.webhook.timeout)
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.request(
                        method=self.config.webhook.method,
                        url=self.config.webhook.url,
                        json=payload,
                        headers=self.config.webhook.headers
                    ) as response:
                        if response.status < 400:
                            logger.info(
                                "Webhook notification sent",
                                extra={
                                    "url": self.config.webhook.url,
                                    "status": response.status,
                                    "attempt": attempt + 1
                                }
                            )
                            return True
                        else:
                            logger.warning(
                                f"Webhook returned error status",
                                extra={
                                    "url": self.config.webhook.url,
                                    "status": response.status,
                                    "attempt": attempt + 1
                                }
                            )
            
            except Exception as e:
                logger.error(
                    f"Failed to send webhook notification",
                    extra={
                        "error": str(e),
                        "attempt": attempt + 1,
                        "url": self.config.webhook.url
                    }
                )
            
            # Wait before retry
            if attempt < self.config.webhook.retry_count - 1:
                await asyncio.sleep(self.config.webhook.retry_delay)
        
        return False
    
    async def send_telegram(
        self,
        message: str,
        db: AsyncSession
    ) -> bool:
        """
        Send Telegram notification.
        
        Args:
            message: Message to send
            db: Database session
            
        Returns:
            bool: True if sent successfully
        """
        if not self.config.telegram.enabled:
            logger.debug("Telegram notifications disabled")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.config.telegram.bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.config.telegram.chat_id,
                "text": message,
                "parse_mode": self.config.telegram.parse_mode
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info("Telegram notification sent")
                        return True
                    else:
                        logger.error(
                            f"Telegram API error",
                            extra={"status": response.status}
                        )
                        return False
        
        except Exception as e:
            logger.error(
                f"Failed to send Telegram notification",
                extra={"error": str(e)}
            )
            return False
    
    async def notify_failure(
        self,
        endpoint: Endpoint,
        result: CheckResult,
        db: AsyncSession
    ) -> None:
        """
        Send failure notification for an endpoint.
        
        Args:
            endpoint: Failed endpoint
            result: Check result with failure details
            db: Database session
        """
        if not self.config.enabled:
            logger.debug("Notifications disabled globally")
            return
        
        # Check cooldown
        if self._is_cooldown_active(endpoint.id):
            logger.debug(
                f"Skipping notification due to cooldown",
                extra={
                    "endpoint_id": endpoint.id,
                    "endpoint_name": endpoint.name
                }
            )
            return
        
        logger.info(
            f"Sending failure notifications",
            extra={
                "endpoint_id": endpoint.id,
                "endpoint_name": endpoint.name
            }
        )
        
        # Send email
        if self.config.email.enabled:
            subject = self._format_message(
                self.config.email.subject_template,
                endpoint,
                result
            )
            body = self._format_message(
                self.config.email.body_template,
                endpoint,
                result
            )
            
            success = await self.send_email(subject, body, db)
            
            # Log notification
            log = NotificationLog(
                endpoint_id=endpoint.id,
                notification_type="email",
                status="sent" if success else "failed",
                message=subject,
                error_message=None if success else "Failed to send email"
            )
            db.add(log)
        
        # Send webhook
        if self.config.webhook.enabled:
            try:
                payload_str = self._format_message(
                    self.config.webhook.payload_template,
                    endpoint,
                    result
                )
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                payload = {
                    "endpoint_name": endpoint.name,
                    "url": endpoint.url,
                    "error": result.error_message,
                    "timestamp": result.checked_at.isoformat()
                }
            
            success = await self.send_webhook(payload, db)
            
            # Log notification
            log = NotificationLog(
                endpoint_id=endpoint.id,
                notification_type="webhook",
                status="sent" if success else "failed",
                message=json.dumps(payload),
                error_message=None if success else "Failed to send webhook"
            )
            db.add(log)
        
        # Send Telegram
        if self.config.telegram.enabled:
            message = self._format_message(
                self.config.telegram.message_template,
                endpoint,
                result
            )
            
            success = await self.send_telegram(message, db)
            
            # Log notification
            log = NotificationLog(
                endpoint_id=endpoint.id,
                notification_type="telegram",
                status="sent" if success else "failed",
                message=message,
                error_message=None if success else "Failed to send telegram"
            )
            db.add(log)
        
        # Update cooldown
        self._update_cooldown(endpoint.id)
        
        # Commit notification logs
        await db.commit()
    
    async def notify_recovery(
        self,
        endpoint: Endpoint,
        result: CheckResult,
        db: AsyncSession
    ) -> None:
        """
        Send recovery notification when endpoint comes back online.
        
        Args:
            endpoint: Recovered endpoint
            result: Successful check result
            db: Database session
        """
        if not self.config.enabled or not self.config.send_recovery:
            return
        
        logger.info(
            f"Sending recovery notifications",
            extra={
                "endpoint_id": endpoint.id,
                "endpoint_name": endpoint.name
            }
        )
        
        # Create recovery message
        recovery_template = "✅ {endpoint_name} is back online!\nURL: {url}\nRecovered at: {timestamp}"
        
        # Send notifications (similar to failure, but with recovery message)
        if self.config.email.enabled:
            subject = f"✅ Recovery: {endpoint.name} is back online"
            body = recovery_template.format(
                endpoint_name=endpoint.name,
                url=endpoint.url,
                timestamp=result.checked_at.isoformat()
            )
            
            await self.send_email(subject, body, db)
        
        if self.config.webhook.enabled:
            payload = {
                "status": "recovery",
                "endpoint_name": endpoint.name,
                "url": endpoint.url,
                "timestamp": result.checked_at.isoformat()
            }
            
            await self.send_webhook(payload, db)
        
        if self.config.telegram.enabled:
            message = recovery_template.format(
                endpoint_name=endpoint.name,
                url=endpoint.url,
                timestamp=result.checked_at.isoformat()
            )
            
            await self.send_telegram(message, db)
        
        await db.commit()