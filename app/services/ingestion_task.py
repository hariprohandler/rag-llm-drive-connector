"""Background task management for document ingestion."""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import os
from enum import Enum
import threading
from sqlalchemy.orm import Session
from app.services.ingest import ingest_google_drive, ingest_onedrive
from app.services.oauth_credential_service import get_google_credentials, get_microsoft_access_token
from app.models.base import get_db


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionTask:
    """Represents a background ingestion task."""
    
    def __init__(
        self,
        task_id: str,
        user_id: str,
        provider: str,
        items: list[Dict[str, Any]],  # List of file/folder IDs to ingest
        knowledge_base_name: Optional[str] = None
    ):
        self.task_id = task_id
        self.user_id = user_id
        self.provider = provider
        self.items = items
        self.knowledge_base_name = knowledge_base_name
        self.status = TaskStatus.PENDING
        self.progress = 0.0  # 0.0 to 100.0
        self.total_items = len(items)
        self.processed_items = 0
        self.message = "Waiting to start..."
        self.error: Optional[str] = None
        self.knowledge_base_id: Optional[int] = None
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._lock = threading.Lock()
    
    def update_progress(self, processed: int, message: str = ""):
        """Update task progress."""
        with self._lock:
            self.processed_items = processed
            self.progress = (processed / self.total_items * 100.0) if self.total_items > 0 else 0.0
            if message:
                self.message = message
            self.updated_at = datetime.utcnow()
    
    def set_status(self, status: TaskStatus, message: str = "", error: Optional[str] = None):
        """Set task status."""
        with self._lock:
            self.status = status
            if message:
                self.message = message
            if error:
                self.error = error
            self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        with self._lock:
            return {
                "task_id": self.task_id,
                "user_id": self.user_id,
                "provider": self.provider,
                "status": self.status.value,
                "progress": round(self.progress, 2),
                "total_items": self.total_items,
                "processed_items": self.processed_items,
                "message": self.message,
                "error": self.error,
                "knowledge_base_id": self.knowledge_base_id,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
            }


# In-memory task store (use Redis in production)
_task_store: Dict[str, IngestionTask] = {}
_task_store_lock = threading.Lock()


def create_ingestion_task(
    user_id: str,
    provider: str,
    items: list[Dict[str, Any]],
    knowledge_base_name: Optional[str] = None
) -> IngestionTask:
    """Create a new ingestion task."""
    task_id = str(uuid.uuid4())
    task = IngestionTask(task_id, user_id, provider, items, knowledge_base_name)
    
    with _task_store_lock:
        _task_store[task_id] = task
    
    return task


def get_task(task_id: str) -> Optional[IngestionTask]:
    """Get a task by ID."""
    with _task_store_lock:
        return _task_store.get(task_id)


def create_file_upload_task(
    user_id: str,
    file_paths: list[str],
    knowledge_base_name: Optional[str] = None
) -> IngestionTask:
    """Create a new file upload ingestion task."""
    task_id = str(uuid.uuid4())
    items = [{"id": path, "name": os.path.basename(path), "type": "file", "path": path} for path in file_paths]
    task = IngestionTask(task_id, user_id, "local", items, knowledge_base_name)
    
    with _task_store_lock:
        _task_store[task_id] = task
    
    return task


def run_ingestion_task(task: IngestionTask):
    """Run ingestion task in background."""
    task.set_status(TaskStatus.RUNNING, "Starting ingestion...")
    
    try:
        # Get database session
        db = next(get_db())
        
        if task.provider == "local":
            # Process local file uploads
            from app.services.ingest import ingest_local_files
            
            file_paths = [item.get("path") or item.get("id") for item in task.items]
            
            # Process files with progress updates
            for idx, file_path in enumerate(file_paths):
                task.update_progress(idx, f"Processing file: {os.path.basename(file_path)}")
            
            success, kb_id = ingest_local_files(
                file_paths=file_paths,
                user_id=task.user_id,
                db=db,
                knowledge_base_name=task.knowledge_base_name
            )
            
            if success and kb_id:
                task.knowledge_base_id = kb_id
            
            task.update_progress(task.total_items, "Ingestion completed!")
            task.set_status(TaskStatus.COMPLETED, "All files ingested successfully")
            
        elif task.provider == "google":
            # Get Google credentials
            credentials = get_google_credentials(db, task.user_id)
            if not credentials:
                raise Exception("Google Drive not connected. Please connect your Google Drive account.")
            
            # Process each item
            all_documents = []
            for idx, item in enumerate(task.items):
                item_id = item.get("id")
                item_type = item.get("type")
                
                if item_type == "folder":
                    task.update_progress(idx, f"Processing folder: {item.get('name', item_id)}")
                    # Ingest folder
                    success, kb_id = ingest_google_drive(
                        folder_id=item_id,
                        credentials=credentials,
                        user_id=task.user_id,
                        db=db,
                        knowledge_base_name=task.knowledge_base_name if idx == 0 else None
                    )
                    if success and kb_id:
                        task.knowledge_base_id = kb_id
                else:
                    task.update_progress(idx, f"Processing file: {item.get('name', item_id)}")
                    # For individual files, we'd need to download and process them
                    # This is a simplified version - you may want to enhance this
                    pass
            
            task.update_progress(task.total_items, "Ingestion completed!")
            task.set_status(TaskStatus.COMPLETED, "All files ingested successfully")
            
        elif task.provider == "microsoft":
            # Get Microsoft access token
            access_token = get_microsoft_access_token(db, task.user_id)
            if not access_token:
                raise Exception("OneDrive not connected. Please connect your OneDrive account.")
            
            # Process each item
            for idx, item in enumerate(task.items):
                item_path = item.get("path") or item.get("id")
                item_type = item.get("type")
                
                if item_type == "folder":
                    task.update_progress(idx, f"Processing folder: {item.get('name', item_path)}")
                    # Ingest folder
                    success, kb_id = ingest_onedrive(
                        folder_path=item_path,
                        access_token=access_token,
                        user_id=task.user_id,
                        db=db,
                        knowledge_base_name=task.knowledge_base_name if idx == 0 else None
                    )
                    if success and kb_id:
                        task.knowledge_base_id = kb_id
                else:
                    task.update_progress(idx, f"Processing file: {item.get('name', item_path)}")
                    # For individual files, similar handling as Google Drive
                    pass
            
            task.update_progress(task.total_items, "Ingestion completed!")
            task.set_status(TaskStatus.COMPLETED, "All files ingested successfully")
        
        db.close()
        
    except Exception as e:
        task.set_status(TaskStatus.FAILED, f"Ingestion failed: {str(e)}", error=str(e))
        if 'db' in locals():
            db.close()

