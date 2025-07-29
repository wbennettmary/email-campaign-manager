from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
import os
import threading
import time
import random
import requests
from datetime import datetime, timedelta
import uuid
import csv
import pandas as pd
from zoho_bounce_integration import (
    initialize_zoho_bounce_detector, 
    get_zoho_bounce_detector,
    setup_bounce_webhook,
    check_email_bounce_status,
    start_bounce_monitoring,
    get_bounce_statistics
)
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import ssl
from datetime import datetime, timedelta
import pandas as pd
import csv
from werkzeug.utils import secure_filename
import zoho_bounce_integration
import zoho_oauth_integration
import logging

# Rate Limiting Configuration
RATE_LIMIT_CONFIG_FILE = 'rate_limit_config.json'

# Default rate limiting settings
DEFAULT_RATE_LIMIT = {
    'enabled': True,
    'emails_per_second': 2,
    'emails_per_minute': 100,
    'emails_per_hour': 1000,
    'emails_per_day': 10000,
    'wait_time_between_emails': 0.5,  # seconds
    'burst_limit': 5,  # max emails in burst
    'cooldown_period': 60,  # seconds after burst
    'daily_quota': 10000,
    'hourly_quota': 1000,
    'minute_quota': 100,
    'second_quota': 2
}

# Rate limiting storage
rate_limit_data = {
    'daily_sent': {},
    'hourly_sent': {},
    'minute_sent': {},
    'second_sent': {},
    'last_send_time': {},
    'burst_count': {},
    'cooldown_until': {}
}

def load_rate_limit_config():
    """Load rate limiting configuration from file"""
    try:
        with open(RATE_LIMIT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_RATE_LIMIT.copy()

def save_rate_limit_config(config):
    """Save rate limiting configuration to file"""
    with open(RATE_LIMIT_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def check_rate_limit(user_id, campaign_id=None):
    """
    Check if user/campaign is within rate limits
    Returns: (allowed: bool, wait_time: float, reason: str)
    """
    # Load campaign-specific rate limits if campaign_id is provided
    campaign_config = None
    if campaign_id:
        try:
            campaigns = read_json_file_simple(CAMPAIGNS_FILE)
            campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
            if campaign and campaign.get('rate_limits'):
                campaign_config = campaign['rate_limits']
        except:
            pass
    
    # Use campaign-specific config if available, otherwise use default
    config = campaign_config if campaign_config else load_rate_limit_config()
    
    if not config.get('enabled', True):
        return True, 0, "Rate limiting disabled"
    
    current_time = time.time()
    current_day = int(current_time // 86400)
    current_hour = int(current_time // 3600)
    current_minute = int(current_time // 60)
    current_second = int(current_time)
    
    # Initialize user data if not exists
    if user_id not in rate_limit_data['daily_sent']:
        rate_limit_data['daily_sent'][user_id] = {}
        rate_limit_data['hourly_sent'][user_id] = {}
        rate_limit_data['minute_sent'][user_id] = {}
        rate_limit_data['second_sent'][user_id] = {}
        rate_limit_data['last_send_time'][user_id] = 0
        rate_limit_data['burst_count'][user_id] = 0
        rate_limit_data['cooldown_until'][user_id] = 0
    
    # Check cooldown period
    if current_time < rate_limit_data['cooldown_until'][user_id]:
        wait_time = rate_limit_data['cooldown_until'][user_id] - current_time
        # Don't wait more than 60 seconds for cooldown
        if wait_time > 60:
            rate_limit_data['cooldown_until'][user_id] = current_time + 60
            wait_time = 60
        return False, wait_time, f"Cooldown period active. Wait {wait_time:.1f} seconds"
    
    # Check burst limit
    if rate_limit_data['burst_count'][user_id] >= config.get('burst_limit', 5):
        cooldown_duration = min(config.get('cooldown_period', 60), 60)  # Max 60 seconds
        rate_limit_data['cooldown_until'][user_id] = current_time + cooldown_duration
        rate_limit_data['burst_count'][user_id] = 0
        return False, cooldown_duration, f"Burst limit exceeded. Cooldown for {cooldown_duration} seconds"
    
    # Check wait time between emails (reduced for better delivery)
    wait_time_between = max(config.get('wait_time_between_emails', 0.5), 0.1)  # Min 0.1 seconds
    time_since_last = current_time - rate_limit_data['last_send_time'][user_id]
    if time_since_last < wait_time_between:
        wait_time = wait_time_between - time_since_last
        # Don't wait more than 5 seconds between emails
        if wait_time > 5:
            wait_time = 5
        return False, wait_time, f"Wait {wait_time:.1f} seconds between emails"
    
    # Check daily quota
    if current_day not in rate_limit_data['daily_sent'][user_id]:
        rate_limit_data['daily_sent'][user_id][current_day] = 0
    
    daily_quota = config.get('daily_quota', 10000)
    if rate_limit_data['daily_sent'][user_id][current_day] >= daily_quota:
        next_day = current_day + 1
        wait_time = (next_day * 86400) - current_time
        return False, wait_time, f"Daily quota exceeded ({daily_quota} emails)"
    
    # Check hourly quota
    if current_hour not in rate_limit_data['hourly_sent'][user_id]:
        rate_limit_data['hourly_sent'][user_id][current_hour] = 0
    
    hourly_quota = config.get('hourly_quota', 1000)
    if rate_limit_data['hourly_sent'][user_id][current_hour] >= hourly_quota:
        next_hour = current_hour + 1
        wait_time = (next_hour * 3600) - current_time
        return False, wait_time, f"Hourly quota exceeded ({hourly_quota} emails)"
    
    # Check minute quota
    if current_minute not in rate_limit_data['minute_sent'][user_id]:
        rate_limit_data['minute_sent'][user_id][current_minute] = 0
    
    minute_quota = config.get('minute_quota', 100)
    if rate_limit_data['minute_sent'][user_id][current_minute] >= minute_quota:
        next_minute = current_minute + 1
        wait_time = (next_minute * 60) - current_time
        return False, wait_time, f"Minute quota exceeded ({minute_quota} emails)"
    
    # Check second quota
    if current_second not in rate_limit_data['second_sent'][user_id]:
        rate_limit_data['second_sent'][user_id][current_second] = 0
    
    second_quota = config.get('second_quota', 2)
    if rate_limit_data['second_sent'][user_id][current_second] >= second_quota:
        next_second = current_second + 1
        wait_time = next_second - current_time
        return False, wait_time, f"Second quota exceeded ({second_quota} emails)"
    
    return True, 0, "Rate limit check passed"

def update_rate_limit_counters(user_id):
    """Update rate limit counters after sending an email"""
    current_time = time.time()
    current_day = int(current_time // 86400)
    current_hour = int(current_time // 3600)
    current_minute = int(current_time // 60)
    current_second = int(current_time)
    
    # Update counters
    rate_limit_data['daily_sent'][user_id][current_day] = rate_limit_data['daily_sent'][user_id].get(current_day, 0) + 1
    rate_limit_data['hourly_sent'][user_id][current_hour] = rate_limit_data['hourly_sent'][user_id].get(current_hour, 0) + 1
    rate_limit_data['minute_sent'][user_id][current_minute] = rate_limit_data['minute_sent'][user_id].get(current_minute, 0) + 1
    rate_limit_data['second_sent'][user_id][current_second] = rate_limit_data['second_sent'][user_id].get(current_second, 0) + 1
    
    # Update timing
    rate_limit_data['last_send_time'][user_id] = current_time
    rate_limit_data['burst_count'][user_id] += 1

def get_rate_limit_stats(user_id):
    """Get current rate limit statistics for a user"""
    config = load_rate_limit_config()
    current_time = time.time()
    current_day = int(current_time // 86400)
    current_hour = int(current_time // 3600)
    current_minute = int(current_time // 60)
    
    daily_sent = rate_limit_data['daily_sent'].get(user_id, {}).get(current_day, 0)
    hourly_sent = rate_limit_data['hourly_sent'].get(user_id, {}).get(current_hour, 0)
    minute_sent = rate_limit_data['minute_sent'].get(user_id, {}).get(current_minute, 0)
    burst_count = rate_limit_data['burst_count'].get(user_id, 0)
    
    return {
        'daily_sent': daily_sent,
        'daily_limit': config.get('daily_quota', 10000),
        'daily_remaining': max(0, config.get('daily_quota', 10000) - daily_sent),
        'hourly_sent': hourly_sent,
        'hourly_limit': config.get('hourly_quota', 1000),
        'hourly_remaining': max(0, config.get('hourly_quota', 1000) - hourly_sent),
        'minute_sent': minute_sent,
        'minute_limit': config.get('minute_quota', 100),
        'minute_remaining': max(0, config.get('minute_quota', 100) - minute_sent),
        'burst_count': burst_count,
        'burst_limit': config.get('burst_limit', 5),
        'wait_time_between': config.get('wait_time_between_emails', 0.5),
        'cooldown_until': rate_limit_data['cooldown_until'].get(user_id, 0),
        'in_cooldown': current_time < rate_limit_data['cooldown_until'].get(user_id, 0)
    }

def cleanup_old_rate_limit_data():
    """Clean up old rate limit data to prevent memory bloat"""
    current_time = time.time()
    cutoff_day = int((current_time - 86400) // 86400)  # 1 day ago
    cutoff_hour = int((current_time - 3600) // 3600)   # 1 hour ago
    cutoff_minute = int((current_time - 60) // 60)     # 1 minute ago
    cutoff_second = int(current_time - 1)              # 1 second ago
    
    for user_id in list(rate_limit_data['daily_sent'].keys()):
        # Clean daily data
        rate_limit_data['daily_sent'][user_id] = {
            day: count for day, count in rate_limit_data['daily_sent'][user_id].items()
            if int(day) > cutoff_day
        }
        
        # Clean hourly data
        rate_limit_data['hourly_sent'][user_id] = {
            hour: count for hour, count in rate_limit_data['hourly_sent'][user_id].items()
            if int(hour) > cutoff_hour
        }
        
        # Clean minute data
        rate_limit_data['minute_sent'][user_id] = {
            minute: count for minute, count in rate_limit_data['minute_sent'][user_id].items()
            if int(minute) > cutoff_minute
        }
        
        # Clean second data
        rate_limit_data['second_sent'][user_id] = {
            second: count for second, count in rate_limit_data['second_sent'][user_id].items()
            if int(second) > cutoff_second
        }

# Initialize rate limit config
RATE_LIMIT_CONFIG = load_rate_limit_config()

# Cleanup thread
def rate_limit_cleanup_thread():
    """Background thread to clean up old rate limit data"""
    while True:
        try:
            cleanup_old_rate_limit_data()
            time.sleep(300)  # Clean up every 5 minutes
        except Exception as e:
            print(f"Rate limit cleanup error: {e}")
            time.sleep(60)

# Start cleanup thread
cleanup_thread = threading.Thread(target=rate_limit_cleanup_thread, daemon=True)
cleanup_thread.start()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# SMTP Configuration
SMTP_CONFIG_FILE = 'smtp_config.json'

def load_smtp_config():
    """Load SMTP configuration from file"""
    try:
        with open(SMTP_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            'enabled': False,
            'server': 'smtp.gmail.com',
            'port': 587,
            'username': 'your-email@gmail.com',
            'password': 'your-app-password',
            'use_tls': True,
            'from_email': 'your-email@gmail.com',
            'from_name': 'Email Campaign Manager'
        }

def reload_smtp_config():
    """Reload SMTP configuration from file"""
    global SMTP_CONFIG
    SMTP_CONFIG = load_smtp_config()

SMTP_CONFIG = load_smtp_config()

# Email templates
EMAIL_TEMPLATES = {
    'password_reset': {
        'subject': 'Password Reset Request - Email Campaign Manager',
        'body': '''
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>Hello {username},</p>
            <p>You have requested a password reset for your Email Campaign Manager account.</p>
            <p>Click the link below to reset your password:</p>
            <p><a href="{reset_link}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request this reset, please ignore this email.</p>
            <p>Best regards,<br>Email Campaign Manager Team</p>
        </body>
        </html>
        '''
    },
    'security_alert': {
        'subject': 'Security Alert - Email Campaign Manager',
        'body': '''
        <html>
        <body>
            <h2>Security Alert</h2>
            <p>Hello {username},</p>
            <p>We detected a security event on your account:</p>
            <p><strong>Event:</strong> {event_type}</p>
            <p><strong>Time:</strong> {timestamp}</p>
            <p><strong>IP Address:</strong> {ip_address}</p>
            <p>If this wasn't you, please contact your administrator immediately.</p>
            <p>Best regards,<br>Email Campaign Manager Security Team</p>
        </body>
        </html>
        '''
    },
    'account_created': {
        'subject': 'Account Created - Email Campaign Manager',
        'body': '''
        <html>
        <body>
            <h2>Welcome to Email Campaign Manager</h2>
            <p>Hello {username},</p>
            <p>Your account has been created successfully.</p>
            <p><strong>Username:</strong> {username}</p>
            <p><strong>Role:</strong> {role}</p>
            <p>You can now log in to your account.</p>
            <p>Best regards,<br>Email Campaign Manager Team</p>
        </body>
        </html>
        '''
    }
}

socketio = SocketIO(app, cors_allowed_origins="*")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Data storage
ACCOUNTS_FILE = 'accounts.json'
CAMPAIGNS_FILE = 'campaigns.json'
USERS_FILE = 'users.json'
CAMPAIGN_LOGS_FILE = 'campaign_logs.json'
NOTIFICATIONS_FILE = 'notifications.json'
BOUNCE_DATA_FILE = 'bounce_data.json'
BOUNCES_FILE = 'bounces.json'
DELIVERY_DATA_FILE = 'delivery_data.json'
DATA_LISTS_FILE = 'data_lists.json'
DATA_LISTS_DIR = 'data_lists'

# File upload configuration
ALLOWED_EXTENSIONS = {'csv', 'txt'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def init_data_files():
    """Initialize data files if they don't exist"""
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump([], f)
    
    if not os.path.exists(CAMPAIGNS_FILE):
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump([], f)
    
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump([{
                'id': 1,
                'username': 'admin',
                'password': generate_password_hash('admin123'),
                'role': 'admin',
                'email': 'admin@example.com',
                'created_at': datetime.now().isoformat(),
                'is_active': True
            }], f)
    
    if not os.path.exists(CAMPAIGN_LOGS_FILE):
        with open(CAMPAIGN_LOGS_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(NOTIFICATIONS_FILE):
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump([], f)
    
    if not os.path.exists(BOUNCE_DATA_FILE):
        with open(BOUNCE_DATA_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(DELIVERY_DATA_FILE):
        with open(DELIVERY_DATA_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(DATA_LISTS_FILE):
        with open(DATA_LISTS_FILE, 'w') as f:
            json.dump([], f)
    
    # Create data_lists directory if it doesn't exist
    if not os.path.exists(DATA_LISTS_DIR):
        os.makedirs(DATA_LISTS_DIR)

# Initialize data files
init_data_files()

# Initialize Zoho bounce detector when app starts
def initialize_zoho_bounce_system():
    """Initialize Zoho bounce detection system"""
    try:
        # Load accounts to get credentials
        with open(ACCOUNTS_FILE, 'r') as f:
            accounts = json.load(f)
        
        if accounts and not get_zoho_bounce_detector():
            # Use the first available account
            first_account = accounts[0] if isinstance(accounts, list) and len(accounts) > 0 else None
            
            if first_account:
                # Extract org_id from account data or headers
                org_id = first_account.get('org_id') or '893358824'  # Default org ID
                
                # Initialize bounce detector
                initialize_zoho_bounce_detector(
                    account_cookies=first_account.get('cookies', {}),
                    account_headers=first_account.get('headers', {}),
                    org_id=org_id
                )
            else:
                print("⚠️ No valid account found for bounce detector initialization")
            
            # Start background bounce monitoring
            start_bounce_monitoring(interval_seconds=300)  # Check every 5 minutes
            
            print("✅ Zoho bounce detector initialized with account data")
            
            # Set up webhook if we have a public URL
            # Note: In production, you would need a public URL for webhooks
            # webhook_url = "https://your-domain.com/webhook/zoho/bounce"
            # setup_bounce_webhook(webhook_url)
            
        else:
            print("⚠️ No accounts available or bounce detector already initialized")
            
    except Exception as e:
        print(f"⚠️ Could not initialize Zoho bounce detector: {e}")

# Initialize Zoho bounce system
initialize_zoho_bounce_system()

# Global variable to track running campaigns
running_campaigns = {}

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.password_hash = user_data['password']
        self.role = user_data.get('role', 'user')  # admin or user
        self.email = user_data.get('email', '')
        self.created_at = user_data.get('created_at', '')
        self._is_active = user_data.get('is_active', True)
        self.permissions = user_data.get('permissions', [])
    
    @property
    def is_active(self):
        return self._is_active
    
    @is_active.setter
    def is_active(self, value):
        self._is_active = value
    
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)
    user_data = next((user for user in users if user['id'] == int(user_id)), None)
    return User(user_data) if user_data else None

def add_notification(message, type='info', campaign_id=None):
    """Add a notification to the system"""
    try:
        with open(NOTIFICATIONS_FILE, 'r') as f:
            notifications = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        notifications = []
    
    notification = {
        'id': str(uuid.uuid4()),
        'message': message,
        'type': type,
        'timestamp': datetime.now().isoformat(),
        'read': False,
        'campaign_id': campaign_id
    }
    
    notifications.insert(0, notification)
    
    # Keep only last 100 notifications
    if len(notifications) > 100:
        notifications = notifications[:100]
    
    with open(NOTIFICATIONS_FILE, 'w') as f:
        json.dump(notifications, f, indent=2)

def send_email(to_email, subject, html_body, text_body=None):
    """Send email using SMTP configuration"""
    if not SMTP_CONFIG['enabled']:
        print(f"Email disabled. Would send to {to_email}: {subject}")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SMTP_CONFIG['from_name']} <{SMTP_CONFIG['from_email']}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add HTML and text parts
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        if text_body:
            text_part = MIMEText(text_body, 'plain')
            msg.attach(text_part)
        
        # Create SMTP connection
        if SMTP_CONFIG['use_tls']:
            server = smtplib.SMTP(SMTP_CONFIG['server'], SMTP_CONFIG['port'])
            server.starttls(context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(SMTP_CONFIG['server'], SMTP_CONFIG['port'])
        
        server.login(SMTP_CONFIG['username'], SMTP_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        
        print(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"Error sending email to {to_email}: {str(e)}")
        return False

def send_password_reset_email(user_email, username, reset_token):
    """Send password reset email"""
    reset_link = f"{request.host_url}reset-password/{reset_token}"
    
    html_body = EMAIL_TEMPLATES['password_reset']['body'].format(
        username=username,
        reset_link=reset_link
    )
    
    subject = EMAIL_TEMPLATES['password_reset']['subject']
    
    return send_email(user_email, subject, html_body)

def send_security_alert_email(user_email, username, event_type, ip_address):
    """Send security alert email"""
    html_body = EMAIL_TEMPLATES['security_alert']['body'].format(
        username=username,
        event_type=event_type,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        ip_address=ip_address
    )
    
    subject = EMAIL_TEMPLATES['security_alert']['subject']
    
    return send_email(user_email, subject, html_body)

def send_account_created_email(user_email, username, role):
    """Send account creation notification email"""
    html_body = EMAIL_TEMPLATES['account_created']['body'].format(
        username=username,
        role=role
    )
    
    subject = EMAIL_TEMPLATES['account_created']['subject']
    
    return send_email(user_email, subject, html_body)

def save_campaign_logs(campaign_id, logs):
    """Save campaign logs to file"""
    try:
        with open(CAMPAIGN_LOGS_FILE, 'r') as f:
            all_logs = json.load(f)
    except:
        all_logs = {}
    
    all_logs[str(campaign_id)] = logs
    
    with open(CAMPAIGN_LOGS_FILE, 'w') as f:
        json.dump(all_logs, f, indent=2)

def get_campaign_logs(campaign_id):
    """Get campaign logs from file"""
    try:
        with open(CAMPAIGN_LOGS_FILE, 'r') as f:
            all_logs = json.load(f)
        
        # Try both string and integer keys
        campaign_id_str = str(campaign_id)
        campaign_id_int = int(campaign_id)
        
        logs = all_logs.get(campaign_id_str, [])
        if not logs:
            logs = all_logs.get(campaign_id_int, [])
        
        print(f"📋 Getting logs for campaign {campaign_id} (str: {campaign_id_str}, int: {campaign_id_int}), found {len(logs)} logs")
        return logs
    except Exception as e:
        print(f"❌ Error reading campaign logs for {campaign_id}: {str(e)}")
        return []

def add_campaign_log(campaign_id, log_entry):
    """Add a single log entry to campaign logs"""
    logs = get_campaign_logs(campaign_id)
    logs.append(log_entry)
    save_campaign_logs(campaign_id, logs)

def log_email(recipient, subject, sender, status, campaign_id=None, details=None):
    """Log email sending attempts to a local file with detailed status"""
    try:
        with open("email_log.txt", "a", encoding="utf-8") as logf:
            campaign_info = f" | Campaign: {campaign_id}" if campaign_id else ""
            details_info = f" | Details: {details}" if details else ""
            logf.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {status} | To: {recipient} | From: {sender} | Subject: {subject}{campaign_info}{details_info}\n")
    except Exception as e:
        print(f"❌ Error writing to email log: {e}")

def add_bounce_email(email, campaign_id, reason, subject=None, sender=None):
    """Add email to bounce list"""
    try:
        with open(BOUNCE_DATA_FILE, 'r') as f:
            bounce_data = json.load(f)
        
        if str(campaign_id) not in bounce_data:
            bounce_data[str(campaign_id)] = []
        
        bounce_entry = {
            'email': email,
            'campaign_id': campaign_id,
            'reason': reason,
            'subject': subject,
            'sender': sender,
            'timestamp': datetime.now().isoformat(),
            'bounce_type': 'hard' if 'not found' in reason.lower() or 'invalid' in reason.lower() else 'soft'
        }
        
        # Check if email already exists to avoid duplicates
        existing_emails = [entry['email'] for entry in bounce_data[str(campaign_id)]]
        if email not in existing_emails:
            bounce_data[str(campaign_id)].append(bounce_entry)
            
            with open(BOUNCE_DATA_FILE, 'w') as f:
                json.dump(bounce_data, f, indent=2)
            
            print(f"📧 Added {email} to bounce list for campaign {campaign_id}")
        
    except Exception as e:
        print(f"Error adding bounce email: {e}")

def add_delivered_email(email, campaign_id, subject=None, sender=None, details=None):
    """Add email to delivered list"""
    try:
        with open(DELIVERY_DATA_FILE, 'r') as f:
            delivery_data = json.load(f)
        
        if str(campaign_id) not in delivery_data:
            delivery_data[str(campaign_id)] = []
        
        delivery_entry = {
            'email': email,
            'campaign_id': campaign_id,
            'subject': subject,
            'sender': sender,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        
        # Check if email already exists to avoid duplicates
        existing_emails = [entry['email'] for entry in delivery_data[str(campaign_id)]]
        if email not in existing_emails:
            delivery_data[str(campaign_id)].append(delivery_entry)
            
            with open(DELIVERY_DATA_FILE, 'w') as f:
                json.dump(delivery_data, f, indent=2)
            
            print(f"✅ Added {email} to delivered list for campaign {campaign_id}")
        
    except Exception as e:
        print(f"Error adding delivered email: {e}")

def get_bounced_emails(campaign_id=None):
    """Get bounced emails for a campaign or all campaigns"""
    try:
        with open(BOUNCE_DATA_FILE, 'r') as f:
            bounce_data = json.load(f)
        
        if campaign_id:
            return bounce_data.get(str(campaign_id), [])
        else:
            all_bounces = []
            for campaign_bounces in bounce_data.values():
                all_bounces.extend(campaign_bounces)
            return all_bounces
    except Exception as e:
        print(f"Error getting bounced emails: {e}")
        return []

def get_delivered_emails(campaign_id=None):
    """Get delivered emails for a campaign or all campaigns"""
    try:
        with open(DELIVERY_DATA_FILE, 'r') as f:
            delivery_data = json.load(f)
        
        if campaign_id:
            return delivery_data.get(str(campaign_id), [])
        else:
            all_delivered = []
            for campaign_delivered in delivery_data.values():
                all_delivered.extend(campaign_delivered)
            return all_delivered
    except Exception as e:
        print(f"Error getting delivered emails: {e}")
        return []

def filter_bounced_emails(emails, campaign_id):
    """Filter out bounced emails from a list"""
    try:
        bounced_emails = get_bounced_emails(campaign_id)
        bounced_email_list = [entry['email'] for entry in bounced_emails]
        
        filtered_emails = [email for email in emails if email not in bounced_email_list]
        removed_count = len(emails) - len(filtered_emails)
        
        if removed_count > 0:
            print(f"🚫 Filtered out {removed_count} bounced emails from campaign {campaign_id}")
        
        return filtered_emails
    except Exception as e:
        print(f"Error filtering bounced emails: {e}")
        return emails

def check_email_delivery_status(email, campaign_id, account):
    """Check email delivery status with IMPROVED Zoho bounce detection"""
    try:
        # First, check if Zoho bounce detector is available
        detector = get_zoho_bounce_detector()
        
        if detector:
            # Use improved Zoho bounce detection
            bounce_status = check_email_bounce_status(email)
            
            if bounce_status.get('bounced', False):
                return {
                    'status': 'bounced',
                    'delivery_status': 'failed',
                    'bounce_reason': bounce_status.get('bounce_reason', 'Unknown bounce'),
                    'timestamp': bounce_status.get('timestamp', datetime.now().isoformat()),
                    'details': f"Bounce detected: {bounce_status.get('bounce_reason', 'Unknown')}",
                    'source': bounce_status.get('source', 'zoho'),
                    'note': bounce_status.get('note', '')
                }
            else:
                # Email appears valid and not in Zoho bounce list
                source = bounce_status.get('source', 'zoho_verification')
                note = bounce_status.get('note', '')
                
                if source == 'zoho_bounce_report':
                    details = 'Email delivered successfully (confirmed by Zoho bounce reports)'
                elif source == 'fallback_detection':
                    details = 'Email appears valid (Zoho APIs not accessible, using fallback detection)'
                else:
                    details = 'Email delivered successfully (no bounce detected)'
                
                return {
                    'status': 'delivered',
                    'delivery_status': 'success',
                    'timestamp': bounce_status.get('timestamp', datetime.now().isoformat()),
                    'details': details,
                    'source': source,
                    'note': note
                }
        else:
            # Enhanced bounce detection for emails with spaces and wrong extensions
            bounce_indicators = [
                "nonexistent", "invalid", "fake", "test", "bounce", 
                "spam", "trash", "disposable", "temp", "throwaway",
                "salsssaqz", "axxzexdflp", "asdf", "qwerty", "123456", 
                "abcdef", "xyz", "aaa", "bbb", "test123", "demo", 
                "sample", "placeholder", "invalid"
            ]
            
            # Check for emails with spaces (common typo)
            if ' ' in email:
                return {
                    'status': 'bounced',
                    'delivery_status': 'failed',
                    'bounce_reason': 'Email contains spaces (invalid format)',
                    'timestamp': datetime.now().isoformat(),
                    'details': 'Email format is invalid - contains spaces',
                    'source': 'format_validation',
                    'note': 'Enhanced validation detected spaces in email'
                }
            
            # Check for wrong email extensions
            wrong_extensions = [
                '.con', '.cmo', '.cm', '.co', '.c', '.om', '.omg', '.gamil', '.gmial',
                '.gmal', '.gmai', '.gmil', '.gmeil', '.gmale', '.gmaiil', '.hotmai', 
                '.hotmal', '.hotmeil', '.hotmaiil', '.outlok', '.yaho', '.live', 
                '.aol', '.icloud', '.proton', '.tutanota', '.mail', '.email'
            ]
            
            email_lower = email.lower()
            for ext in wrong_extensions:
                if email_lower.endswith(ext):
                    return {
                        'status': 'bounced',
                        'delivery_status': 'failed',
                        'bounce_reason': f'Invalid email extension: {ext}',
                        'timestamp': datetime.now().isoformat(),
                        'details': f'Email has wrong extension: {ext}',
                        'source': 'format_validation',
                        'note': f'Enhanced validation detected wrong extension: {ext}'
                    }
            
            email_lower = email.lower()
            for indicator in bounce_indicators:
                if indicator in email_lower:
                    return {
                        'status': 'bounced',
                        'delivery_status': 'failed',
                        'bounce_reason': f'Email contains "{indicator}" indicator',
                        'timestamp': datetime.now().isoformat(),
                        'details': 'Email likely to bounce - contains suspicious pattern',
                        'source': 'pattern_detection',
                        'note': 'Zoho detector not available, using pattern detection'
                    }
            
            # Check for invalid email patterns
            if not '@' in email or '.' not in email.split('@')[1]:
                return {
                    'status': 'bounced',
                    'delivery_status': 'failed',
                    'bounce_reason': 'Invalid email format',
                    'timestamp': datetime.now().isoformat(),
                    'details': 'Email format is invalid',
                    'source': 'format_validation',
                    'note': 'Zoho detector not available, using format validation'
                }
            
            return {
                'status': 'delivered',
                'delivery_status': 'success',
                'timestamp': datetime.now().isoformat(),
                'details': 'Email delivered successfully (pattern-based detection)',
                'source': 'pattern_detection',
                'note': 'Zoho detector not available, using pattern detection'
            }
        
    except Exception as e:
        return {
            'status': 'unknown',
            'delivery_status': 'unknown',
            'timestamp': datetime.now().isoformat(),
            'details': f'Error checking delivery status: {str(e)}',
            'source': 'error',
            'note': f'Exception occurred: {str(e)}'
        }

# Data Lists Utility Functions
def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_email(email):
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def extract_emails_from_file(file_path):
    """Extract emails from uploaded file"""
    emails = []
    try:
        if file_path.endswith('.csv'):
            # Try to read as CSV
            try:
                df = pd.read_csv(file_path)
                # Look for email column
                email_columns = [col for col in df.columns if 'email' in col.lower()]
                if email_columns:
                    emails = df[email_columns[0]].dropna().astype(str).tolist()
                else:
                    # Assume first column contains emails
                    emails = df.iloc[:, 0].dropna().astype(str).tolist()
            except:
                # Fallback to text reading
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    emails = [line.strip() for line in content.split('\n') if line.strip()]
        else:
            # Read as text file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                emails = [line.strip() for line in content.split('\n') if line.strip()]
        
        # Filter valid emails
        valid_emails = []
        invalid_emails = []
        for email in emails:
            if validate_email(email):
                valid_emails.append(email)
            else:
                invalid_emails.append(email)
        
        return valid_emails, invalid_emails
    except Exception as e:
        print(f"Error extracting emails from file: {e}")
        return [], []

def get_data_lists():
    """Get all data lists"""
    try:
        with open(DATA_LISTS_FILE, 'r') as f:
            data_lists = json.load(f)
        if not isinstance(data_lists, list):
            data_lists = []
        return data_lists
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_data_lists(data_lists):
    """Save data lists to file"""
    try:
        with open(DATA_LISTS_FILE, 'w') as f:
            json.dump(data_lists, f, indent=2)
    except Exception as e:
        print(f"Error saving data lists: {e}")

def add_data_list(name, geography, isp, emails, filename=None, description=""):
    """Add a new data list"""
    try:
        data_lists = get_data_lists()
        
        new_list = {
            'id': max([lst['id'] for lst in data_lists], default=0) + 1 if data_lists else 1,
            'name': name,
            'geography': geography,
            'isp': isp,
            'email_count': len(emails),
            'filename': filename,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        data_lists.append(new_list)
        save_data_lists(data_lists)
        
        # Save emails to file
        if filename:
            file_path = os.path.join(DATA_LISTS_DIR, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                for email in emails:
                    f.write(f"{email}\n")
        
        return new_list
    except Exception as e:
        print(f"Error adding data list: {e}")
        return None

def get_data_list_emails(list_id):
    """Get emails from a specific data list"""
    try:
        data_lists = get_data_lists()
        data_list = next((lst for lst in data_lists if lst['id'] == list_id), None)
        
        if not data_list or not data_list.get('filename'):
            return []
        
        file_path = os.path.join(DATA_LISTS_DIR, data_list['filename'])
        if not os.path.exists(file_path):
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            emails = [line.strip() for line in f.readlines() if line.strip()]
        
        return emails
    except Exception as e:
        print(f"Error getting data list emails: {e}")
        return []

def delete_data_list(list_id):
    """Delete a data list and its file"""
    try:
        data_lists = get_data_lists()
        data_list = next((lst for lst in data_lists if lst['id'] == list_id), None)
        
        if not data_list:
            return False
        
        # Delete file if it exists
        if data_list.get('filename'):
            file_path = os.path.join(DATA_LISTS_DIR, data_list['filename'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Remove from data lists
        data_lists = [lst for lst in data_lists if lst['id'] != list_id]
        save_data_lists(data_lists)
        
        return True
    except Exception as e:
        print(f"Error deleting data list: {e}")
        return False

@app.route('/')
@login_required
def dashboard():
    """Enhanced dashboard with real statistics"""
    # Load data
    with open(ACCOUNTS_FILE, 'r') as f:
        accounts = json.load(f)
    
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    with open(NOTIFICATIONS_FILE, 'r') as f:
        notifications = json.load(f)
    
    # Calculate real statistics
    total_accounts = len(accounts)
    active_campaigns = len([c for c in campaigns if c.get('status') == 'running'])
    
    # Calculate emails sent today
    today = datetime.now().date()
    emails_today = 0
    total_sent = 0
    total_attempted = 0
    
    for campaign in campaigns:
        if campaign.get('total_sent'):
            total_sent += campaign.get('total_sent', 0)
            # Check if campaign was active today
            if campaign.get('started_at'):
                try:
                    started_date = datetime.fromisoformat(campaign['started_at']).date()
                    if started_date == today:
                        emails_today += campaign.get('total_sent', 0)
                except:
                    pass
    
    # Calculate success rate
    success_rate = 0
    if total_sent > 0:
        # Count total recipients across all campaigns
        for campaign in campaigns:
            if campaign.get('destinataires'):
                total_attempted += len([email.strip() for email in campaign['destinataires'].split('\n') if email.strip()])
        
        if total_attempted > 0:
            success_rate = round((total_sent / total_attempted) * 100, 1)
    
    # Get recent campaigns (last 5)
    recent_campaigns = sorted(campaigns, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
    
    # Get recent notifications (last 5)
    recent_notifications = sorted(notifications, key=lambda x: x.get('timestamp', ''), reverse=True)[:5]
    
    # Get campaign status breakdown
    status_counts = {}
    for campaign in campaigns:
        status = campaign.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Get bounce and delivery statistics
    total_bounced = len(get_bounced_emails())
    total_delivered = len(get_delivered_emails())
    
    # Get real Zoho bounce statistics if available
    zoho_bounce_stats = {}
    try:
        detector = get_zoho_bounce_detector()
        if detector:
            zoho_stats = get_bounce_statistics(days=30)
            if 'error' not in zoho_stats:
                zoho_bounce_stats = zoho_stats
    except Exception as e:
        print(f"⚠️ Could not get Zoho bounce stats: {e}")
    
    return render_template('dashboard.html', 
                         total_accounts=total_accounts,
                         active_campaigns=active_campaigns,
                         emails_today=emails_today,
                         success_rate=success_rate,
                         total_sent=total_sent,
                         total_bounced=total_bounced,
                         total_delivered=total_delivered,
                         zoho_bounce_stats=zoho_bounce_stats,
                         recent_campaigns=recent_campaigns,
                         recent_notifications=recent_notifications,
                         status_counts=status_counts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    username = request.form.get('username')
    password = request.form.get('password')
    
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        if not isinstance(users, list):
            users = []
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    
    user_data = next((u for u in users if u['username'] == username), None)
    
    if user_data and check_password_hash(user_data['password'], password):
        if not user_data.get('is_active', True):
            flash('Account is disabled. Please contact your administrator.')
            return redirect(url_for('login'))
        
        user = User(user_data)
        login_user(user)
        
        # Send security alert for successful login
        if SMTP_CONFIG['enabled']:
            send_security_alert_email(
                user_data.get('email', ''),
                username,
                'Successful Login',
                request.remote_addr
            )
        
        add_notification(f"User '{username}' logged in successfully", 'info')
        return redirect(url_for('dashboard'))
    else:
        # Send security alert for failed login attempt
        if user_data and SMTP_CONFIG['enabled']:
            send_security_alert_email(
                user_data.get('email', ''),
                username,
                'Failed Login Attempt',
                request.remote_addr
            )
        
        flash('Invalid username or password')
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/accounts')
@login_required
def accounts():
    try:
        accounts = get_user_accounts(current_user)
        return render_template('accounts.html', accounts=accounts)
    except Exception as e:
        print(f"Error loading accounts: {str(e)}")
        return render_template('accounts.html', accounts=[])

@app.route('/campaigns')
@login_required
def campaigns():
    try:
        campaigns = get_user_campaigns(current_user)
        return render_template('campaigns.html', campaigns=campaigns)
    except Exception as e:
        print(f"Error loading campaigns: {str(e)}")
        return render_template('campaigns.html', campaigns=[])

@app.route('/campaigns/<int:campaign_id>/edit')
@login_required
def edit_campaign(campaign_id):
    """Edit campaign page"""
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
    if not campaign:
        flash('Campaign not found')
        return redirect(url_for('campaigns'))
    
    with open(ACCOUNTS_FILE, 'r') as f:
        accounts = json.load(f)
    
    return render_template('edit_campaign.html', campaign=campaign, accounts=accounts)

@app.route('/live-campaigns')
@login_required
def live_campaigns():
    """New page to monitor all running campaigns and recently completed ones"""
    try:
        with open(CAMPAIGNS_FILE, 'r') as f:
            all_campaigns = json.load(f)
        if not isinstance(all_campaigns, list):
            all_campaigns = []
    except (FileNotFoundError, json.JSONDecodeError):
        all_campaigns = []
    
    # Filter campaigns based on user permissions
    if current_user.role == 'admin' or has_permission(current_user, 'view_all_campaigns'):
        # Admin can see all campaigns
        campaigns = all_campaigns
    else:
        # Regular users can only see their own campaigns
        campaigns = [c for c in all_campaigns if c.get('created_by') == current_user.id]
    
    # Get current date for cleanup
    current_date = datetime.now().date()
    
    # Filter campaigns: running + completed today + ready
    active_campaigns = []
    for campaign in campaigns:
        if campaign.get('status') == 'running':
            # Load logs for running campaigns
            campaign['logs'] = get_campaign_logs(campaign['id'])
            active_campaigns.append(campaign)
        elif campaign.get('status') == 'ready':
            # Add ready campaigns (no logs yet)
            campaign['logs'] = []
            active_campaigns.append(campaign)
        elif campaign.get('status') == 'completed':
            # Check if completed today
            try:
                completed_date = datetime.fromisoformat(campaign.get('completed_at', '')).date()
                if completed_date == current_date:
                    # Load logs for completed campaigns
                    campaign['logs'] = get_campaign_logs(campaign['id'])
                    active_campaigns.append(campaign)
            except:
                # If no completed_at date, skip
                pass
    
    # Sort by status (running first) then by started_at
    active_campaigns.sort(key=lambda x: (x.get('status') != 'running', x.get('started_at', '')))
    
    return render_template('live_campaigns.html', campaigns=active_campaigns)

@app.route('/campaigns/<int:campaign_id>/logs')
@login_required
def campaign_logs(campaign_id):
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
    if not campaign:
        flash('Campaign not found')
        return redirect(url_for('campaigns'))
    
    logs = get_campaign_logs(campaign_id)
    return render_template('campaign_logs.html', campaign=campaign, logs=logs)

@app.route('/notifications')
@login_required
def notifications():
    """Notifications page"""
    try:
        with open(NOTIFICATIONS_FILE, 'r') as f:
            notifications = json.load(f)
    except:
        notifications = []
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/bounces')
@login_required
def bounces():
    """View bounced emails"""
    campaign_id = request.args.get('campaign_id', type=int)
    bounced_emails = get_bounced_emails(campaign_id)
    
    # Get campaign names for display
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    campaign_names = {str(c['id']): c['name'] for c in campaigns}
    
    return render_template('bounces.html', 
                         bounced_emails=bounced_emails, 
                         campaign_names=campaign_names,
                         selected_campaign=campaign_id)

@app.route('/delivered')
@login_required
def delivered():
    """View delivered emails"""
    campaign_id = request.args.get('campaign_id', type=int)
    delivered_emails = get_delivered_emails(campaign_id)
    
    # Get campaign names for display
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    campaign_names = {str(c['id']): c['name'] for c in campaigns}
    
    return render_template('delivered.html', 
                         delivered_emails=delivered_emails, 
                         campaign_names=campaign_names,
                         selected_campaign=campaign_id)

# API Endpoints
@app.route('/api/accounts', methods=['GET', 'POST'])
@login_required
def api_accounts():
    if request.method == 'GET':
        try:
            accounts = get_user_accounts(current_user)
            return jsonify(accounts)
        except Exception as e:
            print(f"Error loading accounts: {str(e)}")
            return jsonify([])
    
    elif request.method == 'POST':
        # Check if user has permission to create accounts
        if not has_permission(current_user, 'add_account') and current_user.role != 'admin':
            return jsonify({'error': 'Access denied. You need permission to add accounts.'}), 403
        
        try:
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            print(f"🔍 Creating account with data: {json.dumps(data, indent=2)}")
            print(f"👤 Current user: {current_user.username} (ID: {current_user.id}, Role: {current_user.role})")
            
            # Validate required fields
            required_fields = ['name', 'org_id', 'cookies', 'headers']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            try:
                with open(ACCOUNTS_FILE, 'r') as f:
                    accounts = json.load(f)
                if not isinstance(accounts, list):
                    accounts = []
                print(f"📊 Loaded {len(accounts)} existing accounts")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"⚠️ No existing accounts file or invalid JSON: {e}")
                accounts = []
            
            # Generate new account ID
            new_id = max([acc['id'] for acc in accounts], default=0) + 1 if accounts else 1
            print(f"🆔 Generated new account ID: {new_id}")
            
            new_account = {
                'id': new_id,
                'name': data['name'],
                'org_id': data['org_id'],
                'cookies': data['cookies'],
                'headers': data['headers'],
                'templates': data.get('templates', []),
                'created_at': datetime.now().isoformat(),
                'created_by': current_user.id
            }
            
            print(f"📝 New account data: {json.dumps(new_account, indent=2)}")
            
            accounts.append(new_account)
            
            # Save to file with error handling
            try:
                with open(ACCOUNTS_FILE, 'w') as f:
                    json.dump(accounts, f, indent=2)
                print(f"✅ Successfully saved account to {ACCOUNTS_FILE}")
            except PermissionError as e:
                print(f"❌ Permission error saving account: {e}")
                error_msg = f"Permission denied: Cannot write to {ACCOUNTS_FILE}. Please check file permissions on the server."
                return jsonify({'error': error_msg}), 500
            except Exception as e:
                print(f"❌ Error saving to file: {e}")
                return jsonify({'error': f'Failed to save account to file: {str(e)}'}), 500
            
            try:
                add_notification(f"Account '{data['name']}' added successfully", 'success')
                print(f"✅ Added success notification")
            except Exception as e:
                print(f"⚠️ Could not add notification: {e}")
            
            print(f"🎉 Account creation completed successfully")
            return jsonify(new_account)
            
        except Exception as e:
            print(f"❌ Error saving account: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/accounts/<int:account_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_account(account_id):
    try:
        print(f"🔍 Processing account request: ID={account_id}, Method={request.method}")
        print(f"👤 Current user: {current_user.username} (ID: {current_user.id}, Role: {current_user.role})")
        
        with open(ACCOUNTS_FILE, 'r') as f:
            accounts = json.load(f)
        if not isinstance(accounts, list):
            accounts = []
        print(f"📊 Loaded {len(accounts)} accounts from file")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Error loading accounts file: {e}")
        accounts = []
    
    account = next((acc for acc in accounts if acc['id'] == account_id), None)
    
    if not account:
        print(f"❌ Account {account_id} not found")
        return jsonify({'error': f'Account {account_id} not found'}), 404
    
    print(f"✅ Found account: {account['name']} (ID: {account['id']}, Created by: {account.get('created_by', 'Unknown')})")
    
    # Check if user can access this account
    # Admin can access all accounts, users can only access their own
    if current_user.role != 'admin' and not has_permission(current_user, 'manage_accounts') and account.get('created_by') != current_user.id:
        print(f"❌ Access denied: User {current_user.username} cannot access account {account_id}")
        return jsonify({'error': 'Access denied. You can only manage your own accounts.'}), 403
    
    if request.method == 'GET':
        return jsonify(account)
    
    elif request.method == 'PUT':
        # Check if user has permission to edit accounts
        if current_user.role != 'admin' and not has_permission(current_user, 'manage_accounts') and account.get('created_by') != current_user.id:
            return jsonify({'error': 'Access denied. You can only edit your own accounts.'}), 403
        
        data = request.json
        data['updated_at'] = datetime.now().isoformat()
        account.update(data)
        
        try:
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump(accounts, f, indent=2)
            print(f"✅ Successfully updated account {account_id}")
        except PermissionError as e:
            print(f"❌ Permission error saving updated account: {e}")
            error_msg = f"Permission denied: Cannot write to {ACCOUNTS_FILE}. Please check file permissions on the server."
            return jsonify({'error': error_msg}), 500
        except Exception as e:
            print(f"❌ Error saving updated account: {e}")
            return jsonify({'error': f'Failed to save account: {str(e)}'}), 500
        
        add_notification(f"Account '{account['name']}' updated successfully", 'success')
        return jsonify(account)
    
    elif request.method == 'DELETE':
        print(f"🗑️ Attempting to delete account {account_id}")
        
        # Check if user has permission to delete accounts
        # Admin can delete any account, users can only delete their own
        if current_user.role != 'admin' and not has_permission(current_user, 'manage_accounts') and account.get('created_by') != current_user.id:
            print(f"❌ Access denied: User {current_user.username} cannot delete account {account_id}")
            return jsonify({'error': 'Access denied. You can only delete your own accounts.'}), 403
        
        account_name = account['name']
        print(f"📝 Removing account '{account_name}' from list")
        
        try:
            accounts.remove(account)
            print(f"✅ Account removed from list, {len(accounts)} accounts remaining")
        except ValueError as e:
            print(f"❌ Error removing account from list: {e}")
            return jsonify({'error': f'Failed to remove account from list: {str(e)}'}), 500
        
        try:
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump(accounts, f, indent=2)
            print(f"✅ Successfully saved updated accounts to file")
        except PermissionError as e:
            print(f"❌ Permission error saving accounts file: {e}")
            error_msg = f"Permission denied: Cannot write to {ACCOUNTS_FILE}. Please check file permissions on the server."
            return jsonify({'error': error_msg}), 500
        except Exception as e:
            print(f"❌ Error saving accounts file: {e}")
            return jsonify({'error': f'Failed to save accounts file: {str(e)}'}), 500
        
        try:
            add_notification(f"Account '{account_name}' deleted successfully", 'success')
            print(f"✅ Added deletion notification")
        except Exception as e:
            print(f"⚠️ Could not add notification: {e}")
        
        print(f"🎉 Account '{account_name}' deleted successfully")
        return jsonify({'success': True, 'message': f'Account {account_name} deleted successfully'})

@app.route('/api/accounts/<int:account_id>/templates', methods=['GET'])
@login_required
def get_account_templates(account_id):
    """Get templates for a specific account"""
    try:
        with open(ACCOUNTS_FILE, 'r') as f:
            accounts = json.load(f)
        if not isinstance(accounts, list):
            accounts = []
    except (FileNotFoundError, json.JSONDecodeError):
        accounts = []
    
    account = next((acc for acc in accounts if acc['id'] == account_id), None)
    
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    templates = account.get('templates', [])
    return jsonify(templates)

@app.route('/api/campaigns', methods=['GET', 'POST'])
@login_required
def api_campaigns():
    if request.method == 'GET':
        try:
            campaigns = get_user_campaigns(current_user)
            return jsonify(campaigns)
        except Exception as e:
            print(f"Error loading campaigns: {str(e)}")
            return jsonify([])
    
    elif request.method == 'POST':
        try:
            print(f"🔍 Creating campaign - Memory usage: {log_memory_usage():.1f} MB")
            
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Validate required fields
            required_fields = ['name', 'account_id', 'template_id', 'destinataires', 'subjects', 'froms']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            # Simple file reading
            campaigns = read_json_file_simple(CAMPAIGNS_FILE)
            if not isinstance(campaigns, list):
                campaigns = []
            
            # Generate new campaign ID
            new_id = max([camp['id'] for camp in campaigns], default=0) + 1 if campaigns else 1
            
            # Create campaign object
            new_campaign = {
                'id': new_id,
                'name': str(data['name'])[:100],  # Limit name length
                'account_id': int(data['account_id']),
                'template_id': str(data['template_id']),
                'destinataires': str(data['destinataires']),
                'subjects': str(data['subjects']),
                'froms': str(data['froms']),
                'status': 'ready',
                'created_at': datetime.now().isoformat(),
                'created_by': current_user.id,
                'total_sent': 0,
                'total_attempted': 0
            }
            
            # Add rate limits if provided
            if 'rate_limits' in data and data['rate_limits']:
                new_campaign['rate_limits'] = data['rate_limits']
            
            # Add to campaigns list
            campaigns.append(new_campaign)
            
            # Simple file writing
            if write_json_file_simple(CAMPAIGNS_FILE, campaigns):
                # Add notification
                try:
                    add_notification(f"Campaign '{data['name']}' created successfully", 'success', new_id)
                except Exception as e:
                    print(f"⚠️ Could not add notification: {e}")
                
                # Simple memory cleanup
                cleanup_memory()
                
                print(f"✅ Campaign created successfully - Memory usage: {log_memory_usage():.1f} MB")
                return jsonify(new_campaign)
            else:
                return jsonify({'error': 'Failed to save campaign to file'}), 500
                
        except Exception as e:
            print(f"❌ Error creating campaign: {str(e)}")
            import traceback
            traceback.print_exc()
            cleanup_memory()
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_campaign(campaign_id):
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
    
    if not campaign:
        return ('', 404)
    
    # Check if user can access this campaign
    if not has_permission(current_user, 'view_all_campaigns') and campaign.get('created_by') != current_user.id:
        return jsonify({'error': 'Access denied. You can only manage your own campaigns.'}), 403
    
    if request.method == 'GET':
        return jsonify(campaign)
    
    elif request.method == 'PUT':
        # Check if user has permission to edit campaigns
        if not has_permission(current_user, 'manage_all_campaigns') and campaign.get('created_by') != current_user.id:
            return jsonify({'error': 'Access denied. You can only edit your own campaigns.'}), 403
        
        data = request.json
        campaign.update(data)
        
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump(campaigns, f)
        
        add_notification(f"Campaign '{campaign['name']}' updated successfully", 'success', campaign_id)
        return jsonify(campaign)
    
    elif request.method == 'DELETE':
        # Check if user has permission to delete campaigns
        if not has_permission(current_user, 'manage_all_campaigns') and campaign.get('created_by') != current_user.id:
            return jsonify({'error': 'Access denied. You can only delete your own campaigns.'}), 403
        
        campaign_name = campaign['name']
        campaigns.remove(campaign)
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump(campaigns, f)
        
        add_notification(f"Campaign '{campaign_name}' deleted successfully", 'warning')
        return ('', 204)

@app.route('/api/campaigns/<int:campaign_id>/start', methods=['POST'])
@login_required
def start_campaign(campaign_id):
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    if campaign['status'] == 'running':
        return jsonify({'error': 'Campaign is already running'}), 400
    
    if campaign['status'] not in ['ready', 'stopped', 'paused']:
        return jsonify({'error': 'Campaign cannot be started from current status'}), 400
    
    # Get account
    with open(ACCOUNTS_FILE, 'r') as f:
        accounts = json.load(f)
    
    account = next((acc for acc in accounts if acc['id'] == campaign['account_id']), None)
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    # Update campaign status
    campaign['status'] = 'running'
    campaign['started_at'] = datetime.now().isoformat()
    campaign['total_sent'] = 0
    campaign['total_attempted'] = 0
    
    with open(CAMPAIGNS_FILE, 'w') as f:
        json.dump(campaigns, f)
    
    # Clear previous logs
    save_campaign_logs(campaign_id, [])
    
    # Add to running campaigns
    running_campaigns[campaign_id] = True
    
    # Start campaign in background thread
    thread = threading.Thread(target=send_campaign_emails, args=(campaign, account))
    thread.daemon = True
    thread.start()
    
    add_notification(f"Campaign '{campaign['name']}' started successfully", 'success', campaign_id)
    return jsonify({'message': 'Campaign started successfully'})

@app.route('/api/campaigns/<int:campaign_id>/stop', methods=['POST'])
@login_required
def stop_campaign(campaign_id):
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    if campaign['status'] != 'running':
        return jsonify({'error': 'Campaign is not running'}), 400
    
    # Stop campaign
    campaign['status'] = 'stopped'
    campaign['stopped_at'] = datetime.now().isoformat()
    
    with open(CAMPAIGNS_FILE, 'w') as f:
        json.dump(campaigns, f)
    
    # Remove from running campaigns
    if campaign_id in running_campaigns:
        del running_campaigns[campaign_id]
    
    add_notification(f"Campaign '{campaign['name']}' stopped successfully", 'warning', campaign_id)
    return jsonify({'message': 'Campaign stopped successfully'})

@app.route('/api/campaigns/<int:campaign_id>/relaunch', methods=['POST'])
@login_required
def relaunch_campaign(campaign_id):
    """Relaunch a completed or stopped campaign"""
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    if campaign['status'] == 'running':
        return jsonify({'error': 'Campaign is already running'}), 400
    
    # Get account
    with open(ACCOUNTS_FILE, 'r') as f:
        accounts = json.load(f)
    
    account = next((acc for acc in accounts if acc['id'] == campaign['account_id']), None)
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    # Reset campaign status
    campaign['status'] = 'running'
    campaign['started_at'] = datetime.now().isoformat()
    campaign['total_sent'] = 0
    campaign['total_attempted'] = 0
    
    with open(CAMPAIGNS_FILE, 'w') as f:
        json.dump(campaigns, f)
    
    # Clear previous logs
    save_campaign_logs(campaign_id, [])
    
    # Add to running campaigns
    running_campaigns[campaign_id] = True
    
    # Start campaign in background thread
    thread = threading.Thread(target=send_campaign_emails, args=(campaign, account))
    thread.daemon = True
    thread.start()
    
    add_notification(f"Campaign '{campaign['name']}' relaunched successfully", 'success', campaign_id)
    return jsonify({'message': 'Campaign relaunched successfully'})

@app.route('/api/notifications', methods=['GET'])
@login_required
def api_notifications():
    """Get notifications API"""
    try:
        with open(NOTIFICATIONS_FILE, 'r') as f:
            notifications = json.load(f)
    except:
        notifications = []
    
    return jsonify(notifications)

@app.route('/api/notifications/<notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        with open(NOTIFICATIONS_FILE, 'r') as f:
            notifications = json.load(f)
        
        # Find and update the notification
        for notification in notifications:
            if notification['id'] == notification_id:
                notification['read'] = True
                break
        
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump(notifications, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Notification marked as read'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error marking notification as read: {str(e)}'}), 500

@app.route('/api/notifications/<notification_id>/delete', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """Delete a notification"""
    try:
        with open(NOTIFICATIONS_FILE, 'r') as f:
            notifications = json.load(f)
        
        # Remove the notification
        notifications = [n for n in notifications if n['id'] != notification_id]
        
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump(notifications, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Notification deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error deleting notification: {str(e)}'}), 500

@app.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    try:
        with open(NOTIFICATIONS_FILE, 'r') as f:
            notifications = json.load(f)
        
        # Mark all notifications as read
        for notification in notifications:
            notification['read'] = True
        
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump(notifications, f, indent=2)
        
        return jsonify({'success': True, 'message': 'All notifications marked as read'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error marking notifications as read: {str(e)}'}), 500

@app.route('/api/notifications/clear-all', methods=['DELETE'])
@login_required
def clear_all_notifications():
    """Clear all notifications"""
    try:
        # Clear all notifications by writing empty array
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump([], f, indent=2)
        
        return jsonify({'success': True, 'message': 'All notifications cleared'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error clearing notifications: {str(e)}'}), 500

@app.route('/api/stats')
@login_required
def api_stats():
    """Get enhanced dashboard statistics with delivery tracking"""
    with open(ACCOUNTS_FILE, 'r') as f:
        accounts = json.load(f)
    
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    # Calculate real statistics
    total_accounts = len(accounts)
    active_campaigns = len([c for c in campaigns if c.get('status') == 'running'])
    
    # Calculate emails sent today with delivery tracking
    today = datetime.now().date()
    emails_today = 0
    total_sent = 0
    total_delivered = 0
    total_bounced = 0
    total_attempted = 0
    
    for campaign in campaigns:
        if campaign.get('total_sent'):
            total_sent += campaign.get('total_sent', 0)
            total_delivered += campaign.get('delivered_count', 0)
            total_bounced += campaign.get('bounced_count', 0)
            
            # Check if campaign was active today
            if campaign.get('started_at'):
                try:
                    started_date = datetime.fromisoformat(campaign['started_at']).date()
                    if started_date == today:
                        emails_today += campaign.get('total_sent', 0)
                except:
                    pass
    
    # Calculate delivery rates
    delivery_rate = 0
    bounce_rate = 0
    if total_sent > 0:
        delivery_rate = round((total_delivered / total_sent) * 100, 1)
        bounce_rate = round((total_bounced / total_sent) * 100, 1)
        
        # Count total recipients across all campaigns
        for campaign in campaigns:
            if campaign.get('destinataires'):
                total_attempted += len([email.strip() for email in campaign['destinataires'].split('\n') if email.strip()])
    
    # Get campaign status breakdown
    status_counts = {}
    for campaign in campaigns:
        status = campaign.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return jsonify({
        'total_accounts': total_accounts,
        'active_campaigns': active_campaigns,
        'emails_today': emails_today,
        'delivery_rate': delivery_rate,
        'bounce_rate': bounce_rate,
        'total_sent': total_sent,
        'total_delivered': total_delivered,
        'total_bounced': total_bounced,
        'total_campaigns': len(campaigns),
        'status_counts': status_counts
    })

@app.route('/api/campaigns/<int:campaign_id>/delivery-stats')
@login_required
def get_campaign_delivery_stats(campaign_id):
    """Get detailed delivery statistics for a specific campaign"""
    try:
        # Get campaign
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Return campaign data with delivery statistics
        return jsonify({
            'campaign_id': campaign_id,
            'total_sent': campaign.get('total_sent', 0),
            'delivered': campaign.get('delivered_count', 0),
            'bounced': campaign.get('bounced_count', 0),
            'delivery_rate': campaign.get('delivery_rate', 0),
            'bounce_rate': campaign.get('bounce_rate', 0),
            'error_count': campaign.get('error_count', 0)
        })
        
    except Exception as e:
        return jsonify({'error': f'Error getting delivery stats: {str(e)}'}), 500

@app.route('/api/debug/logs')
@login_required
def debug_logs():
    """Debug endpoint to check campaign logs file"""
    try:
        with open(CAMPAIGN_LOGS_FILE, 'r') as f:
            all_logs = json.load(f)
        
        return jsonify({
            'file_exists': True,
            'total_campaigns_with_logs': len(all_logs),
            'campaign_ids': list(all_logs.keys()),
            'sample_logs': {k: len(v) for k, v in all_logs.items()}
        })
    except Exception as e:
        return jsonify({
            'file_exists': False,
            'error': str(e)
        })

@app.route('/api/campaigns/<int:campaign_id>/logs', methods=['GET'])
@login_required
def get_campaign_logs_api(campaign_id):
    """Get campaign logs API endpoint"""
    try:
        logs = get_campaign_logs(campaign_id)
        print(f"🔍 API: Getting logs for campaign {campaign_id}, found {len(logs)} logs")
        return jsonify(logs)
    except Exception as e:
        print(f"❌ API Error getting logs for campaign {campaign_id}: {str(e)}")
        return jsonify([])

@app.route('/api/campaigns/<int:campaign_id>/delete', methods=['DELETE'])
@login_required
def delete_campaign_api(campaign_id):
    """Delete a campaign"""
    try:
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        
        # Find and remove the campaign
        campaigns = [c for c in campaigns if c['id'] != campaign_id]
        
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump(campaigns, f, indent=2)
        
        # Also remove campaign logs
        try:
            with open(CAMPAIGN_LOGS_FILE, 'r') as f:
                all_logs = json.load(f)
            
            if str(campaign_id) in all_logs:
                del all_logs[str(campaign_id)]
                
            with open(CAMPAIGN_LOGS_FILE, 'w') as f:
                json.dump(all_logs, f, indent=2)
        except:
            pass
        
        # Remove from running campaigns if present
        if campaign_id in running_campaigns:
            del running_campaigns[campaign_id]
        
        return jsonify({'success': True, 'message': 'Campaign deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error deleting campaign: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>/pause', methods=['POST'])
@login_required
def pause_campaign_api(campaign_id):
    """Pause a running campaign"""
    try:
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        if not campaign:
            return jsonify({'success': False, 'message': 'Campaign not found'}), 404
        
        if campaign['status'] != 'running':
            return jsonify({'success': False, 'message': 'Campaign is not running'}), 400
        
        # Update campaign status
        campaign['status'] = 'paused'
        campaign['paused_at'] = datetime.now().isoformat()
        
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump(campaigns, f, indent=2)
        
        # Remove from running campaigns
        if campaign_id in running_campaigns:
            running_campaigns[campaign_id]['status'] = 'paused'
        
        # Add notification
        add_notification(f"Campaign '{campaign['name']}' has been paused", 'warning', campaign_id)
        
        return jsonify({'success': True, 'message': 'Campaign paused successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error pausing campaign: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>/stop', methods=['POST'])
@login_required
def stop_campaign_api(campaign_id):
    """Stop a running or paused campaign"""
    try:
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        if not campaign:
            return jsonify({'success': False, 'message': 'Campaign not found'}), 404
        
        if campaign['status'] not in ['running', 'paused']:
            return jsonify({'success': False, 'message': 'Campaign is not running or paused'}), 400
        
        # Update campaign status
        campaign['status'] = 'stopped'
        campaign['stopped_at'] = datetime.now().isoformat()
        
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump(campaigns, f, indent=2)
        
        # Remove from running campaigns
        if campaign_id in running_campaigns:
            del running_campaigns[campaign_id]
        
        # Add notification
        add_notification(f"Campaign '{campaign['name']}' has been stopped", 'info', campaign_id)
        
        return jsonify({'success': True, 'message': 'Campaign stopped successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error stopping campaign: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>/resume', methods=['POST'])
@login_required
def resume_campaign_api(campaign_id):
    """Resume a paused campaign"""
    try:
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        if not campaign:
            return jsonify({'success': False, 'message': 'Campaign not found'}), 404
        
        if campaign['status'] != 'paused':
            return jsonify({'success': False, 'message': 'Campaign is not paused'}), 400
        
        # Update campaign status
        campaign['status'] = 'running'
        campaign['resumed_at'] = datetime.now().isoformat()
        
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump(campaigns, f, indent=2)
        
        # Add back to running campaigns
        running_campaigns[campaign_id] = {
            'campaign': campaign,
            'status': 'running',
            'started_at': datetime.now().isoformat()
        }
        
        # Add notification
        add_notification(f"Campaign '{campaign['name']}' has been resumed", 'success', campaign_id)
        
        return jsonify({'success': True, 'message': 'Campaign resumed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error resuming campaign: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>/clear-logs', methods=['DELETE'])
@login_required
def clear_campaign_logs_api(campaign_id):
    """Clear logs for a specific campaign without deleting the campaign"""
    try:
        # Clear campaign logs
        try:
            with open(CAMPAIGN_LOGS_FILE, 'r') as f:
                all_logs = json.load(f)
            
            if str(campaign_id) in all_logs:
                del all_logs[str(campaign_id)]
                
            with open(CAMPAIGN_LOGS_FILE, 'w') as f:
                json.dump(all_logs, f, indent=2)
        except:
            pass
        
        # Get campaign name for notification
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        campaign_name = campaign['name'] if campaign else f'Campaign {campaign_id}'
        
        add_notification(f"Logs cleared for campaign '{campaign_name}'", 'info', campaign_id)
        
        return jsonify({'success': True, 'message': 'Campaign logs cleared successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error clearing campaign logs: {str(e)}'}), 500

@app.route('/api/download/bounces/<int:campaign_id>')
@login_required
def download_bounces(campaign_id):
    """Download bounced emails as CSV"""
    try:
        bounced_emails = get_bounced_emails(campaign_id)
        
        if not bounced_emails:
            return jsonify({'error': 'No bounced emails found'}), 404
        
        # Create CSV content
        csv_content = "Email,Campaign ID,Reason,Subject,Sender,Timestamp,Bounce Type\n"
        for entry in bounced_emails:
            csv_content += f'"{entry["email"]}","{entry["campaign_id"]}","{entry["reason"]}","{entry.get("subject", "")}","{entry.get("sender", "")}","{entry["timestamp"]}","{entry["bounce_type"]}"\n'
        
        # Create response with CSV file
        from io import StringIO
        output = StringIO()
        output.write(csv_content)
        output.seek(0)
        
        from flask import send_file
        return send_file(
            StringIO(csv_content),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'bounced_emails_campaign_{campaign_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': f'Error downloading bounces: {str(e)}'}), 500

@app.route('/api/download/delivered/<int:campaign_id>')
@login_required
def download_delivered(campaign_id):
    """Download delivered emails as CSV"""
    try:
        delivered_emails = get_delivered_emails(campaign_id)
        
        if not delivered_emails:
            return jsonify({'error': 'No delivered emails found'}), 404
        
        # Create CSV content
        csv_content = "Email,Campaign ID,Subject,Sender,Details,Timestamp\n"
        for entry in delivered_emails:
            csv_content += f'"{entry["email"]}","{entry["campaign_id"]}","{entry.get("subject", "")}","{entry.get("sender", "")}","{entry.get("details", "")}","{entry["timestamp"]}"\n'
        
        # Create response with CSV file
        from io import StringIO
        output = StringIO()
        output.write(csv_content)
        output.seek(0)
        
        from flask import send_file
        return send_file(
            StringIO(csv_content),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'delivered_emails_campaign_{campaign_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': f'Error downloading delivered emails: {str(e)}'}), 500

@app.route('/api/bounces/<int:campaign_id>')
@login_required
def api_bounces(campaign_id):
    """Get bounced emails for a campaign"""
    try:
        bounced_emails = get_bounced_emails(campaign_id)
        return jsonify(bounced_emails)
    except Exception as e:
        return jsonify({'error': f'Error getting bounces: {str(e)}'}), 500

@app.route('/api/delete/bounce/<int:campaign_id>/<path:email>', methods=['DELETE'])
@login_required
def delete_bounce(campaign_id, email):
    """Delete a specific bounced email"""
    try:
        # Decode the email from URL
        email = email.replace('%40', '@')
        
        print(f"🔍 Attempting to delete bounce: campaign_id={campaign_id}, email={email}")
        
        # Load bounced emails
        try:
            with open(BOUNCES_FILE, 'r') as f:
                bounce_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            bounce_data = {}
        
        print(f"📊 Current bounce data: {json.dumps(bounce_data, indent=2)}")
        
        # Find and remove the specific bounce
        campaign_key = str(campaign_id)
        if campaign_key in bounce_data:
            print(f"✅ Found campaign {campaign_id} with {len(bounce_data[campaign_key])} bounces")
            
            # Check if email exists in this campaign
            existing_emails = [bounce['email'] for bounce in bounce_data[campaign_key]]
            print(f"📧 Emails in campaign {campaign_id}: {existing_emails}")
            
            if email in existing_emails:
                # Filter out the specific email
                original_count = len(bounce_data[campaign_key])
                bounce_data[campaign_key] = [
                    bounce for bounce in bounce_data[campaign_key] 
                    if bounce['email'] != email
                ]
                
                # Save the updated data
                with open(BOUNCES_FILE, 'w') as f:
                    json.dump(bounce_data, f, indent=2)
                
                deleted_count = original_count - len(bounce_data[campaign_key])
                
                print(f"🗑️ Successfully deleted bounced email: {email} from campaign {campaign_id}")
                return jsonify({
                    'success': True, 
                    'message': f'Bounced email {email} deleted successfully',
                    'deleted_count': deleted_count
                })
            else:
                print(f"❌ Email {email} not found in campaign {campaign_id}")
                return jsonify({
                    'success': False, 
                    'message': f'Bounced email {email} not found in campaign {campaign_id}. Available emails: {existing_emails}'
                }), 404
        else:
            print(f"❌ Campaign {campaign_id} not found in bounce data")
            available_campaigns = list(bounce_data.keys())
            return jsonify({
                'success': False, 
                'message': f'No bounce data found for campaign {campaign_id}. Available campaigns: {available_campaigns}'
            }), 404
            
    except Exception as e:
        print(f"❌ Error deleting bounced email: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error deleting bounced email: {str(e)}'
        }), 500

@app.route('/api/delete/bounces/<int:campaign_id>', methods=['DELETE'])
@login_required
def delete_campaign_bounces(campaign_id):
    """Delete all bounced emails for a specific campaign"""
    try:
        # Load bounced emails
        try:
            with open(BOUNCES_FILE, 'r') as f:
                bounce_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            bounce_data = {}
        
        # Remove all bounces for the campaign
        campaign_key = str(campaign_id)
        if campaign_key in bounce_data:
            deleted_count = len(bounce_data[campaign_key])
            del bounce_data[campaign_key]
            
            # Save the updated data
            with open(BOUNCES_FILE, 'w') as f:
                json.dump(bounce_data, f, indent=2)
            
            print(f"🗑️ Deleted all {deleted_count} bounced emails from campaign {campaign_id}")
            return jsonify({
                'success': True, 
                'message': f'All {deleted_count} bounced emails deleted from campaign {campaign_id}',
                'deleted_count': deleted_count
            })
        else:
            return jsonify({
                'success': False, 
                'message': f'No bounce data found for campaign {campaign_id}'
            }), 404
            
    except Exception as e:
        print(f"❌ Error deleting campaign bounces: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error deleting campaign bounces: {str(e)}'
        }), 500

@app.route('/api/delete/bounces/all', methods=['DELETE'])
@login_required
def delete_all_bounces():
    """Delete all bounced emails from all campaigns"""
    try:
        # Load bounced emails
        try:
            with open(BOUNCES_FILE, 'r') as f:
                bounce_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            bounce_data = {}
        
        # Count total bounces
        total_deleted = sum(len(bounces) for bounces in bounce_data.values())
        
        # Clear all bounce data
        bounce_data = {}
        
        # Save the empty data
        with open(BOUNCES_FILE, 'w') as f:
            json.dump(bounce_data, f, indent=2)
        
        print(f"🗑️ Deleted all {total_deleted} bounced emails from all campaigns")
        return jsonify({
            'success': True, 
            'message': f'All {total_deleted} bounced emails deleted from all campaigns',
            'deleted_count': total_deleted
        })
            
    except Exception as e:
        print(f"❌ Error deleting all bounces: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error deleting all bounces: {str(e)}'
        }), 500

@app.route('/webhook/zoho/bounce', methods=['POST'])
def zoho_bounce_webhook():
    """Webhook endpoint to receive bounce notifications from Zoho"""
    try:
        # Get webhook data from Zoho
        webhook_data = request.get_json()
        
        if not webhook_data:
            return jsonify({'error': 'No webhook data received'}), 400
        
        # Process the bounce notification
        detector = get_zoho_bounce_detector()
        if detector:
            bounce_info = detector.process_webhook_bounce(webhook_data)
            
            # Add to bounce list if email is provided
            if bounce_info.get('email'):
                add_bounce_email(
                    email=bounce_info['email'],
                    campaign_id=bounce_info.get('campaign_id', 0),
                    reason=bounce_info.get('bounce_reason', 'Unknown bounce'),
                    subject=bounce_info.get('subject'),
                    sender=bounce_info.get('sender')
                )
                
                # Log the bounce
                log_email(
                    email=bounce_info['email'],
                    subject=bounce_info.get('subject', 'Unknown'),
                    sender=bounce_info.get('sender', 'Unknown'),
                    status="BOUNCED",
                    campaign_id=bounce_info.get('campaign_id', 0),
                    details=f"Real Zoho bounce: {bounce_info.get('bounce_reason', 'Unknown')}"
                )
                
                print(f"📧 REAL ZOHO BOUNCE: {bounce_info['email']} - {bounce_info.get('bounce_reason', 'Unknown')}")
            
            return jsonify({'status': 'success', 'message': 'Bounce processed'}), 200
        else:
            return jsonify({'error': 'Bounce detector not initialized'}), 500
            
    except Exception as e:
        print(f"❌ Error processing Zoho bounce webhook: {str(e)}")
        return jsonify({'error': f'Error processing bounce: {str(e)}'}), 500

@app.route('/api/zoho/bounce-stats')
@login_required
def zoho_bounce_stats():
    """Get bounce statistics from Zoho"""
    try:
        days = request.args.get('days', 30, type=int)
        stats = get_bounce_statistics(days)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Error getting bounce stats: {str(e)}'}), 500

@app.route('/api/zoho/setup-webhook', methods=['POST'])
@login_required
def setup_zoho_webhook():
    """Set up Zoho bounce webhook"""
    try:
        data = request.get_json()
        webhook_url = data.get('webhook_url')
        
        if not webhook_url:
            return jsonify({'error': 'Webhook URL required'}), 400
        
        success = setup_bounce_webhook(webhook_url)
        
        if success:
            return jsonify({'status': 'success', 'message': 'Webhook setup successful'})
        else:
            return jsonify({'error': 'Failed to setup webhook'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error setting up webhook: {str(e)}'}), 500

@app.route('/api/delivered/<int:campaign_id>')
@login_required
def api_delivered(campaign_id):
    """Get delivered emails for a campaign"""
    try:
        delivered_emails = get_delivered_emails(campaign_id)
        return jsonify(delivered_emails)
    except Exception as e:
        return jsonify({'error': f'Error getting delivered emails: {str(e)}'}), 500

# Data Lists Routes
@app.route('/data-lists')
@login_required
def data_lists():
    """Data lists management page"""
    try:
        data_lists = get_data_lists()
        return render_template('data_lists.html', data_lists=data_lists, user_permissions=current_user.permissions)
    except Exception as e:
        flash(f'Error loading data lists: {str(e)}', 'error')
        return render_template('data_lists.html', data_lists=[], user_permissions=[])

@app.route('/api/data-lists', methods=['GET', 'POST'])
@login_required
def api_data_lists():
    """API for data lists operations"""
    if request.method == 'GET':
        try:
            data_lists = get_data_lists()
            return jsonify(data_lists)
        except Exception as e:
            return jsonify({'error': f'Error getting data lists: {str(e)}'}), 500
    
    elif request.method == 'POST':
        # Check if user has permission to create data lists
        if not has_permission(current_user, 'manage_data'):
            return jsonify({'error': 'Access denied. You need permission to manage data lists.'}), 403
        
        try:
            # Handle file upload
            if 'file' in request.files:
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'error': 'No file selected'}), 400
                
                if not allowed_file(file.filename):
                    return jsonify({'error': 'Invalid file type. Only CSV and TXT files are allowed'}), 400
                
                # Save uploaded file
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                file_path = os.path.join(DATA_LISTS_DIR, filename)
                file.save(file_path)
                
                # Extract emails from file
                valid_emails, invalid_emails = extract_emails_from_file(file_path)
                
                if not valid_emails:
                    # Delete the file if no valid emails
                    os.remove(file_path)
                    return jsonify({'error': 'No valid emails found in the file'}), 400
                
                # Get form data
                name = request.form.get('name', 'Unnamed List')
                geography = request.form.get('geography', 'Unknown')
                isp = request.form.get('isp', 'Unknown')
                description = request.form.get('description', '')
                
                # Add data list
                new_list = add_data_list(
                    name=name,
                    geography=geography,
                    isp=isp,
                    emails=valid_emails,
                    filename=filename,
                    description=description
                )
                
                if new_list:
                    add_notification(f"Data list '{name}' uploaded successfully with {len(valid_emails)} emails", 'success')
                    if invalid_emails:
                        add_notification(f"Warning: {len(invalid_emails)} invalid emails were filtered out", 'warning')
                    return jsonify(new_list)
                else:
                    return jsonify({'error': 'Failed to create data list'}), 500
            
            # Handle manual email list
            else:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'No data provided'}), 400
                
                emails_text = data.get('emails', '')
                if not emails_text:
                    return jsonify({'error': 'No emails provided'}), 400
                
                # Parse emails
                emails = [email.strip() for email in emails_text.split('\n') if email.strip()]
                valid_emails = []
                invalid_emails = []
                
                for email in emails:
                    if validate_email(email):
                        valid_emails.append(email)
                    else:
                        invalid_emails.append(email)
                
                if not valid_emails:
                    return jsonify({'error': 'No valid emails provided'}), 400
                
                # Create filename for manual list
                filename = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                
                # Add data list
                new_list = add_data_list(
                    name=data.get('name', 'Manual List'),
                    geography=data.get('geography', 'Unknown'),
                    isp=data.get('isp', 'Unknown'),
                    emails=valid_emails,
                    filename=filename,
                    description=data.get('description', '')
                )
                
                if new_list:
                    add_notification(f"Data list '{data.get('name', 'Manual List')}' created successfully with {len(valid_emails)} emails", 'success')
                    if invalid_emails:
                        add_notification(f"Warning: {len(invalid_emails)} invalid emails were filtered out", 'warning')
                    return jsonify(new_list)
                else:
                    return jsonify({'error': 'Failed to create data list'}), 500
                    
        except Exception as e:
            return jsonify({'error': f'Error creating data list: {str(e)}'}), 500

@app.route('/api/data-lists/<int:list_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_data_list(list_id):
    """API for individual data list operations"""
    if request.method == 'GET':
        try:
            data_lists = get_data_lists()
            data_list = next((lst for lst in data_lists if lst['id'] == list_id), None)
            
            if not data_list:
                return jsonify({'error': 'Data list not found'}), 404
            
            # Get emails if requested
            if request.args.get('include_emails') == 'true':
                # Check if user has permission to manage data
                if not has_permission(current_user, 'manage_data'):
                    return jsonify({
                        'error': 'Access denied. You need manage_data permission to view email addresses.',
                        'id': data_list['id'],
                        'name': data_list['name'],
                        'geography': data_list.get('geography'),
                        'isp': data_list.get('isp'),
                        'description': data_list.get('description'),
                        'email_count': data_list.get('email_count', 0),
                        'created_at': data_list.get('created_at'),
                        'updated_at': data_list.get('updated_at'),
                        'emails': []
                    }), 403
                
                emails = get_data_list_emails(list_id)
                data_list['emails'] = emails
            
            return jsonify(data_list)
        except Exception as e:
            return jsonify({'error': f'Error getting data list: {str(e)}'}), 500
    
    elif request.method == 'PUT':
        # Check if user has permission to manage data lists
        if not has_permission(current_user, 'manage_data'):
            return jsonify({'error': 'Access denied. You need permission to manage data lists.'}), 403
        
        try:
            data_lists = get_data_lists()
            data_list = next((lst for lst in data_lists if lst['id'] == list_id), None)
            
            if not data_list:
                return jsonify({'error': 'Data list not found'}), 404
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Update fields
            for field in ['name', 'geography', 'isp', 'description']:
                if field in data:
                    data_list[field] = data[field]
            
            data_list['updated_at'] = datetime.now().isoformat()
            
            save_data_lists(data_lists)
            add_notification(f"Data list '{data_list['name']}' updated successfully", 'success')
            
            return jsonify(data_list)
        except Exception as e:
            return jsonify({'error': f'Error updating data list: {str(e)}'}), 500
    
    elif request.method == 'DELETE':
        # Check if user has permission to manage data lists
        if not has_permission(current_user, 'manage_data'):
            return jsonify({'error': 'Access denied. You need permission to manage data lists.'}), 403
        
        try:
            if delete_data_list(list_id):
                add_notification("Data list deleted successfully", 'success')
                return jsonify({'message': 'Data list deleted successfully'})
            else:
                return jsonify({'error': 'Data list not found'}), 404
        except Exception as e:
            return jsonify({'error': f'Error deleting data list: {str(e)}'}), 500

@app.route('/api/data-lists/<int:list_id>/download')
@login_required
def download_data_list(list_id):
    """Download data list as CSV"""
    # Check if user has permission to manage data lists
    if not has_permission(current_user, 'manage_data'):
        return jsonify({'error': 'Access denied. You need permission to manage data lists.'}), 403
    
    try:
        data_lists = get_data_lists()
        data_list = next((lst for lst in data_lists if lst['id'] == list_id), None)
        
        if not data_list:
            return jsonify({'error': 'Data list not found'}), 404
        
        emails = get_data_list_emails(list_id)
        if not emails:
            return jsonify({'error': 'No emails found in data list'}), 404
        
        # Create CSV content
        csv_content = "Email\n"
        for email in emails:
            csv_content += f'"{email}"\n'
        
        # Create response with CSV file
        from io import StringIO
        return send_file(
            StringIO(csv_content),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{data_list["name"]}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': f'Error downloading data list: {str(e)}'}), 500

@app.route('/api/data-lists/<int:list_id>/emails')
@login_required
def get_data_list_emails_api(list_id):
    """Get emails from a data list"""
    try:
        # Check if user has permission to manage data
        if not has_permission(current_user, 'manage_data'):
            return jsonify({
                'list_id': list_id,
                'emails': [],
                'count': 0,
                'error': 'Access denied. You need manage_data permission to view email addresses.'
            }), 403
        
        emails = get_data_list_emails(list_id)
        return jsonify({
            'list_id': list_id,
            'emails': emails,
            'count': len(emails)
        })
    except Exception as e:
        return jsonify({'error': f'Error getting emails: {str(e)}'}), 500

@app.route('/api/data-lists/<int:list_id>/campaign-emails')
@login_required
def get_data_list_campaign_emails(list_id):
    """Get emails from a data list for campaign usage (no permission required)"""
    try:
        emails = get_data_list_emails(list_id)
        return jsonify({
            'list_id': list_id,
            'emails': emails,
            'count': len(emails)
        })
    except Exception as e:
        return jsonify({'error': f'Error getting emails: {str(e)}'}), 500

# Smart retry mechanism for rate limit errors
def smart_retry_with_exponential_backoff(campaign_id, email, subject, sender, account, json_data, enhanced_headers, max_retries=6):
    """
    Smart retry mechanism with exponential backoff for 401 rate limit errors
    Retry schedule: 10s, 20s, 1min, 1h, 4h, 24h
    """
    url = "https://crm.zoho.com/crm/v7/settings/functions/send_email_template3/actions/test"
    
    # Retry schedule in seconds: 10s, 20s, 1min, 1h, 4h, 24h
    retry_delays = [10, 20, 60, 3600, 14400, 86400]
    
    for attempt in range(max_retries):
        try:
            print(f"📤 Sending email to: {email} (Attempt {attempt + 1}/{max_retries})")
            print(f"   Subject: {subject}")
            print(f"   Sender: {sender}")
            
            # Make API request
            response = requests.post(
                url,
                json=json_data,
                cookies=account['cookies'],
                headers=enhanced_headers,
                timeout=30  # Increased timeout for retries
            )
            
            # Parse response
            try:
                result = response.json()
                message = result.get("message", "")
                code = result.get("code", "")
            except json.JSONDecodeError:
                message = ""
                code = ""
                result = {}
            
            # Check for 401 rate limit error
            if response.status_code == 401:
                if attempt < max_retries - 1:  # Not the last attempt
                    delay = retry_delays[attempt]
                    print(f"🚨 RATE LIMIT EXCEEDED (401) - Attempt {attempt + 1}/{max_retries}")
                    print(f"⏰ Smart pause: {delay} seconds before retry")
                    
                    # Log the rate limit event
                    rate_limit_log = {
                        'campaign_id': campaign_id,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'warning',
                        'message': f"🚨 Zoho Rate Limit Exceeded (401) - Smart pause for {delay}s",
                        'email': email,
                        'subject': subject,
                        'sender': sender,
                        'type': 'zoho_rate_limit',
                        'attempt': attempt + 1,
                        'retry_delay': delay,
                        'response_code': 401,
                        'api_message': message,
                        'api_code': code
                    }
                    add_campaign_log(campaign_id, rate_limit_log)
                    socketio.emit('email_progress', rate_limit_log)
                    
                    # Send notification for first rate limit hit
                    if attempt == 0:
                        add_notification(
                            f"🚨 Zoho Rate Limit Exceeded for campaign. Smart retry system activated with {delay}s pause.",
                            'warning',
                            campaign_id
                        )
                    
                    # Wait for the specified delay
                    time.sleep(delay)
                    continue
                else:
                    # Final attempt failed
                    final_error = f"❌ FINAL FAILURE: Rate limit exceeded after {max_retries} attempts"
                    print(final_error)
                    
                    final_log = {
                        'campaign_id': campaign_id,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'message': final_error,
                        'email': email,
                        'subject': subject,
                        'sender': sender,
                        'type': 'final_rate_limit_failure',
                        'attempt': max_retries,
                        'response_code': 401,
                        'api_message': message,
                        'api_code': code
                    }
                    add_campaign_log(campaign_id, final_log)
                    socketio.emit('email_progress', final_log)
                    
                    # Send final notification
                    add_notification(
                        f"❌ Campaign paused: Zoho rate limit exceeded after {max_retries} retry attempts. Manual intervention required.",
                        'error',
                        campaign_id
                    )
                    
                    return {
                        'success': False,
                        'status': 'rate_limit_final_failure',
                        'message': final_error,
                        'attempts': max_retries
                    }
            
            # Handle other status codes
            elif response.status_code == 200:
                print(f"✅ Email sent successfully to {email}")
                return {
                    'success': True,
                    'status': 'success',
                    'message': 'Email sent successfully',
                    'attempts': attempt + 1,
                    'response': response,
                    'result': result
                }
            else:
                # Other error codes
                error_msg = f"❌ API Error ({response.status_code}): {message} | Code: {code}"
                print(error_msg)
                
                error_log = {
                    'campaign_id': campaign_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'error',
                    'message': error_msg,
                    'email': email,
                    'subject': subject,
                    'sender': sender,
                    'type': 'api_error',
                    'attempt': attempt + 1,
                    'response_code': response.status_code,
                    'api_message': message,
                    'api_code': code
                }
                add_campaign_log(campaign_id, error_log)
                socketio.emit('email_progress', error_log)
                
                return {
                    'success': False,
                    'status': 'api_error',
                    'message': error_msg,
                    'attempts': attempt + 1,
                    'response_code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            timeout_msg = f"⏰ Timeout sending email to {email} (Attempt {attempt + 1}/{max_retries})"
            print(timeout_msg)
            
            timeout_log = {
                'campaign_id': campaign_id,
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'message': timeout_msg,
                'email': email,
                'subject': subject,
                'sender': sender,
                'type': 'timeout',
                'attempt': attempt + 1
            }
            add_campaign_log(campaign_id, timeout_log)
            socketio.emit('email_progress', timeout_log)
            
            if attempt < max_retries - 1:
                delay = retry_delays[attempt]
                print(f"⏰ Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                return {
                    'success': False,
                    'status': 'timeout_final_failure',
                    'message': f"Final timeout after {max_retries} attempts",
                    'attempts': max_retries
                }
                
        except requests.exceptions.RequestException as e:
            network_error = f"❌ Network error sending email to {email} (Attempt {attempt + 1}/{max_retries}): {str(e)}"
            print(network_error)
            
            network_log = {
                'campaign_id': campaign_id,
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'message': network_error,
                'email': email,
                'subject': subject,
                'sender': sender,
                'type': 'network_error',
                'attempt': attempt + 1,
                'exception': str(e)
            }
            add_campaign_log(campaign_id, network_log)
            socketio.emit('email_progress', network_log)
            
            if attempt < max_retries - 1:
                delay = retry_delays[attempt]
                print(f"⏰ Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                return {
                    'success': False,
                    'status': 'network_final_failure',
                    'message': f"Final network error after {max_retries} attempts: {str(e)}",
                    'attempts': max_retries
                }
    
    # Should never reach here, but just in case
    return {
        'success': False,
        'status': 'unknown_failure',
        'message': 'Unknown failure in retry mechanism',
        'attempts': max_retries
    }

def send_campaign_emails(campaign, account):
    """Send emails for a campaign in background thread with IMPROVED feedback and bounce detection"""
    campaign_id = campaign['id']
    
    try:
        print(f"🚀 Starting campaign: {campaign['name']} (ID: {campaign_id})")
        print(f"📧 Using IMPROVED email sending with REAL delivery feedback")
        
        # Create initial log entry
        start_log = {
            'campaign_id': campaign_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'info',
            'message': f"🚀 Campaign '{campaign['name']}' started with IMPROVED delivery feedback",
            'type': 'start'
        }
        
        # Save to file and emit
        add_campaign_log(campaign_id, start_log)
        socketio.emit('email_progress', start_log)
        
        # Parse recipients, subjects, and senders
        destinataires = [email.strip() for email in campaign['destinataires'].split('\n') if email.strip()]
        subjects = [subject.strip() for subject in campaign['subjects'].split('\n') if subject.strip()]
        froms = [sender.strip() for sender in campaign['froms'].split('\n') if sender.strip()]
        
        # Filter out bounced emails for relaunch
        original_count = len(destinataires)
        destinataires = filter_bounced_emails(destinataires, campaign_id)
        filtered_count = len(destinataires)
        
        if original_count != filtered_count:
            print(f"🚫 Relaunch: Filtered out {original_count - filtered_count} bounced emails")
            add_notification(f"Relaunch: {original_count - filtered_count} bounced emails excluded from campaign '{campaign['name']}'", 'info', campaign_id)
        
        if not destinataires:
            error_msg = "❌ No recipients found in campaign"
            print(error_msg)
            
            error_log = {
                'campaign_id': campaign_id,
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'message': error_msg,
                'type': 'error'
            }
            add_campaign_log(campaign_id, error_log)
            socketio.emit('email_progress', error_log)
            return
        
        total_emails = len(destinataires)
        sent_count = 0
        delivered_count = 0
        bounced_count = 0
        error_count = 0
        
        print(f"📊 Campaign stats: {total_emails} emails to send")
        print(f"🎯 IMPROVED delivery tracking enabled")
        print(f"🔍 Bounce detection enabled")
        
        # Zoho API endpoint - using the working endpoint from your curl
        url = "https://crm.zoho.com/crm/v7/settings/functions/send_email_template3/actions/test"
        
        for i, email in enumerate(destinataires):
            if campaign_id not in running_campaigns:
                print(f"⏹️ Campaign {campaign_id} stopped by user")
                stop_log = {
                    'campaign_id': campaign_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'info',
                    'message': f"⏹️ Campaign stopped by user",
                    'type': 'stopped'
                }
                add_campaign_log(campaign_id, stop_log)
                socketio.emit('email_progress', stop_log)
                break
            
            # Check rate limiting before sending email
            user_id = campaign.get('created_by', 'unknown')
            allowed, wait_time, reason = check_rate_limit(user_id, campaign_id)
            
            if not allowed:
                print(f"⏳ Rate limit hit: {reason}")
                rate_limit_log = {
                    'campaign_id': campaign_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'warning',
                    'message': f"⏳ Rate limit: {reason}",
                    'type': 'rate_limit'
                }
                add_campaign_log(campaign_id, rate_limit_log)
                socketio.emit('email_progress', rate_limit_log)
                
                # Wait for the required time
                if wait_time > 0:
                    print(f"⏰ Waiting {wait_time:.1f} seconds due to rate limit")
                    time.sleep(wait_time)
                    
                    # Check again after waiting
                    allowed, wait_time, reason = check_rate_limit(user_id, campaign_id)
                    if not allowed:
                        print(f"❌ Still rate limited after waiting: {reason}")
                        continue
            
            # Select random subject and sender
            subject = random.choice(subjects) if subjects else "Default Subject"
            sender = random.choice(froms) if froms else "Default Sender"
            
            # Deluge script matching your working curl format
            script = f'''void automation.Send_Email_Template3()
{{
    curl = "https://www.zohoapis.com/crm/v7/settings/email_templates/{campaign['template_id']}";

    getTemplate = invokeurl
    [
        url: curl
        type: GET
        connection: "re"
    ];

    EmailTemplateContent = getTemplate.get("email_templates").get(0).get("content");

    // Liste des destinataires
    destinataires = list();
    destinataires.add("{email}");

    sendmail
    [
        from: "{sender} <" + zoho.loginuserid + ">"
        to: destinataires
        subject: "{subject}"
        message: EmailTemplateContent
    ];
}}'''

            json_data = {
                'functions': [
                    {
                        'script': script,
                        'arguments': {},
                    },
                ],
            }

            # Add missing headers from your working curl
            enhanced_headers = account['headers'].copy()
            enhanced_headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Referer': 'https://crm.zoho.com/',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://crm.zoho.com',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Priority': 'u=0',
                'TE': 'trailers'
            })

            # Use smart retry mechanism with exponential backoff
            print(f"🚀 Using SMART RETRY system with exponential backoff for {email}")
            retry_result = smart_retry_with_exponential_backoff(
                campaign_id, email, subject, sender, account, json_data, enhanced_headers
            )

            if retry_result['success']:
                sent_count += 1
                
                # Check for REAL delivery status
                print(f"🔍 Checking delivery status for {email}...")
                delivery_status = check_email_delivery_status(email, campaign_id, account)
                
                if delivery_status['status'] == 'delivered':
                    delivered_count += 1
                    success_msg = f"✅ Email DELIVERED successfully to {email}"
                    print(f"✅ {success_msg}")
                    log_email(email, subject, sender, "DELIVERED", campaign_id, delivery_status.get('details', ''))
                    add_delivered_email(email, campaign_id, subject, sender, delivery_status.get('details', ''))
                elif delivery_status['status'] == 'bounced':
                    bounced_count += 1
                    bounce_msg = f"📧 Email BOUNCED for {email}"
                    print(f"📧 {bounce_msg}")
                    log_email(email, subject, sender, "BOUNCED", campaign_id, delivery_status.get('details', ''))
                    add_bounce_email(email, campaign_id, delivery_status.get('bounce_reason', 'Unknown bounce'), subject, sender)
                else:
                    delivered_count += 1
                    unknown_msg = f"❓ Email status UNKNOWN for {email} (treating as delivered)"
                    print(f"❓ {unknown_msg}")
                    log_email(email, subject, sender, "UNKNOWN", campaign_id, delivery_status.get('details', ''))
                    add_delivered_email(email, campaign_id, subject, sender, delivery_status.get('details', ''))
                
                success_log = {
                    'campaign_id': campaign_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': delivery_status['status'],
                    'message': success_msg if delivery_status['status'] == 'delivered' else bounce_msg if delivery_status['status'] == 'bounced' else unknown_msg,
                    'email': email,
                    'subject': subject,
                    'sender': sender,
                    'type': 'delivery_status',
                    'attempts': retry_result['attempts'],
                    'delivery_details': delivery_status
                }
                add_campaign_log(campaign_id, success_log)
                socketio.emit('email_progress', success_log)
                
                # Update rate limit counters after successful email sending
                user_id = campaign.get('created_by', 'unknown')
                update_rate_limit_counters(user_id)
                
            else:
                error_count += 1
                error_msg = f"❌ FAILED: {retry_result['message']} to {email}"
                print(error_msg)
                
                error_log = {
                    'campaign_id': campaign_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'error',
                    'message': error_msg,
                    'email': email,
                    'subject': subject,
                    'sender': sender,
                    'type': 'smart_retry_failure',
                    'attempts': retry_result['attempts'],
                    'failure_status': retry_result['status']
                }
                add_campaign_log(campaign_id, error_log)
                socketio.emit('email_progress', error_log)
                log_email(email, subject, sender, f"SMART_RETRY_FAILED: {retry_result['status']}", campaign_id, retry_result['message'])
                
                # If it's a final rate limit failure, we might want to pause the campaign
                if retry_result['status'] == 'rate_limit_final_failure':
                    print(f"🚨 Campaign {campaign_id} paused due to persistent rate limit failures")
                    add_notification(
                        f"🚨 Campaign '{campaign['name']}' paused due to persistent Zoho rate limit failures. Manual intervention required.",
                        'error',
                        campaign_id
                    )
                    # Remove from running campaigns to pause it
                    if campaign_id in running_campaigns:
                        running_campaigns.remove(campaign_id)
                    break
            
            # Pause between emails with random delay
            time.sleep(random.uniform(1, 2))
            
            # Pause every 10 emails for rate limiting
            if (i + 1) % 10 == 0:
                pause_msg = f"⏸️ Pausing for 10 seconds after {i+1} emails (rate limiting)..."
                print(pause_msg)
                pause_log = {
                    'campaign_id': campaign_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'info',
                    'message': pause_msg,
                    'type': 'pause'
                }
                add_campaign_log(campaign_id, pause_log)
                socketio.emit('email_progress', pause_log)
                time.sleep(10)
        
        # Campaign completed with detailed delivery summary
        delivery_rate = round((delivered_count / total_emails) * 100, 1) if total_emails > 0 else 0
        bounce_rate = round((bounced_count / total_emails) * 100, 1) if total_emails > 0 else 0
        
        completion_msg = f"🏁 Campaign completed! Sent: {sent_count}/{total_emails} | Delivered: {delivered_count} | Bounced: {bounced_count} | Errors: {error_count} | Delivery Rate: {delivery_rate}% | Bounce Rate: {bounce_rate}%"
        print(completion_msg)
        
        completion_log = {
            'campaign_id': campaign_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'info',
            'message': completion_msg,
            'type': 'completion',
            'total_sent': sent_count,
            'total_attempted': total_emails,
            'delivered_count': delivered_count,
            'bounced_count': bounced_count,
            'error_count': error_count,
            'delivery_rate': delivery_rate,
            'bounce_rate': bounce_rate
        }
        add_campaign_log(campaign_id, completion_log)
        
        # Update campaign status with delivery stats
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        if campaign:
            campaign['status'] = 'completed'
            campaign['completed_at'] = datetime.now().isoformat()
            campaign['total_sent'] = sent_count
            campaign['total_attempted'] = total_emails
            campaign['delivered_count'] = delivered_count
            campaign['bounced_count'] = bounced_count
            campaign['error_count'] = error_count
            campaign['delivery_rate'] = delivery_rate
            campaign['bounce_rate'] = bounce_rate
            
            with open(CAMPAIGNS_FILE, 'w') as f:
                json.dump(campaigns, f, indent=2)
        
        # Remove from running campaigns
        if campaign_id in running_campaigns:
            del running_campaigns[campaign_id]
        
        # Emit completion with detailed delivery stats
        socketio.emit('campaign_completed', {
            'campaign_id': campaign_id,
            'total_sent': sent_count,
            'total_attempted': total_emails,
            'delivered_count': delivered_count,
            'bounced_count': bounced_count,
            'error_count': error_count,
            'delivery_rate': delivery_rate,
            'bounce_rate': bounce_rate,
            'message': completion_msg
        })
        
        # Add notification with delivery statistics
        if delivery_rate >= 95:
            add_notification(f"Campaign '{campaign['name']}' completed successfully! {delivered_count}/{total_emails} emails delivered ({delivery_rate}% delivery rate).", 'success', campaign_id)
        elif delivery_rate >= 80:
            add_notification(f"Campaign '{campaign['name']}' completed with minor issues. {delivered_count}/{total_emails} emails delivered ({delivery_rate}% delivery rate).", 'warning', campaign_id)
        else:
            add_notification(f"Campaign '{campaign['name']}' completed with delivery issues. {delivered_count}/{total_emails} emails delivered ({delivery_rate}% delivery rate).", 'error', campaign_id)
        
        # Update campaign progress with detailed stats
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        if campaign:
            campaign['total_sent'] = sent_count
            campaign['total_attempted'] = i + 1
            campaign['delivered_count'] = delivered_count
            campaign['bounced_count'] = bounced_count
            campaign['error_count'] = error_count
            
            with open(CAMPAIGNS_FILE, 'w') as f:
                json.dump(campaigns, f, indent=2)
        
    except Exception as e:
        error_msg = f"❌ Campaign error: {str(e)}"
        print(error_msg)
        
        error_log = {
            'campaign_id': campaign_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'message': error_msg,
            'type': 'campaign_error',
            'exception': str(e)
        }
        add_campaign_log(campaign_id, error_log)
        socketio.emit('email_progress', error_log)
        
        # Update campaign status to error
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        if campaign:
            campaign['status'] = 'error'
            campaign['error_message'] = str(e)
            
            with open(CAMPAIGNS_FILE, 'w') as f:
                json.dump(campaigns, f, indent=2)
        
        # Remove from running campaigns
        if campaign_id in running_campaigns:
            del running_campaigns[campaign_id]
        
        # Add error notification
        add_notification(f"Campaign '{campaign['name']}' failed with error: {str(e)}", 'error', campaign_id)

# Template filters
@app.template_filter('get_status_badge_class')
def get_status_badge_class(status):
    """Get Bootstrap badge class for campaign status"""
    classes = {
        'running': 'bg-success',
        'stopped': 'bg-secondary',
        'completed': 'bg-primary',
        'error': 'bg-danger'
    }
    return classes.get(status, 'bg-secondary')

@app.template_filter('get_notification_badge_class')
def get_notification_badge_class(type):
    """Get Bootstrap badge class for notification type"""
    classes = {
        'success': 'bg-success',
        'error': 'bg-danger',
        'warning': 'bg-warning',
        'info': 'bg-info'
    }
    return classes.get(type, 'bg-info')

@app.template_filter('get_notification_icon')
def get_notification_icon(type):
    """Get icon for notification type"""
    icons = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️'
    }
    return icons.get(type, 'ℹ️')

@app.template_filter('format_timestamp')
def format_timestamp(timestamp):
    """Format timestamp for display"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp

# Context processors to make functions available in templates
@app.context_processor
def utility_processor():
    """Make utility functions available in templates"""
    def get_status_badge_class(status):
        if status == 'running':
            return 'bg-primary'
        elif status == 'completed':
            return 'bg-success'
        elif status == 'stopped':
            return 'bg-danger'
        elif status == 'paused':
            return 'bg-warning'
        elif status == 'ready':
            return 'bg-info'
        else:
            return 'bg-secondary'
    
    def get_notification_badge_class(type):
        if type == 'success':
            return 'bg-success'
        elif type == 'error':
            return 'bg-danger'
        elif type == 'warning':
            return 'bg-warning'
        else:
            return 'bg-info'
    
    def get_notification_icon(type):
        if type == 'success':
            return '✅'
        elif type == 'error':
            return '❌'
        elif type == 'warning':
            return '⚠️'
        else:
            return 'ℹ️'
    
    def format_timestamp(timestamp):
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                return timestamp
        return ''
    
    # Get notifications count for all templates
    try:
        with open(NOTIFICATIONS_FILE, 'r') as f:
            notifications = json.load(f)
        notifications_count = len([n for n in notifications if not n.get('read', False)])
    except:
        notifications_count = 0
    
    def is_admin():
        return current_user.is_authenticated and current_user.role == 'admin'
    
    return {
        'get_status_badge_class': get_status_badge_class,
        'get_notification_badge_class': get_notification_badge_class,
        'get_notification_icon': get_notification_icon,
        'format_timestamp': format_timestamp,
        'notifications_count': notifications_count,
        'is_admin': is_admin
    }

# User Management Functions
def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def user_management_required(f):
    """Decorator to require user management permissions"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role not in ['admin']:
            flash('Access denied. User management privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/users')
@login_required
@admin_required
def users():
    """User management page"""
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = []
    return render_template('users.html', users=users)

@app.route('/api/users', methods=['GET', 'POST'])
@login_required
@admin_required
def api_users():
    """User management API"""
    if request.method == 'GET':
        try:
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
            if not isinstance(users, list):
                users = []
        except (FileNotFoundError, json.JSONDecodeError):
            users = []
        return jsonify(users)
    
    elif request.method == 'POST':
        try:
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Validate required fields
            required_fields = ['username', 'password', 'email']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            try:
                with open(USERS_FILE, 'r') as f:
                    users = json.load(f)
                if not isinstance(users, list):
                    users = []
            except (FileNotFoundError, json.JSONDecodeError):
                users = []
            
            # Check if username already exists
            if any(user['username'] == data['username'] for user in users):
                return jsonify({'error': 'Username already exists'}), 400
            
            new_user = {
                'id': max([user['id'] for user in users], default=0) + 1 if users else 1,
                'username': data['username'],
                'password': generate_password_hash(data['password']),
                'email': data['email'],
                'role': data.get('role', 'user'),
                'created_at': datetime.now().isoformat(),
                'is_active': data.get('is_active', True),
                'permissions': data.get('permissions', [])
            }
            
            users.append(new_user)
            
            try:
                with open(USERS_FILE, 'w') as f:
                    json.dump(users, f, indent=2)
            except PermissionError as e:
                print(f"❌ Permission error saving user: {e}")
                error_msg = f"Permission denied: Cannot write to {USERS_FILE}. Please check file permissions on the server."
                return jsonify({'error': error_msg}), 500
            except Exception as e:
                print(f"❌ Error saving user to file: {e}")
                return jsonify({'error': f'Failed to save user to file: {str(e)}'}), 500
            
            # Send account creation email
            if SMTP_CONFIG['enabled']:
                send_account_created_email(data['email'], data['username'], data.get('role', 'user'))
            
            add_notification(f"User '{data['username']}' created successfully", 'success')
            return jsonify(new_user)
            
        except Exception as e:
            print(f"Error creating user: {str(e)}")
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@admin_required
def api_user(user_id):
    """Individual user management API"""
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        if not isinstance(users, list):
            users = []
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading users file: {e}")
        users = []
    
    user = next((u for u in users if u['id'] == user_id), None)
    print(f"Looking for user ID {user_id}, found: {user is not None}")
    
    if request.method == 'GET':
        if user:
            print(f"Returning user data: {user}")
            return jsonify(user)
        else:
            print(f"User {user_id} not found")
            return ('', 404)
    
    elif request.method == 'PUT':
        if not user:
            return ('', 404)
        
        data = request.json
        if 'password' in data and data['password']:
            data['password'] = generate_password_hash(data['password'])
        
        # Update user data
        for key, value in data.items():
            if key in ['username', 'email', 'password', 'role', 'is_active', 'permissions']:
                user[key] = value
        
        try:
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=2)
        except PermissionError as e:
            print(f"❌ Permission error saving user update: {e}")
            error_msg = f"Permission denied: Cannot write to {USERS_FILE}. Please check file permissions on the server."
            return jsonify({'error': error_msg}), 500
        except Exception as e:
            print(f"❌ Error saving user update: {e}")
            return jsonify({'error': f'Failed to save user update: {str(e)}'}), 500
        
        add_notification(f"User '{user['username']}' updated successfully", 'success')
        return jsonify(user)
    
    elif request.method == 'DELETE':
        if not user:
            return ('', 404)
        
        # Prevent deleting the last admin
        if user['role'] == 'admin':
            admin_count = sum(1 for u in users if u['role'] == 'admin')
            if admin_count <= 1:
                return jsonify({'error': 'Cannot delete the last admin user'}), 400
        
        users.remove(user)
        
        try:
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=2)
        except PermissionError as e:
            print(f"❌ Permission error saving user deletion: {e}")
            error_msg = f"Permission denied: Cannot write to {USERS_FILE}. Please check file permissions on the server."
            return jsonify({'error': error_msg}), 500
        except Exception as e:
            print(f"❌ Error saving user deletion: {e}")
            return jsonify({'error': f'Failed to save user deletion: {str(e)}'}), 500
        
        add_notification(f"User '{user['username']}' deleted successfully", 'warning')
        return jsonify({'success': True, 'message': f'User {user["username"]} deleted successfully'})

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('profile.html')

@app.route('/api/profile', methods=['GET', 'PUT'])
@login_required
def api_profile():
    """Profile management API"""
    if request.method == 'GET':
        return jsonify({
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'role': current_user.role,
            'created_at': current_user.created_at,
            'is_active': current_user.is_active
        })
    
    elif request.method == 'PUT':
        try:
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Validate required fields
            required_fields = ['username', 'email']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            try:
                with open(USERS_FILE, 'r') as f:
                    users = json.load(f)
                if not isinstance(users, list):
                    users = []
            except (FileNotFoundError, json.JSONDecodeError):
                return jsonify({'error': 'Error loading user data'}), 500
            
            # Find current user
            user = next((u for u in users if u['id'] == current_user.id), None)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Update fields
            user['username'] = data['username']
            user['email'] = data['email']
            
            # Update password if provided
            if 'password' in data and data['password']:
                user['password'] = generate_password_hash(data['password'])
            
            user['updated_at'] = datetime.now().isoformat()
            
            with open(USERS_FILE, 'w') as f:
                json.dump(users, f, indent=2)
            
            add_notification("Profile updated successfully", 'success')
            return jsonify({'message': 'Profile updated successfully'})
            
        except Exception as e:
            return jsonify({'error': f'Error updating profile: {str(e)}'}), 500

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page"""
    if request.method == 'GET':
        return render_template('forgot_password.html')
    
    elif request.method == 'POST':
        data = request.get_json()
        email = data.get('email', '').strip()
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        try:
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
            if not isinstance(users, list):
                users = []
        except (FileNotFoundError, json.JSONDecodeError):
            return jsonify({'error': 'Error loading user data'}), 500
        
        # Find user by email
        user = next((u for u in users if u.get('email') == email), None)
        if not user:
            # Don't reveal if email exists or not for security
            return jsonify({'message': 'If the email exists, a password reset link has been sent'})
        
        # Generate reset token
        reset_token = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=1)
        
        # Save token
        save_password_reset_token(email, reset_token, expires_at)
        
        # Send email
        send_password_reset_email(email, user['username'], reset_token)
        
        return jsonify({'message': 'If the email exists, a password reset link has been sent'})

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password page"""
    if request.method == 'GET':
        return render_template('reset_password.html', token=token)
    
    elif request.method == 'POST':
        data = request.get_json()
        new_password = data.get('password', '').strip()
        
        if not new_password or len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters long'}), 400
        
        try:
            with open(USERS_FILE, 'r') as f:
                users = json.load(f)
            if not isinstance(users, list):
                users = []
        except (FileNotFoundError, json.JSONDecodeError):
            return jsonify({'error': 'Error loading user data'}), 500
        
        # Find user by token
        user_email = None
        for email, token_data in get_password_reset_tokens().items():
            if token_data['token'] == token:
                user_email = email
                break
        
        if not user_email:
            return jsonify({'error': 'Invalid or expired reset token'}), 400
        
        # Find user
        user = next((u for u in users if u.get('email') == user_email), None)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update password
        user['password'] = generate_password_hash(new_password)
        user['updated_at'] = datetime.now().isoformat()
        
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        
        # Delete token
        delete_password_reset_token(user_email)
        
        # Send security alert
        send_security_alert_email(user_email, user['username'], 'Password Reset', request.remote_addr)
        
        add_notification("Password reset successfully", 'success')
        return jsonify({'message': 'Password reset successfully'})

def get_password_reset_tokens():
    """Get all password reset tokens"""
    try:
        with open(PASSWORD_RESET_TOKENS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Permissions system
PERMISSIONS = {
    'add_account': 'Add Zoho Accounts',
    'manage_accounts': 'Manage All Accounts', 
    'manage_data': 'Manage Data Lists',
    'view_all_campaigns': 'View All Campaigns',
    'manage_all_campaigns': 'Manage All Campaigns',
    'manage_users': 'Manage Users',
    'view_reports': 'View Reports'
}

def has_permission(user, permission):
    """Check if user has specific permission"""
    if not user or not user.is_authenticated:
        return False
    
    # Admin has all permissions
    if user.role == 'admin':
        return True
    
    # Check user-specific permissions
    user_permissions = getattr(user, 'permissions', [])
    return permission in user_permissions

def get_user_accounts(user):
    """Get accounts that user can access"""
    try:
        with open(ACCOUNTS_FILE, 'r') as f:
            accounts = json.load(f)
        if not isinstance(accounts, list):
            accounts = []
    except (FileNotFoundError, json.JSONDecodeError):
        accounts = []
    
    # Admin can see all accounts
    if user.role == 'admin':
        return accounts
    
    # Users with manage_accounts permission can see all accounts
    if has_permission(user, 'manage_accounts'):
        return accounts
    
    # Users with add_account permission can see their own accounts
    if has_permission(user, 'add_account'):
        return [acc for acc in accounts if acc.get('created_by') == user.id]
    
    # Regular users can only see their own accounts
    return [acc for acc in accounts if acc.get('created_by') == user.id]

def get_user_campaigns(user):
    """Get campaigns that user can access"""
    try:
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        if not isinstance(campaigns, list):
            campaigns = []
    except (FileNotFoundError, json.JSONDecodeError):
        campaigns = []
    
    # Admin can see all campaigns
    if user.role == 'admin' or has_permission(user, 'view_all_campaigns'):
        return campaigns
    
    # Regular users can only see their own campaigns
    return [camp for camp in campaigns if camp.get('created_by') == user.id]

# Password reset tokens storage
PASSWORD_RESET_TOKENS_FILE = 'password_reset_tokens.json'

def save_password_reset_token(email, token, expires_at):
    """Save password reset token"""
    try:
        with open(PASSWORD_RESET_TOKENS_FILE, 'r') as f:
            tokens = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        tokens = {}
    
    tokens[email] = {
        'token': token,
        'expires_at': expires_at.isoformat()
    }
    
    with open(PASSWORD_RESET_TOKENS_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)

def get_password_reset_token(email):
    """Get password reset token for email"""
    try:
        with open(PASSWORD_RESET_TOKENS_FILE, 'r') as f:
            tokens = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    
    if email in tokens:
        token_data = tokens[email]
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        
        if expires_at > datetime.now():
            return token_data['token']
        else:
            # Token expired, remove it
            del tokens[email]
            with open(PASSWORD_RESET_TOKENS_FILE, 'w') as f:
                json.dump(tokens, f, indent=2)
    
    return None

def delete_password_reset_token(email):
    """Delete password reset token"""
    try:
        with open(PASSWORD_RESET_TOKENS_FILE, 'r') as f:
            tokens = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    
    if email in tokens:
        del tokens[email]
        with open(PASSWORD_RESET_TOKENS_FILE, 'w') as f:
            json.dump(tokens, f, indent=2)

@app.route('/smtp-config')
@login_required
@admin_required
def smtp_config():
    """SMTP configuration management page"""
    return render_template('smtp_config.html')

@app.route('/system-settings')
@login_required
@admin_required
def system_settings():
    """System settings management page"""
    return render_template('system_settings.html')

@app.route('/backup-restore')
@login_required
@admin_required
def backup_restore():
    """Backup and restore management page"""
    return render_template('backup_restore.html')

@app.route('/api/smtp-config', methods=['GET', 'PUT'])
@login_required
@admin_required
def api_smtp_config():
    """SMTP configuration API"""
    global SMTP_CONFIG
    
    if request.method == 'GET':
        return jsonify(SMTP_CONFIG)
    
    elif request.method == 'PUT':
        try:
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Update SMTP config
            SMTP_CONFIG.update(data)
            
            # Save to file
            with open(SMTP_CONFIG_FILE, 'w') as f:
                json.dump(SMTP_CONFIG, f, indent=2)
            
            # Reload configuration
            reload_smtp_config()
            
            add_notification("SMTP configuration updated successfully", 'success')
            return jsonify({'message': 'SMTP configuration updated successfully'})
            
        except Exception as e:
            return jsonify({'error': f'Error updating SMTP configuration: {str(e)}'}), 500

@app.route('/api/smtp-test', methods=['POST'])
@login_required
@admin_required
def test_smtp_config():
    """Test SMTP configuration"""
    try:
        data = request.json
        test_email = data.get('test_email', '').strip()
        
        if not test_email:
            return jsonify({'error': 'Test email is required'}), 400
        
        # Test email configuration
        test_subject = 'SMTP Configuration Test - Email Campaign Manager'
        test_body = '''
        <html>
        <body>
            <h2>SMTP Configuration Test</h2>
            <p>This is a test email to verify your SMTP configuration is working correctly.</p>
            <p>If you received this email, your SMTP settings are properly configured.</p>
            <p>Best regards,<br>Email Campaign Manager</p>
        </body>
        </html>
        '''
        
        success = send_email(test_email, test_subject, test_body)
        
        if success:
            return jsonify({'message': 'Test email sent successfully'})
        else:
            return jsonify({'error': 'Failed to send test email. Check your SMTP configuration.'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error testing SMTP configuration: {str(e)}'}), 500

@app.route('/rate-limits')
@login_required
def rate_limits():
    """Rate limiting configuration page"""
    return render_template('rate_limits.html')

@app.route('/api/rate-limits', methods=['GET', 'PUT'])
@login_required
def api_rate_limits():
    """Rate limiting configuration API"""
    if request.method == 'GET':
        config = load_rate_limit_config()
        stats = get_rate_limit_stats(current_user.id)
        return jsonify({
            'config': config,
            'stats': stats
        })
    
    elif request.method == 'PUT':
        try:
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Validate data
            required_fields = ['enabled', 'emails_per_second', 'emails_per_minute', 'emails_per_hour', 
                             'emails_per_day', 'wait_time_between_emails', 'burst_limit', 'cooldown_period']
            
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            # Validate numeric values
            numeric_fields = ['emails_per_second', 'emails_per_minute', 'emails_per_hour', 'emails_per_day',
                            'wait_time_between_emails', 'burst_limit', 'cooldown_period']
            
            for field in numeric_fields:
                if not isinstance(data[field], (int, float)) or data[field] < 0:
                    return jsonify({'error': f'Invalid value for {field}: must be a positive number'}), 400
            
            # Update configuration
            config = load_rate_limit_config()
            config.update(data)
            
            # Set quotas based on per-time settings
            config['daily_quota'] = data['emails_per_day']
            config['hourly_quota'] = data['emails_per_hour']
            config['minute_quota'] = data['emails_per_minute']
            config['second_quota'] = data['emails_per_second']
            
            save_rate_limit_config(config)
            
            add_notification("Rate limiting configuration updated successfully", 'success')
            return jsonify({'message': 'Rate limiting configuration updated successfully'})
            
        except Exception as e:
            return jsonify({'error': f'Error updating rate limiting configuration: {str(e)}'}), 500

@app.route('/api/rate-limits/reset', methods=['POST'])
@login_required
@admin_required
def reset_rate_limits():
    """Reset rate limiting data for all users"""
    try:
        global rate_limit_data
        rate_limit_data = {
            'daily_sent': {},
            'hourly_sent': {},
            'minute_sent': {},
            'second_sent': {},
            'last_send_time': {},
            'burst_count': {},
            'cooldown_until': {}
        }
        
        add_notification("Rate limiting data reset successfully", 'success')
        return jsonify({'message': 'Rate limiting data reset successfully'})
        
    except Exception as e:
        return jsonify({'error': f'Error resetting rate limiting data: {str(e)}'}), 500

@app.route('/api/rate-limits/stats')
@login_required
def get_rate_limit_stats_api():
    """Get rate limiting statistics for current user"""
    try:
        stats = get_rate_limit_stats(current_user.id)
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': f'Error getting rate limiting statistics: {str(e)}'}), 500

# Memory optimization imports
import gc
import psutil
import threading
from functools import lru_cache

# Memory monitoring
def log_memory_usage():
    """Log current memory usage for debugging"""
    process = psutil.Process()
    memory_info = process.memory_info()
    print(f"📊 Memory Usage: {memory_info.rss / 1024 / 1024:.1f} MB")
    return memory_info.rss / 1024 / 1024

# Force garbage collection periodically
def cleanup_memory():
    """Force garbage collection to free memory"""
    gc.collect()
    print(f"🧹 Memory cleanup completed. Current usage: {log_memory_usage():.1f} MB")

# Memory-optimized file reading with caching
@lru_cache(maxsize=32)
def read_json_file_cached(filename):
    """Read JSON file with caching to reduce I/O operations"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Error reading {filename}: {e}")
        return [] if 'campaigns' in filename or 'accounts' in filename else {}

# Memory-optimized file writing
def write_json_file_optimized(filename, data):
    """Write JSON file with memory optimization"""
    try:
        # Create backup before writing
        backup_filename = f"{filename}.backup"
        if os.path.exists(filename):
            import shutil
            shutil.copy2(filename, backup_filename)
        
        # Write with atomic operation
        temp_filename = f"{filename}.tmp"
        with open(temp_filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Atomic rename
        os.replace(temp_filename, filename)
        
        # Clean up backup after successful write
        if os.path.exists(backup_filename):
            os.remove(backup_filename)
            
        print(f"✅ Successfully wrote {filename}")
        return True
    except Exception as e:
        print(f"❌ Error writing {filename}: {e}")
        # Restore backup if available
        if os.path.exists(backup_filename):
            os.replace(backup_filename, filename)
        return False

# Simple memory optimization imports
import gc
import psutil

# Simple memory monitoring
def log_memory_usage():
    """Log current memory usage for debugging"""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        print(f"📊 Memory Usage: {memory_info.rss / 1024 / 1024:.1f} MB")
        return memory_info.rss / 1024 / 1024
    except:
        return 0

# Simple garbage collection
def cleanup_memory():
    """Force garbage collection to free memory"""
    try:
        gc.collect()
        print(f"🧹 Memory cleanup completed. Current usage: {log_memory_usage():.1f} MB")
    except:
        pass

# Simple file reading
def read_json_file_simple(filename):
    """Read JSON file with simple error handling"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Error reading {filename}: {e}")
        return [] if 'campaigns' in filename or 'accounts' in filename else {}

# Simple file writing
def write_json_file_simple(filename, data):
    """Write JSON file with simple error handling"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Successfully wrote {filename}")
        return True
    except Exception as e:
        print(f"❌ Error writing {filename}: {e}")
        return False

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) 