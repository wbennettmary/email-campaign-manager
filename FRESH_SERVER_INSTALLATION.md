# Email Campaign Manager - Complete Installation & Management Guide

## 🚀 One-Command Installation

This guide will take your fresh Ubuntu server from zero to a fully working Email Campaign Manager interface.

### Prerequisites
- Fresh Ubuntu 20.04+ server
- Root access (sudo privileges)
- Internet connection

### Step 1: Download and Run the Installation Script

```bash
# Download the automated installation script
wget https://raw.githubusercontent.com/wbennettmary/email-campaign-manager/master/auto_install.sh

# Make it executable
chmod +x auto_install.sh

# Run the automated installation
sudo ./auto_install.sh
```

That's it! The script will automatically:

1. ✅ Update your system
2. ✅ Install all required packages (Python, Nginx, Git, etc.)
3. ✅ Configure firewall
4. ✅ Create application user
5. ✅ Clone the repository
6. ✅ Set up Python virtual environment
7. ✅ Install dependencies
8. ✅ Configure Nginx
9. ✅ Create systemd service
10. ✅ Start all services
11. ✅ Verify everything is working
12. ✅ Show you the access URLs

### Step 2: Access Your Application

After the installation completes, you'll see output like this:

```
🎉 INSTALLATION COMPLETE!

Your Email Campaign Manager is now running!

🌐 Access URLs:
  Direct Application: http://YOUR_SERVER_IP:8000
  Through Nginx: http://YOUR_SERVER_IP
```

## 🔧 Management Commands

The same script handles all management tasks:

### Check Application Status
```bash
sudo ./auto_install.sh status
```

### Update Application
```bash
sudo ./auto_install.sh update
```

### Restart Services
```bash
sudo ./auto_install.sh restart
```

### View Logs
```bash
sudo ./auto_install.sh logs
```

### Show Help
```bash
sudo ./auto_install.sh help
```

## 📋 What Gets Installed

- **Python 3** with virtual environment
- **Flask** web framework
- **Gunicorn** WSGI server
- **Nginx** reverse proxy
- **Git** for code management
- **Firewall** configuration
- **Systemd** service management

## 🎯 Features Included

Your Email Campaign Manager will include:

- 📧 **Email Campaign Management**
- 👥 **Account Management**
- 📊 **Campaign Analytics**
- 📋 **Data Lists Management**
- 🔄 **Bounce Detection**
- 📈 **Delivery Tracking**
- 🎨 **Modern Web Interface**

## 🛠️ Troubleshooting

### If the installation fails:
```bash
# Check what went wrong
sudo journalctl -u email-campaign-manager -n 20

# Restart the service
sudo systemctl restart email-campaign-manager

# Check status
sudo ./auto_install.sh status
```

### If you can't access the application:
```bash
# Check if services are running
sudo ./auto_install.sh status

# Check if ports are listening
sudo netstat -tlnp | grep -E ':(80|8000)'

# Test locally
curl http://127.0.0.1:8000
```

### If you need to reinstall:
```bash
# Stop services
sudo systemctl stop email-campaign-manager
sudo systemctl stop nginx

# Remove old installation
sudo rm -rf /home/emailcampaign/email-campaign-manager
sudo rm /etc/systemd/system/email-campaign-manager.service
sudo rm /etc/nginx/sites-enabled/email-campaign-manager

# Run installation again
sudo ./auto_install.sh
```

### If services won't start:
```bash
# Check logs
sudo ./auto_install.sh logs

# Check system resources
free -h
df -h

# Check Python installation
sudo -u emailcampaign bash -c 'cd /home/emailcampaign/email-campaign-manager && source venv/bin/activate && python --version'
```

## 🔍 Manual Verification

If you want to verify everything manually:

```bash
# Check service status
sudo systemctl status email-campaign-manager
sudo systemctl status nginx

# Check if processes are running
ps aux | grep gunicorn
ps aux | grep nginx

# Check if ports are open
sudo netstat -tlnp | grep -E ':(80|8000)'

# Test application response
curl -I http://127.0.0.1:8000
curl -I http://YOUR_SERVER_IP
```

## 📊 Monitoring

### View Real-time Logs
```bash
# Application logs (follow)
sudo journalctl -u email-campaign-manager -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Check Resource Usage
```bash
# CPU and memory usage
htop

# Disk usage
df -h

# Application directory size
du -sh /home/emailcampaign/email-campaign-manager
```

## 🔒 Security

The installation includes:

- **Firewall configuration** (UFW)
- **Non-root user** for application
- **Service isolation** with systemd
- **Secure file permissions**
- **Nginx security headers**

## 📈 Scaling

To scale your application:

### Increase Workers
Edit the service file:
```bash
sudo nano /etc/systemd/system/email-campaign-manager.service
```

Change the workers parameter:
```
ExecStart=/home/emailcampaign/email-campaign-manager/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 4 app:app
```

Restart the service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart email-campaign-manager
```

### Add SSL/HTTPS
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## 🆘 Support

If you encounter any issues:

1. **Check logs**: `sudo ./auto_install.sh logs`
2. **Verify services**: `sudo ./auto_install.sh status`
3. **Test connectivity**: `curl http://127.0.0.1:8000`
4. **Check system resources**: `htop`, `df -h`

The installation script includes comprehensive error checking and will tell you exactly what went wrong if there are any issues.

## 📝 Quick Reference

| Command | Description |
|---------|-------------|
| `sudo ./auto_install.sh` | Install application |
| `sudo ./auto_install.sh status` | Check status |
| `sudo ./auto_install.sh update` | Update application |
| `sudo ./auto_install.sh restart` | Restart services |
| `sudo ./auto_install.sh logs` | View logs |
| `sudo ./auto_install.sh help` | Show help |

## 🎉 Success!

Once installed, your Email Campaign Manager will be accessible at:
- **Direct**: `http://YOUR_SERVER_IP:8000`
- **Nginx**: `http://YOUR_SERVER_IP`

The application includes a modern web interface with all the features you need for email campaign management! 