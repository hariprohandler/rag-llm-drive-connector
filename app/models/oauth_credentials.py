"""OAuth credentials model for storing Google Drive and OneDrive access tokens."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from datetime import datetime
from app.models.base import Base
import json


class OAuthCredentials(Base):
    """OAuth credentials model for storing user's Google Drive and OneDrive tokens."""
    __tablename__ = "oauth_credentials"

    id = Column(String, primary_key=True)  # Format: {user_id}_{provider}
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String, nullable=False)  # 'google' or 'microsoft'
    
    # Encrypted credentials (JSON string)
    # For Google: stores refresh_token, token, token_uri, client_id, client_secret, scopes
    # For Microsoft: stores access_token, refresh_token, expires_at
    credentials_json = Column(Text, nullable=False)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)  # Token expiration time
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_credentials(self):
        """Get credentials as dictionary."""
        try:
            return json.loads(self.credentials_json)
        except:
            return {}

    def set_credentials(self, creds_dict: dict):
        """Set credentials from dictionary."""
        self.credentials_json = json.dumps(creds_dict)

    def to_dict(self):
        """Convert to dictionary (without sensitive data)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "provider": self.provider,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

