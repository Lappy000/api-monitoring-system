#!/usr/bin/env python3
"""
Test runner script for API Monitor.

Usage:
    python run_tests.py              # All tests with coverage
    python run_tests.py --quick      # Quick smoke tests only
    python run_tests.py --html       # Generate HTML coverage report
    python run_tests.py --module auth  # Test specific module
"""

import sys
import subprocess
from pathlib import Path


def run_command(cmd):
    """Execute command and return result."""
    print(f"\nExecuting: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, shell=True)
    return result.returncode


def main():
    """Main test runner function."""
    args = sys.argv[1:]
    
    project_root = Path(__file__).parent
    
    print("=" * 60)
    print("API Monitor Test Runner")
    print("=" * 60)
    
    if "--quick" in args:
        print("\nRunning quick smoke tests...")
        cmd = ["pytest", "tests/test_simple.py", "tests/test_health_api_comprehensive.py", "-v"]
        return run_command(cmd)
    
    elif "--html" in args:
        print("\nRunning tests with HTML coverage report...")
        cmd = ["pytest", "--cov=app", "--cov-report=html", "--cov-report=term", "-v"]
        code = run_command(cmd)
        if code == 0:
            print("\nHTML report generated: htmlcov/index.html")
        return code
    
    elif "--module" in args:
        try:
            idx = args.index("--module")
            module = args[idx + 1]
            print(f"\nRunning tests for module: {module}...")
            cmd = ["pytest", "tests/", "-k", f"{module}_comprehensive", "--cov=app", "-v"]
            return run_command(cmd)
        except (IndexError, ValueError):
            print("Error: Specify module name after --module")
            print("Example: python run_tests.py --module auth")
            return 1
    
    else:
        print("\nRunning all tests with coverage check...")
        print("This may take ~10 seconds...\n")
        cmd = ["pytest", "--cov=app", "--cov-report=term-missing", "-q"]
        code = run_command(cmd)
        
        if code == 0:
            print("\n" + "=" * 60)
            print("ALL TESTS PASSED")
            print("=" * 60)
            print("\nFor detailed HTML report: python run_tests.py --html")
        else:
            print("\n" + "=" * 60)
            print("SOME TESTS FAILED")
            print("=" * 60)
            print("\nFor details: pytest --cov=app -v --tb=short")
        
        return code


if __name__ == "__main__":
    sys.exit(main())