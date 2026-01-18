"""Default values constants."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DefaultValues:
    """Default values used throughout the application."""
    
    # RAG Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RETRIEVAL_K: int = 4
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    
    # Batch Processing
    EMBEDDING_BATCH_SIZE: int = 100
    INGESTION_BATCH_SIZE: int = 200
    
    # Sync Configuration
    SYNC_INTERVAL_HOURS: int = 24
    SYNC_PRIORITY: int = 5  # Default priority (1-10, lower = higher priority)
    
    # Timeouts
    OPENAI_TIMEOUT: float = 60.0
    HTTP_REQUEST_TIMEOUT: int = 30
    DATABASE_QUERY_TIMEOUT: int = 30
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Organization
    DEFAULT_ORG_NAME: str = "Anukara"
    
    # Collection/Table Names
    DEFAULT_COLLECTION_NAME: str = "documents"
    
    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: int = 1
    
    # JWT
    JWT_EXPIRE_MINUTES: int = 43200  # 30 days
    JWT_ALGORITHM: str = "HS256"
