"""Background task management for tool synchronization."""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
from enum import Enum
import threading
from sqlalchemy.orm import Session
from app.services.zendesk_service import sync_zendesk_tickets
from app.models.base import get_db


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolSyncTask:
    """Represents a background tool synchronization task."""
    
    def __init__(
        self,
        task_id: str,
        user_id: str,
        tool_name: str
    ):
        self.task_id = task_id
        self.user_id = user_id
        self.tool_name = tool_name
        self.status = TaskStatus.PENDING
        self.progress = 0.0  # 0.0 to 100.0
        self.message = "Waiting to start..."
        self.error: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._lock = threading.Lock()
    
    def update_progress(self, progress: float, message: str = ""):
        """Update task progress."""
        with self._lock:
            self.progress = min(100.0, max(0.0, progress))
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
                "tool_name": self.tool_name,
                "status": self.status.value,
                "progress": round(self.progress, 2),
                "message": self.message,
                "error": self.error,
                "result": self.result,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
            }


# In-memory task store (use Redis in production)
_task_store: Dict[str, ToolSyncTask] = {}
_task_store_lock = threading.Lock()


def create_tool_sync_task(
    user_id: str,
    tool_name: str
) -> ToolSyncTask:
    """Create a new tool sync task."""
    task_id = str(uuid.uuid4())
    task = ToolSyncTask(task_id, user_id, tool_name)
    
    with _task_store_lock:
        _task_store[task_id] = task
    
    return task


def get_tool_sync_task(task_id: str) -> Optional[ToolSyncTask]:
    """Get a task by ID."""
    with _task_store_lock:
        return _task_store.get(task_id)


def run_tool_sync_task(task: ToolSyncTask):
    """Run tool sync task in background."""
    task.set_status(TaskStatus.RUNNING, "Starting synchronization...")
    
    try:
        # Get database session
        db = next(get_db())
        
        def progress_callback(progress: float, message: str):
            task.update_progress(progress, message)
        
        if task.tool_name == "zendesk":
            result = sync_zendesk_tickets(
                db=db,
                user_id=task.user_id,
                progress_callback=progress_callback
            )
            task.result = result
            task.set_status(TaskStatus.COMPLETED, "Synchronization completed successfully")
        else:
            raise ValueError(f"Unsupported tool: {task.tool_name}")
        
        db.close()
        
    except Exception as e:
        task.set_status(TaskStatus.FAILED, f"Synchronization failed: {str(e)}", error=str(e))
        if 'db' in locals():
            db.close()

