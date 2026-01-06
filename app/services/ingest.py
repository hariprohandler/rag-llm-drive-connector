"""Document ingestion pipeline for multiple sources."""
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.documents import Document
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import KnowledgeBase
import os


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Get a configured text splitter."""
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap
    )


def get_user_collection_name(user_id: str) -> str:
    """Get collection name for a user."""
    return f"user_{user_id}_documents"


def ingest_documents(
    documents: List[Document],
    collection_name: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Ingest documents into PgVector.
    
    Args:
        documents: List of LangChain Document objects
        collection_name: Collection name for the vectorstore
        metadata: Optional metadata to add to all documents
        
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
    embeddings = OpenAIEmbeddings(openai_api_key=settings.openai_api_key)
    
    PGVector.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        connection_string=settings.database_url,
    )
    
    return True


def ingest_local_files(
    file_paths: List[str],
    user_id: str,
    db: Optional[Session] = None,
    knowledge_base_name: Optional[str] = None
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
        existing_kbs = db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.source_type == "local_file",
            KnowledgeBase.is_active == True
        ).all()
    
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
    
    collection_name = get_user_collection_name(user_id)
    metadata = {"source": "local", "user_id": user_id}
    success = ingest_documents(all_documents, collection_name, metadata)
    
    # Create knowledge base entry if db provided
    kb_id = None
    if db and success:
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
                "duplicate_files": duplicate_files
            },
            document_count=len(all_documents),
            is_active=True
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        kb_id = kb.id
    
    return success, kb_id


def ingest_google_drive(
    folder_id: str,
    credentials: Any,
    user_id: str,
    db: Optional[Session] = None,
    knowledge_base_name: Optional[str] = None
) -> Tuple[bool, Optional[int]]:
    """
    Ingest documents from Google Drive.
    
    Returns:
        Tuple of (success, knowledge_base_id)
    """
    from langchain_community.document_loaders import GoogleDriveLoader
    
    try:
        loader = GoogleDriveLoader(
            folder_id=folder_id,
            credentials=credentials
        )
        documents = loader.load()
        
        # Add metadata
        for doc in documents:
            doc.metadata.update({
                "source": "google_drive",
                "folder_id": folder_id,
                "user_id": user_id
            })
        
        collection_name = get_user_collection_name(user_id)
        metadata = {"source": "google_drive", "user_id": user_id}
        success = ingest_documents(documents, collection_name, metadata)
        
        # Create knowledge base entry if db provided
        kb_id = None
        if db and success:
            kb_name = knowledge_base_name or f"Google Drive Folder ({folder_id})"
            kb = KnowledgeBase(
                user_id=user_id,
                name=kb_name,
                source_type="google_drive",
                source_id=folder_id,
                extra_metadata={"folder_id": folder_id},
                document_count=len(documents),
                is_active=True
            )
            db.add(kb)
            db.commit()
            db.refresh(kb)
            kb_id = kb.id
        
        return success, kb_id
    except Exception as e:
        print(f"Error loading from Google Drive: {e}")
        return False, None


def ingest_onedrive(
    folder_path: str,
    access_token: str,
    user_id: str,
    db: Optional[Session] = None,
    knowledge_base_name: Optional[str] = None
) -> Tuple[bool, Optional[int]]:
    """
    Ingest documents from OneDrive.
    
    Returns:
        Tuple of (success, knowledge_base_id)
    """
    from langchain_community.document_loaders import OneDriveLoader
    
    try:
        loader = OneDriveLoader(
            access_token=access_token,
            folder_path=folder_path
        )
        documents = loader.load()
        
        # Add metadata
        for doc in documents:
            doc.metadata.update({
                "source": "onedrive",
                "folder_path": folder_path,
                "user_id": user_id
            })
        
        collection_name = get_user_collection_name(user_id)
        metadata = {"source": "onedrive", "user_id": user_id}
        success = ingest_documents(documents, collection_name, metadata)
        
        # Create knowledge base entry if db provided
        kb_id = None
        if db and success:
            kb_name = knowledge_base_name or f"OneDrive Folder ({folder_path})"
            kb = KnowledgeBase(
                user_id=user_id,
                name=kb_name,
                source_type="onedrive",
                source_id=folder_path,
                extra_metadata={"folder_path": folder_path},
                document_count=len(documents),
                is_active=True
            )
            db.add(kb)
            db.commit()
            db.refresh(kb)
            kb_id = kb.id
        
        return success, kb_id
    except Exception as e:
        print(f"Error loading from OneDrive: {e}")
        return False, None

