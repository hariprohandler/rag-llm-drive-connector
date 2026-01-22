"""API routes for third-party tool integrations."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import User, ToolConfig, SyncJob
from app.models.connector import SyncJobStatus, Connector, ConnectorStatus
from app.models.base import get_db
from app.services.auth_service import get_current_user
from app.services.sync_worker import create_zendesk_sync_job, get_sync_worker
from app.services.llm_service import encrypt_api_key
from app.helpers.logging_helper import ActivityLogger


router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolConfigRequest(BaseModel):
    tool_name: str
    is_active: bool = True
    config_data: dict


class ToolConfigUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    config_data: Optional[dict] = None


class SyncRequest(BaseModel):
    tool_name: str
    sync_scope: Optional[dict] = None  # e.g., {"max_tickets": 100, "date_range": {...}}
    priority: int = 5  # 1-10, lower = higher priority


@router.get("")
async def list_tools(
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all available tools and their configurations for the current user."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="tool_list",
        endpoint="/api/tools",
        method="GET",
        user_id=current_user.id,
        metadata={}
    )
    
    try:
        tools = db.query(ToolConfig).filter(
            ToolConfig.user_id == current_user.id
        ).all()
        
        # Available tools (others disabled for now)
        available_tools = {
        "zendesk": {
            "name": "Zendesk",
            "description": "Sync support tickets from Zendesk",
            "icon": "🎫",
            "enabled": True,
            "config_fields": [
                {"name": "subdomain", "label": "Subdomain", "type": "text", "required": True, "help": "Your Zendesk subdomain (e.g., 'mycompany' for mycompany.zendesk.com)"},
                {"name": "email", "label": "Email", "type": "email", "required": True, "help": "Your Zendesk account email"},
                {"name": "api_token", "label": "API Token", "type": "password", "required": True, "help": "Zendesk API token (Admin > API > Zendesk API)"}
            ]
        },
        "slack": {
            "name": "Slack",
            "description": "Sync messages and conversations from Slack",
            "icon": "💬",
            "enabled": True,
            "config_fields": [
                {"name": "access_token", "label": "Slack Access Token", "type": "password", "required": True, "help": "Slack Bot User OAuth Token (xoxb-...)"},
                {"name": "channel_ids", "label": "Channel IDs (optional)", "type": "text", "required": False, "help": "Comma-separated list of channel IDs to sync (leave empty for all channels)"}
            ]
        },
        "teams": {
            "name": "Microsoft Teams",
            "description": "Sync messages and conversations from Teams",
            "icon": "👥",
            "enabled": True,
            "requires_oauth": True,
            "provider": "microsoft"
        },
        "outlook": {
            "name": "Outlook",
            "description": "Sync emails from Outlook",
            "icon": "📧",
            "enabled": True,
            "requires_oauth": True,
            "provider": "microsoft"
        },
        "gmail": {
            "name": "Gmail",
            "description": "Sync emails from Gmail",
            "icon": "📨",
            "enabled": True,
            "requires_oauth": True,
            "provider": "google"
        },
        }
        
        # Map user's tool configs
        user_configs = {tool.tool_name: tool.to_dict() for tool in tools}
        
        # Merge with available tools
        result = []
        for tool_key, tool_info in available_tools.items():
            tool_data = {
                "tool_name": tool_key,
                **tool_info,
                "config": user_configs.get(tool_key)
            }
            result.append(tool_data)
        
        activity_logger.log_success({"tools_count": len(result), "configured_count": len(tools)})
        return result
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tool_name}")
async def get_tool_config(
    tool_name: str,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get configuration for a specific tool."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="tool_config_get",
        endpoint=f"/api/tools/{tool_name}",
        method="GET",
        user_id=current_user.id,
        metadata={"tool_name": tool_name}
    )
    
    try:
        tool = db.query(ToolConfig).filter(
            ToolConfig.user_id == current_user.id,
            ToolConfig.tool_name == tool_name
        ).first()
        
        if not tool:
            activity_logger.log_error("Tool configuration not found", status_code=404)
            raise HTTPException(status_code=404, detail="Tool configuration not found")
        
        activity_logger.log_success({"tool_config_id": tool.id})
        return tool.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_tool_config(
    request: ToolConfigRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a tool configuration."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="tool_config_create",
        endpoint="/api/tools",
        method="POST",
        user_id=current_user.id,
        metadata={"tool_name": request.tool_name}
    )
    
    try:
        # Validate tool name
        available_tools = ["zendesk", "gmail", "outlook", "teams", "slack"]
        if request.tool_name not in available_tools:
            raise HTTPException(status_code=400, detail=f"Tool '{request.tool_name}' is not available")
        
        # Check if config already exists
        existing = db.query(ToolConfig).filter(
            ToolConfig.user_id == current_user.id,
            ToolConfig.tool_name == request.tool_name
        ).first()
        
        # Encrypt sensitive fields
        config_data = request.config_data.copy()
        if "api_token" in config_data and config_data["api_token"]:
            # Only encrypt if it's not already masked
            if config_data["api_token"] != "••••••••":
                config_data["api_token"] = encrypt_api_key(config_data["api_token"])
        
        if existing:
            # Update existing config
            existing.is_active = request.is_active
            existing.config_data = config_data
            existing.sync_status = None
            existing.sync_error = None
            db.commit()
            db.refresh(existing)
            activity_logger.log_success({"tool_config_id": existing.id, "action": "updated"})
            return existing.to_dict()
        else:
            # Create new config
            tool_config = ToolConfig(
                user_id=current_user.id,
                tool_name=request.tool_name,
                is_active=request.is_active,
                config_data=config_data
            )
            db.add(tool_config)
            db.commit()
            db.refresh(tool_config)
            activity_logger.log_success({"tool_config_id": tool_config.id, "action": "created"})
            return tool_config.to_dict()
            
    except HTTPException:
        raise
    except ValueError as e:
        # Handle encryption key errors with user-friendly message
        error_msg = str(e)
        if "ENCRYPTION_KEY" in error_msg or "encrypt" in error_msg.lower() or "Fernet" in error_msg:
            activity_logger.log_error(f"Encryption configuration error: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail="System configuration error: Encryption key is not properly configured. Please contact system administrator."
            )
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{tool_name}")
async def update_tool_config(
    tool_name: str,
    request: ToolConfigUpdateRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a tool configuration."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="tool_config_update",
        endpoint=f"/api/tools/{tool_name}",
        method="PUT",
        user_id=current_user.id,
        metadata={"tool_name": tool_name}
    )
    
    try:
        tool = db.query(ToolConfig).filter(
            ToolConfig.user_id == current_user.id,
            ToolConfig.tool_name == tool_name
        ).first()
        
        if not tool:
            raise HTTPException(status_code=404, detail="Tool configuration not found")
        
        if request.is_active is not None:
            tool.is_active = request.is_active
        
        if request.config_data is not None:
            # Encrypt sensitive fields
            config_data = request.config_data.copy()
            existing_config = tool.config_data or {}
            
            # Handle API token: only update if a new value is provided
            if "api_token" in config_data:
                if not config_data["api_token"] or config_data["api_token"].strip() == "":
                    # Empty token means keep existing (user didn't change it)
                    if "api_token" in existing_config:
                        config_data["api_token"] = existing_config["api_token"]
                    else:
                        # No existing token, remove from update
                        config_data.pop("api_token", None)
                elif config_data["api_token"] != "••••••••":
                    # New token provided, encrypt it
                    config_data["api_token"] = encrypt_api_key(config_data["api_token"])
                else:
                    # Masked token means keep existing
                    if "api_token" in existing_config:
                        config_data["api_token"] = existing_config["api_token"]
            
            # Merge with existing config to preserve fields not being updated
            merged_config = {**existing_config, **config_data}
            tool.config_data = merged_config
        
        db.commit()
        db.refresh(tool)
        activity_logger.log_success({"tool_config_id": tool.id})
        return tool.to_dict()
        
    except HTTPException:
        raise
    except ValueError as e:
        # Handle encryption key errors with user-friendly message
        error_msg = str(e)
        if "ENCRYPTION_KEY" in error_msg or "encrypt" in error_msg.lower() or "Fernet" in error_msg:
            activity_logger.log_error(f"Encryption configuration error: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail="System configuration error: Encryption key is not properly configured. Please contact system administrator."
            )
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tool_name}")
async def delete_tool_config(
    tool_name: str,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a tool configuration."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="tool_config_delete",
        endpoint=f"/api/tools/{tool_name}",
        method="DELETE",
        user_id=current_user.id,
        metadata={"tool_name": tool_name}
    )
    
    tool = db.query(ToolConfig).filter(
        ToolConfig.user_id == current_user.id,
        ToolConfig.tool_name == tool_name
    ).first()
    
    if not tool:
        raise HTTPException(status_code=404, detail="Tool configuration not found")
    
    db.delete(tool)
    db.commit()
    activity_logger.log_success({"tool_config_id": tool.id})
    return {"status": "success", "message": "Tool configuration deleted"}


@router.post("/sync")
async def sync_tool(
    request: SyncRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a background sync for a tool using persistent SyncJob."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="tool_sync_start",
        endpoint="/api/tools/sync",
        method="POST",
        user_id=current_user.id,
        metadata={"tool_name": request.tool_name}
    )
    
    try:
        # Validate tool is configured
        tool = db.query(ToolConfig).filter(
            ToolConfig.user_id == current_user.id,
            ToolConfig.tool_name == request.tool_name,
            ToolConfig.is_active == True
        ).first()
        
        if not tool:
            raise HTTPException(
                status_code=400,
                detail=f"Tool '{request.tool_name}' is not configured or not active"
            )
        
        # Validate tool name
        available_tools = ["zendesk", "gmail", "outlook", "teams", "slack"]
        if request.tool_name not in available_tools:
            raise HTTPException(
                status_code=400,
                detail=f"Tool '{request.tool_name}' sync is not available"
            )
        
        # For connectors (Gmail, Outlook, Teams, Slack), use connector sync
        if request.tool_name in ["gmail", "outlook", "teams", "slack"]:
            from app.models.connector import ConnectorType
            from app.services.sync_worker import create_connector_sync_job
            
            # Map tool name to connector type
            type_map = {
                "gmail": ConnectorType.GMAIL,
                "outlook": ConnectorType.OUTLOOK,
                "teams": ConnectorType.TEAMS,
                "slack": ConnectorType.SLACK
            }
            
            connector_type = type_map[request.tool_name]
            
            # Find or create connector
            connector = db.query(Connector).filter(
                Connector.user_id == current_user.id,
                Connector.connector_type == connector_type,
                Connector.is_active == True
            ).first()
            
            if not connector:
                raise HTTPException(
                    status_code=400,
                    detail=f"{request.tool_name.title()} connector not found. Please connect your {request.tool_name} account first."
                )
            
            if connector.status != ConnectorStatus.CONNECTED:
                raise HTTPException(
                    status_code=400,
                    detail=f"{request.tool_name.title()} connector is not connected. Please connect your account first."
                )
            
            # Create connector sync job
            sync_job = create_connector_sync_job(
                db=db,
                connector_id=connector.id,
                user_id=current_user.id,
                organization_id=connector.organization_id,
                knowledge_base_id=None,
                sync_scope=request.sync_scope,
                priority=request.priority
            )
            
            activity_logger.log_success({"job_id": sync_job.id})
            return {
                "status": "queued",
                "job_id": sync_job.id,
                "message": f"Sync queued for {request.tool_name}",
                "job": sync_job.to_dict()
            }
        
        # Check for active sync jobs
        active_jobs = db.query(SyncJob).filter(
            SyncJob.user_id == current_user.id,
            SyncJob.source_type == request.tool_name,
            SyncJob.status.in_([SyncJobStatus.PENDING, SyncJobStatus.QUEUED, SyncJobStatus.PROCESSING, SyncJobStatus.INDEXING])
        ).count()
        
        if active_jobs > 0:
            raise HTTPException(
                status_code=400,
                detail=f"A sync is already in progress for {request.tool_name}. Please wait for it to complete."
            )
        
        # Create sync job
        sync_job = create_zendesk_sync_job(
            db=db,
            user_id=current_user.id,
            organization_id=None,  # Can be added later for org support
            connector_id=None,  # Can be added later
            knowledge_base_id=None,  # Will be created automatically
            sync_scope=request.sync_scope,
            priority=request.priority
        )
        
        # Ensure worker is running
        get_sync_worker()
        
        activity_logger.log_success({"job_id": sync_job.id})
        return {
            "status": "queued",
            "job_id": sync_job.id,
            "message": f"Sync queued for {request.tool_name}",
            "job": sync_job.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/jobs")
async def list_sync_jobs(
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
    status: Optional[str] = None,
):
    """List sync jobs for the current user."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="tool_sync_list",
        endpoint="/api/tools/sync/jobs",
        method="GET",
        user_id=current_user.id,
        metadata={}
    )
    
    try:
        query = db.query(SyncJob).filter(
            SyncJob.user_id == current_user.id
        )
        
        if status:
            try:
                status_enum = SyncJobStatus(status)
                query = query.filter(SyncJob.status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        jobs = query.order_by(desc(SyncJob.created_at)).limit(limit).all()
        
        activity_logger.log_success({"jobs_count": len(jobs)})
        return {
            "jobs": [job.to_dict() for job in jobs],
            "total": len(jobs)
        }
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/jobs/{job_id}")
async def get_sync_job_status(
    job_id: int,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status of a specific sync job."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="tool_sync_status",
        endpoint=f"/api/tools/sync/jobs/{job_id}",
        method="GET",
        user_id=current_user.id,
        metadata={"job_id": job_id}
    )
    
    try:
        job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        
        if not job:
            activity_logger.log_error("Job not found", status_code=404)
            raise HTTPException(status_code=404, detail="Sync job not found")
        
        # Verify job belongs to user
        if job.user_id != current_user.id:
            activity_logger.log_error("Access denied", status_code=403)
            raise HTTPException(status_code=403, detail="Access denied")
        
        activity_logger.log_success({"job_id": job_id, "status": job.status.value})
        return job.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

