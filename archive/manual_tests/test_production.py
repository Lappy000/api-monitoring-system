#!/usr/bin/env python3
"""
Production Readiness Test for API Monitor
Simple test that works with a manually started server
"""

import os
import sys
import time
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.config import load_config

# Global variables
request_ids = set()
rate_limited_requests = 0
successful_requests = 0
failed_requests = 0


def check_server(url):
    """Check if server is running."""
    try:
        response = requests.get(f"{url}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def make_request(session, url, headers, request_num):
    """Make a single request."""
    global rate_limited_requests, successful_requests, failed_requests
    
    try:
        response = session.get(url, headers=headers, timeout=5)
        
        # Track request ID
        request_id = response.headers.get('X-Request-ID')
        if request_id:
            request_ids.add(request_id)
        
        if response.status_code == 429:
            rate_limited_requests += 1
            print(f"  Request {request_num}: Rate limited (429)")
        elif response.status_code == 200:
            successful_requests += 1
            if request_num % 20 == 0:
                print(f"  Request {request_num}: Success (200)")
        else:
            failed_requests += 1
            print(f"  Request {request_num}: Failed ({response.status_code})")
        
        return response.status_code
    
    except Exception as e:
        failed_requests += 1
        print(f"  Request {request_num}: Error - {e}")
        return None


def test_rate_limiting(base_url, api_key, header_name):
    """Test rate limiting."""
    print(f"\n[TEST] Rate Limiting (120 requests)...")
    
    headers = {header_name: api_key}
    session = requests.Session()
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(make_request, session, f"{base_url}/api/v1/endpoints", headers, i)
            for i in range(120)
        ]
        
        for future in as_completed(futures):
            future.result()
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n  Results:")
    print(f"    - Duration: {duration:.2f}s")
    print(f"    - Rate: {120/duration:.2f} req/s")
    print(f"    - Successful: {successful_requests}")
    print(f"    - Rate limited: {rate_limited_requests}")
    print(f"    - Failed: {failed_requests}")
    
    return rate_limited_requests > 0


def test_request_id(base_url, api_key, header_name):
    """Test request ID tracking."""
    print(f"\n[TEST] Request ID Tracking...")
    
    headers = {header_name: api_key}
    
    try:
        response = requests.get(f"{base_url}/api/v1/endpoints", headers=headers, timeout=5)
        if response.status_code == 200:
            request_id = response.headers.get('X-Request-ID')
            if request_id:
                print(f"  ✅ Request ID: {request_id}")
                return True
            else:
                print("  ❌ No request ID")
                return False
        else:
            print(f"  ❌ Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_health(base_url):
    """Test health endpoint."""
    print(f"\n[TEST] Health Check...")
    
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"  ✅ Health endpoint working")
            return True
        else:
            print(f"  ❌ Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Main function."""
    print("="*80)
    print("API MONITOR - PRODUCTION READINESS TEST")
    print("="*80)
    
    # Load config
    config = load_config()
    api_key = config.api.auth.api_key or "test-key"
    header_name = config.api.auth.header_name
    base_url = "http://127.0.0.1:8888"
    
    print(f"\nConfiguration:")
    print(f"  URL: {base_url}")
    print(f"  API Key: {api_key[:8]}...")
    print(f"  Redis: {'Enabled' if config.redis.enabled else 'Disabled'}")
    print(f"  Auth: {'Enabled' if config.api.auth.enabled else 'Disabled'}")
    
    # Check server
    print(f"\nChecking server status...")
    for i in range(15):
        if check_server(base_url):
            print("✅ Server is running!")
            break
        print(f"  Waiting for server... {15-i}s remaining")
        time.sleep(1)
    else:
        print("\n❌ Server not responding")
        print("\nPlease start the server:")
        print("  cd \"Middle python\"")
        print("  uvicorn app.main:app --host 127.0.0.1 --port 8888 --workers 2")
        print("\nThen run: python test_production.py")
        return
    
    # Wait for server to be ready
    print("Waiting for server to be fully ready...")
    time.sleep(3)
    
    # Run tests
    print("\n" + "="*80)
    print("RUNNING TESTS")
    print("="*80)
    
    tests = []
    tests.append(("Health Check", test_health(base_url)))
    tests.append(("Request ID", test_request_id(base_url, api_key, header_name)))
    tests.append(("Rate Limiting", test_rate_limiting(base_url, api_key, header_name)))
    
    # Report
    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    print(f"\nScore: {passed}/{total}")
    
    print("\n" + "="*80)
    print("REQUEST STATISTICS")
    print("="*80)
    print(f"  Total: {successful_requests + rate_limited_requests + failed_requests}")
    print(f"  Successful: {successful_requests}")
    print(f"  Rate Limited: {rate_limited_requests}")
    print(f"  Failed: {failed_requests}")
    print(f"  Request IDs: {len(request_ids)}")
    
    if passed == total:
        print("\n🎉 PRODUCTION READY!")
    else:
        print(f"\n⚠️  {total-passed} test(s) failed")
    
    print("="*80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest stopped.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()