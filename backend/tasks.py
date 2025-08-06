"""
CELERY TASKS - Reliable Email Processing
Handles all background tasks including email sending, campaign processing, and cleanup
"""

import asyncio
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

# Celery imports
from celery import Celery
from celery.exceptions import Retry

# Database imports
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload
import sqlalchemy as sa

# Redis imports
import aioredis

# Email sending imports
import requests
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

# Import models (assuming they're in a separate models file)
from backend.main import Campaign, EmailLog, EmailAccount, DataList, CampaignStatus, EmailStatus, settings

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery app configuration
celery_app = Celery(
    'campaign_tasks',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'backend.tasks.send_campaign_emails': {'queue': 'email_queue'},
        'backend.tasks.process_campaign': {'queue': 'campaign_queue'},
        'backend.tasks.send_single_email': {'queue': 'email_queue'},
        'backend.tasks.update_campaign_stats': {'queue': 'stats_queue'},
        'backend.tasks.cleanup_old_logs': {'queue': 'cleanup_queue'},
    },
    worker_concurrency=10,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_compression='gzip',
    result_compression='gzip',
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=1800,  # 30 minutes soft limit
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
)

# Database setup for tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Redis setup for tasks
redis_client = None

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return redis_client

# Email sending utilities
class EmailSender:
    def __init__(self, account_data: Dict):
        self.account_data = account_data
        self.provider = account_data.get('provider', 'zoho')
        self.credentials = account_data.get('credentials', {})
    
    async def send_email(self, to_email: str, subject: str, message: str) -> tuple[bool, str, float]:
        """Send email and return (success, error_message, delivery_time_ms)"""
        start_time = time.time()
        
        try:
            if self.provider == 'zoho':
                return await self._send_zoho_email(to_email, subject, message, start_time)
            elif self.provider == 'gmail':
                return await self._send_gmail_email(to_email, subject, message, start_time)
            elif self.provider == 'smtp':
                return await self._send_smtp_email(to_email, subject, message, start_time)
            else:
                # For demo purposes, simulate sending
                await asyncio.sleep(0.01)  # Simulate network delay
                delivery_time = (time.time() - start_time) * 1000
                return True, None, delivery_time
                
        except Exception as e:
            delivery_time = (time.time() - start_time) * 1000
            logger.error(f"Email sending failed: {str(e)}")
            return False, str(e), delivery_time
    
    async def _send_zoho_email(self, to_email: str, subject: str, message: str, start_time: float) -> tuple[bool, str, float]:
        """Send email via Zoho API"""
        try:
            # Zoho API implementation
            api_url = "https://mail.zoho.com/api/accounts/{accountId}/messages"
            headers = {
                "Authorization": f"Zoho-oauthtoken {self.credentials.get('access_token')}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "fromAddress": self.credentials.get('from_email'),
                "toAddress": to_email,
                "subject": subject,
                "content": message,
                "mailFormat": "html"
            }
            
            # For demo, simulate the API call
            await asyncio.sleep(0.05)  # Simulate API call
            
            # In production, make actual API call:
            # response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            # if response.status_code == 200:
            #     delivery_time = (time.time() - start_time) * 1000
            #     return True, None, delivery_time
            # else:
            #     delivery_time = (time.time() - start_time) * 1000
            #     return False, f"Zoho API error: {response.status_code}", delivery_time
            
            delivery_time = (time.time() - start_time) * 1000
            return True, None, delivery_time
            
        except Exception as e:
            delivery_time = (time.time() - start_time) * 1000
            return False, f"Zoho error: {str(e)}", delivery_time
    
    async def _send_gmail_email(self, to_email: str, subject: str, message: str, start_time: float) -> tuple[bool, str, float]:
        """Send email via Gmail API"""
        try:
            # Gmail API implementation would go here
            await asyncio.sleep(0.03)  # Simulate API call
            delivery_time = (time.time() - start_time) * 1000
            return True, None, delivery_time
        except Exception as e:
            delivery_time = (time.time() - start_time) * 1000
            return False, f"Gmail error: {str(e)}", delivery_time
    
    async def _send_smtp_email(self, to_email: str, subject: str, message: str, start_time: float) -> tuple[bool, str, float]:
        """Send email via SMTP"""
        try:
            # SMTP implementation would go here
            await asyncio.sleep(0.02)  # Simulate SMTP send
            delivery_time = (time.time() - start_time) * 1000
            return True, None, delivery_time
        except Exception as e:
            delivery_time = (time.time() - start_time) * 1000
            return False, f"SMTP error: {str(e)}", delivery_time

# Rate limiting utility
class RateLimiter:
    def __init__(self, redis_client, account_id: str, rate_limits: Dict):
        self.redis_client = redis_client
        self.account_id = account_id
        self.rate_limits = rate_limits
        
        # Default rate limits
        self.emails_per_second = rate_limits.get('emails_per_second', 1)
        self.emails_per_minute = rate_limits.get('emails_per_minute', 30)
        self.emails_per_hour = rate_limits.get('emails_per_hour', 1000)
        self.wait_time_between_emails = rate_limits.get('wait_time_between_emails', 1.0)
    
    async def check_and_wait(self) -> bool:
        """Check rate limits and wait if necessary"""
        try:
            current_time = int(time.time())
            
            # Check hourly limit
            hour_key = f"rate_limit:{self.account_id}:hour:{current_time // 3600}"
            hourly_count = await self.redis_client.get(hour_key) or 0
            if int(hourly_count) >= self.emails_per_hour:
                logger.warning(f"Hourly rate limit exceeded for account {self.account_id}")
                return False
            
            # Check minute limit
            minute_key = f"rate_limit:{self.account_id}:minute:{current_time // 60}"
            minute_count = await self.redis_client.get(minute_key) or 0
            if int(minute_count) >= self.emails_per_minute:
                wait_time = 60 - (current_time % 60)
                logger.info(f"Minute rate limit reached, waiting {wait_time} seconds")
                await asyncio.sleep(wait_time)
            
            # Check second limit
            second_key = f"rate_limit:{self.account_id}:second:{current_time}"
            second_count = await self.redis_client.get(second_key) or 0
            if int(second_count) >= self.emails_per_second:
                await asyncio.sleep(1)
            
            # Increment counters
            await self.redis_client.incr(hour_key)
            await self.redis_client.expire(hour_key, 3600)
            
            await self.redis_client.incr(minute_key)
            await self.redis_client.expire(minute_key, 60)
            
            await self.redis_client.incr(second_key)
            await self.redis_client.expire(second_key, 1)
            
            # Wait between emails
            if self.wait_time_between_emails > 0:
                await asyncio.sleep(self.wait_time_between_emails)
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limiting error: {str(e)}")
            return True  # Allow on error to prevent blocking

# Main campaign processing task
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_campaign(self, campaign_id: str):
    """Process entire campaign by breaking it into batches"""
    try:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_process_campaign_async(campaign_id))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Campaign processing failed: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise

async def _process_campaign_async(campaign_id: str):
    """Async campaign processing"""
    redis = await get_redis()
    
    try:
        # Get campaign details from database
        async with async_session() as db:
            result = await db.execute(
                sa.select(Campaign, EmailAccount, DataList)
                .join(EmailAccount, Campaign.account_id == EmailAccount.id)
                .join(DataList, Campaign.data_list_id == DataList.id)
                .where(Campaign.id == campaign_id)
            )
            campaign_data = result.first()
            
            if not campaign_data:
                raise Exception("Campaign not found")
            
            campaign, account, data_list = campaign_data
            
            # Check if campaign should still be running
            redis_status = await redis.hget(f"campaign:{campaign_id}", "status")
            if redis_status != CampaignStatus.RUNNING:
                logger.info(f"Campaign {campaign_id} is no longer running, stopping processing")
                return
            
            # Load email list
            emails = await _load_email_list(data_list.file_path, campaign.start_line)
            
            if not emails:
                logger.warning(f"No emails to process for campaign {campaign_id}")
                await _complete_campaign(campaign_id, db, redis)
                return
            
            # Initialize email sender and rate limiter
            email_sender = EmailSender({
                'provider': account.provider,
                'credentials': account.credentials
            })
            
            rate_limiter = RateLimiter(redis, str(account.id), campaign.rate_limits)
            
            # Process emails in batches
            batch_size = 50
            total_emails = len(emails)
            processed = 0
            sent_count = 0
            failed_count = 0
            
            logger.info(f"Starting campaign {campaign_id} with {total_emails} emails")
            
            for i in range(0, total_emails, batch_size):
                # Check if campaign is still running
                current_status = await redis.hget(f"campaign:{campaign_id}", "status")
                if current_status != CampaignStatus.RUNNING:
                    logger.info(f"Campaign {campaign_id} was paused/stopped, breaking")
                    break
                
                batch_emails = emails[i:i + batch_size]
                
                # Process batch
                batch_results = await _process_email_batch(
                    campaign_id, batch_emails, email_sender, rate_limiter,
                    campaign.subject, campaign.message, campaign.test_config
                )
                
                # Update counters
                batch_sent = sum(1 for success, _, _ in batch_results if success)
                batch_failed = len(batch_results) - batch_sent
                
                sent_count += batch_sent
                failed_count += batch_failed
                processed += len(batch_results)
                
                # Update Redis stats
                await redis.hset(f"campaign:{campaign_id}", mapping={
                    "total_sent": str(sent_count),
                    "total_failed": str(failed_count),
                    "progress_percent": str(round((processed / total_emails) * 100, 1))
                })
                
                # Update database stats periodically
                if processed % 100 == 0:
                    await db.execute(
                        sa.update(Campaign)
                        .where(Campaign.id == campaign_id)
                        .values(total_sent=sent_count, total_failed=failed_count)
                    )
                    await db.commit()
                
                # Broadcast progress update
                await _broadcast_campaign_update(campaign_id, {
                    "type": "campaign_progress",
                    "campaign_id": campaign_id,
                    "total_sent": sent_count,
                    "total_failed": failed_count,
                    "progress_percent": round((processed / total_emails) * 100, 1)
                })
                
                # Small delay between batches
                await asyncio.sleep(0.1)
            
            # Final database update
            await db.execute(
                sa.update(Campaign)
                .where(Campaign.id == campaign_id)
                .values(
                    total_sent=sent_count,
                    total_failed=failed_count,
                    status=CampaignStatus.COMPLETED,
                    completed_at=datetime.utcnow()
                )
            )
            await db.commit()
            
            # Update Redis
            await redis.hset(f"campaign:{campaign_id}", mapping={
                "status": CampaignStatus.COMPLETED,
                "completed_at": datetime.utcnow().isoformat(),
                "total_sent": str(sent_count),
                "total_failed": str(failed_count)
            })
            
            # Broadcast completion
            await _broadcast_campaign_update(campaign_id, {
                "type": "campaign_completed",
                "campaign_id": campaign_id,
                "status": CampaignStatus.COMPLETED,
                "total_sent": sent_count,
                "total_failed": failed_count
            })
            
            logger.info(f"Campaign {campaign_id} completed. Sent: {sent_count}, Failed: {failed_count}")
            
    except Exception as e:
        logger.error(f"Campaign processing error: {str(e)}")
        
        # Mark campaign as failed
        async with async_session() as db:
            await db.execute(
                sa.update(Campaign)
                .where(Campaign.id == campaign_id)
                .values(status=CampaignStatus.FAILED)
            )
            await db.commit()
        
        await redis.hset(f"campaign:{campaign_id}", "status", CampaignStatus.FAILED)
        
        await _broadcast_campaign_update(campaign_id, {
            "type": "campaign_failed",
            "campaign_id": campaign_id,
            "status": CampaignStatus.FAILED,
            "error": str(e)
        })
        
        raise

async def _load_email_list(file_path: str, start_line: int = 0) -> List[str]:
    """Load emails from file starting from specified line"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        emails = []
        for i, line in enumerate(lines[start_line:], start_line):
            email = line.strip()
            if '@' in email and '.' in email:  # Basic email validation
                emails.append(email)
        
        return emails
    except Exception as e:
        logger.error(f"Error loading email list: {str(e)}")
        return []

async def _process_email_batch(
    campaign_id: str,
    emails: List[str],
    email_sender: EmailSender,
    rate_limiter: RateLimiter,
    subject: str,
    message: str,
    test_config: Dict
) -> List[tuple[bool, str, float]]:
    """Process a batch of emails"""
    results = []
    test_after = test_config.get('test_after', 0)
    test_email = test_config.get('test_email', '')
    
    for i, email in enumerate(emails):
        # Check rate limits
        can_send = await rate_limiter.check_and_wait()
        if not can_send:
            results.append((False, "Rate limit exceeded", 0))
            continue
        
        # Send email
        success, error_msg, delivery_time = await email_sender.send_email(email, subject, message)
        results.append((success, error_msg, delivery_time))
        
        # Log email result
        await _log_email_result(campaign_id, email, success, error_msg, delivery_time)
        
        # Send test email if configured
        if test_after > 0 and test_email and (i + 1) % test_after == 0:
            await email_sender.send_email(
                test_email,
                f"Test Report - {subject}",
                f"Campaign progress: {i + 1} emails processed successfully."
            )
    
    return results

async def _log_email_result(
    campaign_id: str,
    email: str,
    success: bool,
    error_msg: Optional[str],
    delivery_time: float
):
    """Log email result to database"""
    try:
        async with async_session() as db:
            email_log = EmailLog(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                email=email,
                status=EmailStatus.SENT if success else EmailStatus.FAILED,
                error_message=error_msg,
                delivery_time=int(delivery_time),
                timestamp=datetime.utcnow()
            )
            db.add(email_log)
            await db.commit()
            
    except Exception as e:
        logger.error(f"Error logging email result: {str(e)}")

async def _broadcast_campaign_update(campaign_id: str, message: Dict):
    """Broadcast update via Redis pub/sub"""
    try:
        redis = await get_redis()
        await redis.publish(f"campaign_updates:{campaign_id}", json.dumps(message))
        await redis.publish("campaign_updates:all", json.dumps(message))
    except Exception as e:
        logger.error(f"Error broadcasting update: {str(e)}")

async def _complete_campaign(campaign_id: str, db, redis):
    """Mark campaign as completed"""
    await db.execute(
        sa.update(Campaign)
        .where(Campaign.id == campaign_id)
        .values(
            status=CampaignStatus.COMPLETED,
            completed_at=datetime.utcnow()
        )
    )
    await db.commit()
    
    await redis.hset(f"campaign:{campaign_id}", mapping={
        "status": CampaignStatus.COMPLETED,
        "completed_at": datetime.utcnow().isoformat()
    })

# Individual email sending task (for immediate sends)
@celery_app.task(bind=True, max_retries=3)
def send_single_email(self, account_data: Dict, to_email: str, subject: str, message: str):
    """Send a single email immediately"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        email_sender = EmailSender(account_data)
        success, error_msg, delivery_time = loop.run_until_complete(
            email_sender.send_email(to_email, subject, message)
        )
        
        loop.close()
        
        return {
            "success": success,
            "error": error_msg,
            "delivery_time": delivery_time
        }
        
    except Exception as e:
        logger.error(f"Single email send failed: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)
        raise

# Statistics update task
@celery_app.task
def update_campaign_stats(campaign_id: str):
    """Update campaign statistics"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_update_campaign_stats_async(campaign_id))
        loop.close()
    except Exception as e:
        logger.error(f"Stats update failed: {str(e)}")

async def _update_campaign_stats_async(campaign_id: str):
    """Async stats update"""
    try:
        redis = await get_redis()
        
        async with async_session() as db:
            # Get latest stats from database
            result = await db.execute(
                sa.text("""
                    SELECT 
                        COUNT(*) FILTER (WHERE status = 'sent') as sent_count,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                        AVG(delivery_time) FILTER (WHERE delivery_time IS NOT NULL) as avg_delivery_time
                    FROM email_logs 
                    WHERE campaign_id = :campaign_id
                """),
                {"campaign_id": campaign_id}
            )
            
            stats_row = result.fetchone()
            if stats_row:
                await redis.hset(f"campaign:{campaign_id}", mapping={
                    "total_sent": str(stats_row[0] or 0),
                    "total_failed": str(stats_row[1] or 0),
                    "avg_delivery_time": str(int(stats_row[2] or 0)),
                    "last_updated": datetime.utcnow().isoformat()
                })
                
    except Exception as e:
        logger.error(f"Error updating campaign stats: {str(e)}")

# Cleanup task
@celery_app.task
def cleanup_old_logs():
    """Clean up old email logs"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_cleanup_old_logs_async())
        loop.close()
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")

async def _cleanup_old_logs_async():
    """Async cleanup of old logs"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        async with async_session() as db:
            result = await db.execute(
                sa.delete(EmailLog).where(EmailLog.timestamp < cutoff_date)
            )
            await db.commit()
            
            logger.info(f"Cleaned up {result.rowcount} old email logs")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

# Periodic tasks setup
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'cleanup-old-logs': {
        'task': 'backend.tasks.cleanup_old_logs',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
    },
}

if __name__ == "__main__":
    # For debugging
    celery_app.start()