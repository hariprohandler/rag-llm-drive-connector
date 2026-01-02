"""Tests for database models."""
import pytest
from datetime import datetime
from models import User


def test_user_creation(db_session):
    """Test creating a user."""
    user = User(
        id="google_123",
        email="test@example.com",
        name="Test User",
        provider="google",
        provider_id="123",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    
    assert user.id == "google_123"
    assert user.email == "test@example.com"
    assert user.provider == "google"
    assert user.is_active is True
    assert user.created_at is not None


def test_user_to_dict(db_session):
    """Test user to_dict method."""
    user = User(
        id="google_123",
        email="test@example.com",
        name="Test User",
        provider="google",
        provider_id="123",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    
    user_dict = user.to_dict()
    assert user_dict["id"] == "google_123"
    assert user_dict["email"] == "test@example.com"
    assert user_dict["name"] == "Test User"
    assert user_dict["provider"] == "google"
    assert "created_at" in user_dict


def test_user_uniqueness(db_session):
    """Test that email must be unique."""
    user1 = User(
        id="google_123",
        email="test@example.com",
        name="Test User",
        provider="google",
        provider_id="123"
    )
    db_session.add(user1)
    db_session.commit()
    
    # Try to create another user with same email
    user2 = User(
        id="google_456",
        email="test@example.com",
        name="Another User",
        provider="google",
        provider_id="456"
    )
    db_session.add(user2)
    
    with pytest.raises(Exception):  # SQLAlchemy will raise an integrity error
        db_session.commit()


def test_user_update(db_session):
    """Test updating user information."""
    user = User(
        id="google_123",
        email="test@example.com",
        name="Test User",
        provider="google",
        provider_id="123"
    )
    db_session.add(user)
    db_session.commit()
    
    # Update user
    user.name = "Updated Name"
    user.is_active = False
    db_session.commit()
    db_session.refresh(user)
    
    assert user.name == "Updated Name"
    assert user.is_active is False

