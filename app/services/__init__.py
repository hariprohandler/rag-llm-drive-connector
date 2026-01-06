"""Application services."""
from app.services.auth_service import (
    get_current_user,
    get_or_create_user,
    get_user_by_email,
    create_access_token,
    verify_token,
)
from app.services.auth_oauth import (
    get_google_auth_url,
    handle_google_callback,
    get_microsoft_auth_url,
    handle_microsoft_callback,
)
from app.services.activity_logger import (
    get_logger,
    get_client_ip,
    get_user_agent,
    ActivityLogger,
)

__all__ = [
    # Auth service
    "get_current_user",
    "get_or_create_user",
    "get_user_by_email",
    "create_access_token",
    "verify_token",
    # OAuth service
    "get_google_auth_url",
    "handle_google_callback",
    "get_microsoft_auth_url",
    "handle_microsoft_callback",
    # Activity logger
    "get_logger",
    "get_client_ip",
    "get_user_agent",
    "ActivityLogger",
]
