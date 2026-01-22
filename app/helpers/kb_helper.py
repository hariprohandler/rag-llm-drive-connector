"""Helper functions for creating KnowledgeBase instances with backward compatibility."""
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from datetime import datetime
import json
from app.models import KnowledgeBase


def create_knowledge_base_safe(
    db: Session,
    user_id: str,
    name: str,
    source_type: str,
    source_id: str = None,
    extra_metadata: dict = None,
    document_count: int = 0,
    organization_id: int = None,
    is_active: bool = True
) -> KnowledgeBase:
    """
    Safely create a KnowledgeBase instance, handling cases where organization_id column might not exist.
    
    This function uses the ORM when the column exists (standard approach), and falls back to raw SQL
    only when the column is missing (backward compatibility).
    
    Args:
        db: Database session
        user_id: User ID
        name: Knowledge base name
        source_type: Source type (e.g., 'local_file', 'gmail', etc.)
        source_id: Optional source ID
        extra_metadata: Optional extra metadata dict
        document_count: Document count
        organization_id: Optional organization ID
        is_active: Whether the KB is active
        
    Returns:
        Created KnowledgeBase instance with ID set
    """
    # Check if organization_id column exists in the database
    inspector = inspect(db.bind)
    columns = [col['name'] for col in inspector.get_columns('knowledge_bases')]
    has_org_id = 'organization_id' in columns
    
    if has_org_id:
        # Use standard ORM approach - the column exists
        kb = KnowledgeBase(
            user_id=user_id,
            organization_id=organization_id,
            name=name,
            source_type=source_type,
            source_id=source_id,
            extra_metadata=extra_metadata or {},
            document_count=document_count,
            is_active=is_active
        )
        db.add(kb)
        db.flush()  # Flush to get the ID without committing
        db.commit()
        db.refresh(kb)
        return kb
    else:
        # Fallback: Use raw SQL when column doesn't exist (backward compatibility)
        now = datetime.utcnow()
        extra_metadata_json = json.dumps(extra_metadata) if extra_metadata else None
        
        insert_sql = text("""
            INSERT INTO knowledge_bases 
            (user_id, name, source_type, source_id, extra_metadata, 
             document_count, is_active, created_at, updated_at)
            VALUES 
            (:user_id, :name, :source_type, :source_id, :extra_metadata::jsonb, 
             :document_count, :is_active, :created_at, :updated_at)
            RETURNING id
        """)
        params = {
            'user_id': user_id,
            'name': name,
            'source_type': source_type,
            'source_id': source_id,
            'extra_metadata': extra_metadata_json,
            'document_count': document_count,
            'is_active': is_active,
            'created_at': now,
            'updated_at': now
        }
        
        # Execute the insert and get the ID
        result = db.execute(insert_sql, params)
        kb_id = result.scalar()
        db.commit()
        
        # Fetch the full object
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        return kb
