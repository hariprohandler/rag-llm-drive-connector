from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import User
from app.models.base import get_db
from app.services.ingest import ingest_google_drive, ingest_onedrive, ingest_local_files
from app.services.auth_service import get_current_user


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
    files: list[UploadFile] = File(...),
    knowledge_base_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload and ingest files (requires authentication)."""
    import os
    import shutil
    import tempfile

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

            if success:
                return {
                    "status": "success",
                    "message": "Files uploaded and ingested successfully",
                    "knowledge_base_id": kb_id,
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to ingest files")
        finally:
            # Clean up temp files
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


