#!/usr/bin/env python3
"""
Fixed Email Campaign Manager - Addresses Real Performance Issues
"""

import os
import json
import time
import threading
from datetime import datetime
from functools import wraps
import logging
from concurrent.futures import ThreadPoolExecutor
import queue

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SOCKETIO_ASYNC_MODE'] = 'threading'

# SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# File paths
ACCOUNTS_FILE = 'accounts.json'
CAMPAIGNS_FILE = 'campaigns.json'
USERS_FILE = 'users.json'
DATA_LISTS_FILE = 'data_lists.json'

# Simple in-memory cache
_cache = {}
_cache_timestamps = {}

def get_cached_data(key, ttl=60):
    """Simple cache with TTL"""
    if key in _cache:
        if time.time() - _cache_timestamps[key] < ttl:
            return _cache[key]
        else:
            del _cache[key]
            del _cache_timestamps[key]
    return None

def set_cached_data(key, data, ttl=60):
    """Set cache data"""
    _cache[key] = data
    _cache_timestamps[key] = time.time()

def read_json_file(filename, default=None):
    """Read JSON file with simple error handling"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default or {}
    except Exception as e:
        logger.error(f"Error reading {filename}: {e}")
        return default or {}

def write_json_file(filename, data):
    """Write JSON file atomically"""
    try:
        temp_filename = filename + '.tmp'
        with open(temp_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_filename, filename)
        return True
    except Exception as e:
        logger.error(f"Error writing {filename}: {e}")
        return False

# Campaign execution queue
campaign_queue = queue.Queue()
campaign_workers = ThreadPoolExecutor(max_workers=10)
active_campaigns = {}

def campaign_worker():
    """Simple campaign worker"""
    while True:
        try:
            campaign_id, user_id = campaign_queue.get()
            if campaign_id is None:  # Shutdown signal
                break
            
            execute_campaign_simple(campaign_id, user_id)
            campaign_queue.task_done()
        except Exception as e:
            logger.error(f"Campaign worker error: {e}")

# Start campaign workers
for _ in range(10):
    campaign_workers.submit(campaign_worker)

def execute_campaign_simple(campaign_id, user_id):
    """Simple campaign execution without complex logic"""
    try:
        campaigns = read_json_file(CAMPAIGNS_FILE)
        accounts = read_json_file(ACCOUNTS_FILE)
        data_lists = read_json_file(DATA_LISTS_FILE)
        
        campaign = campaigns.get(str(campaign_id))
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        # Update status
        campaign['status'] = 'running'
        campaign['started_at'] = datetime.now().isoformat()
        write_json_file(CAMPAIGNS_FILE, campaigns)
        
        # Get account and data list
        account_id = campaign.get('account_id')
        account = accounts.get(str(account_id))
        data_list_id = campaign.get('data_list_id')
        data_list = data_lists.get(str(data_list_id))
        
        if not account or not data_list:
            logger.error(f"Account or data list not found for campaign {campaign_id}")
            campaign['status'] = 'failed'
            write_json_file(CAMPAIGNS_FILE, campaigns)
            return
        
        # Read emails from file
        filename = data_list.get('filename')
        if not filename or not os.path.exists(filename):
            logger.error(f"Data file {filename} not found")
            campaign['status'] = 'failed'
            write_json_file(CAMPAIGNS_FILE, campaigns)
            return
        
        # Read emails efficiently
        with open(filename, 'r', encoding='utf-8') as f:
            emails = [line.strip() for line in f if line.strip()]
        
        campaign['total_attempted'] = len(emails)
        campaign['total_sent'] = 0
        campaign['total_failed'] = 0
        
        # Send emails in batches
        batch_size = 50
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            
            # Check if campaign should stop
            current_campaign = read_json_file(CAMPAIGNS_FILE).get(str(campaign_id))
            if current_campaign and current_campaign.get('status') == 'stopped':
                logger.info(f"Campaign {campaign_id} stopped by user")
                break
            
            # Send batch
            for email in batch:
                try:
                    # Simple email sending (replace with your actual logic)
                    success = send_email_simple(account, email, campaign['subject'], campaign['message'])
                    if success:
                        campaign['total_sent'] += 1
                    else:
                        campaign['total_failed'] += 1
                except Exception as e:
                    logger.error(f"Error sending email to {email}: {e}")
                    campaign['total_failed'] += 1
            
            # Update campaign every batch
            write_json_file(CAMPAIGNS_FILE, campaigns)
            
            # Emit update
            socketio.emit('campaign_update', {
                'campaign_id': campaign_id,
                'total_sent': campaign['total_sent'],
                'total_failed': campaign['total_failed'],
                'status': campaign['status']
            })
            
            # Small delay to prevent overwhelming
            time.sleep(0.1)
        
        # Mark as completed
        campaign['status'] = 'completed'
        campaign['completed_at'] = datetime.now().isoformat()
        write_json_file(CAMPAIGNS_FILE, campaigns)
        
        logger.info(f"Campaign {campaign_id} completed: {campaign['total_sent']} sent, {campaign['total_failed']} failed")
        
    except Exception as e:
        logger.error(f"Error executing campaign {campaign_id}: {e}")
        campaigns = read_json_file(CAMPAIGNS_FILE)
        if str(campaign_id) in campaigns:
            campaigns[str(campaign_id)]['status'] = 'failed'
            write_json_file(CAMPAIGNS_FILE, campaigns)

def send_email_simple(account, recipient, subject, message):
    """Simple email sending function"""
    try:
        # Replace this with your actual Zoho email sending code
        logger.info(f"Sending email to {recipient}: {subject}")
        time.sleep(0.01)  # Simulate email sending
        return True
    except Exception as e:
        logger.error(f"Error sending email to {recipient}: {e}")
        return False

# User class
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.username = user_data.get('username')
        self.email = user_data.get('email')
        self.role = user_data.get('role', 'user')

@login_manager.user_loader
def load_user(user_id):
    users = read_json_file(USERS_FILE)
    user_data = users.get(str(user_id))
    if user_data:
        return User(user_data)
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/campaigns')
@login_required
def campaigns():
    campaigns_data = read_json_file(CAMPAIGNS_FILE)
    accounts_data = read_json_file(ACCOUNTS_FILE)
    data_lists = read_json_file(DATA_LISTS_FILE)
    
    campaigns_list = []
    for campaign_id, campaign in campaigns_data.items():
        campaign['id'] = int(campaign_id)
        account_id = campaign.get('account_id')
        campaign['account_name'] = accounts_data.get(str(account_id), {}).get('name', 'Unknown')
        
        data_list_id = campaign.get('data_list_id')
        if data_list_id and str(data_list_id) in data_lists:
            campaign['data_list_name'] = data_lists[str(data_list_id)].get('name', 'Unknown')
        
        campaigns_list.append(campaign)
    
    return render_template('campaigns.html', campaigns=campaigns_list, accounts=accounts_data, data_lists=data_lists)

@app.route('/accounts')
@login_required
def accounts():
    accounts_data = read_json_file(ACCOUNTS_FILE)
    return render_template('accounts.html', accounts=accounts_data)

@app.route('/users')
@login_required
@admin_required
def users():
    users_data = read_json_file(USERS_FILE)
    return render_template('users.html', users=users_data)

@app.route('/data-lists')
@login_required
def data_lists():
    data_lists = read_json_file(DATA_LISTS_FILE)
    return render_template('data_lists.html', data_lists=data_lists)

# API endpoints
@app.route('/api/stats')
@login_required
def api_stats():
    cached_stats = get_cached_data('stats', ttl=30)
    if cached_stats:
        return jsonify(cached_stats)
    
    campaigns = read_json_file(CAMPAIGNS_FILE)
    accounts = read_json_file(ACCOUNTS_FILE)
    
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
    
    set_cached_data('stats', stats, ttl=30)
    return jsonify(stats)

@app.route('/api/campaigns', methods=['GET', 'POST'])
@login_required
def api_campaigns():
    if request.method == 'GET':
        campaigns_data = read_json_file(CAMPAIGNS_FILE)
        return jsonify(campaigns_data)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        campaigns = read_json_file(CAMPAIGNS_FILE)
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
        write_json_file(CAMPAIGNS_FILE, campaigns)
        
        return jsonify({'success': True, 'campaign_id': campaign_id})

@app.route('/api/campaigns/<int:campaign_id>/start', methods=['POST'])
@login_required
def start_campaign(campaign_id):
    campaigns = read_json_file(CAMPAIGNS_FILE)
    campaign = campaigns.get(str(campaign_id))
    
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    if campaign.get('status') == 'running':
        return jsonify({'error': 'Campaign is already running'}), 400
    
    # Add to queue for processing
    campaign_queue.put((campaign_id, current_user.id))
    
    return jsonify({'success': True, 'message': 'Campaign started'})

@app.route('/api/campaigns/<int:campaign_id>/stop', methods=['POST'])
@login_required
def stop_campaign(campaign_id):
    campaigns = read_json_file(CAMPAIGNS_FILE)
    campaign = campaigns.get(str(campaign_id))
    
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404
    
    campaign['status'] = 'stopped'
    write_json_file(CAMPAIGNS_FILE, campaigns)
    
    return jsonify({'success': True, 'message': 'Campaign stopped'})

@app.route('/api/accounts', methods=['GET', 'POST'])
@login_required
def api_accounts():
    if request.method == 'GET':
        accounts_data = read_json_file(ACCOUNTS_FILE)
        return jsonify(accounts_data)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        accounts = read_json_file(ACCOUNTS_FILE)
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
        write_json_file(ACCOUNTS_FILE, accounts)
        
        return jsonify({'success': True, 'account_id': account_id})

@app.route('/api/data-lists', methods=['GET', 'POST'])
@login_required
def api_data_lists():
    if request.method == 'GET':
        data_lists = read_json_file(DATA_LISTS_FILE)
        return jsonify(data_lists)
    
    elif request.method == 'POST':
        data = request.get_json()
        
        data_lists = read_json_file(DATA_LISTS_FILE)
        list_id = str(max([int(k) for k in data_lists.keys()] + [0]) + 1)
        
        new_list = {
            'id': int(list_id),
            'name': data.get('name'),
            'filename': data.get('filename'),
            'created_at': datetime.now().isoformat(),
            'created_by': current_user.id
        }
        
        data_lists[list_id] = new_list
        write_json_file(DATA_LISTS_FILE, data_lists)
        
        return jsonify({'success': True, 'list_id': list_id})

# Login routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        users = read_json_file(USERS_FILE)
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

# Initialize data files
def init_data_files():
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
                'created_at': datetime.now().isoformat()
            }
        },
        DATA_LISTS_FILE: {}
    }
    
    for filename, default_data in files.items():
        if not os.path.exists(filename):
            write_json_file(filename, default_data)

if __name__ == '__main__':
    init_data_files()
    
    print("🚀 Starting Fixed Email Campaign Manager...")
    print("✅ Simple, reliable, and fast")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=8000,
        debug=False,
        use_reloader=False,
        threaded=True
    ) 