from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import User, UserSettings
from app.models.base import get_db
from app.services.auth_service import get_current_user
from app.helpers.logging_helper import ActivityLogger
from app.helpers.vector_db_helper import check_pgvector_compatibility, test_vector_db_connection

router = APIRouter(prefix="/api/settings", tags=["settings"])


class OrganizationSettingsRequest(BaseModel):
    organization_name: str


class OrganizationSettingsResponse(BaseModel):
    organization_name: str


class VectorDBSettingsRequest(BaseModel):
    vector_db_url: str
    enable: bool = True


class VectorDBSettingsResponse(BaseModel):
    vector_db_url: Optional[str] = None
    vector_db_enabled: bool
    vector_db_config: Optional[dict] = None


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


@router.get("/vector-db")
async def get_vector_db_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get vector database settings for the current user."""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    
    if user_settings:
        return {
            "vector_db_url": user_settings.vector_db_url,
            "vector_db_enabled": user_settings.vector_db_enabled or False,
            "vector_db_config": user_settings.vector_db_config
        }
    
    # Return default if no settings exist
    return {
        "vector_db_url": None,
        "vector_db_enabled": False,
        "vector_db_config": None
    }


@router.put("/vector-db")
async def update_vector_db_settings(
    fastapi_request: Request,
    request: VectorDBSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update vector database settings for the current user."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="settings_update",
        endpoint="/api/settings/vector-db",
        method="PUT",
        user_id=current_user.id,
        metadata={"vector_db_url": request.vector_db_url, "enable": request.enable}
    )
    
    try:
        # Check compatibility before enabling
        if request.enable:
            compatible, details = check_pgvector_compatibility(request.vector_db_url)
            if not compatible:
                activity_logger.log_error(f"Vector DB compatibility check failed: {details.get('error', 'Unknown error')}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Vector database compatibility check failed: {details.get('error', 'Unknown error')}. "
                           f"Please ensure the database has pgvector extension installed."
                )
            
            # Test connection
            success, message = test_vector_db_connection(request.vector_db_url)
            if not success:
                activity_logger.log_error(f"Vector DB connection test failed: {message}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Vector database connection test failed: {message}"
                )
        
        user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
        
        if user_settings:
            # Update existing settings
            user_settings.vector_db_url = request.vector_db_url if request.enable else None
            user_settings.vector_db_enabled = request.enable
            if request.enable:
                # Store compatibility check details
                compatible, details = check_pgvector_compatibility(request.vector_db_url)
                user_settings.vector_db_config = {
                    "compatible": compatible,
                    "pgvector_installed": details.get("pgvector_installed", False),
                    "pgvector_version": details.get("pgvector_version"),
                    "postgres_version": details.get("postgres_version"),
                    "verified_at": datetime.utcnow().isoformat()
                }
            else:
                user_settings.vector_db_config = None
            user_settings.updated_at = datetime.utcnow()
        else:
            # Create new settings
            vector_db_config = None
            if request.enable:
                compatible, details = check_pgvector_compatibility(request.vector_db_url)
                vector_db_config = {
                    "compatible": compatible,
                    "pgvector_installed": details.get("pgvector_installed", False),
                    "pgvector_version": details.get("pgvector_version"),
                    "postgres_version": details.get("postgres_version"),
                    "verified_at": datetime.utcnow().isoformat()
                }
            
            user_settings = UserSettings(
                id=current_user.id,
                user_id=current_user.id,
                vector_db_url=request.vector_db_url if request.enable else None,
                vector_db_enabled=request.enable,
                vector_db_config=vector_db_config
            )
            db.add(user_settings)
        
        db.commit()
        db.refresh(user_settings)
        
        activity_logger.log_success()
        return {
            "vector_db_url": user_settings.vector_db_url,
            "vector_db_enabled": user_settings.vector_db_enabled,
            "vector_db_config": user_settings.vector_db_config
        }
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector-db/test")
async def test_vector_db(
    fastapi_request: Request,
    request: VectorDBSettingsRequest,
    current_user: User = Depends(get_current_user),
):
    """Test vector database connection and compatibility without saving."""
    try:
        # Check compatibility
        compatible, details = check_pgvector_compatibility(request.vector_db_url)
        if not compatible:
            return {
                "success": False,
                "compatible": False,
                "message": details.get("error", "Compatibility check failed"),
                "details": details
            }
        
        # Test connection
        success, message = test_vector_db_connection(request.vector_db_url)
        return {
            "success": success,
            "compatible": compatible,
            "message": message,
            "details": details
        }
    except Exception as e:
        return {
            "success": False,
            "compatible": False,
            "message": str(e),
            "details": None
        }
