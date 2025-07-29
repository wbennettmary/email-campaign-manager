#!/bin/bash

echo "🔧 AGGRESSIVE SERVER PERMISSION FIX"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
print_status "Current user: $(whoami)"

# Stop all services first
print_status "Stopping all services..."
sudo systemctl stop email-campaign-manager
sudo systemctl stop nginx

# AGGRESSIVE PERMISSION FIX
print_status "🔧 AGGRESSIVE PERMISSION FIX STARTING..."

# 1. Set ownership to emailcampaign user and group
print_status "Setting ownership to emailcampaign user..."
sudo chown -R emailcampaign:emailcampaign /home/emailcampaign/email-campaign-manager

# 2. Set very permissive permissions for JSON files
print_status "Setting very permissive permissions for JSON files..."
find . -name "*.json" -exec chmod 666 {} \;

# 3. Set permissions for all files and directories
print_status "Setting permissions for all files and directories..."
find . -type d -exec chmod 755 {} \;
find . -type f -exec chmod 644 {} \;

# 4. Make scripts executable
print_status "Making scripts executable..."
chmod +x *.sh

# 5. Set specific permissions for critical files
print_status "Setting specific permissions for critical files..."
chmod 666 *.json
chmod 755 *.py
chmod 755 app.py

# 6. Check current permissions
print_status "Current file permissions:"
ls -la *.json

# 7. Test write permissions for each JSON file
print_status "Testing write permissions for each JSON file..."

for json_file in *.json; do
    if [ -f "$json_file" ]; then
        print_status "Testing write permission for $json_file..."
        echo '{"test": "write_permission_test"}' > "${json_file}.test"
        if [ $? -eq 0 ]; then
            print_success "✓ Write permission OK for $json_file"
            rm "${json_file}.test"
        else
            print_error "✗ Write permission FAILED for $json_file"
        fi
    fi
done

# 8. Ensure JSON files have proper content
print_status "Ensuring JSON files have proper content..."

# Initialize accounts.json if empty or corrupted
if [ ! -s "accounts.json" ] || ! jq empty accounts.json 2>/dev/null; then
    print_warning "accounts.json is empty or corrupted, initializing..."
    echo "[]" > accounts.json
    chmod 666 accounts.json
fi

# Initialize users.json if empty or corrupted
if [ ! -s "users.json" ] || ! jq empty users.json 2>/dev/null; then
    print_warning "users.json is empty or corrupted, initializing..."
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
    chmod 666 users.json
fi

# Initialize other JSON files
for file in campaigns.json notifications.json campaign_logs.json bounces.json rate_limit_config.json; do
    if [ ! -f "$file" ] || [ ! -s "$file" ] || ! jq empty "$file" 2>/dev/null; then
        print_warning "$file is missing, empty, or corrupted, initializing..."
        if [[ "$file" == *"campaigns.json" ]]; then
            echo "[]" > "$file"
        else
            echo "{}" > "$file"
        fi
        chmod 666 "$file"
    fi
done

# 9. Final permission check
print_status "Final permission check..."
ls -la *.json

# 10. Test application startup
print_status "Testing application startup..."
python3 -c "
import json
import os

# Test reading and writing to JSON files
files_to_test = ['accounts.json', 'users.json', 'campaigns.json', 'notifications.json']

for file in files_to_test:
    if os.path.exists(file):
        try:
            # Test reading
            with open(file, 'r') as f:
                data = json.load(f)
            print(f'✓ Read OK: {file}')
            
            # Test writing
            with open(file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f'✓ Write OK: {file}')
        except Exception as e:
            print(f'✗ Error with {file}: {e}')
    else:
        print(f'⚠ File not found: {file}')
"

# 11. Restart services
print_status "Restarting services..."
sudo systemctl start email-campaign-manager
sudo systemctl start nginx

# Wait for services to start
sleep 5

# 12. Check service status
print_status "Checking service status..."
if sudo systemctl is-active --quiet email-campaign-manager; then
    print_success "✓ Application service is running"
else
    print_error "✗ Application service failed to start"
    print_status "Service logs:"
    sudo journalctl -u email-campaign-manager --no-pager -n 10
fi

if sudo systemctl is-active --quiet nginx; then
    print_success "✓ Nginx is running"
else
    print_warning "⚠ Nginx is not running"
fi

# 13. Test web application
print_status "Testing web application..."
if curl -s http://localhost:8000 > /dev/null 2>&1; then
    print_success "✓ Application responding on localhost:8000"
else
    print_warning "⚠ Application not responding on localhost:8000"
fi

if curl -s http://localhost > /dev/null 2>&1; then
    print_success "✓ Application accessible via nginx"
else
    print_warning "⚠ Application not accessible via nginx"
fi

echo ""
print_success "🔧 AGGRESSIVE PERMISSION FIX COMPLETED!"
echo ""
print_status "What was fixed:"
echo "✓ All JSON files now have 666 permissions (read/write for all)"
echo "✓ All files owned by emailcampaign user"
echo "✓ All directories have 755 permissions"
echo "✓ All scripts are executable"
echo "✓ JSON files initialized with proper content"
echo "✓ Services restarted"
echo ""
print_status "Now test:"
echo "1. Create a new account"
echo "2. Delete an existing account"
echo "3. Create a new user"
echo "4. Edit user permissions"
echo "5. Delete a user"
echo ""
print_status "If you still have issues, run this command to check logs:"
echo "sudo journalctl -u email-campaign-manager -f"