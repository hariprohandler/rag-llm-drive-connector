"""Authentication service for user management."""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from app.models import User
from app.models.base import get_db
import config
from app.services.activity_logger import get_logger, get_client_ip, get_user_agent
from app.services.email_encryption import encrypt_email, decrypt_email, hash_email_for_lookup

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
    """
    Get existing user or create new user. Emails are encrypted before storage.
    
    Behavior:
    1. First check if user exists by ID (provider_provider_id) - most reliable
    2. If found, verify provider matches and update user info, then return existing user
    3. If not found by ID, check by email_hash (deterministic)
    4. If not found by hash, check by plain email (for migration)
    5. Only create new user if no existing user is found
    """
    logger = get_logger()
    
    # Encrypt email for storage and create hash for lookups
    encrypted_email = encrypt_email(email)
    email_hash = hash_email_for_lookup(email)
    user_id = f"{provider}_{provider_id}"
    
    # STEP 1: Check if user already exists by ID (primary key - most reliable)
    # First, ensure we're working with a clean session state
    db.expire_all()
    
    # Try multiple approaches to find the user, ensuring we hit the database
    user = None
    
    # Approach 1: Direct query with explicit execution
    try:
        user = db.query(User).filter(User.id == user_id).first()
    except Exception as e:
        logger.log_auth_activity(
            auth_action="user_lookup_error",
            user_id=user_id,
            email=email,
            provider=provider,
            status="error",
            error=f"Query error: {str(e)}",
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None
        )
    
    # Approach 2: If not found, try with get() method (more direct for primary key)
    if not user:
        try:
            user = db.get(User, user_id)
        except Exception:
            pass
    
    # Approach 3: If still not found, commit any pending changes and retry
    if not user:
        try:
            db.commit()  # Commit any pending changes
        except Exception:
            pass
        db.expire_all()  # Expire all cached objects
        user = db.query(User).filter(User.id == user_id).first()
    
    # Approach 4: Last resort - try get() again after commit
    if not user:
        try:
            user = db.get(User, user_id)
        except Exception:
            pass
    
    if user:
        # User exists with this ID - verify provider matches (should always match if ID matches)
        if user.provider != provider:
            # Provider mismatch - log warning but continue with existing user
            logger.log_auth_activity(
                auth_action="user_provider_mismatch",
                user_id=user.id,
                email=email,
                provider=provider,
                status="warning",
                metadata={"existing_provider": user.provider},
                ip_address=get_client_ip(request) if request else None,
                user_agent=get_user_agent(request) if request else None
            )
        
        # Update existing user info (always update picture if provided)
        user.name = name or user.name
        if picture:  # Always update picture if provided from OAuth
            user.picture = picture
        user.provider = provider  # Update provider to match current auth
        user.provider_id = provider_id
        # Ensure email is encrypted and hash is set
        if user.email != encrypted_email:
            user.email = encrypted_email
        if user.email_hash != email_hash:
            user.email_hash = email_hash
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        # Log user update (use original email for logging, not encrypted)
        logger.log_auth_activity(
            auth_action="user_updated",
            user_id=user.id,
            email=email,  # Log original email, not encrypted
            provider=provider,
            status="success",
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None
        )
        
        return user
    
    # STEP 2: If not found by ID, check by email_hash (deterministic lookup)
    if email_hash:
        user = db.query(User).filter(User.email_hash == email_hash).first()
        if user:
            # User exists with same email but potentially different provider
            # If provider is the same, use existing user; otherwise, this is a different account
            if user.provider == provider:
                # Same provider - update existing user info
                user.name = name or user.name
                if picture:
                    user.picture = picture
                user.provider_id = provider_id  # Update provider_id in case it changed
                # Ensure email is encrypted and hash is set
                if user.email != encrypted_email:
                    user.email = encrypted_email
                if user.email_hash != email_hash:
                    user.email_hash = email_hash
                user.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(user)
                
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
            # Different provider - this is a different account, continue to create new user
    
    # STEP 3: If not found by hash, try plain email (for existing unencrypted records during migration)
    user = db.query(User).filter(User.email == email).first()
    if user:
        # User exists with plain email - check if provider matches
        if user.provider == provider:
            # Same provider - encrypt email and update
            user.email = encrypted_email
            user.email_hash = email_hash
            user.name = name or user.name
            if picture:
                user.picture = picture
            user.provider_id = provider_id
            user.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(user)
            
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
        # Different provider - this is a different account, continue to create new user
    
    # STEP 4: No existing user found (or found but with different provider)
    # Before creating, do one final check to ensure user doesn't exist
    # This handles race conditions where user might have been created between checks
    db.expire_all()
    final_check = db.query(User).filter(User.id == user_id).first()
    if final_check:
        # User exists! Use existing user instead of creating
        user = final_check
        # Update existing user info
        user.name = name or user.name
        if picture:
            user.picture = picture
        user.provider = provider
        user.provider_id = provider_id
        if user.email != encrypted_email:
            user.email = encrypted_email
        if user.email_hash != email_hash:
            user.email_hash = email_hash
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
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
    
    # Create new user with encrypted email and hash
    # Note: user_id was already calculated above
    try:
        user = User(
            id=user_id,
            email=encrypted_email,  # Store encrypted email
            email_hash=email_hash,  # Store hash for lookups
            name=name,
            provider=provider,
            provider_id=provider_id,
            picture=picture,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Log user creation (use original email for logging)
        logger.log_auth_activity(
            auth_action="user_created",
            user_id=user.id,
            email=email,  # Log original email, not encrypted
            provider=provider,
            status="success",
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None
        )
        
        return user
    except (IntegrityError, Exception) as e:
        # Catch IntegrityError (unique constraint violations) and any other database errors
        # Check if it's a unique constraint violation
        is_unique_violation = (
            isinstance(e, IntegrityError) or
            "UniqueViolation" in str(e) or
            "duplicate key" in str(e).lower() or
            "unique constraint" in str(e).lower()
        )
        
        if not is_unique_violation:
            # If it's not a unique violation, re-raise the exception
            raise
        # If user creation fails due to unique constraint violation (race condition),
        # rollback and try to fetch the existing user
        db.rollback()
        
        # Expire all cached objects to ensure we see the latest database state
        db.expire_all()
        
        # Retry lookup - user might have been created by another concurrent request
        # Use get() for primary key lookup (more efficient and reliable)
        try:
            user = db.get(User, user_id)
        except:
            user = db.query(User).filter(User.id == user_id).first()
        
        # If still not found, try one more time
        if not user:
            db.expire_all()
            try:
                user = db.get(User, user_id)
            except:
                user = db.query(User).filter(User.id == user_id).first()
        
        if user:
            # User exists, update and return
            user.name = name or user.name
            if picture:
                user.picture = picture
            user.provider = provider
            user.provider_id = provider_id
            # Ensure email is encrypted and hash is set
            if user.email != encrypted_email:
                user.email = encrypted_email
            if user.email_hash != email_hash:
                user.email_hash = email_hash
            user.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(user)
            
            # Log user update (use original email for logging)
            logger.log_auth_activity(
                auth_action="user_updated",
                user_id=user.id,
                email=email,  # Log original email, not encrypted
                provider=provider,
                status="success",
                ip_address=get_client_ip(request) if request else None,
                user_agent=get_user_agent(request) if request else None
            )
            
            return user
        
        # If still not found, re-raise the original exception
        raise


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email. Uses email hash for deterministic lookup."""
    email_hash = hash_email_for_lookup(email)
    # Try hash lookup first (deterministic)
    if email_hash:
        user = db.query(User).filter(User.email_hash == email_hash).first()
        if user:
            return user
    # Fallback to plain email lookup (for migration purposes)
    user = db.query(User).filter(User.email == email).first()
    return user

