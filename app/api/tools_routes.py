"""API routes for third-party tool integrations."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
import threading

from app.models import User, ToolConfig
from app.models.base import get_db
from app.services.auth_service import get_current_user
from app.services.tool_sync_task import create_tool_sync_task, get_tool_sync_task, run_tool_sync_task
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


@router.get("")
async def list_tools(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all available tools and their configurations for the current user."""
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
            "enabled": False,
        },
        "teams": {
            "name": "Microsoft Teams",
            "description": "Sync messages and conversations from Teams",
            "icon": "👥",
            "enabled": False,
        },
        "outlook": {
            "name": "Outlook",
            "description": "Sync emails from Outlook",
            "icon": "📧",
            "enabled": False,
        },
        "gmail": {
            "name": "Gmail",
            "description": "Sync emails from Gmail",
            "icon": "📨",
            "enabled": False,
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
    
    return result


@router.get("/{tool_name}")
async def get_tool_config(
    tool_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get configuration for a specific tool."""
    tool = db.query(ToolConfig).filter(
        ToolConfig.user_id == current_user.id,
        ToolConfig.tool_name == tool_name
    ).first()
    
    if not tool:
        raise HTTPException(status_code=404, detail="Tool configuration not found")
    
    return tool.to_dict()


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
        if request.tool_name not in ["zendesk"]:
            raise HTTPException(status_code=400, detail=f"Tool '{request.tool_name}' is not available yet")
        
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
    background_tasks: BackgroundTasks,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a background sync for a tool."""
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
        
        # Create sync task
        task = create_tool_sync_task(
            user_id=current_user.id,
            tool_name=request.tool_name
        )
        
        # Run in background
        def run_task():
            run_tool_sync_task(task)
        
        thread = threading.Thread(target=run_task, daemon=True)
        thread.start()
        
        activity_logger.log_success({"task_id": task.task_id})
        return {
            "status": "started",
            "task_id": task.task_id,
            "message": f"Sync started for {request.tool_name}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/{task_id}")
async def get_sync_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get the status of a sync task."""
    task = get_tool_sync_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Verify task belongs to user
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return task.to_dict()

