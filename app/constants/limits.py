"""Limits and constraints constants."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    """Application limits and constraints."""
    
    # File Limits
    MAX_FILE_SIZE_MB: int = 100  # 100 MB per file
    MAX_FILES_PER_INGESTION: int = 100
    
    # Text Limits
    MAX_DOCUMENT_LENGTH: int = 1000000  # 1M characters
    MAX_CHUNK_SIZE: int = 10000
    MIN_CHUNK_SIZE: int = 100
    
    # Query Limits
    MAX_QUERY_LENGTH: int = 10000
    MAX_RETRIEVAL_K: int = 100
    MIN_RETRIEVAL_K: int = 1
    
    # Tag Limits
    MAX_TAGS_PER_DOCUMENT: int = 50
    MAX_TAG_NAME_LENGTH: int = 100
    
    # Organization Limits
    MAX_MEMBERS_PER_ORG: int = 1000
    MAX_GROUPS_PER_ORG: int = 100
    MAX_GROUP_NAME_LENGTH: int = 100
    
    # Connector Limits
    MAX_CONNECTORS_PER_USER: int = 10
    MAX_SYNC_JOBS_QUEUE: int = 100
    
    # Fine-tuning Limits
    MAX_FINE_TUNING_JOBS_PER_USER: int = 10
    MAX_TRAINING_DATA_SIZE_GB: float = 10.0
    
    # API Rate Limits
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
