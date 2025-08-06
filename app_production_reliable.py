#!/usr/bin/env python3
"""
Production-Reliable Email Campaign Manager
- Rock-solid reliability for production use
- Automatic error recovery and retry mechanisms
- Persistent campaign state management
- Real-time monitoring with failsafe mechanisms
- Designed to never stop or freeze campaigns
"""

import asyncio
import json
import os
import time
import logging
import traceback
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uuid
from collections import defaultdict
import threading
import sqlite3
import pickle
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# Configure robust logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('campaign_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# FastAPI app with production settings
app = FastAPI(
    title="Production-Reliable Email Campaign Manager",
    description="Rock-solid reliable email campaign manager for 100+ concurrent campaigns",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Production-grade persistent storage
class ReliableStorage:
    def __init__(self, db_path: str = "campaign_manager.db"):
        self.db_path = db_path
        self.lock = threading.RLock()
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with proper schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    account_id INTEGER,
                    data_list_id INTEGER,
                    subject TEXT,
                    message TEXT,
                    from_name TEXT,
                    start_line INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'ready',
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    total_sent INTEGER DEFAULT 0,
                    total_failed INTEGER DEFAULT 0,
                    total_attempted INTEGER DEFAULT 0,
                    last_email_index INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    config TEXT DEFAULT '{}'
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS campaign_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT,
                    email TEXT,
                    status TEXT,
                    message TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS email_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT,
                    email TEXT,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT,
                    processed_at TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')
            
            # Create indexes for performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_campaign_logs_campaign_id ON campaign_logs(campaign_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_email_queue_status ON email_queue(status)')
            
            conn.commit()
    
    def save_campaign(self, campaign_data: dict):
        """Save campaign with error handling"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('''
                        INSERT OR REPLACE INTO campaigns 
                        (id, name, account_id, data_list_id, subject, message, from_name, 
                         start_line, status, created_at, started_at, completed_at, 
                         total_sent, total_failed, total_attempted, last_email_index, 
                         error_count, last_error, config)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        campaign_data.get('id'),
                        campaign_data.get('name'),
                        campaign_data.get('account_id'),
                        campaign_data.get('data_list_id'),
                        campaign_data.get('subject'),
                        campaign_data.get('message'),
                        campaign_data.get('from_name'),
                        campaign_data.get('start_line', 1),
                        campaign_data.get('status', 'ready'),
                        campaign_data.get('created_at'),
                        campaign_data.get('started_at'),
                        campaign_data.get('completed_at'),
                        campaign_data.get('total_sent', 0),
                        campaign_data.get('total_failed', 0),
                        campaign_data.get('total_attempted', 0),
                        campaign_data.get('last_email_index', 0),
                        campaign_data.get('error_count', 0),
                        campaign_data.get('last_error'),
                        json.dumps(campaign_data.get('config', {}))
                    ))
                    conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving campaign {campaign_data.get('id')}: {e}")
            return False
    
    def get_campaign(self, campaign_id: str) -> dict:
        """Get campaign with error handling"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,))
                    row = cursor.fetchone()
                    if row:
                        campaign = dict(row)
                        campaign['config'] = json.loads(campaign.get('config', '{}'))
                        return campaign
            return {}
        except Exception as e:
            logger.error(f"Error getting campaign {campaign_id}: {e}")
            return {}
    
    def get_all_campaigns(self) -> dict:
        """Get all campaigns"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute('SELECT * FROM campaigns ORDER BY created_at DESC')
                    campaigns = {}
                    for row in cursor.fetchall():
                        campaign = dict(row)
                        campaign['config'] = json.loads(campaign.get('config', '{}'))
                        campaigns[campaign['id']] = campaign
                    return campaigns
        except Exception as e:
            logger.error(f"Error getting all campaigns: {e}")
            return {}
    
    def log_email(self, campaign_id: str, email: str, status: str, message: str = ""):
        """Log email with timestamp"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('''
                        INSERT INTO campaign_logs (campaign_id, email, status, message, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (campaign_id, email, status, message, datetime.now().isoformat()))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error logging email for campaign {campaign_id}: {e}")
    
    def get_campaign_logs(self, campaign_id: str, limit: int = 1000) -> list:
        """Get campaign logs"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute('''
                        SELECT * FROM campaign_logs 
                        WHERE campaign_id = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ''', (campaign_id, limit))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting logs for campaign {campaign_id}: {e}")
            return []

# Global storage instance
storage = ReliableStorage()

# Reliable WebSocket connection manager
class ReliableConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.campaign_subscribers: Dict[str, List[WebSocket]] = defaultdict(list)
        self.heartbeat_task = None
        self.start_heartbeat()

    def start_heartbeat(self):
        """Start heartbeat to keep connections alive"""
        async def heartbeat():
            while True:
                try:
                    await asyncio.sleep(30)  # Every 30 seconds
                    await self.send_heartbeat()
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                    await asyncio.sleep(5)
        
        if not self.heartbeat_task:
            self.heartbeat_task = asyncio.create_task(heartbeat())

    async def send_heartbeat(self):
        """Send heartbeat to all connections"""
        message = json.dumps({"type": "heartbeat", "timestamp": datetime.now().isoformat()})
        
        # Clean up disconnected connections
        disconnected = []
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from campaign subscriptions
        for connections in self.campaign_subscribers.values():
            if websocket in connections:
                connections.remove(websocket)
        
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast_campaign_update(self, campaign_id: str, data: dict):
        """Broadcast campaign update with error handling"""
        message = json.dumps({
            "type": "campaign_update",
            "campaign_id": campaign_id,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send to campaign subscribers
        connections = self.campaign_subscribers.get(campaign_id, [])
        disconnected = []
        
        for connection in connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            connections.remove(connection)
        
        # Also send to all active connections
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except:
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

    async def broadcast_stats_update(self, stats: dict):
        """Broadcast stats update"""
        message = json.dumps({
            "type": "stats_update",
            "data": stats,
            "timestamp": datetime.now().isoformat()
        })
        
        disconnected = []
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            if connection in self.active_connections:
                self.active_connections.remove(connection)

# Global connection manager
manager = ReliableConnectionManager()

# Reliable campaign processor
class ReliableCampaignProcessor:
    def __init__(self):
        self.running_campaigns = {}
        self.campaign_tasks = {}
        self.recovery_task = None
        self.stats_task = None
        self.start_background_tasks()
    
    def start_background_tasks(self):
        """Start background tasks for monitoring and recovery"""
        async def recovery_loop():
            while True:
                try:
                    await self.recover_stalled_campaigns()
                    await asyncio.sleep(60)  # Check every minute
                except Exception as e:
                    logger.error(f"Recovery loop error: {e}")
                    await asyncio.sleep(30)
        
        async def stats_loop():
            while True:
                try:
                    await self.broadcast_stats()
                    await asyncio.sleep(10)  # Update stats every 10 seconds
                except Exception as e:
                    logger.error(f"Stats loop error: {e}")
                    await asyncio.sleep(30)
        
        if not self.recovery_task:
            self.recovery_task = asyncio.create_task(recovery_loop())
        
        if not self.stats_task:
            self.stats_task = asyncio.create_task(stats_loop())
    
    async def recover_stalled_campaigns(self):
        """Recover campaigns that may have stalled"""
        try:
            campaigns = storage.get_all_campaigns()
            current_time = datetime.now()
            
            for campaign_id, campaign in campaigns.items():
                if campaign.get('status') == 'running':
                    # Check if campaign has been running too long without updates
                    started_at = campaign.get('started_at')
                    if started_at:
                        start_time = datetime.fromisoformat(started_at)
                        runtime = (current_time - start_time).total_seconds()
                        
                        # If running for more than 2 hours, consider it stalled
                        if runtime > 7200:
                            logger.warning(f"Recovering stalled campaign {campaign_id}")
                            campaign['status'] = 'failed'
                            campaign['last_error'] = 'Campaign stalled - auto-recovered'
                            campaign['completed_at'] = current_time.isoformat()
                            storage.save_campaign(campaign)
                            
                            # Remove from running campaigns
                            if campaign_id in self.running_campaigns:
                                del self.running_campaigns[campaign_id]
                            
                            # Cancel task if exists
                            if campaign_id in self.campaign_tasks:
                                self.campaign_tasks[campaign_id].cancel()
                                del self.campaign_tasks[campaign_id]
                            
                            # Broadcast update
                            await manager.broadcast_campaign_update(campaign_id, campaign)
        
        except Exception as e:
            logger.error(f"Error in recovery process: {e}")
    
    async def broadcast_stats(self):
        """Broadcast updated statistics"""
        try:
            campaigns = storage.get_all_campaigns()
            
            total_campaigns = len(campaigns)
            active_campaigns = sum(1 for c in campaigns.values() if c.get('status') == 'running')
            total_sent = sum(c.get('total_sent', 0) for c in campaigns.values())
            total_failed = sum(c.get('total_failed', 0) for c in campaigns.values())
            
            stats = {
                "total_campaigns": total_campaigns,
                "active_campaigns": active_campaigns,
                "total_sent": total_sent,
                "total_failed": total_failed,
                "delivery_rate": round((total_sent / (total_sent + total_failed) * 100), 1) if (total_sent + total_failed) > 0 else 0,
                "timestamp": datetime.now().isoformat(),
                "running_campaigns": list(self.running_campaigns.keys())
            }
            
            await manager.broadcast_stats_update(stats)
        
        except Exception as e:
            logger.error(f"Error broadcasting stats: {e}")
    
    async def start_campaign(self, campaign_id: str):
        """Start campaign with robust error handling"""
        try:
            campaign = storage.get_campaign(campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")
            
            if campaign.get('status') == 'running':
                raise ValueError(f"Campaign {campaign_id} is already running")
            
            # Mark as running
            campaign['status'] = 'running'
            campaign['started_at'] = datetime.now().isoformat()
            campaign['error_count'] = 0
            campaign['last_error'] = None
            storage.save_campaign(campaign)
            
            # Add to running campaigns
            self.running_campaigns[campaign_id] = campaign
            
            # Start processing task
            task = asyncio.create_task(self._process_campaign(campaign_id))
            self.campaign_tasks[campaign_id] = task
            
            # Broadcast update
            await manager.broadcast_campaign_update(campaign_id, campaign)
            
            logger.info(f"Started campaign {campaign_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting campaign {campaign_id}: {e}")
            # Update campaign status to failed
            campaign = storage.get_campaign(campaign_id)
            if campaign:
                campaign['status'] = 'failed'
                campaign['last_error'] = str(e)
                storage.save_campaign(campaign)
                await manager.broadcast_campaign_update(campaign_id, campaign)
            return False
    
    async def stop_campaign(self, campaign_id: str):
        """Stop campaign safely"""
        try:
            # Cancel task if exists
            if campaign_id in self.campaign_tasks:
                self.campaign_tasks[campaign_id].cancel()
                del self.campaign_tasks[campaign_id]
            
            # Remove from running campaigns
            if campaign_id in self.running_campaigns:
                del self.running_campaigns[campaign_id]
            
            # Update database
            campaign = storage.get_campaign(campaign_id)
            if campaign:
                campaign['status'] = 'stopped'
                campaign['completed_at'] = datetime.now().isoformat()
                storage.save_campaign(campaign)
                await manager.broadcast_campaign_update(campaign_id, campaign)
            
            logger.info(f"Stopped campaign {campaign_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping campaign {campaign_id}: {e}")
            return False
    
    async def _process_campaign(self, campaign_id: str):
        """Process campaign with robust error handling and retry logic"""
        try:
            campaign = storage.get_campaign(campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found during processing")
                return
            
            logger.info(f"Processing campaign {campaign_id}: {campaign.get('name')}")
            
            # Get email list (simulate for now)
            emails = await self._get_email_list(campaign.get('data_list_id'), campaign.get('start_line', 1))
            
            if not emails:
                campaign['status'] = 'failed'
                campaign['last_error'] = 'No emails found in data list'
                storage.save_campaign(campaign)
                await manager.broadcast_campaign_update(campaign_id, campaign)
                return
            
            # Resume from last processed email if campaign was restarted
            start_index = campaign.get('last_email_index', 0)
            emails_to_process = emails[start_index:]
            
            logger.info(f"Campaign {campaign_id}: Processing {len(emails_to_process)} emails (starting from index {start_index})")
            
            batch_size = 50  # Process in smaller batches for reliability
            batch_delay = 2.0  # 2 seconds between batches
            
            for i in range(0, len(emails_to_process), batch_size):
                try:
                    # Check if campaign should be stopped
                    current_campaign = storage.get_campaign(campaign_id)
                    if not current_campaign or current_campaign.get('status') != 'running':
                        logger.info(f"Campaign {campaign_id} stopped during processing")
                        break
                    
                    batch = emails_to_process[i:i + batch_size]
                    batch_sent = 0
                    batch_failed = 0
                    
                    # Process batch with individual error handling
                    for j, email in enumerate(batch):
                        try:
                            # Update progress
                            current_index = start_index + i + j
                            campaign['last_email_index'] = current_index
                            
                            # Simulate email sending (replace with actual Zoho API)
                            success = await self._send_email_reliable(campaign, email)
                            
                            if success:
                                batch_sent += 1
                                storage.log_email(campaign_id, email, 'sent', 'Successfully sent')
                            else:
                                batch_failed += 1
                                storage.log_email(campaign_id, email, 'failed', 'Send failed')
                            
                            # Small delay between emails
                            await asyncio.sleep(0.1)
                            
                        except Exception as e:
                            logger.error(f"Error sending email {email} in campaign {campaign_id}: {e}")
                            batch_failed += 1
                            storage.log_email(campaign_id, email, 'failed', str(e))
                    
                    # Update campaign statistics
                    campaign['total_sent'] = campaign.get('total_sent', 0) + batch_sent
                    campaign['total_failed'] = campaign.get('total_failed', 0) + batch_failed
                    campaign['total_attempted'] = campaign['total_sent'] + campaign['total_failed']
                    
                    # Save progress
                    storage.save_campaign(campaign)
                    
                    # Broadcast real-time update
                    await manager.broadcast_campaign_update(campaign_id, campaign)
                    
                    logger.info(f"Campaign {campaign_id}: Batch completed. Sent: {batch_sent}, Failed: {batch_failed}")
                    
                    # Delay between batches
                    await asyncio.sleep(batch_delay)
                    
                except Exception as e:
                    logger.error(f"Error processing batch in campaign {campaign_id}: {e}")
                    campaign['error_count'] = campaign.get('error_count', 0) + 1
                    campaign['last_error'] = str(e)
                    
                    # If too many errors, stop campaign
                    if campaign['error_count'] >= 5:
                        campaign['status'] = 'failed'
                        campaign['completed_at'] = datetime.now().isoformat()
                        storage.save_campaign(campaign)
                        await manager.broadcast_campaign_update(campaign_id, campaign)
                        logger.error(f"Campaign {campaign_id} failed due to too many errors")
                        return
                    
                    # Wait before retrying
                    await asyncio.sleep(30)
            
            # Mark campaign as completed
            campaign['status'] = 'completed'
            campaign['completed_at'] = datetime.now().isoformat()
            storage.save_campaign(campaign)
            
            # Remove from running campaigns
            if campaign_id in self.running_campaigns:
                del self.running_campaigns[campaign_id]
            
            await manager.broadcast_campaign_update(campaign_id, campaign)
            
            logger.info(f"Campaign {campaign_id} completed successfully. Sent: {campaign.get('total_sent', 0)}, Failed: {campaign.get('total_failed', 0)}")
            
        except Exception as e:
            logger.error(f"Critical error in campaign {campaign_id}: {e}")
            logger.error(traceback.format_exc())
            
            # Mark campaign as failed
            campaign = storage.get_campaign(campaign_id)
            if campaign:
                campaign['status'] = 'failed'
                campaign['last_error'] = str(e)
                campaign['completed_at'] = datetime.now().isoformat()
                storage.save_campaign(campaign)
                await manager.broadcast_campaign_update(campaign_id, campaign)
            
            # Clean up
            if campaign_id in self.running_campaigns:
                del self.running_campaigns[campaign_id]
            if campaign_id in self.campaign_tasks:
                del self.campaign_tasks[campaign_id]
    
    async def _get_email_list(self, data_list_id: int, start_line: int = 1) -> List[str]:
        """Get email list with error handling"""
        try:
            # This is a simulation - replace with your actual data list logic
            # For demo, return a list of test emails
            base_emails = [f"test{i}@example.com" for i in range(start_line, start_line + 2000)]
            return base_emails
        except Exception as e:
            logger.error(f"Error getting email list for data_list_id {data_list_id}: {e}")
            return []
    
    async def _send_email_reliable(self, campaign: dict, email: str) -> bool:
        """Reliable email sending with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Simulate email sending (replace with your actual Zoho API logic)
                await asyncio.sleep(0.01)  # Simulate send time
                
                # Simulate random failures for testing
                import random
                if random.random() < 0.1:  # 10% failure rate for simulation
                    raise Exception("Simulated send failure")
                
                return True
                
            except Exception as e:
                logger.warning(f"Email send attempt {attempt + 1} failed for {email}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All send attempts failed for {email}")
        
        return False

# Global campaign processor
processor = ReliableCampaignProcessor()

# Pydantic models
class CampaignCreate(BaseModel):
    name: str
    account_id: int
    data_list_id: int
    subject: str
    message: str
    from_name: Optional[str] = None
    start_line: int = 1

# API endpoints
@app.get("/api/stats")
async def get_stats():
    """Get comprehensive statistics"""
    campaigns = storage.get_all_campaigns()
    
    total_campaigns = len(campaigns)
    active_campaigns = sum(1 for c in campaigns.values() if c.get('status') == 'running')
    completed_campaigns = sum(1 for c in campaigns.values() if c.get('status') == 'completed')
    failed_campaigns = sum(1 for c in campaigns.values() if c.get('status') == 'failed')
    total_sent = sum(c.get('total_sent', 0) for c in campaigns.values())
    total_failed = sum(c.get('total_failed', 0) for c in campaigns.values())
    
    stats = {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "completed_campaigns": completed_campaigns,
        "failed_campaigns": failed_campaigns,
        "total_sent": total_sent,
        "total_failed": total_failed,
        "delivery_rate": round((total_sent / (total_sent + total_failed) * 100), 1) if (total_sent + total_failed) > 0 else 0,
        "timestamp": datetime.now().isoformat(),
        "running_campaigns": list(processor.running_campaigns.keys()),
        "system_status": "healthy"
    }
    
    return stats

@app.get("/api/campaigns")
async def get_campaigns():
    """Get all campaigns with real-time status"""
    return storage.get_all_campaigns()

@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get specific campaign"""
    campaign = storage.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

@app.get("/api/campaigns/{campaign_id}/logs")
async def get_campaign_logs(campaign_id: str, limit: int = 1000):
    """Get campaign logs"""
    logs = storage.get_campaign_logs(campaign_id, limit)
    return {"logs": logs}

@app.post("/api/campaigns")
async def create_campaign(campaign: CampaignCreate):
    """Create a new campaign"""
    campaign_id = str(uuid.uuid4())
    
    new_campaign = {
        "id": campaign_id,
        "name": campaign.name,
        "account_id": campaign.account_id,
        "data_list_id": campaign.data_list_id,
        "subject": campaign.subject,
        "message": campaign.message,
        "from_name": campaign.from_name,
        "start_line": campaign.start_line,
        "status": "ready",
        "created_at": datetime.now().isoformat(),
        "total_sent": 0,
        "total_failed": 0,
        "total_attempted": 0,
        "last_email_index": 0,
        "error_count": 0
    }
    
    if storage.save_campaign(new_campaign):
        logger.info(f"Created campaign {campaign_id}: {campaign.name}")
        return {"success": True, "campaign_id": campaign_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to create campaign")

@app.post("/api/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str):
    """Start a campaign"""
    success = await processor.start_campaign(campaign_id)
    if success:
        return {"success": True, "message": "Campaign started"}
    else:
        raise HTTPException(status_code=400, detail="Failed to start campaign")

@app.post("/api/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: str):
    """Stop a campaign"""
    success = await processor.stop_campaign(campaign_id)
    if success:
        return {"success": True, "message": "Campaign stopped"}
    else:
        raise HTTPException(status_code=400, detail="Failed to stop campaign")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "subscribe_campaign":
                    campaign_id = message.get("campaign_id")
                    if campaign_id:
                        manager.campaign_subscribers[campaign_id].append(websocket)
                        logger.info(f"WebSocket subscribed to campaign {campaign_id}")
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received via WebSocket")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@app.get("/")
async def get_dashboard():
    """Production dashboard"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Production-Reliable Email Campaign Manager</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
            .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .stat-value { font-size: 2em; font-weight: bold; color: #333; }
            .stat-label { color: #666; margin-top: 5px; }
            .controls { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; transition: background 0.3s; }
            .btn:hover { background: #0056b3; }
            .btn:disabled { background: #ccc; cursor: not-allowed; }
            .btn.success { background: #28a745; }
            .btn.danger { background: #dc3545; }
            .btn.warning { background: #ffc107; color: #333; }
            .campaigns { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .campaign { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px; transition: all 0.3s; }
            .campaign:hover { box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
            .campaign.running { border-left: 5px solid #28a745; background: #f8fff9; }
            .campaign.completed { border-left: 5px solid #17a2b8; background: #f8f9ff; }
            .campaign.failed { border-left: 5px solid #dc3545; background: #fff8f8; }
            .campaign.ready { border-left: 5px solid #ffc107; background: #fffef8; }
            .campaign.stopped { border-left: 5px solid #6c757d; background: #f8f9fa; }
            .status-indicator { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }
            .status-running { background: #28a745; animation: pulse 2s infinite; }
            .status-completed { background: #17a2b8; }
            .status-failed { background: #dc3545; }
            .status-ready { background: #ffc107; }
            .status-stopped { background: #6c757d; }
            @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
            .logs { background: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 10px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 12px; }
            .connection-status { position: fixed; top: 20px; right: 20px; padding: 10px; border-radius: 5px; color: white; font-weight: bold; z-index: 1000; }
            .connected { background: #28a745; }
            .disconnected { background: #dc3545; }
            .progress-bar { width: 100%; height: 10px; background: #e9ecef; border-radius: 5px; overflow: hidden; margin: 10px 0; }
            .progress-fill { height: 100%; background: linear-gradient(90deg, #007bff, #28a745); transition: width 0.3s; }
        </style>
    </head>
    <body>
        <div id="connectionStatus" class="connection-status disconnected">Disconnected</div>
        
        <div class="container">
            <div class="header">
                <h1>🚀 Production-Reliable Email Campaign Manager</h1>
                <p>Rock-solid reliable email campaigns with real-time monitoring</p>
            </div>
            
            <div class="stats-grid" id="statsGrid">
                <div class="stat-card">
                    <div class="stat-value" id="totalCampaigns">0</div>
                    <div class="stat-label">Total Campaigns</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="activeCampaigns">0</div>
                    <div class="stat-label">Active Campaigns</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalSent">0</div>
                    <div class="stat-label">Total Sent</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalFailed">0</div>
                    <div class="stat-label">Total Failed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="deliveryRate">0%</div>
                    <div class="stat-label">Delivery Rate</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="systemStatus">Unknown</div>
                    <div class="stat-label">System Status</div>
                </div>
            </div>
            
            <div class="controls">
                <h3>🎯 Quick Actions</h3>
                <button class="btn" onclick="createTestCampaign()">Create Test Campaign</button>
                <button class="btn success" onclick="refreshData()">Refresh Data</button>
                <button class="btn warning" onclick="stopAllCampaigns()">Stop All Campaigns</button>
                <button class="btn" onclick="toggleAutoRefresh()">Toggle Auto-Refresh</button>
            </div>
            
            <div class="campaigns">
                <h3>📋 Campaigns</h3>
                <div id="campaignsContainer">Loading campaigns...</div>
            </div>
        </div>
        
        <script>
            let ws = null;
            let autoRefresh = true;
            let reconnectAttempts = 0;
            const maxReconnectAttempts = 10;
            
            // Initialize WebSocket connection with robust reconnection
            function initWebSocket() {
                try {
                    ws = new WebSocket('ws://localhost:5000/ws');
                    
                    ws.onopen = function() {
                        console.log('WebSocket connected');
                        document.getElementById('connectionStatus').className = 'connection-status connected';
                        document.getElementById('connectionStatus').textContent = 'Connected';
                        reconnectAttempts = 0;
                    };
                    
                    ws.onmessage = function(event) {
                        try {
                            const data = JSON.parse(event.data);
                            handleWebSocketMessage(data);
                        } catch (e) {
                            console.error('Error parsing WebSocket message:', e);
                        }
                    };
                    
                    ws.onclose = function() {
                        console.log('WebSocket disconnected');
                        document.getElementById('connectionStatus').className = 'connection-status disconnected';
                        document.getElementById('connectionStatus').textContent = 'Disconnected';
                        
                        // Attempt to reconnect
                        if (reconnectAttempts < maxReconnectAttempts) {
                            reconnectAttempts++;
                            setTimeout(initWebSocket, Math.min(1000 * Math.pow(2, reconnectAttempts), 30000));
                        }
                    };
                    
                    ws.onerror = function(error) {
                        console.error('WebSocket error:', error);
                    };
                    
                } catch (e) {
                    console.error('Error initializing WebSocket:', e);
                    setTimeout(initWebSocket, 5000);
                }
            }
            
            function handleWebSocketMessage(data) {
                switch (data.type) {
                    case 'stats_update':
                        updateStatsDisplay(data.data);
                        break;
                    case 'campaign_update':
                        updateCampaignDisplay(data.campaign_id, data.data);
                        break;
                    case 'heartbeat':
                        // Handle heartbeat to keep connection alive
                        break;
                }
            }
            
            function updateStatsDisplay(stats) {
                document.getElementById('totalCampaigns').textContent = stats.total_campaigns || 0;
                document.getElementById('activeCampaigns').textContent = stats.active_campaigns || 0;
                document.getElementById('totalSent').textContent = stats.total_sent || 0;
                document.getElementById('totalFailed').textContent = stats.total_failed || 0;
                document.getElementById('deliveryRate').textContent = (stats.delivery_rate || 0) + '%';
                document.getElementById('systemStatus').textContent = stats.system_status || 'Unknown';
            }
            
            function updateCampaignDisplay(campaignId, data) {
                const campaignElement = document.getElementById(`campaign-${campaignId}`);
                if (campaignElement) {
                    // Update campaign status and data
                    loadCampaigns(); // Reload all campaigns for simplicity
                }
            }
            
            async function refreshData() {
                await Promise.all([loadStats(), loadCampaigns()]);
            }
            
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const stats = await response.json();
                    updateStatsDisplay(stats);
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }
            
            async function loadCampaigns() {
                try {
                    const response = await fetch('/api/campaigns');
                    const campaigns = await response.json();
                    displayCampaigns(campaigns);
                } catch (error) {
                    console.error('Error loading campaigns:', error);
                    document.getElementById('campaignsContainer').innerHTML = '<p style="color: red;">Error loading campaigns</p>';
                }
            }
            
            function displayCampaigns(campaigns) {
                const container = document.getElementById('campaignsContainer');
                
                if (Object.keys(campaigns).length === 0) {
                    container.innerHTML = '<p>No campaigns found. Create one to get started!</p>';
                    return;
                }
                
                let html = '';
                for (const [id, campaign] of Object.entries(campaigns)) {
                    const status = campaign.status || 'ready';
                    const progress = campaign.total_attempted > 0 ? 
                        Math.round((campaign.total_sent / campaign.total_attempted) * 100) : 0;
                    
                    html += `
                        <div class="campaign ${status}" id="campaign-${id}">
                            <h4>${campaign.name}</h4>
                            <p>
                                <span class="status-indicator status-${status}"></span>
                                <strong>Status:</strong> ${status.toUpperCase()}
                                ${campaign.last_error ? `<span style="color: red;"> - ${campaign.last_error}</span>` : ''}
                            </p>
                            <p><strong>Subject:</strong> ${campaign.subject}</p>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${progress}%"></div>
                            </div>
                            <p>
                                <strong>Progress:</strong> ${campaign.total_sent || 0} sent, ${campaign.total_failed || 0} failed 
                                (${campaign.total_attempted || 0} total)
                            </p>
                            <p><strong>Created:</strong> ${new Date(campaign.created_at).toLocaleString()}</p>
                            ${campaign.started_at ? `<p><strong>Started:</strong> ${new Date(campaign.started_at).toLocaleString()}</p>` : ''}
                            ${campaign.completed_at ? `<p><strong>Completed:</strong> ${new Date(campaign.completed_at).toLocaleString()}</p>` : ''}
                            
                            <div style="margin-top: 10px;">
                                <button class="btn ${status === 'running' ? '' : 'success'}" 
                                        onclick="startCampaign('${id}')" 
                                        ${status === 'running' ? 'disabled' : ''}>
                                    ${status === 'running' ? 'Running...' : 'Start Campaign'}
                                </button>
                                <button class="btn danger" 
                                        onclick="stopCampaign('${id}')" 
                                        ${status !== 'running' ? 'disabled' : ''}>
                                    Stop Campaign
                                </button>
                                <button class="btn" onclick="viewLogs('${id}')">View Logs</button>
                            </div>
                        </div>
                    `;
                }
                
                container.innerHTML = html;
            }
            
            async function createTestCampaign() {
                try {
                    const response = await fetch('/api/campaigns', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: `Production Test Campaign ${new Date().toLocaleString()}`,
                            account_id: 1,
                            data_list_id: 1,
                            subject: 'Production Test Email',
                            message: 'This is a production test email with robust error handling.',
                            from_name: 'Production Test',
                            start_line: 1
                        })
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        alert('Campaign created successfully!');
                        await loadCampaigns();
                    } else {
                        alert('Error creating campaign');
                    }
                } catch (error) {
                    console.error('Error creating campaign:', error);
                    alert('Error creating campaign');
                }
            }
            
            async function startCampaign(campaignId) {
                try {
                    const response = await fetch(`/api/campaigns/${campaignId}/start`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    if (result.success) {
                        console.log('Campaign started successfully');
                        await loadCampaigns();
                    } else {
                        alert('Error starting campaign');
                    }
                } catch (error) {
                    console.error('Error starting campaign:', error);
                    alert('Error starting campaign');
                }
            }
            
            async function stopCampaign(campaignId) {
                try {
                    const response = await fetch(`/api/campaigns/${campaignId}/stop`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    if (result.success) {
                        console.log('Campaign stopped successfully');
                        await loadCampaigns();
                    } else {
                        alert('Error stopping campaign');
                    }
                } catch (error) {
                    console.error('Error stopping campaign:', error);
                    alert('Error stopping campaign');
                }
            }
            
            async function stopAllCampaigns() {
                if (!confirm('Are you sure you want to stop all running campaigns?')) {
                    return;
                }
                
                try {
                    const response = await fetch('/api/campaigns');
                    const campaigns = await response.json();
                    
                    const runningCampaigns = Object.values(campaigns).filter(c => c.status === 'running');
                    
                    for (const campaign of runningCampaigns) {
                        await stopCampaign(campaign.id);
                    }
                    
                    alert(`Stopped ${runningCampaigns.length} campaigns`);
                } catch (error) {
                    console.error('Error stopping campaigns:', error);
                    alert('Error stopping campaigns');
                }
            }
            
            async function viewLogs(campaignId) {
                try {
                    const response = await fetch(`/api/campaigns/${campaignId}/logs`);
                    const data = await response.json();
                    
                    let logsHtml = '<h4>Campaign Logs</h4><div class="logs">';
                    if (data.logs && data.logs.length > 0) {
                        data.logs.forEach(log => {
                            logsHtml += `<div>${log.timestamp} - ${log.email} - ${log.status} - ${log.message}</div>`;
                        });
                    } else {
                        logsHtml += '<div>No logs available</div>';
                    }
                    logsHtml += '</div>';
                    
                    // Create modal or update existing display
                    alert('Logs loaded - check console for details');
                    console.log('Campaign logs:', data.logs);
                    
                } catch (error) {
                    console.error('Error loading logs:', error);
                    alert('Error loading logs');
                }
            }
            
            function toggleAutoRefresh() {
                autoRefresh = !autoRefresh;
                alert(`Auto-refresh ${autoRefresh ? 'enabled' : 'disabled'}`);
            }
            
            // Initialize the application
            window.onload = function() {
                initWebSocket();
                refreshData();
                
                // Auto-refresh every 15 seconds
                setInterval(() => {
                    if (autoRefresh) {
                        loadStats();
                    }
                }, 15000);
                
                // Reload campaigns every 30 seconds
                setInterval(() => {
                    if (autoRefresh) {
                        loadCampaigns();
                    }
                }, 30000);
            };
            
            // Handle page visibility changes
            document.addEventListener('visibilitychange', function() {
                if (document.visibilityState === 'visible') {
                    // Page became visible, refresh data
                    refreshData();
                    
                    // Reconnect WebSocket if needed
                    if (!ws || ws.readyState === WebSocket.CLOSED) {
                        initWebSocket();
                    }
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    try:
        # Check database
        campaigns = storage.get_all_campaigns()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check running campaigns
    running_count = len(processor.running_campaigns)
    
    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "database": db_status,
        "running_campaigns": running_count,
        "websocket_connections": len(manager.active_connections),
        "timestamp": datetime.now().isoformat(),
        "uptime": "running"
    }

# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    logger.info("Received shutdown signal, cleaning up...")
    
    # Stop all running campaigns
    for campaign_id in list(processor.running_campaigns.keys()):
        asyncio.create_task(processor.stop_campaign(campaign_id))
    
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    logger.info("Starting Production-Reliable Email Campaign Manager...")
    uvicorn.run(
        "app_production_reliable:app",
        host="0.0.0.0",
        port=5000,
        reload=False,
        access_log=False,
        workers=1
    )