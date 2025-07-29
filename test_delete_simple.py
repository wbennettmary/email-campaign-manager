#!/usr/bin/env python3
"""
Simple test for bounce delete functionality
"""

import requests
import json

def test_delete_individual():
    """Test deleting the specific email that was failing"""
    print("🧪 Testing individual bounce deletion...")
    
    # Test the exact case that was failing
    campaign_id = 11
    email = "salsssaqzdsdapp@gmail.com"
    
    url = f"http://localhost:5000/api/delete/bounce/{campaign_id}/{email}"
    
    try:
        response = requests.delete(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

def test_delete_all():
    """Test deleting all bounces"""
    print("\n🧪 Testing delete all bounces...")
    
    url = "http://localhost:5000/api/delete/bounces/all"
    
    try:
        response = requests.delete(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_delete_individual()
    test_delete_all()