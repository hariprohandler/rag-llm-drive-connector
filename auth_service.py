"""Authentication service for user management."""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import models
import config
from activity_logger import get_logger, get_client_ip, get_user_agent

# JWT Configuration
SECRET_KEY = config.settings.jwt_secret_key or config.settings.openai_api_key  # Use dedicated key if set
ALGORITHM = config.settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = config.settings.jwt_expire_minutes

security = HTTPBearer()


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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(models.get_db)
) -> models.User:
    """Get current authenticated user from JWT token."""
    logger = get_logger()
    token = credentials.credentials
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
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
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
) -> models.User:
    """Get existing user or create new user."""
    logger = get_logger()
    user = db.query(models.User).filter(models.User.email == email).first()
    
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
    user = models.User(
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


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Get user by email."""
    return db.query(models.User).filter(models.User.email == email).first()
