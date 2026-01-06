"""Database models for user management."""
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Text, ForeignKey, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config

Base = declarative_base()


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)  # User ID (email or OAuth ID)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    provider = Column(String, nullable=False)  # 'google' or 'microsoft'
    provider_id = Column(String, nullable=False, index=True)  # OAuth provider user ID
    picture = Column(String, nullable=True)  # Profile picture URL
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "provider": self.provider,
            "picture": self.picture,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LLMConfig(Base):
    """User-specific LLM configuration."""
    __tablename__ = "llm_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
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


class ChatConversation(Base):
    """Chat conversation sessions."""
    __tablename__ = "chat_conversations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=True)  # Auto-generated or user-set title
    is_private = Column(Boolean, default=True)  # Private or generic/public
    llm_config_id = Column(Integer, ForeignKey("llm_configs.id", ondelete="SET NULL"), nullable=True)
    use_rag = Column(Boolean, default=True)  # Whether to use RAG for this conversation
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="chat_conversations")
    llm_config = relationship("LLMConfig", backref="conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "is_private": self.is_private,
            "llm_config_id": self.llm_config_id,
            "use_rag": self.use_rag,
            "message_count": len(self.messages) if self.messages else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatMessage(Base):
    """Individual messages in a chat conversation."""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    message_metadata = Column(JSON, nullable=True)  # Sources, tokens used, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    conversation = relationship("ChatConversation", back_populates="messages")
    
    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "message_metadata": self.message_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Database setup
engine = create_engine(
    config.settings.database_url.replace("postgresql+psycopg2://", "postgresql://"),
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

