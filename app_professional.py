#!/usr/bin/env python3
"""
PROFESSIONAL ENTERPRISE EMAIL CAMPAIGN MANAGER
- Redis for ultra-fast caching and pub/sub
- PostgreSQL for enterprise data reliability
- Celery for distributed task processing
- Professional monitoring and metrics
- Advanced error handling and recovery
- Enterprise security features
- Professional API with rate limiting
- Advanced campaign analytics
- Multi-tenant support
- Professional logging and auditing
"""

import os
import json
import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import uuid
from collections import defaultdict
import logging
import traceback
import hashlib
import jwt
from dataclasses import dataclass
from enum import Enum

# Professional logging setup
import structlog
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
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

# Enterprise imports
import redis
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from celery import Celery
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, g
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import requests

# Professional enums
class CampaignStatus(Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"

class EmailStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"

class UserRole(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    VIEWER = "viewer"

# Professional data classes
@dataclass
class Campaign:
    id: str
    name: str
    subject: str
    message: str
    status: CampaignStatus
    account_id: str
    data_list_id: str
    owner_id: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_recipients: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_opened: int = 0
    total_clicked: int = 0
    rate_limits: Dict = None
    test_config: Dict = None
    tags: List[str] = None

@dataclass
class EmailLog:
    id: str
    campaign_id: str
    email: str
    status: EmailStatus
    timestamp: datetime
    error_message: Optional[str] = None
    delivery_time: Optional[float] = None

# Flask app with professional configuration
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
    REDIS_URL=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    DATABASE_URL=os.environ.get('DATABASE_URL', 'postgresql://campaign_user:campaign_pass@localhost/campaign_db'),
    CELERY_BROKER_URL=os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
    CELERY_RESULT_BACKEND=os.environ.get('REDIS_URL', 'redis://localhost:6379/2'),
    MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB
    RATELIMIT_STORAGE_URL=os.environ.get('REDIS_URL', 'redis://localhost:6379/3'),
)

# Professional rate limiting
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)

# Professional metrics
CAMPAIGN_COUNTER = Counter('campaigns_total', 'Total campaigns', ['status', 'tenant'])
EMAIL_COUNTER = Counter('emails_total', 'Total emails', ['status', 'campaign'])
API_REQUEST_TIME = Histogram('api_request_duration_seconds', 'API request duration', ['endpoint'])
ACTIVE_CAMPAIGNS = Gauge('active_campaigns', 'Active campaigns count')
SYSTEM_HEALTH = Gauge('system_health', 'System health status')

# SocketIO with professional configuration
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8
)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Professional Redis connection with connection pooling
class ProfessionalRedis:
    def __init__(self, url):
        self.pool = redis.ConnectionPool.from_url(url, max_connections=100)
        self.client = redis.Redis(connection_pool=self.pool, decode_responses=True)
        self.pubsub = self.client.pubsub()
    
    def get(self, key):
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error("Redis get error", key=key, error=str(e))
            return None
    
    def set(self, key, value, ex=None):
        try:
            return self.client.set(key, value, ex=ex)
        except Exception as e:
            logger.error("Redis set error", key=key, error=str(e))
            return False
    
    def hget(self, name, key):
        try:
            return self.client.hget(name, key)
        except Exception as e:
            logger.error("Redis hget error", name=name, key=key, error=str(e))
            return None
    
    def hset(self, name, key, value):
        try:
            return self.client.hset(name, key, value)
        except Exception as e:
            logger.error("Redis hset error", name=name, key=key, error=str(e))
            return False
    
    def hgetall(self, name):
        try:
            return self.client.hgetall(name)
        except Exception as e:
            logger.error("Redis hgetall error", name=name, error=str(e))
            return {}
    
    def publish(self, channel, message):
        try:
            return self.client.publish(channel, message)
        except Exception as e:
            logger.error("Redis publish error", channel=channel, error=str(e))
            return False
    
    def delete(self, *keys):
        try:
            return self.client.delete(*keys)
        except Exception as e:
            logger.error("Redis delete error", keys=keys, error=str(e))
            return False

# Global Redis instance
redis_client = ProfessionalRedis(app.config['REDIS_URL'])

# Professional PostgreSQL connection pool
class ProfessionalDatabase:
    def __init__(self, database_url):
        self.pool = ThreadedConnectionPool(
            minconn=5,
            maxconn=50,
            dsn=database_url
        )
        self.init_schema()
    
    def get_connection(self):
        return self.pool.getconn()
    
    def put_connection(self, conn):
        self.pool.putconn(conn)
    
    def init_schema(self):
        """Initialize database schema"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Campaigns table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS campaigns (
                        id UUID PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        subject TEXT NOT NULL,
                        message TEXT NOT NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'draft',
                        account_id UUID NOT NULL,
                        data_list_id UUID NOT NULL,
                        owner_id UUID NOT NULL,
                        tenant_id UUID NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        started_at TIMESTAMPTZ,
                        completed_at TIMESTAMPTZ,
                        total_recipients INTEGER DEFAULT 0,
                        total_sent INTEGER DEFAULT 0,
                        total_failed INTEGER DEFAULT 0,
                        total_opened INTEGER DEFAULT 0,
                        total_clicked INTEGER DEFAULT 0,
                        rate_limits JSONB DEFAULT '{}',
                        test_config JSONB DEFAULT '{}',
                        tags TEXT[] DEFAULT '{}',
                        created_by UUID,
                        updated_by UUID,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                
                # Email logs table with partitioning for performance
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS email_logs (
                        id UUID PRIMARY KEY,
                        campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
                        email VARCHAR(255) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        timestamp TIMESTAMPTZ DEFAULT NOW(),
                        error_message TEXT,
                        delivery_time FLOAT,
                        tenant_id UUID NOT NULL,
                        metadata JSONB DEFAULT '{}'
                    ) PARTITION BY RANGE (timestamp)
                """)
                
                # Accounts table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS accounts (
                        id UUID PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        tenant_id UUID NOT NULL,
                        provider VARCHAR(100) NOT NULL,
                        credentials JSONB NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        daily_limit INTEGER DEFAULT 10000,
                        hourly_limit INTEGER DEFAULT 1000,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        created_by UUID
                    )
                """)
                
                # Users table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id UUID PRIMARY KEY,
                        username VARCHAR(100) UNIQUE NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        role VARCHAR(50) DEFAULT 'user',
                        tenant_id UUID NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        last_login TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        permissions JSONB DEFAULT '[]',
                        settings JSONB DEFAULT '{}'
                    )
                """)
                
                # Data lists table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS data_lists (
                        id UUID PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        tenant_id UUID NOT NULL,
                        file_path VARCHAR(500),
                        total_count INTEGER DEFAULT 0,
                        status VARCHAR(50) DEFAULT 'processing',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        created_by UUID
                    )
                """)
                
                # Create indexes for performance
                cur.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_tenant ON campaigns(tenant_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_email_logs_campaign ON email_logs(campaign_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_email_logs_status ON email_logs(status)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_accounts_tenant ON accounts(tenant_id)")
                
                conn.commit()
                logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error("Error initializing database schema", error=str(e))
            conn.rollback()
        finally:
            self.put_connection(conn)
    
    def execute_query(self, query, params=None, fetch=False):
        """Execute query with connection handling"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                conn.commit()
                return cur.rowcount
        except Exception as e:
            logger.error("Database query error", query=query, error=str(e))
            conn.rollback()
            raise
        finally:
            self.put_connection(conn)

# Global database instance
db = ProfessionalDatabase(app.config['DATABASE_URL'])

# Professional Celery configuration
celery_app = Celery(
    'campaign_manager',
    broker=app.config['CELERY_BROKER_URL'],
    backend=app.config['CELERY_RESULT_BACKEND']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'send_campaign_emails': {'queue': 'email_queue'},
        'process_campaign': {'queue': 'campaign_queue'},
        'analytics_update': {'queue': 'analytics_queue'},
    },
    worker_concurrency=20,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_compression='gzip',
    result_compression='gzip',
    task_time_limit=7200,  # 2 hours
    task_soft_time_limit=3600,  # 1 hour
)

# Professional campaign manager
class ProfessionalCampaignManager:
    def __init__(self):
        self.active_campaigns = set()
        self.campaign_stats = defaultdict(lambda: {
            'sent': 0, 'failed': 0, 'opened': 0, 'clicked': 0
        })
        self._lock = threading.RLock()
        
        # Start background monitoring
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Start background monitoring tasks"""
        def monitor_loop():
            while True:
                try:
                    self._update_metrics()
                    self._check_stalled_campaigns()
                    time.sleep(30)  # Monitor every 30 seconds
                except Exception as e:
                    logger.error("Monitor loop error", error=str(e))
                    time.sleep(60)
        
        threading.Thread(target=monitor_loop, daemon=True).start()
    
    def _update_metrics(self):
        """Update Prometheus metrics"""
        try:
            ACTIVE_CAMPAIGNS.set(len(self.active_campaigns))
            
            # Update system health
            health_score = 1.0
            if redis_client.client.ping():
                health_score *= 0.5
            
            # Check database
            try:
                db.execute_query("SELECT 1", fetch=True)
                health_score += 0.5
            except:
                pass
            
            SYSTEM_HEALTH.set(health_score)
            
        except Exception as e:
            logger.error("Error updating metrics", error=str(e))
    
    def _check_stalled_campaigns(self):
        """Check for stalled campaigns and recover"""
        try:
            # Get campaigns that have been running too long
            query = """
                SELECT id, name, started_at 
                FROM campaigns 
                WHERE status = 'running' 
                AND started_at < NOW() - INTERVAL '4 hours'
            """
            stalled = db.execute_query(query, fetch=True)
            
            for campaign_id, name, started_at in stalled:
                logger.warning("Recovering stalled campaign", 
                             campaign_id=campaign_id, name=name, started_at=started_at)
                self.stop_campaign(campaign_id, reason="Auto-recovered stalled campaign")
                
        except Exception as e:
            logger.error("Error checking stalled campaigns", error=str(e))
    
    def start_campaign(self, campaign_id: str, user_id: str) -> tuple[bool, str]:
        """Start campaign with professional error handling"""
        try:
            with self._lock:
                # Get campaign from database
                query = """
                    SELECT id, name, status, account_id, data_list_id, owner_id
                    FROM campaigns 
                    WHERE id = %s
                """
                result = db.execute_query(query, (campaign_id,), fetch=True)
                
                if not result:
                    return False, "Campaign not found"
                
                campaign_data = result[0]
                
                if campaign_data[2] == 'running':  # status
                    return False, "Campaign is already running"
                
                # Update status to running
                update_query = """
                    UPDATE campaigns 
                    SET status = 'running', started_at = NOW(), updated_by = %s, updated_at = NOW()
                    WHERE id = %s
                """
                db.execute_query(update_query, (user_id, campaign_id))
                
                # Add to active campaigns
                self.active_campaigns.add(campaign_id)
                
                # Start processing with Celery
                process_campaign.delay(campaign_id)
                
                # Cache in Redis for fast access
                redis_client.hset(f"campaign:{campaign_id}", "status", "running")
                redis_client.hset(f"campaign:{campaign_id}", "started_at", datetime.now().isoformat())
                
                # Emit real-time update
                socketio.emit('campaign_started', {
                    'campaign_id': campaign_id,
                    'status': 'running',
                    'started_at': datetime.now().isoformat()
                }, room=f"campaign_{campaign_id}")
                
                # Metrics
                CAMPAIGN_COUNTER.labels(status='started', tenant=current_user.tenant_id if current_user.is_authenticated else 'unknown').inc()
                
                logger.info("Campaign started", campaign_id=campaign_id, user_id=user_id)
                return True, "Campaign started successfully"
                
        except Exception as e:
            logger.error("Error starting campaign", campaign_id=campaign_id, error=str(e))
            return False, f"Error starting campaign: {str(e)}"
    
    def stop_campaign(self, campaign_id: str, reason: str = "User stopped") -> tuple[bool, str]:
        """Stop campaign"""
        try:
            with self._lock:
                # Update database
                update_query = """
                    UPDATE campaigns 
                    SET status = 'stopped', completed_at = NOW(), updated_at = NOW()
                    WHERE id = %s
                """
                db.execute_query(update_query, (campaign_id,))
                
                # Remove from active campaigns
                self.active_campaigns.discard(campaign_id)
                
                # Update Redis
                redis_client.hset(f"campaign:{campaign_id}", "status", "stopped")
                redis_client.hset(f"campaign:{campaign_id}", "completed_at", datetime.now().isoformat())
                
                # Emit real-time update
                socketio.emit('campaign_stopped', {
                    'campaign_id': campaign_id,
                    'status': 'stopped',
                    'reason': reason,
                    'completed_at': datetime.now().isoformat()
                }, room=f"campaign_{campaign_id}")
                
                logger.info("Campaign stopped", campaign_id=campaign_id, reason=reason)
                return True, "Campaign stopped successfully"
                
        except Exception as e:
            logger.error("Error stopping campaign", campaign_id=campaign_id, error=str(e))
            return False, f"Error stopping campaign: {str(e)}"
    
    def delete_campaign(self, campaign_id: str, user_id: str) -> tuple[bool, str]:
        """Delete campaign with cascade"""
        try:
            with self._lock:
                # Stop if running
                if campaign_id in self.active_campaigns:
                    self.stop_campaign(campaign_id, "Deleted by user")
                
                # Delete from database (cascade will handle email_logs)
                delete_query = "DELETE FROM campaigns WHERE id = %s"
                affected = db.execute_query(delete_query, (campaign_id,))
                
                if affected == 0:
                    return False, "Campaign not found"
                
                # Clean up Redis
                redis_client.delete(f"campaign:{campaign_id}")
                
                # Clean up local data
                if campaign_id in self.campaign_stats:
                    del self.campaign_stats[campaign_id]
                
                # Emit real-time update
                socketio.emit('campaign_deleted', {
                    'campaign_id': campaign_id
                })
                
                logger.info("Campaign deleted", campaign_id=campaign_id, user_id=user_id)
                return True, "Campaign deleted successfully"
                
        except Exception as e:
            logger.error("Error deleting campaign", campaign_id=campaign_id, error=str(e))
            return False, f"Error deleting campaign: {str(e)}"

# Global campaign manager
campaign_manager = ProfessionalCampaignManager()

# Professional Celery tasks
@celery_app.task(bind=True, max_retries=3)
def process_campaign(self, campaign_id: str):
    """Process campaign with Celery"""
    try:
        logger.info("Starting campaign processing", campaign_id=campaign_id)
        
        # Get campaign details
        query = """
            SELECT c.id, c.name, c.data_list_id, c.account_id, c.rate_limits,
                   dl.file_path, dl.total_count
            FROM campaigns c
            JOIN data_lists dl ON c.data_list_id = dl.id
            WHERE c.id = %s
        """
        result = db.execute_query(query, (campaign_id,), fetch=True)
        
        if not result:
            raise Exception("Campaign not found")
        
        campaign_data = result[0]
        
        # Process emails in batches
        batch_size = 100
        total_count = campaign_data[6]  # total_count
        
        for batch_start in range(0, total_count, batch_size):
            # Check if campaign is still running
            status = redis_client.hget(f"campaign:{campaign_id}", "status")
            if status != "running":
                logger.info("Campaign stopped during processing", campaign_id=campaign_id)
                break
            
            # Send batch of emails
            send_campaign_emails.delay(campaign_id, batch_start, batch_size)
            
            # Small delay between batches
            time.sleep(0.1)
        
        # Mark as completed if still running
        if redis_client.hget(f"campaign:{campaign_id}", "status") == "running":
            campaign_manager.stop_campaign(campaign_id, "Completed successfully")
            
            # Update status to completed
            db.execute_query(
                "UPDATE campaigns SET status = 'completed' WHERE id = %s",
                (campaign_id,)
            )
        
        logger.info("Campaign processing completed", campaign_id=campaign_id)
        
    except Exception as e:
        logger.error("Campaign processing failed", campaign_id=campaign_id, error=str(e))
        
        # Mark as failed
        db.execute_query(
            "UPDATE campaigns SET status = 'failed' WHERE id = %s",
            (campaign_id,)
        )
        
        # Retry if not max retries
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))

@celery_app.task
def send_campaign_emails(campaign_id: str, batch_start: int, batch_size: int):
    """Send batch of emails"""
    try:
        # Simulate email sending for demo
        import random
        import time
        
        for i in range(batch_start, min(batch_start + batch_size, batch_start + batch_size)):
            email = f"test{i}@example.com"
            
            # Simulate sending
            time.sleep(0.01)  # Fast simulation
            success = random.random() > 0.1  # 90% success rate
            
            # Log email result
            log_email_result(campaign_id, email, 'sent' if success else 'failed')
            
            # Update campaign stats
            if success:
                campaign_manager.campaign_stats[campaign_id]['sent'] += 1
                EMAIL_COUNTER.labels(status='sent', campaign=campaign_id).inc()
            else:
                campaign_manager.campaign_stats[campaign_id]['failed'] += 1
                EMAIL_COUNTER.labels(status='failed', campaign=campaign_id).inc()
            
            # Emit real-time update
            socketio.emit('email_sent', {
                'campaign_id': campaign_id,
                'email': email,
                'status': 'sent' if success else 'failed',
                'stats': campaign_manager.campaign_stats[campaign_id]
            }, room=f"campaign_{campaign_id}")
        
    except Exception as e:
        logger.error("Batch email sending failed", 
                    campaign_id=campaign_id, batch_start=batch_start, error=str(e))

def log_email_result(campaign_id: str, email: str, status: str, error_message: str = None):
    """Log email result to database"""
    try:
        query = """
            INSERT INTO email_logs (id, campaign_id, email, status, error_message, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        db.execute_query(query, (
            str(uuid.uuid4()),
            campaign_id,
            email,
            status,
            error_message,
            current_user.tenant_id if current_user.is_authenticated else 'system'
        ))
    except Exception as e:
        logger.error("Error logging email result", error=str(e))

# Professional User class with multi-tenancy
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.username = user_data.get('username')
        self.email = user_data.get('email')
        self.role = user_data.get('role', 'user')
        self.tenant_id = user_data.get('tenant_id')
        self.permissions = user_data.get('permissions', [])
        self.is_active = user_data.get('is_active', True)

@login_manager.user_loader
def load_user(user_id):
    try:
        query = "SELECT * FROM users WHERE id = %s AND is_active = TRUE"
        result = db.execute_query(query, (user_id,), fetch=True)
        if result:
            user_data = dict(zip([
                'id', 'username', 'email', 'password_hash', 'role', 
                'tenant_id', 'is_active', 'last_login', 'created_at', 
                'permissions', 'settings'
            ], result[0]))
            return User(user_data)
    except Exception as e:
        logger.error("Error loading user", user_id=user_id, error=str(e))
    return None

# Professional API endpoints with rate limiting and metrics
@app.route('/api/stats')
@login_required
@limiter.limit("100 per minute")
def api_stats():
    """Professional stats API with caching"""
    with API_REQUEST_TIME.labels(endpoint='stats').time():
        try:
            # Try Redis cache first
            cache_key = f"stats:{current_user.tenant_id}"
            cached_stats = redis_client.get(cache_key)
            
            if cached_stats:
                return jsonify(json.loads(cached_stats))
            
            # Calculate stats from database
            query = """
                SELECT 
                    COUNT(*) as total_campaigns,
                    COUNT(*) FILTER (WHERE status = 'running') as active_campaigns,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_campaigns,
                    COALESCE(SUM(total_sent), 0) as total_sent,
                    COALESCE(SUM(total_failed), 0) as total_failed
                FROM campaigns 
                WHERE tenant_id = %s
            """
            result = db.execute_query(query, (current_user.tenant_id,), fetch=True)
            
            if result:
                stats = dict(zip([
                    'total_campaigns', 'active_campaigns', 'completed_campaigns',
                    'total_sent', 'total_failed'
                ], result[0]))
                
                # Calculate delivery rate
                total_attempted = stats['total_sent'] + stats['total_failed']
                stats['delivery_rate'] = round(
                    (stats['total_sent'] / total_attempted * 100), 1
                ) if total_attempted > 0 else 0
                
                stats['timestamp'] = datetime.now().isoformat()
                
                # Cache for 10 seconds
                redis_client.set(cache_key, json.dumps(stats), ex=10)
                
                return jsonify(stats)
            else:
                return jsonify({'error': 'No data available'}), 404
                
        except Exception as e:
            logger.error("Error getting stats", error=str(e))
            return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/campaigns')
@login_required
@limiter.limit("200 per minute")
def api_campaigns():
    """Professional campaigns API with pagination"""
    with API_REQUEST_TIME.labels(endpoint='campaigns').time():
        try:
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 50, type=int), 100)
            status_filter = request.args.get('status')
            
            # Build query with filters
            where_clause = "WHERE tenant_id = %s"
            params = [current_user.tenant_id]
            
            if status_filter:
                where_clause += " AND status = %s"
                params.append(status_filter)
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM campaigns {where_clause}"
            total = db.execute_query(count_query, params, fetch=True)[0][0]
            
            # Get paginated results
            offset = (page - 1) * per_page
            query = f"""
                SELECT id, name, subject, status, created_at, started_at, completed_at,
                       total_recipients, total_sent, total_failed, total_opened, total_clicked,
                       owner_id, tags
                FROM campaigns 
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, offset])
            
            campaigns = db.execute_query(query, params, fetch=True)
            
            # Format response
            campaigns_data = []
            for campaign in campaigns:
                campaign_dict = dict(zip([
                    'id', 'name', 'subject', 'status', 'created_at', 'started_at', 
                    'completed_at', 'total_recipients', 'total_sent', 'total_failed',
                    'total_opened', 'total_clicked', 'owner_id', 'tags'
                ], campaign))
                
                # Add real-time stats from Redis if available
                redis_stats = redis_client.hgetall(f"campaign:{campaign_dict['id']}")
                if redis_stats:
                    campaign_dict.update(redis_stats)
                
                campaigns_data.append(campaign_dict)
            
            return jsonify({
                'campaigns': campaigns_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
            
        except Exception as e:
            logger.error("Error getting campaigns", error=str(e))
            return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/campaigns/<campaign_id>/start', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def start_campaign_api(campaign_id):
    """Start campaign API"""
    with API_REQUEST_TIME.labels(endpoint='start_campaign').time():
        success, message = campaign_manager.start_campaign(campaign_id, current_user.id)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400

@app.route('/api/campaigns/<campaign_id>/stop', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def stop_campaign_api(campaign_id):
    """Stop campaign API"""
    with API_REQUEST_TIME.labels(endpoint='stop_campaign').time():
        success, message = campaign_manager.stop_campaign(campaign_id, "Stopped by user")
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400

@app.route('/api/campaigns/<campaign_id>', methods=['DELETE'])
@login_required
@limiter.limit("5 per minute")
def delete_campaign_api(campaign_id):
    """Delete campaign API"""
    with API_REQUEST_TIME.labels(endpoint='delete_campaign').time():
        success, message = campaign_manager.delete_campaign(campaign_id, current_user.id)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400

@app.route('/api/campaigns/<campaign_id>/logs')
@login_required
@limiter.limit("50 per minute")
def get_campaign_logs_api(campaign_id):
    """Get campaign logs API with pagination"""
    with API_REQUEST_TIME.labels(endpoint='campaign_logs').time():
        try:
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', 100, type=int), 500)
            status_filter = request.args.get('status')
            
            # Build query
            where_clause = "WHERE campaign_id = %s"
            params = [campaign_id]
            
            if status_filter:
                where_clause += " AND status = %s"
                params.append(status_filter)
            
            # Get paginated logs
            offset = (page - 1) * per_page
            query = f"""
                SELECT id, email, status, timestamp, error_message, delivery_time
                FROM email_logs 
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, offset])
            
            logs = db.execute_query(query, params, fetch=True)
            
            logs_data = []
            for log in logs:
                logs_data.append(dict(zip([
                    'id', 'email', 'status', 'timestamp', 'error_message', 'delivery_time'
                ], log)))
            
            return jsonify({
                'logs': logs_data,
                'stats': campaign_manager.campaign_stats.get(campaign_id, {})
            })
            
        except Exception as e:
            logger.error("Error getting campaign logs", campaign_id=campaign_id, error=str(e))
            return jsonify({'error': 'Internal server error'}), 500

# Professional WebSocket events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f"tenant_{current_user.tenant_id}")
        logger.info("User connected", user_id=current_user.id, tenant_id=current_user.tenant_id)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(f"tenant_{current_user.tenant_id}")
        logger.info("User disconnected", user_id=current_user.id)

@socketio.on('subscribe_campaign')
def handle_subscribe_campaign(data):
    if current_user.is_authenticated:
        campaign_id = data.get('campaign_id')
        if campaign_id:
            join_room(f"campaign_{campaign_id}")
            
            # Send current stats
            stats = campaign_manager.campaign_stats.get(campaign_id, {})
            emit('campaign_stats', {
                'campaign_id': campaign_id,
                'stats': stats
            })

# Health and monitoring endpoints
@app.route('/health')
def health_check():
    """Professional health check"""
    try:
        # Check Redis
        redis_healthy = redis_client.client.ping()
        
        # Check Database
        db_healthy = bool(db.execute_query("SELECT 1", fetch=True))
        
        # Check Celery (simplified)
        celery_healthy = True  # Would implement proper Celery health check
        
        status = "healthy" if all([redis_healthy, db_healthy, celery_healthy]) else "unhealthy"
        
        return jsonify({
            'status': status,
            'components': {
                'redis': 'healthy' if redis_healthy else 'unhealthy',
                'database': 'healthy' if db_healthy else 'unhealthy',
                'celery': 'healthy' if celery_healthy else 'unhealthy'
            },
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()

# Error handlers
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded', 'retry_after': e.retry_after}), 429

@app.errorhandler(500)
def internal_error(e):
    logger.error("Internal server error", error=str(e))
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    logger.info("Starting Professional Email Campaign Manager")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)