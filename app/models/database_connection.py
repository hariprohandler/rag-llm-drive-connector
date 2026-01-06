"""Database connection model for external database integrations."""
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base


class DatabaseConnection(Base):
    """User-specific database connection for external databases."""
    __tablename__ = "database_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)  # User-friendly name
    db_type = Column(String, nullable=False)  # 'postgresql', 'mysql', 'sqlite', 'mssql', etc.
    
    # Connection details (encrypted)
    connection_string = Column(Text, nullable=False)  # Encrypted connection string
    
    # Schema cache (JSON)
    schema_info = Column(JSON, nullable=True)  # Cached schema information
    schema_updated_at = Column(DateTime, nullable=True)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", backref="database_connections")
    
    def to_dict(self):
        """Convert to dictionary, excluding sensitive connection string."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "db_type": self.db_type,
            "schema_info": self.schema_info,
            "schema_updated_at": self.schema_updated_at.isoformat() if self.schema_updated_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def to_dict_with_connection(self):
        """Convert to dictionary including connection string (for internal use only)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "db_type": self.db_type,
            "connection_string": self.connection_string,
            "schema_info": self.schema_info,
            "schema_updated_at": self.schema_updated_at.isoformat() if self.schema_updated_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

