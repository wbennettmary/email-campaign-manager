#!/bin/bash

# Email Campaign Manager - Ubuntu Server Deployment Script
# Run this script as root on a fresh Ubuntu 22.04 LTS server

set -e  # Exit on any error

echo "🚀 Starting Email Campaign Manager Deployment..."

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

# Update system
print_status "Updating system packages..."
apt update && apt upgrade -y

# Install required packages
print_status "Installing required packages..."
apt install -y python3 python3-pip python3-venv nginx git curl wget unzip
apt install -y build-essential python3-dev libpq-dev certbot python3-certbot-nginx

# Configure firewall
print_status "Configuring firewall..."
ufw allow ssh
ufw allow 'Nginx Full'
ufw --force enable

# Create application user
print_status "Creating application user..."
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
mkdir -p data_lists
mkdir -p logs

print_status "Application setup completed"
EOF

# Copy configuration files
print_status "Installing configuration files..."

# Copy systemd service
cp email-campaign-manager.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable email-campaign-manager

# Copy Nginx configuration
cp nginx.conf /etc/nginx/sites-available/email-campaign-manager
ln -sf /etc/nginx/sites-available/email-campaign-manager /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Start services
print_status "Starting services..."
systemctl start email-campaign-manager
systemctl restart nginx

# Check service status
print_status "Checking service status..."
systemctl status email-campaign-manager --no-pager
systemctl status nginx --no-pager

print_status "Deployment completed successfully!"
print_warning "Next steps:"
echo "1. Update the domain name in /etc/nginx/sites-available/email-campaign-manager"
echo "2. Run: sudo certbot --nginx -d your-domain.com"
echo "3. Access your application at: https://your-domain.com"
echo ""
print_status "Useful commands:"
echo "- Check logs: sudo journalctl -u email-campaign-manager -f"
echo "- Restart app: sudo systemctl restart email-campaign-manager"
echo "- Check status: sudo systemctl status email-campaign-manager" 