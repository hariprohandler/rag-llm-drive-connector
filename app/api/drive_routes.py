"""API routes for Google Drive and OneDrive integration."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import User
from app.models.base import get_db
from app.services.auth_service import get_current_user
from app.services.auth_oauth import get_google_auth_url, handle_google_callback, get_microsoft_auth_url, handle_microsoft_callback
from app.services.oauth_credential_service import (
    get_google_credentials,
    get_microsoft_access_token,
    store_google_credentials,
    store_microsoft_credentials,
    get_or_create_oauth_credentials
)
from app.services.drive_service import list_google_drive_files, list_onedrive_files
from app.services.ingestion_task import create_ingestion_task, get_task, run_ingestion_task
from app.core.config import settings
from fastapi.responses import RedirectResponse


router = APIRouter(prefix="/api/drive", tags=["drive"])


class FileItem(BaseModel):
    id: str
    name: str
    type: str  # 'file' or 'folder'
    size: Optional[str] = None
    modified_time: Optional[str] = None
    path: Optional[str] = None  # For OneDrive folder paths


class IngestRequest(BaseModel):
    items: List[FileItem]
    knowledge_base_name: Optional[str] = None


# Google Drive OAuth for Drive access
@router.get("/connect/google")
async def connect_google_drive(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Initiate Google Drive OAuth connection."""
    redirect_uri = f"{settings.backend_base_url}/api/drive/callback/google"
    # Store user_id in state to ensure credentials are associated with the correct user
    auth_url, state = get_google_auth_url(redirect_uri, request=request, user_id=current_user.id)
    return RedirectResponse(url=auth_url)


@router.get("/callback/google")
async def google_drive_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Handle Google Drive OAuth callback and store credentials."""
    try:
        from app.services.auth_oauth import oauth_states, get_google_oauth_flow
        from googleapiclient.discovery import build
        from app.core.config import settings
        
        if state not in oauth_states:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        state_data = oauth_states.pop(state)
        redirect_uri = state_data["redirect_uri"]
        
        # Verify that the user_id in state matches the current authenticated user
        # This ensures credentials are always associated with the correct user
        stored_user_id = state_data.get("user_id")
        if stored_user_id and stored_user_id != current_user.id:
            raise HTTPException(
                status_code=403, 
                detail="User mismatch: The Google account being connected does not match the logged-in user"
            )
        
        # Get OAuth flow and fetch token
        flow = get_google_oauth_flow(redirect_uri)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Store Google Drive credentials for the current user (use state user_id if available, otherwise current_user)
        target_user_id = stored_user_id or current_user.id
        store_google_credentials(db, target_user_id, credentials)
        
        # Redirect back to frontend documents page
        response = RedirectResponse(
            url=f"{settings.frontend_base_url}/app/documents?connected=google",
            status_code=302,
        )
        # Keep existing cookie
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Microsoft OneDrive OAuth for Drive access
@router.get("/connect/microsoft")
async def connect_microsoft_onedrive(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Initiate Microsoft OneDrive OAuth connection."""
    redirect_uri = f"{settings.backend_base_url}/api/drive/callback/microsoft"
    # Store user_id in state to ensure credentials are associated with the correct user
    auth_url, state = get_microsoft_auth_url(redirect_uri, request=request, user_id=current_user.id)
    return RedirectResponse(url=auth_url)


@router.get("/callback/microsoft")
async def microsoft_onedrive_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Handle Microsoft OneDrive OAuth callback and store credentials."""
    try:
        from app.services.auth_oauth import oauth_states
        import msal
        from app.core.config import settings
        
        if state not in oauth_states:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        state_data = oauth_states.pop(state)
        redirect_uri = state_data["redirect_uri"]
        
        # Verify that the user_id in state matches the current authenticated user
        # This ensures credentials are always associated with the correct user
        stored_user_id = state_data.get("user_id")
        if stored_user_id and stored_user_id != current_user.id:
            raise HTTPException(
                status_code=403, 
                detail="User mismatch: The Microsoft account being connected does not match the logged-in user"
            )
        
        authority = f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}"
        app = msal.ConfidentialClientApplication(
            settings.microsoft_client_id,
            authority=authority,
            client_credential=settings.microsoft_client_secret
        )
        
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=["openid", "email", "profile", "Files.Read.All"],
            redirect_uri=redirect_uri
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result.get('error_description'))
        
        access_token_ms = result.get("access_token")
        
        # Store OneDrive credentials for the current user (use state user_id if available, otherwise current_user)
        target_user_id = stored_user_id or current_user.id
        store_microsoft_credentials(
            db,
            target_user_id,
            access_token_ms,
            result.get("refresh_token"),
            result.get("expires_in")
        )
        
        # Redirect back to frontend
        response = RedirectResponse(
            url=f"{settings.frontend_base_url}/app/documents?connected=microsoft",
            status_code=302,
        )
        # Keep existing cookie
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status/google")
async def check_google_drive_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if Google Drive is connected."""
    creds = get_or_create_oauth_credentials(db, current_user.id, "google")
    return {
        "connected": creds is not None and creds.is_active if creds else False
    }


@router.get("/status/microsoft")
async def check_microsoft_onedrive_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if Microsoft OneDrive is connected."""
    creds = get_or_create_oauth_credentials(db, current_user.id, "microsoft")
    return {
        "connected": creds is not None and creds.is_active if creds else False
    }


@router.get("/files/google")
async def list_google_files(
    folder_id: Optional[str] = Query(None, description="Folder ID (None for root)"),
    page_token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List files and folders from Google Drive."""
    credentials = get_google_credentials(db, current_user.id)
    if not credentials:
        raise HTTPException(status_code=401, detail="Google Drive not connected")
    
    try:
        result = list_google_drive_files(credentials, folder_id, page_token)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/microsoft")
async def list_microsoft_files(
    folder_path: str = Query("/", description="Folder path (default: root)"),
    page_token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List files and folders from OneDrive."""
    access_token = get_microsoft_access_token(db, current_user.id)
    if not access_token:
        raise HTTPException(status_code=401, detail="OneDrive not connected")
    
    try:
        result = list_onedrive_files(access_token, folder_path, page_token)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/google")
async def start_google_ingestion(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start background ingestion from Google Drive."""
    # Verify connection
    credentials = get_google_credentials(db, current_user.id)
    if not credentials:
        raise HTTPException(status_code=401, detail="Google Drive not connected")
    
    # Create task
    items = [{"id": item.id, "name": item.name, "type": item.type} for item in request.items]
    task = create_ingestion_task(
        current_user.id,
        "google",
        items,
        request.knowledge_base_name
    )
    
    # Start background task
    background_tasks.add_task(run_ingestion_task, task)
    
    return {"task_id": task.task_id, "status": task.status.value}


@router.post("/ingest/microsoft")
async def start_microsoft_ingestion(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start background ingestion from OneDrive."""
    # Verify connection
    access_token = get_microsoft_access_token(db, current_user.id)
    if not access_token:
        raise HTTPException(status_code=401, detail="OneDrive not connected")
    
    # Create task
    items = [{"id": item.id, "name": item.name, "type": item.type, "path": getattr(item, 'path', None)} for item in request.items]
    task = create_ingestion_task(
        current_user.id,
        "microsoft",
        items,
        request.knowledge_base_name
    )
    
    # Start background task
    background_tasks.add_task(run_ingestion_task, task)
    
    return {"task_id": task.task_id, "status": task.status.value}


@router.get("/task/{task_id}")
async def get_ingestion_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get ingestion task status and progress."""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return task.to_dict()

