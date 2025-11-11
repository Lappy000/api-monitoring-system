"""User model for authentication and RBAC."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from app.database.base import Base


# Association table for many-to-many relationship between users and roles
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)


class Role(Base):
    """Role model for RBAC."""
    
    __tablename__ = "roles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    permissions: Mapped[dict] = mapped_column(SQLiteJSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
    
    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}', is_active={self.is_active})>"
    
    @property
    def permissions_list(self) -> list:
        """Get permissions as a list."""
        if not self.permissions or not isinstance(self.permissions, dict):
            return []
        return self.permissions.get('permissions', [])
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if role has specific permission.
        
        Args:
            permission: Permission string (e.g., 'endpoints:read', 'endpoints:write')
            
        Returns:
            bool: True if role has permission
        """
        if not self.permissions or not isinstance(self.permissions, dict):
            return False
        
        perms_list = self.permissions.get('permissions', [])
        
        # Check direct permission
        if permission in perms_list:
            return True
        
        # Check wildcard permissions (e.g., 'endpoints:*')
        resource, action = permission.split(':', 1) if ':' in permission else (permission, '')
        wildcard_perm = f"{resource}:*"
        if wildcard_perm in perms_list:
            return True
        
        return False


class User(Base):
    """User model for authentication."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', is_active={self.is_active})>"
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if user has specific permission (via roles or superuser status).
        
        Args:
            permission: Permission string (e.g., 'endpoints:read')
            
        Returns:
            bool: True if user has permission
        """
        # Superusers have all permissions
        if self.is_superuser:
            return True
        
        # Check if user is active
        if not self.is_active:
            return False
        
        # Check permissions from roles
        for role in self.roles:
            if role.is_active and role.has_permission(permission):
                return True
        
        return False
    
    def has_role(self, role_name: str) -> bool:
        """
        Check if user has specific role.
        
        Args:
            role_name: Role name to check
            
        Returns:
            bool: True if user has the role
        """
        if not self.is_active:
            return False
        
        return any(role.name == role_name and role.is_active for role in self.roles)
    
    def set_password(self, password: str) -> None:
        """
        Set user password (hashes it).
        
        Args:
            password: Plain text password
        """
        from app.core.auth import get_password_hash
        self.hashed_password = get_password_hash(password)
    
    def verify_password(self, password: str) -> bool:
        """
        Verify password against stored hash.
        
        Args:
            password: Plain text password to verify
            
        Returns:
            bool: True if password matches
        """
        from app.core.auth import verify_password
        return verify_password(password, self.hashed_password)
    
    def get_permissions(self) -> list:
        """
        Get all permissions for the user from their roles.
        
        Returns:
            list: List of permission strings
        """
        if self.is_superuser:
            return ["*"]
        
        if not self.is_active:
            return []
        
        permissions = []
        for role in self.roles:
            if role.is_active and role.permissions:
                role_perms = role.permissions.get('permissions', [])
                permissions.extend(role_perms)
        
        return list(set(permissions))  # Remove duplicates