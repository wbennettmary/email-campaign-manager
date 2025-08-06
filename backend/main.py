"""
PROFESSIONAL EMAIL CAMPAIGN MANAGER - BACKEND
Modern FastAPI backend with async/await, Redis, PostgreSQL, and Celery
Built for reliability, scalability, and performance
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import logging
from contextlib import asynccontextmanager

# FastAPI and async imports
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import uvicorn

# Database and caching
import asyncpg
import aioredis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, selectinload
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
import sqlalchemy as sa

# Background tasks
from celery import Celery
import requests

# Validation
from pydantic import BaseModel, EmailStr, Field, validator
from enum import Enum

# Security
import jwt
from passlib.context import CryptContext
import secrets

# Monitoring
from prometheus_fastapi_instrumentator import Instrumentator

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://campaign_user:campaign_pass@localhost/campaign_db")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

settings = Settings()

# Database setup
engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=20, max_overflow=30)
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

# Redis setup
redis_client = None

# Celery setup
celery_app = Celery(
    "campaign_manager",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['backend.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'send_campaign_emails': {'queue': 'email_queue'},
        'process_campaign_batch': {'queue': 'campaign_queue'},
    },
    worker_concurrency=10,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Enums
class CampaignStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"

class EmailStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

class EmailAccount(Base):
    __tablename__ = "email_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    provider = Column(String(100), nullable=False)  # zoho, gmail, etc.
    credentials = Column(JSON, nullable=False)  # encrypted credentials
    is_active = Column(Boolean, default=True)
    daily_limit = Column(Integer, default=10000)
    hourly_limit = Column(Integer, default=1000)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class DataList(Base):
    __tablename__ = "data_lists"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    file_path = Column(String(500))
    total_count = Column(Integer, default=0)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    subject = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(50), default=CampaignStatus.DRAFT, index=True)
    
    # Relationships
    account_id = Column(UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=False)
    data_list_id = Column(UUID(as_uuid=True), ForeignKey("data_lists.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Campaign settings
    rate_limits = Column(JSON, default={})
    test_config = Column(JSON, default={})
    start_line = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Statistics
    total_recipients = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_campaigns_status_created', 'status', 'created_at'),
        Index('idx_campaigns_user_status', 'created_by', 'status'),
    )

class EmailLog(Base):
    __tablename__ = "email_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    error_message = Column(Text)
    delivery_time = Column(Integer)  # milliseconds
    
    __table_args__ = (
        Index('idx_email_logs_campaign_status', 'campaign_id', 'status'),
        Index('idx_email_logs_timestamp', 'timestamp'),
    )

# Pydantic Models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool
    created_at: datetime

class EmailAccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    provider: str = Field(..., regex="^(zoho|gmail|outlook)$")
    credentials: Dict[str, Any]
    daily_limit: int = Field(default=10000, ge=1, le=50000)
    hourly_limit: int = Field(default=1000, ge=1, le=5000)

class EmailAccountResponse(BaseModel):
    id: str
    name: str
    email: str
    provider: str
    is_active: bool
    daily_limit: int
    hourly_limit: int
    created_at: datetime

class DataListCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    file_content: str  # Base64 encoded file content

class DataListResponse(BaseModel):
    id: str
    name: str
    total_count: int
    created_at: datetime

class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    account_id: str
    data_list_id: str
    rate_limits: Optional[Dict[str, Any]] = {}
    test_config: Optional[Dict[str, Any]] = {}
    start_line: int = Field(default=0, ge=0)

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    account_id: Optional[str] = None
    data_list_id: Optional[str] = None
    rate_limits: Optional[Dict[str, Any]] = None
    test_config: Optional[Dict[str, Any]] = None
    start_line: Optional[int] = None

class CampaignResponse(BaseModel):
    id: str
    name: str
    subject: str
    message: str
    status: str
    account_id: str
    data_list_id: str
    rate_limits: Dict[str, Any]
    test_config: Dict[str, Any]
    start_line: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_recipients: int
    total_sent: int
    total_failed: int

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.campaign_subscribers: Dict[str, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        # Remove from campaign subscriptions
        for campaign_id, subscribers in self.campaign_subscribers.items():
            if client_id in subscribers:
                subscribers.remove(client_id)
        logger.info(f"Client {client_id} disconnected")
    
    async def subscribe_to_campaign(self, client_id: str, campaign_id: str):
        if campaign_id not in self.campaign_subscribers:
            self.campaign_subscribers[campaign_id] = []
        if client_id not in self.campaign_subscribers[campaign_id]:
            self.campaign_subscribers[campaign_id].append(client_id)
    
    async def broadcast_to_campaign(self, campaign_id: str, message: dict):
        if campaign_id in self.campaign_subscribers:
            for client_id in self.campaign_subscribers[campaign_id]:
                if client_id in self.active_connections:
                    try:
                        await self.active_connections[client_id].send_json(message)
                    except Exception as e:
                        logger.error(f"Error sending message to {client_id}: {e}")
                        self.disconnect(client_id)
    
    async def broadcast_to_all(self, message: dict):
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)
        
        for client_id in disconnected:
            self.disconnect(client_id)

manager = ConnectionManager()

# Database dependency
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

# Authentication
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    result = await db.execute(sa.select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# Startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global redis_client
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Application started")
    yield
    
    # Shutdown
    if redis_client:
        await redis_client.close()
    logger.info("Application shutdown")

# FastAPI app
app = FastAPI(
    title="Professional Email Campaign Manager",
    description="High-performance, scalable email campaign management system",
    version="2.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus monitoring
Instrumentator().instrument(app).expose(app)

# API Routes

# Authentication
@app.post("/api/auth/register")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(sa.select(User).where(
        (User.username == user.username) | (User.email == user.email)
    ))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Create user
    hashed_password = pwd_context.hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return {"message": "User created successfully", "user_id": str(db_user.id)}

@app.post("/api/auth/login")
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(sa.select(User).where(User.username == user.username))
    db_user = result.scalar_one_or_none()
    
    if not db_user or not pwd_context.verify(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not db_user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")
    
    # Update last login
    db_user.last_login = datetime.utcnow()
    await db.commit()
    
    access_token = create_access_token(data={"sub": str(db_user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(db_user)
    }

# Email Accounts
@app.post("/api/accounts", response_model=EmailAccountResponse)
async def create_email_account(
    account: EmailAccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_account = EmailAccount(
        name=account.name,
        email=account.email,
        provider=account.provider,
        credentials=account.credentials,  # In production, encrypt this
        daily_limit=account.daily_limit,
        hourly_limit=account.hourly_limit,
        created_by=current_user.id
    )
    db.add(db_account)
    await db.commit()
    await db.refresh(db_account)
    
    # Cache in Redis
    await redis_client.hset(
        f"account:{db_account.id}",
        mapping={
            "name": account.name,
            "email": account.email,
            "provider": account.provider,
            "is_active": "true"
        }
    )
    
    return EmailAccountResponse.from_orm(db_account)

@app.get("/api/accounts", response_model=List[EmailAccountResponse])
async def get_email_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        sa.select(EmailAccount).where(
            EmailAccount.created_by == current_user.id,
            EmailAccount.is_active == True
        ).order_by(EmailAccount.created_at.desc())
    )
    accounts = result.scalars().all()
    return [EmailAccountResponse.from_orm(account) for account in accounts]

# Data Lists
@app.post("/api/data-lists", response_model=DataListResponse)
async def create_data_list(
    data_list: DataListCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Process file content (simplified - in production, handle file upload properly)
    import base64
    import tempfile
    
    try:
        file_content = base64.b64decode(data_list.file_content).decode('utf-8')
        emails = [line.strip() for line in file_content.split('\n') if '@' in line.strip()]
        
        # Save to temporary file (in production, use proper file storage)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('\n'.join(emails))
            file_path = f.name
        
        db_data_list = DataList(
            name=data_list.name,
            file_path=file_path,
            total_count=len(emails),
            created_by=current_user.id
        )
        db.add(db_data_list)
        await db.commit()
        await db.refresh(db_data_list)
        
        return DataListResponse.from_orm(db_data_list)
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")

@app.get("/api/data-lists", response_model=List[DataListResponse])
async def get_data_lists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        sa.select(DataList).where(
            DataList.created_by == current_user.id
        ).order_by(DataList.created_at.desc())
    )
    data_lists = result.scalars().all()
    return [DataListResponse.from_orm(data_list) for data_list in data_lists]

# Campaigns
@app.post("/api/campaigns", response_model=CampaignResponse)
async def create_campaign(
    campaign: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate account and data list exist
    account_result = await db.execute(
        sa.select(EmailAccount).where(
            EmailAccount.id == campaign.account_id,
            EmailAccount.created_by == current_user.id,
            EmailAccount.is_active == True
        )
    )
    if not account_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Email account not found")
    
    data_list_result = await db.execute(
        sa.select(DataList).where(
            DataList.id == campaign.data_list_id,
            DataList.created_by == current_user.id
        )
    )
    data_list = data_list_result.scalar_one_or_none()
    if not data_list:
        raise HTTPException(status_code=404, detail="Data list not found")
    
    db_campaign = Campaign(
        name=campaign.name,
        subject=campaign.subject,
        message=campaign.message,
        account_id=campaign.account_id,
        data_list_id=campaign.data_list_id,
        created_by=current_user.id,
        rate_limits=campaign.rate_limits,
        test_config=campaign.test_config,
        start_line=campaign.start_line,
        total_recipients=data_list.total_count,
        status=CampaignStatus.READY
    )
    db.add(db_campaign)
    await db.commit()
    await db.refresh(db_campaign)
    
    # Cache in Redis
    await redis_client.hset(
        f"campaign:{db_campaign.id}",
        mapping={
            "status": CampaignStatus.READY,
            "total_recipients": data_list.total_count,
            "total_sent": "0",
            "total_failed": "0"
        }
    )
    
    # Broadcast update
    await manager.broadcast_to_all({
        "type": "campaign_created",
        "campaign": CampaignResponse.from_orm(db_campaign).dict()
    })
    
    return CampaignResponse.from_orm(db_campaign)

@app.get("/api/campaigns", response_model=List[CampaignResponse])
async def get_campaigns(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = sa.select(Campaign).where(Campaign.created_by == current_user.id)
    
    if status:
        query = query.where(Campaign.status == status)
    
    query = query.order_by(Campaign.created_at.desc())
    
    result = await db.execute(query)
    campaigns = result.scalars().all()
    
    # Enhance with real-time data from Redis
    enhanced_campaigns = []
    for campaign in campaigns:
        campaign_data = CampaignResponse.from_orm(campaign)
        
        # Get real-time stats from Redis
        redis_stats = await redis_client.hgetall(f"campaign:{campaign.id}")
        if redis_stats:
            campaign_data.total_sent = int(redis_stats.get("total_sent", campaign.total_sent))
            campaign_data.total_failed = int(redis_stats.get("total_failed", campaign.total_failed))
            if redis_stats.get("status"):
                campaign_data.status = redis_stats["status"]
        
        enhanced_campaigns.append(campaign_data)
    
    return enhanced_campaigns

@app.post("/api/campaigns/{campaign_id}/start")
async def start_campaign(
    campaign_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get campaign
    result = await db.execute(
        sa.select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.created_by == current_user.id
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status == CampaignStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Campaign is already running")
    
    # Update status to running
    campaign.status = CampaignStatus.RUNNING
    campaign.started_at = datetime.utcnow()
    await db.commit()
    
    # Update Redis
    await redis_client.hset(
        f"campaign:{campaign_id}",
        mapping={
            "status": CampaignStatus.RUNNING,
            "started_at": campaign.started_at.isoformat()
        }
    )
    
    # Start campaign processing with Celery
    from backend.tasks import process_campaign
    process_campaign.delay(str(campaign_id))
    
    # Broadcast update
    await manager.broadcast_to_campaign(campaign_id, {
        "type": "campaign_started",
        "campaign_id": campaign_id,
        "status": CampaignStatus.RUNNING,
        "started_at": campaign.started_at.isoformat()
    })
    
    return {"message": "Campaign started successfully", "status": CampaignStatus.RUNNING}

@app.post("/api/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        sa.select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.created_by == current_user.id
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status != CampaignStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Campaign is not running")
    
    # Update status
    campaign.status = CampaignStatus.PAUSED
    await db.commit()
    
    # Update Redis
    await redis_client.hset(f"campaign:{campaign_id}", "status", CampaignStatus.PAUSED)
    
    # Broadcast update
    await manager.broadcast_to_campaign(campaign_id, {
        "type": "campaign_paused",
        "campaign_id": campaign_id,
        "status": CampaignStatus.PAUSED
    })
    
    return {"message": "Campaign paused successfully", "status": CampaignStatus.PAUSED}

@app.delete("/api/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        sa.select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.created_by == current_user.id
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Delete from database (cascade will handle email_logs)
    await db.delete(campaign)
    await db.commit()
    
    # Clean up Redis
    await redis_client.delete(f"campaign:{campaign_id}")
    
    # Broadcast update
    await manager.broadcast_to_all({
        "type": "campaign_deleted",
        "campaign_id": campaign_id
    })
    
    return {"message": "Campaign deleted successfully"}

# Statistics
@app.get("/api/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Try Redis cache first
    cache_key = f"stats:{current_user.id}"
    cached_stats = await redis_client.get(cache_key)
    
    if cached_stats:
        return json.loads(cached_stats)
    
    # Calculate from database
    result = await db.execute(
        sa.text("""
            SELECT 
                COUNT(*) as total_campaigns,
                COUNT(*) FILTER (WHERE status = 'running') as active_campaigns,
                COUNT(*) FILTER (WHERE status = 'completed') as completed_campaigns,
                COALESCE(SUM(total_sent), 0) as total_sent,
                COALESCE(SUM(total_failed), 0) as total_failed
            FROM campaigns 
            WHERE created_by = :user_id
        """),
        {"user_id": current_user.id}
    )
    
    stats_row = result.fetchone()
    
    stats = {
        "total_campaigns": stats_row[0],
        "active_campaigns": stats_row[1],
        "completed_campaigns": stats_row[2],
        "total_sent": stats_row[3],
        "total_failed": stats_row[4],
        "delivery_rate": round((stats_row[3] / (stats_row[3] + stats_row[4]) * 100), 1) if (stats_row[3] + stats_row[4]) > 0 else 0,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Cache for 10 seconds
    await redis_client.setex(cache_key, 10, json.dumps(stats))
    
    return stats

# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "subscribe_campaign":
                campaign_id = data.get("campaign_id")
                if campaign_id:
                    await manager.subscribe_to_campaign(client_id, campaign_id)
                    
                    # Send current campaign stats
                    redis_stats = await redis_client.hgetall(f"campaign:{campaign_id}")
                    if redis_stats:
                        await websocket.send_json({
                            "type": "campaign_stats",
                            "campaign_id": campaign_id,
                            "stats": redis_stats
                        })
                        
    except WebSocketDisconnect:
        manager.disconnect(client_id)

# Health check
@app.get("/health")
async def health_check():
    try:
        # Check database
        await engine.execute(sa.text("SELECT 1"))
        db_healthy = True
    except:
        db_healthy = False
    
    try:
        # Check Redis
        await redis_client.ping()
        redis_healthy = True
    except:
        redis_healthy = False
    
    status = "healthy" if all([db_healthy, redis_healthy]) else "unhealthy"
    
    return {
        "status": status,
        "components": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
        log_level="info"
    )