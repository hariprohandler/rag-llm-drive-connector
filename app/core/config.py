"""Configuration settings for the RAG application."""
import os
import logging
from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def get_env_files() -> list[str]:
    """
    Determine which environment files to load based on ENVIRONMENT variable.
    
    Priority order (later files override earlier ones):
    1. .env (base configuration)
    2. .env.{ENVIRONMENT} (environment-specific, e.g., .env.development, .env.production)
    
    If ENVIRONMENT is not set, only .env is loaded.
    """
    env_files = [".env"]  # Always load base .env first
    
    # Get environment from environment variable (not from .env file)
    environment = os.getenv("ENVIRONMENT", "").lower()
    
    if environment:
        env_file = f".env.{environment}"
        env_path = Path(env_file)
        if env_path.exists():
            env_files.append(env_file)
            logger.info(f"Loading environment-specific config from: {env_file}")
        else:
            logger.warning(f"Environment file {env_file} not found, using .env only")
    else:
        logger.info("ENVIRONMENT variable not set, using .env only")
    
    return env_files


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
    
    # Base URL for React frontend (used for post-auth redirects)
    # Example: http://localhost:3000, https://app.my-domain.com
    frontend_base_url: str = "http://localhost:3000"
    
    # Base URL for backend (used by frontend/Gradio to call API & auth endpoints)
    # Example: http://localhost:8000, https://api.my-domain.com
    backend_base_url: str = "http://localhost:8000"
    
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
        env_file = get_env_files()
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env files (e.g., Docker Compose variables)


settings = Settings()

