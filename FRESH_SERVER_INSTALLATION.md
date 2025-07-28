# Email Campaign Manager - Fresh Server Installation

## 🚀 One-Command Installation

This guide will take your fresh Ubuntu server from zero to a fully working Email Campaign Manager interface.

### Prerequisites
- Fresh Ubuntu 20.04+ server
- Root access (sudo privileges)
- Internet connection

### Step 1: Download the Installation Script

```bash
# Download the automated installation script
wget https://raw.githubusercontent.com/wbennettmary/email-campaign-manager/master/auto_install.sh

# Make it executable
chmod +x auto_install.sh
```

### Step 2: Run the Installation

```bash
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

### Step 3: Access Your Application

After the installation completes, you'll see output like this:

```
🎉 INSTALLATION COMPLETE!

Your Email Campaign Manager is now running!

🌐 Access URLs:
  Direct Application: http://YOUR_SERVER_IP:8000
  Through Nginx: http://YOUR_SERVER_IP
```

### What Gets Installed

- **Python 3** with virtual environment
- **Flask** web framework
- **Gunicorn** WSGI server
- **Nginx** reverse proxy
- **Git** for code management
- **Firewall** configuration
- **Systemd** service management

### Troubleshooting

If something goes wrong, the script will show you exactly what failed. Common solutions:

#### If the script fails:
```bash
# Check what went wrong
sudo journalctl -u email-campaign-manager -n 20

# Restart the service
sudo systemctl restart email-campaign-manager

# Check status
sudo systemctl status email-campaign-manager
```

#### If you can't access the application:
```bash
# Check if services are running
sudo systemctl status email-campaign-manager
sudo systemctl status nginx

# Check if ports are listening
sudo netstat -tlnp | grep -E ':(80|8000)'

# Test locally
curl http://127.0.0.1:8000
```

#### If you need to reinstall:
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

### Manual Installation (Alternative)

If you prefer to run commands manually, you can use the step-by-step guide in `DEPLOYMENT_GUIDE.md`.

### Features Installed

Your Email Campaign Manager will include:

- 📧 **Email Campaign Management**
- 👥 **Account Management**
- 📊 **Campaign Analytics**
- 📋 **Data Lists Management**
- 🔄 **Bounce Detection**
- 📈 **Delivery Tracking**
- 🎨 **Modern Web Interface**

### Support

If you encounter any issues:

1. Check the logs: `sudo journalctl -u email-campaign-manager -f`
2. Verify services: `sudo systemctl status email-campaign-manager`
3. Test connectivity: `curl http://127.0.0.1:8000`

The installation script includes comprehensive error checking and will tell you exactly what went wrong if there are any issues. 