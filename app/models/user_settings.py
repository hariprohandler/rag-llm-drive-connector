"""User settings model for storing user preferences."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Boolean
from datetime import datetime
from app.models.base import Base


class UserSettings(Base):
    """User settings model for storing user preferences like organization name."""
    __tablename__ = "user_settings"
    
    id = Column(String, primary_key=True)  # Same as user_id (one-to-one relationship)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    organization_name = Column(String, nullable=True, default="Anukara")
    preferences = Column(Text, nullable=True)  # JSON string for additional preferences
    # Vector database configuration for user's own RAG DB
    vector_db_url = Column(String, nullable=True)  # Custom pgvector database URL
    vector_db_config = Column(JSON, nullable=True)  # Additional config (e.g., verified status, last_check)
    vector_db_enabled = Column(Boolean, default=False, nullable=False)  # Whether custom DB is enabled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "organization_name": self.organization_name,
            "preferences": self.preferences,
            "vector_db_url": self.vector_db_url,
            "vector_db_config": self.vector_db_config,
            "vector_db_enabled": self.vector_db_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

