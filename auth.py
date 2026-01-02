"""OAuth authentication handlers for Google Drive and OneDrive."""
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import msal
from typing import Dict, Optional, Any
import config
import os


# In-memory storage for user credentials (use database in production)
user_credentials: Dict[str, Dict[str, Any]] = {}


def get_google_flow() -> Flow:
    """Create a Google OAuth flow."""
    if not config.settings.google_client_id or not config.settings.google_client_secret:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"
        )
    
    client_config = {
        "web": {
            "client_id": config.settings.google_client_id,
            "client_secret": config.settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [config.settings.google_redirect_uri]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=config.settings.google_scopes,
        redirect_uri=config.settings.google_redirect_uri
    )
    
    return flow


def get_google_auth_url(state: Optional[str] = None) -> str:
    """Get Google OAuth authorization URL."""
    flow = get_google_flow()
    auth_url, _ = flow.authorization_url(
        prompt='consent',
        access_type='offline',
        include_granted_scopes='true',
        state=state
    )
    return auth_url


def handle_google_callback(code: str, state: Optional[str] = None) -> Credentials:
    """Handle Google OAuth callback and return credentials."""
    flow = get_google_flow()
    
    # For local development, disable SSL verification
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    return credentials


def get_microsoft_auth_url(state: Optional[str] = None) -> str:
    """Get Microsoft OAuth authorization URL."""
    if not config.settings.microsoft_client_id or not config.settings.microsoft_tenant_id:
        raise HTTPException(
            status_code=500,
            detail="Microsoft OAuth not configured. Please set MICROSOFT_CLIENT_ID and MICROSOFT_TENANT_ID"
        )
    
    authority = f"https://login.microsoftonline.com/{config.settings.microsoft_tenant_id}"
    
    auth_url = (
        f"{authority}/oauth2/v2.0/authorize?"
        f"client_id={config.settings.microsoft_client_id}&"
        f"response_type=code&"
        f"redirect_uri={config.settings.microsoft_redirect_uri}&"
        f"response_mode=query&"
        f"scope={' '.join(config.settings.microsoft_scopes)}&"
        f"state={state or ''}"
    )
    
    return auth_url


def handle_microsoft_callback(code: str) -> str:
    """Handle Microsoft OAuth callback and return access token."""
    if not config.settings.microsoft_client_id or not config.settings.microsoft_client_secret:
        raise HTTPException(
            status_code=500,
            detail="Microsoft OAuth not configured"
        )
    
    authority = f"https://login.microsoftonline.com/{config.settings.microsoft_tenant_id}"
    
    app = msal.ConfidentialClientApplication(
        config.settings.microsoft_client_id,
        authority=authority,
        client_credential=config.settings.microsoft_client_secret
    )
    
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=config.settings.microsoft_scopes,
        redirect_uri=config.settings.microsoft_redirect_uri
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=400,
            detail=f"Authentication failed: {result.get('error_description')}"
        )
    
    return result.get("access_token")


def store_user_credentials(user_id: str, provider: str, credentials: Any):
    """Store user credentials (in-memory for prototype, use DB in production)."""
    if user_id not in user_credentials:
        user_credentials[user_id] = {}
    
    user_credentials[user_id][provider] = credentials


def get_user_credentials(user_id: str, provider: str) -> Optional[Any]:
    """Get stored user credentials."""
    return user_credentials.get(user_id, {}).get(provider)

