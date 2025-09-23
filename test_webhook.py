#!/usr/bin/env python3
"""
Simple test script to verify webhook functionality.
"""
import requests
import json
from datetime import datetime

def test_webhook(base_url='http://localhost:5000'):
    """Test the webhook endpoints."""
    print("Testing Webhook Endpoints")
    print("=" * 40)
    
    # Test health check
    print("\n1. Testing health check endpoint...")
    try:
        response = requests.get(f"{base_url}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test webhook endpoint
    print("\n2. Testing webhook endpoint...")
    test_payload = {
        "message": "Hello, this is a test message!",
        "user_id": "test_user_123",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        response = requests.post(
            f"{base_url}/webhook",
            json=test_payload,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test the test endpoint
    print("\n3. Testing test endpoint (GET)...")
    try:
        response = requests.get(f"{base_url}/webhook/test")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_webhook()