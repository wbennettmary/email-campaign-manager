# Email Campaign Manager - Upgrade Implementation Guide

## Quick Start: Critical Improvements (Phase 1)

This guide provides step-by-step instructions to implement the most critical improvements to make the application production-ready.

### Step 1: Database Migration (Priority: Critical)

#### 1.1 Install Required Dependencies

```bash
pip install flask-sqlalchemy flask-migrate python-dotenv
```

#### 1.2 Create Database Models

Create `models.py`:

```python
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    org_id = db.Column(db.String(50), nullable=False)
    cookies = db.Column(db.JSON)
    headers = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship
    campaigns = db.relationship('Campaign', backref='account', lazy=True)

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    template_id = db.Column(db.String(50), nullable=False)
    destinataires = db.Column(db.Text)
    subjects = db.Column(db.Text)
    froms = db.Column(db.Text)
    status = db.Column(db.String(20), default='ready')
    total_sent = db.Column(db.Integer, default=0)
    total_attempted = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    # Relationship
    logs = db.relationship('CampaignLog', backref='campaign', lazy=True, cascade='all, delete-orphan')

class CampaignLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20))  # success, error, info
    message = db.Column(db.Text)
    email = db.Column(db.String(200))
    subject = db.Column(db.String(200))
    sender = db.Column(db.String(200))
    log_type = db.Column(db.String(50))

class Notification(db.Model):
    id = db.Column(db.String(36), primary_key=True)  # UUID
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='info')
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    
    # Relationship
    campaign = db.relationship('Campaign', backref='notifications')
```

#### 1.3 Create Configuration File

Create `config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email settings
    EMAIL_DELAY = int(os.environ.get('EMAIL_DELAY', 2))
    EMAIL_BATCH_SIZE = int(os.environ.get('EMAIL_BATCH_SIZE', 10))
    EMAIL_BATCH_DELAY = int(os.environ.get('EMAIL_BATCH_DELAY', 5))
    
    # Zoho API settings
    ZOHO_API_BASE_URL = 'https://www.zohoapis.com/crm/v7'
    ZOHO_API_TIMEOUT = int(os.environ.get('ZOHO_API_TIMEOUT', 30))

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # Add production-specific settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 7200  # 2 hours

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
```

#### 1.4 Create Migration Script

Create `migrate_to_db.py`:

```python
#!/usr/bin/env python3
"""
Migration script to convert JSON data to SQLite database
"""

import json
import os
from datetime import datetime
from app import create_app, db
from app.models import User, Account, Campaign, CampaignLog, Notification

def migrate_json_to_db():
    """Migrate existing JSON data to database"""
    app = create_app()
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Migrate users
        if os.path.exists('users.json'):
            with open('users.json', 'r') as f:
                users_data = json.load(f)
            
            for user_data in users_data:
                user = User.query.filter_by(username=user_data['username']).first()
                if not user:
                    user = User(
                        username=user_data['username'],
                        email=user_data.get('email')
                    )
                    user.set_password('admin123')  # Default password
                    db.session.add(user)
                    print(f"✅ Migrated user: {user_data['username']}")
        
        # Migrate accounts
        if os.path.exists('accounts.json'):
            with open('accounts.json', 'r') as f:
                accounts_data = json.load(f)
            
            for account_data in accounts_data:
                account = Account.query.filter_by(id=account_data['id']).first()
                if not account:
                    account = Account(
                        id=account_data['id'],
                        name=account_data['name'],
                        org_id=account_data['org_id'],
                        cookies=account_data['cookies'],
                        headers=account_data['headers']
                    )
                    db.session.add(account)
                    print(f"✅ Migrated account: {account_data['name']}")
        
        # Migrate campaigns
        if os.path.exists('campaigns.json'):
            with open('campaigns.json', 'r') as f:
                campaigns_data = json.load(f)
            
            for campaign_data in campaigns_data:
                campaign = Campaign.query.filter_by(id=campaign_data['id']).first()
                if not campaign:
                    # Parse datetime strings
                    created_at = datetime.fromisoformat(campaign_data['created_at'])
                    started_at = None
                    completed_at = None
                    
                    if campaign_data.get('started_at'):
                        started_at = datetime.fromisoformat(campaign_data['started_at'])
                    if campaign_data.get('completed_at'):
                        completed_at = datetime.fromisoformat(campaign_data['completed_at'])
                    
                    campaign = Campaign(
                        id=campaign_data['id'],
                        name=campaign_data['name'],
                        account_id=campaign_data['account_id'],
                        template_id=campaign_data['template_id'],
                        destinataires=campaign_data['destinataires'],
                        subjects=campaign_data['subjects'],
                        froms=campaign_data['froms'],
                        status=campaign_data['status'],
                        total_sent=campaign_data.get('total_sent', 0),
                        total_attempted=campaign_data.get('total_attempted', 0),
                        created_at=created_at,
                        started_at=started_at,
                        completed_at=completed_at
                    )
                    db.session.add(campaign)
                    print(f"✅ Migrated campaign: {campaign_data['name']}")
        
        # Migrate campaign logs
        if os.path.exists('campaign_logs.json'):
            with open('campaign_logs.json', 'r') as f:
                logs_data = json.load(f)
            
            for campaign_id_str, logs in logs_data.items():
                campaign_id = int(campaign_id_str)
                for log_data in logs:
                    # Parse timestamp
                    timestamp = datetime.fromisoformat(log_data['timestamp'])
                    
                    log = CampaignLog(
                        campaign_id=campaign_id,
                        timestamp=timestamp,
                        status=log_data['status'],
                        message=log_data['message'],
                        email=log_data.get('email'),
                        subject=log_data.get('subject'),
                        sender=log_data.get('sender'),
                        log_type=log_data.get('type')
                    )
                    db.session.add(log)
                print(f"✅ Migrated {len(logs)} logs for campaign {campaign_id}")
        
        # Migrate notifications
        if os.path.exists('notifications.json'):
            with open('notifications.json', 'r') as f:
                notifications_data = json.load(f)
            
            for notification_data in notifications_data:
                # Parse timestamp
                timestamp = datetime.fromisoformat(notification_data['timestamp'])
                
                notification = Notification(
                    id=notification_data['id'],
                    message=notification_data['message'],
                    type=notification_data['type'],
                    campaign_id=notification_data.get('campaign_id'),
                    timestamp=timestamp,
                    read=notification_data.get('read', False)
                )
                db.session.add(notification)
            print(f"✅ Migrated {len(notifications_data)} notifications")
        
        # Commit all changes
        db.session.commit()
        print("\n🎉 Migration completed successfully!")
        print("You can now delete the old JSON files if everything looks good.")

if __name__ == '__main__':
    migrate_json_to_db()
```

### Step 2: Application Factory Pattern

#### 2.1 Create Application Factory

Update `app/__init__.py`:

```python
from flask import Flask
from flask_socketio import SocketIO
from flask_login import LoginManager
from config import config
from models import db

socketio = SocketIO()
login_manager = LoginManager()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.campaigns import campaigns_bp
    from app.routes.accounts import accounts_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(api_bp)
    
    # User loader
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    return app
```

#### 2.2 Create Blueprint Structure

Create `app/routes/auth.py`:

```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from app.models import User, db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('campaigns.dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
```

### Step 3: Enhanced Security

#### 3.1 Create Security Middleware

Create `app/utils/security.py`:

```python
from functools import wraps
from flask import request, jsonify, current_app
import time
from collections import defaultdict
import threading

# Rate limiting storage
rate_limit_storage = defaultdict(list)
rate_limit_lock = threading.Lock()

def rate_limit(limit=100, window=60):
    """Simple rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            current_time = time.time()
            
            with rate_limit_lock:
                # Clean old entries
                rate_limit_storage[client_ip] = [
                    timestamp for timestamp in rate_limit_storage[client_ip]
                    if current_time - timestamp < window
                ]
                
                # Check if limit exceeded
                if len(rate_limit_storage[client_ip]) >= limit:
                    return jsonify({'error': 'Rate limit exceeded'}), 429
                
                # Add current request
                rate_limit_storage[client_ip].append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_input(data, required_fields=None, optional_fields=None):
    """Validate input data"""
    if required_fields:
        for field in required_fields:
            if field not in data or not data[field]:
                return False, f"Missing required field: {field}"
    
    if optional_fields:
        for field in optional_fields:
            if field in data and not isinstance(data[field], str):
                return False, f"Invalid field type: {field}"
    
    return True, None

def sanitize_input(text):
    """Basic input sanitization"""
    if not text:
        return text
    
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    return text.strip()
```

#### 3.2 Update Requirements

Update `requirements.txt`:

```txt
Flask==2.3.3
Flask-SocketIO==5.3.6
Flask-Login==0.6.3
Flask-SQLAlchemy==3.0.5
Flask-Migrate==4.0.5
Werkzeug==2.3.7
requests==2.31.0
python-socketio==5.8.0
python-engineio==4.7.1
python-dotenv==1.0.0
SQLAlchemy==2.0.21
alembic==1.12.0
```

### Step 4: Environment Configuration

#### 4.1 Create Environment File

Create `.env`:

```env
# Flask Configuration
SECRET_KEY=your-super-secret-key-change-this-in-production
FLASK_ENV=development
FLASK_DEBUG=1

# Database Configuration
DATABASE_URL=sqlite:///app.db

# Email Settings
EMAIL_DELAY=2
EMAIL_BATCH_SIZE=10
EMAIL_BATCH_DELAY=5

# Zoho API Settings
ZOHO_API_TIMEOUT=30

# Security Settings
SESSION_LIFETIME=7200
RATE_LIMIT_PER_MINUTE=100
```

#### 4.2 Create Production Environment File

Create `.env.production`:

```env
# Flask Configuration
SECRET_KEY=your-production-secret-key
FLASK_ENV=production
FLASK_DEBUG=0

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost/email_campaign_manager

# Email Settings
EMAIL_DELAY=3
EMAIL_BATCH_SIZE=5
EMAIL_BATCH_DELAY=10

# Zoho API Settings
ZOHO_API_TIMEOUT=30

# Security Settings
SESSION_LIFETIME=3600
RATE_LIMIT_PER_MINUTE=50

# Redis Configuration (for production)
REDIS_URL=redis://localhost:6379/0
```

### Step 5: Implementation Steps

#### 5.1 Execute Migration

```bash
# 1. Install new dependencies
pip install -r requirements.txt

# 2. Create new application structure
mkdir -p app/routes app/models app/utils app/templates

# 3. Copy existing templates
cp templates/* app/templates/

# 4. Run database migration
python migrate_to_db.py

# 5. Test the application
python run.py
```

#### 5.2 Update Main Application File

Create `run.py`:

```python
from app import create_app, socketio
import os

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=app.config['DEBUG'])
```

### Step 6: Testing the Migration

#### 6.1 Create Test Script

Create `test_migration.py`:

```python
#!/usr/bin/env python3
"""
Test script to verify migration was successful
"""

from app import create_app, db
from app.models import User, Account, Campaign, CampaignLog, Notification

def test_migration():
    """Test that all data was migrated correctly"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Testing migration results...")
        
        # Test users
        users = User.query.all()
        print(f"✅ Users: {len(users)}")
        for user in users:
            print(f"   - {user.username}")
        
        # Test accounts
        accounts = Account.query.all()
        print(f"✅ Accounts: {len(accounts)}")
        for account in accounts:
            print(f"   - {account.name} (ID: {account.id})")
        
        # Test campaigns
        campaigns = Campaign.query.all()
        print(f"✅ Campaigns: {len(campaigns)}")
        for campaign in campaigns:
            print(f"   - {campaign.name} (Status: {campaign.status})")
        
        # Test logs
        logs = CampaignLog.query.all()
        print(f"✅ Campaign Logs: {len(logs)}")
        
        # Test notifications
        notifications = Notification.query.all()
        print(f"✅ Notifications: {len(notifications)}")
        
        print("\n🎉 Migration test completed!")

if __name__ == '__main__':
    test_migration()
```

## Next Steps After Migration

### 1. Backup Old Data
```bash
# Create backup of old JSON files
mkdir backup
cp *.json backup/
cp *.txt backup/
```

### 2. Update Templates
Update all templates to use the new database models instead of JSON data.

### 3. Implement Error Handling
Add proper error handling and logging throughout the application.

### 4. Add Testing
Create comprehensive tests for all functionality.

### 5. Security Hardening
Implement additional security measures like:
- CSRF protection
- Input validation
- SQL injection prevention
- XSS protection

## Production Deployment Checklist

- [ ] Change SECRET_KEY in production
- [ ] Use PostgreSQL instead of SQLite
- [ ] Set up Redis for caching
- [ ] Configure proper logging
- [ ] Set up monitoring
- [ ] Implement backup strategy
- [ ] Configure HTTPS
- [ ] Set up rate limiting
- [ ] Add health checks
- [ ] Configure environment variables

This implementation guide provides the foundation for a production-ready application. The database migration is the most critical improvement that will enable all other enhancements. 