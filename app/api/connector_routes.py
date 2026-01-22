"""API routes for connector management (Gmail, Outlook, Teams, Slack)."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import User, Connector
from app.models.base import get_db
from app.models.connector import ConnectorType, ConnectorStatus, SyncJob, SyncJobStatus
from app.services.auth_service import get_current_user
from app.services.auth_oauth import get_google_auth_url, get_microsoft_auth_url
from app.services.oauth_credential_service import (
    get_or_create_oauth_credentials,
    store_google_credentials,
    store_microsoft_credentials
)
from app.services.sync_worker import create_connector_sync_job
from app.core.config import settings
from app.helpers.logging_helper import ActivityLogger
from fastapi.responses import RedirectResponse
from datetime import datetime

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


class ConnectorCreateRequest(BaseModel):
    connector_type: str
    connector_name: str
    config: Optional[dict] = None
    auto_sync_enabled: bool = False
    sync_interval_hours: int = 24


class ConnectorUpdateRequest(BaseModel):
    connector_name: Optional[str] = None
    config: Optional[dict] = None
    auto_sync_enabled: Optional[bool] = None
    sync_interval_hours: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("")
async def list_connectors(
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all connectors for the current user."""
    connectors = db.query(Connector).filter(
        Connector.user_id == current_user.id
    ).order_by(desc(Connector.created_at)).all()
    
    return [connector.to_dict() for connector in connectors]


@router.get("/{connector_id}")
async def get_connector(
    connector_id: int,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific connector."""
    connector = db.query(Connector).filter(
        Connector.id == connector_id,
        Connector.user_id == current_user.id
    ).first()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    return connector.to_dict()


@router.post("")
async def create_connector(
    request: ConnectorCreateRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new connector."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="connector_create",
        endpoint="/api/connectors",
        method="POST",
        user_id=current_user.id,
        metadata={"connector_type": request.connector_type}
    )
    
    try:
        # Validate connector type
        try:
            connector_type = ConnectorType(request.connector_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid connector type: {request.connector_type}"
            )
        
        # Check if connector already exists for this type
        existing = db.query(Connector).filter(
            Connector.user_id == current_user.id,
            Connector.connector_type == connector_type,
            Connector.is_active == True
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"A {connector_type.value} connector already exists"
            )
        
        # Create connector
        connector = Connector(
            user_id=current_user.id,
            connector_type=connector_type,
            connector_name=request.connector_name,
            config=request.config or {},
            auto_sync_enabled=request.auto_sync_enabled,
            sync_interval_hours=request.sync_interval_hours,
            status=ConnectorStatus.DISCONNECTED,
            is_active=True
        )
        
        db.add(connector)
        db.commit()
        db.refresh(connector)
        
        activity_logger.log_success({"connector_id": connector.id})
        return connector.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{connector_id}")
async def update_connector(
    connector_id: int,
    request: ConnectorUpdateRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a connector."""
    connector = db.query(Connector).filter(
        Connector.id == connector_id,
        Connector.user_id == current_user.id
    ).first()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if request.connector_name is not None:
        connector.connector_name = request.connector_name
    if request.config is not None:
        connector.config = request.config
    if request.auto_sync_enabled is not None:
        connector.auto_sync_enabled = request.auto_sync_enabled
    if request.sync_interval_hours is not None:
        connector.sync_interval_hours = request.sync_interval_hours
    if request.is_active is not None:
        connector.is_active = request.is_active
    
    db.commit()
    db.refresh(connector)
    
    return connector.to_dict()


@router.delete("/{connector_id}")
async def delete_connector(
    connector_id: int,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a connector."""
    connector = db.query(Connector).filter(
        Connector.id == connector_id,
        Connector.user_id == current_user.id
    ).first()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    db.delete(connector)
    db.commit()
    
    return {"status": "success", "message": "Connector deleted"}


@router.get("/connect/{connector_type}")
async def connect_connector(
    connector_type: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initiate OAuth connection for a connector."""
    try:
        conn_type = ConnectorType(connector_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid connector type: {connector_type}")
    
    # Get or create connector
    connector = db.query(Connector).filter(
        Connector.user_id == current_user.id,
        Connector.connector_type == conn_type
    ).first()
    
    if not connector:
        # Create connector if it doesn't exist
        connector = Connector(
            user_id=current_user.id,
            connector_type=conn_type,
            connector_name=f"{conn_type.value.title()} Connector",
            status=ConnectorStatus.DISCONNECTED,
            is_active=True
        )
        db.add(connector)
        db.commit()
        db.refresh(connector)
    
    # Redirect to OAuth based on connector type
    if conn_type in [ConnectorType.GMAIL, ConnectorType.GOOGLE_DRIVE]:
        redirect_uri = f"{settings.backend_base_url}/api/connectors/callback/google"
        auth_url, state = get_google_auth_url(
            redirect_uri,
            request=request,
            user_id=current_user.id
        )
        # Store connector_id in state (we'll need to modify auth_oauth to support this)
        return RedirectResponse(url=auth_url)
    elif conn_type in [ConnectorType.OUTLOOK, ConnectorType.TEAMS, ConnectorType.ONEDRIVE]:
        redirect_uri = f"{settings.backend_base_url}/api/connectors/callback/microsoft"
        auth_url, state = get_microsoft_auth_url(
            redirect_uri,
            request=request,
            user_id=current_user.id
        )
        return RedirectResponse(url=auth_url)
    elif conn_type == ConnectorType.SLACK:
        # Slack uses a different OAuth flow - redirect to Slack OAuth
        # For now, return an error - Slack OAuth needs to be implemented
        raise HTTPException(
            status_code=501,
            detail="Slack OAuth connection not yet implemented. Please configure manually."
        )
    else:
        raise HTTPException(status_code=400, detail=f"OAuth not supported for {connector_type}")


@router.get("/callback/google")
async def google_connector_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Handle Google OAuth callback for connectors."""
    try:
        from app.services.auth_oauth import oauth_states, get_google_oauth_flow
        from googleapiclient.discovery import build
        
        if state not in oauth_states:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        state_data = oauth_states.pop(state)
        redirect_uri = state_data["redirect_uri"]
        
        # Get OAuth flow and fetch token
        flow = get_google_oauth_flow(redirect_uri)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Store credentials
        store_google_credentials(db, current_user.id, credentials)
        
        # Update connector status
        # Find connectors that use Google OAuth
        connectors = db.query(Connector).filter(
            Connector.user_id == current_user.id,
            Connector.connector_type.in_([ConnectorType.GMAIL, ConnectorType.GOOGLE_DRIVE])
        ).all()
        
        for connector in connectors:
            connector.status = ConnectorStatus.CONNECTED
            connector.error_message = None
            oauth_cred = get_or_create_oauth_credentials(db, current_user.id, "google")
            if oauth_cred:
                connector.oauth_credential_id = oauth_cred.id
        
        db.commit()
        
        return RedirectResponse(
            url=f"{settings.frontend_base_url}/app/tools?connected=google",
            status_code=302
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback/microsoft")
async def microsoft_connector_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Handle Microsoft OAuth callback for connectors."""
    try:
        from app.services.auth_oauth import oauth_states
        import msal
        
        if state not in oauth_states:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        state_data = oauth_states.pop(state)
        redirect_uri = state_data["redirect_uri"]
        
        authority = f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}"
        app = msal.ConfidentialClientApplication(
            settings.microsoft_client_id,
            authority=authority,
            client_credential=settings.microsoft_client_secret
        )
        
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=["openid", "email", "profile", "Files.Read.All", "Mail.Read", "Chat.Read"],
            redirect_uri=redirect_uri
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result.get('error_description'))
        
        # Store credentials
        store_microsoft_credentials(
            db,
            current_user.id,
            result.get("access_token"),
            result.get("refresh_token"),
            result.get("expires_in")
        )
        
        # Update connector status
        connectors = db.query(Connector).filter(
            Connector.user_id == current_user.id,
            Connector.connector_type.in_([
                ConnectorType.OUTLOOK,
                ConnectorType.TEAMS,
                ConnectorType.ONEDRIVE
            ])
        ).all()
        
        for connector in connectors:
            connector.status = ConnectorStatus.CONNECTED
            connector.error_message = None
            oauth_cred = get_or_create_oauth_credentials(db, current_user.id, "microsoft")
            if oauth_cred:
                connector.oauth_credential_id = oauth_cred.id
        
        db.commit()
        
        return RedirectResponse(
            url=f"{settings.frontend_base_url}/app/tools?connected=microsoft",
            status_code=302
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{connector_id}/sync")
async def sync_connector(
    connector_id: int,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a sync for a connector."""
    connector = db.query(Connector).filter(
        Connector.id == connector_id,
        Connector.user_id == current_user.id
    ).first()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.status != ConnectorStatus.CONNECTED:
        raise HTTPException(
            status_code=400,
            detail=f"Connector is not connected (status: {connector.status.value})"
        )
    
    # Check for active sync jobs
    active_jobs = db.query(SyncJob).filter(
        SyncJob.connector_id == connector_id,
        SyncJob.status.in_([
            SyncJobStatus.PENDING,
            SyncJobStatus.QUEUED,
            SyncJobStatus.PROCESSING,
            SyncJobStatus.INDEXING
        ])
    ).count()
    
    if active_jobs > 0:
        raise HTTPException(
            status_code=400,
            detail="A sync is already in progress for this connector"
        )
    
    # Create sync job
    sync_job = create_connector_sync_job(
        db=db,
        connector_id=connector_id,
        user_id=current_user.id,
        organization_id=connector.organization_id,
        knowledge_base_id=None,
        sync_scope={"manual_trigger": True},
        priority=5
    )
    
    return {
        "status": "queued",
        "job_id": sync_job.id,
        "message": f"Sync queued for {connector.connector_type.value}",
        "job": sync_job.to_dict()
    }
