#!/bin/bash

# Email Campaign Manager - Complete Automated Installation & Management Script
# This script handles everything: installation, updates, status, and maintenance
# Run as: sudo ./auto_install.sh [install|update|status|restart|logs]

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
   print_error "This script must be run as root: sudo ./auto_install.sh"
   exit 1
fi

# Get server IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")

# Function to install everything from scratch
install_application() {
    print_header "EMAIL CAMPAIGN MANAGER - COMPLETE INSTALLATION"
    echo "This script will install everything automatically on your fresh server."
    echo "Server IP: $SERVER_IP"
    echo ""
    
    # Step 1: Update system and install packages
    print_header "STEP 1: UPDATING SYSTEM AND INSTALLING PACKAGES"
    print_status "Updating system packages..."
    apt update && apt upgrade -y
    
    print_status "Installing required packages..."
    apt install -y python3 python3-pip python3-venv nginx git curl wget unzip
    apt install -y build-essential python3-dev libpq-dev
    
    # Step 2: Configure firewall
    print_header "STEP 2: CONFIGURING FIREWALL"
    print_status "Configuring firewall..."
    ufw allow ssh
    ufw allow 'Nginx Full'
    ufw --force enable
    
    # Step 3: Create application user
    print_header "STEP 3: CREATING APPLICATION USER"
    print_status "Creating application user..."
    if ! id "emailcampaign" &>/dev/null; then
        adduser --disabled-password --gecos "" emailcampaign
        usermod -aG sudo emailcampaign
        print_status "User 'emailcampaign' created successfully"
    else
        print_warning "User 'emailcampaign' already exists"
    fi
    
    # Step 4: Create application directories
    print_header "STEP 4: CREATING APPLICATION DIRECTORIES"
    print_status "Creating application directories..."
    mkdir -p /var/log/email-campaign-manager
    mkdir -p /var/run/email-campaign-manager
    chown emailcampaign:emailcampaign /var/log/email-campaign-manager
    chown emailcampaign:emailcampaign /var/run/email-campaign-manager
    
    # Step 5: Deploy application
    print_header "STEP 5: DEPLOYING APPLICATION"
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

# Install dependencies with specific versions to avoid compatibility issues
pip install --upgrade pip
pip install Flask==2.3.3
pip install Flask-SocketIO==5.3.6
pip install Flask-Login==0.6.3
pip install Werkzeug==2.3.7
pip install requests==2.31.0
pip install python-socketio==5.8.0
pip install python-engineio==4.7.1
pip install numpy==1.24.3
pip install pandas==2.0.3
pip install gunicorn==21.2.0

# Create data directories
mkdir -p data_lists logs

echo "Application setup completed"
EOF
    
    # Step 6: Create Nginx configuration
    print_header "STEP 6: CREATING NGINX CONFIGURATION"
    print_status "Creating Nginx configuration..."
    cat > /etc/nginx/sites-available/email-campaign-manager << 'EOF'
server {
    listen 80;
    server_name _;
    
    client_max_body_size 50M;
    
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
}
EOF
    
    # Step 7: Create systemd service
    print_header "STEP 7: CREATING SYSTEMD SERVICE"
    print_status "Creating systemd service..."
    cat > /etc/systemd/system/email-campaign-manager.service << 'EOF'
[Unit]
Description=Email Campaign Manager
After=network.target

[Service]
Type=simple
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment="PATH=/home/emailcampaign/email-campaign-manager/venv/bin"
Environment="FLASK_ENV=production"
Environment="FLASK_APP=app.py"
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 2 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Step 8: Configure Nginx
    print_header "STEP 8: CONFIGURING NGINX"
    print_status "Configuring Nginx..."
    ln -sf /etc/nginx/sites-available/email-campaign-manager /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    
    # Step 9: Start services
    print_header "STEP 9: STARTING SERVICES"
    print_status "Starting application service..."
    systemctl daemon-reload
    systemctl enable email-campaign-manager
    systemctl start email-campaign-manager
    
    print_status "Starting Nginx..."
    systemctl restart nginx
    
    # Step 10: Wait for services to start
    print_header "STEP 10: WAITING FOR SERVICES TO START"
    print_status "Waiting for services to start..."
    sleep 10
    
    # Step 11: Verify installation
    print_header "STEP 11: VERIFYING INSTALLATION"
    print_status "Checking service status..."
    
    # Check application service
    if systemctl is-active --quiet email-campaign-manager; then
        print_status "✅ Application service is running"
    else
        print_error "❌ Application service failed to start"
        print_status "Checking logs for errors..."
        journalctl -u email-campaign-manager --no-pager -n 20
        exit 1
    fi
    
    # Check Nginx service
    if systemctl is-active --quiet nginx; then
        print_status "✅ Nginx service is running"
    else
        print_error "❌ Nginx service failed to start"
        systemctl status nginx --no-pager
        exit 1
    fi
    
    # Check if port 8000 is listening
    if netstat -tlnp | grep -q ":8000"; then
        print_status "✅ Application is listening on port 8000"
    else
        print_error "❌ Application is not listening on port 8000"
        exit 1
    fi
    
    # Check if port 80 is listening
    if netstat -tlnp | grep -q ":80"; then
        print_status "✅ Nginx is listening on port 80"
    else
        print_error "❌ Nginx is not listening on port 80"
        exit 1
    fi
    
    # Test application response
    print_status "Testing application response..."
    if curl -s http://127.0.0.1:8000 > /dev/null; then
        print_status "✅ Application is responding"
    else
        print_error "❌ Application is not responding"
        print_status "Checking application logs..."
        journalctl -u email-campaign-manager --no-pager -n 10
        exit 1
    fi
    
    # Step 12: Final verification
    print_header "STEP 12: FINAL VERIFICATION"
    print_status "Testing external access..."
    if curl -s http://$SERVER_IP > /dev/null; then
        print_status "✅ External access is working"
    else
        print_warning "⚠️  External access test failed (this might be normal if firewall is blocking)"
    fi
    
    # Step 13: Installation complete
    print_header "🎉 INSTALLATION COMPLETE!"
    echo ""
    print_status "Your Email Campaign Manager is now running!"
    echo ""
    echo "🌐 Access URLs:"
    echo "  Direct Application: http://$SERVER_IP:8000"
    echo "  Through Nginx: http://$SERVER_IP"
    echo ""
    echo "📊 Service Status:"
    systemctl status email-campaign-manager --no-pager | head -10
    echo ""
    echo "🔧 Useful Commands:"
    echo "  View logs: sudo ./auto_install.sh logs"
    echo "  Check status: sudo ./auto_install.sh status"
    echo "  Restart services: sudo ./auto_install.sh restart"
    echo "  Update application: sudo ./auto_install.sh update"
    echo ""
    print_status "Installation completed successfully! You can now access your Email Campaign Manager."
}

# Function to update the application
update_application() {
    print_header "UPDATING EMAIL CAMPAIGN MANAGER"
    
    print_status "Pulling latest changes from GitHub..."
    sudo -u emailcampaign bash << 'EOF'
cd /home/emailcampaign/email-campaign-manager
git pull origin master
source venv/bin/activate

# Update dependencies with specific versions to avoid compatibility issues
pip install --upgrade pip
pip install Flask==2.3.3
pip install Flask-SocketIO==5.3.6
pip install Flask-Login==0.6.3
pip install Werkzeug==2.3.7
pip install requests==2.31.0
pip install python-socketio==5.8.0
pip install python-engineio==4.7.1
pip install numpy==1.24.3
pip install pandas==2.0.3
pip install gunicorn==21.2.0

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
    
    echo ""
    echo "🌐 Access URLs:"
    echo "  Direct Application: http://$SERVER_IP:8000"
    echo "  Through Nginx: http://$SERVER_IP"
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

# Function to view logs
view_logs() {
    print_header "VIEWING LOGS"
    echo "Choose log type:"
    echo "1) Application logs (follow)"
    echo "2) Application logs (last 50 lines)"
    echo "3) Nginx access logs"
    echo "4) Nginx error logs"
    echo "5) System logs"
    read -p "Enter choice (1-5): " log_choice
    
    case $log_choice in
        1)
            journalctl -u email-campaign-manager -f
            ;;
        2)
            journalctl -u email-campaign-manager --no-pager -n 50
            ;;
        3)
            tail -f /var/log/nginx/access.log
            ;;
        4)
            tail -f /var/log/nginx/error.log
            ;;
        5)
            journalctl -u email-campaign-manager --no-pager -n 100
            ;;
        *)
            echo "Invalid choice"
            ;;
    esac
}

# Function to show help
show_help() {
    echo "Email Campaign Manager - Complete Management Script"
    echo ""
    echo "Usage: sudo ./auto_install.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  install  - Complete initial installation (first time only)"
    echo "  update   - Update application from GitHub"
    echo "  status   - Show application status"
    echo "  restart  - Restart all services"
    echo "  logs     - View application logs"
    echo "  help     - Show this help message"
    echo ""
    echo "Examples:"
    echo "  sudo ./auto_install.sh install  # First time installation"
    echo "  sudo ./auto_install.sh update   # Update from GitHub"
    echo "  sudo ./auto_install.sh status   # Check status"
    echo "  sudo ./auto_install.sh logs     # View logs"
    echo ""
    echo "If no command is provided, 'install' will be run by default."
}

# Main script logic
case "${1:-install}" in
    "install")
        install_application
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
    "logs")
        view_logs
        ;;
    "help"|*)
        show_help
        ;;
esac 