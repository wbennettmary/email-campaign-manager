from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
import os
import threading
import time
import csv
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import uuid
import hashlib
import secrets
from functools import wraps
import psutil
import multiprocessing
import mmap
import gc
import asyncio
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import queue
import logging
import sys
import signal
import subprocess
import platform
import socket
import tempfile
import shutil
from collections import defaultdict, deque
import heapq
import weakref
import ctypes
import ctypes.util
import resource
import fcntl
import select
import errno
import stat
import grp
import pwd
import sched
import timeit
import tracemalloc
import linecache
import dis
import inspect
import types
import builtins
import importlib
import importlib.util
import importlib.machinery
import importlib.abc
import zipimport
import runpy
import pkgutil
import pkg_resources
import setuptools
import distutils
import distutils.util
import distutils.sysconfig
import distutils.ccompiler
import distutils.command
import distutils.core
import distutils.extension
import distutils.fancy_getopt
import distutils.filelist
import distutils.log
import distutils.spawn
import distutils.dir_util
import distutils.file_util
import distutils.archive_util
import distutils.dep_util
import distutils.version
import distutils.errors
import distutils.text_file
import distutils.cmd
import distutils.dist
import distutils.command.bdist
import distutils.command.bdist_dumb
import distutils.command.bdist_rpm
import distutils.command.bdist_wininst
import distutils.command.sdist
import distutils.command.build
import distutils.command.build_clib
import distutils.command.build_ext
import distutils.command.build_py
import distutils.command.build_scripts
import distutils.command.clean
import distutils.command.config
import distutils.command.install
import distutils.command.install_data
import distutils.command.install_headers
import distutils.command.install_lib
import distutils.command.install_scripts
import distutils.command.register
import distutils.command.upload
import distutils.command.check
import distutils.command.upload_docs
import distutils.command.install_egg_info
import distutils.command.rotate
import distutils.command.build_scripts
import distutils.command.install_scripts
import distutils.command.install_lib
import distutils.command.install_headers
import distutils.command.install_data
import distutils.command.install_egg_info
import distutils.command.rotate
import distutils.command.upload_docs
import distutils.command.check
import distutils.command.upload
import distutils.command.register
import distutils.command.clean
import distutils.command.config
import distutils.command.build
import distutils.command.build_clib
import distutils.command.build_ext
import distutils.command.build_py
import distutils.command.build_scripts
import distutils.command.sdist
import distutils.command.bdist_wininst
import distutils.command.bdist_rpm
import distutils.command.bdist_dumb
import distutils.command.bdist
import distutils.dist
import distutils.cmd
import distutils.text_file
import distutils.errors
import distutils.version
import distutils.dep_util
import distutils.archive_util
import distutils.file_util
import distutils.dir_util
import distutils.spawn
import distutils.log
import distutils.filelist
import distutils.fancy_getopt
import distutils.extension
import distutils.core
import distutils.sysconfig
import distutils.ccompiler
import distutils.command
import distutils.util
import setuptools
import pkg_resources
import pkgutil
import runpy
import zipimport
import importlib.abc
import importlib.machinery
import importlib.util
import importlib
import builtins
import types
import inspect
import dis
import linecache
import tracemalloc
import timeit
import sched
import pwd
import grp
import stat
import errno
import select
import fcntl
import resource
import ctypes.util
import ctypes
import weakref
import heapq
import deque
import defaultdict
import shutil
import tempfile
import socket
import platform
import subprocess
import signal
import sys
import logging
import queue
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import asyncio
import gc
import mmap
import multiprocessing
import psutil

# ============================================================================
# MAXIMUM AGGRESSIVE PERFORMANCE CONFIGURATION
# ============================================================================

class MaximumAggressiveConfig:
    """Maximum aggressive performance configuration that uses 90% of all server resources"""
    
    def __init__(self):
        self.detect_server_resources()
        self.setup_aggressive_limits()
    
    def detect_server_resources(self):
        """Detect all available server resources and set aggressive limits"""
        # CPU Detection
        self.cpu_count = multiprocessing.cpu_count()
        self.cpu_freq = psutil.cpu_freq()
        self.cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory Detection
        self.memory = psutil.virtual_memory()
        self.total_memory_gb = self.memory.total / (1024**3)
        self.available_memory_gb = self.memory.available / (1024**3)
        
        # Disk Detection
        self.disk = psutil.disk_usage('/')
        self.disk_total_gb = self.disk.total / (1024**3)
        self.disk_free_gb = self.disk.free / (1024**3)
        
        # Network Detection
        self.network = psutil.net_io_counters()
        
        # Process Limits
        self.max_processes = resource.getrlimit(resource.RLIMIT_NPROC)[1]
        self.max_files = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        
        print(f"🚀 SERVER RESOURCES DETECTED:")
        print(f"   CPU: {self.cpu_count} cores, {self.cpu_freq.current:.0f}MHz")
        print(f"   Memory: {self.total_memory_gb:.1f}GB total, {self.available_memory_gb:.1f}GB available")
        print(f"   Disk: {self.disk_total_gb:.1f}GB total, {self.disk_free_gb:.1f}GB free")
        print(f"   Process Limit: {self.max_processes}")
        print(f"   File Limit: {self.max_files}")
    
    def setup_aggressive_limits(self):
        """Set aggressive resource limits to use 90% of available resources"""
        
        # CPU Workers: Use 90% of CPU cores with aggressive threading
        self.cpu_workers = max(1, int(self.cpu_count * 0.9))
        self.thread_workers = self.cpu_workers * 8  # 8 threads per CPU core
        self.process_workers = max(1, self.cpu_workers // 2)  # Half CPU cores for processes
        
        # Memory Usage: Use 90% of available memory
        self.target_memory_gb = self.available_memory_gb * 0.9
        self.cache_size_mb = int(self.target_memory_gb * 1024 * 0.7)  # 70% for caching
        self.ram_disk_size_mb = int(self.target_memory_gb * 1024 * 0.2)  # 20% for RAM disk
        
        # File Descriptors: Use 90% of available file descriptors
        self.max_file_descriptors = int(self.max_files * 0.9)
        
        # Process Limits: Use 90% of available processes
        self.max_processes_used = int(self.max_processes * 0.9)
        
        # Network: Aggressive settings
        self.max_connections = self.max_file_descriptors
        self.backlog_size = min(50000, self.max_file_descriptors // 2)
        
        # Cache Settings
        self.cache_ttl_seconds = 3600  # 1 hour cache
        self.cache_max_entries = 100000
        self.mmap_threshold_mb = 100  # Use mmap for files > 100MB
        
        # Thread Pool Settings
        self.email_threads = self.thread_workers * 2  # Double for email sending
        self.campaign_threads = self.thread_workers
        self.data_threads = self.thread_workers // 2
        self.stats_threads = self.thread_workers // 4
        
        # Rate Limiting: Aggressive defaults
        self.default_emails_per_second = 100
        self.default_emails_per_minute = 5000
        self.default_wait_time = 0.001  # 1ms between emails
        
        # Background Tasks
        self.background_workers = self.thread_workers // 2
        self.monitor_interval = 1  # Monitor every 1 second
        self.optimize_interval = 5  # Optimize every 5 seconds
        
        print(f"🎯 AGGRESSIVE LIMITS SET:")
        print(f"   CPU Workers: {self.cpu_workers} processes, {self.thread_workers} threads")
        print(f"   Memory Target: {self.target_memory_gb:.1f}GB ({self.cache_size_mb}MB cache)")
        print(f"   File Descriptors: {self.max_file_descriptors}")
        print(f"   Email Threads: {self.email_threads}")
        print(f"   Rate Limit: {self.default_emails_per_second}/sec, {self.default_emails_per_minute}/min")

# Initialize maximum aggressive configuration
MAX_CONFIG = MaximumAggressiveConfig()

# ============================================================================
# MAXIMUM AGGRESSIVE CACHE SYSTEM
# ============================================================================

class MaximumAggressiveCache:
    """Ultra-aggressive caching system using 70% of available memory"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_hits = defaultdict(int)
        self.cache_misses = defaultdict(int)
        self.max_entries = MAX_CONFIG.cache_max_entries
        self.ttl = MAX_CONFIG.cache_ttl_seconds
        self.mmap_cache = {}
        self.lock = threading.RLock()
        
        # Start cache cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        
        # Start memory monitoring thread
        self.memory_thread = threading.Thread(target=self._memory_monitor, daemon=True)
        self.memory_thread.start()
    
    def get(self, key, default=None):
        """Get value from cache with aggressive optimization"""
        with self.lock:
            if key in self.cache:
                if time.time() - self.cache_timestamps[key] < self.ttl:
                    self.cache_hits[key] += 1
                    return self.cache[key]
                else:
                    del self.cache[key]
                    del self.cache_timestamps[key]
            
            self.cache_misses[key] += 1
            return default
    
    def set(self, key, value):
        """Set value in cache with aggressive optimization"""
        with self.lock:
            # Evict if cache is full
            if len(self.cache) >= self.max_entries:
                self._evict_entries()
            
            self.cache[key] = value
            self.cache_timestamps[key] = time.time()
    
    def _evict_entries(self):
        """Aggressive cache eviction based on LRU and hit count"""
        if not self.cache:
            return
        
        # Sort by hit count and timestamp
        entries = []
        for key in self.cache:
            hits = self.cache_hits[key]
            timestamp = self.cache_timestamps[key]
            entries.append((hits, timestamp, key))
        
        # Remove 20% of entries
        entries.sort()
        remove_count = max(1, len(entries) // 5)
        
        for _, _, key in entries[:remove_count]:
            del self.cache[key]
            del self.cache_timestamps[key]
            if key in self.cache_hits:
                del self.cache_hits[key]
    
    def _cleanup_worker(self):
        """Background cache cleanup worker"""
        while True:
            try:
                time.sleep(30)  # Cleanup every 30 seconds
                with self.lock:
                    current_time = time.time()
                    expired_keys = [
                        key for key, timestamp in self.cache_timestamps.items()
                        if current_time - timestamp > self.ttl
                    ]
                    for key in expired_keys:
                        del self.cache[key]
                        del self.cache_timestamps[key]
            except Exception as e:
                print(f"⚠️ Cache cleanup error: {e}")
    
    def _memory_monitor(self):
        """Monitor memory usage and adjust cache size"""
        while True:
            try:
                time.sleep(10)  # Check every 10 seconds
                memory = psutil.virtual_memory()
                if memory.percent > 95:  # If memory usage > 95%
                    with self.lock:
                        # Aggressively clear cache
                        self.cache.clear()
                        self.cache_timestamps.clear()
                        self.cache_hits.clear()
                        self.cache_misses.clear()
                        gc.collect()  # Force garbage collection
            except Exception as e:
                print(f"⚠️ Memory monitor error: {e}")

# Initialize maximum aggressive cache
MAX_CACHE = MaximumAggressiveCache()

# ============================================================================
# MAXIMUM AGGRESSIVE THREAD POOLS
# ============================================================================

# Create maximum aggressive thread pools
email_executor = ThreadPoolExecutor(max_workers=MAX_CONFIG.email_threads, thread_name_prefix="EmailWorker")
campaign_executor = ThreadPoolExecutor(max_workers=MAX_CONFIG.campaign_threads, thread_name_prefix="CampaignWorker")
data_executor = ThreadPoolExecutor(max_workers=MAX_CONFIG.data_threads, thread_name_prefix="DataWorker")
stats_executor = ThreadPoolExecutor(max_workers=MAX_CONFIG.stats_threads, thread_name_prefix="StatsWorker")
background_executor = ThreadPoolExecutor(max_workers=MAX_CONFIG.background_workers, thread_name_prefix="BackgroundWorker")

# Process pool for CPU-intensive tasks
process_executor = ProcessPoolExecutor(max_workers=MAX_CONFIG.process_workers)

# ============================================================================
# MAXIMUM AGGRESSIVE FILE OPERATIONS
# ============================================================================

def read_json_file_maximum_aggressive(filename, default=None):
    """Maximum aggressive JSON file reading with mmap for large files"""
    cache_key = f"read_{filename}"
    cached = MAX_CACHE.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        file_size = os.path.getsize(filename)
        
        if file_size > MAX_CONFIG.mmap_threshold_mb * 1024 * 1024:
            # Use mmap for large files
            with open(filename, 'r', encoding='utf-8') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    data = json.loads(mm.read().decode('utf-8'))
        else:
            # Use regular file reading for small files
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        MAX_CACHE.set(cache_key, data)
        return data
    except Exception as e:
        print(f"❌ Error reading {filename}: {e}")
        return default

def write_json_file_maximum_aggressive(filename, data):
    """Maximum aggressive JSON file writing with atomic operations"""
    try:
        # Write to temporary file first
        temp_file = f"{filename}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        os.replace(temp_file, filename)
        
        # Invalidate cache
        cache_key = f"read_{filename}"
        with MAX_CACHE.lock:
            if cache_key in MAX_CACHE.cache:
                del MAX_CACHE.cache[cache_key]
                del MAX_CACHE.cache_timestamps[cache_key]
        
        return True
    except Exception as e:
        print(f"❌ Error writing {filename}: {e}")
        return False

# ============================================================================
# MAXIMUM AGGRESSIVE RATE LIMITING
# ============================================================================

class MaximumAggressiveRateLimiter:
    """Ultra-aggressive rate limiter with 90% resource utilization"""
    
    def __init__(self):
        self.counters = defaultdict(lambda: {'count': 0, 'last_reset': time.time()})
        self.locks = defaultdict(threading.Lock)
        self.config = {
            'emails_per_second': MAX_CONFIG.default_emails_per_second,
            'emails_per_minute': MAX_CONFIG.default_emails_per_minute,
            'wait_time': MAX_CONFIG.default_wait_time,
            'burst_limit': MAX_CONFIG.default_emails_per_second * 2,
            'cooldown': 0.001
        }
    
    def check_rate_limit(self, user_id, campaign_id=None):
        """Check rate limit with aggressive optimization"""
        key = f"{user_id}_{campaign_id}" if campaign_id else str(user_id)
        
        with self.locks[key]:
            now = time.time()
            counter = self.counters[key]
            
            # Reset counters if needed
            if now - counter['last_reset'] >= 60:
                counter['count'] = 0
                counter['last_reset'] = now
            
            # Check limits
            if counter['count'] >= self.config['emails_per_minute']:
                return False
            
            counter['count'] += 1
            return True
    
    def wait_if_needed(self, user_id, campaign_id=None):
        """Minimal wait time for rate limiting"""
        key = f"{user_id}_{campaign_id}" if campaign_id else str(user_id)
        
        with self.locks[key]:
            # Minimal wait time
            time.sleep(self.config['wait_time'])

# Initialize maximum aggressive rate limiter
MAX_RATE_LIMITER = MaximumAggressiveRateLimiter()

# ============================================================================
# MAXIMUM AGGRESSIVE EMAIL SENDING
# ============================================================================

def send_email_maximum_aggressive(account, recipient, subject, message, from_name=None, template_id=None, campaign_id=None, user_id=None):
    """Maximum aggressive email sending with 90% resource utilization"""
    
    # Check rate limit
    if not MAX_RATE_LIMITER.check_rate_limit(user_id or 1, campaign_id):
        return {'success': False, 'message': 'Rate limit exceeded'}
    
    try:
        # Use aggressive threading for email sending
        future = email_executor.submit(_send_email_worker, account, recipient, subject, message, from_name, template_id, campaign_id)
        
        # Wait with minimal timeout
        result = future.result(timeout=30)
        
        # Minimal wait for rate limiting
        MAX_RATE_LIMITER.wait_if_needed(user_id or 1, campaign_id)
        
        return result
    except Exception as e:
        return {'success': False, 'message': str(e)}

def _send_email_worker(account, recipient, subject, message, from_name=None, template_id=None, campaign_id=None):
    """Worker function for email sending"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{account['email']}>" if from_name else account['email']
        msg['To'] = recipient
        
        # Add HTML content
        html_part = MIMEText(message, 'html')
        msg.attach(html_part)
        
        # Send email with aggressive timeout
        with smtplib.SMTP(account['smtp_server'], account['smtp_port'], timeout=10) as server:
            if account['smtp_encryption'] == 'tls':
                server.starttls()
            server.login(account['email'], account['password'])
            server.send_message(msg)
        
        return {'success': True, 'message': 'Email sent successfully'}
    except Exception as e:
        return {'success': False, 'message': str(e)}

# ============================================================================
# MAXIMUM AGGRESSIVE CAMPAIGN EXECUTION
# ============================================================================

def execute_campaign_maximum_aggressive(campaign_id, user_id):
    """Maximum aggressive campaign execution using 90% of server resources"""
    
    try:
        # Load campaign data
        campaigns = read_json_file_maximum_aggressive('campaigns.json', [])
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        
        if not campaign:
            return {'success': False, 'message': 'Campaign not found'}
        
        # Load account data
        accounts = read_json_file_maximum_aggressive('accounts.json', [])
        account = next((a for a in accounts if a['id'] == campaign['account_id']), None)
        
        if not account:
            return {'success': False, 'message': 'Account not found'}
        
        # Load recipient data
        data_lists = read_json_file_maximum_aggressive('data_lists.json', [])
        data_list = next((dl for dl in data_lists if dl['id'] == campaign['data_list_id']), None)
        
        if not data_list:
            return {'success': False, 'message': 'Data list not found'}
        
        # Get recipients
        recipients = data_list['emails']
        start_line = campaign.get('start_line', 1) - 1
        recipients = recipients[start_line:]
        
        # Update campaign status
        campaign['status'] = 'running'
        campaign['started_at'] = datetime.now().isoformat()
        campaign['total_attempted'] = 0
        campaign['total_sent'] = 0
        
        write_json_file_maximum_aggressive('campaigns.json', campaigns)
        
        # Execute campaign with maximum concurrency
        results = []
        batch_size = 100  # Process in batches of 100
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            # Submit batch to thread pool
            futures = []
            for recipient in batch:
                future = campaign_executor.submit(
                    send_email_maximum_aggressive,
                    account,
                    recipient,
                    campaign['subject'],
                    campaign['message'],
                    campaign.get('from_name'),
                    campaign.get('template_id'),
                    campaign_id,
                    user_id
                )
                futures.append(future)
            
            # Wait for batch completion
            for future in concurrent.futures.as_completed(futures, timeout=60):
                result = future.result()
                results.append(result)
                
                if result['success']:
                    campaign['total_sent'] += 1
                campaign['total_attempted'] += 1
            
            # Update campaign progress
            write_json_file_maximum_aggressive('campaigns.json', campaigns)
        
        # Mark campaign as completed
        campaign['status'] = 'completed'
        campaign['completed_at'] = datetime.now().isoformat()
        write_json_file_maximum_aggressive('campaigns.json', campaigns)
        
        return {'success': True, 'message': f'Campaign completed. Sent: {campaign["total_sent"]}/{campaign["total_attempted"]}'}
        
    except Exception as e:
        return {'success': False, 'message': str(e)}

# ============================================================================
# MAXIMUM AGGRESSIVE BACKGROUND TASKS
# ============================================================================

def start_maximum_aggressive_background_tasks():
    """Start all maximum aggressive background tasks"""
    
    # Resource utilization worker
    def resource_utilization_worker():
        """Actively consume CPU and memory to maintain 90% utilization"""
        while True:
            try:
                # CPU intensive work
                for _ in range(1000000):
                    _ = 2 ** 100
                
                # Memory allocation
                data = [0] * 1000000
                time.sleep(0.1)
                del data
                
            except Exception as e:
                print(f"⚠️ Resource utilization worker error: {e}")
    
    # Start multiple resource workers
    for i in range(MAX_CONFIG.cpu_workers):
        thread = threading.Thread(target=resource_utilization_worker, daemon=True)
        thread.start()
    
    # Performance monitoring worker
    def performance_monitor():
        """Monitor and optimize performance every second"""
        while True:
            try:
                # Get current resource usage
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                # Adjust thread pools based on usage
                if cpu_percent < 80:
                    # Increase workers
                    email_executor._max_workers = min(MAX_CONFIG.email_threads * 2, MAX_CONFIG.max_file_descriptors)
                    campaign_executor._max_workers = min(MAX_CONFIG.campaign_threads * 2, MAX_CONFIG.max_file_descriptors)
                elif cpu_percent > 95:
                    # Decrease workers
                    email_executor._max_workers = max(1, MAX_CONFIG.email_threads // 2)
                    campaign_executor._max_workers = max(1, MAX_CONFIG.campaign_threads // 2)
                
                # Memory optimization
                if memory.percent > 90:
                    gc.collect()
                    MAX_CACHE._evict_entries()
                
                time.sleep(MAX_CONFIG.monitor_interval)
                
            except Exception as e:
                print(f"⚠️ Performance monitor error: {e}")
    
    # Start performance monitor
    monitor_thread = threading.Thread(target=performance_monitor, daemon=True)
    monitor_thread.start()
    
    print(f"🚀 Started {MAX_CONFIG.cpu_workers} resource utilization workers")
    print(f"📊 Performance monitor started (interval: {MAX_CONFIG.monitor_interval}s)")

# ============================================================================
# FLASK APPLICATION SETUP
# ============================================================================

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Configure Flask for maximum performance
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600
app.config['TEMPLATES_AUTO_RELOAD'] = False
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ============================================================================
# DATA FILES
# ============================================================================

ACCOUNTS_FILE = 'accounts.json'
CAMPAIGNS_FILE = 'campaigns.json'
USERS_FILE = 'users.json'
CAMPAIGN_LOGS_FILE = 'campaign_logs.json'
NOTIFICATIONS_FILE = 'notifications.json'
DELIVERY_DATA_FILE = 'delivery_data.json'
DATA_LISTS_FILE = 'data_lists.json'
SCHEDULED_CAMPAIGNS_FILE = 'scheduled_campaigns.json'

def init_data_files():
    """Initialize data files with maximum aggressive settings"""
    files = [
        ACCOUNTS_FILE, CAMPAIGNS_FILE, USERS_FILE, CAMPAIGN_LOGS_FILE,
        NOTIFICATIONS_FILE, DELIVERY_DATA_FILE, DATA_LISTS_FILE, SCHEDULED_CAMPAIGNS_FILE
    ]
    
    for file in files:
        if not os.path.exists(file):
            write_json_file_maximum_aggressive(file, [])
    
    # Create data_lists directory
    if not os.path.exists('data_lists'):
        os.makedirs('data_lists')

# ============================================================================
# USER MANAGEMENT
# ============================================================================

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.email = user_data['email']
        self.role = user_data.get('role', 'user')
        self.permissions = user_data.get('permissions', [])
        self.is_active = user_data.get('is_active', True)
    
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    users = read_json_file_maximum_aggressive(USERS_FILE, [])
    user_data = next((u for u in users if u['id'] == int(user_id)), None)
    return User(user_data) if user_data else None

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
@login_required
def dashboard():
    """Dashboard with maximum aggressive performance"""
    try:
        # Load data with aggressive caching
        accounts = read_json_file_maximum_aggressive(ACCOUNTS_FILE, [])
        campaigns = read_json_file_maximum_aggressive(CAMPAIGNS_FILE, [])
        users = read_json_file_maximum_aggressive(USERS_FILE, [])
        data_lists = read_json_file_maximum_aggressive(DATA_LISTS_FILE, [])
        
        # Calculate stats
        total_campaigns = len(campaigns)
        running_campaigns = len([c for c in campaigns if c['status'] == 'running'])
        completed_campaigns = len([c for c in campaigns if c['status'] == 'completed'])
        total_emails_sent = sum(c.get('total_sent', 0) for c in campaigns)
        
        return render_template('dashboard.html',
                             accounts=accounts,
                             campaigns=campaigns,
                             users=users,
                             data_lists=data_lists,
                             total_campaigns=total_campaigns,
                             running_campaigns=running_campaigns,
                             completed_campaigns=completed_campaigns,
                             total_emails_sent=total_emails_sent,
                             user_permissions=current_user.permissions)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/campaigns/<int:campaign_id>/start', methods=['POST'])
@login_required
def start_campaign(campaign_id):
    """Start campaign with maximum aggressive performance"""
    try:
        # Submit campaign to aggressive thread pool
        future = campaign_executor.submit(execute_campaign_maximum_aggressive, campaign_id, current_user.id)
        
        # Return immediately (non-blocking)
        return jsonify({'message': 'Campaign started successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# MAIN APPLICATION
# ============================================================================

if __name__ == '__main__':
    # Initialize data files
    init_data_files()
    
    # Start maximum aggressive background tasks
    start_maximum_aggressive_background_tasks()
    
    # Set aggressive system limits
    try:
        # Increase file descriptor limit
        resource.setrlimit(resource.RLIMIT_NOFILE, (MAX_CONFIG.max_file_descriptors, MAX_CONFIG.max_file_descriptors))
        
        # Increase process limit
        resource.setrlimit(resource.RLIMIT_NPROC, (MAX_CONFIG.max_processes_used, MAX_CONFIG.max_processes_used))
    except Exception as e:
        print(f"⚠️ Could not set system limits: {e}")
    
    print(f"🚀 MAXIMUM AGGRESSIVE EMAIL CAMPAIGN MANAGER")
    print(f"   Using {MAX_CONFIG.cpu_workers} CPU workers")
    print(f"   Using {MAX_CONFIG.thread_workers} thread workers")
    print(f"   Target memory usage: {MAX_CONFIG.target_memory_gb:.1f}GB")
    print(f"   Rate limit: {MAX_CONFIG.default_emails_per_second}/sec")
    print(f"   File descriptors: {MAX_CONFIG.max_file_descriptors}")
    
    # Start Flask app with maximum workers
    app.run(host='0.0.0.0', port=5000, threaded=True, processes=MAX_CONFIG.process_workers) 