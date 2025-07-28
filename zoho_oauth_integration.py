#!/usr/bin/env python3
"""
Zoho CRM OAuth2 Authentication Integration
This module implements proper OAuth2 authentication for Zoho CRM APIs
Following the official Zoho OAuth2 flow for email delivery feedback
"""

import requests
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ZohoOAuth2Client:
    """
    Zoho CRM OAuth2 Client for proper API authentication
    """
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8000/callback"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        # OAuth2 endpoints
        self.auth_url = "https://accounts.zoho.com/oauth/v2/auth"
        self.token_url = "https://accounts.zoho.com/oauth/v2/token"
        
        # API endpoints
        self.api_base = "https://www.zohoapis.com"
        
    def get_authorization_url(self, scopes: List[str] = None) -> str:
        """
        Generate the authorization URL for OAuth2 flow
        
        Args:
            scopes: List of Zoho CRM scopes to request
            
        Returns:
            Authorization URL to open in browser
        """
        if scopes is None:
            scopes = [
                "ZohoCRM.modules.emails.CREATE",
                "ZohoCRM.modules.emails.READ",
                "ZohoCRM.settings.email_templates.ALL",
                "ZohoCRM.settings.functions.ALL"
            ]
        
        params = {
            'scope': ','.join(scopes),
            'client_id': self.client_id,
            'response_type': 'code',
            'access_type': 'offline',
            'redirect_uri': self.redirect_uri
        }
        
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        logger.info(f"🔗 Authorization URL generated: {auth_url}")
        return auth_url
    
    def open_authorization_url(self, scopes: List[str] = None) -> str:
        """
        Open the authorization URL in browser and return the URL for manual access
        
        Args:
            scopes: List of Zoho CRM scopes to request
            
        Returns:
            Authorization URL (in case browser doesn't open)
        """
        auth_url = self.get_authorization_url(scopes)
        
        try:
            webbrowser.open(auth_url)
            logger.info("🌐 Opened authorization URL in browser")
        except Exception as e:
            logger.warning(f"⚠️ Could not open browser automatically: {str(e)}")
        
        return auth_url
    
    def exchange_code_for_tokens(self, grant_code: str) -> Dict:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            grant_code: Authorization code from OAuth2 callback
            
        Returns:
            Dict with access_token, refresh_token, and expires_in
        """
        try:
            data = {
                'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri,
                'code': grant_code
            }
            
            response = requests.post(self.token_url, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info("✅ Successfully exchanged code for tokens")
                logger.info(f"   Access token expires at: {self.token_expires_at}")
                
                return token_data
            else:
                logger.error(f"❌ Failed to exchange code for tokens: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Error exchanging code for tokens: {str(e)}")
            return {}
    
    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using the refresh token
        
        Returns:
            bool: True if refresh successful
        """
        if not self.refresh_token:
            logger.error("❌ No refresh token available")
            return False
        
        try:
            data = {
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token
            }
            
            response = requests.post(self.token_url, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                
                self.access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info("✅ Successfully refreshed access token")
                logger.info(f"   New token expires at: {self.token_expires_at}")
                
                return True
            else:
                logger.error(f"❌ Failed to refresh access token: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error refreshing access token: {str(e)}")
            return False
    
    def get_valid_access_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary
        
        Returns:
            Valid access token or None
        """
        if not self.access_token:
            logger.error("❌ No access token available")
            return None
        
        # Check if token is expired (with 5 minute buffer)
        if self.token_expires_at and datetime.now() + timedelta(minutes=5) >= self.token_expires_at:
            logger.info("🔄 Access token expired, refreshing...")
            if not self.refresh_access_token():
                return None
        
        return self.access_token
    
    def get_authorized_headers(self) -> Dict:
        """
        Get headers with valid OAuth2 token for API requests
        
        Returns:
            Dict with Authorization header
        """
        access_token = self.get_valid_access_token()
        if not access_token:
            return {}
        
        return {
            'Authorization': f'Zoho-oauthtoken {access_token}',
            'Content-Type': 'application/json'
        }
    
    def send_email(self, from_email: str, to_emails: List[str], subject: str, content: str) -> Dict:
        """
        Send email via Zoho CRM API with OAuth2 authentication
        
        Args:
            from_email: Sender email address
            to_emails: List of recipient email addresses
            subject: Email subject
            content: Email content (HTML)
            
        Returns:
            Dict with API response
        """
        headers = self.get_authorized_headers()
        if not headers:
            return {'error': 'No valid access token'}
        
        try:
            url = f"{self.api_base}/crm/v5/Emails"
            
            data = {
                "data": [{
                    "from": from_email,
                    "to": to_emails,
                    "subject": subject,
                    "content": content
                }]
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 201:
                result = response.json()
                logger.info("✅ Email sent successfully via Zoho API")
                return result
            else:
                logger.error(f"❌ Failed to send email: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return {'error': f'HTTP {response.status_code}', 'response': response.text}
                
        except Exception as e:
            logger.error(f"❌ Error sending email: {str(e)}")
            return {'error': str(e)}
    
    def get_email_status(self, email_id: str = None, limit: int = 100) -> Dict:
        """
        Get email delivery status and feedback from Zoho CRM API
        
        Args:
            email_id: Specific email ID to check (optional)
            limit: Number of emails to retrieve
            
        Returns:
            Dict with email status information
        """
        headers = self.get_authorized_headers()
        if not headers:
            return {'error': 'No valid access token'}
        
        try:
            if email_id:
                url = f"{self.api_base}/crm/v5/Emails/{email_id}"
            else:
                url = f"{self.api_base}/crm/v5/Emails?per_page={limit}"
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Retrieved email status from Zoho API")
                
                # Process email data
                emails = data.get('data', [])
                processed_emails = []
                
                for email in emails:
                    processed_email = {
                        'id': email.get('id'),
                        'to': email.get('to'),
                        'subject': email.get('subject'),
                        'status': email.get('status'),
                        'delivery_time': email.get('delivery_time'),
                        'open_count': email.get('open_count', 0),
                        'last_open_time': email.get('last_open_time'),
                        'bounce_count': email.get('bounce_count', 0),
                        'bounce_reason': email.get('bounce_reason'),
                        'created_time': email.get('created_time')
                    }
                    processed_emails.append(processed_email)
                
                return {
                    'success': True,
                    'emails': processed_emails,
                    'total_count': len(processed_emails)
                }
            else:
                logger.error(f"❌ Failed to get email status: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return {'error': f'HTTP {response.status_code}', 'response': response.text}
                
        except Exception as e:
            logger.error(f"❌ Error getting email status: {str(e)}")
            return {'error': str(e)}
    
    def get_bounce_reports(self, days: int = 7) -> List[Dict]:
        """
        Get bounce reports from Zoho CRM API
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of bounce reports
        """
        headers = self.get_authorized_headers()
        if not headers:
            return []
        
        try:
            # Get emails from the last N days
            url = f"{self.api_base}/crm/v5/Emails?per_page=200"
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                emails = data.get('data', [])
                
                # Filter for bounced emails
                bounce_reports = []
                cutoff_date = datetime.now() - timedelta(days=days)
                
                for email in emails:
                    # Check if email has bounced
                    if email.get('bounce_count', 0) > 0:
                        created_time = email.get('created_time')
                        if created_time:
                            try:
                                email_date = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                                if email_date >= cutoff_date:
                                    bounce_reports.append({
                                        'email': email.get('to'),
                                        'reason': email.get('bounce_reason', 'Unknown bounce'),
                                        'type': 'hard' if email.get('bounce_count', 0) > 0 else 'soft',
                                        'timestamp': created_time,
                                        'source': 'zoho_oauth_api',
                                        'email_id': email.get('id')
                                    })
                            except:
                                # If date parsing fails, include anyway
                                bounce_reports.append({
                                    'email': email.get('to'),
                                    'reason': email.get('bounce_reason', 'Unknown bounce'),
                                    'type': 'hard' if email.get('bounce_count', 0) > 0 else 'soft',
                                    'timestamp': created_time,
                                    'source': 'zoho_oauth_api',
                                    'email_id': email.get('id')
                                })
                
                logger.info(f"📊 Retrieved {len(bounce_reports)} bounce reports from Zoho OAuth API")
                return bounce_reports
            else:
                logger.error(f"❌ Failed to get bounce reports: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error getting bounce reports: {str(e)}")
            return []
    
    def save_tokens(self, filepath: str = "zoho_tokens.json"):
        """
        Save tokens to file for persistence
        
        Args:
            filepath: Path to save tokens
        """
        try:
            token_data = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'token_expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri,
                'saved_at': datetime.now().isoformat()
            }
            
            with open(filepath, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            logger.info(f"✅ Tokens saved to {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Error saving tokens: {str(e)}")
    
    def load_tokens(self, filepath: str = "zoho_tokens.json") -> bool:
        """
        Load tokens from file
        
        Args:
            filepath: Path to load tokens from
            
        Returns:
            bool: True if tokens loaded successfully
        """
        try:
            with open(filepath, 'r') as f:
                token_data = json.load(f)
            
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            
            expires_at = token_data.get('token_expires_at')
            if expires_at:
                self.token_expires_at = datetime.fromisoformat(expires_at)
            
            logger.info(f"✅ Tokens loaded from {filepath}")
            return True
            
        except FileNotFoundError:
            logger.info(f"📄 No token file found at {filepath}")
            return False
        except Exception as e:
            logger.error(f"❌ Error loading tokens: {str(e)}")
            return False

# Global OAuth2 client instance
zoho_oauth_client = None

def initialize_zoho_oauth_client(client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8000/callback"):
    """Initialize the global Zoho OAuth2 client"""
    global zoho_oauth_client
    zoho_oauth_client = ZohoOAuth2Client(client_id, client_secret, redirect_uri)
    logger.info("✅ Zoho OAuth2 client initialized")
    return zoho_oauth_client

def get_zoho_oauth_client() -> Optional[ZohoOAuth2Client]:
    """Get the global Zoho OAuth2 client instance"""
    return zoho_oauth_client

def setup_zoho_oauth_flow(client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8000/callback"):
    """
    Complete OAuth2 setup flow
    
    Args:
        client_id: OAuth2 client ID from Zoho Developer Console
        client_secret: OAuth2 client secret from Zoho Developer Console
        redirect_uri: Redirect URI for OAuth2 flow
    """
    global zoho_oauth_client
    
    # Initialize client
    zoho_oauth_client = ZohoOAuth2Client(client_id, client_secret, redirect_uri)
    
    # Try to load existing tokens
    if zoho_oauth_client.load_tokens():
        logger.info("✅ Loaded existing tokens")
        return zoho_oauth_client
    
    # Generate authorization URL
    auth_url = zoho_oauth_client.open_authorization_url()
    
    print("\n🔐 Zoho OAuth2 Setup Instructions:")
    print("=" * 50)
    print("1. The authorization URL has been opened in your browser")
    print("2. Sign in to your Zoho account when prompted")
    print("3. Grant the requested permissions")
    print("4. You'll be redirected to a URL with a 'code' parameter")
    print("5. Copy the 'code' parameter value")
    print(f"\n🔗 Authorization URL: {auth_url}")
    print("\n📋 After getting the authorization code, call:")
    print("   complete_oauth_setup(grant_code)")
    
    return zoho_oauth_client

def complete_oauth_setup(grant_code: str):
    """
    Complete OAuth2 setup with authorization code
    
    Args:
        grant_code: Authorization code from OAuth2 callback
    """
    global zoho_oauth_client
    
    if not zoho_oauth_client:
        logger.error("❌ OAuth2 client not initialized")
        return False
    
    # Exchange code for tokens
    token_data = zoho_oauth_client.exchange_code_for_tokens(grant_code)
    
    if token_data:
        # Save tokens for future use
        zoho_oauth_client.save_tokens()
        logger.info("✅ OAuth2 setup completed successfully")
        return True
    else:
        logger.error("❌ OAuth2 setup failed")
        return False 