#!/bin/bash

# Email Campaign Manager - Complete Automated Deployment Script
# Handles everything: initial setup, updates, and maintenance
# Run as: sudo ./deploy.sh [setup|update|status|restart]

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root: sudo ./deploy.sh"
   exit 1
fi

# Get server IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")

# Function to setup everything from scratch
setup_application() {
    print_header "SETTING UP EMAIL CAMPAIGN MANAGER FROM SCRATCH"
    
    print_status "Updating system packages..."
    apt update && apt upgrade -y
    
    print_status "Installing required packages..."
    apt install -y python3 python3-pip python3-venv nginx git curl wget unzip
    apt install -y build-essential python3-dev libpq-dev
    
    print_status "Configuring firewall..."
    ufw allow ssh
    ufw allow 'Nginx Full'
    ufw --force enable
    
    print_status "Creating application user..."
    if ! id "emailcampaign" &>/dev/null; then
        adduser --disabled-password --gecos "" emailcampaign
        usermod -aG sudo emailcampaign
        print_status "User 'emailcampaign' created successfully"
    else
        print_warning "User 'emailcampaign' already exists"
    fi
    
    print_status "Creating application directories..."
    mkdir -p /var/log/email-campaign-manager
    mkdir -p /var/run/email-campaign-manager
    chown emailcampaign:emailcampaign /var/log/email-campaign-manager
    chown emailcampaign:emailcampaign /var/run/email-campaign-manager
    
    print_status "Setting up application..."
    sudo -u emailcampaign bash << 'EOF'
cd /home/emailcampaign

# Clone repository
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
    
    print_status "Creating Nginx configuration..."
    cat > /etc/nginx/sites-available/email-campaign-manager << 'EOF'
server {
    listen 80;
    server_name _;
    
    client_max_body_size 50M;
    
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private must-revalidate auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/javascript;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /static/ {
        alias /home/emailcampaign/email-campaign-manager/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    location ~ /\. {
        deny all;
    }
    
    location ~ \.(py|pyc|log|json)$ {
        deny all;
    }
}
EOF
    
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

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/emailcampaign/email-campaign-manager
ReadWritePaths=/var/log/email-campaign-manager
ReadWritePaths=/var/run/email-campaign-manager

[Install]
WantedBy=multi-user.target
EOF
    
    print_status "Configuring Nginx..."
    ln -sf /etc/nginx/sites-available/email-campaign-manager /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    
    print_status "Starting services..."
    systemctl daemon-reload
    systemctl enable email-campaign-manager
    systemctl start email-campaign-manager
    systemctl restart nginx
    
    print_status "Setup completed successfully!"
    show_access_info
}

# Function to update the application
update_application() {
    print_header "UPDATING EMAIL CAMPAIGN MANAGER"
    
    print_status "Pulling latest changes from GitHub..."
    sudo -u emailcampaign bash << 'EOF'
cd /home/emailcampaign/email-campaign-manager
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
deactivate
EOF
    
    print_status "Restarting application..."
    systemctl restart email-campaign-manager
    
    print_status "Update completed successfully!"
    show_status
}

# Function to show application status
show_status() {
    print_header "APPLICATION STATUS"
    
    echo "📊 Service Status:"
    systemctl status email-campaign-manager --no-pager
    
    echo ""
    echo "🌐 Nginx Status:"
    systemctl status nginx --no-pager
    
    echo ""
    echo "🔍 Port Status:"
    netstat -tlnp | grep -E ':(80|8000)' || echo "No services listening on ports 80/8000"
    
    show_access_info
}

# Function to restart services
restart_services() {
    print_header "RESTARTING SERVICES"
    
    print_status "Restarting application..."
    systemctl restart email-campaign-manager
    
    print_status "Restarting Nginx..."
    systemctl restart nginx
    
    print_status "Services restarted successfully!"
    show_status
}

# Function to show access information
show_access_info() {
    echo ""
    print_status "Your Email Campaign Manager is accessible at:"
    echo "  🌐 Direct Application: http://$SERVER_IP:8000"
    echo "  🌐 Through Nginx: http://$SERVER_IP"
    echo ""
    print_status "Useful commands:"
    echo "  📝 View logs: sudo journalctl -u email-campaign-manager -f"
    echo "  🔄 Update: sudo ./deploy.sh update"
    echo "  📊 Status: sudo ./deploy.sh status"
    echo "  🔄 Restart: sudo ./deploy.sh restart"
}

# Function to show help
show_help() {
    echo "Email Campaign Manager - Deployment Script"
    echo ""
    echo "Usage: sudo ./deploy.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup    - Complete initial setup (first time only)"
    echo "  update   - Update application from GitHub"
    echo "  status   - Show application status"
    echo "  restart  - Restart all services"
    echo "  help     - Show this help message"
    echo ""
    echo "Examples:"
    echo "  sudo ./deploy.sh setup    # First time setup"
    echo "  sudo ./deploy.sh update   # Update from GitHub"
    echo "  sudo ./deploy.sh status   # Check status"
}

# Main script logic
case "${1:-help}" in
    "setup")
        setup_application
        ;;
    "update")
        update_application
        ;;
    "status")
        show_status
        ;;
    "restart")
        restart_services
        ;;
    "help"|*)
        show_help
        ;;
esac 