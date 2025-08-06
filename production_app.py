#!/usr/bin/env python3
"""
Production-Grade Email Campaign Manager
- FastAPI for async operations
- Redis for real-time data and caching
- PostgreSQL for reliable data storage
- Celery for distributed task processing
- WebSockets for real-time updates
- Designed to handle 100+ concurrent campaigns
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uuid

import aioredis
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import uvicorn
from celery import Celery
import structlog
import orjson
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(serializer=orjson.dumps)
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Prometheus metrics
CAMPAIGN_COUNTER = Counter('campaigns_total', 'Total campaigns processed', ['status'])
EMAIL_COUNTER = Counter('emails_total', 'Total emails sent', ['status'])
RESPONSE_TIME = Histogram('response_time_seconds', 'Response time')
ACTIVE_CAMPAIGNS = Gauge('active_campaigns', 'Number of active campaigns')
RESOURCE_USAGE = Gauge('resource_usage_percent', 'Resource usage percentage', ['resource'])

# FastAPI app with production settings
app = FastAPI(
    title="Production Email Campaign Manager",
    description="High-performance email campaign manager designed for 100+ concurrent campaigns",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Redis connection
redis_pool = None
redis_client = None

# PostgreSQL connection pool
db_pool = None

# Celery for distributed task processing
celery_app = Celery(
    "campaign_manager",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["production_app"]
)

# Celery configuration for maximum performance
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "send_campaign_emails": {"queue": "email_queue"},
        "process_campaign": {"queue": "campaign_queue"},
        "update_stats": {"queue": "stats_queue"},
    },
    worker_concurrency=50,  # High concurrency for email sending
    worker_prefetch_multiplier=4,
    task_acks_late=True,
    worker_disable_rate_limits=True,
    task_compression="gzip",
    result_compression="gzip",
    task_ignore_result=False,
    result_expires=3600,
)

# WebSocket connection manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.campaign_subscribers: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected", connections=len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        # Remove from campaign subscriptions
        for campaign_id, connections in self.campaign_subscribers.items():
            if websocket in connections:
                connections.remove(websocket)
        logger.info("WebSocket disconnected", connections=len(self.active_connections))

    async def subscribe_to_campaign(self, websocket: WebSocket, campaign_id: str):
        if campaign_id not in self.campaign_subscribers:
            self.campaign_subscribers[campaign_id] = []
        self.campaign_subscribers[campaign_id].append(websocket)

    async def broadcast_campaign_update(self, campaign_id: str, data: dict):
        if campaign_id in self.campaign_subscribers:
            message = orjson.dumps({
                "type": "campaign_update",
                "campaign_id": campaign_id,
                "data": data
            })
            
            disconnected = []
            for connection in self.campaign_subscribers[campaign_id]:
                try:
                    await connection.send_bytes(message)
                except:
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for connection in disconnected:
                self.campaign_subscribers[campaign_id].remove(connection)

    async def broadcast_stats_update(self, stats: dict):
        message = orjson.dumps({
            "type": "stats_update",
            "data": stats
        })
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_bytes(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.active_connections.remove(connection)

manager = ConnectionManager()

# Pydantic models
class CampaignCreate(BaseModel):
    name: str
    account_id: int
    data_list_id: int
    subject: str
    message: str
    from_name: Optional[str] = None
    start_line: int = 1
    test_after_config: Optional[Dict] = None
    rate_limits: Optional[Dict] = None

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    from_name: Optional[str] = None
    start_line: Optional[int] = None
    test_after_config: Optional[Dict] = None
    rate_limits: Optional[Dict] = None

class AccountCreate(BaseModel):
    name: str
    org_id: str
    cookies: Dict = Field(default_factory=dict)
    headers: Dict = Field(default_factory=dict)

# Database connection functions
async def get_db_connection():
    return await db_pool.acquire()

async def release_db_connection(connection):
    await db_pool.release(connection)

# Redis functions for real-time data
async def get_redis():
    return redis_client

async def set_campaign_status(campaign_id: str, status: str, extra_data: dict = None):
    """Update campaign status in Redis for real-time updates"""
    data = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat()
    }
    if extra_data:
        data.update(extra_data)
    
    await redis_client.hset(f"campaign:{campaign_id}", mapping=data)
    await redis_client.expire(f"campaign:{campaign_id}", 86400)  # 24 hours
    
    # Broadcast update via WebSocket
    await manager.broadcast_campaign_update(campaign_id, data)

async def get_campaign_status(campaign_id: str) -> dict:
    """Get campaign status from Redis"""
    data = await redis_client.hgetall(f"campaign:{campaign_id}")
    return {k.decode(): v.decode() for k, v in data.items()} if data else {}

async def increment_campaign_counter(campaign_id: str, counter_type: str, amount: int = 1):
    """Increment campaign counters (sent, failed, etc.)"""
    await redis_client.hincrby(f"campaign:{campaign_id}", counter_type, amount)
    
    # Get updated data and broadcast
    data = await get_campaign_status(campaign_id)
    await manager.broadcast_campaign_update(campaign_id, data)

# Celery tasks for distributed processing
@celery_app.task(bind=True)
def process_campaign(self, campaign_id: str, campaign_data: dict):
    """Process a campaign asynchronously"""
    logger.info("Starting campaign processing", campaign_id=campaign_id)
    
    try:
        # Update status to running
        asyncio.run(set_campaign_status(campaign_id, "running", {
            "started_at": datetime.utcnow().isoformat(),
            "total_sent": 0,
            "total_failed": 0
        }))
        
        # Get email list
        emails = get_email_list(campaign_data["data_list_id"], campaign_data.get("start_line", 1))
        
        if not emails:
            asyncio.run(set_campaign_status(campaign_id, "failed", {
                "error": "No emails found in data list"
            }))
            return
        
        # Process emails in batches for maximum performance
        batch_size = 500  # Large batches for high throughput
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            
            # Check if campaign should be stopped
            status_data = asyncio.run(get_campaign_status(campaign_id))
            if status_data.get("status") == "stopped":
                logger.info("Campaign stopped by user", campaign_id=campaign_id)
                break
            
            # Send batch of emails
            send_campaign_emails.delay(campaign_id, batch, campaign_data)
            
            # Small delay to prevent overwhelming
            time.sleep(0.1)
        
        # Mark as completed
        asyncio.run(set_campaign_status(campaign_id, "completed", {
            "completed_at": datetime.utcnow().isoformat()
        }))
        
        CAMPAIGN_COUNTER.labels(status="completed").inc()
        logger.info("Campaign completed", campaign_id=campaign_id)
        
    except Exception as e:
        logger.error("Campaign processing failed", campaign_id=campaign_id, error=str(e))
        asyncio.run(set_campaign_status(campaign_id, "failed", {
            "error": str(e)
        }))
        CAMPAIGN_COUNTER.labels(status="failed").inc()

@celery_app.task(bind=True)
def send_campaign_emails(self, campaign_id: str, emails: List[str], campaign_data: dict):
    """Send emails for a campaign batch"""
    try:
        account_data = get_account_data(campaign_data["account_id"])
        if not account_data:
            logger.error("Account not found", account_id=campaign_data["account_id"])
            return
        
        sent_count = 0
        failed_count = 0
        
        for email in emails:
            try:
                # Simulate email sending (replace with actual Zoho API call)
                success = send_email_via_zoho(
                    account_data,
                    email,
                    campaign_data["subject"],
                    campaign_data["message"],
                    campaign_data.get("from_name")
                )
                
                if success:
                    sent_count += 1
                    EMAIL_COUNTER.labels(status="sent").inc()
                else:
                    failed_count += 1
                    EMAIL_COUNTER.labels(status="failed").inc()
                
                # Apply rate limiting
                apply_rate_limiting(campaign_data.get("rate_limits", {}))
                
            except Exception as e:
                failed_count += 1
                EMAIL_COUNTER.labels(status="failed").inc()
                logger.error("Email sending failed", email=email, error=str(e))
        
        # Update counters in Redis
        if sent_count > 0:
            asyncio.run(increment_campaign_counter(campaign_id, "total_sent", sent_count))
        if failed_count > 0:
            asyncio.run(increment_campaign_counter(campaign_id, "total_failed", failed_count))
        
        logger.info("Batch processed", campaign_id=campaign_id, sent=sent_count, failed=failed_count)
        
    except Exception as e:
        logger.error("Batch processing failed", campaign_id=campaign_id, error=str(e))

def get_email_list(data_list_id: int, start_line: int = 1) -> List[str]:
    """Get emails from data list (implement based on your storage)"""
    # This is a placeholder - implement based on your data storage
    return ["test@example.com"] * 1000  # Sample data

def get_account_data(account_id: int) -> dict:
    """Get account data (implement based on your storage)"""
    # This is a placeholder - implement based on your data storage
    return {"name": "Test Account", "org_id": "test123"}

def send_email_via_zoho(account_data: dict, email: str, subject: str, message: str, from_name: str = None) -> bool:
    """Send email via Zoho API (implement your actual logic)"""
    # This is a placeholder - implement your actual Zoho email sending logic
    time.sleep(0.01)  # Simulate email sending delay
    return True

def apply_rate_limiting(rate_limits: dict):
    """Apply rate limiting between emails"""
    wait_time = rate_limits.get("wait_time_between_emails", 0.1)
    time.sleep(wait_time)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    global redis_pool, redis_client, db_pool
    
    # Initialize Redis connection
    redis_pool = aioredis.ConnectionPool.from_url(
        "redis://localhost:6379/0",
        max_connections=100,
        decode_responses=True
    )
    redis_client = aioredis.Redis(connection_pool=redis_pool)
    
    # Initialize PostgreSQL connection pool
    db_pool = await asyncpg.create_pool(
        "postgresql://user:password@localhost/campaign_manager",
        min_size=10,
        max_size=50,
        command_timeout=60
    )
    
    logger.info("Production application started")

@app.on_event("shutdown")
async def shutdown_event():
    global redis_pool, db_pool
    
    if redis_pool:
        await redis_pool.disconnect()
    
    if db_pool:
        await db_pool.close()
    
    logger.info("Production application shutdown")

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = orjson.loads(data)
            
            if message.get("type") == "subscribe_campaign":
                campaign_id = message.get("campaign_id")
                if campaign_id:
                    await manager.subscribe_to_campaign(websocket, campaign_id)
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# API endpoints
@app.get("/api/stats")
async def get_stats():
    """Get real-time statistics"""
    redis = await get_redis()
    
    # Get stats from Redis cache
    cached_stats = await redis.get("stats:current")
    if cached_stats:
        return orjson.loads(cached_stats)
    
    # Calculate stats if not cached
    stats = {
        "total_campaigns": await redis.scard("campaigns:all"),
        "active_campaigns": await redis.scard("campaigns:active"),
        "total_sent": await redis.get("stats:total_sent") or 0,
        "total_failed": await redis.get("stats:total_failed") or 0,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Cache for 5 seconds
    await redis.setex("stats:current", 5, orjson.dumps(stats))
    
    # Broadcast to connected clients
    await manager.broadcast_stats_update(stats)
    
    return stats

@app.get("/api/campaigns")
async def get_campaigns():
    """Get all campaigns with real-time status"""
    redis = await get_redis()
    
    campaign_keys = await redis.keys("campaign:*")
    campaigns = []
    
    for key in campaign_keys:
        campaign_data = await redis.hgetall(key)
        if campaign_data:
            campaigns.append(campaign_data)
    
    return campaigns

@app.post("/api/campaigns")
async def create_campaign(campaign: CampaignCreate):
    """Create a new campaign"""
    campaign_id = str(uuid.uuid4())
    
    campaign_data = {
        "id": campaign_id,
        "name": campaign.name,
        "account_id": campaign.account_id,
        "data_list_id": campaign.data_list_id,
        "subject": campaign.subject,
        "message": campaign.message,
        "from_name": campaign.from_name,
        "start_line": campaign.start_line,
        "test_after_config": orjson.dumps(campaign.test_after_config or {}),
        "rate_limits": orjson.dumps(campaign.rate_limits or {}),
        "status": "ready",
        "created_at": datetime.utcnow().isoformat(),
        "total_sent": 0,
        "total_failed": 0
    }
    
    redis = await get_redis()
    await redis.hset(f"campaign:{campaign_id}", mapping=campaign_data)
    await redis.sadd("campaigns:all", campaign_id)
    
    logger.info("Campaign created", campaign_id=campaign_id, name=campaign.name)
    
    return {"success": True, "campaign_id": campaign_id}

@app.post("/api/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str):
    """Start a campaign asynchronously"""
    redis = await get_redis()
    
    # Get campaign data
    campaign_data = await redis.hgetall(f"campaign:{campaign_id}")
    if not campaign_data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign_data.get("status") == "running":
        raise HTTPException(status_code=400, detail="Campaign is already running")
    
    # Add to active campaigns
    await redis.sadd("campaigns:active", campaign_id)
    
    # Start processing asynchronously with Celery
    process_campaign.delay(campaign_id, campaign_data)
    
    ACTIVE_CAMPAIGNS.inc()
    
    logger.info("Campaign started", campaign_id=campaign_id)
    
    return {"success": True, "message": "Campaign started"}

@app.post("/api/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: str):
    """Stop a running campaign"""
    redis = await get_redis()
    
    # Update status
    await set_campaign_status(campaign_id, "stopped")
    await redis.srem("campaigns:active", campaign_id)
    
    ACTIVE_CAMPAIGNS.dec()
    
    logger.info("Campaign stopped", campaign_id=campaign_id)
    
    return {"success": True, "message": "Campaign stopped"}

@app.get("/api/campaigns/{campaign_id}/status")
async def get_campaign_status_endpoint(campaign_id: str):
    """Get real-time campaign status"""
    status_data = await get_campaign_status(campaign_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return status_data

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis = await get_redis()
    
    try:
        await redis.ping()
        redis_status = "healthy"
    except:
        redis_status = "unhealthy"
    
    try:
        conn = await get_db_connection()
        await release_db_connection(conn)
        db_status = "healthy"
    except:
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if redis_status == "healthy" and db_status == "healthy" else "unhealthy",
        "redis": redis_status,
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        "production_app:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        loop="uvloop",
        http="httptools",
        access_log=False,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )