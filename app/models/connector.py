"""Connector models for third-party integrations (Slack, Teams, etc.)."""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Text, JSON, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.base import Base


class ConnectorType(str, enum.Enum):
    """Connector type enumeration."""
    GOOGLE_DRIVE = "google_drive"
    ONEDRIVE = "onedrive"
    SLACK = "slack"
    TEAMS = "teams"
    GMAIL = "gmail"
    OUTLOOK = "outlook"


class ConnectorStatus(str, enum.Enum):
    """Connector connection status."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"
    EXPIRED = "expired"


class Connector(Base):
    """Connector model for managing third-party integrations."""
    __tablename__ = "connectors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    
    connector_type = Column(SQLEnum(ConnectorType), nullable=False, index=True)
    connector_name = Column(String, nullable=False)  # User-friendly name
    status = Column(SQLEnum(ConnectorStatus), nullable=False, default=ConnectorStatus.DISCONNECTED, index=True)
    
    # Connection configuration (stores connector-specific settings)
    config = Column(JSON, nullable=True)  # Channel IDs, workspace IDs, etc.
    
    # OAuth credentials reference
    oauth_credential_id = Column(String, ForeignKey("oauth_credentials.id", ondelete="SET NULL"), nullable=True)
    
    # Sync configuration
    auto_sync_enabled = Column(Boolean, default=False, nullable=False, index=True)
    sync_interval_hours = Column(Integer, default=24, nullable=False)  # How often to auto-sync
    last_sync_at = Column(DateTime, nullable=True, index=True)
    next_sync_at = Column(DateTime, nullable=True, index=True)
    
    # Metadata
    error_message = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="connectors")
    organization = relationship("Organization", backref="connectors")
    oauth_credentials = relationship("OAuthCredentials", foreign_keys=[oauth_credential_id])
    sync_jobs = relationship("SyncJob", back_populates="connector", cascade="all, delete-orphan")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_connector_user_type', 'user_id', 'connector_type', 'is_active'),
        Index('ix_connector_org_type', 'organization_id', 'connector_type', 'is_active'),
        Index('ix_connector_status_sync', 'status', 'auto_sync_enabled', 'next_sync_at'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "connector_type": self.connector_type.value if isinstance(self.connector_type, ConnectorType) else self.connector_type,
            "connector_name": self.connector_name,
            "status": self.status.value if isinstance(self.status, ConnectorStatus) else self.status,
            "config": self.config,
            "oauth_credential_id": self.oauth_credential_id,
            "auto_sync_enabled": self.auto_sync_enabled,
            "sync_interval_hours": self.sync_interval_hours,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "next_sync_at": self.next_sync_at.isoformat() if self.next_sync_at else None,
            "error_message": self.error_message,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SyncJobStatus(str, enum.Enum):
    """Sync job status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncJob(Base):
    """Sync job model for queue-based background processing."""
    __tablename__ = "sync_jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    connector_id = Column(Integer, ForeignKey("connectors.id", ondelete="CASCADE"), nullable=True, index=True)  # Nullable for tools like Zendesk that use ToolConfig
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Job configuration
    source_type = Column(String, nullable=False, index=True)  # 'slack', 'teams', 'onedrive', etc.
    sync_scope = Column(JSON, nullable=True)  # Channels, folders, date ranges to sync
    priority = Column(Integer, default=5, nullable=False, index=True)  # 1-10, lower = higher priority
    
    # Job status and progress
    status = Column(SQLEnum(SyncJobStatus), nullable=False, default=SyncJobStatus.PENDING, index=True)
    progress_percentage = Column(Integer, default=0, nullable=False)
    current_step = Column(String, nullable=True)  # Current processing step
    items_processed = Column(Integer, default=0, nullable=False)
    items_total = Column(Integer, nullable=True)
    
    # Results
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True)
    items_indexed = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    connector = relationship("Connector", back_populates="sync_jobs")
    knowledge_base = relationship("KnowledgeBase", foreign_keys=[knowledge_base_id])
    
    # Indexes for efficient queue processing
    __table_args__ = (
        Index('ix_sync_job_status_priority', 'status', 'priority', 'created_at'),
        Index('ix_sync_job_user_status', 'user_id', 'status', 'created_at'),
        Index('ix_sync_job_connector_status', 'connector_id', 'status', 'created_at'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "connector_id": self.connector_id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "source_type": self.source_type,
            "sync_scope": self.sync_scope,
            "priority": self.priority,
            "status": self.status.value if isinstance(self.status, SyncJobStatus) else self.status,
            "progress_percentage": self.progress_percentage,
            "current_step": self.current_step,
            "items_processed": self.items_processed,
            "items_total": self.items_total,
            "knowledge_base_id": self.knowledge_base_id,
            "items_indexed": self.items_indexed,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
