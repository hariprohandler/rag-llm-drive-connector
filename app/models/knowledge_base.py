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
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)  # For institutional accounts
    name = Column(String, nullable=False)  # User-friendly name
    source_type = Column(String, nullable=False, index=True)  # 'local_file', 'google_drive', 'onedrive'
    source_id = Column(String, nullable=True)  # File path, folder ID, etc.
    extra_metadata = Column(JSON, nullable=True)  # Additional metadata (file size, folder name, etc.)
    document_count = Column(Integer, default=0)  # Number of documents ingested
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="knowledge_bases")
    organization = relationship("Organization", back_populates="knowledge_bases")
    shares = relationship("DocumentShare", back_populates="knowledge_base", cascade="all, delete-orphan")
    tags = relationship("DocumentTag", back_populates="knowledge_base", cascade="all, delete-orphan")
    # Fine-tuning jobs that use this KB as data source - defined in fine_tuning.py
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "name": self.name,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "extra_metadata": self.extra_metadata,
            "document_count": self.document_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

