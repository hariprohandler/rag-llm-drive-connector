"""User settings model for storing user preferences."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from datetime import datetime
from app.models.base import Base


class UserSettings(Base):
    """User settings model for storing user preferences like organization name."""
    __tablename__ = "user_settings"
    
    id = Column(String, primary_key=True)  # Same as user_id (one-to-one relationship)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    organization_name = Column(String, nullable=True, default="RAG Chat Platform")
    preferences = Column(Text, nullable=True)  # JSON string for additional preferences
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "organization_name": self.organization_name,
            "preferences": self.preferences,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

