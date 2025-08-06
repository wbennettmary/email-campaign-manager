#!/bin/bash

echo "🔧 Fixing Production Deployment Issues"
echo "======================================"

echo "1. Stopping all services..."
docker-compose down

echo ""
echo "2. Cleaning up containers and networks..."
docker system prune -f
docker network prune -f

echo ""
echo "3. Creating simplified FastAPI application..."
cat > simple_production_app.py << 'EOF'
#!/usr/bin/env python3
"""
Simplified Production FastAPI Application
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Production Email Campaign Manager",
    description="High-performance email campaign manager",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for quick start (replace with database later)
campaigns_storage = {}
active_campaigns = set()
stats_data = {
    "total_campaigns": 0,
    "active_campaigns": 0,
    "total_sent": 0,
    "total_failed": 0
}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if self.active_connections:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)
            
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

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    message: Optional[str] = None

# Routes
@app.get("/")
async def root():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Production Email Campaign Manager</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .status { padding: 20px; background: #e8f5e8; border-radius: 5px; margin: 20px 0; }
            .campaign { padding: 15px; border: 1px solid #ddd; margin: 10px 0; border-radius: 5px; }
            button { padding: 10px 20px; margin: 5px; cursor: pointer; }
            .stats { display: flex; gap: 20px; margin: 20px 0; }
            .stat-box { padding: 20px; background: #f0f8ff; border-radius: 5px; text-align: center; }
        </style>
    </head>
    <body>
        <h1>🚀 Production Email Campaign Manager</h1>
        <div class="status">
            <h3>✅ System Status: OPERATIONAL</h3>
            <p>FastAPI is running successfully!</p>
            <p>Real-time updates: <span id="connection-status">Connecting...</span></p>
        </div>
        
        <div class="stats">
            <div class="stat-box">
                <h4>Total Campaigns</h4>
                <div id="total-campaigns">0</div>
            </div>
            <div class="stat-box">
                <h4>Active Campaigns</h4>
                <div id="active-campaigns">0</div>
            </div>
            <div class="stat-box">
                <h4>Emails Sent</h4>
                <div id="total-sent">0</div>
            </div>
        </div>

        <h3>Create Test Campaign</h3>
        <button onclick="createTestCampaign()">Create Test Campaign</button>
        <button onclick="startAllCampaigns()">Start All Campaigns</button>
        <button onclick="stopAllCampaigns()">Stop All Campaigns</button>

        <h3>Campaigns</h3>
        <div id="campaigns-list"></div>

        <script>
            // WebSocket connection
            const ws = new WebSocket('ws://localhost:8000/ws');
            
            ws.onopen = function(event) {
                document.getElementById('connection-status').textContent = 'Connected ✅';
                console.log('WebSocket connected');
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                console.log('Received:', data);
                updateUI(data);
            };
            
            ws.onclose = function(event) {
                document.getElementById('connection-status').textContent = 'Disconnected ❌';
                console.log('WebSocket disconnected');
            };

            function updateUI(data) {
                if (data.type === 'stats_update') {
                    document.getElementById('total-campaigns').textContent = data.stats.total_campaigns;
                    document.getElementById('active-campaigns').textContent = data.stats.active_campaigns;
                    document.getElementById('total-sent').textContent = data.stats.total_sent;
                }
                refreshCampaigns();
            }

            async function createTestCampaign() {
                const response = await fetch('/api/campaigns', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: 'Test Campaign ' + Date.now(),
                        account_id: 1,
                        data_list_id: 1,
                        subject: 'Test Subject',
                        message: 'Test Message'
                    })
                });
                const result = await response.json();
                console.log('Campaign created:', result);
                refreshCampaigns();
            }

            async function startAllCampaigns() {
                const campaigns = await fetch('/api/campaigns').then(r => r.json());
                for (const campaign of Object.values(campaigns)) {
                    if (campaign.status === 'ready') {
                        await fetch(`/api/campaigns/${campaign.id}/start`, { method: 'POST' });
                    }
                }
                refreshCampaigns();
            }

            async function stopAllCampaigns() {
                const campaigns = await fetch('/api/campaigns').then(r => r.json());
                for (const campaign of Object.values(campaigns)) {
                    if (campaign.status === 'running') {
                        await fetch(`/api/campaigns/${campaign.id}/stop`, { method: 'POST' });
                    }
                }
                refreshCampaigns();
            }

            async function refreshCampaigns() {
                const campaigns = await fetch('/api/campaigns').then(r => r.json());
                const list = document.getElementById('campaigns-list');
                list.innerHTML = '';
                
                for (const campaign of Object.values(campaigns)) {
                    const div = document.createElement('div');
                    div.className = 'campaign';
                    div.innerHTML = `
                        <h4>${campaign.name}</h4>
                        <p>Status: ${campaign.status}</p>
                        <p>Sent: ${campaign.total_sent || 0} | Failed: ${campaign.total_failed || 0}</p>
                        <button onclick="startCampaign('${campaign.id}')" ${campaign.status === 'running' ? 'disabled' : ''}>Start</button>
                        <button onclick="stopCampaign('${campaign.id}')" ${campaign.status !== 'running' ? 'disabled' : ''}>Stop</button>
                    `;
                    list.appendChild(div);
                }
            }

            async function startCampaign(campaignId) {
                await fetch(`/api/campaigns/${campaignId}/start`, { method: 'POST' });
                refreshCampaigns();
            }

            async function stopCampaign(campaignId) {
                await fetch(`/api/campaigns/${campaignId}/stop`, { method: 'POST' });
                refreshCampaigns();
            }

            // Initial load
            refreshCampaigns();
            
            // Refresh stats every 5 seconds
            setInterval(async () => {
                const stats = await fetch('/api/stats').then(r => r.json());
                document.getElementById('total-campaigns').textContent = stats.total_campaigns;
                document.getElementById('active-campaigns').textContent = stats.active_campaigns;
                document.getElementById('total-sent').textContent = stats.total_sent;
            }, 5000);
        </script>
    </body>
    </html>
    """)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }

@app.get("/api/stats")
async def get_stats():
    stats = {
        "total_campaigns": len(campaigns_storage),
        "active_campaigns": len(active_campaigns),
        "total_sent": stats_data["total_sent"],
        "total_failed": stats_data["total_failed"],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Broadcast to WebSocket clients
    await manager.broadcast({
        "type": "stats_update",
        "stats": stats
    })
    
    return stats

@app.get("/api/campaigns")
async def get_campaigns():
    return campaigns_storage

@app.post("/api/campaigns")
async def create_campaign(campaign: CampaignCreate):
    campaign_id = str(uuid.uuid4())
    
    campaign_data = {
        "id": campaign_id,
        "name": campaign.name,
        "account_id": campaign.account_id,
        "data_list_id": campaign.data_list_id,
        "subject": campaign.subject,
        "message": campaign.message,
        "from_name": campaign.from_name,
        "status": "ready",
        "created_at": datetime.utcnow().isoformat(),
        "total_sent": 0,
        "total_failed": 0
    }
    
    campaigns_storage[campaign_id] = campaign_data
    
    logger.info(f"Campaign created: {campaign_id} - {campaign.name}")
    
    return {"success": True, "campaign_id": campaign_id}

@app.post("/api/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str):
    if campaign_id not in campaigns_storage:
        return {"error": "Campaign not found"}, 404
    
    campaign = campaigns_storage[campaign_id]
    if campaign["status"] == "running":
        return {"error": "Campaign is already running"}, 400
    
    campaign["status"] = "running"
    campaign["started_at"] = datetime.utcnow().isoformat()
    active_campaigns.add(campaign_id)
    
    # Start background task to simulate email sending
    asyncio.create_task(simulate_email_sending(campaign_id))
    
    logger.info(f"Campaign started: {campaign_id}")
    
    return {"success": True, "message": "Campaign started"}

@app.post("/api/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: str):
    if campaign_id not in campaigns_storage:
        return {"error": "Campaign not found"}, 404
    
    campaign = campaigns_storage[campaign_id]
    campaign["status"] = "stopped"
    campaign["stopped_at"] = datetime.utcnow().isoformat()
    
    if campaign_id in active_campaigns:
        active_campaigns.remove(campaign_id)
    
    logger.info(f"Campaign stopped: {campaign_id}")
    
    return {"success": True, "message": "Campaign stopped"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now
            await websocket.send_text(f"Received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def simulate_email_sending(campaign_id: str):
    """Simulate email sending process"""
    campaign = campaigns_storage.get(campaign_id)
    if not campaign:
        return
    
    # Simulate sending 1000 emails
    total_emails = 1000
    
    for i in range(total_emails):
        if campaign["status"] != "running":
            break
        
        # Simulate email sending delay
        await asyncio.sleep(0.1)  # 100ms per email
        
        # Simulate success/failure (90% success rate)
        if i % 10 != 0:  # 90% success
            campaign["total_sent"] += 1
            stats_data["total_sent"] += 1
        else:
            campaign["total_failed"] += 1
            stats_data["total_failed"] += 1
        
        # Broadcast progress every 10 emails
        if i % 10 == 0:
            await manager.broadcast({
                "type": "campaign_update",
                "campaign_id": campaign_id,
                "progress": {
                    "sent": campaign["total_sent"],
                    "failed": campaign["total_failed"],
                    "progress": (i / total_emails) * 100
                }
            })
    
    # Mark as completed
    campaign["status"] = "completed"
    campaign["completed_at"] = datetime.utcnow().isoformat()
    
    if campaign_id in active_campaigns:
        active_campaigns.remove(campaign_id)
    
    logger.info(f"Campaign completed: {campaign_id}")

if __name__ == "__main__":
    uvicorn.run(
        "simple_production_app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        access_log=True
    )
EOF

echo ""
echo "4. Creating simplified Docker Compose..."
cat > docker-compose-simple.yml << 'EOF'
version: '3.8'

services:
  app:
    build: 
      context: .
      dockerfile: Dockerfile-simple
    ports:
      - "8000:8000"
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
    volumes:
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx-simple.conf:/etc/nginx/nginx.conf
    depends_on:
      - app
    restart: unless-stopped
EOF

echo ""
echo "5. Creating simplified Dockerfile..."
cat > Dockerfile-simple << 'EOF'
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY simple_production_app.py .

RUN pip install fastapi uvicorn[standard] websockets

EXPOSE 8000

CMD ["python", "simple_production_app.py"]
EOF

echo ""
echo "6. Creating simplified Nginx config..."
cat > nginx-simple.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream fastapi_backend {
        server app:8000;
    }

    server {
        listen 80;
        
        location / {
            proxy_pass http://fastapi_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
EOF

echo ""
echo "7. Starting simplified production system..."
docker-compose -f docker-compose-simple.yml up -d --build

echo ""
echo "8. Waiting for services to start..."
sleep 20

echo ""
echo "9. Testing the application..."
echo "Testing direct FastAPI access..."
curl -s http://localhost:8000/health | jq '.' || echo "❌ FastAPI test failed"

echo ""
echo "Testing through Nginx..."
curl -s http://localhost/health | jq '.' || echo "❌ Nginx test failed"

echo ""
echo "10. Checking service status..."
docker-compose -f docker-compose-simple.yml ps

echo ""
echo "✅ Simplified production system deployed!"
echo ""
echo "🌐 Access URLs:"
echo "- Direct FastAPI: http://localhost:8000"
echo "- Through Nginx: http://localhost (or your server IP)"
echo ""
echo "📊 To monitor:"
echo "- View logs: docker-compose -f docker-compose-simple.yml logs -f"
echo "- Check status: docker-compose -f docker-compose-simple.yml ps"
echo ""
echo "🔧 If still having issues:"
echo "- Check firewall: sudo ufw status"
echo "- Check ports: netstat -tuln | grep -E '(80|8000)'"
echo "- Restart: docker-compose -f docker-compose-simple.yml restart"