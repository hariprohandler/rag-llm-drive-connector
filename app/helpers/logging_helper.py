"""Helper functions for activity logging."""
import time
from typing import Optional, Dict, Any
from fastapi import Request
from app.services.activity_logger import get_logger, get_client_ip, get_user_agent
from app.middleware.tracing import get_tracing_id


class ActivityLogger:
    """Context manager for logging API activities."""
    
    def __init__(
        self,
        request: Request,
        activity_type: str,
        endpoint: str,
        method: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.request = request
        self.activity_type = activity_type
        self.endpoint = endpoint
        self.method = method
        self.user_id = user_id
        self.metadata = metadata or {}
        self.start_time = time.time()
        self.logger = get_logger()
        self.tracing_id = get_tracing_id(request)
    
    def log_success(self, response_data: Optional[Dict[str, Any]] = None, status_code: int = 200):
        """Log successful activity."""
        response_time_ms = (time.time() - self.start_time) * 1000
        self.logger.log_activity(
            activity_type=self.activity_type,
            user_id=self.user_id,
            endpoint=self.endpoint,
            method=self.method,
            status="success",
            metadata={**self.metadata, **(response_data or {})},
            ip_address=get_client_ip(self.request),
            user_agent=get_user_agent(self.request),
            response_time_ms=response_time_ms,
            tracing_id=self.tracing_id,
            response_status_code=status_code
        )
    
    def log_error(self, error: str, status_code: int = 500):
        """Log failed activity."""
        response_time_ms = (time.time() - self.start_time) * 1000
        self.logger.log_activity(
            activity_type=self.activity_type,
            user_id=self.user_id,
            endpoint=self.endpoint,
            method=self.method,
            status="error",
            error=error,
            metadata=self.metadata,
            ip_address=get_client_ip(self.request),
            user_agent=get_user_agent(self.request),
            response_time_ms=response_time_ms,
            tracing_id=self.tracing_id,
            response_status_code=status_code
        )
    
    def log_failure(self, error: str, status_code: int = 500):
        """Log failed activity (alias for log_error)."""
        self.log_error(error, status_code)

