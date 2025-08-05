#!/bin/bash

echo "🚀 Deploying Optimized Email Campaign Manager"
echo "============================================="

# Stop current service
echo "🛑 Stopping current service..."
sudo systemctl stop email-campaign-manager

# Backup current app
echo "💾 Backing up current application..."
cp app.py app_backup_$(date +%Y%m%d_%H%M%S).py

# Replace with optimized version
echo "⚡ Installing optimized version..."
cp app_optimized.py app.py

# Install required packages
echo "📦 Installing required packages..."
source venv/bin/activate
pip install gunicorn gevent eventlet

# Create optimized gunicorn configuration
echo "⚙️ Creating optimized Gunicorn configuration..."
cat > gunicorn_optimized.conf.py << EOF
# Gunicorn configuration for high performance
bind = "0.0.0.0:5000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 120
keepalive = 5
preload_app = True
daemon = False

# Performance optimizations
worker_tmp_dir = "/dev/shm"
forwarded_allow_ips = "*"
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "warning"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)
EOF

# Create optimized systemd service
echo "🔧 Creating optimized systemd service..."
sudo tee /etc/systemd/system/email-campaign-manager.service > /dev/null << EOF
[Unit]
Description=Optimized Email Campaign Manager
After=network.target

[Service]
Type=exec
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment=PATH=/home/emailcampaign/email-campaign-manager/venv/bin
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn -c gunicorn_optimized.conf.py app:app
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=email-campaign-manager

# Performance optimizations
LimitNOFILE=65536
LimitNPROC=4096
MemoryMax=2G
CPUQuota=200%

# Environment variables for performance
Environment=PYTHONUNBUFFERED=1
Environment=FLASK_ENV=production
Environment=WERKZEUG_RUN_MAIN=true

[Install]
WantedBy=multi-user.target
EOF

# Optimize system settings
echo "📊 Optimizing system settings..."
echo "net.core.somaxconn = 65536" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65536" | sudo tee -a /etc/sysctl.conf
echo "vm.swappiness = 10" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Increase file descriptor limits
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Create performance monitoring script
echo "📊 Creating performance monitoring script..."
cat > monitor_performance.sh << 'EOF'
#!/bin/bash

echo "=== Performance Monitor ==="
echo "Date: $(date)"
echo ""

echo "=== Application Status ==="
systemctl status email-campaign-manager --no-pager -l

echo ""
echo "=== Memory Usage ==="
free -h

echo ""
echo "=== CPU Usage ==="
top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1

echo ""
echo "=== Active Connections ==="
netstat -an | grep :5000 | wc -l

echo ""
echo "=== Cache Status ==="
ps aux | grep gunicorn | grep -v grep | wc -l

echo ""
echo "=== Response Time Test ==="
time curl -s http://localhost:5000/api/stats > /dev/null
EOF

chmod +x monitor_performance.sh

# Reload systemd and start service
echo "🔄 Starting optimized service..."
sudo systemctl daemon-reload
sudo systemctl enable email-campaign-manager
sudo systemctl start email-campaign-manager

# Wait for service to start
echo "⏳ Waiting for service to start..."
sleep 5

# Check service status
echo "📋 Service Status:"
sudo systemctl status email-campaign-manager --no-pager -l

# Test performance
echo ""
echo "🧪 Testing performance..."
./monitor_performance.sh

echo ""
echo "✅ Optimized deployment completed!"
echo ""
echo "🎯 Performance improvements:"
echo "- 4 Gunicorn workers with gevent"
echo "- Aggressive caching (60-second TTL)"
echo "- Background stats pre-calculation"
echo "- Optimized file I/O operations"
echo "- Reduced logging overhead"
echo "- Production-ready configuration"
echo ""
echo "📊 Monitor performance with: ./monitor_performance.sh"
echo "📝 View logs with: sudo journalctl -u email-campaign-manager -f" 