#!/usr/bin/env python3
"""
Zoho OAuth2 Setup Script
This script helps you set up OAuth2 authentication for Zoho CRM APIs
Following the exact steps provided for proper email delivery feedback
"""

import sys
import os
from zoho_oauth_integration import setup_zoho_oauth_flow, complete_oauth_setup, get_zoho_oauth_client

def print_setup_instructions():
    """Print detailed setup instructions"""
    print("🔐 ZOHO OAUTH2 SETUP - STEP BY STEP")
    print("=" * 60)
    print()
    print("📋 STEP 1: Create OAuth Client in Zoho Developer Console")
    print("   1. Go to https://api-console.zoho.com/")
    print("   2. Click 'Add Client' → choose 'Server-based'")
    print("   3. Give it a Name (e.g., 'Email Campaign Manager')")
    print("   4. Homepage URL: http://localhost")
    print("   5. Redirect URI: http://localhost:8000/callback")
    print("   6. You'll get a Client ID and Client Secret")
    print()
    print("📋 STEP 2: Required Scopes")
    print("   Make sure your OAuth client has these scopes:")
    print("   - ZohoCRM.modules.emails.CREATE")
    print("   - ZohoCRM.modules.emails.READ")
    print("   - ZohoCRM.settings.email_templates.ALL")
    print("   - ZohoCRM.settings.functions.ALL")
    print()
    print("📋 STEP 3: Run this script with your credentials")
    print("   python setup_zoho_oauth.py YOUR_CLIENT_ID YOUR_CLIENT_SECRET")
    print()

def main():
    """Main setup function"""
    print_setup_instructions()
    
    # Check if credentials provided as arguments
    if len(sys.argv) >= 3:
        client_id = sys.argv[1]
        client_secret = sys.argv[2]
        redirect_uri = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:8000/callback"
        
        print(f"🚀 Starting OAuth2 setup with provided credentials...")
        print(f"   Client ID: {client_id[:10]}...")
        print(f"   Redirect URI: {redirect_uri}")
        print()
        
        # Start OAuth2 flow
        client = setup_zoho_oauth_flow(client_id, client_secret, redirect_uri)
        
        if client:
            print("\n✅ OAuth2 client initialized successfully!")
            print("\n📋 Next steps:")
            print("   1. Complete the authorization in your browser")
            print("   2. Get the authorization code from the redirect URL")
            print("   3. Run: complete_oauth_setup('YOUR_AUTH_CODE')")
            print()
            
            # Check if we have valid tokens
            if client.get_valid_access_token():
                print("🎉 OAuth2 setup is complete! You can now use Zoho APIs.")
                test_oauth_connection(client)
            else:
                print("⏳ Waiting for authorization code...")
        
    else:
        print("❌ Please provide your OAuth2 credentials:")
        print("   python setup_zoho_oauth.py YOUR_CLIENT_ID YOUR_CLIENT_SECRET")
        print()
        print("💡 If you don't have credentials yet, follow Step 1 above first.")

def test_oauth_connection(client):
    """Test the OAuth2 connection"""
    print("\n🧪 Testing OAuth2 connection...")
    
    try:
        # Test getting email status
        result = client.get_email_status(limit=5)
        
        if result.get('success'):
            print("✅ OAuth2 connection successful!")
            print(f"   Retrieved {result.get('total_count', 0)} emails")
            
            # Test bounce reports
            bounce_reports = client.get_bounce_reports(days=7)
            print(f"   Found {len(bounce_reports)} bounce reports in last 7 days")
            
            print("\n🎉 Zoho OAuth2 integration is working perfectly!")
            print("   You now have access to real email delivery feedback!")
            
        else:
            print("❌ OAuth2 connection test failed:")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing OAuth2 connection: {str(e)}")

def interactive_setup():
    """Interactive setup mode"""
    print("\n🔐 INTERACTIVE OAUTH2 SETUP")
    print("=" * 40)
    
    client_id = input("Enter your Client ID: ").strip()
    client_secret = input("Enter your Client Secret: ").strip()
    redirect_uri = input("Enter Redirect URI (default: http://localhost:8000/callback): ").strip()
    
    if not redirect_uri:
        redirect_uri = "http://localhost:8000/callback"
    
    if not client_id or not client_secret:
        print("❌ Client ID and Client Secret are required!")
        return
    
    # Start OAuth2 flow
    client = setup_zoho_oauth_flow(client_id, client_secret, redirect_uri)
    
    if client:
        print("\n✅ OAuth2 client initialized!")
        print("\n📋 Complete the authorization in your browser, then:")
        
        auth_code = input("Enter the authorization code: ").strip()
        
        if auth_code:
            if complete_oauth_setup(auth_code):
                print("🎉 OAuth2 setup completed successfully!")
                test_oauth_connection(client)
            else:
                print("❌ OAuth2 setup failed. Please check your credentials and try again.")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments provided, run interactive mode
        interactive_setup()
    else:
        # Arguments provided, run main setup
        main() 