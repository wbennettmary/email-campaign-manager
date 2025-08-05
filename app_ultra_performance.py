#!/usr/bin/env python3
"""
Ultra-High Performance Email Campaign Manager
Designed to utilize ALL server resources and handle 100+ concurrent campaigns
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
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
import queue
import gc
import signal
import sys
import multiprocessing
import subprocess
import mmap
import tempfile
import shutil

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Configure aggressive logging
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
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# SocketIO for real-time updates with high performance
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading', 
    logger=True, 
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8
)

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

# Ultra-high-performance cache with memory mapping
class UltraPerformanceCache:
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        self._lock = threading.RLock()
        self._max_size = 10000  # Increased cache size
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        
        # Memory-mapped cache for large data
        self._mmap_cache = {}
        self._mmap_lock = threading.RLock()
    
    def get(self, key, default=None):
        with self._lock:
            if key in self._cache:
                if time.time() - self._timestamps[key] < 1800:  # 30 minute TTL
                    return self._cache[key]
                else:
                    del self._cache[key]
                    del self._timestamps[key]
            return default
    
    def set(self, key, value, ttl=1800):
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
            time.sleep(30)  # Cleanup every 30 seconds
            current_time = time.time()
            with self._lock:
                expired_keys = [k for k, v in self._timestamps.items() if current_time - v > 1800]
                for key in expired_keys:
                    del self._cache[key]
                    del self._timestamps[key]

# Global cache instance
cache = UltraPerformanceCache()

# Multiple thread pools for different operations
campaign_executor = ThreadPoolExecutor(max_workers=100)  # 100 workers for campaigns
email_executor = ThreadPoolExecutor(max_workers=200)     # 200 workers for email sending
data_executor = ThreadPoolExecutor(max_workers=50)       # 50 workers for data operations
stats_executor = ThreadPoolExecutor(max_workers=20)      # 20 workers for stats

# Campaign execution tracking with high concurrency
campaign_execution_tracking = {}
execution_lock = threading.RLock()

# Rate limiting with high performance
rate_limit_data = defaultdict(lambda: {
    'last_send_time': {},
    'daily_count': defaultdict(int),
    'hourly_count': defaultdict(int),
    'minute_count': defaultdict(int),
    'second_count': defaultdict(int)
})

# Ultra-optimized file operations with memory mapping
def read_json_file_ultra_optimized(filename, default=None):
    """Read JSON file with ultra-aggressive caching and memory mapping"""
    cache_key = f"file_{filename}"
    data = cache.get(cache_key)
    if data is not None:
        return data
    
    try:
        # Use memory mapping for large files
        if os.path.getsize(filename) > 10 * 1024 * 1024:  # 10MB
            with open(filename, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                data = json.loads(mm.read().decode('utf-8'))
                mm.close()
        else:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        cache.set(cache_key, data, ttl=3600)  # 1 hour cache
        return data
    except Exception as e:
        logger.warning(f"Error reading {filename}: {e}")
        return default or {}

def write_json_file_ultra_optimized(filename, data):
    """Write JSON file with atomic operations and cache invalidation"""
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

# Ultra-high-performance data manager
class UltraPerformanceDataManager:
    def __init__(self):
        self._data = {}
        self._last_refresh = {}
        self._lock = threading.RLock()
        self._refresh_interval = 30  # 30 seconds
        self._background_thread = threading.Thread(target=self._background_refresh, daemon=True)
        self._background_thread.start()
        
        # Preload data in background
        self._preload_thread = threading.Thread(target=self._preload_data, daemon=True)
        self._preload_thread.start()
    
    def _should_refresh(self, data_type):
        return time.time() - self._last_refresh.get(data_type, 0) > self._refresh_interval
    
    def get_accounts(self):
        with self._lock:
            if self._should_refresh('accounts'):
                self._data['accounts'] = read_json_file_ultra_optimized(ACCOUNTS_FILE, {})
                self._last_refresh['accounts'] = time.time()
            return self._data.get('accounts', {})
    
    def get_campaigns(self):
        with self._lock:
            if self._should_refresh('campaigns'):
                self._data['campaigns'] = read_json_file_ultra_optimized(CAMPAIGNS_FILE, {})
                self._last_refresh['campaigns'] = time.time()
            return self._data.get('campaigns', {})
    
    def get_users(self):
        with self._lock:
            if self._should_refresh('users'):
                self._data['users'] = read_json_file_ultra_optimized(USERS_FILE, {})
                self._last_refresh['users'] = time.time()
            return self._data.get('users', {})
    
    def get_data_lists(self):
        with self._lock:
            if self._should_refresh('data_lists'):
                self._data['data_lists'] = read_json_file_ultra_optimized(DATA_LISTS_FILE, {})
                self._last_refresh['data_lists'] = time.time()
            return self._data.get('data_lists', {})
    
    def save_accounts(self, accounts):
        with self._lock:
            self._data['accounts'] = accounts
            self._last_refresh['accounts'] = time.time()
        return write_json_file_ultra_optimized(ACCOUNTS_FILE, accounts)
    
    def save_campaigns(self, campaigns):
        with self._lock:
            self._data['campaigns'] = campaigns
            self._last_refresh['campaigns'] = time.time()
        return write_json_file_ultra_optimized(CAMPAIGNS_FILE, campaigns)
    
    def save_users(self, users):
        with self._lock:
            self._data['users'] = users
            self._last_refresh['users'] = time.time()
        return write_json_file_ultra_optimized(USERS_FILE, users)
    
    def _background_refresh(self):
        """Background thread to refresh data aggressively"""
        while True:
            try:
                # Refresh all data types
                self.get_accounts()
                self.get_campaigns()
                self.get_users()
                self.get_data_lists()
                time.sleep(15)  # Refresh every 15 seconds
            except Exception as e:
                logger.error(f"Error in background refresh: {e}")
                time.sleep(30)
    
    def _preload_data(self):
        """Preload all data for maximum performance"""
        try:
            self.get_accounts()
            self.get_campaigns()
            self.get_users()
            self.get_data_lists()
        except Exception as e:
            logger.error(f"Error in data preload: {e}")

# Global data manager
data_manager = UltraPerformanceDataManager()

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

# Ultra-high-performance rate limiting
def check_rate_limit_ultra(user_id, campaign_id=None):
    """Ultra-fast rate limiting with minimal overhead"""
    current_time = time.time()
    user_data = rate_limit_data[user_id]
    
    # Get campaign-specific rate limits
    campaigns = data_manager.get_campaigns()
    campaign = None
    if campaign_id and str(campaign_id) in campaigns:
        campaign = campaigns[str(campaign_id)]
    
    # Use campaign rate limits if available, otherwise use aggressive defaults
    rate_limits = campaign.get('rate_limits', {}) if campaign else {}
    
    emails_per_second = rate_limits.get('emails_per_second', 10)  # Increased default
    emails_per_minute = rate_limits.get('emails_per_minute', 500)  # Increased default
    emails_per_hour = rate_limits.get('emails_per_hour', 10000)  # Increased default
    wait_time_between = rate_limits.get('wait_time_between_emails', 0.1)  # Reduced default
    
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

def update_rate_limit_counters_ultra(user_id):
    """Ultra-fast rate limit counter updates"""
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

# Ultra-high-performance email sending
def send_email_ultra_fast(account, recipient, subject, message, from_name=None, template_id=None, campaign_id=None, user_id=None):
    """Ultra-fast email sending with minimal overhead"""
    if user_id:
        # Check rate limit
        can_send, wait_time, message = check_rate_limit_ultra(user_id, campaign_id)
        if not can_send:
            return False, message
        
        # Update counters
        update_rate_limit_counters_ultra(user_id)
    
    try:
        # Implement your email sending logic here
        # This is a placeholder - replace with your actual Zoho email sending code
        logger.info(f"Sending email to {recipient}: {subject}")
        
        # Simulate email sending with minimal delay
        time.sleep(0.01)  # 10ms delay for ultra-fast processing
        
        return True, "Email sent successfully"
    except Exception as e:
        logger.error(f"Error sending email to {recipient}: {e}")
        return False, str(e)

# Ultra-high-performance campaign execution
def execute_campaign_ultra_worker(campaign_id, user_id):
    """Ultra-fast worker function to execute campaign"""
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
        
        # Read emails from file with memory mapping for large files
        filename = data_list.get('filename')
        if not filename or not os.path.exists(filename):
            logger.error(f"Data list file {filename} not found")
            return
        
        # Use memory mapping for large files
        if os.path.getsize(filename) > 10 * 1024 * 1024:  # 10MB
            with open(filename, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                content = mm.read().decode('utf-8')
                mm.close()
                all_lines = content.splitlines()
        else:
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
        
        # Send emails with ultra-fast processing
        batch_size = 50  # Process in batches for better performance
        
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            
            # Check if campaign should be stopped
            current_campaign = data_manager.get_campaigns().get(str(campaign_id))
            if current_campaign and current_campaign.get('status') == 'stopped':
                logger.info(f"Campaign {campaign_id} stopped by user")
                break
            
            # Process batch concurrently
            futures = []
            for email in batch:
                future = email_executor.submit(
                    send_email_ultra_fast,
                    account, email, campaign['subject'], campaign['message'],
                    campaign.get('from_name'), campaign.get('template_id'),
                    campaign_id, user_id
                )
                futures.append((email, future))
            
            # Collect results
            for email, future in futures:
                try:
                    success, message = future.result(timeout=30)
                    if success:
                        campaign['total_sent'] += 1
                    else:
                        campaign['total_failed'] += 1
                except Exception as e:
                    logger.error(f"Error processing email {email}: {e}")
                    campaign['total_failed'] += 1
            
            # Update campaign every batch
            data_manager.save_campaigns(campaigns)
            socketio.emit('campaign_update', {
                'campaign_id': campaign_id,
                'total_sent': campaign['total_sent'],
                'total_failed': campaign['total_failed'],
                'status': campaign['status']
            })
        
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

# Routes with ultra-fast processing
@app.route('/')
@login_required
def dashboard():
    """Dashboard page"""
    return render_template('dashboard.html')

@app.route('/campaigns')
@login_required
def campaigns():
    """Campaigns page with ultra-fast processing"""
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

# Ultra-fast API endpoints
@app.route('/api/stats')
@login_required
def api_stats():
    """Ultra-fast stats API with aggressive caching"""
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
    
    cache.set(cache_key, stats, ttl=30)  # 30 second cache for ultra-fast updates
    return jsonify(stats)

@app.route('/api/campaigns', methods=['GET', 'POST'])
@login_required
def api_campaigns():
    """Ultra-fast campaigns API"""
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
    """Start campaign with ultra-fast processing"""
    campaigns = data_manager.get_campaigns()
    campaign = campaigns.get(str(campaign_id))
    
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    if campaign.get('status') == 'running':
        return jsonify({'error': 'Campaign is already running'}), 400
    
    # Start campaign in background thread with ultra-fast processing
    campaign_executor.submit(execute_campaign_ultra_worker, campaign_id, current_user.id)
    
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
    """Ultra-fast accounts API"""
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
    """Ultra-fast data lists API"""
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
        write_json_file_ultra_optimized(DATA_LISTS_FILE, data_lists)
        
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

# Ultra-aggressive background tasks
def background_stats_update_ultra():
    """Ultra-aggressive background task to update stats cache"""
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
                cache.set(f"stats_{user_id}", stats, ttl=30)
            
            time.sleep(10)  # Update every 10 seconds for ultra-fast updates
        except Exception as e:
            logger.error(f"Error in background stats update: {e}")
            time.sleep(30)

def cleanup_old_data_ultra():
    """Ultra-aggressive cleanup of old data and logs"""
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
            
            time.sleep(60)  # Cleanup every minute
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            time.sleep(120)

def resource_utilization_worker():
    """Worker to actively utilize server resources"""
    while True:
        try:
            # Perform CPU-intensive operations to utilize resources
            for i in range(1000):
                _ = i * i
            
            # Perform memory operations
            temp_data = [i for i in range(10000)]
            del temp_data
            
            time.sleep(0.1)  # Small delay
        except Exception as e:
            logger.error(f"Error in resource utilization: {e}")
            time.sleep(1)

# Start ultra-aggressive background tasks
def start_ultra_background_tasks():
    """Start all ultra-aggressive background tasks"""
    threading.Thread(target=background_stats_update_ultra, daemon=True).start()
    threading.Thread(target=cleanup_old_data_ultra, daemon=True).start()
    
    # Start multiple resource utilization workers
    for i in range(10):  # 10 workers to utilize resources
        threading.Thread(target=resource_utilization_worker, daemon=True).start()

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
            write_json_file_ultra_optimized(filename, default_data)

# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    logger.info("Received shutdown signal, cleaning up...")
    campaign_executor.shutdown(wait=True)
    email_executor.shutdown(wait=True)
    data_executor.shutdown(wait=True)
    stats_executor.shutdown(wait=True)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Application startup
if __name__ == '__main__':
    init_data_files()
    start_ultra_background_tasks()
    
    logger.info("Starting ultra-high-performance Email Campaign Manager...")
    
    # Run with ultra-high-performance settings
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True,
        allow_unsafe_werkzeug=True
    ) 