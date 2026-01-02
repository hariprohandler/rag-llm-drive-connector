"""Tests for authentication service."""
import pytest
from datetime import timedelta
from auth_service import (
    create_access_token,
    verify_token,
    get_or_create_user,
    get_user_by_email,
    SECRET_KEY
)
from models import User


def test_create_access_token():
    """Test creating a JWT access token."""
    data = {"sub": "test_user_123", "email": "test@example.com"}
    token = create_access_token(data)
    
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_token_success():
    """Test verifying a valid token."""
    data = {"sub": "test_user_123", "email": "test@example.com"}
    token = create_access_token(data)
    payload = verify_token(token)
    
    assert payload["sub"] == "test_user_123"
    assert payload["email"] == "test@example.com"


def test_verify_token_expired():
    """Test verifying an expired token."""
    data = {"sub": "test_user_123"}
    # Create token with very short expiration
    from jose import jwt
    from datetime import datetime, timedelta
    expire = datetime.utcnow() - timedelta(minutes=1)
    data.update({"exp": expire})
    token = jwt.encode(data, SECRET_KEY, algorithm="HS256")
    
    with pytest.raises(Exception):  # Should raise JWTError for expired token
        verify_token(token)


def test_verify_token_invalid():
    """Test verifying an invalid token."""
    invalid_token = "invalid.token.here"
    
    with pytest.raises(Exception):
        verify_token(invalid_token)


def test_get_or_create_user_new(db_session):
    """Test creating a new user."""
    user = get_or_create_user(
        db=db_session,
        email="newuser@example.com",
        name="New User",
        provider="google",
        provider_id="99999"
    )
    
    assert user.email == "newuser@example.com"
    assert user.name == "New User"
    assert user.provider == "google"
    assert user.id == "google_99999"
    
    # Verify it's in the database
    db_user = db_session.query(User).filter(User.email == "newuser@example.com").first()
    assert db_user is not None
    assert db_user.id == user.id


def test_get_or_create_user_existing(db_session):
    """Test getting an existing user."""
    # Create user first
    user1 = get_or_create_user(
        db=db_session,
        email="existing@example.com",
        name="Original Name",
        provider="google",
        provider_id="11111"
    )
    
    # Try to get or create again
    user2 = get_or_create_user(
        db=db_session,
        email="existing@example.com",
        name="Updated Name",
        provider="google",
        provider_id="11111"
    )
    
    assert user1.id == user2.id
    assert user2.name == "Updated Name"  # Should update name


def test_get_user_by_email(db_session, test_user):
    """Test getting user by email."""
    user = get_user_by_email(db_session, "test@example.com")
    
    assert user is not None
    assert user.email == "test@example.com"
    assert user.id == test_user.id


def test_get_user_by_email_not_found(db_session):
    """Test getting user by email when user doesn't exist."""
    user = get_user_by_email(db_session, "nonexistent@example.com")
    assert user is None

