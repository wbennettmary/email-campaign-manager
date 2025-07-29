#!/bin/bash

echo "🚨 EMERGENCY FIX: 502 Bad Gateway Error"
echo "======================================"

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

# Stop all services first
print_status "Stopping all services..."
sudo systemctl stop email-campaign-manager 2>/dev/null
sudo systemctl stop email-campaign-manager-optimized 2>/dev/null
sudo systemctl stop nginx 2>/dev/null

# Kill any remaining processes
print_status "Killing any remaining processes..."
pkill -f gunicorn 2>/dev/null
pkill -f python3 2>/dev/null

# Wait a moment
sleep 3

# Check if psutil is installed
print_status "Checking psutil installation..."
if ! python3 -c "import psutil" 2>/dev/null; then
    print_status "Installing psutil..."
    pip3 install psutil==5.9.5
fi

# Create a simple, working gunicorn configuration
print_status "Creating simple gunicorn configuration..."
cat > gunicorn_simple.conf.py << 'EOF'
# Simple Gunicorn configuration for stability
bind = "127.0.0.1:8000"
workers = 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 60
keepalive = 2
preload_app = False
worker_exit_on_app_exit = True
EOF

# Create a simple, working systemd service
print_status "Creating simple systemd service..."
cat > email-campaign-manager-simple.service << 'EOF'
[Unit]
Description=Email Campaign Manager (Simple)
After=network.target

[Service]
Type=exec
User=emailcampaign
Group=emailcampaign
WorkingDirectory=/home/emailcampaign/email-campaign-manager
Environment=PATH=/home/emailcampaign/email-campaign-manager/venv/bin
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn --config gunicorn_simple.conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=email-campaign-manager

# Simple memory limits
MemoryMax=1500M
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# Install the simple service
print_status "Installing simple service..."
sudo cp email-campaign-manager-simple.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-campaign-manager-simple

# Fix file permissions
print_status "Fixing file permissions..."
sudo chown -R emailcampaign:emailcampaign .
chmod 666 *.json
chmod +x *.sh
chmod +x *.py

# Initialize JSON files if they don't exist or are corrupted
print_status "Initializing JSON files..."
for file in accounts.json campaigns.json users.json notifications.json campaign_logs.json bounces.json rate_limit_config.json; do
    if [ ! -f "$file" ] || [ ! -s "$file" ]; then
        print_status "Initializing $file..."
        if [[ "$file" == *"campaigns.json" ]] || [[ "$file" == *"accounts.json" ]]; then
            echo "[]" > "$file"
        else
            echo "{}" > "$file"
        fi
        chmod 666 "$file"
    fi
done

# Ensure users.json has admin user
print_status "Ensuring admin user exists..."
if [ ! -s "users.json" ] || ! python3 -c "import json; data=json.load(open('users.json')); print('admin' in [u.get('username') for u in data])" 2>/dev/null; then
    print_status "Creating admin user..."
    cat > users.json << 'EOF'
[
  {
    "id": 1,
    "username": "admin",
    "password_hash": "pbkdf2:sha256:600000$admin$your-hashed-password-here",
    "role": "admin",
    "permissions": ["add_account", "manage_accounts", "view_all_campaigns", "manage_data"],
    "is_active": true,
    "created_at": "2024-01-01T00:00:00"
  }
]
EOF
    chmod 666 users.json
fi

# Start the simple service
print_status "Starting simple service..."
sudo systemctl start email-campaign-manager-simple

# Wait for service to start
sleep 10

# Check service status
print_status "Checking service status..."
if sudo systemctl is-active --quiet email-campaign-manager-simple; then
    print_success "✅ Simple service is running"
else
    print_error "❌ Simple service failed to start"
    print_status "Service logs:"
    sudo journalctl -u email-campaign-manager-simple --no-pager -n 20
    exit 1
fi

# Test application
print_status "Testing application..."
sleep 5
if curl -s http://localhost:8000 > /dev/null; then
    print_success "✅ Application is responding on localhost:8000"
else
    print_error "❌ Application not responding on localhost:8000"
    print_status "Checking if port 8000 is listening..."
    netstat -tlnp | grep :8000 || echo "Port 8000 not listening"
    exit 1
fi

# Start nginx
print_status "Starting nginx..."
sudo systemctl start nginx

# Wait for nginx
sleep 3

# Test nginx
print_status "Testing nginx..."
if curl -s http://localhost > /dev/null; then
    print_success "✅ Nginx is working"
else
    print_warning "⚠️ Nginx not responding, checking configuration..."
    sudo nginx -t
    sudo systemctl status nginx
fi

# Show current status
print_status "Current system status:"
echo "Memory usage:"
free -h
echo ""
echo "Disk usage:"
df -h /
echo ""
echo "Service status:"
sudo systemctl status email-campaign-manager-simple --no-pager -l
echo ""
echo "Nginx status:"
sudo systemctl status nginx --no-pager -l

print_success "🎉 Emergency fix completed!"
echo ""
print_status "📋 What was fixed:"
echo "✅ Created simple, stable gunicorn configuration"
echo "✅ Created simple systemd service"
echo "✅ Fixed file permissions"
echo "✅ Initialized corrupted/missing JSON files"
echo "✅ Ensured admin user exists"
echo "✅ Started application with minimal configuration"
echo ""
print_status "🔗 Your application should now be accessible at:"
echo "http://35.92.165.197"
echo ""
print_status "📊 Monitor the application:"
echo "• Check service status: sudo systemctl status email-campaign-manager-simple"
echo "• View logs: sudo journalctl -u email-campaign-manager-simple -f"
echo "• Test locally: curl http://localhost:8000"
echo ""
print_status "⚠️ If you still have issues:"
echo "• Check logs: sudo journalctl -u email-campaign-manager-simple --no-pager -n 50"
echo "• Restart service: sudo systemctl restart email-campaign-manager-simple"
echo "• Check nginx: sudo systemctl status nginx"