"""Organization and institutional account models for multi-tenant support."""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Text, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class Organization(Base):
    """Organization model for institutional accounts."""
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)  # URL-friendly identifier
    description = Column(Text, nullable=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    settings = Column(JSON, nullable=True)  # Organization-level settings
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    groups = relationship("OrganizationGroup", back_populates="organization", cascade="all, delete-orphan")
    shared_documents = relationship("DocumentShare", back_populates="organization", cascade="all, delete-orphan")
    knowledge_bases = relationship("KnowledgeBase", back_populates="organization", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "settings": self.settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OrganizationMember(Base):
    """Organization member model for role-based access control."""
    __tablename__ = "organization_members"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, default="member", index=True)  # 'admin' or 'member'
    invited_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    groups = relationship("OrganizationGroupMember", back_populates="member", cascade="all, delete-orphan")
    
    # Unique constraint: user can only have one membership per organization
    __table_args__ = (
        UniqueConstraint('organization_id', 'user_id', name='uq_org_member'),
        Index('ix_org_member_user_org', 'user_id', 'organization_id'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "role": self.role,
            "invited_by": self.invited_by,
            "is_active": self.is_active,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OrganizationGroup(Base):
    """Organization group model for organizing members."""
    __tablename__ = "organization_groups"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="groups")
    members = relationship("OrganizationGroupMember", back_populates="group", cascade="all, delete-orphan")
    shared_documents = relationship("DocumentShare", back_populates="group", cascade="all, delete-orphan")
    
    # Unique constraint: group name must be unique within organization
    __table_args__ = (
        UniqueConstraint('organization_id', 'name', name='uq_org_group_name'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OrganizationGroupMember(Base):
    """Many-to-many relationship between organization groups and members."""
    __tablename__ = "organization_group_members"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("organization_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("organization_members.id", ondelete="CASCADE"), nullable=False, index=True)
    added_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    group = relationship("OrganizationGroup", back_populates="members")
    member = relationship("OrganizationMember", back_populates="groups")
    
    # Unique constraint: member can only be in group once
    __table_args__ = (
        UniqueConstraint('group_id', 'member_id', name='uq_group_member'),
        Index('ix_group_member_ids', 'group_id', 'member_id'),
    )
