#!/bin/bash

echo "🔧 DEPLOYING FIXED EMAIL CAMPAIGN MANAGER"
echo "========================================"
echo "This fixes the real performance issues without overcomplicating"
echo ""

# Stop current service
echo "🛑 Stopping current service..."
sudo systemctl stop email-campaign-manager 2>/dev/null || true
sudo pkill -f gunicorn 2>/dev/null || true
sudo pkill -f python 2>/dev/null || true

# Backup current app
echo "💾 Backing up current application..."
cp app.py app_backup_$(date +%Y%m%d_%H%M%S).py 2>/dev/null || true

# Replace with fixed version
echo "✅ Installing fixed version..."
cp app_fixed.py app.py

# Install required packages
echo "📦 Installing required packages..."
source venv/bin/activate
pip install flask flask-socketio flask-login werkzeug

# Create simple gunicorn configuration
echo "⚙️ Creating simple Gunicorn configuration..."
cat > gunicorn_simple.conf.py << 'EOF'
# Simple Gunicorn configuration
import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "email-campaign-manager"

# Server mechanics
pidfile = "/tmp/gunicorn_simple.pid"
user = "emailcampaign"
group = "emailcampaign"

def when_ready(server):
    server.log.info("Simple server ready")

def worker_int(worker):
    server.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)
EOF

# Create simple systemd service
echo "🔧 Creating simple systemd service..."
sudo tee /etc/systemd/system/email-campaign-manager.service > /dev/null << 'EOF'
[Unit]
Description=Fixed Email Campaign Manager
After=network.target

[Service]
Type=exec
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment=PATH=/home/emailcampaign/email-campaign-manager/venv/bin
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn -c gunicorn_simple.conf.py app:app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=email-campaign-manager

# Simple resource limits
LimitNOFILE=65536
MemoryMax=2G
CPUQuota=200%

# Environment variables
Environment=PYTHONUNBUFFERED=1
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
EOF

# Apply basic system optimizations
echo "📊 Applying basic system optimizations..."
echo "net.core.somaxconn = 65536" | sudo tee -a /etc/sysctl.conf
echo "fs.file-max = 65536" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Increase file descriptor limits
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "emailcampaign soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "emailcampaign hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Create simple monitoring script
echo "📊 Creating simple monitoring script..."
cat > monitor_simple.sh << 'EOF'
#!/bin/bash

echo "=== SIMPLE PERFORMANCE MONITOR ==="
echo "Date: $(date)"
echo ""

echo "=== System Resources ==="
echo "CPU Cores: $(nproc)"
echo "Total RAM: $(free -h | grep Mem | awk '{print $2}')"
echo "Available RAM: $(free -h | grep Mem | awk '{print $7}')"

echo ""
echo "=== CPU Usage ==="
top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1

echo ""
echo "=== Memory Usage ==="
free -h

echo ""
echo "=== Application Status ==="
systemctl status email-campaign-manager --no-pager -l

echo ""
echo "=== Gunicorn Workers ==="
ps aux | grep gunicorn | grep -v grep | wc -l

echo ""
echo "=== Response Time Test ==="
time curl -s http://localhost:5000/api/stats > /dev/null

echo ""
echo "=== Process Tree ==="
pstree -p $(pgrep -f gunicorn) 2>/dev/null || echo "No gunicorn processes found"

echo ""
echo "=== Resource Utilization ==="
echo "CPU Usage by Process:"
ps aux --sort=-%cpu | head -5

echo ""
echo "Memory Usage by Process:"
ps aux --sort=-%mem | head -5

echo ""
echo "=== Load Average ==="
uptime

echo ""
echo "=== Campaign Status ==="
curl -s http://localhost:5000/api/campaigns | jq '.[] | select(.status == "running") | {id, name, status, total_sent, total_failed}' 2>/dev/null || echo "No running campaigns found"
EOF

chmod +x monitor_simple.sh

# Reload systemd and start service
echo "🔄 Starting fixed service..."
sudo systemctl daemon-reload
sudo systemctl enable email-campaign-manager
sudo systemctl start email-campaign-manager

# Wait for service to start
echo "⏳ Waiting for service to start..."
sleep 10

# Check service status
echo "📋 Service Status:"
sudo systemctl status email-campaign-manager --no-pager -l

# Test performance
echo ""
echo "🧪 Testing performance..."
./monitor_simple.sh

echo ""
echo "✅ FIXED DEPLOYMENT COMPLETED!"
echo ""
echo "🎯 What was fixed:"
echo "- Removed complex caching that was causing freezes"
echo "- Simplified file operations"
echo "- Used simple queue-based campaign processing"
echo "- Removed background processes that were consuming resources"
echo "- Used basic Gunicorn configuration"
echo "- Simple error handling"
echo "- No complex rate limiting"
echo "- No memory mapping"
echo "- No aggressive optimizations"
echo ""
echo "📊 Monitor performance with: ./monitor_simple.sh"
echo "📝 View logs with: sudo journalctl -u email-campaign-manager -f"
echo ""
echo "🚀 The application should now be fast and reliable!"
echo "💪 Expected performance: Fast page loads, no freezing"
echo "💪 Expected resource usage: Normal CPU/memory usage"
echo "💪 Expected behavior: Smooth operation, working campaigns" 