#!/bin/bash

echo "🚀 Email Campaign Manager - Low Memory Server Optimization"
echo "=========================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as emailcampaign user
if [[ $EUID -eq 0 ]]; then
    print_error "This script should not be run as root. Please run as emailcampaign user."
    exit 1
fi

# Navigate to application directory
cd /home/emailcampaign/email-campaign-manager

print_status "Current directory: $(pwd)"
print_status "Current user: $(whoami)"

# Stop current service
print_status "Stopping current service..."
sudo systemctl stop email-campaign-manager

# Install psutil if not already installed
print_status "Installing psutil for memory monitoring..."
pip3 install psutil==5.9.5

# Run the optimization script
print_status "Running server optimization script..."
python3 optimize_server.py

# Install optimized service
print_status "Installing optimized service..."
sudo cp email-campaign-manager-optimized.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-campaign-manager-optimized

# Start optimized service
print_status "Starting optimized service..."
sudo systemctl start email-campaign-manager-optimized

# Wait for service to start
sleep 5

# Check service status
print_status "Checking service status..."
if sudo systemctl is-active --quiet email-campaign-manager-optimized; then
    print_success "✅ Optimized service is running"
else
    print_error "❌ Optimized service failed to start"
    print_status "Service logs:"
    sudo journalctl -u email-campaign-manager-optimized --no-pager -n 10
    exit 1
fi

# Test application
print_status "Testing application..."
if curl -s http://localhost:8000 > /dev/null; then
    print_success "✅ Application is responding"
else
    print_warning "⚠️ Application not responding on localhost:8000"
fi

# Start memory monitor in background
print_status "Starting memory monitor..."
nohup python3 memory_monitor.py > memory_monitor.log 2>&1 &
print_success "✅ Memory monitor started in background"

# Set up performance monitoring
print_status "Setting up performance monitoring..."
chmod +x check_performance.sh

# Create cron job for performance monitoring (every 10 minutes)
(crontab -l 2>/dev/null; echo "*/10 * * * * /home/emailcampaign/email-campaign-manager/check_performance.sh >> /home/emailcampaign/email-campaign-manager/performance.log 2>&1") | crontab -

print_success "✅ Performance monitoring scheduled"

# Show current memory usage
print_status "Current system memory usage:"
free -h

print_success "🎉 Server optimization completed!"
echo ""
print_status "📋 What was optimized:"
echo "✅ Reduced Gunicorn workers to 1 (single worker for low memory)"
echo "✅ Added memory limits and monitoring"
echo "✅ Optimized JSON file handling"
echo "✅ Added automatic garbage collection"
echo "✅ Created performance monitoring scripts"
echo "✅ Set up memory monitoring"
echo ""
print_status "📊 Monitor your application:"
echo "• Check performance: ./check_performance.sh"
echo "• View memory monitor logs: tail -f memory_monitor.log"
echo "• View performance logs: tail -f performance.log"
echo "• Check service status: sudo systemctl status email-campaign-manager-optimized"
echo ""
print_status "🔧 If you need to restart the service:"
echo "sudo systemctl restart email-campaign-manager-optimized"