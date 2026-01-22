"""Document ingestion pipeline for multiple sources."""
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import KnowledgeBase, UserSettings
from app.models.knowledge_base import safe_query_knowledge_bases
from app.models.user_settings import safe_query_user_settings
from app.helpers.vector_db_helper import get_collection_name, get_user_vector_db_url, get_vector_table_name
from app.constants import DefaultValues, SourceType
import os


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Get a configured text splitter."""
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap
    )


def get_user_collection_name(user_id: str, knowledge_base_id: Optional[int] = None) -> str:
    """
    Get collection name for a user.
    
    For better organization, we organize collections by knowledge base:
    - If knowledge_base_id is provided: user_{user_id}_kb_{kb_id}
    - Otherwise: user_{user_id}_documents (for backward compatibility)
    """
    return get_collection_name(user_id, knowledge_base_id)


def ingest_documents(
    documents: List[Document],
    collection_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    db_url: Optional[str] = None,
    source_type: Optional[str] = None
) -> bool:
    """
    Ingest documents into PgVector.
    
    For petabyte-scale performance, documents are organized by:
    - Source type (for future table separation - currently uses collection filtering)
    - Knowledge base ID (for fine-grained access)
    - Collection name (for logical grouping within source tables)
    
    Args:
        documents: List of LangChain Document objects
        collection_name: Collection name for the vectorstore
        metadata: Optional metadata to add to all documents
        db_url: Optional database URL (uses default from settings if not provided)
        source_type: Optional source type (e.g., 'slack', 'teams', 'onedrive') for table organization
        
    Returns:
        True if successful
    """
    if not documents:
        return False
    
    # Add metadata to documents if provided
    # Sanitize metadata to remove NUL characters that can cause database errors
    if metadata:
        sanitized_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, str):
                sanitized_metadata[key] = value.replace('\x00', '')
            else:
                sanitized_metadata[key] = value
        for doc in documents:
            # Also sanitize existing metadata
            sanitized_doc_metadata = {}
            for key, value in doc.metadata.items():
                if isinstance(value, str):
                    sanitized_doc_metadata[key] = value.replace('\x00', '')
                else:
                    sanitized_doc_metadata[key] = value
            doc.metadata = sanitized_doc_metadata
            doc.metadata.update(sanitized_metadata)
    
    # Ensure source_type is in metadata for efficient filtering
    # This enables future table separation while maintaining backward compatibility
    if source_type:
        for doc in documents:
            if "source_type" not in doc.metadata:
                doc.metadata["source_type"] = source_type
            # Also add for collection-based filtering (until tables are migrated)
            if "source" not in doc.metadata:
                doc.metadata["source"] = source_type
    
    # Split documents into chunks
    splitter = get_text_splitter()
    chunks = splitter.split_documents(documents)
    
    # Sanitize chunks - remove NUL characters from content and metadata
    for chunk in chunks:
        # Sanitize content
        if chunk.page_content:
            chunk.page_content = chunk.page_content.replace('\x00', '')
        
        # Sanitize metadata (recursively handle nested structures)
        if chunk.metadata:
            sanitized_metadata = {}
            for key, value in chunk.metadata.items():
                if isinstance(value, str):
                    sanitized_metadata[key] = value.replace('\x00', '')
                elif isinstance(value, dict):
                    # Handle nested dictionaries
                    sanitized_dict = {}
                    for k, v in value.items():
                        if isinstance(v, str):
                            sanitized_dict[k] = v.replace('\x00', '')
                        else:
                            sanitized_dict[k] = v
                    sanitized_metadata[key] = sanitized_dict
                else:
                    sanitized_metadata[key] = value
            chunk.metadata = sanitized_metadata
    
    # Create embeddings and store in PgVector
    # Use batch processing for faster embedding generation
    embeddings = OpenAIEmbeddings(
        openai_api_key=settings.openai_api_key,
        chunk_size=DefaultValues.EMBEDDING_BATCH_SIZE,
        max_retries=DefaultValues.MAX_RETRIES,
        request_timeout=DefaultValues.OPENAI_TIMEOUT
    )
    
    # Use user-configured DB URL if provided, otherwise use default
    vector_db_url = db_url or settings.database_url
    
    # Use add_documents with batch processing for better performance
    # Check if collection exists, if not create it
    vectorstore = PGVector(
        collection_name=collection_name,
        connection=vector_db_url,
        embeddings=embeddings,
        use_jsonb=True,  # Use JSONB for metadata as recommended
    )
    
    # Ensure tables are created with the correct schema (langchain_postgres uses uuid, not id)
    # This will create tables if they don't exist, or verify the schema matches
    try:
        vectorstore.create_tables_if_not_exists()
    except Exception as e:
        print(f"Warning: Could not create/verify tables: {e}")
        # Continue anyway - table might already exist
    
    # Add documents in batches to avoid memory issues and improve performance
    # Batch size is configured in DefaultValues for consistency
    batch_size = DefaultValues.INGESTION_BATCH_SIZE
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    
    # Use add_documents which handles batching internally for embeddings
    # This is more efficient than manual batching
    try:
        # Try adding all documents at once (PGVector handles batching internally)
        vectorstore.add_documents(chunks)
    except Exception as e:
        print(f"Error adding all documents at once, falling back to batches: {e}")
        # Fallback to manual batching if needed
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            try:
                vectorstore.add_documents(batch)
            except Exception as batch_error:
                print(f"Error adding batch {i//batch_size + 1}/{total_batches}: {batch_error}")
                # Try adding documents one by one if batch fails
                for chunk in batch:
                    try:
                        vectorstore.add_documents([chunk])
                    except Exception as chunk_error:
                        print(f"Error adding individual chunk: {chunk_error}")
                        continue
    
    return True


def ingest_local_files(
    file_paths: List[str],
    user_id: str,
    db: Optional[Session] = None,
    knowledge_base_name: Optional[str] = None,
    knowledge_base_id: Optional[int] = None
) -> Tuple[bool, Optional[int]]:
    """
    Ingest local files (PDFs, text files, etc.).
    
    Files are stored in the 'knowledge_bases' table with:
    - source_type = 'local_file'
    - extra_metadata contains file information (file_name, file_path, file_size, etc.)
    
    Returns:
        Tuple of (success, knowledge_base_id)
    """
    from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
    import hashlib
    
    all_documents = []
    file_metadata = []
    duplicate_files = []
    
    # Check for duplicate files by comparing file name and size
    existing_kbs = []
    if db:
        try:
            existing_kbs = safe_query_knowledge_bases(
                db,
                {
                    "user_id": user_id,
                    "source_type": "local_file",
                    "is_active": True
                }
            )
        except Exception as e:
            # If query fails, log and continue without duplicate detection
            print(f"Warning: Could not query existing knowledge bases for duplicate detection: {e}")
            db.rollback()
            existing_kbs = []
    
    # Build a set of existing files (name + size) for duplicate detection
    existing_files = set()
    for kb in existing_kbs:
        if kb.extra_metadata and "files" in kb.extra_metadata:
            for file_info in kb.extra_metadata["files"]:
                file_key = (file_info.get("file_name", ""), file_info.get("file_size", 0))
                existing_files.add(file_key)
    
    # Track files in current batch to detect duplicates within the batch
    current_batch_files = set()
    
    for file_path in file_paths:
        # Sanitize file path - remove NUL characters and other problematic characters
        file_path = file_path.replace('\x00', '') if file_path else ""
        if not file_path or not os.path.exists(file_path):
            continue
            
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext == '.pdf':
                loader = PyPDFLoader(file_path)
            elif file_ext in ['.txt', '.md']:
                loader = TextLoader(file_path)
            elif file_ext in ['.docx', '.doc']:
                loader = Docx2txtLoader(file_path)
            else:
                continue
                
            # Load documents - this can be slow for large files
            # Consider adding progress callback here if needed
            docs = loader.load()
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            # Sanitize file path for metadata storage
            sanitized_path = file_path.replace('\x00', '')
            file_name = os.path.basename(sanitized_path)
            
            # Check for duplicate file (same name and size)
            file_key = (file_name, file_size)
            is_duplicate = file_key in existing_files
            
            file_metadata.append({
                "file_name": file_name,
                "file_path": sanitized_path,
                "file_size": file_size,
                "file_type": file_ext,
                "is_duplicate": is_duplicate
            })
            
            if is_duplicate:
                duplicate_files.append(file_name)
                # Mark documents as duplicate in metadata
                for doc in docs:
                    doc.metadata["is_duplicate"] = True
                    doc.metadata["duplicate_note"] = f"Duplicate copy of {file_name}"
            
            # Add file metadata and sanitize document content
            sanitized_path = file_path.replace('\x00', '') if file_path else ""
            sanitized_name = os.path.basename(sanitized_path) if sanitized_path else ""
            for doc in docs:
                # Sanitize document content - remove NUL characters
                if doc.page_content:
                    doc.page_content = doc.page_content.replace('\x00', '')
                
                # Sanitize existing metadata
                sanitized_doc_metadata = {}
                for key, value in doc.metadata.items():
                    if isinstance(value, str):
                        sanitized_doc_metadata[key] = value.replace('\x00', '')
                    else:
                        sanitized_doc_metadata[key] = value
                doc.metadata = sanitized_doc_metadata
                
                # Add new metadata (already sanitized)
                doc.metadata.update({
                    "source": "local",
                    "file_path": sanitized_path,
                    "file_name": sanitized_name,
                    "user_id": user_id
                })
            all_documents.extend(docs)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            continue
    
    if not all_documents:
        return False, None
    
    # Get user's vector DB configuration if available
    user_vector_db_url = None
    if db:
        try:
            user_settings = safe_query_user_settings(db, user_id)
        except Exception as e:
            print(f"Warning: Could not query user settings: {e}")
            db.rollback()
            user_settings = None
        user_vector_db_url = get_user_vector_db_url(user_settings)
    
    # Create knowledge base entry first if db provided (to get kb_id for collection naming)
    # IMPORTANT: Create KB even if ingestion might fail, so we can track what was attempted
    kb_id = knowledge_base_id
    if db and not kb_id:
        try:
            # Build knowledge base name with duplicate indicator if needed
            duplicate_note = ""
            if duplicate_files:
                duplicate_note = f" ({len(duplicate_files)} duplicate file(s): {', '.join(duplicate_files[:3])}{'...' if len(duplicate_files) > 3 else ''})"
            
            kb_name = knowledge_base_name or f"Local Files ({len(file_paths)} files){duplicate_note}"
            # Sanitize file paths - remove NUL characters and other problematic characters
            sanitized_paths = [path.replace('\x00', '') for path in file_paths]
            # Store sanitized file paths in extra_metadata instead of source_id to avoid NUL character issues
            kb = KnowledgeBase(
                user_id=user_id,
                name=kb_name,
                source_type="local_file",
                source_id="local_files",  # Use a simple identifier instead of file paths
                extra_metadata={
                    "files": file_metadata, 
                    "file_paths": sanitized_paths,
                    "has_duplicates": len(duplicate_files) > 0,
                    "duplicate_files": duplicate_files,
                },
                document_count=len(all_documents),
                is_active=True
            )
            db.add(kb)
            db.flush()  # Flush to get the ID without committing
            kb_id = kb.id
            db.commit()  # Now commit
            db.refresh(kb)  # Refresh to ensure we have the latest state
            print(f"Successfully created knowledge base with ID: {kb_id} for user: {user_id}, name: {kb_name}")
        except Exception as e:
            print(f"ERROR creating knowledge base entry: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            # Don't fail the whole ingestion if KB creation fails
            # The documents are already in the vector DB if success=True
            # But we should still return the kb_id as None so the caller knows
    
    # Use knowledge_base-specific collection name for better organization
    source_type = "local_file"
    collection_name = get_user_collection_name(user_id, kb_id)
    metadata = {
        "source": "local",
        "user_id": user_id,
        "source_type": source_type
    }
    # Add knowledge_base_id to metadata if available
    if kb_id:
        metadata["knowledge_base_id"] = kb_id
    
    success = ingest_documents(all_documents, collection_name, metadata, db_url=user_vector_db_url, source_type=source_type)
    
    # Update knowledge base with ingestion success status
    if db and kb_id:
        try:
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if kb:
                if not kb.extra_metadata:
                    kb.extra_metadata = {}
                kb.extra_metadata["ingestion_success"] = success
                db.commit()
        except Exception as e:
            print(f"Warning: Could not update KB ingestion status: {e}")
    
    return success, kb_id


def ingest_google_drive(
    folder_id: str,
    credentials: Any,
    user_id: str,
    db: Optional[Session] = None,
    knowledge_base_name: Optional[str] = None,
    knowledge_base_id: Optional[int] = None
) -> Tuple[bool, Optional[int]]:
    """
    Ingest documents from Google Drive.
    
    Returns:
        Tuple of (success, knowledge_base_id)
    """
    from langchain_community.document_loaders import GoogleDriveLoader
    
    try:
        # Get user's vector DB configuration if available
        user_vector_db_url = None
        if db:
            try:
                user_settings = safe_query_user_settings(db, user_id)
            except Exception as e:
                print(f"Warning: Could not query user settings: {e}")
                db.rollback()
                user_settings = None
            user_vector_db_url = get_user_vector_db_url(user_settings)
        
        # Create knowledge base entry first (to get kb_id for collection naming)
        kb_id = knowledge_base_id
        if db and not kb_id:
            kb_name = knowledge_base_name or f"Google Drive Folder ({folder_id})"
            kb = KnowledgeBase(
                user_id=user_id,
                name=kb_name,
                source_type="google_drive",
                source_id=folder_id,
                extra_metadata={"folder_id": folder_id},
                document_count=0,  # Will update after ingestion
                is_active=True
            )
            db.add(kb)
            db.flush()
            kb_id = kb.id
            db.commit()
            db.refresh(kb)
        
        loader = GoogleDriveLoader(
            folder_id=folder_id,
            credentials=credentials
        )
        documents = loader.load()
        
        # Add metadata with knowledge_base_id
        for doc in documents:
            doc_metadata = {
                "source": "google_drive",
                "folder_id": folder_id,
                "user_id": user_id,
                "source_type": "google_drive"
            }
            if kb_id:
                doc_metadata["knowledge_base_id"] = kb_id
            doc.metadata.update(doc_metadata)
        
        # Use knowledge_base-specific collection name
        source_type = SourceType.GOOGLE_DRIVE.value
        collection_name = get_user_collection_name(user_id, kb_id)
        metadata = {"source": "google_drive", "user_id": user_id, "source_type": source_type}
        if kb_id:
            metadata["knowledge_base_id"] = kb_id
        success = ingest_documents(documents, collection_name, metadata, db_url=user_vector_db_url, source_type=source_type)
        
        # Update knowledge base with document count and ingestion status
        if db and kb_id:
            try:
                kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
                if kb:
                    kb.document_count = len(documents)
                    if not kb.extra_metadata:
                        kb.extra_metadata = {"folder_id": folder_id}
                    kb.extra_metadata["ingestion_success"] = success
                    db.commit()
            except Exception as e:
                print(f"Warning: Could not update KB: {e}")
        
        return success, kb_id
    except Exception as e:
        print(f"Error loading from Google Drive: {e}")
        return False, None


def ingest_onedrive(
    folder_path: str,
    access_token: str,
    user_id: str,
    db: Optional[Session] = None,
    knowledge_base_name: Optional[str] = None,
    knowledge_base_id: Optional[int] = None
) -> Tuple[bool, Optional[int]]:
    """
    Ingest documents from OneDrive.
    
    Returns:
        Tuple of (success, knowledge_base_id)
    """
    from langchain_community.document_loaders import OneDriveLoader
    
    try:
        # Get user's vector DB configuration if available
        user_vector_db_url = None
        if db:
            try:
                user_settings = safe_query_user_settings(db, user_id)
            except Exception as e:
                print(f"Warning: Could not query user settings: {e}")
                db.rollback()
                user_settings = None
            user_vector_db_url = get_user_vector_db_url(user_settings)
        
        # Create knowledge base entry first (to get kb_id for collection naming)
        kb_id = knowledge_base_id
        if db and not kb_id:
            kb_name = knowledge_base_name or f"OneDrive Folder ({folder_path})"
            kb = KnowledgeBase(
                user_id=user_id,
                name=kb_name,
                source_type="onedrive",
                source_id=folder_path,
                extra_metadata={"folder_path": folder_path},
                document_count=0,  # Will update after ingestion
                is_active=True
            )
            db.add(kb)
            db.flush()
            kb_id = kb.id
            db.commit()
            db.refresh(kb)
        
        loader = OneDriveLoader(
            access_token=access_token,
            folder_path=folder_path
        )
        documents = loader.load()
        
        # Add metadata with knowledge_base_id
        for doc in documents:
            doc_metadata = {
                "source": "onedrive",
                "folder_path": folder_path,
                "user_id": user_id,
                "source_type": "onedrive"
            }
            if kb_id:
                doc_metadata["knowledge_base_id"] = kb_id
            doc.metadata.update(doc_metadata)
        
        # Use knowledge_base-specific collection name
        source_type = SourceType.ONEDRIVE.value
        collection_name = get_user_collection_name(user_id, kb_id)
        metadata = {"source": "onedrive", "user_id": user_id, "source_type": source_type}
        if kb_id:
            metadata["knowledge_base_id"] = kb_id
        success = ingest_documents(documents, collection_name, metadata, db_url=user_vector_db_url, source_type=source_type)
        
        # Update knowledge base with document count and ingestion status
        if db and kb_id:
            try:
                kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
                if kb:
                    kb.document_count = len(documents)
                    if not kb.extra_metadata:
                        kb.extra_metadata = {"folder_path": folder_path}
                    kb.extra_metadata["ingestion_success"] = success
                    db.commit()
            except Exception as e:
                print(f"Warning: Could not update KB: {e}")
        
        return success, kb_id
    except Exception as e:
        print(f"Error loading from OneDrive: {e}")
        return False, None

