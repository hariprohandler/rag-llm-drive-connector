from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import User, UserSettings
from app.models.base import get_db
from app.services.auth_service import get_current_user
from app.helpers.logging_helper import ActivityLogger

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
        return {"organization_name": user_settings.organization_name or "Anukara"}
    
    # Return default if no settings exist
    return {"organization_name": "Anukara"}


@router.put("/organization")
async def update_organization_settings(
    fastapi_request: Request,
    request: OrganizationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update organization settings for the current user."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="settings_update",
        endpoint="/api/settings/organization",
        method="PUT",
        user_id=current_user.id,
        metadata={"organization_name": request.organization_name}
    )
    try:
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
        
        activity_logger.log_success()
        return {"organization_name": user_settings.organization_name}
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
