import os
import json
import time
import random
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import csv
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
from functools import wraps

# File constants
ACCOUNTS_FILE = 'accounts.json'
CAMPAIGNS_FILE = 'campaigns.json'
USERS_FILE = 'users.json'
NOTIFICATIONS_FILE = 'notifications.json'
CAMPAIGN_LOGS_FILE = 'campaign_logs.json'
BOUNCES_FILE = 'bounces.json'
DELIVERED_FILE = 'delivered.json'
DATA_LISTS_FILE = 'data_lists.json'
PASSWORD_RESET_TOKENS_FILE = 'password_reset_tokens.json'
SMTP_CONFIG_FILE = 'smtp_config.json'

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize extensions
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Global variables
running_campaigns = {}

# Simple file operations
def read_json_file(filename):
    """Read JSON file with error handling"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Error reading {filename}: {e}")
        return [] if 'campaigns' in filename or 'accounts' in filename else {}

def write_json_file(filename, data):
    """Write JSON file with error handling"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Successfully wrote {filename}")
        return True
    except Exception as e:
        print(f"❌ Error writing {filename}: {e}")
        return False

# Initialize data files
def init_data_files():
    """Initialize all data files if they don't exist"""
    files_to_init = {
        ACCOUNTS_FILE: [],
        CAMPAIGNS_FILE: [],
        USERS_FILE: [],
        NOTIFICATIONS_FILE: [],
        CAMPAIGN_LOGS_FILE: {},
        BOUNCES_FILE: {},
        DELIVERED_FILE: {},
        DATA_LISTS_FILE: [],
        PASSWORD_RESET_TOKENS_FILE: {},
        SMTP_CONFIG_FILE: {}
    }
    
    for filename, default_data in files_to_init.items():
        if not os.path.exists(filename):
            write_json_file(filename, default_data)
            print(f"✅ Initialized {filename}")

# Initialize files on startup
init_data_files()

# User class
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.username = user_data.get('username')
        self.role = user_data.get('role', 'user')
        self.permissions = user_data.get('permissions', [])
        self.is_active = user_data.get('is_active', True)
        self.created_at = user_data.get('created_at')

@login_manager.user_loader
def load_user(user_id):
    users = read_json_file(USERS_FILE)
    user_data = next((user for user in users if user['id'] == int(user_id)), None)
    return User(user_data) if user_data else None

# Notification functions
def add_notification(message, type='info', campaign_id=None):
    """Add a notification"""
    notifications = read_json_file(NOTIFICATIONS_FILE)
    notification = {
        'id': str(uuid.uuid4()),
        'message': message,
        'type': type,
        'timestamp': datetime.now().isoformat(),
        'read': False,
        'campaign_id': campaign_id
    }
    notifications.append(notification)
    write_json_file(NOTIFICATIONS_FILE, notifications)
    socketio.emit('new_notification', notification)

# Campaign log functions
def add_campaign_log(campaign_id, log_entry):
    """Add a log entry for a campaign"""
    logs = read_json_file(CAMPAIGN_LOGS_FILE)
    if str(campaign_id) not in logs:
        logs[str(campaign_id)] = []
    logs[str(campaign_id)].append(log_entry)
    write_json_file(CAMPAIGN_LOGS_FILE, logs)

def get_campaign_logs(campaign_id):
    """Get logs for a campaign"""
    logs = read_json_file(CAMPAIGN_LOGS_FILE)
    return logs.get(str(campaign_id), [])

# Bounce and delivery functions
def add_bounce_email(email, campaign_id, reason, subject=None, sender=None):
    """Add a bounced email"""
    bounces = read_json_file(BOUNCES_FILE)
    if str(campaign_id) not in bounces:
        bounces[str(campaign_id)] = []
    
    bounce_entry = {
        'email': email,
        'reason': reason,
        'subject': subject,
        'sender': sender,
        'timestamp': datetime.now().isoformat()
    }
    bounces[str(campaign_id)].append(bounce_entry)
    write_json_file(BOUNCES_FILE, bounces)

def add_delivered_email(email, campaign_id, subject=None, sender=None, details=None):
    """Add a delivered email"""
    delivered = read_json_file(DELIVERED_FILE)
    if str(campaign_id) not in delivered:
        delivered[str(campaign_id)] = []
    
    delivered_entry = {
        'email': email,
        'subject': subject,
        'sender': sender,
        'details': details,
        'timestamp': datetime.now().isoformat()
    }
    delivered[str(campaign_id)].append(delivered_entry)
    write_json_file(DELIVERED_FILE, delivered)

def get_bounced_emails(campaign_id=None):
    """Get bounced emails"""
    bounces = read_json_file(BOUNCES_FILE)
    if campaign_id:
        return bounces.get(str(campaign_id), [])
    return bounces

def get_delivered_emails(campaign_id=None):
    """Get delivered emails"""
    delivered = read_json_file(DELIVERED_FILE)
    if campaign_id:
        return delivered.get(str(campaign_id), [])
    return delivered

def filter_bounced_emails(emails, campaign_id):
    """Filter out bounced emails from a list"""
    bounces = get_bounced_emails(campaign_id)
    bounced_emails = {bounce['email'] for bounce in bounces}
    return [email for email in emails if email not in bounced_emails]

# Email sending function
def send_campaign_emails(campaign, account):
    """Send emails for a campaign"""
    campaign_id = campaign['id']
    
    try:
        print(f"🚀 Starting campaign: {campaign['name']} (ID: {campaign_id})")
        
        # Create initial log entry
        start_log = {
            'campaign_id': campaign_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'info',
            'message': f"🚀 Campaign '{campaign['name']}' started",
            'type': 'start'
        }
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
        error_count = 0
        
        print(f"📊 Campaign stats: {total_emails} emails to send")
        
        # Zoho API endpoint
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
            
            # Select random subject and sender
            subject = random.choice(subjects) if subjects else "Default Subject"
            sender = random.choice(froms) if froms else "Default Sender"
            
            # Deluge script
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

            # Headers
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

            try:
                print(f"📤 Sending email to: {email}")
                
                # Make API request
                response = requests.post(
                    url,
                    json=json_data,
                    cookies=account['cookies'],
                    headers=headers,
                    timeout=30
                )
                
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
                    
                else:
                    error_msg = f"❌ API Error ({response.status_code})"
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
                        'response_code': response.status_code
                    }
                    add_campaign_log(campaign_id, error_log)
                    socketio.emit('email_progress', error_log)
                    
            except Exception as e:
                error_msg = f"❌ Error sending email to {email}: {str(e)}"
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
                    'type': 'send_error',
                    'exception': str(e)
                }
                add_campaign_log(campaign_id, error_log)
                socketio.emit('email_progress', error_log)
            
            # Update campaign progress
            campaigns = read_json_file(CAMPAIGNS_FILE)
            campaign_index = next((i for i, c in enumerate(campaigns) if c['id'] == campaign_id), None)
            
            if campaign_index is not None:
                campaigns[campaign_index]['total_sent'] = sent_count
                campaigns[campaign_index]['total_attempted'] = i + 1
                write_json_file(CAMPAIGNS_FILE, campaigns)
            
            # Small delay between emails
            time.sleep(0.5)
        
        # Campaign completed
        completion_msg = f"🏁 Campaign '{campaign['name']}' completed! Sent: {sent_count}, Errors: {error_count}"
        print(completion_msg)
        
        completion_log = {
            'campaign_id': campaign_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'info',
            'message': completion_msg,
            'type': 'completion',
            'total_sent': sent_count,
            'total_errors': error_count
        }
        add_campaign_log(campaign_id, completion_log)
        socketio.emit('email_progress', completion_log)
        
        # Update campaign status
        campaigns = read_json_file(CAMPAIGNS_FILE)
        campaign_index = next((i for i, c in enumerate(campaigns) if c['id'] == campaign_id), None)
        
        if campaign_index is not None:
            campaigns[campaign_index]['status'] = 'completed'
            campaigns[campaign_index]['completed_at'] = datetime.now().isoformat()
            campaigns[campaign_index]['total_sent'] = sent_count
            campaigns[campaign_index]['total_attempted'] = total_emails
            write_json_file(CAMPAIGNS_FILE, campaigns)
        
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
        campaigns = read_json_file(CAMPAIGNS_FILE)
        campaign_index = next((i for i, c in enumerate(campaigns) if c['id'] == campaign_id), None)
        
        if campaign_index is not None:
            campaigns[campaign_index]['status'] = 'error'
            write_json_file(CAMPAIGNS_FILE, campaigns)
        
        # Remove from running campaigns
        if campaign_id in running_campaigns:
            del running_campaigns[campaign_id]
        
        # Send error notification
        add_notification(f"❌ Campaign '{campaign['name']}' failed: {str(e)}", 'error', campaign_id)

# Routes
@app.route('/')
@login_required
def dashboard():
    """Dashboard page"""
    campaigns = read_json_file(CAMPAIGNS_FILE)
    accounts = read_json_file(ACCOUNTS_FILE)
    notifications = read_json_file(NOTIFICATIONS_FILE)
    
    # Filter campaigns based on user permissions
    if current_user.role == 'admin' or 'view_all_campaigns' in current_user.permissions:
        user_campaigns = campaigns
    else:
        user_campaigns = [c for c in campaigns if c.get('created_by') == current_user.id]
    
    # Calculate statistics
    total_campaigns = len(user_campaigns)
    running_campaigns_count = len([c for c in user_campaigns if c.get('status') == 'running'])
    completed_campaigns = len([c for c in user_campaigns if c.get('status') == 'completed'])
    total_sent = sum(c.get('total_sent', 0) for c in user_campaigns)
    
    # Get recent notifications
    recent_notifications = notifications[-5:] if notifications else []
    
    return render_template('dashboard.html', 
                         campaigns=user_campaigns,
                         accounts=accounts,
                         notifications=recent_notifications,
                         stats={
                             'total_campaigns': total_campaigns,
                             'running_campaigns': running_campaigns_count,
                             'completed_campaigns': completed_campaigns,
                             'total_sent': total_sent
                         })

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = read_json_file(USERS_FILE)
        user_data = next((user for user in users if user['username'] == username), None)
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data)
            login_user(user)
            add_notification(f"User {username} logged in successfully", 'info')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# API Routes
@app.route('/api/campaigns', methods=['GET', 'POST'])
@login_required
def api_campaigns():
    """Campaigns API"""
    if request.method == 'GET':
        campaigns = read_json_file(CAMPAIGNS_FILE)
        
        # Filter campaigns based on user permissions
        if current_user.role == 'admin' or 'view_all_campaigns' in current_user.permissions:
            return jsonify(campaigns)
        else:
            user_campaigns = [c for c in campaigns if c.get('created_by') == current_user.id]
            return jsonify(user_campaigns)
    
    elif request.method == 'POST':
        try:
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Validate required fields
            required_fields = ['name', 'account_id', 'template_id', 'destinataires', 'subjects', 'froms']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            campaigns = read_json_file(CAMPAIGNS_FILE)
            
            # Generate new campaign ID
            new_id = max([camp['id'] for camp in campaigns], default=0) + 1 if campaigns else 1
            
            # Create campaign object
            new_campaign = {
                'id': new_id,
                'name': str(data['name'])[:100],
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
            
            campaigns.append(new_campaign)
            
            if write_json_file(CAMPAIGNS_FILE, campaigns):
                add_notification(f"Campaign '{data['name']}' created successfully", 'success', new_id)
                return jsonify(new_campaign)
            else:
                return jsonify({'error': 'Failed to save campaign to file'}), 500
                
        except Exception as e:
            print(f"❌ Error creating campaign: {str(e)}")
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>/start', methods=['POST'])
@login_required
def start_campaign(campaign_id):
    """Start a campaign"""
    try:
        campaigns = read_json_file(CAMPAIGNS_FILE)
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Check permissions
        if current_user.role != 'admin' and campaign.get('created_by') != current_user.id:
            return jsonify({'error': 'Permission denied'}), 403
        
        if campaign['status'] == 'running':
            return jsonify({'error': 'Campaign is already running'}), 400
        
        # Get account
        accounts = read_json_file(ACCOUNTS_FILE)
        account = next((a for a in accounts if a['id'] == campaign['account_id']), None)
        
        if not account:
            return jsonify({'error': 'Account not found'}), 404
        
        # Update campaign status
        campaign['status'] = 'running'
        campaign['started_at'] = datetime.now().isoformat()
        write_json_file(CAMPAIGNS_FILE, campaigns)
        
        # Add to running campaigns
        running_campaigns[campaign_id] = True
        
        # Start sending emails in background thread
        thread = threading.Thread(target=send_campaign_emails, args=(campaign, account))
        thread.daemon = True
        thread.start()
        
        add_notification(f"Campaign '{campaign['name']}' started", 'success', campaign_id)
        return jsonify({'message': 'Campaign started successfully'})
        
    except Exception as e:
        return jsonify({'error': f'Error starting campaign: {str(e)}'}), 500

@app.route('/api/campaigns/<int:campaign_id>/stop', methods=['POST'])
@login_required
def stop_campaign(campaign_id):
    """Stop a campaign"""
    try:
        campaigns = read_json_file(CAMPAIGNS_FILE)
        campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Check permissions
        if current_user.role != 'admin' and campaign.get('created_by') != current_user.id:
            return jsonify({'error': 'Permission denied'}), 403
        
        if campaign['status'] != 'running':
            return jsonify({'error': 'Campaign is not running'}), 400
        
        # Remove from running campaigns
        if campaign_id in running_campaigns:
            del running_campaigns[campaign_id]
        
        # Update campaign status
        campaign['status'] = 'stopped'
        campaign['stopped_at'] = datetime.now().isoformat()
        write_json_file(CAMPAIGNS_FILE, campaigns)
        
        add_notification(f"Campaign '{campaign['name']}' stopped", 'warning', campaign_id)
        return jsonify({'message': 'Campaign stopped successfully'})
        
    except Exception as e:
        return jsonify({'error': f'Error stopping campaign: {str(e)}'}), 500

# Template filters
@app.template_filter('get_status_badge_class')
def get_status_badge_class(status):
    """Get Bootstrap badge class for status"""
    status_classes = {
        'ready': 'bg-primary',
        'running': 'bg-success',
        'completed': 'bg-info',
        'stopped': 'bg-warning',
        'error': 'bg-danger'
    }
    return status_classes.get(status, 'bg-secondary')

@app.template_filter('format_timestamp')
def format_timestamp(timestamp):
    """Format timestamp for display"""
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp

# Context processor
@app.context_processor
def utility_processor():
    def is_admin():
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def has_permission(permission):
        return current_user.is_authenticated and permission in current_user.permissions
    
    return {
        'is_admin': is_admin,
        'has_permission': has_permission
    }

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)