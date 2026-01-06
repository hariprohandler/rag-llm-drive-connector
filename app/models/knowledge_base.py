"""Knowledge base model."""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class KnowledgeBase(Base):
    """User knowledge base sources (files, drives, etc.)."""
    __tablename__ = "knowledge_bases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)  # User-friendly name
    source_type = Column(String, nullable=False)  # 'local_file', 'google_drive', 'onedrive'
    source_id = Column(String, nullable=True)  # File path, folder ID, etc.
    extra_metadata = Column(JSON, nullable=True)  # Additional metadata (file size, folder name, etc.)
    document_count = Column(Integer, default=0)  # Number of documents ingested
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", backref="knowledge_bases")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "extra_metadata": self.extra_metadata,
            "document_count": self.document_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

