#!/bin/bash

echo "🔧 Fixing permissions for Email Campaign Manager on server..."
echo ""

# Get current user
CURRENT_USER=$(whoami)
echo "Current user: $CURRENT_USER"
echo ""

# Check if we're in the correct directory
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Please run this script from the application directory."
    exit 1
fi

# Fix permissions for data_lists directory
echo "📁 Fixing permissions for data_lists directory..."
if [ -d "data_lists" ]; then
    chmod -R 755 data_lists
    chown -R $CURRENT_USER:$CURRENT_USER data_lists
    echo "✅ data_lists permissions fixed successfully"
else
    echo "⚠️  data_lists directory not found, creating it..."
    mkdir -p data_lists
    chmod 755 data_lists
    chown $CURRENT_USER:$CURRENT_USER data_lists
    echo "✅ data_lists directory created with correct permissions"
fi

echo ""

# Fix permissions for current directory
echo "📂 Fixing permissions for current directory..."
chmod 755 .
chown $CURRENT_USER:$CURRENT_USER .

# Fix permissions for all JSON files
echo "📄 Fixing permissions for data files..."
chmod 644 *.json
chown $CURRENT_USER:$CURRENT_USER *.json

# Fix permissions for app.py
echo "🐍 Fixing permissions for app.py..."
chmod 755 app.py
chown $CURRENT_USER:$CURRENT_USER app.py

echo ""
echo "✅ Permission fix completed!"
echo "You can now run the application without permission errors."
echo ""
echo "To restart the application:"
echo "  sudo systemctl restart email-campaign-manager"
echo "  # or if using screen/pm2:"
echo "  pm2 restart app"
echo ""