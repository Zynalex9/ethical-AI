"""
Authentication router with register, login, refresh, and profile endpoints.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.user import User
from app.models.audit_log import AuditLog, AuditAction, ResourceType
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token
)
from app.services.auth_service import (
    hash_password,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_id,
    get_user_by_email
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """
    Register a new user account.
    
    Args:
        user_data: User registration data (email, password, name)
        request: FastAPI request object for IP logging
        db: Database session
        
    Returns:
        Created user object
        
    Raises:
        HTTPException: 400 if email already exists
    """
    # Check if email already exists
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        name=user_data.name
    )
    db.add(user)
    await db.flush()
    
    # Create audit log
    audit_log = AuditLog(
        user_id=user.id,
        action=AuditAction.USER_REGISTER,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        details={"email": user.email, "name": user.name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.add(audit_log)
    
    return user


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Token:
    """
    Authenticate user and return JWT tokens.
    
    Args:
        user_data: Login credentials (email, password)
        request: FastAPI request object for IP logging
        db: Database session
        
    Returns:
        JWT access and refresh tokens
        
    Raises:
        HTTPException: 401 if credentials are invalid
    """
    user = await authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated"
        )
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    
    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    # Create audit log
    audit_log = AuditLog(
        user_id=user.id,
        action=AuditAction.USER_LOGIN,
        resource_type=ResourceType.USER,
        resource_id=user.id,
        details={"email": user.email},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db.add(audit_log)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token_str: str,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Token:
    """
    Refresh access token using a valid refresh token.
    
    Args:
        refresh_token_str: The refresh token
        db: Database session
        
    Returns:
        New JWT access and refresh tokens
        
    Raises:
        HTTPException: 401 if refresh token is invalid
    """
    # Decode refresh token
    payload = decode_token(refresh_token_str)
    if payload is None or payload.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Get user
    from uuid import UUID
    try:
        user_id = UUID(payload.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated"
        )
    
    # Create new tokens
    access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token(user.id)
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: CurrentUser
) -> User:
    """
    Get the current authenticated user's profile.
    
    Args:
        current_user: The authenticated user (injected by dependency)
        
    Returns:
        User profile information
    """
    return current_user
