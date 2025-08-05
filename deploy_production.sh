#!/bin/bash

echo "🚀 Deploying Production Email Campaign Manager"
echo "=============================================="

# Stop current service
echo "🛑 Stopping current service..."
sudo systemctl stop email-campaign-manager

# Backup current app
echo "💾 Backing up current application..."
cp app.py app_backup_$(date +%Y%m%d_%H%M%S).py

# Replace with production version
echo "⚡ Installing production version..."
cp app_production.py app.py

# Install required packages
echo "📦 Installing required packages..."
source venv/bin/activate
pip install gunicorn gevent eventlet psutil requests schedule

# Create high-performance gunicorn configuration
echo "⚙️ Creating high-performance Gunicorn configuration..."
cat > gunicorn_production.conf.py << EOF
# High-performance Gunicorn configuration
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1  # Use all CPU cores
worker_class = "gevent"
worker_connections = 2000
max_requests = 2000
max_requests_jitter = 200
timeout = 300
keepalive = 10
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
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "email-campaign-manager"

# Server mechanics
pidfile = "/tmp/gunicorn.pid"
user = "emailcampaign"
group = "emailcampaign"
tmp_upload_dir = "/dev/shm"

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

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

def worker_abort(worker):
    worker.log.info("Worker aborted (pid: %s)", worker.pid)
EOF

# Create optimized systemd service
echo "🔧 Creating optimized systemd service..."
sudo tee /etc/systemd/system/email-campaign-manager.service > /dev/null << EOF
[Unit]
Description=Production Email Campaign Manager
After=network.target

[Service]
Type=exec
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment=PATH=/home/emailcampaign/email-campaign-manager/venv/bin
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn -c gunicorn_production.conf.py app:app
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=email-campaign-manager

# Performance optimizations - Use ALL server resources
LimitNOFILE=100000
LimitNPROC=10000
MemoryMax=6G
CPUQuota=400%

# Environment variables for performance
Environment=PYTHONUNBUFFERED=1
Environment=FLASK_ENV=production
Environment=WERKZEUG_RUN_MAIN=true
Environment=PYTHONOPTIMIZE=1

# Resource limits
Nice=-10
IOSchedulingClass=1
IOSchedulingPriority=4

[Install]
WantedBy=multi-user.target
EOF

# Optimize system settings for maximum performance
echo "📊 Optimizing system settings for maximum performance..."
echo "net.core.somaxconn = 100000" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 100000" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_fin_timeout = 30" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_keepalive_time = 1200" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_tw_buckets = 5000" | sudo tee -a /etc/sysctl.conf
echo "vm.swappiness = 1" | sudo tee -a /etc/sysctl.conf
echo "vm.dirty_ratio = 10" | sudo tee -a /etc/sysctl.conf
echo "vm.dirty_background_ratio = 5" | sudo tee -a /etc/sysctl.conf
echo "vm.overcommit_memory = 1" | sudo tee -a /etc/sysctl.conf
echo "fs.file-max = 100000" | sudo tee -a /etc/sysctl.conf

# Apply sysctl changes
sudo sysctl -p

# Increase file descriptor limits
echo "* soft nofile 100000" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 100000" | sudo tee -a /etc/security/limits.conf
echo "* soft nproc 10000" | sudo tee -a /etc/security/limits.conf
echo "* hard nproc 10000" | sudo tee -a /etc/security/limits.conf

# Create performance monitoring script
echo "📊 Creating comprehensive performance monitoring script..."
cat > monitor_production.sh << 'EOF'
#!/bin/bash

echo "=== Production Performance Monitor ==="
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
echo "=== Active Connections ==="
netstat -an | grep :5000 | wc -l

echo ""
echo "=== File Descriptors ==="
lsof -p $(pgrep -f gunicorn) 2>/dev/null | wc -l

echo ""
echo "=== Response Time Test ==="
time curl -s http://localhost:5000/api/stats > /dev/null

echo ""
echo "=== Disk I/O ==="
iostat -x 1 1

echo ""
echo "=== Network Usage ==="
ss -tuln | grep :5000

echo ""
echo "=== Process Tree ==="
pstree -p $(pgrep -f gunicorn) 2>/dev/null || echo "No gunicorn processes found"
EOF

chmod +x monitor_production.sh

# Create resource utilization script
echo "📈 Creating resource utilization script..."
cat > optimize_resources.sh << 'EOF'
#!/bin/bash

echo "=== Resource Optimization ==="

# Set process priority
echo "Setting high priority for email-campaign-manager..."
sudo renice -n -10 -p $(pgrep -f email-campaign-manager) 2>/dev/null || echo "Process not found"

# Clear caches
echo "Clearing system caches..."
sudo sync
sudo echo 3 > /proc/sys/vm/drop_caches

# Optimize memory
echo "Optimizing memory usage..."
sudo echo 1 > /proc/sys/vm/compact_memory

# Set CPU governor to performance
echo "Setting CPU governor to performance..."
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

echo "Resource optimization completed!"
EOF

chmod +x optimize_resources.sh

# Create log rotation for high volume
echo "📝 Setting up high-volume log rotation..."
sudo tee /etc/logrotate.d/email-campaign-manager > /dev/null << EOF
/var/log/email-campaign-manager.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 emailcampaign emailcampaign
    postrotate
        systemctl reload email-campaign-manager
    endscript
    size 100M
}

/home/emailcampaign/email-campaign-manager/app.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 emailcampaign emailcampaign
    size 50M
}
EOF

# Set up cron jobs for maintenance
echo "⏰ Setting up maintenance cron jobs..."
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/emailcampaign/email-campaign-manager/monitor_production.sh >> /home/emailcampaign/production_monitor.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "0 */2 * * * /home/emailcampaign/email-campaign-manager/optimize_resources.sh >> /home/emailcampaign/resource_optimization.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "0 2 * * * find /home/emailcampaign/email-campaign-manager -name '*.log' -mtime +7 -delete") | crontab -

# Reload systemd and start service
echo "🔄 Starting production service..."
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
./monitor_production.sh

# Optimize resources
echo ""
echo "🔧 Optimizing resources..."
./optimize_resources.sh

echo ""
echo "✅ Production deployment completed!"
echo ""
echo "🎯 Performance improvements:"
echo "- Using ALL CPU cores (workers = CPU cores * 2 + 1)"
echo "- High-performance caching with 10-minute TTL"
echo "- Background data refresh every 30 seconds"
echo "- 20 worker threads for async operations"
echo "- Optimized rate limiting and campaign execution"
echo "- Real-time campaign updates via SocketIO"
echo "- Comprehensive monitoring and maintenance"
echo ""
echo "📊 Monitor performance with: ./monitor_production.sh"
echo "🔧 Optimize resources with: ./optimize_resources.sh"
echo "📝 View logs with: sudo journalctl -u email-campaign-manager -f"
echo ""
echo "🚀 The application should now utilize ALL server resources efficiently!" 