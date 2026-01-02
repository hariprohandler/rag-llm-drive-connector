"""Database models for user management."""
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
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

