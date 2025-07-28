#!/usr/bin/env python3
"""
Helper script to extract Zoho CRM credentials from browser
"""

import json
import re

def extract_from_curl(curl_command):
    """Extract cookies and headers from cURL command"""
    cookies = {}
    headers = {}
    
    # Extract cookies
    cookie_match = re.search(r"-H 'Cookie: ([^']+)'", curl_command)
    if cookie_match:
        cookie_string = cookie_match.group(1)
        for cookie in cookie_string.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                cookies[name.strip()] = value.strip()
    
    # Extract headers
    header_matches = re.findall(r"-H '([^:]+): ([^']+)'", curl_command)
    for name, value in header_matches:
        if name != 'Cookie':  # Skip cookie header
            headers[name] = value
    
    return cookies, headers

def format_for_web_interface(cookies, headers):
    """Format credentials for web interface"""
    print("=== COOKIES (JSON) ===")
    print(json.dumps(cookies, indent=2))
    print("\n=== HEADERS (JSON) ===")
    print(json.dumps(headers, indent=2))
    print("\n=== ORGANIZATION ID ===")
    org_id = headers.get('X-CRM-ORG', 'Not found')
    print(org_id)

def main():
    print("🔧 Zoho CRM Credentials Extractor")
    print("=" * 40)
    print()
    print("Instructions:")
    print("1. Log into Zoho CRM")
    print("2. Open Developer Tools (F12)")
    print("3. Go to Network tab")
    print("4. Make any action in Zoho CRM (click on a contact, etc.)")
    print("5. Right-click on any request → Copy → Copy as cURL")
    print("6. Paste the cURL command below")
    print()
    
    while True:
        print("Paste your cURL command (or 'quit' to exit):")
        curl_input = input().strip()
        
        if curl_input.lower() == 'quit':
            break
            
        if not curl_input:
            print("Please paste a cURL command")
            continue
            
        try:
            cookies, headers = extract_from_curl(curl_input)
            
            if not cookies and not headers:
                print("❌ No credentials found in cURL command")
                print("Make sure you copied the full cURL command")
                continue
                
            print("\n✅ Credentials extracted successfully!")
            format_for_web_interface(cookies, headers)
            
            print("\n" + "=" * 40)
            print("📋 Copy these values to your web interface:")
            print("1. Copy the COOKIES JSON to the Cookies field")
            print("2. Copy the HEADERS JSON to the Headers field")
            print("3. Copy the ORGANIZATION ID to the Organization ID field")
            print("=" * 40)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            print("Please check your cURL command format")

if __name__ == '__main__':
    main() 