"""Authentication and authorization utilities for RBAC system."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.user import User, Role
from app.config import Config
from app.database.session import get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Password hashing context - using bcrypt with compatibility settings
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",  # Use bcrypt 2b variant for better compatibility
    bcrypt__truncate_error=False  # Don't error on passwords > 72 bytes, truncate instead
)

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security scheme for FastAPI docs
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        bool: True if password matches
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Generate a password hash.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> bool:
    """
    Validate password strength.
    
    Requirements:
    - At least 8 characters
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one number
    - Contains at least one special character
    
    Args:
        password: Password to validate
        
    Returns:
        bool: True if password meets strength requirements
    """
    if len(password) < 8:
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    
    return has_upper and has_lower and has_digit and has_special


def create_access_token(data: Dict[str, Any], secret_key: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in token
        secret_key: Secret key for encoding
        expires_delta: Token expiration time
        
    Returns:
        str: JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str, secret_key: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token
        secret_key: Secret key for decoding
        
    Returns:
        Optional[Dict[str, Any]]: Decoded token data or None if invalid
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """
    Get user by username.
    
    Args:
        db: Database session
        username: Username to find
        
    Returns:
        Optional[User]: User object or None
    """
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    Get user by email.
    
    Args:
        db: Database session
        email: Email to find
        
    Returns:
        Optional[User]: User object or None
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password.
    
    Args:
        db: Database session
        username: Username
        password: Password
        
    Returns:
        Optional[User]: User object if authentication successful, None otherwise
    """
    user = await get_user_by_username(db, username)
    
    if not user:
        return None
    
    if not user.is_active:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    return user


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None
) -> User:
    """
    Get current authenticated user from JWT token.
    
    Args:
        db: Database session
        credentials: HTTP authorization credentials
        request: FastAPI request (to get config from app.state)
        
    Returns:
        User: Authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Get secret key from app state if request provided
    secret_key = None
    if request and hasattr(request.app.state, 'config'):
        secret_key = request.app.state.config.api.auth.api_key
    
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error"
        )
    
    try:
        payload = verify_token(credentials.credentials, secret_key)
        if payload is None:
            raise credentials_exception
        
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get current active user.
    
    Args:
        current_user: Current user from get_current_user
        
    Returns:
        User: Active user
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get current admin user.
    
    Args:
        current_user: Current user from get_current_user
        
    Returns:
        User: Admin user
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


async def verify_api_key(request: Request, config: Config) -> bool:
    """
    Verify API key from request headers.
    
    Args:
        request: FastAPI request object
        config: Application configuration
        
    Returns:
        bool: True if API key is valid
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not config.api.auth.enabled:
        return True  # Auth disabled, allow all requests
    
    api_key = request.headers.get(config.api.auth.header_name)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key missing",
            headers={"WWW-Authenticate": f"ApiKey {config.api.auth.header_name}"},
        )
    
    if api_key != config.api.auth.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": f"ApiKey {config.api.auth.header_name}"},
        )
    
    return True


async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    is_superuser: bool = False
) -> User:
    """
    Create a new user.
    
    Args:
        db: Database session
        username: Username
        email: Email address
        password: Plain text password
        full_name: Full name
        is_superuser: Whether user is superuser
        
    Returns:
        User: Created user object
    """
    # Check if user already exists
    existing = await get_user_by_username(db, username)
    if existing:
        raise ValueError(f"User with username '{username}' already exists")
    
    existing_email = await get_user_by_email(db, email)
    if existing_email:
        raise ValueError(f"User with email '{email}' already exists")
    
    hashed_password = get_password_hash(password)
    
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=hashed_password,
        is_superuser=is_superuser,
        is_active=True
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


async def create_role(
    db: AsyncSession,
    name: str,
    description: Optional[str] = None,
    permissions: Optional[Dict[str, Any]] = None
) -> Role:
    """
    Create a new role.
    
    Args:
        db: Database session
        name: Role name
        description: Role description
        permissions: Permission dictionary
        
    Returns:
        Role: Created role object
    """
    # Check if role already exists
    existing = await db.execute(select(Role).where(Role.name == name))
    if existing.scalar_one_or_none():
        raise ValueError(f"Role with name '{name}' already exists")
    
    role = Role(
        name=name,
        description=description,
        permissions=permissions or {"permissions": []}
    )
    
    db.add(role)
    await db.commit()
    await db.refresh(role)
    
    return role


async def assign_role_to_user(db: AsyncSession, user: User, role: Role) -> None:
    """
    Assign a role to a user.
    
    Args:
        db: Database session
        user: User object
        role: Role object
    """
    if role not in user.roles:
        user.roles.append(role)
        await db.commit()


async def initialize_default_roles(db: AsyncSession) -> None:
    """
    Initialize default roles with permissions.
    
    Args:
        db: Database session
    """
    # Check if roles already exist
    admin_role = await db.execute(select(Role).where(Role.name == "admin"))
    if not admin_role.scalar_one_or_none():
        # Admin role - all permissions
        await create_role(
            db,
            name="admin",
            description="Administrator with full system access",
            permissions={
                "permissions": [
                    "*"
                ]
            }
        )
    
    operator_role = await db.execute(select(Role).where(Role.name == "operator"))
    if not operator_role.scalar_one_or_none():
        # Operator role - endpoint management and monitoring
        await create_role(
            db,
            name="operator",
            description="Operator with endpoint management and monitoring access",
            permissions={
                "permissions": [
                    "endpoints:read",
                    "endpoints:write",
                    "endpoints:delete",
                    "stats:read",
                    "checks:run"
                ]
            }
        )
    
    viewer_role = await db.execute(select(Role).where(Role.name == "viewer"))
    if not viewer_role.scalar_one_or_none():
        # Viewer role - read-only access
        await create_role(
            db,
            name="viewer",
            description="Viewer with read-only access to monitoring data",
            permissions={
                "permissions": [
                    "endpoints:read",
                    "stats:read"
                ]
            }
        )


def require_permission(permission: str):
    """
    Decorator to require specific permission for endpoint access.
    
    Args:
        permission: Required permission string
        
    Returns:
        Decorator function
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get current user from request (would need to be passed in)
            user = kwargs.get("current_user")
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not user.has_permission(permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# API Key authentication dependency
async def api_key_auth(request: Request, config: Config) -> bool:
    """
    API Key authentication dependency for FastAPI.
    
    Args:
        request: FastAPI request object
        config: Application configuration
        
    Returns:
        bool: True if authenticated
        
    Raises:
        HTTPException: If authentication fails
    """
    return await verify_api_key(request, config)


# Combined auth dependency that checks both JWT and API key
async def require_auth(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """
    Combined authentication that checks for JWT token or API key.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        User: Authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    # Get config from app state
    if not hasattr(request.app.state, 'config'):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration not loaded"
        )
    
    config = request.app.state.config
    
    # Try API key first
    try:
        await verify_api_key(request, config)
        # For API key auth, get the actual user from database
        # Use get_or_create pattern to avoid race conditions
        return await get_or_create_api_user(db)
    except HTTPException:
        # If API key fails, try JWT
        pass
    
    # Try JWT token
    try:
        credentials = await security(request)
        return await get_current_user(db, credentials, request)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_or_create_api_user(db: AsyncSession) -> User:
    """
    Get or create the API key user in a thread-safe manner.
    
    Args:
        db: Database session
        
    Returns:
        User: API key user
    """
    # Try to get existing user first
    result = await db.execute(
        select(User).where(User.username == "api_key_user")
    )
    api_user = result.scalar_one_or_none()
    
    if api_user:
        return api_user
    
    # User doesn't exist, try to create it
    # Use a savepoint to handle potential race conditions
    try:
        api_user = User(
            username="api_key_user",
            email="system@localhost",
            hashed_password="",  # No password for API key user
            is_superuser=True,
            is_active=True,
            full_name="API Key System User"
        )
        db.add(api_user)
        await db.commit()
        await db.refresh(api_user)
        logger.info("Created API key user")
        return api_user
    except Exception as e:
        # If creation failed (likely due to race condition), try to get again
        await db.rollback()
        result = await db.execute(
            select(User).where(User.username == "api_key_user")
        )
        api_user = result.scalar_one_or_none()
        if api_user:
            return api_user
        raise e