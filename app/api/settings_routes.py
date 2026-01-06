from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import User, UserSettings
from app.models.base import get_db
from auth_service import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


class OrganizationSettingsRequest(BaseModel):
    organization_name: str


class OrganizationSettingsResponse(BaseModel):
    organization_name: str


@router.get("/organization")
async def get_organization_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get organization settings for the current user."""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    
    if user_settings:
        return {"organization_name": user_settings.organization_name or "RAG Chat Platform"}
    
    # Return default if no settings exist
    return {"organization_name": "RAG Chat Platform"}


@router.put("/organization")
async def update_organization_settings(
    request: OrganizationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update organization settings for the current user."""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    
    if user_settings:
        # Update existing settings
        user_settings.organization_name = request.organization_name
        user_settings.updated_at = datetime.utcnow()
    else:
        # Create new settings
        user_settings = UserSettings(
            id=current_user.id,
            user_id=current_user.id,
            organization_name=request.organization_name,
        )
        db.add(user_settings)
    
    db.commit()
    db.refresh(user_settings)
    
    return {"organization_name": user_settings.organization_name}
