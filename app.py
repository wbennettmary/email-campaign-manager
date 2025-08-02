from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
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
import gc
import psutil

# Rate Limiting Configuration
RATE_LIMIT_CONFIG_FILE = 'rate_limit_config.json'

# Default rate limiting settings - Conservative for reliable delivery
DEFAULT_RATE_LIMIT = {
    'enabled': True,
    'emails_per_second': 1,       # 1 email per second
    'emails_per_minute': 50,      # 50 emails per minute (allowing for delays)
    'emails_per_hour': 500,       # 500 emails per hour
    'emails_per_day': 5000,       # 5000 emails per day
    'wait_time_between_emails': 1.0,  # 1 second between emails
    'burst_limit': 10,            # 10 emails in burst
    'cooldown_period': 5,         # 5 seconds cooldown after 10 emails
    'daily_quota': 5000,
    'hourly_quota': 500,
    'minute_quota': 50,
    'second_quota': 1
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
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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
    """Initialize data files if they don't exist with server compatibility"""
    print("🔧 Initializing data files for server compatibility...")
    
    # Define files to initialize with their default content
    files_config = {
        ACCOUNTS_FILE: [],
        CAMPAIGNS_FILE: [],
        USERS_FILE: [{
            'id': 1,
            'username': 'admin',
            'password': generate_password_hash('admin123'),
            'role': 'admin',
            'email': 'admin@example.com',
            'created_at': datetime.now().isoformat(),
            'is_active': True
        }],
        CAMPAIGN_LOGS_FILE: {},
        NOTIFICATIONS_FILE: [],
        BOUNCE_DATA_FILE: {},
        DELIVERY_DATA_FILE: {},
        DATA_LISTS_FILE: []
    }
    
    # Initialize each file
    for filename, default_content in files_config.items():
        try:
            if not os.path.exists(filename):
                success = write_json_file_simple(filename, default_content)
                if success:
                    print(f"✅ Created {filename}")
                else:
                    print(f"❌ Failed to create {filename}")
            else:
                print(f"✅ {filename} already exists")
        except Exception as e:
            print(f"❌ Error initializing {filename}: {e}")
    
    # Create data_lists directory if it doesn't exist
    try:
        if not os.path.exists(DATA_LISTS_DIR):
            os.makedirs(DATA_LISTS_DIR, exist_ok=True)
            print(f"✅ Created directory {DATA_LISTS_DIR}")
        else:
            print(f"✅ Directory {DATA_LISTS_DIR} already exists")
    except Exception as e:
        print(f"❌ Error creating directory {DATA_LISTS_DIR}: {e}")
    
    # Check file permissions
    print("🔍 Checking file permissions...")
    for filename in files_config.keys():
        if os.path.exists(filename):
            try:
                # Test if we can read and write
                with open(filename, 'r') as f:
                    f.read(1)
                with open(filename, 'a') as f:
                    f.write('')
                print(f"✅ {filename} is readable and writable")
            except Exception as e:
                print(f"⚠️ {filename} has permission issues: {e}")
    
    print("🎯 Data file initialization completed")

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
    try:
        # Load data using robust file reading
        accounts = read_json_file_simple(ACCOUNTS_FILE)
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        notifications = read_json_file_simple(NOTIFICATIONS_FILE)
        
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
    except Exception as e:
        print(f"❌ Error in dashboard: {str(e)}")
        # Return a basic dashboard with error handling
        return render_template('dashboard.html', 
                             total_accounts=0,
                             active_campaigns=0,
                             emails_today=0,
                             success_rate=0,
                             total_sent=0,
                             total_bounced=0,
                             total_delivered=0,
                             zoho_bounce_stats={},
                             recent_campaigns=[],
                             recent_notifications=[],
                             status_counts={},
                             error=str(e))

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
    try:
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        accounts = read_json_file_simple(ACCOUNTS_FILE)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        if not campaign:
            flash('Campaign not found')
            return redirect(url_for('campaigns'))
        
        return render_template('edit_campaign.html', campaign=campaign, accounts=accounts)
    except Exception as e:
        print(f"❌ Error in edit_campaign: {str(e)}")
        flash('Error loading campaign data')
        return redirect(url_for('campaigns'))

@app.route('/live-campaigns')
@login_required
def live_campaigns():
    """New page to monitor all running campaigns and recently completed ones"""
    try:
        all_campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        if not isinstance(all_campaigns, list):
            all_campaigns = []
    except Exception as e:
        print(f"❌ Error loading campaigns for live view: {str(e)}")
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
    try:
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        if not campaign:
            flash('Campaign not found')
            return redirect(url_for('campaigns'))
        
        logs = get_campaign_logs(campaign_id)
        return render_template('campaign_logs.html', campaign=campaign, logs=logs)
    except Exception as e:
        print(f"❌ Error in campaign_logs: {str(e)}")
        flash('Error loading campaign logs')
        return redirect(url_for('campaigns'))

@app.route('/notifications')
@login_required
def notifications():
    """Notifications page"""
    try:
        notifications = read_json_file_simple(NOTIFICATIONS_FILE)
    except Exception as e:
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
            
            # Detect available templates for this account
            print(f"🔍 Detecting templates for new account: {data['name']}")
            try:
                available_templates = detect_available_templates(new_account)
                if available_templates:
                    new_account['template_info'] = available_templates
                    # Store Zoho templates if available
                    first_template = available_templates[0] if available_templates else None
                    if first_template:
                        new_account['zoho_templates'] = first_template.get('zoho_templates', [])
                        new_account['template_mapping'] = first_template.get('template_mapping', {})
                    print(f"✅ Detected {len(available_templates)} templates for account")
                else:
                    print(f"⚠️ No templates detected for account")
                    new_account['template_info'] = []
                    new_account['zoho_templates'] = []
                    new_account['template_mapping'] = {}
            except Exception as e:
                print(f"⚠️ Error detecting templates: {e}")
                new_account['template_info'] = []
                new_account['zoho_templates'] = []
                new_account['template_mapping'] = {}
            
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
                print("❌ No JSON data received")
                return jsonify({'error': 'No data provided'}), 400
            
            print(f"🔍 Received campaign data: {data}")
            print(f"🔍 Data type: {type(data)}")
            print(f"🔍 Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Enhanced validation with detailed debugging
            required_fields = ['name', 'account_id', 'subject', 'message', 'data_list_id']
            missing_fields = []
            
            for field in required_fields:
                print(f"🔍 Checking field: {field}")
                if field not in data:
                    missing_fields.append(f"{field} (not present)")
                    print(f"❌ Field {field} not present in data")
                elif data[field] is None:
                    missing_fields.append(f"{field} (null)")
                    print(f"❌ Field {field} is null")
                elif isinstance(data[field], str) and not data[field].strip():
                    missing_fields.append(f"{field} (empty string)")
                    print(f"❌ Field {field} is empty string")
                elif isinstance(data[field], (int, float)) and data[field] <= 0:
                    missing_fields.append(f"{field} (invalid value: {data[field]})")
                    print(f"❌ Field {field} has invalid value: {data[field]}")
                else:
                    print(f"✅ Field {field} is valid: {data[field]}")
            
            if missing_fields:
                error_msg = f"Missing or invalid required fields: {', '.join(missing_fields)}"
                print(f"❌ Validation failed: {error_msg}")
                return jsonify({'error': error_msg, 'missing_fields': missing_fields}), 400
            
            print(f"✅ All required fields validated successfully")
            
            # Simple file reading
            campaigns = read_json_file_simple(CAMPAIGNS_FILE)
            if not isinstance(campaigns, list):
                campaigns = []
            
            # Generate new campaign ID
            new_id = max([camp['id'] for camp in campaigns], default=0) + 1 if campaigns else 1
            
            # Handle rate limiting settings
            rate_limits = data.get('rate_limits')
            
            # Create campaign object with new universal structure
            new_campaign = {
                'id': new_id,
                'name': str(data['name'])[:100],  # Limit name length
                'account_id': int(data['account_id']),
                'subject': str(data['subject']),
                'message': str(data['message']),  # Custom template content
                'data_list_id': int(data['data_list_id']),
                'from_name': str(data.get('from_name', 'Campaign Sender')),
                'template_id': str(data.get('template_id', '')),  # Optional Zoho template ID
                'use_custom_template': data.get('use_custom_template', True),  # Default to custom template
                'rate_limits': rate_limits,  # Custom rate limits for this campaign
                'status': 'ready',
                'created_at': datetime.now().isoformat(),
                'created_by': current_user.id,
                'total_sent': 0,
                'total_attempted': 0,
                'system_version': 'universal_v2'  # Mark as using new system
            }
            
            # Add to campaigns list
            campaigns.append(new_campaign)
            
            # Robust file writing with detailed error handling
            print(f"💾 Attempting to save campaign to {CAMPAIGNS_FILE}")
            save_success = write_json_file_simple(CAMPAIGNS_FILE, campaigns)
            
            if save_success:
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
                # Try to get more detailed error information
                import os
                current_dir = os.getcwd()
                file_path = os.path.abspath(CAMPAIGNS_FILE)
                file_exists = os.path.exists(CAMPAIGNS_FILE)
                file_writable = os.access(os.path.dirname(file_path), os.W_OK) if os.path.dirname(file_path) else True
                
                error_details = {
                    'error': 'Failed to save campaign to file',
                    'details': {
                        'current_directory': current_dir,
                        'file_path': file_path,
                        'file_exists': file_exists,
                        'directory_writable': file_writable,
                        'campaigns_count': len(campaigns)
                    }
                }
                
                print(f"❌ Campaign save failed: {error_details}")
                return jsonify(error_details), 500
                
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
    with open(CAMPAIGNS_FILE, 'r', encoding='utf-8') as f:
        campaigns = json.load(f)
    
    campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    if campaign['status'] == 'running':
        return jsonify({'error': 'Campaign is already running'}), 400
    
    if campaign['status'] not in ['ready', 'stopped', 'paused']:
        return jsonify({'error': 'Campaign cannot be started from current status'}), 400
    
    # Get account
    with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
        accounts = json.load(f)
    
    account = next((acc for acc in accounts if acc['id'] == campaign['account_id']), None)
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    # Check if campaign uses new universal system
    if campaign.get('system_version') == 'universal_v2':
        # Use new universal system
        print(f"🚀 Starting universal campaign: {campaign['name']}")
        
        # Update campaign status
        campaign['status'] = 'running'
        campaign['started_at'] = datetime.now().isoformat()
        campaign['total_sent'] = 0
        campaign['total_attempted'] = 0
        
        with open(CAMPAIGNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(campaigns, f)
        
        # Clear previous logs
        save_campaign_logs(campaign_id, [])
        
        # Add to running campaigns
        running_campaigns[campaign_id] = True
        
        # Start campaign in background thread using universal system
        thread = threading.Thread(target=send_universal_campaign_emails, args=(campaign, account))
        thread.daemon = True
        thread.start()
        
        add_notification(f"Campaign '{campaign['name']}' started successfully", 'success', campaign_id)
        return jsonify({'message': 'Campaign started successfully'})
    else:
        # Legacy campaign - use old system for backward compatibility
        print(f"🚀 Starting legacy campaign: {campaign['name']}")
        
        # Update campaign status
        campaign['status'] = 'running'
        campaign['started_at'] = datetime.now().isoformat()
        campaign['total_sent'] = 0
        campaign['total_attempted'] = 0
        
        with open(CAMPAIGNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(campaigns, f)
        
        # Clear previous logs
        save_campaign_logs(campaign_id, [])
        
        # Add to running campaigns
        running_campaigns[campaign_id] = True
        
        # Start campaign in background thread using old system
        thread = threading.Thread(target=send_campaign_emails, args=(campaign, account))
        thread.daemon = True
        thread.start()
        
        add_notification(f"Campaign '{campaign['name']}' started successfully (legacy mode)", 'success', campaign_id)
        return jsonify({'message': 'Campaign started successfully (legacy mode)'})

@app.route('/api/campaigns/<int:campaign_id>/stop', methods=['POST'])
@login_required
def stop_campaign(campaign_id):
    with open(CAMPAIGNS_FILE, 'r', encoding='utf-8') as f:
        campaigns = json.load(f)
    
    campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    if campaign['status'] != 'running':
        return jsonify({'error': 'Campaign is not running'}), 400
    
    # Stop campaign
    campaign['status'] = 'stopped'
    campaign['stopped_at'] = datetime.now().isoformat()
    
    with open(CAMPAIGNS_FILE, 'w', encoding='utf-8') as f:
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
    with open(CAMPAIGNS_FILE, 'r', encoding='utf-8') as f:
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
    
    # Start campaign in background thread using new sequential sending
    if campaign.get('system_version') == 'universal_v2':
        thread = threading.Thread(target=send_universal_campaign_emails, args=(campaign, account))
    else:
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
    try:
        # Use robust file reading functions
        accounts = read_json_file_simple(ACCOUNTS_FILE)
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        
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
        
    except Exception as e:
        print(f"❌ Error in api_stats: {str(e)}")
        return jsonify({
            'total_accounts': 0,
            'active_campaigns': 0,
            'emails_today': 0,
            'delivery_rate': 0,
            'bounce_rate': 0,
            'total_sent': 0,
            'total_delivered': 0,
            'total_bounced': 0,
            'total_campaigns': 0,
            'status_counts': {},
            'error': str(e)
        }), 500

@app.route('/api/campaigns/<int:campaign_id>/delivery-stats')
@login_required
def get_campaign_delivery_stats(campaign_id):
    """Get detailed delivery statistics for a specific campaign"""
    try:
        # Get campaign using robust file reading
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        
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
        print(f"❌ Error in get_campaign_delivery_stats: {str(e)}")
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

@app.route('/api/campaigns/<int:campaign_id>/logs/refresh', methods=['GET'])
@login_required
def refresh_campaign_logs_api(campaign_id):
    """Refresh campaign logs and return latest data"""
    try:
        logs = get_campaign_logs(campaign_id)
        
        # Also get updated campaign stats
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
        
        return jsonify({
            'success': True,
            'logs': logs,
            'campaign': campaign,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ API Error refreshing logs for campaign {campaign_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': [],
            'campaign': None,
            'timestamp': datetime.now().isoformat()
        })

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

def send_campaign_emails(campaign, account):
    """Send emails for a campaign in background thread with IMPROVED feedback and bounce detection"""
    campaign_id = campaign['id']
    
    try:
        print(f"🚀 Starting campaign: {campaign['name']} (ID: {campaign_id})")
        print(f"📧 Using SIMPLE email sending without rate limits")
        
        # Create initial log entry
        start_log = {
            'campaign_id': campaign_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'info',
            'message': f"🚀 Campaign '{campaign['name']}' started with SIMPLE delivery",
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
        print(f"🎯 SIMPLE delivery tracking enabled")
        print(f"🔍 Bounce detection enabled")
        
        # Get the correct template URL and function for this account
        template_config = get_template_url_and_function(account, campaign.get('template_id'))
        url = template_config['url']
        function_name = template_config['function_name']
        template_number = template_config['template_number']
        
        print(f"📧 Using template {template_number} for account: {account['name']}")
        print(f"🔗 Template URL: {url}")
        print(f"⚙️ Function: {function_name}")
        
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
            
            # Select random subject and sender
            subject = random.choice(subjects) if subjects else "Default Subject"
            sender = random.choice(froms) if froms else "Default Sender"
            
            # Deluge script matching your working curl format with dynamic template function
            script = f'''void automation.{function_name}()
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

            # Simple send without rate limits
            print(f"📤 Sending email to: {email}")
            print(f"   Subject: {subject}")
            print(f"   Sender: {sender}")
            
            try:
                # Make API request
                response = requests.post(
                    url,
                    json=json_data,
                    cookies=account['cookies'],
                    headers=enhanced_headers,
                    timeout=30
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
                
                # Check response
                if response.status_code == 200:
                    print(f"✅ Email sent successfully to {email}")
                    sent_count += 1
                    
                    # Log success
                    success_log = {
                        'campaign_id': campaign_id,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'success',
                        'message': f"✅ Email sent successfully to {email}",
                        'email': email,
                        'subject': subject,
                        'sender': sender,
                        'type': 'email_sent',
                        'total_sent': sent_count,
                        'total_attempted': i + 1
                    }
                    add_campaign_log(campaign_id, success_log)
                    socketio.emit('email_progress', success_log)
                    
                    # Check for REAL delivery status
                    print(f"🔍 Checking delivery status for {email}...")
                    delivery_status = check_email_delivery_status(email, campaign_id, account)
                    
                    if delivery_status.get('delivered'):
                        delivered_count += 1
                        add_delivered_email(email, campaign_id, subject, sender, delivery_status)
                        print(f"✅ Email confirmed delivered to {email}")
                    elif delivery_status.get('bounced'):
                        bounced_count += 1
                        add_bounce_email(email, campaign_id, delivery_status.get('bounce_reason', 'Unknown'), subject, sender)
                        print(f"❌ Email bounced: {email} - {delivery_status.get('bounce_reason', 'Unknown')}")
                    else:
                        print(f"⚠️ Delivery status unknown for {email}")
                    
                else:
                    # Handle errors
                    error_msg = f"❌ API Error ({response.status_code}): {message} | Code: {code}"
                    print(error_msg)
                    error_count += 1
                    
                    error_log = {
                        'campaign_id': campaign_id,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'message': error_msg,
                        'email': email,
                        'subject': subject,
                        'sender': sender,
                        'type': 'api_error',
                        'response_code': response.status_code,
                        'api_message': message,
                        'api_code': code
                    }
                    add_campaign_log(campaign_id, error_log)
                    socketio.emit('email_progress', error_log)
                    
                    # If it's an authentication error, stop the campaign
                    if response.status_code == 401:
                        auth_error_msg = f"❌ Authentication error - stopping campaign. Please check account credentials."
                        print(auth_error_msg)
                        add_notification(auth_error_msg, 'error', campaign_id)
                        break
                    
            except requests.exceptions.Timeout:
                timeout_msg = f"⏰ Timeout sending email to {email}"
                print(timeout_msg)
                error_count += 1
                
                timeout_log = {
                    'campaign_id': campaign_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'error',
                    'message': timeout_msg,
                    'email': email,
                    'subject': subject,
                    'sender': sender,
                    'type': 'timeout'
                }
                add_campaign_log(campaign_id, timeout_log)
                socketio.emit('email_progress', timeout_log)
                
            except requests.exceptions.RequestException as e:
                network_error = f"❌ Network error sending email to {email}: {str(e)}"
                print(network_error)
                error_count += 1
                
                network_log = {
                    'campaign_id': campaign_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'error',
                    'message': network_error,
                    'email': email,
                    'subject': subject,
                    'sender': sender,
                    'type': 'network_error',
                    'exception': str(e)
                }
                add_campaign_log(campaign_id, network_log)
                socketio.emit('email_progress', network_log)
            
            # Update campaign progress
            campaigns = read_json_file_simple(CAMPAIGNS_FILE)
            campaign_index = next((i for i, c in enumerate(campaigns) if c['id'] == campaign_id), None)
            
            if campaign_index is not None:
                campaigns[campaign_index]['total_sent'] = sent_count
                campaigns[campaign_index]['total_attempted'] = i + 1
                write_json_file_simple(CAMPAIGNS_FILE, campaigns)
            
            # Small delay between emails to avoid overwhelming the API
            time.sleep(0.5)
        
        # Campaign completed
        completion_msg = f"🏁 Campaign '{campaign['name']}' completed! Sent: {sent_count}, Errors: {error_count}, Delivered: {delivered_count}, Bounced: {bounced_count}"
        print(completion_msg)
        
        completion_log = {
            'campaign_id': campaign_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'info',
            'message': completion_msg,
            'type': 'completion',
            'total_sent': sent_count,
            'total_errors': error_count,
            'total_delivered': delivered_count,
            'total_bounced': bounced_count
        }
        add_campaign_log(campaign_id, completion_log)
        socketio.emit('email_progress', completion_log)
        
        # Update campaign status
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        campaign_index = next((i for i, c in enumerate(campaigns) if c['id'] == campaign_id), None)
        
        if campaign_index is not None:
            campaigns[campaign_index]['status'] = 'completed'
            campaigns[campaign_index]['completed_at'] = datetime.now().isoformat()
            campaigns[campaign_index]['total_sent'] = sent_count
            campaigns[campaign_index]['total_attempted'] = total_emails
            write_json_file_simple(CAMPAIGNS_FILE, campaigns)
        
        # Remove from running campaigns
        if campaign_id in running_campaigns:
            del running_campaigns[campaign_id]
        
        # Send completion notification
        add_notification(completion_msg, 'success', campaign_id)
        
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
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        campaign_index = next((i for i, c in enumerate(campaigns) if c['id'] == campaign_id), None)
        
        if campaign_index is not None:
            campaigns[campaign_index]['status'] = 'error'
            write_json_file_simple(CAMPAIGNS_FILE, campaigns)
        
        # Remove from running campaigns
        if campaign_id in running_campaigns:
            del running_campaigns[campaign_id]
        
        # Send error notification
        add_notification(f"❌ Campaign '{campaign['name']}' failed: {str(e)}", 'error', campaign_id)

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
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        if not isinstance(campaigns, list):
            campaigns = []
    except Exception as e:
        print(f"❌ Error loading campaigns: {str(e)}")
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

def test_account_authentication(account_id, test_email=None, custom_message=None, custom_subject=None, custom_from_name=None):
    """
    Test account by sending a test email to verify both authentication and email sending
    """
    try:
        # Load account
        accounts = read_json_file_simple(ACCOUNTS_FILE)
        account = next((acc for acc in accounts if acc['id'] == account_id), None)
        
        if not account:
            return {
                'success': False,
                'message': f'Account {account_id} not found'
            }
        
        # Use provided test email or default
        if not test_email:
            test_email = 'test@example.com'
        
        print(f"🧪 Testing account: {account['name']}")
        print(f"📧 Test email: {test_email}")
        
        # Get the correct template URL and function for this account
        template_config = get_template_url_and_function(account)
        url = template_config['url']
        function_name = template_config['function_name']
        template_number = template_config['template_number']
        
        print(f"📧 Using template {template_number}")
        print(f"🔗 Template URL: {url}")
        print(f"⚙️ Function: {function_name}")
        
        # Create test email content
        if custom_subject:
            test_subject = custom_subject
        else:
            test_subject = f"🧪 Test Email - {account['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Use custom message if provided, otherwise use default
        if custom_message:
            test_message = custom_message
        else:
            test_message = f"This is a test email from the Email Campaign Manager.\\n\\nAccount: {account['name']}\\nTemplate Function: {function_name}\\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\nIf you receive this email, the test was successful!\\n\\nThis confirms that:\\n- Your account authentication is working\\n- The template function is available\\n- Email sending is functional\\n\\nYou can now use this account for campaigns."
        
        # Set from name - use custom name if provided, otherwise use default
        if custom_from_name:
            from_name = custom_from_name
        else:
            from_name = "Test Sender"
        
        # Deluge script for test email - simple approach without fetching templates
        script = f'''void automation.{function_name}()
{{
    // Simple test email without fetching template
    testSubject = "{test_subject}";
    testMessage = "{test_message}";

    // Test recipient
    destinataires = list();
    destinataires.add("{test_email}");

    sendmail
    [
        from: "{from_name} <" + zoho.loginuserid + ">"
        to: destinataires
        subject: testSubject
        message: testMessage
    ];
    
    info "Test email sent successfully to {test_email}";
}}'''
        
        json_data = {'functions': [{'script': script, 'arguments': {}}]}
        headers = account['headers'].copy()
        headers.update({
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
        
        print(f"🚀 Sending test request to: {url}")
        response = requests.post(url, json=json_data, cookies=account['cookies'], headers=headers, timeout=30)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response text: {response.text[:500]}...")
        
        if response.status_code == 200:
            print(f"✅ Test email sent successfully to {test_email}")
            return {
                'success': True,
                'message': f'Test email sent successfully to {test_email}',
                'template_used': template_number,
                'function_used': function_name,
                'subject_used': test_subject,
                'from_used': f"{from_name} <{account.get('org_id', 'test')}@zoho.com>",
                'account_name': account.get('name', 'Unknown')
            }
        else:
            error_msg = f"❌ Test email failed (Status: {response.status_code})"
            print(error_msg)
            print(f"📄 Full response: {response.text}")
            return {
                'success': False,
                'message': f'Test email failed: HTTP {response.status_code}',
                'error': response.text,
                'account_name': account.get('name', 'Unknown'),
                'status_code': response.status_code,
                'template_used': template_number,
                'function_used': function_name,
                'subject_used': test_subject,
                'from_used': f"{from_name} <{account.get('org_id', 'test')}@zoho.com>"
            }
            
    except Exception as e:
        error_msg = f"❌ Error sending test email: {str(e)}"
        print(error_msg)
        return {
            'success': False,
            'message': f'Error sending test email: {str(e)}',
            'error': str(e)
        }

@app.route('/api/accounts/<int:account_id>/refresh-templates', methods=['POST'])
@login_required
def refresh_account_templates(account_id):
    """Refresh template detection for an account"""
    try:
        accounts = read_json_file_simple(ACCOUNTS_FILE)
        account = next((a for a in accounts if a['id'] == account_id), None)
        
        if not account:
            return jsonify({'error': 'Account not found'}), 404
        
        # Check permissions
        if current_user.role != 'admin' and account.get('created_by') != current_user.id:
            return jsonify({'error': 'Permission denied'}), 403
        
        # Detect templates
        print(f"🔍 Refreshing templates for account: {account['name']}")
        available_templates = detect_available_templates(account)
        
        # Update account with new template info
        for i, acc in enumerate(accounts):
            if acc['id'] == account_id:
                accounts[i]['template_info'] = available_templates
                write_json_file_simple(ACCOUNTS_FILE, accounts)
                break
        
        # Get the first available template info for additional details
        first_template = available_templates[0] if available_templates else None
        zoho_templates = first_template.get('zoho_templates', []) if first_template else []
        template_mapping = first_template.get('template_mapping', {}) if first_template else {}
        
        return jsonify({
            'success': True,
            'message': f'Found {len(available_templates)} templates and {len(zoho_templates)} Zoho templates',
            'templates': available_templates,
            'zoho_templates': zoho_templates,
            'template_mapping': template_mapping
        })
        
    except Exception as e:
        return jsonify({'error': f'Error refreshing templates: {str(e)}'}), 500

@app.route('/api/accounts/<int:account_id>/test', methods=['POST'])
@login_required
def test_account(account_id):
    """Test account authentication"""
    try:
        # Get test email and custom parameters from request
        data = request.get_json() if request.is_json else {}
        test_email = data.get('test_email', 'test@example.com')
        custom_message = data.get('custom_message')
        custom_subject = data.get('custom_subject')
        custom_from_name = data.get('custom_from_name')
        
        result = test_account_authentication(account_id, test_email, custom_message, custom_subject, custom_from_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error testing account: {str(e)}'
        }), 500

@app.route('/api/campaigns/<int:campaign_id>/test', methods=['POST'])
@login_required
def test_campaign(campaign_id):
    """Test campaign by sending a single test email"""
    try:
        # Get campaign data
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
        
        if not campaign:
            return jsonify({'success': False, 'message': 'Campaign not found'}), 404
        
        # Check permissions
        if not has_permission(current_user, 'manage_campaigns'):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        
        # Get account data
        accounts = read_json_file_simple(ACCOUNTS_FILE)
        account = next((acc for acc in accounts if acc['id'] == campaign['account_id']), None)
        
        if not account:
            return jsonify({'success': False, 'message': 'Account not found'}), 404
        
        # Get test email and custom parameters from request
        data = request.get_json()
        test_email = data.get('test_email')
        custom_message = data.get('custom_message')
        custom_subject = data.get('custom_subject')
        custom_from_name = data.get('custom_from_name')
        
        if not test_email:
            return jsonify({'success': False, 'message': 'Test email is required'}), 400
        
        # Send test email using campaign template
        result = send_test_email(account, test_email, campaign.get('template_id'), custom_message, custom_subject, custom_from_name)
        
        if result['success']:
            # Add test log
            add_campaign_log(campaign_id, {
                'timestamp': datetime.now().isoformat(),
                'type': 'test',
                'message': f'Test email sent to {test_email}',
                'details': result
            })
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error testing campaign: {str(e)}")
        return jsonify({'success': False, 'message': f'Error testing campaign: {str(e)}'}), 500

# Test email functionality
def send_test_email(account, test_email, template_id=None, custom_message=None, custom_subject=None, custom_from_name=None):
    """Send a test email to verify account connection and template functionality"""
    try:
        print(f"🧪 Sending test email to: {test_email}")
        print(f"📧 Using account: {account['name']}")
        
        # Get the correct template URL and function for this account
        template_config = get_template_url_and_function(account, template_id)
        url = template_config['url']
        function_name = template_config['function_name']
        template_number = template_config['template_number']
        
        print(f"📧 Using template {template_number} for test")
        print(f"🔗 Template URL: {url}")
        print(f"⚙️ Function: {function_name}")
        
        # Create test email content
        if custom_subject:
            test_subject = custom_subject
        else:
            test_subject = f"🧪 Test Email - {account['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Use custom message if provided, otherwise use default
        if custom_message:
            test_message = custom_message
        else:
            test_message = f"This is a test email from the Email Campaign Manager.\\n\\nAccount: {account['name']}\\nTemplate Function: {function_name}\\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\nIf you receive this email, the test was successful!\\n\\nThis confirms that:\\n- Your account authentication is working\\n- The template function is available\\n- Email sending is functional\\n\\nYou can now use this account for campaigns."
        
        # Set from name - use custom name if provided, otherwise use default
        if custom_from_name:
            from_name = custom_from_name
        else:
            from_name = "Test Sender"
        
        # Deluge script for test email - simple approach without fetching templates
        script = f'''void automation.{function_name}()
{{
    // Simple test email without fetching template
    testSubject = "{test_subject}";
    testMessage = "{test_message}";

    // Test recipient
    destinataires = list();
    destinataires.add("{test_email}");

    sendmail
    [
        from: "{from_name} <" + zoho.loginuserid + ">"
        to: destinataires
        subject: testSubject
        message: testMessage
    ];
    
    info "Test email sent successfully to {test_email}";
}}'''
        
        json_data = {'functions': [{'script': script, 'arguments': {}}]}
        
        # Use the exact same headers as the working campaign function
        headers = account['headers'].copy()
        headers.update({
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
        
        print(f"🚀 Sending test request to: {url}")
        print(f"📄 Request data: {json_data}")
        
        response = requests.post(url, json=json_data, cookies=account['cookies'], headers=headers, timeout=30)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response text: {response.text[:500]}...")
        
        if response.status_code == 200:
            print(f"✅ Test email sent successfully to {test_email}")
            return {
                'success': True,
                'message': f'Test email sent successfully to {test_email}',
                'template_used': template_number,
                'function_used': function_name,
                'subject_used': test_subject,
                'from_used': f"{from_name} <{account.get('org_id', 'test')}@zoho.com>"
            }
        else:
            error_msg = f"❌ Test email failed (Status: {response.status_code})"
            print(error_msg)
            print(f"📄 Full response: {response.text}")
            return {
                'success': False,
                'message': f'Test email failed: HTTP {response.status_code}',
                'error': response.text,
                'template_used': template_number,
                'function_used': function_name,
                'subject_used': test_subject,
                'from_used': f"{from_name} <{account.get('org_id', 'test')}@zoho.com>"
            }
            
    except Exception as e:
        error_msg = f"❌ Error sending test email: {str(e)}"
        print(error_msg)
        return {
            'success': False,
            'message': f'Error sending test email: {str(e)}',
            'error': str(e)
        }

# Simple memory optimization functions
def log_memory_usage():
    """Log current memory usage for debugging"""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        print(f"📊 Memory Usage: {memory_info.rss / 1024 / 1024:.1f} MB")
        return memory_info.rss / 1024 / 1024
    except:
        return 0

def cleanup_memory():
    """Force garbage collection to free memory"""
    try:
        gc.collect()
        print(f"🧹 Memory cleanup completed. Current usage: {log_memory_usage():.1f} MB")
    except:
        pass

def read_json_file_simple(filename):
    """Read JSON file with robust error handling for server environments"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ File not found: {filename} - creating empty file")
        # Create empty file with appropriate default
        if 'campaigns' in filename:
            default_data = []
        elif 'accounts' in filename:
            default_data = []
        elif 'users' in filename:
            default_data = []
        elif 'notifications' in filename:
            default_data = []
        elif 'data_lists' in filename:
            default_data = []
        else:
            default_data = {}
        
        # Try to create the file
        try:
            write_json_file_simple(filename, default_data)
            return default_data
        except Exception as e:
            print(f"❌ Could not create {filename}: {e}")
            return default_data
            
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON decode error in {filename}: {e}")
        # Try to backup corrupted file and create new one
        try:
            import shutil
            backup_name = filename + '.backup.' + str(int(time.time()))
            shutil.copy2(filename, backup_name)
            print(f"📁 Backed up corrupted file to {backup_name}")
        except:
            pass
        
        # Return appropriate default
        if 'campaigns' in filename:
            return []
        elif 'accounts' in filename:
            return []
        elif 'users' in filename:
            return []
        elif 'notifications' in filename:
            return []
        elif 'data_lists' in filename:
            return []
        else:
            return {}
            
    except Exception as e:
        print(f"⚠️ Error reading {filename}: {e}")
        # Return appropriate default
        if 'campaigns' in filename:
            return []
        elif 'accounts' in filename:
            return []
        elif 'users' in filename:
            return []
        elif 'notifications' in filename:
            return []
        elif 'data_lists' in filename:
            return []
        else:
            return {}

def write_json_file_simple(filename, data):
    """Write JSON file with robust error handling for server environments"""
    try:
        # Ensure the directory exists
        import os
        directory = os.path.dirname(filename)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        # Create a temporary file first
        temp_filename = filename + '.tmp'
        
        # Write to temporary file
        with open(temp_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Atomic move (works on both Windows and Unix)
        import shutil
        shutil.move(temp_filename, filename)
        
        print(f"✅ Successfully wrote {filename}")
        return True
        
    except PermissionError as e:
        print(f"❌ Permission error writing {filename}: {e}")
        # Try to create with different permissions
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Successfully wrote {filename} with fallback method")
            return True
        except Exception as e2:
            print(f"❌ Fallback also failed for {filename}: {e2}")
            return False
            
    except Exception as e:
        print(f"❌ Error writing {filename}: {e}")
        # Try one more time with basic method
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Successfully wrote {filename} with basic method")
            return True
        except Exception as e2:
            print(f"❌ All methods failed for {filename}: {e2}")
            return False

# Template detection and management functions
def detect_available_templates(account):
    """Detect available email templates for an account and fetch template IDs"""
    try:
        print(f"🔍 Detecting templates for account: {account['name']}")
        
        available_templates = []
        template_numbers = [2, 3, 4, 5, 6, 7, 8, 9, 10]  # Common template numbers
        
        # First, try to fetch all email templates from Zoho CRM
        print(f"📧 Fetching email templates from Zoho CRM...")
        try:
            templates_url = "https://www.zohoapis.com/crm/v7/settings/email_templates"
            headers = account['headers'].copy()
            headers.update({
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
            
            response = requests.get(
                templates_url,
                cookies=account['cookies'],
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                templates_data = response.json()
                zoho_templates = templates_data.get('email_templates', [])
                print(f"✅ Successfully fetched {len(zoho_templates)} templates from Zoho CRM")
                
                # Create a mapping of template names to IDs
                template_mapping = {}
                for template in zoho_templates:
                    template_name = template.get('name', 'Unknown')
                    template_id = template.get('id', '')
                    template_mapping[template_name.lower()] = {
                        'id': template_id,
                        'name': template_name,
                        'subject': template.get('subject', ''),
                        'content': template.get('content', '')[:100] + '...' if template.get('content') else ''
                    }
                    print(f"📋 Found template: {template_name} (ID: {template_id})")
            else:
                print(f"⚠️ Could not fetch templates from Zoho CRM (Status: {response.status_code})")
                zoho_templates = []
                template_mapping = {}
                
        except Exception as e:
            print(f"⚠️ Error fetching templates from Zoho CRM: {str(e)}")
            zoho_templates = []
            template_mapping = {}
        
        # Now test each template function
        for template_num in template_numbers:
            try:
                # Test template endpoint
                url = f"https://crm.zoho.com/crm/v7/settings/functions/send_email_template{template_num}/actions/test"
                
                # Create a simple test script
                test_script = f'''void automation.Send_Email_Template{template_num}()
{{
    // Simple test to check if template exists
    info "Template {template_num} test";
}}'''
                
                json_data = {
                    'functions': [
                        {
                            'script': test_script,
                            'arguments': {},
                        },
                    ],
                }
                
                headers = account['headers'].copy()
                headers.update({
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
                
                response = requests.post(
                    url,
                    json=json_data,
                    cookies=account['cookies'],
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    template_info = {
                        'number': template_num,
                        'url': url,
                        'function_name': f'Send_Email_Template{template_num}',
                        'status': 'available',
                        'zoho_templates': zoho_templates,  # Include all fetched templates
                        'template_mapping': template_mapping  # Include template mapping
                    }
                    available_templates.append(template_info)
                    print(f"✅ Template {template_num} is available")
                else:
                    print(f"❌ Template {template_num} not available (Status: {response.status_code})")
                    
            except Exception as e:
                print(f"⚠️ Error testing template {template_num}: {str(e)}")
                continue
        
        print(f"📊 Found {len(available_templates)} available templates")
        return available_templates
        
    except Exception as e:
        print(f"❌ Error detecting templates: {str(e)}")
        return []

def get_account_template_info(account, template_id=None):
    """Get template information for an account"""
    try:
        # If account has stored template info, use it
        if 'template_info' in account and account['template_info']:
            templates = account['template_info']
            
            # If specific template_id requested, find it
            if template_id:
                for template in templates:
                    if template.get('template_id') == template_id:
                        return template
                return None
            
            # Return first available template as default
            return templates[0] if templates else None
        
        # Fallback: detect templates if not stored
        print(f"🔍 No stored template info, detecting templates for account: {account['name']}")
        available_templates = detect_available_templates(account)
        
        # Update account with template info
        if available_templates:
            account['template_info'] = available_templates
            # Save updated account info
            try:
                accounts = read_json_file_simple(ACCOUNTS_FILE)
                for i, acc in enumerate(accounts):
                    if acc['id'] == account['id']:
                        accounts[i]['template_info'] = available_templates
                        write_json_file_simple(ACCOUNTS_FILE, accounts)
                        break
            except Exception as e:
                print(f"⚠️ Could not save template info: {e}")
        
        return available_templates[0] if available_templates else None
        
    except Exception as e:
        print(f"❌ Error getting template info: {str(e)}")
        return None

def get_template_url_and_function(account, template_id=None):
    """Get the correct URL and function name for an account's template"""
    try:
        template_info = get_account_template_info(account, template_id)
        
        if template_info:
            return {
                'url': template_info['url'],
                'function_name': template_info['function_name'],
                'template_number': template_info['number']
            }
        else:
            # Test which templates are actually available for this account
            print(f"🔍 Testing available templates for account: {account['name']}")
            available_templates = []
            
            # Test templates 1-10 to see which ones exist
            for template_num in range(1, 11):
                test_url = f"https://crm.zoho.com/crm/v7/settings/functions/send_email_template{template_num}/actions/test"
                
                try:
                    # Create a simple test script
                    test_script = f'''void automation.Send_Email_Template{template_num}()
{{
    info "Testing template {template_num}";
}}'''
                    
                    test_data = {'functions': [{'script': test_script, 'arguments': {}}]}
                    
                    # Use account headers
                    headers = account['headers'].copy()
                    headers.update({
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
                    
                    response = requests.post(test_url, json=test_data, cookies=account['cookies'], headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        print(f"✅ Template {template_num} is available")
                        available_templates.append({
                            'url': test_url,
                            'function_name': f'Send_Email_Template{template_num}',
                            'number': template_num
                        })
                    else:
                        print(f"❌ Template {template_num} not available (Status: {response.status_code})")
                        
                except Exception as e:
                    print(f"❌ Error testing template {template_num}: {e}")
                    continue
            
            if available_templates:
                # Use the first available template
                selected_template = available_templates[0]
                print(f"🎯 Using template {selected_template['number']} for account {account['name']}")
                
                # Save this info to the account for future use
                try:
                    accounts = read_json_file_simple(ACCOUNTS_FILE)
                    for i, acc in enumerate(accounts):
                        if acc['id'] == account['id']:
                            accounts[i]['template_info'] = available_templates
                            write_json_file_simple(ACCOUNTS_FILE, accounts)
                            break
                except Exception as e:
                    print(f"⚠️ Could not save template info: {e}")
                
                return selected_template
            else:
                # No templates found, use template1 as last resort
                print(f"⚠️ No templates found for account {account['name']}, using template1 as fallback")
                return {
                    'url': "https://crm.zoho.com/crm/v7/settings/functions/send_email_template1/actions/test",
                    'function_name': 'Send_Email_Template1',
                    'template_number': 1
                }
            
    except Exception as e:
        print(f"❌ Error getting template URL: {str(e)}")
        # Fallback to template1 instead of template3
        return {
            'url': "https://crm.zoho.com/crm/v7/settings/functions/send_email_template1/actions/test",
            'function_name': 'Send_Email_Template1',
            'template_number': 1
        }

def send_universal_email(account, recipients, subject, message, from_name=None, template_id=None, campaign_id=None):
    """
    Universal email sending function based on the test email mechanism
    This replaces the old campaign sending logic with the proven test email approach
    """
    try:
        print(f"📧 Sending universal email to {len(recipients)} recipients")
        print(f"📧 Using account: {account['name']}")
        print(f"📨 Subject: {subject}")
        print(f"👤 From: {from_name or 'Default Sender'}")
        
        # Rate limiting check
        user_id = current_user.id if current_user else 1
        allowed, wait_time, reason = check_rate_limit(user_id, campaign_id)
        if not allowed:
            print(f"⏱️ Rate limit exceeded: {reason}")
            return {
                'success': False,
                'message': f'Rate limit exceeded: {reason}',
                'rate_limited': True,
                'wait_time': wait_time
            }
        
        # Get the correct template URL and function for this account
        template_config = get_template_url_and_function(account, template_id)
        url = template_config['url']
        function_name = template_config['function_name']
        template_number = template_config['template_number']
        
        print(f"📧 Using template {template_number}")
        print(f"🔗 Template URL: {url}")
        print(f"⚙️ Function: {function_name}")
        
        # Set from name - use provided name or default
        if from_name:
            from_display = from_name
        else:
            from_display = "Campaign Sender"
        
        # Properly escape the message content for Deluge script
        def escape_for_deluge(text):
            """Escape text for Deluge script while preserving HTML formatting"""
            # First, normalize line endings
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            # Remove all line breaks and extra spaces to create single-line HTML
            text = ' '.join(text.split())
            # Escape quotes
            text = text.replace('"', '\\"')
            return text
        
        escaped_message = escape_for_deluge(message)
        escaped_subject = escape_for_deluge(subject)
        
        # Create the Deluge script for sending emails
        # Convert recipients list to Deluge list format
        recipients_list = '[' + ', '.join([f'"{email}"' for email in recipients]) + ']'
        
        script = f'''void automation.{function_name}()
{{
    // Universal email sending using custom content
    emailSubject = "{escaped_subject}";
    emailMessage = "{escaped_message}";
    
    // Recipients list
    destinataires = {recipients_list};
    
    sendmail
    [
        from: "{from_display} <" + zoho.loginuserid + ">"
        to: destinataires
        subject: emailSubject
        html: emailMessage
    ];
    
    info "Universal email sent successfully to " + destinataires.size() + " recipients";
}}'''
        
        json_data = {'functions': [{'script': script, 'arguments': {}}]}
        
        # Use the exact same headers as the working test email function
        headers = account['headers'].copy()
        headers.update({
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
        
        print(f"🚀 Sending universal email request to: {url}")
        print(f"📄 Recipients count: {len(recipients)}")
        
        response = requests.post(url, json=json_data, cookies=account['cookies'], headers=headers, timeout=60)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response text: {response.text[:500]}...")
        
        if response.status_code == 200:
            print(f"✅ Universal email sent successfully to {len(recipients)} recipients")
            
            # Update rate limit counters
            update_rate_limit_counters(user_id)
            
            # Log successful sends
            if campaign_id:
                for recipient in recipients:
                    add_delivered_email(recipient, campaign_id, subject, f"{from_display} <{account.get('org_id', 'test')}@zoho.com>", {
                        'template_used': template_number,
                        'function_used': function_name,
                        'account_name': account['name']
                    })
            
            return {
                'success': True,
                'message': f'Email sent successfully to {len(recipients)} recipients',
                'recipients_count': len(recipients),
                'template_used': template_number,
                'function_used': function_name,
                'subject_used': subject,
                'from_used': f"{from_display} <{account.get('org_id', 'test')}@zoho.com>",
                'account_name': account['name']
            }
        else:
            error_msg = f"❌ Universal email failed (Status: {response.status_code})"
            print(error_msg)
            print(f"📄 Full response: {response.text}")
            
            # Log failed sends
            if campaign_id:
                for recipient in recipients:
                    add_bounce_email(recipient, campaign_id, "API Error", subject, f"{from_display} <{account.get('org_id', 'test')}@zoho.com>")
            
            return {
                'success': False,
                'message': f'Email sending failed: HTTP {response.status_code}',
                'error': response.text,
                'recipients_count': len(recipients),
                'template_used': template_number,
                'function_used': function_name,
                'subject_used': subject,
                'from_used': f"{from_display} <{account.get('org_id', 'test')}@zoho.com>",
                'account_name': account['name']
            }
            
    except Exception as e:
        error_msg = f"❌ Error sending universal email: {str(e)}"
        print(error_msg)
        
        # Log error for all recipients
        if campaign_id:
            for recipient in recipients:
                add_bounce_email(recipient, campaign_id, "System Error", subject, f"{from_display} <{account.get('org_id', 'test')}@zoho.com>")
        
        return {
            'success': False,
            'message': f'Error sending email: {str(e)}',
            'error': str(e),
            'recipients_count': len(recipients)
        }

def send_universal_campaign_emails(campaign, account):
    """
    Universal campaign sending function using the new universal email system
    This replaces the old send_campaign_emails function
    """
    try:
        print(f"🚀 Starting universal campaign: {campaign['name']}")
        print(f"📧 Account: {account['name']}")
        print(f"📨 Subject: {campaign['subject']}")
        print(f"👤 From: {campaign.get('from_name', 'Campaign Sender')}")
        
        # Get data list emails
        data_list_id = campaign.get('data_list_id')
        if not data_list_id:
            print("❌ No data list ID found in campaign")
            return
        
        # Get emails from data list
        try:
            emails = get_data_list_emails(data_list_id)
            if not emails:
                print("❌ No emails found in data list")
                return
            print(f"📧 Found {len(emails)} emails in data list")
        except Exception as e:
            print(f"❌ Error getting emails from data list: {str(e)}")
            return
        
        # Filter out bounced emails
        bounced_emails = get_bounced_emails(campaign['id'])
        filtered_emails = [email for email in emails if email not in bounced_emails]
        
        if len(filtered_emails) != len(emails):
            print(f"⚠️ Filtered out {len(emails) - len(filtered_emails)} bounced emails")
        
        if not filtered_emails:
            print("❌ No valid emails to send to after filtering")
            return
        
        # Get campaign content
        subject = campaign['subject']
        message = campaign['message']  # Custom template content
        from_name = campaign.get('from_name', 'Campaign Sender')
        template_id = campaign.get('template_id', None)
        
        print(f"📄 Message length: {len(message)} characters")
        print(f"📋 Using custom template: {campaign.get('use_custom_template', True)}")
        
        # Send emails using sequential email function (one by one)
        result = send_sequential_emails(
            account=account,
            recipients=filtered_emails,
            subject=subject,
            message=message,
            from_name=from_name,
            template_id=template_id,
            campaign_id=campaign['id']
        )
        
        # Update campaign status based on result
        campaigns = read_json_file_simple(CAMPAIGNS_FILE)
        campaign_index = next((i for i, c in enumerate(campaigns) if c['id'] == campaign['id']), None)
        if campaign_index is not None:
            if result['success']:
                campaigns[campaign_index]['status'] = 'completed'
                campaigns[campaign_index]['completed_at'] = datetime.now().isoformat()
                campaigns[campaign_index]['total_sent'] = result.get('emails_sent', 0)
                campaigns[campaign_index]['total_attempted'] = result.get('total_attempted', 0)
                # Add success log
                add_campaign_log(campaign['id'], {
                    'timestamp': datetime.now().isoformat(),
                    'type': 'success',
                    'message': f'Campaign completed successfully. Sent to {result.get("emails_sent", 0)} recipients.',
                    'details': result
                })
                print(f"✅ Campaign completed successfully - {result.get('emails_sent', 0)} emails sent")
                add_notification(f"Campaign '{campaign['name']}' completed successfully", 'success', campaign['id'])
            else:
                campaigns[campaign_index]['status'] = 'failed'
                campaigns[campaign_index]['failed_at'] = datetime.now().isoformat()
                campaigns[campaign_index]['total_attempted'] = result.get('total_attempted', 0)
                # Add failure log
                add_campaign_log(campaign['id'], {
                    'timestamp': datetime.now().isoformat(),
                    'type': 'error',
                    'message': f'Campaign failed: {result.get("message", "Unknown error")}',
                    'details': result
                })
                print(f"❌ Campaign failed: {result.get('message', 'Unknown error')}")
                add_notification(f"Campaign '{campaign['name']}' failed: {result.get('message', 'Unknown error')}", 'error', campaign['id'])
            # Save updated campaign
            write_json_file_simple(CAMPAIGNS_FILE, campaigns)
        
        # Remove from running campaigns
        if campaign['id'] in running_campaigns:
            del running_campaigns[campaign['id']]
        
    except Exception as e:
        print(f"❌ Error in universal campaign sending: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Update campaign status to failed
        try:
            campaigns = read_json_file_simple(CAMPAIGNS_FILE)
            campaign_index = next((i for i, c in enumerate(campaigns) if c['id'] == campaign['id']), None)
            
            if campaign_index is not None:
                campaigns[campaign_index]['status'] = 'failed'
                campaigns[campaign_index]['failed_at'] = datetime.now().isoformat()
                
                # Add error log
                add_campaign_log(campaign['id'], {
                    'timestamp': datetime.now().isoformat(),
                    'type': 'error',
                    'message': f'Campaign error: {str(e)}',
                    'details': {'error': str(e)}
                })
                
                write_json_file_simple(CAMPAIGNS_FILE, campaigns)
        except:
            pass
        
        # Remove from running campaigns
        if campaign['id'] in running_campaigns:
            del running_campaigns[campaign['id']]
        
        add_notification(f"Campaign '{campaign['name']}' failed with error: {str(e)}", 'error', campaign['id'])

def send_sequential_emails(account, recipients, subject, message, from_name=None, template_id=None, campaign_id=None):
    """
    Sequential email sending function - sends emails one by one with proper delays
    This ensures emails are sent sequentially, not in parallel
    """
    try:
        print(f"📧 Starting sequential email sending to {len(recipients)} recipients")
        print(f"📧 Using account: {account['name']}")
        print(f"📨 Subject: {subject}")
        print(f"👤 From: {from_name or 'Default Sender'}")
        
        # Get the correct template URL and function for this account
        template_config = get_template_url_and_function(account, template_id)
        url = template_config['url']
        function_name = template_config['function_name']
        template_number = template_config['template_number']
        
        print(f"📧 Using template {template_number}")
        print(f"🔗 Template URL: {url}")
        print(f"⚙️ Function: {function_name}")
        
        # Set from name - use provided name or default
        if from_name:
            from_display = from_name
        else:
            from_display = "Campaign Sender"
        
        # Properly escape the message content for Deluge script
        def escape_for_deluge(text):
            """Escape text for Deluge script while preserving HTML formatting"""
            # First, normalize line endings
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            # Remove all line breaks and extra spaces to create single-line HTML
            text = ' '.join(text.split())
            # Escape quotes
            text = text.replace('"', '\\"')
            return text
        
        escaped_message = escape_for_deluge(message)
        escaped_subject = escape_for_deluge(subject)
        
        # Rate limiting variables
        user_id = current_user.id if current_user else 1
        emails_sent = 0
        emails_failed = 0
        burst_count = 0
        
        # Emit campaign start event
        if campaign_id:
            try:
                socketio.emit('email_progress', {
                    'campaign_id': campaign_id,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'info',
                    'message': f'🚀 Starting sequential email campaign to {len(recipients)} recipients',
                    'email': None,
                    'subject': subject,
                    'sender': f"{from_display} <{account.get('org_id', 'test')}@zoho.com>"
                })
            except Exception as e:
                print(f"⚠️ Socket.IO start emission failed: {e}")
        
        # Send emails one by one
        for i, recipient in enumerate(recipients):
            try:
                # Check rate limit before each email
                allowed, wait_time, reason = check_rate_limit(user_id, campaign_id)
                if not allowed:
                    print(f"⏱️ Rate limit exceeded: {reason}")
                    # Wait for the required time
                    time.sleep(wait_time)
                    # Check again after waiting
                    allowed, wait_time, reason = check_rate_limit(user_id, campaign_id)
                    if not allowed:
                        print(f"❌ Still rate limited after waiting: {reason}")
                        break
                
                # Create Deluge script for single email
                script = f'''void automation.{function_name}()
{{
    // Sequential email sending - single recipient
    emailSubject = "{escaped_subject}";
    emailMessage = "{escaped_message}";
    
    // Single recipient
    destinataires = ["{recipient}"];
    
    sendmail
    [
        from: "{from_display} <" + zoho.loginuserid + ">"
        to: destinataires
        subject: emailSubject
        html: emailMessage
    ];
    
    info "Sequential email sent successfully to " + destinataires.size() + " recipient";
}}'''
                
                json_data = {'functions': [{'script': script, 'arguments': {}}]}
                
                # Use the exact same headers as the working test email function
                headers = account['headers'].copy()
                headers.update({
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
                
                print(f"📧 Sending email {i+1}/{len(recipients)} to: {recipient}")
                
                response = requests.post(url, json=json_data, cookies=account['cookies'], headers=headers, timeout=60)
                
                if response.status_code == 200:
                    print(f"✅ Email {i+1} sent successfully to {recipient}")
                    emails_sent += 1
                    burst_count += 1
                    
                    # Update rate limit counters
                    update_rate_limit_counters(user_id)
                    
                    # Log successful send
                    if campaign_id:
                        add_delivered_email(recipient, campaign_id, subject, f"{from_display} <{account.get('org_id', 'test')}@zoho.com>", {
                            'template_used': template_number,
                            'function_used': function_name,
                            'account_name': account['name'],
                            'email_number': i + 1
                        })
                    
                    # Add campaign log
                    if campaign_id:
                        log_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'status': 'success',
                            'message': f'Email {i+1}/{len(recipients)} sent successfully to {recipient}',
                            'email': recipient,
                            'subject': subject,
                            'sender': f"{from_display} <{account.get('org_id', 'test')}@zoho.com>"
                        }
                        add_campaign_log(campaign_id, log_entry)
                        
                        # Emit real-time update via Socket.IO
                        try:
                            socketio.emit('email_progress', {
                                'campaign_id': campaign_id,
                                'timestamp': log_entry['timestamp'],
                                'status': 'success',
                                'message': log_entry['message'],
                                'email': recipient,
                                'subject': subject,
                                'sender': log_entry['sender']
                            })
                        except Exception as e:
                            print(f"⚠️ Socket.IO emission failed: {e}")
                    
                else:
                    print(f"❌ Email {i+1} failed to {recipient} (Status: {response.status_code})")
                    emails_failed += 1
                    
                    # Log failed send
                    if campaign_id:
                        add_bounce_email(recipient, campaign_id, f"API Error {response.status_code}", subject, f"{from_display} <{account.get('org_id', 'test')}@zoho.com>")
                    
                    # Add campaign log
                    if campaign_id:
                        log_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'status': 'error',
                            'message': f'Email {i+1}/{len(recipients)} failed to {recipient}: HTTP {response.status_code}',
                            'email': recipient,
                            'subject': subject,
                            'sender': f"{from_display} <{account.get('org_id', 'test')}@zoho.com>"
                        }
                        add_campaign_log(campaign_id, log_entry)
                        
                        # Emit real-time update via Socket.IO
                        try:
                            socketio.emit('email_progress', {
                                'campaign_id': campaign_id,
                                'timestamp': log_entry['timestamp'],
                                'status': 'error',
                                'message': log_entry['message'],
                                'email': recipient,
                                'subject': subject,
                                'sender': log_entry['sender']
                            })
                        except Exception as e:
                            print(f"⚠️ Socket.IO emission failed: {e}")
                
                # Wait between emails (1 second)
                if i < len(recipients) - 1:  # Don't wait after the last email
                    time.sleep(1.0)
                
                # Check if we need a burst cooldown (every 10 emails)
                if burst_count >= 10:
                    print(f"⏱️ Burst limit reached ({burst_count} emails). Waiting 5 seconds...")
                    time.sleep(5.0)
                    burst_count = 0
                
            except Exception as e:
                print(f"❌ Error sending email {i+1} to {recipient}: {str(e)}")
                emails_failed += 1
                
                # Log error
                if campaign_id:
                    add_bounce_email(recipient, campaign_id, f"System Error: {str(e)}", subject, f"{from_display} <{account.get('org_id', 'test')}@zoho.com>")
                
                # Add campaign log
                if campaign_id:
                    log_entry = {
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'message': f'Email {i+1}/{len(recipients)} error to {recipient}: {str(e)}',
                        'email': recipient,
                        'subject': subject,
                        'sender': f"{from_display} <{account.get('org_id', 'test')}@zoho.com>"
                    }
                    add_campaign_log(campaign_id, log_entry)
                    
                    # Emit real-time update via Socket.IO
                    try:
                        socketio.emit('email_progress', {
                            'campaign_id': campaign_id,
                            'timestamp': log_entry['timestamp'],
                            'status': 'error',
                            'message': log_entry['message'],
                            'email': recipient,
                            'subject': subject,
                            'sender': log_entry['sender']
                        })
                    except Exception as e:
                        print(f"⚠️ Socket.IO emission failed: {e}")
        
        print(f"🏁 Sequential email sending completed!")
        print(f"✅ Successfully sent: {emails_sent}")
        print(f"❌ Failed: {emails_failed}")
        print(f"📊 Total attempted: {len(recipients)}")
        
        # Emit campaign completion event
        if campaign_id:
            try:
                socketio.emit('campaign_completed', {
                    'campaign_id': campaign_id,
                    'total_sent': emails_sent,
                    'total_attempted': len(recipients),
                    'emails_failed': emails_failed,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                print(f"⚠️ Socket.IO completion emission failed: {e}")
        
        return {
            'success': True,
            'message': f'Sequential email sending completed. Sent: {emails_sent}, Failed: {emails_failed}',
            'emails_sent': emails_sent,
            'emails_failed': emails_failed,
            'total_attempted': len(recipients),
            'template_used': template_number,
            'function_used': function_name,
            'subject_used': subject,
            'from_used': f"{from_display} <{account.get('org_id', 'test')}@zoho.com>",
            'account_name': account['name']
        }
            
    except Exception as e:
        error_msg = f"❌ Error in sequential email sending: {str(e)}"
        print(error_msg)
        
        return {
            'success': False,
            'message': f'Error in sequential email sending: {str(e)}',
            'error': str(e),
            'emails_sent': emails_sent if 'emails_sent' in locals() else 0,
            'emails_failed': emails_failed if 'emails_failed' in locals() else 0,
            'total_attempted': len(recipients)
        }

@app.route('/rate-limits')
@login_required
def rate_limits():
    """Rate limiting configuration page"""
    config = load_rate_limit_config()
    return render_template('rate_limits.html', config=config)

@app.route('/api/rate-limits', methods=['GET', 'PUT'])
@login_required
def api_rate_limits():
    """API endpoint for rate limiting configuration"""
    if request.method == 'GET':
        config = load_rate_limit_config()
        return jsonify(config)
    
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            
            # Validate the configuration
            required_fields = ['emails_per_second', 'emails_per_minute', 'emails_per_hour', 'emails_per_day', 
                             'wait_time_between_emails', 'burst_limit', 'cooldown_period']
            
            for field in required_fields:
                if field not in data:
                    return jsonify({'success': False, 'message': f'Missing required field: {field}'}), 400
                
                # Validate numeric values
                try:
                    value = float(data[field])
                    if value < 0:
                        return jsonify({'success': False, 'message': f'{field} must be positive'}), 400
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'message': f'{field} must be a number'}), 400
            
            # Additional validation
            if data['wait_time_between_emails'] < 0.1:
                return jsonify({'success': False, 'message': 'Wait time between emails must be at least 0.1 seconds'}), 400
            
            if data['burst_limit'] < 1:
                return jsonify({'success': False, 'message': 'Burst limit must be at least 1'}), 400
            
            if data['cooldown_period'] < 1:
                return jsonify({'success': False, 'message': 'Cooldown period must be at least 1 second'}), 400
            
            # Update the configuration
            config = {
                'enabled': data.get('enabled', True),
                'emails_per_second': data['emails_per_second'],
                'emails_per_minute': data['emails_per_minute'],
                'emails_per_hour': data['emails_per_hour'],
                'emails_per_day': data['emails_per_day'],
                'wait_time_between_emails': data['wait_time_between_emails'],
                'burst_limit': data['burst_limit'],
                'cooldown_period': data['cooldown_period'],
                'daily_quota': data['emails_per_day'],
                'hourly_quota': data['emails_per_hour'],
                'minute_quota': data['emails_per_minute'],
                'second_quota': data['emails_per_second']
            }
            
            save_rate_limit_config(config)
            
            # Add notification
            add_notification(f'Rate limiting configuration updated successfully', 'success')
            
            return jsonify({
                'success': True, 
                'message': 'Rate limiting configuration updated successfully',
                'config': config
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error updating configuration: {str(e)}'}), 500

@app.route('/api/rate-limits/reset', methods=['POST'])
@login_required
def reset_rate_limits():
    """Reset rate limiting configuration to defaults"""
    try:
        save_rate_limit_config(DEFAULT_RATE_LIMIT.copy())
        add_notification('Rate limiting configuration reset to defaults', 'info')
        return jsonify({
            'success': True, 
            'message': 'Rate limiting configuration reset to defaults',
            'config': DEFAULT_RATE_LIMIT.copy()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error resetting configuration: {str(e)}'}), 500

@app.route('/api/rate-limits/stats')
@login_required
def get_rate_limit_stats_api():
    """Get current rate limiting statistics"""
    try:
        user_id = current_user.id
        stats = get_rate_limit_stats(user_id)
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting stats: {str(e)}'}), 500



if __name__ == '__main__':
    # Production vs Development settings
    import os
    is_production = os.environ.get('FLASK_ENV') == 'production'
    
    if is_production:
        # Production settings
        socketio.run(app, host='127.0.0.1', port=5000, debug=False, threaded=True)
    else:
        # Development settings
        socketio.run(app, host='0.0.0.0', port=5000, debug=True) 