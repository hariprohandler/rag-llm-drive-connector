from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.base import get_db
from app.models import User
from app.services.auth_service import verify_token
from app.services.auth_oauth import (
    get_google_auth_url,
    handle_google_callback,
    get_microsoft_auth_url,
    handle_microsoft_callback,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login/google")
async def google_login(request: Request):
    """Initiate Google OAuth login."""
    # Use the configured redirect URI from settings to ensure consistency
    redirect_uri = settings.google_redirect_uri
    auth_url, state = get_google_auth_url(redirect_uri, request=request)
    return RedirectResponse(url=auth_url)


@router.get("/callback/google")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback."""
    try:
        user, access_token = handle_google_callback(code, state, db, request=request)

        # Redirect to React frontend and set JWT in HTTP-only cookie
        response = RedirectResponse(
            url=f"{settings.frontend_base_url}/app/chat",
            status_code=302,
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            path="/",  # Ensure cookie is available for all paths
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/login/microsoft")
async def microsoft_login(request: Request):
    """Initiate Microsoft OAuth login."""
    # Use the configured redirect URI from settings to ensure consistency
    redirect_uri = settings.microsoft_redirect_uri
    auth_url, state = get_microsoft_auth_url(redirect_uri, request=request)
    return RedirectResponse(url=auth_url)


@router.get("/callback/microsoft")
async def microsoft_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle Microsoft OAuth callback."""
    try:
        user, access_token = handle_microsoft_callback(code, state, db, request=request)

        # Redirect to React frontend and set JWT in HTTP-only cookie
        response = RedirectResponse(
            url=f"{settings.frontend_base_url}/app/chat",
            status_code=302,
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            path="/",  # Ensure cookie is available for all paths
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me")
async def get_current_user_info(request: Request, db: Session = Depends(get_db)):
    """
    Get current user information for the React frontend.
    Uses the JWT stored in the 'access_token' HTTP-only cookie.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = verify_token(token)
    except HTTPException:
        # verify_token already logs and throws HTTPException
        raise

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user.to_dict()


