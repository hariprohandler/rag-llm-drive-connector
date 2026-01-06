"""OAuth authentication handlers for Google and Microsoft user authentication."""
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials as GoogleCredentials
from googleapiclient.discovery import build
import msal
from typing import Dict, Optional, Any, Tuple
import config
from app.models import User
from app.services.auth_service import get_or_create_user, create_access_token
from app.services.activity_logger import get_logger, get_client_ip, get_user_agent
from app.middleware.tracing import get_tracing_id
import secrets

# In-memory storage for OAuth state (use Redis in production)
oauth_states: Dict[str, Dict[str, Any]] = {}


def get_google_oauth_flow(redirect_uri: str) -> Flow:
    """Create a Google OAuth flow for user authentication."""
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
            "redirect_uris": [redirect_uri]
        }
    }
    
    # Scopes for user info and Drive access
    scopes = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    
    flow = Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=redirect_uri
    )
    
    return flow


def get_google_auth_url(redirect_uri: str, request: Optional[Request] = None, user_id: Optional[str] = None) -> Tuple[str, str]:
    """Get Google OAuth authorization URL and state."""
    flow = get_google_oauth_flow(redirect_uri)
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    auth_url, _ = flow.authorization_url(
        prompt='consent',
        access_type='offline',
        include_granted_scopes='true',
        state=state
    )
    
    # Store state with user_id to ensure credentials are associated with the correct user
    oauth_states[state] = {
        "provider": "google", 
        "redirect_uri": redirect_uri,
        "user_id": user_id  # Store user_id to verify on callback
    }
    
    # Log OAuth initiation
    logger = get_logger()
    logger.log_auth_activity(
        auth_action="oauth_initiated",
        provider="google",
        status="success",
        metadata={"redirect_uri": redirect_uri},
        ip_address=get_client_ip(request) if request else None,
        user_agent=get_user_agent(request) if request else None,
        tracing_id=get_tracing_id(request) if request else None
    )
    
    return auth_url, state


def handle_google_callback(code: str, state: str, db: Session, request: Optional[Request] = None) -> Tuple[User, str]:
    """Handle Google OAuth callback and create/update user."""
    logger = get_logger()
    
    if state not in oauth_states:
        logger.log_auth_activity(
            auth_action="oauth_callback",
            provider="google",
            status="failure",
            error="Invalid state parameter",
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            tracing_id=get_tracing_id(request) if request else None
        )
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    state_data = oauth_states.pop(state)
    redirect_uri = state_data["redirect_uri"]
    
    try:
        flow = get_google_oauth_flow(redirect_uri)
        
        # Fetch token
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Get user info from Google
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')
        google_id = user_info.get('id')
        
        if not email:
            logger.log_auth_activity(
                auth_action="oauth_callback",
                provider="google",
                status="failure",
                error="Email not provided by Google",
                ip_address=get_client_ip(request) if request else None,
                user_agent=get_user_agent(request) if request else None
            )
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        # Create or get user
        user = get_or_create_user(
            db=db,
            email=email,
            name=name,
            provider="google",
            provider_id=google_id,
            picture=picture,
            request=request
        )
        
        # Create JWT token
        access_token = create_access_token(data={"sub": user.id, "email": user.email}, request=request)
        
        # Log successful OAuth callback
        logger.log_auth_activity(
            auth_action="oauth_callback",
            user_id=user.id,
            email=email,
            provider="google",
            status="success",
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            tracing_id=get_tracing_id(request) if request else None
        )
        
        return user, access_token
    except Exception as e:
        logger.log_auth_activity(
            auth_action="oauth_callback",
            provider="google",
            status="failure",
            error=str(e),
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            tracing_id=get_tracing_id(request) if request else None
        )
        raise


def get_microsoft_auth_url(redirect_uri: str, request: Optional[Request] = None, user_id: Optional[str] = None) -> Tuple[str, str]:
    """Get Microsoft OAuth authorization URL."""
    if not config.settings.microsoft_client_id or not config.settings.microsoft_tenant_id:
        raise HTTPException(
            status_code=500,
            detail="Microsoft OAuth not configured"
        )
    
    # Generate state
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {
        "provider": "microsoft", 
        "redirect_uri": redirect_uri,
        "user_id": user_id  # Store user_id to verify on callback
    }
    
    authority = f"https://login.microsoftonline.com/{config.settings.microsoft_tenant_id}"
    scopes = [
        "openid",
        "email",
        "profile",
        "Files.Read.All"
    ]
    
    auth_url = (
        f"{authority}/oauth2/v2.0/authorize?"
        f"client_id={config.settings.microsoft_client_id}&"
        f"response_type=code&"
        f"redirect_uri={redirect_uri}&"
        f"response_mode=query&"
        f"scope={' '.join(scopes)}&"
        f"state={state}"
    )
    
    # Log OAuth initiation
    logger = get_logger()
    logger.log_auth_activity(
        auth_action="oauth_initiated",
        provider="microsoft",
        status="success",
        metadata={"redirect_uri": redirect_uri},
        ip_address=get_client_ip(request) if request else None,
        user_agent=get_user_agent(request) if request else None
    )
    
    return auth_url, state


def handle_microsoft_callback(code: str, state: str, db: Session, request: Optional[Request] = None) -> Tuple[User, str]:
    """Handle Microsoft OAuth callback and create/update user."""
    logger = get_logger()
    
    if state not in oauth_states:
        logger.log_auth_activity(
            auth_action="oauth_callback",
            provider="microsoft",
            status="failure",
            error="Invalid state parameter",
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            tracing_id=get_tracing_id(request) if request else None
        )
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    state_data = oauth_states.pop(state)
    redirect_uri = state_data["redirect_uri"]
    
    try:
        if not config.settings.microsoft_client_id or not config.settings.microsoft_client_secret:
            raise HTTPException(status_code=500, detail="Microsoft OAuth not configured")
        
        authority = f"https://login.microsoftonline.com/{config.settings.microsoft_tenant_id}"
        
        app = msal.ConfidentialClientApplication(
            config.settings.microsoft_client_id,
            authority=authority,
            client_credential=config.settings.microsoft_client_secret
        )
        
        scopes = ["openid", "email", "profile", "Files.Read.All"]
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=scopes,
            redirect_uri=redirect_uri
        )
        
        if "error" in result:
            logger.log_auth_activity(
                auth_action="oauth_callback",
                provider="microsoft",
                status="failure",
                error=result.get('error_description', 'Authentication failed'),
                ip_address=get_client_ip(request) if request else None,
                user_agent=get_user_agent(request) if request else None
            )
            raise HTTPException(
                status_code=400,
                detail=f"Authentication failed: {result.get('error_description')}"
            )
        
        access_token = result.get("access_token")
        
        # Get user info from Microsoft Graph
        import requests
        graph_response = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if graph_response.status_code != 200:
            logger.log_auth_activity(
                auth_action="oauth_callback",
                provider="microsoft",
                status="failure",
                error="Failed to get user info from Microsoft",
                ip_address=get_client_ip(request) if request else None,
                user_agent=get_user_agent(request) if request else None
            )
            raise HTTPException(status_code=400, detail="Failed to get user info from Microsoft")
        
        user_info = graph_response.json()
        
        email = user_info.get('mail') or user_info.get('userPrincipalName')
        name = user_info.get('displayName')
        picture = None  # Microsoft Graph doesn't provide picture in basic profile
        microsoft_id = user_info.get('id')
        
        if not email:
            logger.log_auth_activity(
                auth_action="oauth_callback",
                provider="microsoft",
                status="failure",
                error="Email not provided by Microsoft",
                ip_address=get_client_ip(request) if request else None,
                user_agent=get_user_agent(request) if request else None
            )
            raise HTTPException(status_code=400, detail="Email not provided by Microsoft")
        
        # Create or get user
        user = get_or_create_user(
            db=db,
            email=email,
            name=name,
            provider="microsoft",
            provider_id=microsoft_id,
            picture=picture,
            request=request
        )
        
        # Create JWT token
        jwt_token = create_access_token(data={"sub": user.id, "email": user.email}, request=request)
        
        # Log successful OAuth callback
        logger.log_auth_activity(
            auth_action="oauth_callback",
            user_id=user.id,
            email=email,
            provider="microsoft",
            status="success",
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            tracing_id=get_tracing_id(request) if request else None
        )
        
        return user, jwt_token
    except Exception as e:
        logger.log_auth_activity(
            auth_action="oauth_callback",
            provider="microsoft",
            status="failure",
            error=str(e),
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            tracing_id=get_tracing_id(request) if request else None
        )
        raise

