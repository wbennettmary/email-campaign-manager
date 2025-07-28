# 🚀 Ubuntu Server Deployment Guide

## Email Campaign Manager - Production Deployment

This guide will walk you through deploying your Email Campaign Manager to a production Ubuntu server with SSL, monitoring, and proper security.

---

## 📋 Prerequisites

### Server Requirements
- **OS**: Ubuntu 22.04 LTS (recommended)
- **RAM**: Minimum 1GB, Recommended 2GB+
- **Storage**: Minimum 20GB, Recommended 40GB+
- **CPU**: 1-2 cores minimum
- **Domain**: A domain name pointing to your server IP

### Before You Start
1. **Domain Setup**: Point your domain to your server's IP address
2. **Server Access**: SSH access to your Ubuntu server
3. **Root Access**: Sudo privileges on the server

---

## 🔧 Step-by-Step Deployment

### Step 1: Server Preparation

Connect to your Ubuntu server via SSH and run:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y python3 python3-pip python3-venv nginx git curl wget unzip
sudo apt install -y build-essential python3-dev libpq-dev certbot python3-certbot-nginx
```

### Step 2: Security Configuration

```bash
# Configure firewall
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Create application user
sudo adduser emailcampaign
sudo usermod -aG sudo emailcampaign
```

### Step 3: Application Setup

```bash
# Switch to application user
sudo su - emailcampaign

# Clone your repository
git clone https://github.com/wbennettmary/email-campaign-manager.git
cd email-campaign-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Create necessary directories
mkdir -p data_lists logs
```

### Step 4: Configuration Files

The deployment includes these configuration files:

1. **`gunicorn.conf.py`** - Gunicorn server configuration
2. **`email-campaign-manager.service`** - Systemd service file
3. **`nginx.conf`** - Nginx reverse proxy configuration
4. **`deploy.sh`** - Automated deployment script

### Step 5: Automated Deployment

```bash
# Make deployment script executable
chmod +x deploy.sh

# Run deployment script (as root)
sudo ./deploy.sh
```

### Step 6: Domain Configuration

1. **Update Nginx Configuration**:
   ```bash
   sudo nano /etc/nginx/sites-available/email-campaign-manager
   ```
   Replace `your-domain.com` with your actual domain name.

2. **Test Nginx Configuration**:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### Step 7: SSL Certificate

```bash
# Install SSL certificate
sudo certbot --nginx -d your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### Step 8: Final Configuration

```bash
# Restart services
sudo systemctl restart email-campaign-manager
sudo systemctl restart nginx

# Check service status
sudo systemctl status email-campaign-manager
sudo systemctl status nginx
```

---

## 🔍 Verification & Testing

### Check Application Status
```bash
# Check if application is running
sudo systemctl status email-campaign-manager

# Check logs
sudo journalctl -u email-campaign-manager -f

# Test web access
curl -I http://localhost:8000
```

### Test Web Interface
1. Open your browser and go to `https://your-domain.com`
2. Verify the application loads correctly
3. Test login functionality
4. Check all features work as expected

---

## 📊 Monitoring & Maintenance

### Log Files
- **Application Logs**: `/var/log/email-campaign-manager/`
- **System Logs**: `sudo journalctl -u email-campaign-manager`
- **Nginx Logs**: `/var/log/nginx/`

### Useful Commands

```bash
# Restart application
sudo systemctl restart email-campaign-manager

# Check application status
sudo systemctl status email-campaign-manager

# View real-time logs
sudo journalctl -u email-campaign-manager -f

# Update application
cd /home/emailcampaign/email-campaign-manager
git pull origin master
sudo systemctl restart email-campaign-manager

# Check disk usage
df -h

# Check memory usage
free -h

# Monitor system resources
htop
```

### Backup Strategy

```bash
# Create backup script
sudo nano /home/emailcampaign/backup.sh
```

```bash
#!/bin/bash
# Backup script for Email Campaign Manager

BACKUP_DIR="/home/emailcampaign/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup application data
tar -czf $BACKUP_DIR/app_data_$DATE.tar.gz \
    /home/emailcampaign/email-campaign-manager/*.json \
    /home/emailcampaign/email-campaign-manager/data_lists/ \
    /home/emailcampaign/email-campaign-manager/logs/

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz \
    /etc/nginx/sites-available/email-campaign-manager \
    /etc/systemd/system/email-campaign-manager.service

echo "Backup completed: $BACKUP_DIR/"
```

---

## 🔒 Security Considerations

### Firewall Configuration
- Only SSH and HTTP/HTTPS ports are open
- All other ports are blocked by default

### File Permissions
- Application runs as dedicated user `emailcampaign`
- Sensitive files are protected from web access
- Log files have appropriate permissions

### SSL/TLS
- Automatic SSL certificate renewal
- Modern TLS protocols (TLS 1.2, 1.3)
- Strong cipher suites

### Application Security
- Security headers configured in Nginx
- Input validation and sanitization
- Rate limiting (can be added to Nginx)

---

## 🚨 Troubleshooting

### Common Issues

1. **Application Won't Start**:
   ```bash
   sudo journalctl -u email-campaign-manager -n 50
   ```

2. **Nginx Errors**:
   ```bash
   sudo nginx -t
   sudo tail -f /var/log/nginx/error.log
   ```

3. **Permission Issues**:
   ```bash
   sudo chown -R emailcampaign:emailcampaign /home/emailcampaign/email-campaign-manager
   ```

4. **Port Conflicts**:
   ```bash
   sudo netstat -tlnp | grep :8000
   sudo netstat -tlnp | grep :80
   ```

### Performance Optimization

1. **Database Optimization** (if using PostgreSQL):
   ```bash
   sudo apt install postgresql postgresql-contrib
   ```

2. **Caching** (Redis):
   ```bash
   sudo apt install redis-server
   ```

3. **Monitoring** (Optional):
   ```bash
   sudo apt install htop iotop nethogs
   ```

---

## 📈 Scaling Considerations

### Vertical Scaling
- Increase server resources (RAM, CPU, Storage)
- Optimize application configuration
- Add caching layers

### Horizontal Scaling
- Load balancer setup
- Multiple application instances
- Database clustering

### Monitoring Tools
- **System Monitoring**: htop, iotop, nethogs
- **Application Monitoring**: Custom health checks
- **Log Monitoring**: logrotate, fail2ban

---

## ✅ Deployment Checklist

- [ ] Server updated and secured
- [ ] Application user created
- [ ] Repository cloned and dependencies installed
- [ ] Configuration files in place
- [ ] Services started and enabled
- [ ] Domain configured in Nginx
- [ ] SSL certificate installed
- [ ] Application accessible via HTTPS
- [ ] All features tested
- [ ] Backup strategy implemented
- [ ] Monitoring configured
- [ ] Documentation updated

---

## 🎯 Next Steps

After successful deployment:

1. **Set up monitoring and alerting**
2. **Configure automated backups**
3. **Implement log rotation**
4. **Set up CI/CD pipeline**
5. **Configure email notifications**
6. **Plan for scaling**

---

## 📞 Support

If you encounter issues during deployment:

1. Check the logs: `sudo journalctl -u email-campaign-manager -f`
2. Verify configuration files
3. Test each component individually
4. Review this guide for troubleshooting steps

---

**Happy Deploying! 🚀** 