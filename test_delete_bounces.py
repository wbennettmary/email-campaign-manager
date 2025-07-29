#!/usr/bin/env python3
"""
Test script for bounce delete functionality
"""

import requests
import json

# Test configuration
BASE_URL = "http://localhost:5000"

def test_delete_individual_bounce():
    """Test deleting a single bounced email"""
    print("🧪 Testing individual bounce deletion...")
    
    # Test data
    campaign_id = 1
    email = "test1@example.com"
    
    url = f"{BASE_URL}/api/delete/bounce/{campaign_id}/{email}"
    
    try:
        response = requests.delete(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            if data.get('success'):
                print("✅ Individual bounce deletion successful!")
            else:
                print(f"❌ Individual bounce deletion failed: {data.get('message')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing individual bounce deletion: {e}")

def test_delete_campaign_bounces():
    """Test deleting all bounces for a campaign"""
    print("\n🧪 Testing campaign bounce deletion...")
    
    campaign_id = 1
    url = f"{BASE_URL}/api/delete/bounces/{campaign_id}"
    
    try:
        response = requests.delete(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            if data.get('success'):
                print("✅ Campaign bounce deletion successful!")
            else:
                print(f"❌ Campaign bounce deletion failed: {data.get('message')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing campaign bounce deletion: {e}")

def test_delete_all_bounces():
    """Test deleting all bounces"""
    print("\n🧪 Testing all bounces deletion...")
    
    url = f"{BASE_URL}/api/delete/bounces/all"
    
    try:
        response = requests.delete(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            if data.get('success'):
                print("✅ All bounces deletion successful!")
            else:
                print(f"❌ All bounces deletion failed: {data.get('message')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing all bounces deletion: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting bounce delete functionality tests...")
    print("=" * 50)
    
    # Test individual deletion
    test_delete_individual_bounce()
    
    # Test campaign deletion
    test_delete_campaign_bounces()
    
    # Test all deletion
    test_delete_all_bounces()
    
    print("\n" + "=" * 50)
    print("🏁 Tests completed!")

if __name__ == "__main__":
    main()