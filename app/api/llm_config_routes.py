from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import User
from app.models.base import get_db
from app.services.llm_service import (
    create_llm_config,
    get_llm_configs,
    get_llm_config,
    update_llm_config,
    delete_llm_config,
)
from app.services.auth_service import get_current_user


class LLMConfigRequest(BaseModel):
    provider: str  # 'openai', 'gemini', 'anthropic', 'custom'
    api_key: str
    model_name: Optional[str] = None
    base_url: Optional[str] = None  # For custom LLMs
    temperature: Optional[str] = "0"
    max_tokens: Optional[int] = None
    is_default: bool = False


class LLMConfigUpdateRequest(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[int] = None
    is_default: Optional[bool] = None


router = APIRouter(prefix="/api/llm-configs", tags=["llm-configs"])


@router.post("")
async def create_llm_config_endpoint(
    request: LLMConfigRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new LLM configuration."""
    try:
        config_obj = create_llm_config(
            db=db,
            user_id=current_user.id,
            provider=request.provider,
            api_key=request.api_key,
            model_name=request.model_name,
            base_url=request.base_url,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            is_default=request.is_default,
        )
        return config_obj.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_llm_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all LLM configurations for the current user."""
    configs = get_llm_configs(db, current_user.id)
    return [config.to_dict() for config in configs]


@router.get("/{config_id}")
async def get_llm_config_endpoint(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific LLM configuration."""
    config_obj = get_llm_config(db, current_user.id, config_id)
    if not config_obj:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    return config_obj.to_dict()


@router.put("/{config_id}")
async def update_llm_config_endpoint(
    config_id: int,
    request: LLMConfigUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an LLM configuration."""
    config_obj = update_llm_config(
        db=db,
        user_id=current_user.id,
        config_id=config_id,
        provider=request.provider,
        api_key=request.api_key,
        model_name=request.model_name,
        base_url=request.base_url,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        is_default=request.is_default,
    )
    if not config_obj:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    return config_obj.to_dict()


@router.delete("/{config_id}")
async def delete_llm_config_endpoint(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an LLM configuration."""
    success = delete_llm_config(db, current_user.id, config_id)
    if not success:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    return {"status": "success", "message": "LLM configuration deleted"}


