"""Authentication service for user management."""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from app.models import User
from app.models.base import get_db
import config
from activity_logger import get_logger, get_client_ip, get_user_agent

# JWT Configuration
SECRET_KEY = config.settings.jwt_secret_key or config.settings.openai_api_key  # Use dedicated key if set
ALGORITHM = config.settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = config.settings.jwt_expire_minutes

# Make security optional to support cookie-based auth
security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, request: Optional[Request] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # Log token creation
    logger = get_logger()
    logger.log_auth_activity(
        auth_action="token_created",
        user_id=data.get("sub"),
        email=data.get("email"),
        status="success",
        metadata={"expires_at": expire.isoformat()},
        ip_address=get_client_ip(request) if request else None,
        user_agent=get_user_agent(request) if request else None
    )
    
    return encoded_jwt


def verify_token(token: str, request: Optional[Request] = None) -> dict:
    """Verify and decode JWT token."""
    logger = get_logger()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Log successful verification
        logger.log_auth_activity(
            auth_action="token_verified",
            user_id=payload.get("sub"),
            email=payload.get("email"),
            status="success",
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None
        )
        
        return payload
    except JWTError as e:
        # Log failed verification (no user_id available)
        logger.log_auth_activity(
            auth_action="token_verified",
            status="failure",
            error=str(e),
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    Supports both cookie-based (for React frontend) and Bearer token (for API clients) authentication.
    """
    logger = get_logger()
    
    # Try to get token from cookie first (for React frontend)
    token = request.cookies.get("access_token")
    
    # Fallback to Authorization header (for API clients)
    if not token and credentials:
        token = credentials.credentials
    
    if not token:
        logger.log_auth_activity(
            auth_action="user_retrieval",
            status="failure",
            error="No token provided (neither cookie nor Authorization header)",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_token(token, request=request)
    user_id: str = payload.get("sub")
    
    if user_id is None:
        logger.log_auth_activity(
            auth_action="user_retrieval",
            status="failure",
            error="User ID not found in token",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        logger.log_auth_activity(
            auth_action="user_retrieval",
            user_id=user_id,
            status="failure",
            error="User not found or inactive",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request)
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Log successful user retrieval (infrequent, just for tracking)
    # Commented out to avoid too much logging - uncomment if needed
    # logger.log_auth_activity(
    #     auth_action="user_retrieval",
    #     user_id=user_id,
    #     email=user.email,
    #     status="success",
    #     ip_address=get_client_ip(request),
    #     user_agent=get_user_agent(request)
    # )
    
    return user


def get_or_create_user(
    db: Session,
    email: str,
    name: Optional[str],
    provider: str,
    provider_id: str,
    picture: Optional[str] = None,
    request: Optional[Request] = None
) -> User:
    """Get existing user or create new user."""
    logger = get_logger()
    user = db.query(User).filter(User.email == email).first()
    
    if user:
        # Update user info
        user.name = name or user.name
        user.picture = picture or user.picture
        user.provider = provider
        user.provider_id = provider_id
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        # Log user update
        logger.log_auth_activity(
            auth_action="user_updated",
            user_id=user.id,
            email=email,
            provider=provider,
            status="success",
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None
        )
        
        return user
    
    # Create new user
    user_id = f"{provider}_{provider_id}"
    user = User(
        id=user_id,
        email=email,
        name=name,
        provider=provider,
        provider_id=provider_id,
        picture=picture,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Log user creation
    logger.log_auth_activity(
        auth_action="user_created",
        user_id=user.id,
        email=email,
        provider=provider,
        status="success",
        ip_address=get_client_ip(request) if request else None,
        user_agent=get_user_agent(request) if request else None
    )
    
    return user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()
