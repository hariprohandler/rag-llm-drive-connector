"""Helper utilities for vector database configuration and compatibility checks."""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import logging

from app.constants import TableNames, CollectionPrefix
from app.locales import t

logger = logging.getLogger(__name__)


def normalize_db_url(url: str) -> str:
    """Normalize database URL to postgresql:// format for psycopg2."""
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql://")
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://")
    return url


def check_pgvector_compatibility(db_url: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if the PostgreSQL database has pgvector extension installed and compatible.
    
    Args:
        db_url: PostgreSQL database connection URL
        
    Returns:
        Tuple of (is_compatible, details_dict)
        details_dict contains:
            - compatible: bool
            - pgvector_installed: bool
            - pgvector_version: str or None
            - postgres_version: str or None
            - error: str or None
    """
    details = {
        "compatible": False,
        "pgvector_installed": False,
        "pgvector_version": None,
        "postgres_version": None,
        "error": None
    }
    
    try:
        normalized_url = normalize_db_url(db_url)
        conn = psycopg2.connect(normalized_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check PostgreSQL version
        cursor.execute("SELECT version();")
        pg_version = cursor.fetchone()[0]
        details["postgres_version"] = pg_version.split(',')[0]  # Just the main version string
        
        # Check if pgvector extension exists
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            );
        """)
        has_vector_ext = cursor.fetchone()[0]
        
        if not has_vector_ext:
            # Try to create it
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    );
                """)
                has_vector_ext = cursor.fetchone()[0]
            except Exception as e:
                details["error"] = f"Cannot create pgvector extension: {str(e)}"
                cursor.close()
                conn.close()
                return False, details
        
        if has_vector_ext:
            details["pgvector_installed"] = True
            # Try to get pgvector version
            try:
                cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
                result = cursor.fetchone()
                if result:
                    details["pgvector_version"] = result[0]
            except Exception:
                pass
            
            # Test vector type availability
            try:
                cursor.execute("SELECT '1,2,3'::vector;")
                details["compatible"] = True
            except Exception as e:
                details["error"] = f"pgvector extension exists but vector type not working: {str(e)}"
        else:
            details["error"] = "pgvector extension not found and could not be created"
        
        cursor.close()
        conn.close()
        
    except psycopg2.OperationalError as e:
        details["error"] = f"Connection failed: {str(e)}"
    except Exception as e:
        details["error"] = f"Unexpected error: {str(e)}"
        logger.exception("Error checking pgvector compatibility")
    
    return details["compatible"], details


def test_vector_db_connection(db_url: str) -> Tuple[bool, str]:
    """
    Test if we can connect to the database and perform basic operations.
    
    Args:
        db_url: Database connection URL
        
    Returns:
        Tuple of (success, message)
    """
    try:
        normalized_url = normalize_db_url(db_url)
        conn = psycopg2.connect(normalized_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT 1;")
        cursor.fetchone()
        
        # Test pgvector compatibility
        compatible, details = check_pgvector_compatibility(db_url)
        
        cursor.close()
        conn.close()
        
        if compatible:
            return True, "Connection successful and pgvector is compatible"
        else:
            return False, details.get("error", "Connection successful but pgvector check failed")
            
    except psycopg2.OperationalError as e:
        return False, f"Connection failed: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def get_user_vector_db_url(user_settings) -> Optional[str]:
    """
    Get the vector database URL for a user, either from their settings or default.
    
    For backward compatibility: If a user has a vector_db_url configured but 
    vector_db_enabled is False (e.g., after migration), we still use it.
    The vector_db_enabled flag is primarily for explicit user control via UI.
    
    Args:
        user_settings: UserSettings model instance or None
        
    Returns:
        Vector database URL string or None (None means use default database)
    """
    if user_settings and user_settings.vector_db_url:
        # Use the URL if it exists, regardless of enabled flag
        # This preserves existing configurations after migration
        # The enabled flag is for UI control, but if URL exists, use it
        return user_settings.vector_db_url
    return None


def get_vector_table_name(source_type: str, use_source_tables: bool = True) -> Optional[str]:
    """
    Get the physical table name for a source type.
    
    For petabyte-scale performance, we use separate tables per source type:
    - vectors_slack - Slack messages
    - vectors_teams - Teams messages
    - vectors_onedrive - OneDrive files
    - vectors_google_drive - Google Drive files
    - vectors_local_file - Local files
    - vectors_zendesk - Zendesk tickets
    
    This provides:
    - 10-100x faster queries (search only relevant table)
    - Better index performance (smaller, focused indexes)
    - Reduced lock contention (writes spread across tables)
    - Effective partitioning (can partition each table independently)
    
    Args:
        source_type: Source type (e.g., 'slack', 'teams', 'onedrive', 'local_file')
        use_source_tables: If False, returns None to use default collection table
        
    Returns:
        Table name string or None (to use default langchain_pg_embedding table)
    """
    if not use_source_tables:
        return None
    
    # Use constants for table names
    return TableNames.get_table_name(source_type)


def get_source_type_from_table(table_name: str) -> Optional[str]:
    """
    Extract source type from table name (reverse mapping).
    
    Args:
        table_name: Table name (e.g., 'vectors_slack')
        
    Returns:
        Source type string or None
    """
    return TableNames.get_source_type(table_name)


def get_collection_name(
    user_id: str,
    knowledge_base_id: Optional[int] = None,
    source_type: Optional[str] = None,
    organization_id: Optional[int] = None
) -> str:
    """
    Generate a collection name for vector storage.
    
    For better organization and petabyte-scale scalability, we organize collections by:
    - Source type for optimal query performance (separate tables per source type)
    - Knowledge base ID for fine-grained access
    - Organization ID for institutional accounts
    
    Collection naming strategy:
    1. If organization_id and source_type: org_{org_id}_source_{source_type}_kb_{kb_id}
    2. If organization_id: org_{org_id}_kb_{kb_id}
    3. If knowledge_base_id and source_type: user_{user_id}_source_{source_type}_kb_{kb_id}
    4. If knowledge_base_id: user_{user_id}_kb_{kb_id}
    5. Fallback: user_{user_id}_documents
    
    This allows:
    - Source-specific searches (separate tables per source type = faster queries)
    - Better scalability (can partition by source type and knowledge base)
    - Easier management (delete/update specific sources)
    - Institutional account support (organization-level collections)
    
    Args:
        user_id: User ID
        knowledge_base_id: Optional knowledge base ID
        source_type: Optional source type (e.g., 'local_file', 'google_drive', 'onedrive')
        organization_id: Optional organization ID for institutional accounts
        
    Returns:
        Collection name string
    """
    # Normalize source_type for use in collection name (remove special chars)
    safe_source_type = None
    if source_type:
        safe_source_type = source_type.replace('-', '_').replace(' ', '_').lower()
    
    if organization_id:
        # Institutional account collections
        if safe_source_type and knowledge_base_id:
            return f"{CollectionPrefix.ORG_PREFIX}{organization_id}_{CollectionPrefix.SOURCE_PREFIX}{safe_source_type}_{CollectionPrefix.KB_PREFIX}{knowledge_base_id}"
        elif safe_source_type:
            return f"{CollectionPrefix.ORG_PREFIX}{organization_id}_{CollectionPrefix.SOURCE_PREFIX}{safe_source_type}"
        elif knowledge_base_id:
            return f"{CollectionPrefix.ORG_PREFIX}{organization_id}_{CollectionPrefix.KB_PREFIX}{knowledge_base_id}"
        else:
            return f"{CollectionPrefix.ORG_PREFIX}{organization_id}{CollectionPrefix.DOCUMENTS_SUFFIX}"
    else:
        # Personal account collections
        if safe_source_type and knowledge_base_id:
            return f"{CollectionPrefix.USER_PREFIX}{user_id}_{CollectionPrefix.SOURCE_PREFIX}{safe_source_type}_{CollectionPrefix.KB_PREFIX}{knowledge_base_id}"
        elif knowledge_base_id:
            return f"{CollectionPrefix.USER_PREFIX}{user_id}_{CollectionPrefix.KB_PREFIX}{knowledge_base_id}"
        elif safe_source_type:
            return f"{CollectionPrefix.USER_PREFIX}{user_id}_{CollectionPrefix.SOURCE_PREFIX}{safe_source_type}"
        else:
            # Fallback to user-level collection (for backward compatibility)
            return f"{CollectionPrefix.USER_PREFIX}{user_id}{CollectionPrefix.DOCUMENTS_SUFFIX}"


def build_tag_filter(tag_ids: Optional[list] = None, tag_slugs: Optional[list] = None) -> Optional[Dict[str, Any]]:
    """
    Build a metadata filter for tag-based document filtering.
    
    For petabyte-scale queries, tag filtering happens at the metadata level
    in the vector database, allowing efficient filtering without scanning
    the full document set.
    
    Args:
        tag_ids: List of tag IDs to filter by
        tag_slugs: List of tag slugs to filter by
        
    Returns:
        Metadata filter dictionary for PGVector search, or None
    """
    if not tag_ids and not tag_slugs:
        return None
    
    filter_dict = {}
    
    if tag_ids:
        # Filter by tag IDs in metadata
        filter_dict["tag_ids"] = {"$contains": tag_ids}
    
    if tag_slugs:
        # Filter by tag slugs in metadata
        filter_dict["tag_slugs"] = {"$contains": tag_slugs}
    
    return filter_dict if filter_dict else None


def build_metadata_with_tags(
    base_metadata: Dict[str, Any],
    tag_ids: Optional[list] = None,
    tag_slugs: Optional[list] = None
) -> Dict[str, Any]:
    """
    Add tag information to document metadata for efficient filtering.
    
    This allows tag-based filtering at query time without joins,
    optimizing for petabyte-scale datasets.
    
    Args:
        base_metadata: Base metadata dictionary
        tag_ids: List of tag IDs to add
        tag_slugs: List of tag slugs to add
        
    Returns:
        Metadata dictionary with tag information
    """
    metadata = base_metadata.copy()
    
    if tag_ids:
        if "tag_ids" not in metadata:
            metadata["tag_ids"] = []
        if isinstance(metadata["tag_ids"], list):
            metadata["tag_ids"].extend([str(tid) for tid in tag_ids])
        else:
            metadata["tag_ids"] = [str(tid) for tid in tag_ids]
    
    if tag_slugs:
        if "tag_slugs" not in metadata:
            metadata["tag_slugs"] = []
        if isinstance(metadata["tag_slugs"], list):
            metadata["tag_slugs"].extend(tag_slugs)
        else:
            metadata["tag_slugs"] = tag_slugs
    
    # Deduplicate tag lists
    if "tag_ids" in metadata and isinstance(metadata["tag_ids"], list):
        metadata["tag_ids"] = list(set(metadata["tag_ids"]))
    if "tag_slugs" in metadata and isinstance(metadata["tag_slugs"], list):
        metadata["tag_slugs"] = list(set(metadata["tag_slugs"]))
    
    return metadata
