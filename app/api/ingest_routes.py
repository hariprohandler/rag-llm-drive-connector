from typing import Optional
import time

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import User
from app.models.base import get_db
from app.services.ingest import ingest_google_drive, ingest_onedrive, ingest_local_files
from app.services.auth_service import get_current_user
from app.services.activity_logger import get_logger, get_client_ip, get_user_agent
from app.middleware.tracing import get_tracing_id


class IngestDriveRequest(BaseModel):
    folder_id: str


class IngestOneDriveRequest(BaseModel):
    folder_path: str


class FileUploadRequest(BaseModel):
    file_paths: list[str]
    knowledge_base_name: Optional[str] = None


router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/google-drive")
async def ingest_google(
    request: IngestDriveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingest documents from Google Drive (requires authentication)."""
    # TODO: Retrieve stored credentials for user (implement credential storage)
    raise HTTPException(
        status_code=501,
        detail="Google Drive ingestion requires credential storage implementation",
    )


@router.post("/onedrive")
async def ingest_onedrive_endpoint(
    request: IngestOneDriveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingest documents from OneDrive (requires authentication)."""
    # TODO: Retrieve stored credentials for user (implement credential storage)
    raise HTTPException(
        status_code=501,
        detail="OneDrive ingestion requires credential storage implementation",
    )


@router.post("/files")
async def ingest_files(
    request: FileUploadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingest local files (requires authentication)."""
    try:
        success, kb_id = ingest_local_files(
            file_paths=request.file_paths,
            user_id=current_user.id,
            db=db,
            knowledge_base_name=request.knowledge_base_name,
        )
        if success:
            return {
                "status": "success",
                "message": "Files ingested successfully",
                "knowledge_base_id": kb_id,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to ingest files")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    knowledge_base_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload and ingest files (requires authentication)."""
    import os
    import shutil
    import tempfile

    logger = get_logger()
    tracing_id = get_tracing_id(request)
    start_time = time.time()
    file_names = [f.filename for f in files] if files else []
    
    try:
        # Save uploaded files to temp directory
        temp_dir = tempfile.mkdtemp()
        file_paths = []

        try:
            for file in files:
                # Sanitize filename to remove NUL characters
                sanitized_filename = file.filename.replace('\x00', '') if file.filename else "unnamed_file"
                file_path = os.path.join(temp_dir, sanitized_filename)
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                file_paths.append(file_path)

            success, kb_id = ingest_local_files(
                file_paths=file_paths,
                user_id=current_user.id,
                db=db,
                knowledge_base_name=knowledge_base_name,
            )

            # Verify knowledge base was created if kb_id is returned
            if kb_id:
                from app.models import KnowledgeBase
                kb_verify = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
                if not kb_verify:
                    print(f"WARNING: Knowledge base ID {kb_id} was returned but not found in database after commit!")
                else:
                    print(f"Verified: Knowledge base ID {kb_id} exists in database for user {current_user.id}")

            response_time_ms = (time.time() - start_time) * 1000
            
            if success:
                logger.log_activity(
                    activity_type="file_upload",
                    user_id=current_user.id,
                    endpoint="/api/ingest/upload",
                    method="POST",
                    status="success",
                    metadata={"file_count": len(file_names), "file_names": file_names, "knowledge_base_id": kb_id},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request),
                    response_time_ms=response_time_ms,
                    tracing_id=tracing_id,
                    response_status_code=200
                )
                return {
                    "status": "success",
                    "message": "Files uploaded and ingested successfully",
                    "knowledge_base_id": kb_id,
                }
            else:
                logger.log_activity(
                    activity_type="file_upload",
                    user_id=current_user.id,
                    endpoint="/api/ingest/upload",
                    method="POST",
                    status="failure",
                    error="Failed to ingest files",
                    metadata={"file_count": len(file_names), "file_names": file_names},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request),
                    response_time_ms=response_time_ms,
                    tracing_id=tracing_id,
                    response_status_code=500
                )
                raise HTTPException(status_code=500, detail="Failed to ingest files")
        finally:
            # Clean up temp files
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        logger.log_activity(
            activity_type="file_upload",
            user_id=current_user.id if current_user else None,
            endpoint="/api/ingest/upload",
            method="POST",
            status="error",
            error=str(e),
            metadata={"file_count": len(file_names), "file_names": file_names},
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            response_time_ms=response_time_ms,
            tracing_id=tracing_id,
            response_status_code=500
        )
        raise HTTPException(status_code=500, detail=str(e))


