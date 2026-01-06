"""Service for interacting with Google Drive and OneDrive APIs."""
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials as GoogleCredentials
from googleapiclient.discovery import build
import requests
from app.services.oauth_credential_service import get_google_credentials, get_microsoft_access_token


def list_google_drive_files(
    credentials: GoogleCredentials,
    folder_id: Optional[str] = None,
    page_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    List files and folders from Google Drive.
    
    Args:
        credentials: Google OAuth credentials
        folder_id: Optional folder ID to list contents of (None for root)
        page_token: Optional page token for pagination
        
    Returns:
        Dictionary with 'files' list and 'next_page_token'
    """
    service = build('drive', 'v3', credentials=credentials)
    
    query = "trashed=false"
    if folder_id:
        query += f" and '{folder_id}' in parents"
    else:
        query += " and 'root' in parents"
    
    results = service.files().list(
        q=query,
        pageSize=100,
        fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)",
        pageToken=page_token
    ).execute()
    
    files = []
    for item in results.get('files', []):
        files.append({
            "id": item['id'],
            "name": item['name'],
            "type": "folder" if item['mimeType'] == 'application/vnd.google-apps.folder' else "file",
            "size": item.get('size', '0'),
            "modified_time": item.get('modifiedTime', ''),
            "parents": item.get('parents', [])
        })
    
    return {
        "files": files,
        "next_page_token": results.get('nextPageToken')
    }


def list_onedrive_files(
    access_token: str,
    folder_path: str = "/",
    page_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    List files and folders from OneDrive.
    
    Args:
        access_token: Microsoft OAuth access token
        folder_path: Folder path to list (default: root)
        page_token: Optional page token for pagination
        
    Returns:
        Dictionary with 'files' list and 'next_page_token'
    """
    # Convert folder path to OneDrive API format
    if folder_path == "/" or folder_path == "":
        url = "https://graph.microsoft.com/v1.0/me/drive/root/children"
    else:
        # URL encode the path
        encoded_path = folder_path.strip('/').replace('/', '%2F')
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{encoded_path}:/children"
    
    if page_token:
        url += f"?$skiptoken={page_token}"
    else:
        url += "?$top=100"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    files = []
    
    for item in data.get('value', []):
        files.append({
            "id": item['id'],
            "name": item['name'],
            "type": "folder" if 'folder' in item else "file",
            "size": item.get('size', 0),
            "modified_time": item.get('lastModifiedDateTime', ''),
            "path": item.get('parentReference', {}).get('path', '')
        })
    
    return {
        "files": files,
        "next_page_token": data.get('@odata.nextLink', '').split('$skiptoken=')[-1] if '@odata.nextLink' in data else None
    }


def download_google_drive_file(
    credentials: GoogleCredentials,
    file_id: str
) -> bytes:
    """Download a file from Google Drive."""
    service = build('drive', 'v3', credentials=credentials)
    request = service.files().get_media(fileId=file_id)
    return request.execute()


def download_onedrive_file(
    access_token: str,
    file_id: str
) -> bytes:
    """Download a file from OneDrive."""
    url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.content

