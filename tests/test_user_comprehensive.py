"""Comprehensive tests for User and Role models."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models.user import User, Role


@pytest.fixture
def sample_role():
    """Create sample role."""
    role = Role(
        id=1,
        name="admin",
        description="Administrator role",
        permissions={"permissions": ["*"]},
        is_active=True
    )
    return role


@pytest.fixture
def sample_user():
    """Create sample user."""
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashed_password_here",
        is_active=True,
        is_superuser=False
    )
    return user


def test_role_creation():
    """Test role model creation."""
    role = Role(
        name="operator",
        description="Operator role",
        permissions={"permissions": ["endpoints:read", "endpoints:write"]},
        is_active=True
    )
    
    assert role.name == "operator"
    assert role.description == "Operator role"
    assert role.is_active is True


def test_role_repr(sample_role):
    """Test role string representation."""
    repr_str = repr(sample_role)
    
    assert "Role" in repr_str
    assert "id=1" in repr_str
    assert "name='admin'" in repr_str
    assert "is_active=True" in repr_str


def test_role_permissions_list(sample_role):
    """Test getting permissions as list."""
    perms = sample_role.permissions_list
    
    assert isinstance(perms, list)
    assert "*" in perms


def test_role_permissions_list_empty():
    """Test permissions list when none defined."""
    role = Role(name="empty", permissions={})
    
    assert role.permissions_list == []


def test_role_permissions_list_none():
    """Test permissions list when permissions is None."""
    role = Role(name="none", permissions=None)
    
    assert role.permissions_list == []


def test_role_has_permission_direct(sample_role):
    """Test direct permission check."""
    sample_role.permissions = {"permissions": ["endpoints:read", "endpoints:write"]}
    
    assert sample_role.has_permission("endpoints:read") is True
    assert sample_role.has_permission("endpoints:write") is True
    assert sample_role.has_permission("endpoints:delete") is False


def test_role_has_permission_wildcard():
    """Test wildcard permission check."""
    role = Role(
        name="admin",
        permissions={"permissions": ["endpoints:*", "stats:read"]}
    )
    
    # Wildcard permissions
    assert role.has_permission("endpoints:read") is True
    assert role.has_permission("endpoints:write") is True
    assert role.has_permission("endpoints:delete") is True
    
    # Non-wildcard permission
    assert role.has_permission("stats:read") is True
    assert role.has_permission("stats:write") is False


def test_role_has_permission_no_permissions():
    """Test permission check when no permissions defined."""
    role = Role(name="empty", permissions=None)
    
    assert role.has_permission("any:permission") is False


def test_role_has_permission_invalid_format():
    """Test permission check with invalid permissions format."""
    role = Role(name="invalid", permissions="not a dict")
    
    assert role.has_permission("any:permission") is False


def test_user_creation():
    """Test user model creation."""
    user = User(
        username="newuser",
        email="new@example.com",
        full_name="New User",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False
    )
    
    assert user.username == "newuser"
    assert user.email == "new@example.com"
    assert user.is_active is True
    assert user.is_superuser is False


def test_user_repr(sample_user):
    """Test user string representation."""
    repr_str = repr(sample_user)
    
    assert "User" in repr_str
    assert "id=1" in repr_str
    assert "username='testuser'" in repr_str
    assert "is_active=True" in repr_str


def test_user_has_permission_superuser(sample_user):
    """Test that superusers have all permissions."""
    sample_user.is_superuser = True
    
    assert sample_user.has_permission("any:permission") is True
    assert sample_user.has_permission("another:permission") is True


def test_user_has_permission_inactive(sample_user):
    """Test that inactive users have no permissions."""
    sample_user.is_active = False
    
    assert sample_user.has_permission("any:permission") is False


def test_user_has_permission_via_role(sample_user, sample_role):
    """Test user permissions through roles."""
    sample_user.roles = [sample_role]
    sample_role.permissions = {"permissions": ["endpoints:read"]}
    
    assert sample_user.has_permission("endpoints:read") is True
    assert sample_user.has_permission("endpoints:write") is False


def test_user_has_permission_multiple_roles(sample_user):
    """Test user permissions with multiple roles."""
    role1 = Role(
        name="reader",
        permissions={"permissions": ["endpoints:read"]},
        is_active=True
    )
    
    role2 = Role(
        name="writer",
        permissions={"permissions": ["endpoints:write"]},
        is_active=True
    )
    
    sample_user.roles = [role1, role2]
    
    assert sample_user.has_permission("endpoints:read") is True
    assert sample_user.has_permission("endpoints:write") is True


def test_user_has_permission_inactive_role(sample_user):
    """Test that inactive roles don't grant permissions."""
    role = Role(
        name="inactive",
        permissions={"permissions": ["endpoints:read"]},
        is_active=False
    )
    
    sample_user.roles = [role]
    
    assert sample_user.has_permission("endpoints:read") is False


def test_user_has_role_success(sample_user, sample_role):
    """Test checking if user has specific role."""
    sample_user.roles = [sample_role]
    
    assert sample_user.has_role("admin") is True
    assert sample_user.has_role("operator") is False


def test_user_has_role_inactive_user(sample_user, sample_role):
    """Test has_role returns False for inactive users."""
    sample_user.is_active = False
    sample_user.roles = [sample_role]
    
    assert sample_user.has_role("admin") is False


def test_user_has_role_inactive_role(sample_user):
    """Test has_role returns False for inactive roles."""
    role = Role(name="inactive", is_active=False)
    sample_user.roles = [role]
    
    assert sample_user.has_role("inactive") is False


def test_user_set_password(sample_user):
    """Test setting user password."""
    # Patch where it's used, not where it's defined
    with patch('app.core.auth.get_password_hash') as mock_hash:
        mock_hash.return_value = "new_hashed_password"
        
        sample_user.set_password("newpassword123")
        
        assert sample_user.hashed_password == "new_hashed_password"
        mock_hash.assert_called_once_with("newpassword123")


def test_user_verify_password_success(sample_user):
    """Test successful password verification."""
    # Patch where it's used, not where it's defined
    with patch('app.core.auth.verify_password') as mock_verify:
        mock_verify.return_value = True
        
        result = sample_user.verify_password("correctpassword")
        
        assert result is True
        mock_verify.assert_called_once_with("correctpassword", sample_user.hashed_password)


def test_user_verify_password_failure(sample_user):
    """Test failed password verification."""
    # Patch where it's used, not where it's defined
    with patch('app.core.auth.verify_password') as mock_verify:
        mock_verify.return_value = False
        
        result = sample_user.verify_password("wrongpassword")
        
        assert result is False


def test_user_get_permissions_superuser(sample_user):
    """Test getting permissions for superuser."""
    sample_user.is_superuser = True
    
    perms = sample_user.get_permissions()
    
    assert perms == ["*"]


def test_user_get_permissions_inactive(sample_user):
    """Test getting permissions for inactive user."""
    sample_user.is_active = False
    
    perms = sample_user.get_permissions()
    
    assert perms == []


def test_user_get_permissions_from_roles(sample_user):
    """Test getting permissions from user roles."""
    role1 = Role(
        name="reader",
        permissions={"permissions": ["endpoints:read", "stats:read"]},
        is_active=True
    )
    
    role2 = Role(
        name="writer",
        permissions={"permissions": ["endpoints:write", "endpoints:read"]},
        is_active=True
    )
    
    sample_user.roles = [role1, role2]
    
    perms = sample_user.get_permissions()
    
    # Should have unique permissions
    assert "endpoints:read" in perms
    assert "endpoints:write" in perms
    assert "stats:read" in perms
    # No duplicates
    assert isinstance(perms, list)
    assert len(set(perms)) == len(perms)


def test_user_get_permissions_inactive_roles(sample_user):
    """Test that inactive roles don't contribute permissions."""
    active_role = Role(
        name="active",
        permissions={"permissions": ["endpoints:read"]},
        is_active=True
    )
    
    inactive_role = Role(
        name="inactive",
        permissions={"permissions": ["endpoints:write"]},
        is_active=False
    )
    
    sample_user.roles = [active_role, inactive_role]
    
    perms = sample_user.get_permissions()
    
    assert "endpoints:read" in perms
    assert "endpoints:write" not in perms


def test_user_get_permissions_empty_roles(sample_user):
    """Test getting permissions when user has no roles."""
    sample_user.roles = []
    
    perms = sample_user.get_permissions()
    
    assert perms == []


def test_role_has_permission_with_colon_format():
    """Test permission check with resource:action format."""
    role = Role(
        name="custom",
        permissions={"permissions": ["endpoints:read"]}
    )
    
    assert role.has_permission("endpoints:read") is True
    assert role.has_permission("endpoints:write") is False


def test_role_has_permission_no_colon():
    """Test permission check without colon separator."""
    role = Role(
        name="custom",
        permissions={"permissions": ["admin"]}
    )
    
    # Permission without colon
    assert role.has_permission("admin") is True
    assert role.has_permission("user") is False