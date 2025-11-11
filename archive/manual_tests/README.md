# Archived Manual Test Files

**Date Archived:** 2025-11-10

## Purpose

These files are **old manual test scripts** that were cluttering the root directory. They have been archived here to maintain project cleanliness while preserving historical testing approaches.

## Archived Files

- `test_all_scenarios.py` - Old comprehensive test scenarios
- `test_final.py` - Legacy final test script
- `test_final_simple.py` - Simplified version of final tests
- `test_production.py` - Old production test
- `test_production_final.py` - Another production test variant
- `test_production_ready.py` - Production readiness checks
- `test_scenarios_simple.py` - Simple scenario tests
- `production_load_simulation.py` - Load testing simulation
- `production_simulation.py` - Production environment simulation
- `production_test_manual.py` - Manual production testing script
- `quick_test.py` - Quick sanity checks
- `run_production_test.py` - Production test runner

## ⚠️ IMPORTANT

**DO NOT USE THESE FILES FOR TESTING!**

The **official, maintained test suite** is located in:
```
tests/
├── conftest.py
├── test_api_endpoints.py
├── test_auth_integration.py
├── test_edge_cases.py
├── test_functionality.py
├── test_integration.py
├── test_notification_integration.py
└── test_simple.py
```

## Running Proper Tests

To run the official test suite:

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_integration.py -v
```

## Why These Were Archived

1. **Duplication** - 12 different test files with overlapping functionality
2. **Inconsistency** - No clear naming convention or organization
3. **Confusion** - Made it unclear which tests were official
4. **Import Errors** - Some used `get_config()` which doesn't exist

## Historical Value

These files are kept for reference only. They may contain useful test scenarios or approaches that could be incorporated into the official test suite after proper review and refactoring.