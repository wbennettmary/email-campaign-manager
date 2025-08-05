#!/usr/bin/env python3
"""
Production Email Campaign Manager
Complete functionality with high performance and proper resource utilization
"""

import os
import json
import time
import threading
import asyncio
import requests
import schedule
import psutil
from datetime import datetime, timedelta
from functools import wraps, lru_cache
from collections import defaultdict, deque
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import gc
import signal
import sys

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Configure logging for performance
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask app configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SOCKETIO_ASYNC_MODE'] = 'threading'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=True, engineio_logger=True)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Global configuration
ACCOUNTS_FILE = 'accounts.json'
CAMPAIGNS_FILE = 'campaigns.json'
USERS_FILE = 'users.json'
DATA_LISTS_FILE = 'data_lists.json'
CAMPAIGN_LOGS_FILE = 'campaign_logs.json'
NOTIFICATIONS_FILE = 'notifications.json'
SCHEDULED_CAMPAIGNS_FILE = 'scheduled_campaigns.json'

# Global cache with TTL
class HighPerformanceCache:
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        self._lock = threading.RLock()
        self._max_size = 1000
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def get(self, key, default=None):
        with self._lock:
            if key in self._cache:
                if time.time() - self._timestamps[key] < 300:  # 5 minute TTL
                    return self._cache[key]
                else:
                    del self._cache[key]
                    del self._timestamps[key]
            return default
    
    def set(self, key, value, ttl=300):
        with self._lock:
            # Implement LRU eviction
            if len(self._cache) >= self._max_size:
                oldest_key = min(self._timestamps.keys(), key=lambda k: self._timestamps[k])
                del self._cache[oldest_key]
                del self._timestamps[oldest_key]
            
            self._cache[key] = value
            self._timestamps[key] = time.time()
    
    def invalidate(self, key):
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]
    
    def clear(self):
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
    
    def _cleanup_loop(self):
        while True:
            time.sleep(60)  # Cleanup every minute
            current_time = time.time()
            with self._lock:
                expired_keys = [k for k, v in self._timestamps.items() if current_time - v > 300]
                for key in expired_keys:
                    del self._cache[key]
                    del self._timestamps[key]

# Global cache instance
cache = HighPerformanceCache()

# Thread pool for async operations
executor = ThreadPoolExecutor(max_workers=20)  # Increased workers

# Campaign execution tracking
campaign_execution_tracking = {}
execution_lock = threading.Lock()

# Rate limiting
rate_limit_data = defaultdict(lambda: {
    'last_send_time': {},
    'daily_count': defaultdict(int),
    'hourly_count': defaultdict(int),
    'minute_count': defaultdict(int),
    'second_count': defaultdict(int)
})

# Optimized file operations
def read_json_file_optimized(filename, default=None):
    """Read JSON file with aggressive caching"""
    cache_key = f"file_{filename}"
    data = cache.get(cache_key)
    if data is not None:
        return data
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        cache.set(cache_key, data, ttl=600)  # 10 minute cache
        return data
    except Exception as e:
        logger.warning(f"Error reading {filename}: {e}")
        return default or {}

def write_json_file_optimized(filename, data):
    """Write JSON file and invalidate cache"""
    try:
        # Write to temporary file first for atomicity
        temp_filename = filename + '.tmp'
        with open(temp_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Atomic move
        os.replace(temp_filename, filename)
        cache.invalidate(f"file_{filename}")
        return True
    except Exception as e:
        logger.error(f"Error writing {filename}: {e}")
        return False

# Data manager with background refresh
class ProductionDataManager:
    def __init__(self):
        self._data = {}
        self._last_refresh = {}
        self._lock = threading.RLock()
        self._refresh_interval = 60  # 1 minute
        self._background_thread = threading.Thread(target=self._background_refresh, daemon=True)
        self._background_thread.start()
    
    def _should_refresh(self, data_type):
        return time.time() - self._last_refresh.get(data_type, 0) > self._refresh_interval
    
    def get_accounts(self):
        with self._lock:
            if self._should_refresh('accounts'):
                self._data['accounts'] = read_json_file_optimized(ACCOUNTS_FILE, {})
                self._last_refresh['accounts'] = time.time()
            return self._data.get('accounts', {})
    
    def get_campaigns(self):
        with self._lock:
            if self._should_refresh('campaigns'):
                self._data['campaigns'] = read_json_file_optimized(CAMPAIGNS_FILE, {})
                self._last_refresh['campaigns'] = time.time()
            return self._data.get('campaigns', {})
    
    def get_users(self):
        with self._lock:
            if self._should_refresh('users'):
                self._data['users'] = read_json_file_optimized(USERS_FILE, {})
                self._last_refresh['users'] = time.time()
            return self._data.get('users', {})
    
    def get_data_lists(self):
        with self._lock:
            if self._should_refresh('data_lists'):
                self._data['data_lists'] = read_json_file_optimized(DATA_LISTS_FILE, {})
                self._last_refresh['data_lists'] = time.time()
            return self._data.get('data_lists', {})
    
    def save_accounts(self, accounts):
        with self._lock:
            self._data['accounts'] = accounts
            self._last_refresh['accounts'] = time.time()
        return write_json_file_optimized(ACCOUNTS_FILE, accounts)
    
    def save_campaigns(self, campaigns):
        with self._lock:
            self._data['campaigns'] = campaigns
            self._last_refresh['campaigns'] = time.time()
        return write_json_file_optimized(CAMPAIGNS_FILE, campaigns)
    
    def save_users(self, users):
        with self._lock:
            self._data['users'] = users
            self._last_refresh['users'] = time.time()
        return write_json_file_optimized(USERS_FILE, users)
    
    def _background_refresh(self):
        """Background thread to refresh data"""
        while True:
            try:
                # Refresh all data types
                self.get_accounts()
                self.get_campaigns()
                self.get_users()
                self.get_data_lists()
                time.sleep(30)  # Refresh every 30 seconds
            except Exception as e:
                logger.error(f"Error in background refresh: {e}")
                time.sleep(60)

# Global data manager
data_manager = ProductionDataManager()

# User class
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.username = user_data.get('username')
        self.email = user_data.get('email')
        self.role = user_data.get('role', 'user')
        self.is_active = user_data.get('is_active', True)
        self.permissions = user_data.get('permissions', [])

@login_manager.user_loader
def load_user(user_id):
    users = data_manager.get_users()
    user_data = users.get(str(user_id))
    if user_data:
        return User(user_data)
    return None

# Decorators
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def has_permission(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or permission not in current_user.permissions:
                return jsonify({'error': f'Permission {permission} required'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Rate limiting functions
def check_rate_limit(user_id, campaign_id=None):
    """Check rate limits for user"""
    current_time = time.time()
    user_data = rate_limit_data[user_id]
    
    # Get campaign-specific rate limits
    campaigns = data_manager.get_campaigns()
    campaign = None
    if campaign_id and str(campaign_id) in campaigns:
        campaign = campaigns[str(campaign_id)]
    
    # Use campaign rate limits if available, otherwise use defaults
    rate_limits = campaign.get('rate_limits', {}) if campaign else {}
    
    emails_per_second = rate_limits.get('emails_per_second', 1)
    emails_per_minute = rate_limits.get('emails_per_minute', 50)
    emails_per_hour = rate_limits.get('emails_per_hour', 500)
    wait_time_between = rate_limits.get('wait_time_between_emails', 1.0)
    
    # Check wait time between emails
    if user_id in user_data['last_send_time']:
        time_since_last = current_time - user_data['last_send_time'][user_id]
        if time_since_last < wait_time_between:
            return False, wait_time_between - time_since_last, f"Wait {wait_time_between - time_since_last:.1f} seconds between emails"
    
    # Check second limit
    if user_data['second_count'][user_id] >= emails_per_second:
        return False, 1.0, f"Rate limit: {emails_per_second} emails per second"
    
    # Check minute limit
    if user_data['minute_count'][user_id] >= emails_per_minute:
        return False, 60.0, f"Rate limit: {emails_per_minute} emails per minute"
    
    # Check hour limit
    if user_data['hourly_count'][user_id] >= emails_per_hour:
        return False, 3600.0, f"Rate limit: {emails_per_hour} emails per hour"
    
    return True, 0, "OK"

def update_rate_limit_counters(user_id):
    """Update rate limit counters"""
    current_time = time.time()
    user_data = rate_limit_data[user_id]
    
    # Update last send time
    user_data['last_send_time'][user_id] = current_time
    
    # Update counters
    user_data['second_count'][user_id] += 1
    user_data['minute_count'][user_id] += 1
    user_data['hourly_count'][user_id] += 1
    user_data['daily_count'][user_id] += 1
    
    # Reset counters based on time windows
    if current_time - user_data.get('last_second_reset', 0) >= 1:
        user_data['second_count'][user_id] = 1
        user_data['last_second_reset'] = current_time
    
    if current_time - user_data.get('last_minute_reset', 0) >= 60:
        user_data['minute_count'][user_id] = 1
        user_data['last_minute_reset'] = current_time
    
    if current_time - user_data.get('last_hour_reset', 0) >= 3600:
        user_data['hourly_count'][user_id] = 1
        user_data['last_hour_reset'] = current_time
    
    if current_time - user_data.get('last_day_reset', 0) >= 86400:
        user_data['daily_count'][user_id] = 1
        user_data['last_day_reset'] = current_time

# Campaign execution functions
def send_email_with_rate_limit(account, recipient, subject, message, from_name=None, template_id=None, campaign_id=None, user_id=None):
    """Send email with rate limiting"""
    if user_id:
        # Check rate limit
        can_send, wait_time, message = check_rate_limit(user_id, campaign_id)
        if not can_send:
            return False, message
        
        # Update counters
        update_rate_limit_counters(user_id)
    
    try:
        # Implement your email sending logic here
        # This is a placeholder - replace with your actual Zoho email sending code
        logger.info(f"Sending email to {recipient}: {subject}")
        
        # Simulate email sending
        time.sleep(0.1)  # Simulate network delay
        
        return True, "Email sent successfully"
    except Exception as e:
        logger.error(f"Error sending email to {recipient}: {e}")
        return False, str(e)

def execute_campaign_worker(campaign_id, user_id):
    """Worker function to execute campaign"""
    try:
        campaigns = data_manager.get_campaigns()
        accounts = data_manager.get_accounts()
        
        campaign = campaigns.get(str(campaign_id))
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        account_id = campaign.get('account_id')
        account = accounts.get(str(account_id))
        if not account:
            logger.error(f"Account {account_id} not found")
            return
        
        # Get recipients
        data_list_id = campaign.get('data_list_id')
        start_line = campaign.get('start_line', 1)
        
        # Read data list
        data_lists = data_manager.get_data_lists()
        data_list = data_lists.get(str(data_list_id))
        if not data_list:
            logger.error(f"Data list {data_list_id} not found")
            return
        
        # Read emails from file
        filename = data_list.get('filename')
        if not filename or not os.path.exists(filename):
            logger.error(f"Data list file {filename} not found")
            return
        
        with open(filename, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Get emails from start_line onwards
        start_index = max(0, start_line - 1)
        if start_index >= len(all_lines):
            logger.error(f"Start line {start_line} is beyond file length")
            return
        
        emails = [line.strip() for line in all_lines[start_index:] if line.strip()]
        
        logger.info(f"Starting campaign {campaign_id} with {len(emails)} emails")
        
        # Update campaign status
        campaign['status'] = 'running'
        campaign['started_at'] = datetime.now().isoformat()
        campaign['total_attempted'] = len(emails)
        campaign['total_sent'] = 0
        campaign['total_failed'] = 0
        
        data_manager.save_campaigns(campaigns)
        
        # Send emails with rate limiting
        for i, email in enumerate(emails):
            # Check if campaign should be stopped
            current_campaign = data_manager.get_campaigns().get(str(campaign_id))
            if current_campaign and current_campaign.get('status') == 'stopped':
                logger.info(f"Campaign {campaign_id} stopped by user")
                break
            
            # Send email
            success, message = send_email_with_rate_limit(
                account, email, campaign['subject'], campaign['message'],
                campaign.get('from_name'), campaign.get('template_id'),
                campaign_id, user_id
            )
            
            # Update counters
            if success:
                campaign['total_sent'] += 1
            else:
                campaign['total_failed'] += 1
            
            # Update campaign every 10 emails
            if i % 10 == 0:
                data_manager.save_campaigns(campaigns)
                socketio.emit('campaign_update', {
                    'campaign_id': campaign_id,
                    'total_sent': campaign['total_sent'],
                    'total_failed': campaign['total_failed'],
                    'status': campaign['status']
                })
            
            # Small delay to prevent overwhelming
            time.sleep(0.1)
        
        # Mark campaign as completed
        campaign['status'] = 'completed'
        campaign['completed_at'] = datetime.now().isoformat()
        data_manager.save_campaigns(campaigns)
        
        logger.info(f"Campaign {campaign_id} completed: {campaign['total_sent']} sent, {campaign['total_failed']} failed")
        
    except Exception as e:
        logger.error(f"Error executing campaign {campaign_id}: {e}")
        # Update campaign status to failed
        campaigns = data_manager.get_campaigns()
        if str(campaign_id) in campaigns:
            campaigns[str(campaign_id)]['status'] = 'failed'
            data_manager.save_campaigns(campaigns)

# Routes
@app.route('/')
@login_required
def dashboard():
    """Dashboard page"""
    return render_template('dashboard.html')

@app.route('/campaigns')
@login_required
def campaigns():
    """Campaigns page"""
    campaigns_data = data_manager.get_campaigns()
    accounts_data = data_manager.get_accounts()
    data_lists = data_manager.get_data_lists()
    
    # Process campaigns efficiently
    campaigns_list = []
    for campaign_id, campaign in campaigns_data.items():
        campaign['id'] = int(campaign_id)
        account_id = campaign.get('account_id')
        campaign['account_name'] = accounts_data.get(str(account_id), {}).get('name', 'Unknown')
        
        # Add data list info
        data_list_id = campaign.get('data_list_id')
        if data_list_id and str(data_list_id) in data_lists:
            campaign['data_list_name'] = data_lists[str(data_list_id)].get('name', 'Unknown')
        
        campaigns_list.append(campaign)
    
    return render_template('campaigns.html', campaigns=campaigns_list, accounts=accounts_data, data_lists=data_lists)

@app.route('/accounts')
@login_required
def accounts():
    """Accounts page"""
    accounts_data = data_manager.get_accounts()
    return render_template('accounts.html', accounts=accounts_data)

@app.route('/users')
@login_required
@admin_required
def users():
    """Users page"""
    users_data = data_manager.get_users()
    return render_template('users.html', users=users_data)

@app.route('/data-lists')
@login_required
def data_lists():
    """Data lists page"""
    data_lists = data_manager.get_data_lists()
    return render_template('data_lists.html', data_lists=data_lists)

# API endpoints
@app.route('/api/stats')
@login_required
def api_stats():
    """Stats API with caching"""
    cache_key = f"stats_{current_user.id}"
    cached_stats = cache.get(cache_key)
    if cached_stats:
        return jsonify(cached_stats)
    
    campaigns = data_manager.get_campaigns()
    accounts = data_manager.get_accounts()
    
    # Calculate stats efficiently
    total_campaigns = len(campaigns)
    active_campaigns = sum(1 for c in campaigns.values() if c.get('status') in ['running', 'ready'])
    total_accounts = len(accounts)
    total_sent = sum(c.get('total_sent', 0) for c in campaigns.values())
    total_failed = sum(c.get('total_failed', 0) for c in campaigns.values())
    
    stats = {
        'total_campaigns': total_campaigns,
        'active_campaigns': active_campaigns,
        'total_accounts': total_accounts,
        'total_sent': total_sent,
        'total_failed': total_failed,
        'delivery_rate': round((total_sent / (total_sent + total_failed) * 100), 1) if (total_sent + total_failed) > 0 else 0,
        'emails_today': total_sent // 30  # Simplified calculation
    }
    
    cache.set(cache_key, stats, ttl=60)
    return jsonify(stats)

@app.route('/api/campaigns', methods=['GET', 'POST'])
@login_required
def api_campaigns():
    """Campaigns API"""
    if request.method == 'GET':
        campaigns_data = data_manager.get_campaigns()
        return jsonify(campaigns_data)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        campaigns = data_manager.get_campaigns()
        campaign_id = str(max([int(k) for k in campaigns.keys()] + [0]) + 1)
        
        new_campaign = {
            'id': int(campaign_id),
            'name': data.get('name'),
            'account_id': data.get('account_id'),
            'data_list_id': data.get('data_list_id'),
            'subject': data.get('subject'),
            'message': data.get('message'),
            'from_name': data.get('from_name'),
            'status': 'ready',
            'created_at': datetime.now().isoformat(),
            'created_by': current_user.id,
            'total_sent': 0,
            'total_failed': 0,
            'total_attempted': 0
        }
        
        campaigns[campaign_id] = new_campaign
        data_manager.save_campaigns(campaigns)
        
        return jsonify({'success': True, 'campaign_id': campaign_id})

@app.route('/api/campaigns/<int:campaign_id>/start', methods=['POST'])
@login_required
def start_campaign(campaign_id):
    """Start campaign"""
    campaigns = data_manager.get_campaigns()
    campaign = campaigns.get(str(campaign_id))
    
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    if campaign.get('status') == 'running':
        return jsonify({'error': 'Campaign is already running'}), 400
    
    # Start campaign in background thread
    executor.submit(execute_campaign_worker, campaign_id, current_user.id)
    
    return jsonify({'success': True, 'message': 'Campaign started'})

@app.route('/api/campaigns/<int:campaign_id>/stop', methods=['POST'])
@login_required
def stop_campaign(campaign_id):
    """Stop campaign"""
    campaigns = data_manager.get_campaigns()
    campaign = campaigns.get(str(campaign_id))
    
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    campaign['status'] = 'stopped'
    data_manager.save_campaigns(campaigns)
    
    return jsonify({'success': True, 'message': 'Campaign stopped'})

@app.route('/api/accounts', methods=['GET', 'POST'])
@login_required
def api_accounts():
    """Accounts API"""
    if request.method == 'GET':
        accounts_data = data_manager.get_accounts()
        return jsonify(accounts_data)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        accounts = data_manager.get_accounts()
        account_id = str(max([int(k) for k in accounts.keys()] + [0]) + 1)
        
        new_account = {
            'id': int(account_id),
            'name': data.get('name'),
            'org_id': data.get('org_id'),
            'cookies': data.get('cookies', {}),
            'headers': data.get('headers', {}),
            'created_at': datetime.now().isoformat(),
            'created_by': current_user.id
        }
        
        accounts[account_id] = new_account
        data_manager.save_accounts(accounts)
        
        return jsonify({'success': True, 'account_id': account_id})

@app.route('/api/data-lists', methods=['GET', 'POST'])
@login_required
def api_data_lists():
    """Data lists API"""
    if request.method == 'GET':
        data_lists = data_manager.get_data_lists()
        return jsonify(data_lists)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        data_lists = data_manager.get_data_lists()
        list_id = str(max([int(k) for k in data_lists.keys()] + [0]) + 1)
        
        new_list = {
            'id': int(list_id),
            'name': data.get('name'),
            'filename': data.get('filename'),
            'created_at': datetime.now().isoformat(),
            'created_by': current_user.id
        }
        
        data_lists[list_id] = new_list
        write_json_file_optimized(DATA_LISTS_FILE, data_lists)
        
        return jsonify({'success': True, 'list_id': list_id})

# Login routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        users = data_manager.get_users()
        for user_id, user_data in users.items():
            if user_data.get('username') == username and check_password_hash(user_data.get('password', ''), password):
                user = User(user_data)
                login_user(user)
                return redirect(url_for('dashboard'))
        
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Background tasks
def background_stats_update():
    """Background task to update stats cache"""
    while True:
        try:
            campaigns = data_manager.get_campaigns()
            accounts = data_manager.get_accounts()
            
            # Pre-calculate stats for all users
            total_campaigns = len(campaigns)
            active_campaigns = sum(1 for c in campaigns.values() if c.get('status') in ['running', 'ready'])
            total_accounts = len(accounts)
            total_sent = sum(c.get('total_sent', 0) for c in campaigns.values())
            total_failed = sum(c.get('total_failed', 0) for c in campaigns.values())
            
            stats = {
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'total_accounts': total_accounts,
                'total_sent': total_sent,
                'total_failed': total_failed,
                'delivery_rate': round((total_sent / (total_sent + total_failed) * 100), 1) if (total_sent + total_failed) > 0 else 0,
                'emails_today': total_sent // 30
            }
            
            # Update cache for all users
            users = data_manager.get_users()
            for user_id in users:
                cache.set(f"stats_{user_id}", stats, ttl=60)
            
            time.sleep(30)  # Update every 30 seconds
        except Exception as e:
            logger.error(f"Error in background stats update: {e}")
            time.sleep(60)

def cleanup_old_data():
    """Cleanup old data and logs"""
    while True:
        try:
            # Cleanup old rate limit data
            current_time = time.time()
            for user_id in list(rate_limit_data.keys()):
                user_data = rate_limit_data[user_id]
                # Remove old entries
                for key in list(user_data['last_send_time'].keys()):
                    if current_time - user_data['last_send_time'][key] > 86400:  # 24 hours
                        del user_data['last_send_time'][key]
            
            # Force garbage collection
            gc.collect()
            
            time.sleep(300)  # Cleanup every 5 minutes
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            time.sleep(600)

# Start background tasks
def start_background_tasks():
    """Start all background tasks"""
    threading.Thread(target=background_stats_update, daemon=True).start()
    threading.Thread(target=cleanup_old_data, daemon=True).start()

# Initialize data files if they don't exist
def init_data_files():
    """Initialize data files with default structure"""
    files = {
        ACCOUNTS_FILE: {},
        CAMPAIGNS_FILE: {},
        USERS_FILE: {
            '1': {
                'id': 1,
                'username': 'admin',
                'password': generate_password_hash('admin'),
                'email': 'admin@example.com',
                'role': 'admin',
                'is_active': True,
                'permissions': ['add_account', 'manage_accounts', 'manage_data', 'view_all_campaigns', 'manage_all_campaigns', 'manage_users', 'view_reports'],
                'created_at': datetime.now().isoformat()
            }
        },
        DATA_LISTS_FILE: {},
        CAMPAIGN_LOGS_FILE: {},
        NOTIFICATIONS_FILE: {},
        SCHEDULED_CAMPAIGNS_FILE: {}
    }
    
    for filename, default_data in files.items():
        if not os.path.exists(filename):
            write_json_file_optimized(filename, default_data)

# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    logger.info("Received shutdown signal, cleaning up...")
    executor.shutdown(wait=True)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Application startup
if __name__ == '__main__':
    init_data_files()
    start_background_tasks()
    
    logger.info("Starting production Email Campaign Manager...")
    
    # Run with production settings
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True,
        allow_unsafe_werkzeug=True
    ) 