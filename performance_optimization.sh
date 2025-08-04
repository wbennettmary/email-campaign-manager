#!/bin/bash

echo "🚀 Performance Optimization for AWS t3a.large Server"
echo "=================================================="

# 1. System-level optimizations
echo "📊 Optimizing system settings..."

# Increase file descriptor limits
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Optimize kernel parameters
echo "net.core.somaxconn = 65536" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65536" | sudo tee -a /etc/sysctl.conf
echo "vm.swappiness = 10" | sudo tee -a /etc/sysctl.conf
echo "vm.dirty_ratio = 15" | sudo tee -a /etc/sysctl.conf
echo "vm.dirty_background_ratio = 5" | sudo tee -a /etc/sysctl.conf

# Apply sysctl changes
sudo sysctl -p

# 2. Install performance monitoring tools
echo "📈 Installing performance monitoring tools..."
sudo apt update
sudo apt install -y htop iotop nethogs sysstat

# 3. Optimize Python environment
echo "🐍 Optimizing Python environment..."
cd /home/emailcampaign/email-campaign-manager

# Activate virtual environment
source venv/bin/activate

# Install performance packages
pip install psutil memory-profiler line-profiler

# 4. Create optimized gunicorn configuration
echo "⚙️ Creating optimized Gunicorn configuration..."
cat > gunicorn_optimized.conf << EOF
[program:email-campaign-manager]
command=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn --workers=4 --worker-class=gevent --worker-connections=1000 --max-requests=1000 --max-requests-jitter=100 --timeout=120 --keep-alive=5 --preload app:app --bind=0.0.0.0:5000
directory=/home/emailcampaign/email-campaign-manager
user=emailcampaign
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/email-campaign-manager.log
environment=PYTHONPATH="/home/emailcampaign/email-campaign-manager"
EOF

# 5. Create systemd service with optimized settings
echo "🔧 Creating optimized systemd service..."
sudo tee /etc/systemd/system/email-campaign-manager.service > /dev/null << EOF
[Unit]
Description=Email Campaign Manager
After=network.target

[Service]
Type=exec
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment=PATH=/home/emailcampaign/email-campaign-manager/venv/bin
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn --workers=4 --worker-class=gevent --worker-connections=1000 --max-requests=1000 --max-requests-jitter=100 --timeout=120 --keep-alive=5 --preload app:app --bind=0.0.0.0:5000
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

[Install]
WantedBy=multi-user.target
EOF

# 6. Optimize Nginx configuration
echo "🌐 Optimizing Nginx configuration..."
sudo tee /etc/nginx/sites-available/email-campaign-manager > /dev/null << EOF
server {
    listen 80;
    server_name _;

    # Performance optimizations
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
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    proxy_buffering off;
    proxy_request_buffering off;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        proxy_pass http://127.0.0.1:5000;
    }
}
EOF

# 7. Enable and restart services
echo "🔄 Restarting services with optimizations..."
sudo systemctl daemon-reload
sudo systemctl enable email-campaign-manager
sudo systemctl restart email-campaign-manager

sudo ln -sf /etc/nginx/sites-available/email-campaign-manager /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl restart nginx

# 8. Set up log rotation
echo "📝 Setting up log rotation..."
sudo tee /etc/logrotate.d/email-campaign-manager > /dev/null << EOF
/var/log/email-campaign-manager.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 emailcampaign emailcampaign
    postrotate
        systemctl reload email-campaign-manager
    endscript
}
EOF

# 9. Create performance monitoring script
echo "📊 Creating performance monitoring script..."
cat > monitor_performance.sh << 'EOF'
#!/bin/bash

echo "=== Performance Monitor ==="
echo "Date: $(date)"
echo ""

echo "=== CPU Usage ==="
top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1

echo "=== Memory Usage ==="
free -h

echo "=== Disk I/O ==="
iostat -x 1 1

echo "=== Network Usage ==="
nethogs -t

echo "=== Application Status ==="
systemctl status email-campaign-manager --no-pager -l

echo "=== Log File Size ==="
ls -lh /var/log/email-campaign-manager.log

echo "=== Active Connections ==="
netstat -an | grep :5000 | wc -l
EOF

chmod +x monitor_performance.sh

# 10. Create cleanup script
echo "🧹 Creating cleanup script..."
cat > cleanup_logs.sh << 'EOF'
#!/bin/bash

echo "Cleaning up old logs and cache..."
sudo journalctl --vacuum-time=7d
sudo find /var/log -name "*.log" -mtime +7 -delete
sudo find /home/emailcampaign/email-campaign-manager -name "*.log" -mtime +7 -delete

# Clear Python cache
find /home/emailcampaign/email-campaign-manager -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find /home/emailcampaign/email-campaign-manager -name "*.pyc" -delete

echo "Cleanup completed!"
EOF

chmod +x cleanup_logs.sh

# 11. Set up cron jobs for maintenance
echo "⏰ Setting up maintenance cron jobs..."
(crontab -l 2>/dev/null; echo "0 2 * * * /home/emailcampaign/email-campaign-manager/cleanup_logs.sh") | crontab -
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/emailcampaign/email-campaign-manager/monitor_performance.sh >> /home/emailcampaign/performance.log 2>&1") | crontab -

echo "✅ Performance optimization completed!"
echo ""
echo "📋 Summary of optimizations:"
echo "- Increased file descriptor limits"
echo "- Optimized kernel parameters"
echo "- Configured Gunicorn with 4 workers and gevent"
echo "- Optimized Nginx with gzip compression"
echo "- Set up log rotation and cleanup"
echo "- Added performance monitoring"
echo ""
echo "🔄 Restarting application..."
sudo systemctl restart email-campaign-manager
sudo systemctl status email-campaign-manager

echo ""
echo "🎯 Performance should be significantly improved!"
echo "📊 Monitor performance with: ./monitor_performance.sh"
echo "🧹 Clean up logs with: ./cleanup_logs.sh" 