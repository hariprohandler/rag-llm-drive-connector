"""Service for managing LLM configurations."""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import LLMConfig
from app.core.config import settings
from cryptography.fernet import Fernet
import os
import base64


def get_encryption_key() -> bytes:
    """Get or generate encryption key for API keys."""
    key = settings.encryption_key or os.getenv("ENCRYPTION_KEY")
    if not key:
        # In production, this should be set as env var
        # For development, generate a key and store it
        key = Fernet.generate_key()
        print(f"WARNING: Generated encryption key. Set ENCRYPTION_KEY={key.decode()} in production!")
        return key
    else:
        # If key is provided as string, encode it
        if isinstance(key, str):
            # If it's a base64-encoded key, decode it
            try:
                return base64.urlsafe_b64decode(key)
            except:
                # If not base64, treat as raw string and encode
                return key.encode()
        return key


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key."""
    f = Fernet(get_encryption_key())
    return f.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key."""
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_key.encode()).decode()


def create_llm_config(
    db: Session,
    user_id: str,
    provider: str,
    api_key: str,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[str] = "0",
    max_tokens: Optional[int] = None,
    is_default: bool = False
) -> LLMConfig:
    """
    Create a new LLM configuration for a user.
    
    Args:
        db: Database session
        user_id: User ID
        provider: LLM provider ('openai', 'gemini', 'anthropic', 'custom')
        api_key: API key (will be encrypted)
        model_name: Optional model name
        base_url: Optional base URL for custom LLMs
        temperature: Temperature setting
        max_tokens: Maximum tokens
        is_default: Whether this should be the default config
        
    Returns:
        Created LLMConfig instance
    """
    # If setting as default, unset other defaults
    if is_default:
        db.query(LLMConfig).filter(
            LLMConfig.user_id == user_id,
            LLMConfig.is_default == True
        ).update({"is_default": False})
    
    encrypted_key = encrypt_api_key(api_key)
    
    llm_config = LLMConfig(
        user_id=user_id,
        provider=provider,
        api_key=encrypted_key,
        model_name=model_name,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        is_default=is_default,
        is_active=True
    )
    
    db.add(llm_config)
    db.commit()
    db.refresh(llm_config)
    
    return llm_config


def get_llm_configs(db: Session, user_id: str, include_inactive: bool = False) -> List[LLMConfig]:
    """Get all LLM configurations for a user."""
    query = db.query(LLMConfig).filter(LLMConfig.user_id == user_id)
    if not include_inactive:
        query = query.filter(LLMConfig.is_active == True)
    return query.order_by(LLMConfig.is_default.desc(), LLMConfig.created_at.desc()).all()


def get_llm_config(db: Session, user_id: str, config_id: int, include_inactive: bool = False) -> Optional[LLMConfig]:
    """Get a specific LLM configuration."""
    query = db.query(LLMConfig).filter(
        LLMConfig.id == config_id,
        LLMConfig.user_id == user_id
    )
    if not include_inactive:
        query = query.filter(LLMConfig.is_active == True)
    return query.first()


def update_llm_config(
    db: Session,
    user_id: str,
    config_id: int,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[str] = None,
    max_tokens: Optional[int] = None,
    is_default: Optional[bool] = None,
    is_active: Optional[bool] = None
) -> Optional[LLMConfig]:
    """Update an LLM configuration."""
    config = get_llm_config(db, user_id, config_id, include_inactive=True)
    if not config:
        return None
    
    if provider is not None:
        config.provider = provider
    if api_key is not None:
        config.api_key = encrypt_api_key(api_key)
    if model_name is not None:
        config.model_name = model_name
    if base_url is not None:
        config.base_url = base_url
    if temperature is not None:
        config.temperature = temperature
    if max_tokens is not None:
        config.max_tokens = max_tokens
    if is_default is not None:
        if is_default:
            # Unset other defaults
            db.query(LLMConfig).filter(
                LLMConfig.user_id == user_id,
                LLMConfig.is_default == True,
                LLMConfig.id != config_id
            ).update({"is_default": False})
        config.is_default = is_default
    if is_active is not None:
        config.is_active = is_active
    
    db.commit()
    db.refresh(config)
    
    return config


def delete_llm_config(db: Session, user_id: str, config_id: int) -> bool:
    """Soft delete an LLM configuration (set is_active to False)."""
    config = get_llm_config(db, user_id, config_id, include_inactive=True)
    if not config:
        return False
    
    config.is_active = False
    # If this was the default, unset it
    if config.is_default:
        config.is_default = False
    db.commit()
    
    return True

