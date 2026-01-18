"""Tag model for organizing and filtering documents."""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class Tag(Base):
    """Tag model for categorizing documents (customer-defined and system-created)."""
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, index=True)
    slug = Column(String, nullable=False, index=True)  # URL-friendly tag identifier
    description = Column(Text, nullable=True)
    color = Column(String, nullable=True)  # Hex color for UI display
    
    # Tag ownership
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # User-specific tag
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)  # Org-wide tag
    
    # Tag type
    is_system = Column(Boolean, default=False, nullable=False, index=True)  # System-created vs user-created
    
    # Metadata
    usage_count = Column(Integer, default=0, nullable=False)  # Track how many documents use this tag
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document_tags = relationship("DocumentTag", back_populates="tag", cascade="all, delete-orphan")
    
    # Constraints: tag name/slug must be unique per user/org (null means global/system tag)
    __table_args__ = (
        UniqueConstraint('name', 'user_id', 'organization_id', name='uq_tag_name_owner'),
        UniqueConstraint('slug', 'user_id', 'organization_id', name='uq_tag_slug_owner'),
        Index('ix_tag_user_org', 'user_id', 'organization_id', 'is_active'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "color": self.color,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "is_system": self.is_system,
            "usage_count": self.usage_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DocumentTag(Base):
    """Many-to-many relationship between documents (knowledge bases) and tags."""
    __tablename__ = "document_tags"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True)
    added_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="tags")
    tag = relationship("Tag", back_populates="document_tags")
    
    # Unique constraint: document can only have tag once
    __table_args__ = (
        UniqueConstraint('knowledge_base_id', 'tag_id', name='uq_doc_tag'),
        Index('ix_doc_tag_ids', 'knowledge_base_id', 'tag_id'),
    )
