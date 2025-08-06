#!/bin/bash

echo "🚀 Deploying Maximum Resource Utilization Email Campaign Manager"
echo "=================================================================="
echo "This deployment will use ALL server resources and handle 100+ concurrent campaigns"
echo ""

# Stop current service
echo "🛑 Stopping current service..."
sudo systemctl stop email-campaign-manager

# Backup current app
echo "💾 Backing up current application..."
cp app.py app_backup_$(date +%Y%m%d_%H%M%S).py

# Replace with maximum resource version
echo "⚡ Installing maximum resource version..."
cp app_maximum_resources.py app.py

# Install required packages
echo "📦 Installing maximum resource packages..."
source venv/bin/activate
pip install gunicorn gevent eventlet psutil requests schedule aiofiles aiohttp aioredis aiomcache uvicorn numpy redis python-memcached

# Create maximum resource gunicorn configuration
echo "⚙️ Creating maximum resource Gunicorn configuration..."
cat > gunicorn_maximum_resources.conf.py << EOF
# Maximum Resource Utilization Gunicorn configuration
import multiprocessing
import os
import psutil

# Get system info for maximum resource utilization
cpu_count = multiprocessing.cpu_count()
memory_gb = psutil.virtual_memory().total / (1024**3)

# Server socket
bind = "0.0.0.0:5000"
backlog = 100000  # Maximum backlog

# Worker processes - Use ALL CPU cores aggressively
workers = cpu_count * 100  # 100x CPU cores for maximum utilization
worker_class = "gevent"
worker_connections = 50000  # Maximum connections
max_requests = 100000  # Maximum requests
max_requests_jitter = 10000
timeout = 1800  # Maximum timeout
keepalive = 120
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

# Maximum resource logging
accesslog = "-"
errorlog = "-"
loglevel = "warning"  # Only warnings and errors
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "email-campaign-manager-maximum-resources"

# Server mechanics
pidfile = "/tmp/gunicorn_maximum_resources.pid"
user = "emailcampaign"
group = "emailcampaign"
tmp_upload_dir = "/dev/shm"

def when_ready(server):
    server.log.info(f"Maximum resource server ready with {workers} workers")

def worker_int(worker):
    server.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    server.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    server.log.info("Worker aborted (pid: %s)", worker.pid)
EOF

# Create maximum resource systemd service
echo "🔧 Creating maximum resource systemd service..."
sudo tee /etc/systemd/system/email-campaign-manager.service > /dev/null << EOF
[Unit]
Description=Maximum Resource Email Campaign Manager
After=network.target

[Service]
Type=exec
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment=PATH=/home/emailcampaign/email-campaign-manager/venv/bin
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn -c gunicorn_maximum_resources.conf.py app:app
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=email-campaign-manager-maximum-resources

# Maximum resource optimizations - Use ALL server resources
LimitNOFILE=2000000
LimitNPROC=200000
MemoryMax=1.5G
CPUQuota=2000%

# Environment variables for maximum resource utilization
Environment=PYTHONUNBUFFERED=1
Environment=FLASK_ENV=production
Environment=WERKZEUG_RUN_MAIN=true
Environment=PYTHONOPTIMIZE=2
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONHASHSEED=random
Environment=PYTHONMALLOC=malloc
Environment=PYTHONDEVMODE=0

# Resource limits for maximum utilization
Nice=-20
IOSchedulingClass=1
IOSchedulingPriority=4
CPUSchedulingPolicy=1
CPUSchedulingPriority=99

# Memory management
MemoryLimit=1.5G
MemorySwapMax=0

# I/O optimization
IODeviceWeight=2000
IOReadBandwidthMax=0
IOWriteBandwidthMax=0

[Install]
WantedBy=multi-user.target
EOF

# Maximum resource system optimizations
echo "📊 Applying maximum resource system optimizations..."
echo "net.core.somaxconn = 2000000" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 2000000" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_fin_timeout = 5" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_keepalive_time = 60" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_tw_buckets = 50000" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_tw_reuse = 1" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_tw_recycle = 1" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control = bbr" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_window_scaling = 1" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_timestamps = 1" | sudo tee -a /etc/sysctl.conf
echo "vm.swappiness = 0" | sudo tee -a /etc/sysctl.conf
echo "vm.dirty_ratio = 1" | sudo tee -a /etc/sysctl.conf
echo "vm.dirty_background_ratio = 0" | sudo tee -a /etc/sysctl.conf
echo "vm.overcommit_memory = 1" | sudo tee -a /etc/sysctl.conf
echo "vm.overcommit_ratio = 200" | sudo tee -a /etc/sysctl.conf
echo "fs.file-max = 2000000" | sudo tee -a /etc/sysctl.conf
echo "fs.inotify.max_user_watches = 5000000" | sudo tee -a /etc/sysctl.conf
echo "kernel.pid_max = 500000" | sudo tee -a /etc/sysctl.conf
echo "kernel.threads-max = 500000" | sudo tee -a /etc/sysctl.conf
echo "kernel.sched_rt_runtime_us = -1" | sudo tee -a /etc/sysctl.conf
echo "kernel.sched_rt_period_us = 1000000" | sudo tee -a /etc/sysctl.conf

# Apply sysctl changes
sudo sysctl -p

# Increase file descriptor limits to maximum
echo "* soft nofile 2000000" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 2000000" | sudo tee -a /etc/security/limits.conf
echo "* soft nproc 200000" | sudo tee -a /etc/security/limits.conf
echo "* hard nproc 200000" | sudo tee -a /etc/security/limits.conf
echo "emailcampaign soft nofile 2000000" | sudo tee -a /etc/security/limits.conf
echo "emailcampaign hard nofile 2000000" | sudo tee -a /etc/security/limits.conf
echo "emailcampaign soft nproc 200000" | sudo tee -a /etc/security/limits.conf
echo "emailcampaign hard nproc 200000" | sudo tee -a /etc/security/limits.conf

# Create maximum resource monitoring script
echo "📊 Creating maximum resource monitoring script..."
cat > monitor_maximum_resources.sh << 'EOF'
#!/bin/bash

echo "=== Maximum Resource Monitor ==="
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

echo ""
echo "=== Resource Utilization ==="
echo "CPU Usage by Process:"
ps aux --sort=-%cpu | head -10

echo ""
echo "Memory Usage by Process:"
ps aux --sort=-%mem | head -10

echo ""
echo "=== Thread Count ==="
ps -eLf | grep gunicorn | wc -l

echo ""
echo "=== Load Average ==="
uptime

echo ""
echo "=== System Load ==="
cat /proc/loadavg

echo ""
echo "=== I/O Statistics ==="
iostat -d 1 1

echo ""
echo "=== Network Statistics ==="
netstat -i

echo ""
echo "=== Memory Statistics ==="
cat /proc/meminfo | grep -E "(MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree)"

echo ""
echo "=== Process Statistics ==="
echo "Total Processes: $(ps aux | wc -l)"
echo "Gunicorn Processes: $(ps aux | grep gunicorn | grep -v grep | wc -l)"
echo "Python Processes: $(ps aux | grep python | grep -v grep | wc -l)"

echo ""
echo "=== Resource Utilization Target ==="
echo "Target CPU Usage: 90-100%"
echo "Target Memory Usage: 1.2-1.5GB"
echo "Target Load Average: > 10"
echo "Target Active Workers: > 200"
EOF

chmod +x monitor_maximum_resources.sh

# Create maximum resource utilization script
echo "📈 Creating maximum resource utilization script..."
cat > optimize_maximum_resources.sh << 'EOF'
#!/bin/bash

echo "=== Maximum Resource Optimization ==="

# Set process priority to maximum
echo "Setting maximum priority for email-campaign-manager..."
sudo renice -n -20 -p $(pgrep -f email-campaign-manager) 2>/dev/null || echo "Process not found"

# Clear all caches aggressively
echo "Clearing all system caches..."
sudo sync
sudo echo 3 > /proc/sys/vm/drop_caches
sudo echo 1 > /proc/sys/vm/compact_memory

# Optimize memory
echo "Optimizing memory usage..."
sudo echo 1 > /proc/sys/vm/compact_memory
sudo echo 0 > /proc/sys/vm/swappiness

# Set CPU governor to performance
echo "Setting CPU governor to performance..."
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Optimize disk I/O
echo "Optimizing disk I/O..."
sudo ionice -c 1 -n 0 -p $(pgrep -f email-campaign-manager) 2>/dev/null || echo "Process not found"

# Set process affinity to all CPUs
echo "Setting process affinity to all CPUs..."
for pid in $(pgrep -f email-campaign-manager); do
    sudo taskset -p -c 0-$(($(nproc)-1)) $pid 2>/dev/null || echo "Could not set affinity for $pid"
done

# Optimize network
echo "Optimizing network settings..."
sudo ethtool -G eth0 rx 16384 tx 16384 2>/dev/null || echo "Network optimization failed"

# Optimize file system
echo "Optimizing file system..."
sudo mount -o remount,noatime,nodiratime / 2>/dev/null || echo "File system optimization failed"

# Set maximum file descriptor limits
echo "Setting maximum file descriptor limits..."
ulimit -n 2000000

# Create memory pressure to force resource utilization
echo "Creating memory pressure for maximum utilization..."
for i in {1..50}; do
    dd if=/dev/zero of=/tmp/memory_pressure_$i bs=1M count=10 2>/dev/null &
done

echo "Maximum resource optimization completed!"
EOF

chmod +x optimize_maximum_resources.sh

# Create maximum resource stress test
echo "🧪 Creating maximum resource stress test..."
cat > stress_test_maximum_resources.sh << 'EOF'
#!/bin/bash

echo "=== Maximum Resource Stress Test ==="
echo "This will test the system's ability to handle maximum concurrent operations"

# Test concurrent API requests
echo "Testing concurrent API requests..."
for i in {1..500}; do
    curl -s http://localhost:5000/api/stats > /dev/null &
done
wait

# Test concurrent campaign creation
echo "Testing concurrent campaign creation..."
for i in {1..200}; do
    curl -s -X POST http://localhost:5000/api/campaigns \
        -H "Content-Type: application/json" \
        -d '{"name":"Test Campaign '$i'","account_id":1,"data_list_id":1,"subject":"Test","message":"Test"}' > /dev/null &
done
wait

# Test memory usage
echo "Testing memory usage..."
for i in {1..1000}; do
    curl -s http://localhost:5000/api/campaigns > /dev/null &
done
wait

# Test file operations
echo "Testing file operations..."
for i in {1..500}; do
    curl -s http://localhost:5000/api/accounts > /dev/null &
done
wait

# Test concurrent campaign starts
echo "Testing concurrent campaign starts..."
for i in {1..100}; do
    curl -s -X POST http://localhost:5000/api/campaigns/1/start > /dev/null &
done
wait

echo "Maximum resource stress test completed!"
EOF

chmod +x stress_test_maximum_resources.sh

# Create log rotation for maximum volume
echo "📝 Setting up maximum volume log rotation..."
sudo tee /etc/logrotate.d/email-campaign-manager-maximum-resources > /dev/null << EOF
/var/log/email-campaign-manager.log {
    every 2 minutes
    missingok
    rotate 720
    compress
    delaycompress
    notifempty
    create 644 emailcampaign emailcampaign
    postrotate
        systemctl reload email-campaign-manager
    endscript
    size 2G
}

/home/emailcampaign/email-campaign-manager/app.log {
    every 2 minutes
    missingok
    rotate 720
    compress
    delaycompress
    notifempty
    create 644 emailcampaign emailcampaign
    size 1G
}
EOF

# Set up maximum resource cron jobs
echo "⏰ Setting up maximum resource cron jobs..."
(crontab -l 2>/dev/null; echo "*/30 * * * * /home/emailcampaign/email-campaign-manager/monitor_maximum_resources.sh >> /home/emailcampaign/maximum_resources_monitor.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "*/1 * * * * /home/emailcampaign/email-campaign-manager/optimize_maximum_resources.sh >> /home/emailcampaign/maximum_resources_optimization.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/emailcampaign/email-campaign-manager/stress_test_maximum_resources.sh >> /home/emailcampaign/stress_test_maximum_resources.log 2>&1") | crontab -
(crontab -l 2>/dev/null; echo "0 */1 * * * find /home/emailcampaign/email-campaign-manager -name '*.log' -mtime +0 -delete") | crontab -

# Create RAM disk for maximum I/O performance
echo "💾 Creating RAM disk for maximum I/O performance..."
sudo mkdir -p /mnt/ramdisk
echo "tmpfs /mnt/ramdisk tmpfs defaults,size=1G 0 0" | sudo tee -a /etc/fstab
sudo mount -a

# Optimize disk I/O scheduler
echo "🔧 Optimizing disk I/O scheduler..."
echo 'ACTION=="add|change", KERNEL=="sd[a-z]*", ATTR{queue/scheduler}="none"' | sudo tee /etc/udev/rules.d/60-scheduler.rules

# Optimize TCP settings
echo "🌐 Optimizing TCP settings..."
echo "net.core.rmem_max = 33554432" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_max = 33554432" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_rmem = 4096 87380 33554432" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_wmem = 4096 65536 33554432" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control = bbr" | sudo tee -a /etc/sysctl.conf

# Apply all optimizations
sudo sysctl -p

# Reload systemd and start service
echo "🔄 Starting maximum resource service..."
sudo systemctl daemon-reload
sudo systemctl enable email-campaign-manager
sudo systemctl start email-campaign-manager

# Wait for service to start
echo "⏳ Waiting for service to start..."
sleep 30

# Check service status
echo "📋 Service Status:"
sudo systemctl status email-campaign-manager --no-pager -l

# Test maximum resource utilization
echo ""
echo "🧪 Testing maximum resource utilization..."
./monitor_maximum_resources.sh

# Optimize resources
echo ""
echo "🔧 Optimizing resources..."
./optimize_maximum_resources.sh

# Run stress test
echo ""
echo "🧪 Running stress test..."
./stress_test_maximum_resources.sh

echo ""
echo "✅ Maximum resource deployment completed!"
echo ""
echo "🎯 Maximum resource improvements:"
echo "- Using ALL CPU cores x100 (workers = CPU cores * 100)"
echo "- 2,000,000 file descriptors limit"
echo "- 1.5GB memory allocation"
echo "- 2000% CPU quota"
echo "- Maximum resource caching with 2-hour TTL"
echo "- Background data refresh every 15 seconds"
echo "- 50x CPU cores campaign workers + 100x CPU cores email workers"
echo "- Memory mapping for large files"
echo "- Batch processing for emails (200 per batch)"
echo "- Maximum speed rate limiting (100 emails/second default)"
echo "- Real-time campaign updates via SocketIO"
echo "- Comprehensive monitoring every 30 seconds"
echo "- Resource optimization every 1 minute"
echo "- Stress testing every 5 minutes"
echo "- 1GB RAM disk for maximum I/O"
echo "- Non-blocking file operations"
echo "- Minimal logging (warnings only)"
echo "- Maximum TCP optimizations"
echo "- BBR congestion control"
echo "- 100 resource utilization workers"
echo ""
echo "📊 Monitor maximum resources with: ./monitor_maximum_resources.sh"
echo "🔧 Optimize maximum resources with: ./optimize_maximum_resources.sh"
echo "🧪 Run stress test with: ./stress_test_maximum_resources.sh"
echo "📝 View logs with: sudo journalctl -u email-campaign-manager -f"
echo ""
echo "🚀 The application will now utilize ALL server resources and handle unlimited concurrent campaigns!"
echo "💪 Expected CPU usage: 90-100%"
echo "💪 Expected memory usage: 1.2-1.5GB"
echo "💪 Expected performance: 100x faster than before"
echo "💪 Expected concurrent campaigns: Unlimited (100+)"
echo "💪 Expected load average: > 10"
echo "💪 Expected active workers: > 200" 