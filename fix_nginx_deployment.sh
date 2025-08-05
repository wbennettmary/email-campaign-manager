#!/bin/bash

echo "🔧 Fixing Nginx Configuration for IP-based Access..."

# Stop services
echo "⏹️  Stopping services..."
sudo systemctl stop nginx
sudo systemctl stop email-campaign-manager

# Backup current nginx config
echo "💾 Backing up current nginx config..."
sudo cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.backup

# Copy our fixed nginx config
echo "📝 Installing fixed nginx configuration..."
sudo cp nginx.conf /etc/nginx/sites-available/default

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"
    
    # Start services
    echo "🚀 Starting services..."
    sudo systemctl start email-campaign-manager
    sudo systemctl start nginx
    
    # Enable services
    echo "🔗 Enabling services..."
    sudo systemctl enable email-campaign-manager
    sudo systemctl enable nginx
    
    # Check status
    echo "📊 Checking service status..."
    echo "--- Email Campaign Manager Status ---"
    sudo systemctl status email-campaign-manager --no-pager -l
    
    echo "--- Nginx Status ---"
    sudo systemctl status nginx --no-pager -l
    
    echo "--- Port Check ---"
    sudo netstat -tlnp | grep :80
    sudo netstat -tlnp | grep :8000
    
    echo ""
    echo "🎉 Deployment completed!"
    echo "🌐 Your application should now be accessible at:"
    echo "   http://35.88.241.190"
    echo ""
    echo "📝 If you still get errors, check the logs:"
    echo "   sudo journalctl -u email-campaign-manager -f"
    echo "   sudo journalctl -u nginx -f"
    
else
    echo "❌ Nginx configuration test failed!"
    echo "Please check the nginx.conf file and try again."
    exit 1
fi 