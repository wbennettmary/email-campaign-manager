#!/usr/bin/env python3
"""
Simple SMTP Test Script
Tests the SMTP configuration and email sending functionality
"""

import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl

def load_smtp_config():
    """Load SMTP configuration from file"""
    try:
        with open('smtp_config.json', 'r') as f:
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

def test_smtp_connection(config):
    """Test SMTP connection"""
    print(f"Testing SMTP connection to {config['server']}:{config['port']}")
    
    try:
        if config['use_tls']:
            server = smtplib.SMTP(config['server'], config['port'])
            server.starttls(context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(config['server'], config['port'])
        
        server.login(config['username'], config['password'])
        print("✅ SMTP connection successful!")
        server.quit()
        return True
        
    except Exception as e:
        print(f"❌ SMTP connection failed: {str(e)}")
        return False

def test_email_sending(config, test_email):
    """Test sending a test email"""
    print(f"Sending test email to {test_email}")
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{config['from_name']} <{config['from_email']}>"
        msg['To'] = test_email
        msg['Subject'] = 'SMTP Test - Email Campaign Manager'
        
        html_body = '''
        <html>
        <body>
            <h2>SMTP Configuration Test</h2>
            <p>This is a test email to verify your SMTP configuration is working correctly.</p>
            <p>If you received this email, your SMTP settings are properly configured.</p>
            <p>Best regards,<br>Email Campaign Manager</p>
        </body>
        </html>
        '''
        
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        if config['use_tls']:
            server = smtplib.SMTP(config['server'], config['port'])
            server.starttls(context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(config['server'], config['port'])
        
        server.login(config['username'], config['password'])
        server.send_message(msg)
        server.quit()
        
        print("✅ Test email sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send test email: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🔧 SMTP Configuration Test")
    print("=" * 40)
    
    # Load configuration
    config = load_smtp_config()
    
    print(f"Configuration loaded:")
    print(f"  Enabled: {config['enabled']}")
    print(f"  Server: {config['server']}:{config['port']}")
    print(f"  Username: {config['username']}")
    print(f"  From: {config['from_name']} <{config['from_email']}>")
    print(f"  TLS: {config['use_tls']}")
    print()
    
    if not config['enabled']:
        print("⚠️  SMTP is disabled in configuration")
        print("   Set 'enabled': true in smtp_config.json to enable")
        return
    
    # Test connection
    if test_smtp_connection(config):
        # Test email sending
        test_email = input("Enter test email address: ").strip()
        if test_email:
            test_email_sending(config, test_email)
        else:
            print("No test email provided, skipping email test")
    else:
        print("❌ Cannot test email sending - connection failed")

if __name__ == "__main__":
    main()