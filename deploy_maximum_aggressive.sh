#!/bin/bash

echo "🚀 DEPLOYING MAXIMUM AGGRESSIVE EMAIL CAMPAIGN MANAGER"
echo "   This will use 90% of ALL server resources for maximum performance"
echo ""

# ============================================================================
# SYSTEM DETECTION AND OPTIMIZATION
# ============================================================================

echo "🔍 DETECTING SERVER RESOURCES..."

# Get CPU info
CPU_CORES=$(nproc)
CPU_FREQ=$(cat /proc/cpuinfo | grep "cpu MHz" | head -1 | awk '{print $4}')
echo "   CPU: $CPU_CORES cores, ${CPU_FREQ}MHz"

# Get memory info
TOTAL_MEM=$(free -g | grep Mem | awk '{print $2}')
AVAILABLE_MEM=$(free -g | grep Mem | awk '{print $7}')
echo "   Memory: ${TOTAL_MEM}GB total, ${AVAILABLE_MEM}GB available"

# Get disk info
DISK_TOTAL=$(df -h / | tail -1 | awk '{print $2}')
DISK_FREE=$(df -h / | tail -1 | awk '{print $4}')
echo "   Disk: ${DISK_TOTAL} total, ${DISK_FREE} free"

# Calculate aggressive limits (90% of resources)
CPU_WORKERS=$((CPU_CORES * 9 / 10))
THREAD_WORKERS=$((CPU_WORKERS * 8))
MEMORY_TARGET=$((AVAILABLE_MEM * 9 / 10))
FILE_DESCRIPTORS=1000000
PROCESS_LIMIT=100000

echo ""
echo "🎯 SETTING AGGRESSIVE LIMITS:"
echo "   CPU Workers: $CPU_WORKERS processes, $THREAD_WORKERS threads"
echo "   Memory Target: ${MEMORY_TARGET}GB"
echo "   File Descriptors: $FILE_DESCRIPTORS"
echo "   Process Limit: $PROCESS_LIMIT"

# ============================================================================
# SYSTEM OPTIMIZATION
# ============================================================================

echo ""
echo "⚡ APPLYING MAXIMUM SYSTEM OPTIMIZATIONS..."

# Set system limits
echo "* soft nofile $FILE_DESCRIPTORS" >> /etc/security/limits.conf
echo "* hard nofile $FILE_DESCRIPTORS" >> /etc/security/limits.conf
echo "* soft nproc $PROCESS_LIMIT" >> /etc/security/limits.conf
echo "* hard nproc $PROCESS_LIMIT" >> /etc/security/limits.conf

# Kernel optimizations
cat >> /etc/sysctl.conf << EOF

# Maximum aggressive performance settings
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 50000
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 10
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_tw_recycle = 1
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6
net.ipv4.tcp_congestion_control = bbr
net.core.rmem_default = 262144
net.core.rmem_max = 16777216
net.core.wmem_default = 262144
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 65536 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
vm.swappiness = 1
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
vm.overcommit_memory = 1
fs.file-max = $FILE_DESCRIPTORS
kernel.pid_max = $PROCESS_LIMIT
kernel.threads-max = $PROCESS_LIMIT
EOF

# Apply sysctl settings
sysctl -p

# ============================================================================
# CREATE MAXIMUM AGGRESSIVE GUNICORN CONFIG
# ============================================================================

echo ""
echo "🔧 CREATING MAXIMUM AGGRESSIVE GUNICORN CONFIG..."

cat > gunicorn_maximum_aggressive.py << EOF
# Maximum Aggressive Gunicorn Configuration
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 50000
max_requests = 10000
max_requests_jitter = 1000

# Worker processes
workers = $CPU_WORKERS
worker_class = "sync"
worker_connections = 10000
timeout = 300
keepalive = 5

# Process naming
proc_name = "email-campaign-manager-maximum-aggressive"

# Logging
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process management
preload_app = True
daemon = False
pidfile = "/var/run/gunicorn/email-campaign-manager.pid"
user = "emailcampaign"
group = "emailcampaign"

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Maximum performance settings
worker_tmp_dir = "/dev/shm"
max_requests_jitter = 1000
graceful_timeout = 300
EOF

# ============================================================================
# CREATE MAXIMUM AGGRESSIVE SYSTEMD SERVICE
# ============================================================================

echo ""
echo "🔧 CREATING MAXIMUM AGGRESSIVE SYSTEMD SERVICE..."

cat > /etc/systemd/system/email-campaign-manager-maximum-aggressive.service << EOF
[Unit]
Description=Email Campaign Manager - Maximum Aggressive Performance
After=network.target

[Service]
Type=exec
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/opt/email-campaign-manager
Environment=PATH=/opt/email-campaign-manager/venv/bin
ExecStart=/opt/email-campaign-manager/venv/bin/gunicorn -c gunicorn_maximum_aggressive.py app_maximum_aggressive:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=5

# Maximum resource limits
LimitNOFILE=$FILE_DESCRIPTORS
LimitNPROC=$PROCESS_LIMIT
MemoryMax=${MEMORY_TARGET}G
CPUQuota=1000%
Nice=-20
IOSchedulingClass=1
IOSchedulingPriority=4

# Performance settings
StandardOutput=journal
StandardError=journal
SyslogIdentifier=email-campaign-manager

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/email-campaign-manager /var/log/gunicorn /tmp

[Install]
WantedBy=multi-user.target
EOF

# ============================================================================
# CREATE MAXIMUM AGGRESSIVE NGINX CONFIG
# ============================================================================

echo ""
echo "🔧 CREATING MAXIMUM AGGRESSIVE NGINX CONFIG..."

cat > /etc/nginx/sites-available/email-campaign-manager-maximum-aggressive << EOF
server {
    listen 80;
    server_name _;
    
    # Maximum performance settings
    client_max_body_size 100M;
    client_body_buffer_size 128k;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 4k;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # Proxy settings
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
    proxy_buffer_size 64k;
    proxy_buffers 4 32k;
    proxy_busy_buffers_size 64k;
    proxy_temp_file_write_size 64k;
    
    # Upstream with maximum workers
    upstream email_campaign_backend {
        server 127.0.0.1:5000;
        keepalive 1000;
    }
    
    location / {
        proxy_pass http://email_campaign_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
    
    # Static files
    location /static/ {
        alias /opt/email-campaign-manager/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# ============================================================================
# CREATE MAXIMUM AGGRESSIVE MONITORING SCRIPTS
# ============================================================================

echo ""
echo "🔧 CREATING MAXIMUM AGGRESSIVE MONITORING SCRIPTS..."

cat > /opt/email-campaign-manager/monitor_maximum_aggressive.sh << EOF
#!/bin/bash

# Maximum Aggressive Performance Monitor
LOG_FILE="/var/log/email-campaign-manager/monitor.log"

log() {
    echo "\$(date '+%Y-%m-%d %H:%M:%S') - \$1" >> \$LOG_FILE
}

# Check CPU usage
CPU_USAGE=\$(top -bn1 | grep "Cpu(s)" | awk '{print \$2}' | cut -d'%' -f1)
if [ "\$CPU_USAGE" -lt 80 ]; then
    log "WARNING: CPU usage only \$CPU_USAGE% - not aggressive enough"
fi

# Check memory usage
MEMORY_USAGE=\$(free | grep Mem | awk '{printf("%.0f", \$3/\$2 * 100.0)}')
if [ "\$MEMORY_USAGE" -lt 80 ]; then
    log "WARNING: Memory usage only \$MEMORY_USAGE% - not aggressive enough"
fi

# Check file descriptors
FD_USAGE=\$(lsof | wc -l)
FD_LIMIT=\$(ulimit -n)
FD_PERCENT=\$((FD_USAGE * 100 / FD_LIMIT))
if [ "\$FD_PERCENT" -lt 80 ]; then
    log "WARNING: File descriptor usage only \$FD_PERCENT% - not aggressive enough"
fi

# Check process count
PROCESS_COUNT=\$(ps aux | wc -l)
PROCESS_LIMIT=\$(ulimit -u)
PROCESS_PERCENT=\$((PROCESS_COUNT * 100 / PROCESS_LIMIT))
if [ "\$PROCESS_PERCENT" -lt 80 ]; then
    log "WARNING: Process usage only \$PROCESS_PERCENT% - not aggressive enough"
fi

log "Resource usage - CPU: \$CPU_USAGE%, Memory: \$MEMORY_USAGE%, FD: \$FD_PERCENT%, Processes: \$PROCESS_PERCENT%"
EOF

chmod +x /opt/email-campaign-manager/monitor_maximum_aggressive.sh

# Create optimization script
cat > /opt/email-campaign-manager/optimize_maximum_aggressive.sh << EOF
#!/bin/bash

# Maximum Aggressive Performance Optimizer
LOG_FILE="/var/log/email-campaign-manager/optimize.log"

log() {
    echo "\$(date '+%Y-%m-%d %H:%M:%S') - \$1" >> \$LOG_FILE
}

# Force garbage collection
python3 -c "import gc; gc.collect()"

# Clear page cache
sync && echo 3 > /proc/sys/vm/drop_caches

# Optimize memory
echo 1 > /proc/sys/vm/compact_memory

# Restart service if needed
if ! systemctl is-active --quiet email-campaign-manager-maximum-aggressive; then
    systemctl restart email-campaign-manager-maximum-aggressive
    log "Restarted email campaign manager service"
fi

log "Performance optimization completed"
EOF

chmod +x /opt/email-campaign-manager/optimize_maximum_aggressive.sh

# ============================================================================
# SETUP CRON JOBS FOR MAXIMUM AGGRESSIVE MONITORING
# ============================================================================

echo ""
echo "🔧 SETTING UP MAXIMUM AGGRESSIVE CRON JOBS..."

# Add monitoring cron jobs
(crontab -l 2>/dev/null; echo "*/1 * * * * /opt/email-campaign-manager/monitor_maximum_aggressive.sh") | crontab -
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/email-campaign-manager/optimize_maximum_aggressive.sh") | crontab -

# ============================================================================
# CREATE RAM DISK FOR MAXIMUM PERFORMANCE
# ============================================================================

echo ""
echo "🔧 CREATING RAM DISK FOR MAXIMUM PERFORMANCE..."

# Calculate RAM disk size (20% of available memory)
RAM_DISK_SIZE=$((MEMORY_TARGET * 1024 * 20 / 100))

# Create RAM disk mount point
mkdir -p /mnt/ramdisk

# Add RAM disk to fstab
echo "tmpfs /mnt/ramdisk tmpfs defaults,size=${RAM_DISK_SIZE}M,noatime,nodiratime 0 0" >> /etc/fstab

# Mount RAM disk
mount /mnt/ramdisk

# Create directories in RAM disk
mkdir -p /mnt/ramdisk/email-campaign-manager
mkdir -p /mnt/ramdisk/email-campaign-manager/cache
mkdir -p /mnt/ramdisk/email-campaign-manager/temp

# ============================================================================
# FINAL SETUP AND START
# ============================================================================

echo ""
echo "🔧 FINAL SETUP..."

# Create log directories
mkdir -p /var/log/gunicorn
mkdir -p /var/log/email-campaign-manager
mkdir -p /var/run/gunicorn

# Set permissions
chown -R emailcampaign:emailcampaign /var/log/gunicorn
chown -R emailcampaign:emailcampaign /var/log/email-campaign-manager
chown -R emailcampaign:emailcampaign /var/run/gunicorn
chown -R emailcampaign:emailcampaign /mnt/ramdisk/email-campaign-manager

# Enable and start services
systemctl daemon-reload
systemctl enable email-campaign-manager-maximum-aggressive
systemctl enable nginx

# Enable nginx site
ln -sf /etc/nginx/sites-available/email-campaign-manager-maximum-aggressive /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Start services
systemctl restart nginx
systemctl start email-campaign-manager-maximum-aggressive

# ============================================================================
# VERIFICATION
# ============================================================================

echo ""
echo "✅ MAXIMUM AGGRESSIVE DEPLOYMENT COMPLETED!"
echo ""
echo "📊 DEPLOYMENT SUMMARY:"
echo "   CPU Workers: $CPU_WORKERS processes, $THREAD_WORKERS threads"
echo "   Memory Target: ${MEMORY_TARGET}GB (${RAM_DISK_SIZE}MB RAM disk)"
echo "   File Descriptors: $FILE_DESCRIPTORS"
echo "   Process Limit: $PROCESS_LIMIT"
echo "   Rate Limit: 100 emails/sec, 5000 emails/min"
echo ""
echo "🔧 SERVICES:"
echo "   Email Campaign Manager: \$(systemctl is-active email-campaign-manager-maximum-aggressive)"
echo "   Nginx: \$(systemctl is-active nginx)"
echo ""
echo "📈 MONITORING:"
echo "   Monitor logs: tail -f /var/log/email-campaign-manager/monitor.log"
echo "   Service logs: journalctl -u email-campaign-manager-maximum-aggressive -f"
echo "   Performance: htop, iotop, nethogs"
echo ""
echo "🚀 The application is now running with MAXIMUM AGGRESSIVE performance!"
echo "   It will use 90% of all available server resources."
echo "" 