"""Zendesk integration service for syncing support tickets."""
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from langchain_core.documents import Document
from app.models import ToolConfig
from app.services.ingest import ingest_documents, get_user_collection_name
from app.services.llm_service import encrypt_api_key, decrypt_api_key


def get_zendesk_config(db: Session, user_id: str) -> Optional[ToolConfig]:
    """Get active Zendesk configuration for a user."""
    return db.query(ToolConfig).filter(
        ToolConfig.user_id == user_id,
        ToolConfig.tool_name == "zendesk",
        ToolConfig.is_active == True
    ).first()


def fetch_zendesk_tickets(
    subdomain: str,
    email: str,
    api_token: str,
    page_size: int = 100,
    max_tickets: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetch tickets from Zendesk API.
    
    Args:
        subdomain: Zendesk subdomain (e.g., "mycompany" for mycompany.zendesk.com)
        email: Zendesk email
        api_token: Zendesk API token
        page_size: Number of tickets per page
        max_tickets: Maximum number of tickets to fetch (None for all)
        
    Returns:
        List of ticket dictionaries
    """
    # Clean subdomain - remove any .zendesk.com or .com suffixes
    subdomain = subdomain.strip().lower()
    if subdomain.endswith('.zendesk.com'):
        subdomain = subdomain[:-12]
    if subdomain.endswith('.com'):
        subdomain = subdomain[:-4]
    # Remove any leading/trailing dots
    subdomain = subdomain.strip('.')
    
    if not subdomain:
        raise ValueError("Invalid subdomain: subdomain cannot be empty")
    
    base_url = f"https://{subdomain}.zendesk.com/api/v2"
    auth = (f"{email}/token", api_token)
    all_tickets = []
    page = 1
    
    # Configure SSL/TLS for requests
    # Use a session with proper SSL configuration
    session = requests.Session()
    # Disable SSL warnings if verification is disabled (for development)
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except ImportError:
        pass
    
    # Track if we need to disable SSL verification (set on first SSL error)
    ssl_verify = True
    
    while True:
        url = f"{base_url}/tickets.json"
        params = {
            "per_page": page_size,
            "page": page,
            "sort_by": "updated_at",
            "sort_order": "desc"
        }
        
        try:
            # Make request with SSL verification (or without if previous request failed)
            response = session.get(
                url, 
                auth=auth, 
                params=params, 
                timeout=30,
                verify=ssl_verify  # Verify SSL certificates (or not if SSL failed before)
            )
            response.raise_for_status()
            data = response.json()
            
            tickets = data.get("tickets", [])
            if not tickets:
                break
            
            all_tickets.extend(tickets)
            
            if max_tickets and len(all_tickets) >= max_tickets:
                all_tickets = all_tickets[:max_tickets]
                break
            
            # Check if there are more pages
            if not data.get("next_page"):
                break
            
            page += 1
            
        except requests.exceptions.SSLError as ssl_error:
            # SSL/TLS handshake failure
            if ssl_verify:
                # First SSL error - try again with verification disabled
                error_msg = (
                    f"SSL/TLS handshake failed when connecting to Zendesk.\n"
                    f"  This could be due to:\n"
                    f"  1. Network/firewall blocking SSL connections\n"
                    f"  2. Outdated SSL certificates in the Docker container\n"
                    f"  3. TLS version mismatch\n"
                    f"  Original error: {str(ssl_error)}\n"
                    f"  Retrying with SSL verification disabled (development mode)..."
                )
                print(f"WARNING: {error_msg}")
                ssl_verify = False
                # Retry the same request with SSL verification disabled
                continue
            else:
                # SSL already disabled and still failing
                raise Exception(
                    f"Failed to fetch Zendesk tickets: SSL/TLS handshake failure even with verification disabled. "
                    f"Please check your network connection. Error: {str(ssl_error)}"
                )
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch Zendesk tickets: {str(e)}")
    
    return all_tickets


def convert_tickets_to_documents(tickets: List[Dict[str, Any]]) -> List[Document]:
    """
    Convert Zendesk tickets to LangChain Document objects.
    
    Args:
        tickets: List of ticket dictionaries from Zendesk API
        
    Returns:
        List of Document objects
    """
    documents = []
    
    for ticket in tickets:
        # Build document content from ticket
        content_parts = []
        
        # Subject
        if ticket.get("subject"):
            content_parts.append(f"Subject: {ticket['subject']}")
        
        # Description
        if ticket.get("description"):
            content_parts.append(f"\nDescription:\n{ticket['description']}")
        
        # Status and Priority
        status = ticket.get("status", "unknown")
        priority = ticket.get("priority", "unknown")
        content_parts.append(f"\nStatus: {status}, Priority: {priority}")
        
        # Tags
        if ticket.get("tags"):
            content_parts.append(f"\nTags: {', '.join(ticket['tags'])}")
        
        # Custom fields (if any)
        if ticket.get("custom_fields"):
            custom_fields = []
            for field in ticket["custom_fields"]:
                if field.get("value"):
                    custom_fields.append(f"{field.get('name', 'Field')}: {field['value']}")
            if custom_fields:
                content_parts.append(f"\nCustom Fields: {', '.join(custom_fields)}")
        
        content = "\n".join(content_parts)
        
        # Create metadata
        metadata = {
            "source": "zendesk",
            "source_type": "ticket",
            "ticket_id": str(ticket.get("id")),
            "ticket_url": ticket.get("url", ""),
            "status": status,
            "priority": priority,
            "created_at": ticket.get("created_at", ""),
            "updated_at": ticket.get("updated_at", ""),
            "requester_id": str(ticket.get("requester_id", "")),
            "assignee_id": str(ticket.get("assignee_id", "")),
            "tags": ", ".join(ticket.get("tags", [])),
        }
        
        documents.append(Document(page_content=content, metadata=metadata))
    
    return documents


def sync_zendesk_tickets(
    db: Session,
    user_id: str,
    progress_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Sync Zendesk tickets for a user and ingest them into RAG.
    
    Args:
        db: Database session
        user_id: User ID
        progress_callback: Optional callback function(progress, message) for progress updates
        
    Returns:
        Dictionary with sync results
    """
    config = get_zendesk_config(db, user_id)
    if not config:
        raise ValueError("Zendesk not configured for this user")
    
    if progress_callback:
        progress_callback(0, "Starting Zendesk sync...")
    
    # Decrypt API token
    config_data = config.config_data
    api_token = config_data.get("api_token")
    if api_token:
        try:
            api_token = decrypt_api_key(api_token)
        except Exception as e:
            raise ValueError(f"Failed to decrypt API token: {str(e)}")
    
    subdomain = config_data.get("subdomain")
    email = config_data.get("email")
    
    if not all([subdomain, email, api_token]):
        raise ValueError("Zendesk configuration incomplete")
    
    # Update sync status
    config.sync_status = "syncing"
    config.sync_error = None
    db.commit()
    
    try:
        if progress_callback:
            progress_callback(10, "Fetching tickets from Zendesk...")
        
        # Fetch tickets
        tickets = fetch_zendesk_tickets(subdomain, email, api_token)
        
        if progress_callback:
            progress_callback(30, f"Fetched {len(tickets)} tickets. Converting to documents...")
        
        # Convert to documents
        documents = convert_tickets_to_documents(tickets)
        
        if progress_callback:
            progress_callback(50, f"Converted {len(documents)} documents. Ingesting into RAG...")
        
        # Ingest into RAG
        collection_name = get_user_collection_name(user_id)
        success = ingest_documents(
            documents=documents,
            collection_name=collection_name,
            metadata={"source": "zendesk", "synced_at": datetime.utcnow().isoformat()}
        )
        
        if not success:
            raise Exception("Failed to ingest documents into RAG")
        
        if progress_callback:
            progress_callback(100, f"Successfully synced {len(tickets)} tickets")
        
        # Update sync status
        config.sync_status = "completed"
        config.last_sync_at = datetime.utcnow()
        config.sync_error = None
        db.commit()
        
        return {
            "success": True,
            "tickets_synced": len(tickets),
            "documents_created": len(documents),
            "last_sync_at": config.last_sync_at.isoformat()
        }
        
    except Exception as e:
        # Update sync status with error
        config.sync_status = "failed"
        config.sync_error = str(e)
        db.commit()
        
        if progress_callback:
            progress_callback(0, f"Sync failed: {str(e)}")
        
        raise

