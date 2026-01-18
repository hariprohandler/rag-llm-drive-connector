"""Tool configuration model for third-party integrations."""
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class ToolConfig(Base):
    """User-specific tool configuration for third-party integrations."""
    __tablename__ = "tool_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name = Column(String, nullable=False, index=True)  # 'zendesk', 'slack', 'teams', etc.
    is_active = Column(Boolean, default=True)
    
    # Tool-specific configuration stored as JSON
    # For Zendesk: { "subdomain": "...", "email": "...", "api_token": "..." (encrypted) }
    config_data = Column(JSON, nullable=False)
    
    # Sync status
    last_sync_at = Column(DateTime, nullable=True)
    sync_status = Column(String, nullable=True)  # 'idle', 'syncing', 'completed', 'failed'
    sync_error = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", backref="tool_configs")
    
    def to_dict(self):
        """Convert to dictionary, excluding sensitive data."""
        config_data = self.config_data.copy() if self.config_data else {}
        
        # Mask sensitive fields
        if "api_token" in config_data:
            config_data["api_token"] = "••••••••" if config_data["api_token"] else None
        
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tool_name": self.tool_name,
            "is_active": self.is_active,
            "config_data": config_data,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "sync_status": self.sync_status,
            "sync_error": self.sync_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def to_dict_with_secrets(self):
        """Convert to dictionary including sensitive data (for internal use)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tool_name": self.tool_name,
            "is_active": self.is_active,
            "config_data": self.config_data,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "sync_status": self.sync_status,
            "sync_error": self.sync_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

