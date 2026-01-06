"""Tracing middleware for request tracking."""
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable
import time


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and track tracingId for each request."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if tracingId is provided in headers, otherwise generate one
        tracing_id = request.headers.get("X-Tracing-Id") or request.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        # Add tracingId to request state for access throughout the request lifecycle
        request.state.tracing_id = tracing_id
        request.state.start_time = time.time()
        
        # Add tracingId to response headers
        response = await call_next(request)
        response.headers["X-Tracing-Id"] = tracing_id
        
        return response


def get_tracing_id(request: Request) -> str:
    """Get tracing ID from request state."""
    return getattr(request.state, "tracing_id", "unknown")

