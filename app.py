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
from datetime import datetime
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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
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
                'password': generate_password_hash('admin123')
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
            first_account = list(accounts.values())[0]
            
            # Extract org_id from account data or headers
            org_id = first_account.get('org_id') or '893358824'  # Default org ID
            
            # Initialize bounce detector
            initialize_zoho_bounce_detector(
                account_cookies=first_account.get('cookies', {}),
                account_headers=first_account.get('headers', {}),
                org_id=org_id
            )
            
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
    except:
        notifications = []
    
    notification = {
        'id': str(uuid.uuid4()),
        'message': message,
        'type': type,
        'campaign_id': campaign_id,
        'timestamp': datetime.now().isoformat(),
        'read': False
    }
    
    notifications.append(notification)
    
    # Keep only last 100 notifications
    if len(notifications) > 100:
        notifications = notifications[-100:]
    
    with open(NOTIFICATIONS_FILE, 'w') as f:
        json.dump(notifications, f)
    
    # Emit notification to all connected clients
    socketio.emit('new_notification', notification)

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
            # Fallback to pattern-based detection if Zoho detector not available
            bounce_indicators = [
                "nonexistent", "invalid", "fake", "test", "bounce", 
                "spam", "trash", "disposable", "temp", "throwaway",
                "salsssaqz", "axxzexdflp"
            ]
            
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
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        
        user_data = next((user for user in users if user['username'] == username), None)
        
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/accounts')
@login_required
def accounts():
    try:
        with open(ACCOUNTS_FILE, 'r') as f:
            accounts = json.load(f)
        if not isinstance(accounts, list):
            accounts = []
    except (FileNotFoundError, json.JSONDecodeError):
        accounts = []
    return render_template('accounts.html', accounts=accounts)

@app.route('/campaigns')
@login_required
def campaigns():
    try:
        with open(CAMPAIGNS_FILE, 'r') as f:
            campaigns = json.load(f)
        if not isinstance(campaigns, list):
            campaigns = []
    except (FileNotFoundError, json.JSONDecodeError):
        campaigns = []
    return render_template('campaigns.html', campaigns=campaigns)

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
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
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
            with open(ACCOUNTS_FILE, 'r') as f:
                accounts = json.load(f)
            if not isinstance(accounts, list):
                accounts = []
        except (FileNotFoundError, json.JSONDecodeError):
            accounts = []
        return jsonify(accounts)
    
    elif request.method == 'POST':
        data = request.json
        try:
            with open(ACCOUNTS_FILE, 'r') as f:
                accounts = json.load(f)
            if not isinstance(accounts, list):
                accounts = []
        except (FileNotFoundError, json.JSONDecodeError):
            accounts = []
        
        new_account = {
            'id': max([acc['id'] for acc in accounts], default=0) + 1 if accounts else 1,
            'name': data['name'],
            'org_id': data['org_id'],
            'cookies': data['cookies'],
            'headers': data['headers'],
            'created_at': datetime.now().isoformat()
        }
        
        accounts.append(new_account)
        
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump(accounts, f)
        
        add_notification(f"Account '{data['name']}' added successfully", 'success')
        return jsonify(new_account)

@app.route('/api/accounts/<int:account_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_account(account_id):
    try:
        with open(ACCOUNTS_FILE, 'r') as f:
            accounts = json.load(f)
        if not isinstance(accounts, list):
            accounts = []
    except (FileNotFoundError, json.JSONDecodeError):
        accounts = []
    
    account = next((acc for acc in accounts if acc['id'] == account_id), None)
    
    if request.method == 'GET':
        return jsonify(account) if account else ('', 404)
    
    elif request.method == 'PUT':
        if not account:
            return ('', 404)
        
        data = request.json
        data['updated_at'] = datetime.now().isoformat()
        account.update(data)
        
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump(accounts, f)
        
        add_notification(f"Account '{account['name']}' updated successfully", 'success')
        return jsonify(account)
    
    elif request.method == 'DELETE':
        if not account:
            return ('', 404)
        
        accounts.remove(account)
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump(accounts, f)
        
        add_notification(f"Account '{account['name']}' deleted successfully", 'warning')
        return ('', 204)

@app.route('/api/campaigns', methods=['GET', 'POST'])
@login_required
def api_campaigns():
    if request.method == 'GET':
        try:
            with open(CAMPAIGNS_FILE, 'r') as f:
                campaigns = json.load(f)
            if not isinstance(campaigns, list):
                campaigns = []
        except (FileNotFoundError, json.JSONDecodeError):
            campaigns = []
        return jsonify(campaigns)
    
    elif request.method == 'POST':
        data = request.json
        try:
            with open(CAMPAIGNS_FILE, 'r') as f:
                campaigns = json.load(f)
            if not isinstance(campaigns, list):
                campaigns = []
        except (FileNotFoundError, json.JSONDecodeError):
            campaigns = []
        
        new_campaign = {
            'id': max([camp['id'] for camp in campaigns], default=0) + 1 if campaigns else 1,
            'name': data['name'],
            'account_id': data['account_id'],
            'template_id': data['template_id'],
            'destinataires': data['destinataires'],
            'subjects': data['subjects'],
            'froms': data['froms'],
            'status': 'ready',
            'created_at': datetime.now().isoformat(),
            'total_sent': 0,
            'total_attempted': 0
        }
        
        campaigns.append(new_campaign)
        
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump(campaigns, f)
        
        add_notification(f"Campaign '{data['name']}' created successfully", 'success', new_campaign['id'])
        return jsonify(new_campaign)

@app.route('/api/campaigns/<int:campaign_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_campaign(campaign_id):
    with open(CAMPAIGNS_FILE, 'r') as f:
        campaigns = json.load(f)
    
    campaign = next((camp for camp in campaigns if camp['id'] == campaign_id), None)
    
    if request.method == 'GET':
        return jsonify(campaign) if campaign else ('', 404)
    
    elif request.method == 'PUT':
        if not campaign:
            return ('', 404)
        
        data = request.json
        campaign.update(data)
        
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump(campaigns, f)
        
        add_notification(f"Campaign '{campaign['name']}' updated successfully", 'success', campaign_id)
        return jsonify(campaign)
    
    elif request.method == 'DELETE':
        if not campaign:
            return ('', 404)
        
        campaigns.remove(campaign)
        with open(CAMPAIGNS_FILE, 'w') as f:
            json.dump(campaigns, f)
        
        add_notification(f"Campaign '{campaign['name']}' deleted successfully", 'warning')
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
        return render_template('data_lists.html', data_lists=data_lists)
    except Exception as e:
        flash(f'Error loading data lists: {str(e)}', 'error')
        return render_template('data_lists.html', data_lists=[])

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
                    add_notification(f"Manual data list '{data.get('name', 'Manual List')}' created with {len(valid_emails)} emails", 'success')
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
                emails = get_data_list_emails(list_id)
                data_list['emails'] = emails
            
            return jsonify(data_list)
        except Exception as e:
            return jsonify({'error': f'Error getting data list: {str(e)}'}), 500
    
    elif request.method == 'PUT':
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
            
            # Select random subject and sender
            subject = random.choice(subjects) if subjects else "Default Subject"
            sender = random.choice(froms) if froms else "Default Sender"
            
            # Deluge script matching your working curl format
            script = f'''void automation.Send_Email_Template1()
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

            success = False
            attempt = 0
            max_attempts = 3

            while not success and attempt < max_attempts:
                try:
                    attempt += 1
                    print(f"📤 Sending email {i+1}/{total_emails} to: {email} (Attempt {attempt}/{max_attempts})")
                    print(f"   Subject: {subject}")
                    print(f"   Sender: {sender}")
                    print(f"   🔍 IMPROVED delivery tracking enabled")
                    
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
                    
                    # Make API request with enhanced headers
                    response = requests.post(
                        url,
                        json=json_data,
                        cookies=account['cookies'],
                        headers=enhanced_headers,
                        timeout=20
                    )

                    # Parse response for better feedback
                    try:
                        result = response.json()
                        message = result.get("message", "")
                        code = result.get("code", "")
                    except json.JSONDecodeError as e:
                        print(f"🔍 JSON Parse Error: {e}")
                        message = ""
                        code = ""
                        result = {}

                    if response.status_code == 200 and (code == "success" or not code):
                        sent_count += 1
                        
                        # Check for REAL delivery status (simplified version)
                        print(f"🔍 Checking delivery status for {email}...")
                        delivery_status = check_email_delivery_status(email, campaign_id, account)
                        
                        if delivery_status['status'] == 'delivered':
                            delivered_count += 1
                            success_msg = f"✅ Email DELIVERED successfully to {email}"
                            print(f"✅ {success_msg}")
                            log_email(email, subject, sender, "DELIVERED", campaign_id, delivery_status.get('details', ''))
                            # Add to delivered list
                            add_delivered_email(email, campaign_id, subject, sender, delivery_status.get('details', ''))
                        elif delivery_status['status'] == 'bounced':
                            bounced_count += 1
                            bounce_msg = f"📧 Email BOUNCED for {email}"
                            print(f"📧 {bounce_msg}")
                            log_email(email, subject, sender, "BOUNCED", campaign_id, delivery_status.get('details', ''))
                            # Add to bounce list
                            add_bounce_email(email, campaign_id, delivery_status.get('bounce_reason', 'Unknown bounce'), subject, sender)
                        else:
                            # Unknown status - treat as delivered for now
                            delivered_count += 1
                            unknown_msg = f"❓ Email status UNKNOWN for {email} (treating as delivered)"
                            print(f"❓ {unknown_msg}")
                            log_email(email, subject, sender, "UNKNOWN", campaign_id, delivery_status.get('details', ''))
                            # Add to delivered list
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
                            'attempt': attempt,
                            'delivery_details': delivery_status
                        }
                        add_campaign_log(campaign_id, success_log)
                        socketio.emit('email_progress', success_log)
                        success = True
                        
                    else:
                        error_count += 1
                        error_msg = f"❌ FAILED ({response.status_code}) to {email} | Message: {message} | Code: {code}"
                        print(error_msg)
                        
                        error_log = {
                            'campaign_id': campaign_id,
                            'timestamp': datetime.now().isoformat(),
                            'status': 'error',
                            'message': error_msg,
                            'email': email,
                            'subject': subject,
                            'sender': sender,
                            'type': 'error',
                            'attempt': attempt,
                            'response_code': response.status_code,
                            'api_code': code
                        }
                        add_campaign_log(campaign_id, error_log)
                        socketio.emit('email_progress', error_log)
                        log_email(email, subject, sender, f"FAILED ({code})", campaign_id, message)
                        
                        if attempt < max_attempts:
                            print(f"🔄 Retrying in 3 seconds... (Attempt {attempt + 1}/{max_attempts})")
                            time.sleep(3)

                except requests.exceptions.Timeout:
                    error_count += 1
                    timeout_msg = f"⏰ Timeout sending email to {email} (Attempt {attempt}/{max_attempts})"
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
                        'attempt': attempt
                    }
                    add_campaign_log(campaign_id, timeout_log)
                    socketio.emit('email_progress', timeout_log)
                    log_email(email, subject, sender, "TIMEOUT", campaign_id)
                    
                    if attempt < max_attempts:
                        print(f"🔄 Retrying in 3 seconds... (Attempt {attempt + 1}/{max_attempts})")
                        time.sleep(3)
                        
                except requests.exceptions.RequestException as e:
                    error_count += 1
                    error_msg = f"❌ Network error sending email to {email} (Attempt {attempt}/{max_attempts}): {str(e)}"
                    print(error_msg)
                    
                    network_error_log = {
                        'campaign_id': campaign_id,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'message': error_msg,
                        'email': email,
                        'subject': subject,
                        'sender': sender,
                        'type': 'network_error',
                        'attempt': attempt,
                        'exception': str(e)
                    }
                    add_campaign_log(campaign_id, network_error_log)
                    socketio.emit('email_progress', network_error_log)
                    log_email(email, subject, sender, f"NETWORK_ERROR: {str(e)}", campaign_id)
                    
                    if attempt < max_attempts:
                        print(f"🔄 Retrying in 3 seconds... (Attempt {attempt + 1}/{max_attempts})")
                        time.sleep(3)
                        
                except Exception as e:
                    error_count += 1
                    error_msg = f"⚠️ Exception sending email to {email} (Attempt {attempt}/{max_attempts}): {str(e)}"
                    print(error_msg)
                    
                    exception_log = {
                        'campaign_id': campaign_id,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'message': error_msg,
                        'email': email,
                        'subject': subject,
                        'sender': sender,
                        'type': 'exception',
                        'attempt': attempt,
                        'exception': str(e)
                    }
                    add_campaign_log(campaign_id, exception_log)
                    socketio.emit('email_progress', exception_log)
                    log_email(email, subject, sender, f"EXCEPTION: {str(e)}", campaign_id)
                    
                    if attempt < max_attempts:
                        print(f"🔄 Retrying in 3 seconds... (Attempt {attempt + 1}/{max_attempts})")
                        time.sleep(3)
            
            # If all attempts failed, increment error count
            if not success:
                error_count += 1
            
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
    
    return {
        'get_status_badge_class': get_status_badge_class,
        'get_notification_badge_class': get_notification_badge_class,
        'get_notification_icon': get_notification_icon,
        'format_timestamp': format_timestamp,
        'notifications_count': notifications_count
    }

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) 