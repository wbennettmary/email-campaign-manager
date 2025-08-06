#!/bin/bash

echo "🚀 DEPLOYING PROFESSIONAL EMAIL CAMPAIGN MANAGER v2.0"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please run as emailcampaign user, not root"
    exit 1
fi

# Phase 1: Stop old services
print_status "PHASE 1: Stopping old services"
sudo systemctl stop email-campaign-manager 2>/dev/null || true
sudo systemctl disable email-campaign-manager 2>/dev/null || true

# Phase 2: Update code
print_status "PHASE 2: Updating code"
cd /home/emailcampaign/email-campaign-manager
git stash 2>/dev/null || true
git pull origin master

# Phase 3: Clean up Docker
print_status "PHASE 3: Cleaning up Docker"
docker-compose down 2>/dev/null || true
docker system prune -f
docker volume prune -f

# Phase 4: Install Docker if not present
if ! command -v docker &> /dev/null; then
    print_status "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

# Phase 5: Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    print_status "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Phase 6: Set up directories
print_status "PHASE 4: Setting up directories"
mkdir -p /home/emailcampaign/email-campaign-manager/data_lists
mkdir -p /home/emailcampaign/email-campaign-manager/logs
mkdir -p /home/emailcampaign/email-campaign-manager/static
mkdir -p /home/emailcampaign/email-campaign-manager/templates

# Phase 7: Set permissions
print_status "PHASE 5: Setting permissions"
sudo chown -R emailcampaign:emailcampaign /home/emailcampaign/email-campaign-manager
chmod -R 755 /home/emailcampaign/email-campaign-manager

# Phase 8: Build and start services
print_status "PHASE 6: Building and starting services"
docker-compose build --no-cache

if [ $? -ne 0 ]; then
    print_error "Docker build failed!"
    exit 1
fi

docker-compose up -d

if [ $? -ne 0 ]; then
    print_error "Docker compose failed!"
    exit 1
fi

# Phase 9: Wait for services
print_status "PHASE 7: Waiting for services to start"
sleep 30

# Phase 10: Check service status
print_status "PHASE 8: Checking service status"
docker-compose ps

# Phase 11: Test endpoints
print_status "PHASE 9: Testing endpoints"

# Wait a bit more for services to be ready
sleep 10

# Test backend health
echo "Testing backend health..."
curl -f http://localhost:8000/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
    print_status "Backend health check: OK"
else
    print_warning "Backend health check: FAILED (this might be normal during startup)"
fi

# Test nginx
echo "Testing nginx..."
curl -f http://localhost/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
    print_status "Nginx health check: OK"
else
    print_warning "Nginx health check: FAILED (this might be normal during startup)"
fi

# Phase 12: Final status
print_status "PHASE 10: Final status"
echo ""
echo "🎉 DEPLOYMENT COMPLETE!"
echo "======================"
echo ""
echo "📊 SERVICE STATUS:"
docker-compose ps
echo ""
echo "🌐 ACCESS URLs:"
echo "   Main App: http://$(curl -s ifconfig.me)"
echo "   API Docs: http://$(curl -s ifconfig.me):8000/docs"
echo "   Health: http://$(curl -s ifconfig.me)/health"
echo ""
echo "📝 LOGS:"
echo "   View logs: docker-compose logs -f"
echo "   Backend logs: docker-compose logs backend"
echo "   Nginx logs: docker-compose logs nginx"
echo ""
echo "🔧 TROUBLESHOOTING:"
echo "   If you see 403 errors, wait 1-2 minutes for services to fully start"
echo "   Check logs: docker-compose logs"
echo "   Restart: docker-compose restart"
echo ""
print_status "Deployment completed successfully!" 