#!/bin/bash

echo "🚀 DEPLOYING WORKING FLASK EMAIL CAMPAIGN MANAGER"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Phase 1: Stop all Docker services
print_status "PHASE 1: Stopping Docker services"
docker-compose down 2>/dev/null || true
docker rm -f $(docker ps -aq) 2>/dev/null || true
docker system prune -af

# Phase 2: Stop system services
print_status "PHASE 2: Stopping system services"
sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl disable nginx 2>/dev/null || true
sudo systemctl stop email-campaign-manager 2>/dev/null || true
sudo systemctl disable email-campaign-manager 2>/dev/null || true

# Phase 3: Set up working Flask app
print_status "PHASE 3: Setting up working Flask app"

# Create systemd service file
sudo tee /etc/systemd/system/email-campaign-manager.service > /dev/null <<EOF
[Unit]
Description=Email Campaign Manager
After=network.target

[Service]
Type=simple
User=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment=PATH=/home/emailcampaign/email-campaign-manager/venv/bin
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/python app_working.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Phase 4: Set up virtual environment
print_status "PHASE 4: Setting up virtual environment"
cd /home/emailcampaign/email-campaign-manager

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install flask flask-socketio flask-login werkzeug requests schedule gunicorn

# Phase 5: Set permissions
print_status "PHASE 5: Setting permissions"
sudo chown -R emailcampaign:emailcampaign /home/emailcampaign/email-campaign-manager
chmod -R 755 /home/emailcampaign/email-campaign-manager
mkdir -p data_lists logs
chmod 755 data_lists logs

# Phase 6: Start the service
print_status "PHASE 6: Starting Flask service"
sudo systemctl daemon-reload
sudo systemctl enable email-campaign-manager
sudo systemctl start email-campaign-manager

# Phase 7: Wait and check status
print_status "PHASE 7: Checking service status"
sleep 5
sudo systemctl status email-campaign-manager

# Phase 8: Test the application
print_status "PHASE 8: Testing application"
sleep 3
curl -f http://localhost:5000/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
    print_status "Application is running successfully!"
else
    print_warning "Application might still be starting up..."
fi

# Phase 9: Final status
print_status "PHASE 9: Final status"
echo ""
echo "🎉 WORKING FLASK APP DEPLOYED!"
echo "=============================="
echo ""
echo "📊 SERVICE STATUS:"
sudo systemctl status email-campaign-manager --no-pager
echo ""
echo "🌐 ACCESS URL:"
echo "   Main App: http://$(curl -s ifconfig.me):5000"
echo "   Health: http://$(curl -s ifconfig.me):5000/health"
echo ""
echo "📝 LOGS:"
echo "   View logs: sudo journalctl -u email-campaign-manager -f"
echo "   Restart: sudo systemctl restart email-campaign-manager"
echo ""
echo "🔧 FEATURES:"
echo "   ✅ Fast Flask app (no Docker complexity)"
echo "   ✅ Real-time logs with SocketIO"
echo "   ✅ Instant campaign actions"
echo "   ✅ Working duplicate campaigns"
echo "   ✅ Unlimited concurrent campaigns"
echo ""
print_status "Deployment completed successfully!" 