"""Knowledge base model."""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, text
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional, List
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
            "organization_id": getattr(self, 'organization_id', None),  # Safe access for backward compatibility
            "name": self.name,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "extra_metadata": self.extra_metadata,
            "document_count": self.document_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def safe_query_knowledge_bases(db, filters: dict) -> List[KnowledgeBase]:
    """
    Safely query KnowledgeBase with backward compatibility for organization_id column.
    
    This function handles cases where the organization_id column might not exist
    in the database yet (e.g., migration not run or app not restarted).
    
    Args:
        db: Database session
        filters: Dictionary of filters (e.g., {'user_id': '...', 'source_type': '...', 'is_active': True})
        
    Returns:
        List of KnowledgeBase objects
    """
    try:
        # Try normal ORM query first
        query = db.query(KnowledgeBase)
        for key, value in filters.items():
            if hasattr(KnowledgeBase, key):
                query = query.filter(getattr(KnowledgeBase, key) == value)
        return query.all()
    except Exception as e:
        error_str = str(e).lower()
        # If organization_id column doesn't exist, use raw SQL
        if "organization_id" in error_str or "undefinedcolumn" in error_str:
            db.rollback()
            # Build WHERE clause dynamically
            where_clauses = []
            params = {}
            for key, value in filters.items():
                if key in ['id', 'user_id', 'source_type', 'is_active', 'name', 'source_id']:
                    where_clauses.append(f"{key} = :{key}")
                    params[key] = value
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            sql = text(f"""
                SELECT id, user_id, name, source_type, source_id, extra_metadata, 
                       document_count, is_active, created_at, updated_at
                FROM knowledge_bases 
                WHERE {where_sql}
            """)
            
            result = db.execute(sql, params)
            knowledge_bases = []
            for row in result:
                kb = KnowledgeBase()
                kb.id = row[0]
                kb.user_id = row[1]
                kb.name = row[2]
                kb.source_type = row[3]
                kb.source_id = row[4]
                kb.extra_metadata = row[5]
                kb.document_count = row[6]
                kb.is_active = row[7]
                kb.created_at = row[8]
                kb.updated_at = row[9]
                # organization_id will be None (not set)
                knowledge_bases.append(kb)
            return knowledge_bases
        else:
            # Re-raise if it's a different error
            raise

