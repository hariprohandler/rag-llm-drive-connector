"""User settings model for storing user preferences."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Boolean, text
from datetime import datetime
from typing import Optional
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
            "vector_db_url": getattr(self, 'vector_db_url', None),  # Safe access for backward compatibility
            "vector_db_config": getattr(self, 'vector_db_config', None),  # Safe access for backward compatibility
            "vector_db_enabled": getattr(self, 'vector_db_enabled', False),  # Safe access for backward compatibility
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def safe_query_user_settings(db, user_id: str) -> Optional[UserSettings]:
    """
    Safely query UserSettings with backward compatibility for vector_db columns.
    
    This function handles cases where the vector_db columns might not exist
    in the database yet (e.g., migration not run or app not restarted).
    
    Args:
        db: Database session
        user_id: User ID to query
        
    Returns:
        UserSettings object or None if not found
    """
    try:
        # Try normal ORM query first
        return db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    except Exception as e:
        error_str = str(e).lower()
        # If vector_db columns don't exist, use raw SQL
        if "vector_db" in error_str or "undefinedcolumn" in error_str:
            db.rollback()
            try:
                sql = text("""
                    SELECT id, user_id, organization_name, preferences, 
                           created_at, updated_at
                    FROM user_settings 
                    WHERE user_id = :user_id
                    LIMIT 1
                """)
                
                result = db.execute(sql, {"user_id": user_id})
                row = result.fetchone()
                if not row:
                    return None
                
                user_settings = UserSettings()
                user_settings.id = row[0]
                user_settings.user_id = row[1]
                user_settings.organization_name = row[2]
                user_settings.preferences = row[3]
                user_settings.created_at = row[4]
                user_settings.updated_at = row[5]
                # vector_db columns will be None/False (not set)
                return user_settings
            except Exception as e2:
                print(f"Error in raw SQL fallback for UserSettings: {e2}")
                db.rollback()
                return None
        else:
            # Re-raise if it's a different error
            raise

