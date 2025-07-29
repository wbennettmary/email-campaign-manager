#!/bin/bash

echo "🚀 Email Campaign Manager - Server Setup & Fix Script"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as emailcampaign user."
   exit 1
fi

# Navigate to the application directory
cd /home/emailcampaign/email-campaign-manager

print_status "Current directory: $(pwd)"

# Stop the application service first
print_status "Stopping application service..."
sudo systemctl stop email-campaign-manager

# Fix ownership - ensure all files belong to emailcampaign user
print_status "Setting correct file ownership..."
sudo chown -R emailcampaign:emailcampaign .

# Set correct permissions for directories
print_status "Setting directory permissions..."
find . -type d -exec chmod 755 {} \;

# Set correct permissions for files
print_status "Setting file permissions..."
find . -type f -exec chmod 644 {} \;

# Make scripts executable
print_status "Making scripts executable..."
chmod +x *.sh

# Set specific permissions for JSON data files (readable and writable by owner and group)
print_status "Setting JSON data file permissions..."
chmod 664 *.json

# Check if JSON files exist and create them if they don't
print_status "Checking and initializing JSON data files..."

# Initialize accounts.json if it doesn't exist
if [ ! -f "accounts.json" ]; then
    print_warning "accounts.json not found, creating empty file..."
    echo "[]" > accounts.json
    chmod 664 accounts.json
fi

# Initialize campaigns.json if it doesn't exist
if [ ! -f "campaigns.json" ]; then
    print_warning "campaigns.json not found, creating empty file..."
    echo "[]" > campaigns.json
    chmod 664 campaigns.json
fi

# Initialize users.json if it doesn't exist
if [ ! -f "users.json" ]; then
    print_warning "users.json not found, creating with admin user..."
    echo '[
  {
    "id": 1,
    "username": "admin",
    "password_hash": "pbkdf2:sha256:600000$admin$your-hashed-password-here",
    "role": "admin",
    "permissions": ["add_account", "manage_accounts", "view_all_campaigns", "manage_data"],
    "is_active": true,
    "created_at": "2024-01-01T00:00:00"
  }
]' > users.json
    chmod 664 users.json
fi

# Initialize other JSON files
for file in notifications.json campaign_logs.json bounces.json rate_limit_config.json; do
    if [ ! -f "$file" ]; then
        print_warning "$file not found, creating empty file..."
        echo "{}" > "$file"
        chmod 664 "$file"
    fi
done

# Check the current permissions
print_status "Current file permissions:"
ls -la *.json

# Test file write permissions
print_status "Testing file write permissions..."
echo '{"test": "permission_test"}' > test_permission.json
if [ $? -eq 0 ]; then
    print_success "File write permission test passed"
    rm test_permission.json
else
    print_error "File write permission test failed"
    exit 1
fi

# Restart the application service
print_status "Restarting the application service..."
sudo systemctl restart email-campaign-manager

# Wait a moment for the service to start
sleep 3

# Check service status
print_status "Checking service status..."
if sudo systemctl is-active --quiet email-campaign-manager; then
    print_success "Application service is running"
else
    print_error "Application service failed to start"
    print_status "Checking service logs..."
    sudo journalctl -u email-campaign-manager --no-pager -n 20
    exit 1
fi

# Check service logs for any errors
print_status "Checking recent service logs..."
sudo journalctl -u email-campaign-manager --no-pager -n 10

# Test the application
print_status "Testing application connectivity..."
if curl -s http://localhost:8000 > /dev/null; then
    print_success "Application is responding on localhost:8000"
else
    print_warning "Application is not responding on localhost:8000 (this might be normal if nginx is configured)"
fi

# Check nginx status
print_status "Checking nginx status..."
if sudo systemctl is-active --quiet nginx; then
    print_success "Nginx is running"
    if curl -s http://localhost > /dev/null; then
        print_success "Application is accessible via nginx"
    else
        print_warning "Application is not accessible via nginx (check nginx configuration)"
    fi
else
    print_warning "Nginx is not running"
fi

echo ""
print_success "Server setup completed successfully!"
echo ""
print_status "Next steps:"
echo "1. Test account creation and deletion in the web interface"
echo "2. Check that users with 'add_account' permission can manage their own accounts"
echo "3. Verify that admin can manage all accounts"
echo "4. Monitor the application logs for any issues"
echo ""
print_status "If you encounter any issues, check the logs with:"
echo "sudo journalctl -u email-campaign-manager -f"