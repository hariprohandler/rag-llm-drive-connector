"""LLM configuration model."""
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class LLMConfig(Base):
    """User-specific LLM configuration."""
    __tablename__ = "llm_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    config_name = Column(String, nullable=True)  # User-friendly name for the configuration
    provider = Column(String, nullable=False)  # 'openai', 'gemini', 'anthropic', 'custom'
    api_key = Column(Text, nullable=False)  # Encrypted API key
    model_name = Column(String, nullable=True)  # Model name (e.g., 'gpt-4', 'claude-3-opus')
    base_url = Column(String, nullable=True)  # For custom hosted LLMs
    temperature = Column(String, nullable=True, default="0")  # Temperature setting
    max_tokens = Column(Integer, nullable=True)  # Max tokens
    is_default = Column(Boolean, default=False)  # Default LLM for user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", backref="llm_configs")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "config_name": self.config_name,
            "provider": self.provider,
            "model_name": self.model_name,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

