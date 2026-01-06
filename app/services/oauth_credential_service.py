"""Service for managing OAuth credentials for Google Drive and OneDrive."""
from sqlalchemy.orm import Session
from typing import Optional
from app.models import OAuthCredentials
from google.oauth2.credentials import Credentials as GoogleCredentials
from google_auth_oauthlib.flow import Flow
import config
import json
from datetime import datetime, timedelta


def get_or_create_oauth_credentials(
    db: Session,
    user_id: str,
    provider: str
) -> Optional[OAuthCredentials]:
    """Get existing OAuth credentials or return None."""
    cred_id = f"{user_id}_{provider}"
    return db.query(OAuthCredentials).filter(OAuthCredentials.id == cred_id).first()


def store_google_credentials(
    db: Session,
    user_id: str,
    credentials: GoogleCredentials
) -> OAuthCredentials:
    """Store Google OAuth credentials."""
    cred_id = f"{user_id}_google"
    
    # Convert credentials to dict
    creds_dict = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    
    # Calculate expiration
    expires_at = None
    if credentials.expiry:
        expires_at = credentials.expiry
    
    # Get or create
    oauth_cred = db.query(OAuthCredentials).filter(OAuthCredentials.id == cred_id).first()
    if oauth_cred:
        oauth_cred.set_credentials(creds_dict)
        oauth_cred.expires_at = expires_at
        oauth_cred.is_active = True
        oauth_cred.updated_at = datetime.utcnow()
    else:
        oauth_cred = OAuthCredentials(
            id=cred_id,
            user_id=user_id,
            provider="google",
            expires_at=expires_at,
            is_active=True
        )
        oauth_cred.set_credentials(creds_dict)
        db.add(oauth_cred)
    
    db.commit()
    db.refresh(oauth_cred)
    return oauth_cred


def store_microsoft_credentials(
    db: Session,
    user_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_in: Optional[int] = None
) -> OAuthCredentials:
    """Store Microsoft OAuth credentials."""
    cred_id = f"{user_id}_microsoft"
    
    creds_dict = {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }
    
    # Calculate expiration
    expires_at = None
    if expires_in:
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    # Get or create
    oauth_cred = db.query(OAuthCredentials).filter(OAuthCredentials.id == cred_id).first()
    if oauth_cred:
        oauth_cred.set_credentials(creds_dict)
        oauth_cred.expires_at = expires_at
        oauth_cred.is_active = True
        oauth_cred.updated_at = datetime.utcnow()
    else:
        oauth_cred = OAuthCredentials(
            id=cred_id,
            user_id=user_id,
            provider="microsoft",
            expires_at=expires_at,
            is_active=True
        )
        oauth_cred.set_credentials(creds_dict)
        db.add(oauth_cred)
    
    db.commit()
    db.refresh(oauth_cred)
    return oauth_cred


def get_google_credentials(
    db: Session,
    user_id: str
) -> Optional[GoogleCredentials]:
    """Get Google credentials as GoogleCredentials object."""
    oauth_cred = get_or_create_oauth_credentials(db, user_id, "google")
    if not oauth_cred or not oauth_cred.is_active:
        return None
    
    creds_dict = oauth_cred.get_credentials()
    if not creds_dict:
        return None
    
    # Check if expired and refresh if needed
    if oauth_cred.expires_at and oauth_cred.expires_at < datetime.utcnow():
        # Try to refresh
        try:
            creds = GoogleCredentials(**creds_dict)
            if creds.refresh_token:
                # Refresh the token
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                # Store updated credentials
                store_google_credentials(db, user_id, creds)
                return creds
        except Exception:
            return None
    
    try:
        return GoogleCredentials(**creds_dict)
    except Exception:
        return None


def get_microsoft_access_token(
    db: Session,
    user_id: str
) -> Optional[str]:
    """Get Microsoft access token."""
    oauth_cred = get_or_create_oauth_credentials(db, user_id, "microsoft")
    if not oauth_cred or not oauth_cred.is_active:
        return None
    
    creds_dict = oauth_cred.get_credentials()
    return creds_dict.get("access_token")

