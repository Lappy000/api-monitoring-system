# Contributing to API Monitoring System

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)

## 🤝 Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

### Our Standards

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- Basic knowledge of FastAPI and async Python

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/api-monitoring-system.git
   cd api-monitoring-system
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Set Up Pre-commit Hooks** (recommended)
   ```bash
   pip install pre-commit
   pre-commit install
   ```

5. **Verify Setup**
   ```bash
   # Quick verification (recommended)
   python verify_tests.py
   
   # Or run tests manually
   python run_tests.py --quick
   ```

6. **Start Development Server**
   ```bash
   uvicorn app.main:app --reload
   ```

## 💡 How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:
- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Relevant logs or screenshots

**Template:**
```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '....'
3. See error

**Expected behavior**
What you expected to happen.

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.11.4]
- Version: [e.g., 1.0.0]
```

### Suggesting Features

Feature requests are welcome! Please:
- Check if feature already exists or is planned
- Provide clear use case
- Explain expected behavior
- Consider implementation complexity

**Template:**
```markdown
**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution**
What you want to happen.

**Describe alternatives**
Alternative solutions you've considered.

**Additional context**
Any other context, mockups, or examples.
```

### Code Contributions

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

2. **Make Changes**
   - Write clean, documented code
   - Follow coding standards (see below)
   - Add tests for new functionality
   - Update documentation

3. **Test Your Changes**
   ```bash
   # Quick verification (recommended)
   python verify_tests.py
   
   # Run comprehensive tests only
   pytest tests/test_*_comprehensive.py --cov=app --cov-report=term
   
   # Run with HTML coverage report
   python run_tests.py --html
   
   # Test specific module
   python run_tests.py --module your_module
   
   # Type checking
   mypy app/
   
   # Linting
   flake8 app/ tests/
   
   # Formatting
   black app/ tests/
   ```
   
   **⚠️ IMPORTANT:** Don't run `pytest` without parameters! Use `python verify_tests.py` or `python run_tests.py` instead to avoid event loop conflicts with legacy tests.

4. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## 📝 Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line Length**: 100 characters (not 79)
- **Quotes**: Double quotes for strings
- **Imports**: Organized in this order:
  1. Standard library
  2. Third-party packages
  3. Local application imports

**Example:**
```python
"""Module docstring."""

import asyncio
from typing import Optional, List

from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.endpoint import Endpoint
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MyClass:
    """Class docstring."""
    
    def __init__(self, param: str) -> None:
        """Initialize with param."""
        self.param = param
    
    async def my_method(self) -> Optional[str]:
        """
        Method docstring.
        
        Returns:
            Optional result string
        """
        return self.param
```

### Type Hints

- **Always** use type hints for function parameters and return values
- Use `Optional[T]` for nullable types
- Use `List[T]`, `Dict[K, V]` from typing module

```python
from typing import Optional, List, Dict

async def get_endpoints(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False
) -> List[Endpoint]:
    """Get endpoints with pagination."""
    pass
```

### Async/Await

- Use `async def` for all I/O operations
- Use `await` for async calls
- Don't mix sync and async code

```python
# Good
async def fetch_data() -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Bad
def fetch_data() -> dict:
    # Sync code in async context
    response = requests.get(url)
    return response.json()
```

### Error Handling

- Use specific exceptions
- Provide context in error messages
- Log errors appropriately

```python
try:
    result = await risky_operation()
except ValueError as e:
    logger.error(
        "Invalid value in operation",
        extra={"error": str(e), "context": "important_context"}
    )
    raise
except Exception as e:
    logger.exception("Unexpected error in operation")
    raise
```

## 🧪 Testing Guidelines

### Current Test Coverage: **80%**

The project has comprehensive test coverage with **232 passing tests** and **0 failures**.

### Running Tests

**For Contributors (Recommended):**
```bash
# Quick verification - checks everything
python verify_tests.py

# Full test suite with HTML report
python run_tests.py --html

# Test specific module
python run_tests.py --module endpoints
python run_tests.py --module auth
```

**⚠️ IMPORTANT:** Never run `pytest` without parameters! This will run legacy tests that conflict with new comprehensive tests. Always use the scripts above or:

```bash
# Safe manual pytest command (comprehensive tests only)
pytest tests/test_*_comprehensive.py --cov=app --cov-report=html
```

### Test Structure

All new tests should go in `tests/test_*_comprehensive.py` files:

```
tests/
├── conftest.py                        # Shared fixtures
├── test_*_comprehensive.py            # ✅ NEW comprehensive tests (USE THESE)
│   ├── test_endpoints_comprehensive.py
│   ├── test_auth_comprehensive.py
│   └── test_notifications_comprehensive.py
└── test_*.py                          # ⚠️ Legacy tests (don't modify)
```

### Writing Tests

Create comprehensive test files following this pattern:

```python
"""Comprehensive tests for module_name."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.module import YourClass


@pytest.fixture
def mock_dependency():
    """Mock external dependency."""
    mock = AsyncMock()
    mock.method.return_value = "mocked_value"
    return mock


@pytest.mark.asyncio
async def test_feature_success(mock_dependency):
    """
    Test successful feature execution.
    
    Ensures:
    - Feature works correctly
    - Dependencies are called properly
    - Return value is correct
    """
    # Arrange
    instance = YourClass(mock_dependency)
    
    # Act
    result = await instance.feature()
    
    # Assert
    assert result == expected_value
    mock_dependency.method.assert_called_once()


@pytest.mark.asyncio
async def test_feature_error_handling(mock_dependency):
    """Test feature handles errors correctly."""
    # Arrange
    mock_dependency.method.side_effect = Exception("Test error")
    instance = YourClass(mock_dependency)
    
    # Act & Assert
    with pytest.raises(Exception, match="Test error"):
        await instance.feature()
```

### Test Coverage Requirements

- **New code:** Aim for **80%+ coverage**
- **Bug fixes:** Include regression tests
- **New features:** Must include comprehensive tests
- **Critical paths:** Require 100% coverage

```bash
# Check coverage
python run_tests.py --html
# Opens browser with detailed coverage report
```

### Test Documentation

For detailed testing information:
- **[README_TESTING.md](README_TESTING.md)** - Complete testing guide
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Quick start guide
- **[tests/README.md](tests/README.md)** - Technical details

### Writing Good Tests

```python
async def test_endpoint_creation():
    """
    Test creating a new endpoint.
    
    Ensures:
    - Endpoint is saved to database
    - All fields are correctly populated
    - Validation works as expected
    """
    # Arrange
    endpoint_data = {
        "name": "Test API",
        "url": "https://api.test.com",
        "method": "GET",
        "interval": 60
    }
    
    # Act
    result = await create_endpoint(endpoint_data)
    
    # Assert
    assert result.id is not None
    assert result.name == endpoint_data["name"]
    assert result.is_active is True
```

## 💬 Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting, missing semi-colons, etc
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding tests
- `chore`: Updating build tasks, package manager configs, etc

### Examples

```bash
feat(health-checker): add circuit breaker pattern

Implement circuit breaker to prevent cascading failures
when monitoring endpoints are consistently failing.

Closes #123

---

fix(api): correct status code validation

Fixed validation to allow status codes 100-599 instead of
200-599.

Fixes #456

---

docs(readme): update installation instructions

Added Docker installation steps and improved clarity
of setup process.
```

## 🔄 Pull Request Process

### Before Submitting

- [ ] Tests pass locally
- [ ] Code is formatted (`black app/ tests/`)
- [ ] Linting passes (`flake8 app/ tests/`)
- [ ] Type hints are correct (`mypy app/`)
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated (for significant changes)

### PR Title

Use conventional commit format:
```
feat(scope): add new feature
fix(scope): resolve bug
docs: update documentation
```

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally
- [ ] Coverage maintained/improved

## Screenshots (if applicable)

## Related Issues
Closes #issue_number
```

### Review Process

1. **Automated Checks**: CI/CD must pass
2. **Code Review**: At least one approval required
3. **Merge**: Squash and merge preferred
4. **Delete Branch**: After merge

## 🎯 Areas for Contribution

### High Priority

- [ ] Increase test coverage to 80%+
- [ ] Add more notification channels
- [ ] Implement WebSocket for real-time updates
- [ ] Add Prometheus metrics export

### Medium Priority

- [ ] Create web dashboard
- [ ] Add more examples
- [ ] Improve documentation
- [ ] Add load testing suite

### Good First Issues

Look for issues labeled `good-first-issue` or `help-wanted`

## 📚 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Pytest Async](https://pytest-asyncio.readthedocs.io/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

## ❓ Questions?

- Open an issue with label `question`
- Check existing issues and discussions
- Read the documentation

## 🙏 Thank You!

Your contributions make this project better for everyone!

---

**Happy Coding!** 🚀