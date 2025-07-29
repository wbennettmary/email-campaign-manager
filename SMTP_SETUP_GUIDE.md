# SMTP Configuration Guide

This guide explains how to set up SMTP email notifications for the Email Campaign Manager.

## Overview

The SMTP system provides:
- **Password Reset Emails**: Secure token-based password reset
- **Security Alert Emails**: Notifications for login attempts
- **Account Creation Emails**: Welcome emails for new users
- **Test Email Functionality**: Verify SMTP configuration

## Quick Setup

### 1. Access SMTP Configuration
1. Log in as an **admin** user
2. Navigate to **SMTP Config** in the sidebar (admin only)
3. Or go to **User Dropdown** → **SMTP Configuration**

### 2. Configure Your Email Provider

#### Gmail Setup
1. **Enable 2-Factor Authentication** on your Google account
2. **Generate App Password**:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. **Configure in app**:
   - Server: `smtp.gmail.com`
   - Port: `587`
   - Username: `your-email@gmail.com`
   - Password: `[App Password]` (not your regular password)
   - Enable TLS

#### Outlook/Hotmail Setup
1. **Enable 2-Factor Authentication**
2. **Generate App Password**
3. **Configure in app**:
   - Server: `smtp-mail.outlook.com`
   - Port: `587`
   - Username: `your-email@outlook.com`
   - Password: `[App Password]`
   - Enable TLS

#### Yahoo Setup
1. **Enable 2-Factor Authentication**
2. **Generate App Password**
3. **Configure in app**:
   - Server: `smtp.mail.yahoo.com`
   - Port: `587`
   - Username: `your-email@yahoo.com`
   - Password: `[App Password]`
   - Enable TLS

### 3. Enable Email Notifications
1. Check **"Enable Email Notifications"**
2. Click **"Save Configuration"**
3. Click **"Test Configuration"** to verify settings

## Configuration File

The SMTP configuration is stored in `smtp_config.json`:

```json
{
  "enabled": true,
  "server": "smtp.gmail.com",
  "port": 587,
  "username": "your-email@gmail.com",
  "password": "your-app-password",
  "use_tls": true,
  "from_email": "your-email@gmail.com",
  "from_name": "Email Campaign Manager"
}
```

## Email Templates

### Password Reset Email
- **Subject**: "Password Reset Request - Email Campaign Manager"
- **Content**: Secure reset link with 1-hour expiration
- **Security**: Token-based, IP tracking

### Security Alert Email
- **Subject**: "Security Alert - Email Campaign Manager"
- **Content**: Login attempt notifications
- **Tracking**: Event type, timestamp, IP address

### Account Creation Email
- **Subject**: "Account Created - Email Campaign Manager"
- **Content**: Welcome message with account details
- **Information**: Username, role, login instructions

## Testing

### Web Interface Test
1. Go to **SMTP Config** page
2. Click **"Test Configuration"**
3. Enter test email address
4. Click **"Send Test Email"**

### Command Line Test
```bash
python test_smtp.py
```

## Security Features

### Password Reset Security
- **Token Expiration**: 1 hour
- **Single Use**: Tokens are deleted after use
- **IP Tracking**: Logs IP addresses for security
- **No Email Disclosure**: Doesn't reveal if email exists

### Security Alerts
- **Successful Logins**: Notified with IP address
- **Failed Logins**: Alerted for potential security threats
- **Password Changes**: Confirmation emails sent
- **Account Creation**: Welcome emails with security tips

## Troubleshooting

### Common Issues

#### "Authentication Failed"
- **Cause**: Wrong password or username
- **Solution**: Use App Password, not regular password
- **Check**: 2-Factor Authentication is enabled

#### "Connection Refused"
- **Cause**: Wrong server or port
- **Solution**: Verify SMTP server settings
- **Common Servers**:
  - Gmail: `smtp.gmail.com:587`
  - Outlook: `smtp-mail.outlook.com:587`
  - Yahoo: `smtp.mail.yahoo.com:587`

#### "TLS/SSL Error"
- **Cause**: TLS settings mismatch
- **Solution**: Enable TLS for port 587, disable for port 25
- **Note**: Most providers require TLS

#### "Email Not Sending"
- **Cause**: Configuration not saved or disabled
- **Solution**: 
  1. Check "Enable Email Notifications"
  2. Save configuration
  3. Test with web interface

### Provider-Specific Issues

#### Gmail
- **App Password Required**: Cannot use regular password
- **Less Secure Apps**: Disabled by Google (use App Passwords)
- **Rate Limits**: 500 emails/day for free accounts

#### Outlook
- **App Password Required**: 2FA must be enabled
- **Modern Authentication**: Required for new accounts
- **Rate Limits**: 300 emails/day for free accounts

#### Yahoo
- **App Password Required**: 2FA must be enabled
- **Account Security**: May require additional verification
- **Rate Limits**: 500 emails/day for free accounts

## Advanced Configuration

### Custom SMTP Server
For custom SMTP servers (e.g., company email):

```json
{
  "enabled": true,
  "server": "mail.yourcompany.com",
  "port": 587,
  "username": "noreply@yourcompany.com",
  "password": "your-password",
  "use_tls": true,
  "from_email": "noreply@yourcompany.com",
  "from_name": "Your Company Name"
}
```

### SSL vs TLS
- **Port 587**: Use TLS (recommended)
- **Port 465**: Use SSL
- **Port 25**: No encryption (not recommended)

## Monitoring

### Email Logs
- Check application logs for email sending status
- Failed emails are logged with error details
- Success messages confirm delivery

### Security Monitoring
- All security events are logged
- IP addresses are tracked
- Failed login attempts trigger alerts

## Best Practices

### Security
1. **Use App Passwords**: Never use regular passwords
2. **Enable 2FA**: Required for App Passwords
3. **Regular Updates**: Keep credentials secure
4. **Monitor Alerts**: Check security notifications

### Configuration
1. **Test First**: Always test before going live
2. **Backup Config**: Keep configuration file secure
3. **Regular Testing**: Test monthly to ensure functionality
4. **Documentation**: Keep setup notes for reference

### Maintenance
1. **Monitor Quotas**: Check email sending limits
2. **Update Credentials**: Rotate App Passwords regularly
3. **Review Logs**: Check for failed emails
4. **Backup Data**: Regular backups of configuration

## Support

### Getting Help
1. **Check Logs**: Application logs show detailed errors
2. **Test Script**: Use `test_smtp.py` for diagnostics
3. **Provider Support**: Contact email provider for account issues
4. **Documentation**: Refer to this guide for common issues

### Emergency Access
If SMTP is not working:
1. **Disable Notifications**: Set `"enabled": false`
2. **Manual Reset**: Admin can reset passwords directly
3. **Alternative**: Use password reset via admin interface

---

**Note**: SMTP configuration is admin-only. Regular users cannot access or modify email settings.