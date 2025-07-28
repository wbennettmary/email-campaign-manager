#!/bin/bash

# Email Campaign Manager - Update Script
# Run this script to update the application from GitHub

set -e  # Exit on any error

echo "🔄 Starting Email Campaign Manager Update..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as emailcampaign user
if [[ $EUID -eq 0 ]]; then
   print_warning "Running as root, switching to emailcampaign user..."
   sudo -u emailcampaign bash -c "$0"
   exit 0
fi

# Go to application directory
cd /home/emailcampaign/email-campaign-manager

print_status "Pulling latest changes from GitHub..."
git pull origin master

print_status "Activating virtual environment..."
source venv/bin/activate

print_status "Installing/updating dependencies..."
pip install -r requirements.txt

print_status "Deactivating virtual environment..."
deactivate

print_status "Restarting application service..."
sudo systemctl restart email-campaign-manager

print_status "Checking service status..."
sleep 2
sudo systemctl status email-campaign-manager --no-pager

print_status "Update completed successfully!"
print_status "Your application is now running the latest version from GitHub." 