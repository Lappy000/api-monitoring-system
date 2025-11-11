@echo off
REM Test runner script for API Monitor (Windows)

echo ========================================
echo    API Monitor Test Suite
echo ========================================
echo.

if "%1"=="quick" (
    echo Running quick smoke tests...
    pytest tests/test_simple.py tests/test_health_api_comprehensive.py -v
    goto end
)

if "%1"=="html" (
    echo Running tests with HTML coverage report...
    pytest --cov=app --cov-report=html --cov-report=term -v
    echo.
    echo HTML report generated: htmlcov\index.html
    start htmlcov\index.html
    goto end
)

if "%1"=="" (
    echo Running all tests with coverage...
    pytest --cov=app --cov-report=term-missing -q
    goto end
)

echo Unknown option: %1
echo.
echo Usage:
echo   test.bat          - Run all tests with coverage
echo   test.bat quick    - Run quick smoke tests
echo   test.bat html     - Generate HTML coverage report
echo.

:end