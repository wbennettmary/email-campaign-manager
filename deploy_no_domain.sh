#!/bin/bash

# Email Campaign Manager - No Domain Deployment Script
# Run this script as root on Ubuntu server

set -e  # Exit on any error

echo "🚀 Starting Email Campaign Manager Deployment (No Domain)..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root"
   exit 1
fi

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)
print_status "Detected server IP: $SERVER_IP"

# Update system
print_status "Updating system packages..."
apt update && apt upgrade -y

# Install required packages
print_status "Installing required packages..."
apt install -y python3 python3-pip python3-venv nginx git curl wget unzip
apt install -y build-essential python3-dev libpq-dev

# Configure firewall
print_status "Configuring firewall..."
ufw allow ssh
ufw allow 'Nginx Full'
ufw --force enable

# Create application user if not exists
print_status "Setting up application user..."
if ! id "emailcampaign" &>/dev/null; then
    adduser --disabled-password --gecos "" emailcampaign
    usermod -aG sudo emailcampaign
    print_status "User 'emailcampaign' created successfully"
else
    print_warning "User 'emailcampaign' already exists"
fi

# Create necessary directories
print_status "Creating application directories..."
mkdir -p /var/log/email-campaign-manager
mkdir -p /var/run/email-campaign-manager
chown emailcampaign:emailcampaign /var/log/email-campaign-manager
chown emailcampaign:emailcampaign /var/run/email-campaign-manager

# Switch to application user and setup application
print_status "Setting up application..."
sudo -u emailcampaign bash << 'EOF'
cd /home/emailcampaign

# Clone repository if not exists
if [ ! -d "email-campaign-manager" ]; then
    git clone https://github.com/wbennettmary/email-campaign-manager.git
    cd email-campaign-manager
else
    cd email-campaign-manager
    git pull origin master
fi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Create data directories
mkdir -p data_lists logs

print_status "Application setup completed"
EOF

# Create Nginx configuration for no domain
print_status "Creating Nginx configuration..."
cat > /etc/nginx/sites-available/email-campaign-manager << 'EOF'
server {
    listen 80;
    server_name _;  # Accepts any hostname/IP
    
    # Client max body size for file uploads
    client_max_body_size 50M;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private must-revalidate auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/javascript;
    
    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Static files (if needed)
    location /static/ {
        alias /home/emailcampaign/email-campaign-manager/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Deny access to sensitive files
    location ~ /\. {
        deny all;
    }
    
    location ~ \.(py|pyc|log|json)$ {
        deny all;
    }
}
EOF

# Create systemd service file
print_status "Creating systemd service..."
cat > /etc/systemd/system/email-campaign-manager.service << 'EOF'
[Unit]
Description=Email Campaign Manager
After=network.target

[Service]
Type=notify
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment="PATH=/home/emailcampaign/email-campaign-manager/venv/bin"
Environment="FLASK_ENV=production"
Environment="FLASK_APP=app.py"
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn --config gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/emailcampaign/email-campaign-manager
ReadWritePaths=/var/log/email-campaign-manager
ReadWritePaths=/var/run/email-campaign-manager

[Install]
WantedBy=multi-user.target
EOF

# Enable Nginx site
print_status "Configuring Nginx..."
ln -sf /etc/nginx/sites-available/email-campaign-manager /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Reload systemd and start services
print_status "Starting services..."
systemctl daemon-reload
systemctl enable email-campaign-manager
systemctl start email-campaign-manager
systemctl restart nginx

# Check service status
print_status "Checking service status..."
sleep 3
systemctl status email-campaign-manager --no-pager
systemctl status nginx --no-pager

# Test application
print_status "Testing application..."
sleep 2
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200\|302"; then
    print_status "Application is running successfully!"
else
    print_warning "Application might not be fully started yet. Please wait a moment and check manually."
fi

print_status "Deployment completed successfully!"
echo ""
print_status "Your Email Campaign Manager is now accessible at:"
echo "  🌐 Direct Application: http://$SERVER_IP:8000"
echo "  🌐 Through Nginx: http://$SERVER_IP"
echo ""
print_status "Useful commands:"
echo "- Check logs: sudo journalctl -u email-campaign-manager -f"
echo "- Restart app: sudo systemctl restart email-campaign-manager"
echo "- Check status: sudo systemctl status email-campaign-manager"
echo "- View Nginx logs: sudo tail -f /var/log/nginx/error.log"
echo ""
print_warning "Note: This setup uses HTTP only (no SSL). For production use, consider adding SSL later." 