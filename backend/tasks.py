"""
CELERY TASKS - Simplified Working Version
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

# Celery imports
from celery import Celery

# Basic imports
import requests
import asyncio

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery app configuration
celery_app = Celery(
    'campaign_tasks',
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_concurrency=4,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Simple email sending task
@celery_app.task(bind=True, max_retries=3)
def send_test_email(self, to_email: str, subject: str, message: str):
    """Send a test email"""
    try:
        logger.info(f"Sending test email to {to_email}")
        
        # Simulate email sending
        time.sleep(0.1)
        
        return {
            "success": True,
            "email": to_email,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Test email failed: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)
        raise

# Campaign processing task
@celery_app.task(bind=True, max_retries=3)
def process_campaign(self, campaign_id: str):
    """Process a campaign"""
    try:
        logger.info(f"Processing campaign {campaign_id}")
        
        # Simulate campaign processing
        time.sleep(1)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Campaign processing failed: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)
        raise

# Health check task
@celery_app.task
def health_check():
    """Simple health check task"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    celery_app.start()