"""Fine-tuning job models for model customization."""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Text, Enum as SQLEnum, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.base import Base


class FineTuningStatus(str, enum.Enum):
    """Fine-tuning job status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    PREPARING = "preparing"
    TRAINING = "training"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FineTuningJob(Base):
    """Fine-tuning job model for tracking model training jobs."""
    __tablename__ = "fine_tuning_jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Model information
    base_model_name = Column(String, nullable=False, index=True)  # Hugging Face model ID
    base_model_repository = Column(String, nullable=False, default="huggingface")  # Model source
    tuned_model_name = Column(String, nullable=True, index=True)  # Custom name for tuned model
    
    # Training data source
    data_source_type = Column(String, nullable=False, index=True)  # 'knowledge_base', 'uploaded', 'custom'
    data_source_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True)  # KB ID if applicable
    data_source_config = Column(JSON, nullable=True)  # Additional data source configuration
    
    # Job status and progress
    status = Column(SQLEnum(FineTuningStatus), nullable=False, default=FineTuningStatus.PENDING, index=True)
    progress_percentage = Column(Integer, default=0, nullable=False)
    current_step = Column(String, nullable=True)  # Current training step description
    error_message = Column(Text, nullable=True)  # Error details if failed
    
    # Hugging Face integration
    hf_job_id = Column(String, nullable=True, index=True)  # Hugging Face job ID
    hf_model_id = Column(String, nullable=True, index=True)  # Published Hugging Face model ID
    hf_repository = Column(String, nullable=True)  # Hugging Face repository path
    
    # Training configuration
    training_config = Column(JSON, nullable=True)  # Hyperparameters, epochs, etc.
    
    # Results and metrics
    training_metrics = Column(JSON, nullable=True)  # Loss, accuracy, etc.
    validation_metrics = Column(JSON, nullable=True)
    
    # Publishing
    is_published = Column(Boolean, default=False, nullable=False, index=True)
    published_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    knowledge_base = relationship("KnowledgeBase", foreign_keys=[data_source_id])
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_ft_job_user_status', 'user_id', 'status'),
        Index('ix_ft_job_org_status', 'organization_id', 'status'),
        Index('ix_ft_job_status_created', 'status', 'created_at'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "base_model_name": self.base_model_name,
            "base_model_repository": self.base_model_repository,
            "tuned_model_name": self.tuned_model_name,
            "data_source_type": self.data_source_type,
            "data_source_id": self.data_source_id,
            "data_source_config": self.data_source_config,
            "status": self.status.value if isinstance(self.status, FineTuningStatus) else self.status,
            "progress_percentage": self.progress_percentage,
            "current_step": self.current_step,
            "error_message": self.error_message,
            "hf_job_id": self.hf_job_id,
            "hf_model_id": self.hf_model_id,
            "hf_repository": self.hf_repository,
            "training_config": self.training_config,
            "training_metrics": self.training_metrics,
            "validation_metrics": self.validation_metrics,
            "is_published": self.is_published,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
