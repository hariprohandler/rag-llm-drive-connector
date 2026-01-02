"""Document ingestion pipeline for multiple sources."""
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.documents import Document
from typing import List, Optional, Dict, Any
import config
import os


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    """Get a configured text splitter."""
    return RecursiveCharacterTextSplitter(
        chunk_size=config.settings.chunk_size,
        chunk_overlap=config.settings.chunk_overlap
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
    if metadata:
        for doc in documents:
            doc.metadata.update(metadata)
    
    # Split documents into chunks
    splitter = get_text_splitter()
    chunks = splitter.split_documents(documents)
    
    # Create embeddings and store in PgVector
    embeddings = OpenAIEmbeddings(openai_api_key=config.settings.openai_api_key)
    
    PGVector.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        connection_string=config.settings.database_url,
    )
    
    return True


def ingest_local_files(file_paths: List[str], user_id: str) -> bool:
    """Ingest local files (PDFs, text files, etc.)."""
    from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
    
    all_documents = []
    
    for file_path in file_paths:
        if not os.path.exists(file_path):
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
            # Add file metadata
            for doc in docs:
                doc.metadata.update({
                    "source": "local",
                    "file_path": file_path,
                    "file_name": os.path.basename(file_path),
                    "user_id": user_id
                })
            all_documents.extend(docs)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            continue
    
    if not all_documents:
        return False
    
    collection_name = get_user_collection_name(user_id)
    metadata = {"source": "local", "user_id": user_id}
    return ingest_documents(all_documents, collection_name, metadata)


def ingest_google_drive(
    folder_id: str,
    credentials: Any,
    user_id: str
) -> bool:
    """Ingest documents from Google Drive."""
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
        return ingest_documents(documents, collection_name, metadata)
    except Exception as e:
        print(f"Error loading from Google Drive: {e}")
        return False


def ingest_onedrive(
    folder_path: str,
    access_token: str,
    user_id: str
) -> bool:
    """Ingest documents from OneDrive."""
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
        return ingest_documents(documents, collection_name, metadata)
    except Exception as e:
        print(f"Error loading from OneDrive: {e}")
        return False

