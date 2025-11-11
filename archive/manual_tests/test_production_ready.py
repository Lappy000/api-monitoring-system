#!/usr/bin/env python3
"""
Production Readiness Test for API Monitor
Simple, robust test with automatic server management
"""

import os
import sys
import time
import subprocess
import requests
import threading
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


def check_server_running(url):
    """Check if server is running and accessible."""
    try:
        response = requests.get(f"{url}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def start_server():
    """Start the API server in background."""
    print("Starting API server in background...")
    
    # Get current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Start server process
    process = subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8888",
        "--workers", "2",
        "--log-level", "info"
    ], cwd=current_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    print("Waiting for server to start (max 30 seconds)...")
    for i in range(30):
        if check_server_running("http://127.0.0.1:8888"):
            print("✅ Server started successfully!")
            return process
        time.sleep(1)
        print(f"  Waiting... {i+1}/30")
    
    print("❌ Server failed to start in time")
    return None


def make_request(session, url, headers, request_num):
    """Make a single request and track results."""
    global rate_limited_requests, successful_requests, failed_requests
    
    try:
        response = session.get(url, headers=headers, timeout=5)
        
        # Track request ID from response
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
    
    except requests.exceptions.RequestException as e:
        failed_requests += 1
        print(f"  Request {request_num}: Exception - {e}")
        return None


def test_rate_limiting(base_url, api_key, header_name):
    """Test rate limiting with burst requests."""
    print(f"\n[TEST] Rate Limiting...")
    print(f"  Making 120 requests to {base_url}/api/v1/endpoints")
    
    headers = {header_name: api_key}
    session = requests.Session()
    
    # Make 120 requests in quick succession
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
    
    if rate_limited_requests > 0:
        print("  ✅ Rate limiting is working!")
        return True
    else:
        print("  ⚠️  No rate limiting observed")
        return False


def test_request_id_tracking(base_url, api_key, header_name):
    """Test request ID tracking."""
    print(f"\n[TEST] Request ID Tracking...")
    
    headers = {header_name: api_key}
    
    try:
        response = requests.get(f"{base_url}/api/v1/endpoints", headers=headers, timeout=5)
        if response.status_code == 200:
            request_id = response.headers.get('X-Request-ID')
            if request_id:
                print(f"  ✅ Request ID present: {request_id}")
                return True
            else:
                print("  ❌ No request ID in response")
                return False
        else:
            print(f"  ❌ Request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return False


def test_health_endpoint(base_url):
    """Test health endpoint."""
    print(f"\n[TEST] Health Endpoint...")
    
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"  ✅ Health endpoint working")
            return True
        else:
            print(f"  ❌ Health endpoint returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return False


def generate_report():
    """Generate test report."""
    print("\n" + "="*80)
    print("PRODUCTION READINESS TEST REPORT")
    print("="*80)
    print(f"Generated at: {datetime.now().isoformat()}")
    
    print(f"\nRequest Statistics:")
    print(f"  - Total requests: {successful_requests + rate_limited_requests + failed_requests}")
    print(f"  - Successful: {successful_requests}")
    print(f"  - Rate limited: {rate_limited_requests}")
    print(f"  - Failed: {failed_requests}")
    
    print(f"\nRequest IDs tracked: {len(request_ids)}")
    
    print("\n" + "="*80)
    
    if rate_limited_requests > 0 and len(request_ids) > 0:
        print("✅ APPLICATION IS PRODUCTION READY!")
        print("   - Rate limiting working")
        print("   - Request ID tracking working")
        print("   - Server handling load correctly")
    else:
        print("⚠️  APPLICATION NEEDS ATTENTION")
        if rate_limited_requests == 0:
            print("   - Rate limiting not observed")
        if len(request_ids) == 0:
            print("   - Request ID tracking not working")
    
    print("="*80)


def main():
    """Main test function."""
    print("="*80)
    print("API MONITOR PRODUCTION READINESS TEST")
    print("="*80)
    
    # Load configuration
    config = load_config()
    api_key = config.api.auth.api_key or "test-key"
    header_name = config.api.auth.header_name
    base_url = "http://127.0.0.1:8888"
    
    print(f"\nConfiguration:")
    print(f"  - API URL: {base_url}")
    print(f"  - API Key: {api_key[:8]}...")
    print(f"  - Redis: {'Enabled' if config.redis.enabled else 'Disabled'}")
    print(f"  - Auth: {'Enabled' if config.api.auth.enabled else 'Disabled'}")
    
    # Check if server is already running
    print(f"\nChecking if server is running...")
    if check_server_running(base_url):
        print("✅ Server is already running")
        server_process = None
    else:
        print("⚠️  Server not running, starting it automatically...")
        server_process = start_server()
        if not server_process:
            print("❌ Failed to start server. Please start it manually:")
            print("   cd \"Middle python\"")
            print("   uvicorn app.main:app --host 127.0.0.1 --port 8888 --workers 2")
            return
    
    try:
        # Wait a bit more for server to be fully ready
        time.sleep(3)
        
        # Test 1: Health endpoint
        health_ok = test_health_endpoint(base_url)
        
        if not health_ok:
            print("\n❌ Health check failed. Cannot continue with tests.")
            return
        
        # Test 2: Request ID tracking
        request_id_ok = test_request_id_tracking(base_url, api_key, header_name)
        
        # Test 3: Rate limiting
        rate_limit_ok = test_rate_limiting(base_url, api_key, header_name)
        
        # Generate report
        generate_report()
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        tests = [
            ("Health Endpoint", health_ok),
            ("Request ID Tracking", request_id_ok),
            ("Rate Limiting", rate_limit_ok),
        ]
        
        passed = sum(1 for _, result in tests if result)
        total = len(tests)
        
        for test_name, result in tests:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name}: {status}")
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 APPLICATION IS PRODUCTION READY!")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed - review before production")
        
        print("="*80)
        
    finally:
        # Stop server if we started it
        if server_process:
            print("\nStopping server...")
            server_process.terminate()
            server_process.wait()
            print("Server stopped.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()