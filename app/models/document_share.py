"""Document sharing model for institutional accounts and access control."""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Text, Enum as SQLEnum, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.base import Base


class ShareType(str, enum.Enum):
    """Document share type enumeration."""
    PUBLIC = "public"  # Share with all organization members
    MEMBER = "member"  # Share with specific member(s)
    GROUP = "group"  # Share with specific group(s)
    PRIVATE = "private"  # Only owner


class DocumentShare(Base):
    """Document sharing model for controlling access to documents in organizations."""
    __tablename__ = "document_shares"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Share type determines how access is granted
    share_type = Column(SQLEnum(ShareType), nullable=False, default=ShareType.PRIVATE, index=True)
    
    # For MEMBER share type: specific member IDs (stored as JSON array)
    shared_with_members = Column(JSON, nullable=True)  # List of member IDs
    
    # For GROUP share type: specific group ID
    group_id = Column(Integer, ForeignKey("organization_groups.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Owner information
    shared_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    
    # Metadata
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="shares")
    organization = relationship("Organization", back_populates="shared_documents")
    group = relationship("OrganizationGroup", back_populates="shared_documents")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_doc_share_org_type', 'organization_id', 'share_type'),
        Index('ix_doc_share_kb_org', 'knowledge_base_id', 'organization_id'),
        Index('ix_doc_share_active_type', 'is_active', 'share_type'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "organization_id": self.organization_id,
            "share_type": self.share_type.value if isinstance(self.share_type, ShareType) else self.share_type,
            "shared_with_members": self.shared_with_members,
            "group_id": self.group_id,
            "shared_by": self.shared_by,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
