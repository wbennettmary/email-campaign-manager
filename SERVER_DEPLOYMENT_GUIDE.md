# Server Deployment Guide

## 🚀 Overview

This guide provides step-by-step instructions for deploying the Email Campaign Manager to a production server. The application is designed to work both locally for testing and on a server for production use.

## 📋 Prerequisites

### Server Requirements
- **Operating System**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **Python**: 3.8+ (3.11 recommended)
- **Memory**: Minimum 2GB RAM (4GB+ recommended)
- **Storage**: 10GB+ free space
- **Network**: Stable internet connection for Zoho API access

### Software Dependencies
- **Python 3.11+**
- **pip** (Python package manager)
- **git** (for code deployment)
- **nginx** (web server)
- **supervisor** (process manager)
- **ufw** (firewall)

## 🔧 Installation Steps

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv git nginx supervisor ufw

# Create application directory
sudo mkdir -p /opt/email-campaign-manager
sudo chown $USER:$USER /opt/email-campaign-manager
```

### 2. Application Deployment

```bash
# Clone or upload application
cd /opt/email-campaign-manager

# If using git:
git clone <your-repository-url> .

# Or upload files manually to this directory

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration Setup

```bash
# Create configuration files
mkdir -p config
touch config/rate_limit_config.json
touch config/smtp_config.json

# Set proper permissions
chmod 600 config/*.json
```

### 4. Environment Configuration

```bash
# Create environment file
cat > .env << EOF
FLASK_ENV=production
FLASK_APP=app.py
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
DATABASE_URL=sqlite:///email_campaign_manager.db
LOG_LEVEL=INFO
EOF

# Set proper permissions
chmod 600 .env
```

## 🔒 Security Configuration

### 1. Firewall Setup

```bash
# Configure firewall
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# Check status
sudo ufw status
```

### 2. SSL Certificate (Optional but Recommended)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate (replace with your domain)
sudo certbot --nginx -d yourdomain.com
```

## 🌐 Nginx Configuration

### 1. Create Nginx Site Configuration

```bash
sudo nano /etc/nginx/sites-available/email-campaign-manager
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com;  # Replace with your domain or IP
    
    # Redirect HTTP to HTTPS (if using SSL)
    # return 301 https://$server_name$request_uri;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Static files (if any)
    location /static/ {
        alias /opt/email-campaign-manager/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
```

### 2. Enable Site

```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/email-campaign-manager /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

## 🔄 Supervisor Configuration

### 1. Create Supervisor Configuration

```bash
sudo nano /etc/supervisor/conf.d/email-campaign-manager.conf
```

Add the following configuration:

```ini
[program:email-campaign-manager]
directory=/opt/email-campaign-manager
command=/opt/email-campaign-manager/venv/bin/python app.py
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/email-campaign-manager/app.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
environment=FLASK_ENV="production",PYTHONPATH="/opt/email-campaign-manager"
```

### 2. Setup Logging

```bash
# Create log directory
sudo mkdir -p /var/log/email-campaign-manager
sudo chown www-data:www-data /var/log/email-campaign-manager

# Update supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start email-campaign-manager
```

## 📊 Monitoring and Logs

### 1. Application Logs

```bash
# View application logs
sudo tail -f /var/log/email-campaign-manager/app.log

# View supervisor logs
sudo supervisorctl status email-campaign-manager
sudo supervisorctl tail email-campaign-manager
```

### 2. Nginx Logs

```bash
# Access logs
sudo tail -f /var/log/nginx/access.log

# Error logs
sudo tail -f /var/log/nginx/error.log
```

## 🔧 Maintenance Commands

### Application Management

```bash
# Restart application
sudo supervisorctl restart email-campaign-manager

# Stop application
sudo supervisorctl stop email-campaign-manager

# Start application
sudo supervisorctl start email-campaign-manager

# Check status
sudo supervisorctl status email-campaign-manager
```

### Update Application

```bash
# Stop application
sudo supervisorctl stop email-campaign-manager

# Update code
cd /opt/email-campaign-manager
git pull  # or upload new files

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Start application
sudo supervisorctl start email-campaign-manager
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Application Won't Start
```bash
# Check logs
sudo supervisorctl tail email-campaign-manager

# Check permissions
ls -la /opt/email-campaign-manager/
sudo chown -R www-data:www-data /opt/email-campaign-manager/
```

#### 2. Nginx Issues
```bash
# Test configuration
sudo nginx -t

# Check Nginx status
sudo systemctl status nginx

# Restart Nginx
sudo systemctl restart nginx
```

#### 3. Port Issues
```bash
# Check if port 5000 is in use
sudo netstat -tlnp | grep :5000

# Kill process if needed
sudo kill -9 <PID>
```

#### 4. Permission Issues
```bash
# Fix permissions
sudo chown -R www-data:www-data /opt/email-campaign-manager/
sudo chmod -R 755 /opt/email-campaign-manager/
sudo chmod 600 /opt/email-campaign-manager/config/*.json
```

## 🔒 Security Best Practices

### 1. Regular Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python packages
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Backup Strategy
```bash
# Create backup script
cat > /opt/email-campaign-manager/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/email-campaign-manager"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup application data
tar -czf $BACKUP_DIR/app_data_$DATE.tar.gz \
    /opt/email-campaign-manager/*.json \
    /opt/email-campaign-manager/config/ \
    /opt/email-campaign-manager/*.db

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
EOF

chmod +x /opt/email-campaign-manager/backup.sh

# Add to crontab for daily backups
echo "0 2 * * * /opt/email-campaign-manager/backup.sh" | sudo crontab -
```

### 3. Monitoring
```bash
# Install monitoring tools
sudo apt install -y htop iotop

# Monitor system resources
htop
iotop
```

## 📈 Performance Optimization

### 1. Nginx Optimization
```nginx
# Add to nginx configuration
worker_processes auto;
worker_connections 1024;

# Enable gzip compression
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
```

### 2. Application Optimization
```python
# In app.py, for production
if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000, debug=False, threaded=True)
```

## 🎯 Production Checklist

- [ ] Server security updates installed
- [ ] Firewall configured
- [ ] SSL certificate installed (if using domain)
- [ ] Application running under supervisor
- [ ] Nginx configured and running
- [ ] Logs being written to proper locations
- [ ] Backup strategy implemented
- [ ] Monitoring in place
- [ ] Rate limiting configured
- [ ] Error handling tested
- [ ] Performance optimized

## 🔄 Deployment Script

Create a deployment script for easy updates:

```bash
cat > /opt/email-campaign-manager/deploy.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Starting deployment..."

# Stop application
sudo supervisorctl stop email-campaign-manager

# Backup current version
./backup.sh

# Update code
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Fix permissions
sudo chown -R www-data:www-data /opt/email-campaign-manager/
sudo chmod 600 config/*.json

# Start application
sudo supervisorctl start email-campaign-manager

echo "✅ Deployment completed successfully!"
EOF

chmod +x /opt/email-campaign-manager/deploy.sh
```

## 📞 Support

For issues or questions:
1. Check application logs: `/var/log/email-campaign-manager/app.log`
2. Check supervisor status: `sudo supervisorctl status`
3. Check Nginx logs: `/var/log/nginx/error.log`
4. Verify configuration files and permissions

---

**Your Email Campaign Manager is now ready for production use! 🎉** 