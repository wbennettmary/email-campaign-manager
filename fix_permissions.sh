#!/bin/bash

echo "🔧 Fixing file permissions for Email Campaign Manager..."

# Navigate to the application directory
cd /home/emailcampaign/email-campaign-manager

# Set correct ownership for all files
echo "📁 Setting ownership to emailcampaign user..."
sudo chown -R emailcampaign:emailcampaign .

# Set correct permissions for directories
echo "📂 Setting directory permissions..."
find . -type d -exec chmod 755 {} \;

# Set correct permissions for files
echo "📄 Setting file permissions..."
find . -type f -exec chmod 644 {} \;

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x *.sh

# Set specific permissions for JSON data files
echo "📊 Setting JSON data file permissions..."
chmod 666 *.json

# Check the current permissions
echo "📋 Current file permissions:"
ls -la *.json

echo "✅ Permissions fixed successfully!"
echo "🔄 Restarting the application service..."

# Restart the application service
sudo systemctl restart email-campaign-manager

# Check service status
echo "📊 Service status:"
sudo systemctl status email-campaign-manager --no-pager

echo "🎉 Done! Try deleting an account now."