"""Configuration settings for the RAG application."""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database - Master (for writes)
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
    
    # Database - Slave (for reads, optional - falls back to master if not set)
    database_read_url: Optional[str] = None
    
    # MongoDB for activity logging
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "rag_activity_logs"
    
    # OpenAI (default fallback)
    openai_api_key: Optional[str] = None
    
    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/auth/callback/google"
    
    # Microsoft OAuth
    microsoft_client_id: Optional[str] = None
    microsoft_client_secret: Optional[str] = None
    microsoft_tenant_id: Optional[str] = None
    microsoft_redirect_uri: str = "http://localhost:8000/auth/callback/microsoft"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    gradio_port: int = 7860
    
    # RAG settings
    collection_name: str = "documents"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_k: int = 4
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0
    
    # Authentication
    jwt_secret_key: str = ""  # Override with dedicated secret key
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 43200  # 30 days
    
    # Encryption key for API keys
    encryption_key: Optional[str] = None
    
    # OAuth scopes
    google_scopes: list = [
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    microsoft_scopes: list = [
        "Files.Read.All"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

