#!/usr/bin/env python3
"""
High-Performance Email Campaign Manager
- FastAPI for async operations
- In-memory caching for speed
- Non-blocking operations
- Real-time updates
- Designed to handle 100+ concurrent campaigns
"""

import asyncio
import json
import os
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid
from collections import defaultdict
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Configure logging for minimal overhead
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# FastAPI app with high performance settings
app = FastAPI(
    title="High-Performance Email Campaign Manager",
    description="Fast email campaign manager for 100+ concurrent campaigns",
    version="1.5.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory high-speed cache
class HighSpeedCache:
    def __init__(self):
        self._cache = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str):
        async with self._lock:
            return self._cache.get(key)
    
    async def set(self, key: str, value: Any):
        async with self._lock:
            self._cache[key] = value
    
    async def delete(self, key: str):
        async with self._lock:
            self._cache.pop(key, None)
    
    async def keys(self, pattern: str = None):
        async with self._lock:
            if pattern:
                return [k for k in self._cache.keys() if pattern in k]
            return list(self._cache.keys())

# Global cache instance
cache = HighSpeedCache()

# WebSocket connection manager for real-time updates
class FastConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.campaign_subscribers: Dict[str, List[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for connections in self.campaign_subscribers.values():
            if websocket in connections:
                connections.remove(websocket)

    async def broadcast_campaign_update(self, campaign_id: str, data: dict):
        message = json.dumps({
            "type": "campaign_update",
            "campaign_id": campaign_id,
            "data": data
        })
        
        # Send to all subscribers of this campaign
        connections = self.campaign_subscribers.get(campaign_id, [])
        for connection in connections[:]:  # Copy list to avoid modification during iteration
            try:
                await connection.send_text(message)
            except:
                connections.remove(connection)

    async def broadcast_stats_update(self, stats: dict):
        message = json.dumps({
            "type": "stats_update",
            "data": stats
        })
        
        for connection in self.active_connections[:]:  # Copy list
            try:
                await connection.send_text(message)
            except:
                self.active_connections.remove(connection)

manager = FastConnectionManager()

# Pydantic models
class CampaignCreate(BaseModel):
    name: str
    account_id: int
    data_list_id: int
    subject: str
    message: str
    from_name: Optional[str] = None
    start_line: int = 1

class CampaignStatus(BaseModel):
    campaign_id: str
    status: str
    total_sent: int = 0
    total_failed: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

# High-speed data operations
async def load_json_fast(filename: str) -> dict:
    """Fast JSON loading with caching"""
    cache_key = f"file_{filename}"
    cached_data = await cache.get(cache_key)
    if cached_data:
        return cached_data
    
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        
        await cache.set(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return {}

async def save_json_fast(filename: str, data: dict):
    """Fast JSON saving with cache update"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        cache_key = f"file_{filename}"
        await cache.set(cache_key, data)
        return True
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")
        return False

# Campaign processing functions
async def process_campaign_fast(campaign_id: str, campaign_data: dict):
    """Fast campaign processing with real-time updates"""
    try:
        # Update status to running
        await update_campaign_status(campaign_id, "running", {
            "started_at": datetime.now().isoformat(),
            "total_sent": 0,
            "total_failed": 0
        })
        
        # Get email list (simulated for now - replace with your data list logic)
        emails = await get_email_list_fast(campaign_data["data_list_id"], campaign_data.get("start_line", 1))
        
        if not emails:
            await update_campaign_status(campaign_id, "failed", {"error": "No emails found"})
            return
        
        # Process emails in batches for maximum speed
        batch_size = 100
        total_sent = 0
        total_failed = 0
        
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            
            # Check if campaign should be stopped
            campaign_status = await get_campaign_status(campaign_id)
            if campaign_status and campaign_status.get("status") == "stopped":
                break
            
            # Process batch concurrently
            tasks = []
            for email in batch:
                task = asyncio.create_task(send_email_fast(campaign_data, email))
                tasks.append(task)
            
            # Wait for all emails in batch to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count results
            batch_sent = sum(1 for r in results if r is True)
            batch_failed = len(results) - batch_sent
            
            total_sent += batch_sent
            total_failed += batch_failed
            
            # Update status in real-time
            await update_campaign_status(campaign_id, "running", {
                "total_sent": total_sent,
                "total_failed": total_failed
            })
            
            # Small delay to prevent overwhelming
            await asyncio.sleep(0.01)
        
        # Mark as completed
        await update_campaign_status(campaign_id, "completed", {
            "completed_at": datetime.now().isoformat(),
            "total_sent": total_sent,
            "total_failed": total_failed
        })
        
    except Exception as e:
        logger.error(f"Campaign {campaign_id} failed: {e}")
        await update_campaign_status(campaign_id, "failed", {"error": str(e)})

async def send_email_fast(campaign_data: dict, email: str) -> bool:
    """Fast email sending simulation"""
    try:
        # Simulate email sending (replace with your Zoho API logic)
        await asyncio.sleep(0.001)  # 1ms simulated send time
        return True
    except Exception as e:
        logger.error(f"Email send failed for {email}: {e}")
        return False

async def get_email_list_fast(data_list_id: int, start_line: int = 1) -> List[str]:
    """Fast email list retrieval"""
    # This is a simulation - replace with your actual data list logic
    data_lists = await load_json_fast("data_lists.json")
    data_list = data_lists.get(str(data_list_id))
    
    if not data_list:
        return []
    
    # For demo, return a list of test emails
    base_emails = [f"test{i}@example.com" for i in range(start_line, start_line + 1000)]
    return base_emails

async def update_campaign_status(campaign_id: str, status: str, extra_data: dict = None):
    """Update campaign status with real-time broadcast"""
    data = {
        "status": status,
        "updated_at": datetime.now().isoformat()
    }
    if extra_data:
        data.update(extra_data)
    
    # Update cache
    await cache.set(f"campaign_status_{campaign_id}", data)
    
    # Broadcast update
    await manager.broadcast_campaign_update(campaign_id, data)

async def get_campaign_status(campaign_id: str) -> dict:
    """Get campaign status from cache"""
    return await cache.get(f"campaign_status_{campaign_id}") or {}

# Initialize data files
async def init_data_files():
    """Initialize data files if they don't exist"""
    files = {
        "campaigns.json": {},
        "accounts.json": {
            "1": {
                "id": 1,
                "name": "Default Account",
                "org_id": "default123",
                "created_at": datetime.now().isoformat()
            }
        },
        "data_lists.json": {
            "1": {
                "id": 1,
                "name": "Default List",
                "filename": "default_list.txt",
                "created_at": datetime.now().isoformat()
            }
        },
        "users.json": {
            "1": {
                "id": 1,
                "username": "admin",
                "password": "admin",
                "role": "admin",
                "created_at": datetime.now().isoformat()
            }
        }
    }
    
    for filename, default_data in files.items():
        if not os.path.exists(filename):
            await save_json_fast(filename, default_data)

# API endpoints
@app.get("/api/stats")
async def get_stats():
    """Get real-time statistics"""
    campaigns = await load_json_fast("campaigns.json")
    accounts = await load_json_fast("accounts.json")
    
    # Get active campaigns from cache
    active_campaigns = 0
    total_sent = 0
    total_failed = 0
    
    campaign_keys = await cache.keys("campaign_status_")
    for key in campaign_keys:
        status_data = await cache.get(key)
        if status_data:
            if status_data.get("status") == "running":
                active_campaigns += 1
            total_sent += status_data.get("total_sent", 0)
            total_failed += status_data.get("total_failed", 0)
    
    stats = {
        "total_campaigns": len(campaigns),
        "active_campaigns": active_campaigns,
        "total_accounts": len(accounts),
        "total_sent": total_sent,
        "total_failed": total_failed,
        "delivery_rate": round((total_sent / (total_sent + total_failed) * 100), 1) if (total_sent + total_failed) > 0 else 0,
        "timestamp": datetime.now().isoformat()
    }
    
    # Broadcast stats update
    await manager.broadcast_stats_update(stats)
    
    return stats

@app.get("/api/campaigns")
async def get_campaigns():
    """Get all campaigns with real-time status"""
    campaigns = await load_json_fast("campaigns.json")
    
    # Add real-time status from cache
    for campaign_id, campaign in campaigns.items():
        status_data = await get_campaign_status(campaign_id)
        if status_data:
            campaign.update(status_data)
    
    return campaigns

@app.post("/api/campaigns")
async def create_campaign(campaign: CampaignCreate):
    """Create a new campaign"""
    campaigns = await load_json_fast("campaigns.json")
    campaign_id = str(len(campaigns) + 1)
    
    new_campaign = {
        "id": int(campaign_id),
        "name": campaign.name,
        "account_id": campaign.account_id,
        "data_list_id": campaign.data_list_id,
        "subject": campaign.subject,
        "message": campaign.message,
        "from_name": campaign.from_name,
        "start_line": campaign.start_line,
        "status": "ready",
        "created_at": datetime.now().isoformat()
    }
    
    campaigns[campaign_id] = new_campaign
    await save_json_fast("campaigns.json", campaigns)
    
    return {"success": True, "campaign_id": campaign_id}

@app.post("/api/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str):
    """Start a campaign asynchronously"""
    campaigns = await load_json_fast("campaigns.json")
    campaign = campaigns.get(campaign_id)
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Check if already running
    current_status = await get_campaign_status(campaign_id)
    if current_status and current_status.get("status") == "running":
        raise HTTPException(status_code=400, detail="Campaign is already running")
    
    # Start processing in background
    asyncio.create_task(process_campaign_fast(campaign_id, campaign))
    
    return {"success": True, "message": "Campaign started"}

@app.post("/api/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: str):
    """Stop a running campaign"""
    await update_campaign_status(campaign_id, "stopped")
    return {"success": True, "message": "Campaign stopped"}

@app.get("/api/campaigns/{campaign_id}/status")
async def get_campaign_status_endpoint(campaign_id: str):
    """Get real-time campaign status"""
    status_data = await get_campaign_status(campaign_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="Campaign status not found")
    
    return status_data

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "subscribe_campaign":
                campaign_id = message.get("campaign_id")
                if campaign_id:
                    manager.campaign_subscribers[campaign_id].append(websocket)
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Basic HTML page for testing
@app.get("/")
async def get_dashboard():
    """Simple dashboard page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>High-Performance Email Campaign Manager</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .stats { background: #f0f0f0; padding: 20px; border-radius: 5px; margin: 20px 0; }
            .button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }
            .button:hover { background: #0056b3; }
            .campaign { background: white; border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .status-running { border-left: 5px solid #28a745; }
            .status-completed { border-left: 5px solid #17a2b8; }
            .status-failed { border-left: 5px solid #dc3545; }
            .status-ready { border-left: 5px solid #ffc107; }
        </style>
    </head>
    <body>
        <h1>🚀 High-Performance Email Campaign Manager</h1>
        
        <div class="stats" id="stats">
            <h3>📊 Real-Time Statistics</h3>
            <div id="stats-content">Loading...</div>
        </div>
        
        <div>
            <h3>🎯 Quick Actions</h3>
            <button class="button" onclick="createTestCampaign()">Create Test Campaign</button>
            <button class="button" onclick="refreshStats()">Refresh Stats</button>
            <button class="button" onclick="loadCampaigns()">Load Campaigns</button>
        </div>
        
        <div>
            <h3>📋 Campaigns</h3>
            <div id="campaigns">Loading campaigns...</div>
        </div>
        
        <script>
            let ws = null;
            
            // Initialize WebSocket connection
            function initWebSocket() {
                ws = new WebSocket('ws://localhost:5000/ws');
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    if (data.type === 'stats_update') {
                        updateStatsDisplay(data.data);
                    } else if (data.type === 'campaign_update') {
                        updateCampaignDisplay(data.campaign_id, data.data);
                    }
                };
                
                ws.onclose = function() {
                    setTimeout(initWebSocket, 3000); // Reconnect after 3 seconds
                };
            }
            
            // Load and display statistics
            async function refreshStats() {
                try {
                    const response = await fetch('/api/stats');
                    const stats = await response.json();
                    updateStatsDisplay(stats);
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }
            
            function updateStatsDisplay(stats) {
                document.getElementById('stats-content').innerHTML = `
                    <strong>Total Campaigns:</strong> ${stats.total_campaigns} | 
                    <strong>Active:</strong> ${stats.active_campaigns} | 
                    <strong>Accounts:</strong> ${stats.total_accounts} | 
                    <strong>Sent:</strong> ${stats.total_sent} | 
                    <strong>Failed:</strong> ${stats.total_failed} | 
                    <strong>Delivery Rate:</strong> ${stats.delivery_rate}%
                `;
            }
            
            // Load and display campaigns
            async function loadCampaigns() {
                try {
                    const response = await fetch('/api/campaigns');
                    const campaigns = await response.json();
                    displayCampaigns(campaigns);
                } catch (error) {
                    console.error('Error loading campaigns:', error);
                }
            }
            
            function displayCampaigns(campaigns) {
                const campaignsDiv = document.getElementById('campaigns');
                if (Object.keys(campaigns).length === 0) {
                    campaignsDiv.innerHTML = '<p>No campaigns found. Create one to get started!</p>';
                    return;
                }
                
                let html = '';
                for (const [id, campaign] of Object.entries(campaigns)) {
                    const status = campaign.status || 'ready';
                    html += `
                        <div class="campaign status-${status}" id="campaign-${id}">
                            <h4>${campaign.name}</h4>
                            <p><strong>Status:</strong> ${status.toUpperCase()}</p>
                            <p><strong>Subject:</strong> ${campaign.subject}</p>
                            <p><strong>Sent:</strong> ${campaign.total_sent || 0} | <strong>Failed:</strong> ${campaign.total_failed || 0}</p>
                            <button class="button" onclick="startCampaign('${id}')" ${status === 'running' ? 'disabled' : ''}>
                                ${status === 'running' ? 'Running...' : 'Start Campaign'}
                            </button>
                            <button class="button" onclick="stopCampaign('${id}')" ${status !== 'running' ? 'disabled' : ''}>
                                Stop Campaign
                            </button>
                        </div>
                    `;
                }
                campaignsDiv.innerHTML = html;
            }
            
            function updateCampaignDisplay(campaignId, data) {
                const campaignDiv = document.getElementById(`campaign-${campaignId}`);
                if (campaignDiv) {
                    // Update the campaign display with new data
                    loadCampaigns(); // Reload all campaigns for simplicity
                }
            }
            
            // Create a test campaign
            async function createTestCampaign() {
                try {
                    const response = await fetch('/api/campaigns', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            name: `Test Campaign ${Date.now()}`,
                            account_id: 1,
                            data_list_id: 1,
                            subject: 'Test Email Subject',
                            message: 'This is a test email message.',
                            from_name: 'Test Sender',
                            start_line: 1
                        })
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        alert('Campaign created successfully!');
                        loadCampaigns();
                    }
                } catch (error) {
                    console.error('Error creating campaign:', error);
                    alert('Error creating campaign');
                }
            }
            
            // Start a campaign
            async function startCampaign(campaignId) {
                try {
                    const response = await fetch(`/api/campaigns/${campaignId}/start`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    if (result.success) {
                        alert('Campaign started!');
                        loadCampaigns();
                    }
                } catch (error) {
                    console.error('Error starting campaign:', error);
                    alert('Error starting campaign');
                }
            }
            
            // Stop a campaign
            async function stopCampaign(campaignId) {
                try {
                    const response = await fetch(`/api/campaigns/${campaignId}/stop`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    if (result.success) {
                        alert('Campaign stopped!');
                        loadCampaigns();
                    }
                } catch (error) {
                    console.error('Error stopping campaign:', error);
                    alert('Error stopping campaign');
                }
            }
            
            // Initialize the page
            window.onload = function() {
                initWebSocket();
                refreshStats();
                loadCampaigns();
                
                // Refresh stats every 5 seconds
                setInterval(refreshStats, 5000);
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Startup event
@app.on_event("startup")
async def startup_event():
    await init_data_files()
    logger.warning("High-Performance Email Campaign Manager started!")

if __name__ == "__main__":
    uvicorn.run(
        "app_fast:app",
        host="0.0.0.0",
        port=5000,
        reload=False,
        access_log=False,
        workers=1,
        loop="asyncio"
    )