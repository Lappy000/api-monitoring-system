"""Comprehensive tests for authentication and authorization module - FIXED VERSION."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from fastapi import HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, ExpiredSignatureError

from app.core import auth
from app.models.user import User, Role
from app.config import Config


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_config():
    """Create properly structured mock config."""
    config = MagicMock()
    # Don't use spec=Config as it prevents nested attribute assignment
    config.api = MagicMock()
    config.api.auth = MagicMock()
    config.api.auth.enabled = True
    config.api.auth.header_name = "X-API-Key"
    config.api.auth.api_key = "test-secret-key"
    return config


@pytest.fixture
def mock_request(mock_config):
    """Create mock request with proper nested attributes."""
    request = MagicMock(spec=Request)
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.config = mock_config
    request.headers = MagicMock()
    return request


@pytest.fixture
def sample_user():
    """Create sample user."""
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    user.hashed_password = "hashed_password_here"
    user.is_active = True
    user.is_superuser = False
    user.last_login = None
    user.roles = []
    user.has_permission = MagicMock(return_value=True)
    return user


@pytest.fixture
def sample_role():
    """Create sample role."""
    role = MagicMock(spec=Role)
    role.id = 1
    role.name = "admin"
    role.description = "Administrator role"
    role.permissions = {"permissions": ["*"]}
    role.is_active = True
    return role


@pytest.fixture
def secret_key():
    """Create test secret key."""
    return "test-secret-key-for-jwt-tokens"


def test_verify_password_success():
    """Test successful password verification with mocked pwd_context."""
    password = "TestPass123!"
    hashed = "$2b$12$mockedhashvaluehere"
    
    with patch('app.core.auth.pwd_context.verify') as mock_verify:
        mock_verify.return_value = True
        assert auth.verify_password(password, hashed) is True
        
    with patch('app.core.auth.pwd_context.verify') as mock_verify:
        mock_verify.return_value = False
        assert auth.verify_password(password, "wronghash") is False


def test_get_password_hash():
    """Test password hashing with mocked pwd_context."""
    password = "SecurePass123!"
    expected_hash = "$2b$12$mockedhashvalue"
    
    with patch('app.core.auth.pwd_context.hash') as mock_hash:
        mock_hash.return_value = expected_hash
        hashed = auth.get_password_hash(password)
        
        assert hashed == expected_hash
        mock_hash.assert_called_once_with(password)


def test_validate_password_strength():
    """Test password strength validation."""
    # Valid passwords
    assert auth.validate_password_strength("SecurePass123!") is True
    assert auth.validate_password_strength("MyP@ssw0rd") is True
    
    # Invalid passwords
    assert auth.validate_password_strength("short") is False  # Too short
    assert auth.validate_password_strength("nouppercase123!") is False  # No uppercase
    assert auth.validate_password_strength("NOLOWERCASE123!") is False  # No lowercase
    assert auth.validate_password_strength("NoNumbers!") is False  # No numbers
    assert auth.validate_password_strength("NoSpecial123") is False  # No special chars


def test_create_access_token(secret_key):
    """Test JWT token creation."""
    data = {"sub": "testuser", "user_id": 1}
    token = auth.create_access_token(data, secret_key)
    
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_with_expiration(secret_key):
    """Test JWT token creation with custom expiration."""
    data = {"sub": "testuser"}
    expires = timedelta(minutes=60)
    token = auth.create_access_token(data, secret_key, expires)
    
    assert token is not None
    
    # Verify token can be decoded
    decoded = auth.verify_token(token, secret_key)
    assert decoded is not None
    assert decoded["sub"] == "testuser"


def test_verify_token_success(secret_key):
    """Test successful token verification."""
    data = {"sub": "testuser"}
    token = auth.create_access_token(data, secret_key)
    
    decoded = auth.verify_token(token, secret_key)
    assert decoded is not None
    assert decoded["sub"] == "testuser"


def test_verify_token_expired(secret_key):
    """Test token verification with expired token."""
    # Create token that's already expired
    data = {"sub": "testuser", "exp": datetime.utcnow() - timedelta(minutes=1)}
    
    # Mock jwt.encode to return a token string
    with patch('app.core.auth.jwt.encode') as mock_encode, \
         patch('app.core.auth.jwt.decode') as mock_decode:
        
        mock_encode.return_value = "expired.token.here"
        # jose raises ExpiredSignatureError for expired tokens
        mock_decode.side_effect = ExpiredSignatureError("Token expired")
        
        token = auth.create_access_token(data, secret_key)
        decoded = auth.verify_token(token, secret_key)
        
        # Should return None when token is expired
        assert decoded is None


def test_verify_token_invalid(secret_key):
    """Test token verification with invalid token."""
    decoded = auth.verify_token("invalid.token.here", secret_key)
    assert decoded is None


def test_verify_token_wrong_secret():
    """Test token verification with wrong secret key."""
    data = {"sub": "testuser"}
    token = auth.create_access_token(data, "correct-secret")
    
    decoded = auth.verify_token(token, "wrong-secret")
    assert decoded is None


@pytest.mark.asyncio
async def test_get_user_by_username(mock_db, sample_user):
    """Test getting user by username."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_db.execute.return_value = mock_result
    
    user = await auth.get_user_by_username(mock_db, "testuser")
    
    assert user is not None
    assert user.username == "testuser"
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_by_username_not_found(mock_db):
    """Test getting non-existent user by username."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    user = await auth.get_user_by_username(mock_db, "nonexistent")
    
    assert user is None


@pytest.mark.asyncio
async def test_get_user_by_email(mock_db, sample_user):
    """Test getting user by email."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_db.execute.return_value = mock_result
    
    user = await auth.get_user_by_email(mock_db, "test@example.com")
    
    assert user is not None
    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_authenticate_user_success(mock_db, sample_user):
    """Test successful user authentication."""
    with patch('app.core.auth.get_user_by_username') as mock_get_user, \
         patch('app.core.auth.verify_password') as mock_verify:
        
        mock_get_user.return_value = sample_user
        mock_verify.return_value = True
        
        user = await auth.authenticate_user(mock_db, "testuser", "correctpassword")
        
        assert user is not None
        assert user.username == "testuser"
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(mock_db, sample_user):
    """Test authentication with wrong password."""
    with patch('app.core.auth.get_user_by_username') as mock_get_user, \
         patch('app.core.auth.verify_password') as mock_verify:
        
        mock_get_user.return_value = sample_user
        mock_verify.return_value = False
        
        user = await auth.authenticate_user(mock_db, "testuser", "wrongpassword")
        
        assert user is None
        mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_user_inactive(mock_db, sample_user):
    """Test authentication with inactive user."""
    sample_user.is_active = False
    
    with patch('app.core.auth.get_user_by_username') as mock_get_user:
        mock_get_user.return_value = sample_user
        
        user = await auth.authenticate_user(mock_db, "testuser", "password")
        
        assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found(mock_db):
    """Test authentication with non-existent user."""
    with patch('app.core.auth.get_user_by_username') as mock_get_user:
        mock_get_user.return_value = None
        
        user = await auth.authenticate_user(mock_db, "nonexistent", "password")
        
        assert user is None


@pytest.mark.asyncio
async def test_verify_api_key_disabled(mock_request, mock_config):
    """Test API key verification when auth is disabled."""
    mock_config.api.auth.enabled = False
    
    result = await auth.verify_api_key(mock_request, mock_config)
    
    assert result is True


@pytest.mark.asyncio
async def test_verify_api_key_missing(mock_request, mock_config):
    """Test API key verification with missing key."""
    mock_request.headers.get = MagicMock(return_value=None)
    
    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_api_key(mock_request, mock_config)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "API key missing" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_api_key_invalid(mock_request, mock_config):
    """Test API key verification with invalid key."""
    mock_request.headers.get = MagicMock(return_value="wrong-key")
    
    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_api_key(mock_request, mock_config)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid API key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_api_key_success(mock_request, mock_config):
    """Test successful API key verification."""
    mock_request.headers.get = MagicMock(return_value="test-secret-key")
    
    result = await auth.verify_api_key(mock_request, mock_config)
    
    assert result is True


@pytest.mark.asyncio
async def test_create_user_success(mock_db):
    """Test successful user creation."""
    with patch('app.core.auth.get_user_by_username') as mock_get_user, \
         patch('app.core.auth.get_user_by_email') as mock_get_email, \
         patch('app.core.auth.get_password_hash') as mock_hash:
        
        mock_get_user.return_value = None
        mock_get_email.return_value = None
        mock_hash.return_value = "hashed_password"
        
        user = await auth.create_user(
            mock_db,
            username="newuser",
            email="new@example.com",
            password="SecurePass123!",
            full_name="New User",
            is_superuser=False
        )
        
        assert user is not None
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_user_duplicate_username(mock_db, sample_user):
    """Test user creation with duplicate username."""
    with patch('app.core.auth.get_user_by_username') as mock_get_user:
        mock_get_user.return_value = sample_user
        
        with pytest.raises(ValueError) as exc_info:
            await auth.create_user(
                mock_db,
                username="testuser",
                email="new@example.com",
                password="SecurePass123!"
            )
        
        assert "already exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_user_duplicate_email(mock_db, sample_user):
    """Test user creation with duplicate email."""
    with patch('app.core.auth.get_user_by_username') as mock_get_user, \
         patch('app.core.auth.get_user_by_email') as mock_get_email:
        
        mock_get_user.return_value = None
        mock_get_email.return_value = sample_user
        
        with pytest.raises(ValueError) as exc_info:
            await auth.create_user(
                mock_db,
                username="newuser",
                email="test@example.com",
                password="SecurePass123!"
            )
        
        assert "already exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_role_success(mock_db):
    """Test successful role creation."""
    # Mock db.execute to return a result with scalar_one_or_none
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    role = await auth.create_role(
        mock_db,
        name="operator",
        description="Operator role",
        permissions={"permissions": ["endpoints:read", "stats:read"]}
    )
    
    assert role is not None
    assert role.name == "operator"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_role_duplicate(mock_db, sample_role):
    """Test role creation with duplicate name."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_role
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(ValueError) as exc_info:
        await auth.create_role(
            mock_db,
            name="admin",
            description="Admin role"
        )
    
    assert "already exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_assign_role_to_user(mock_db, sample_user, sample_role):
    """Test assigning role to user."""
    sample_user.roles = []
    
    await auth.assign_role_to_user(mock_db, sample_user, sample_role)
    
    assert sample_role in sample_user.roles
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_assign_role_to_user_already_assigned(mock_db, sample_user, sample_role):
    """Test assigning role that user already has."""
    sample_user.roles = [sample_role]
    
    await auth.assign_role_to_user(mock_db, sample_user, sample_role)
    
    # Should not add duplicate - commit still called but role not added again
    assert sample_user.roles.count(sample_role) == 1
    # commit not called since role already in list
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_default_roles(mock_db):
    """Test initializing default roles."""
    # Mock all db.execute calls to return None (roles don't exist)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    with patch('app.core.auth.create_role') as mock_create_role:
        await auth.initialize_default_roles(mock_db)
        
        # Should create 3 default roles
        assert mock_create_role.call_count == 3
        
        # Verify role names
        role_names = [call.kwargs['name'] for call in mock_create_role.call_args_list]
        assert "admin" in role_names
        assert "operator" in role_names
        assert "viewer" in role_names


@pytest.mark.asyncio
async def test_initialize_default_roles_existing(mock_db, sample_role):
    """Test initializing default roles when they already exist."""
    # Mock all execute calls to return existing roles
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_role
    mock_db.execute.return_value = mock_result
    
    with patch('app.core.auth.create_role') as mock_create_role:
        await auth.initialize_default_roles(mock_db)
        
        # Should not create any roles
        mock_create_role.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_api_user_existing(mock_db, sample_user):
    """Test getting existing API user."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_db.execute.return_value = mock_result
    
    user = await auth.get_or_create_api_user(mock_db)
    
    assert user is not None
    assert user.username == "testuser"
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_api_user_new(mock_db):
    """Test creating new API user."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    user = await auth.get_or_create_api_user(mock_db)
    
    assert user is not None
    assert user.username == "api_key_user"
    assert user.is_superuser is True
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_require_permission_decorator():
    """Test permission requirement decorator."""
    # Create mock function
    async def mock_function(current_user=None):
        return "success"
    
    # Apply decorator
    decorated = auth.require_permission("endpoints:read")(mock_function)
    
    # Test with user having permission
    mock_user = MagicMock(spec=User)
    mock_user.has_permission.return_value = True
    
    result = await decorated(current_user=mock_user)
    assert result == "success"


@pytest.mark.asyncio
async def test_require_permission_no_permission():
    """Test permission decorator with user lacking permission."""
    async def mock_function(current_user=None):
        return "success"
    
    decorated = auth.require_permission("endpoints:read")(mock_function)
    
    mock_user = MagicMock(spec=User)
    mock_user.has_permission.return_value = False
    
    with pytest.raises(HTTPException) as exc_info:
        await decorated(current_user=mock_user)
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_permission_no_user():
    """Test permission decorator with no user."""
    async def mock_function(current_user=None):
        return "success"
    
    decorated = auth.require_permission("endpoints:read")(mock_function)
    
    with pytest.raises(HTTPException) as exc_info:
        await decorated(current_user=None)
    
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED