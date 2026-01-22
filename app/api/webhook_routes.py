"""Webhook routes for receiving notifications from connected apps."""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import User, Connector
from app.models.base import get_db
from app.models.connector import ConnectorType, ConnectorStatus
from app.services.auth_service import get_current_user
from app.services.sync_worker import create_connector_sync_job
from app.helpers.logging_helper import ActivityLogger
from datetime import datetime

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class WebhookPayload(BaseModel):
    """Generic webhook payload."""
    connector_type: Optional[str] = None
    connector_id: Optional[int] = None
    event_type: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@router.post("/connector/{connector_id}")
async def handle_connector_webhook(
    connector_id: int,
    payload: WebhookPayload,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Handle webhook notifications from connected apps.
    Triggers a manual sync for the connector.
    """
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="webhook_received",
        endpoint=f"/api/webhooks/connector/{connector_id}",
        method="POST",
        user_id=current_user.id,
        metadata={"connector_id": connector_id, "event_type": payload.event_type}
    )
    
    try:
        # Get connector
        connector = db.query(Connector).filter(
            Connector.id == connector_id,
            Connector.user_id == current_user.id
        ).first()
        
        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")
        
        if connector.status != ConnectorStatus.CONNECTED:
            raise HTTPException(
                status_code=400,
                detail=f"Connector is not connected (status: {connector.status.value})"
            )
        
        # Check if there's already an active sync job
        from app.models.connector import SyncJob, SyncJobStatus
        active_jobs = db.query(SyncJob).filter(
            SyncJob.connector_id == connector_id,
            SyncJob.status.in_([
                SyncJobStatus.PENDING,
                SyncJobStatus.QUEUED,
                SyncJobStatus.PROCESSING,
                SyncJobStatus.INDEXING
            ])
        ).count()
        
        if active_jobs > 0:
            activity_logger.log_success({
                "message": "Sync already in progress",
                "active_jobs": active_jobs
            })
            return {
                "status": "queued",
                "message": "A sync is already in progress for this connector"
            }
        
        # Create sync job with resume functionality
        # The sync will resume from last_sync_at if available
        sync_scope = payload.data or {}
        
        # Add webhook event info to sync scope
        sync_scope["webhook_triggered"] = True
        sync_scope["webhook_event_type"] = payload.event_type
        sync_scope["webhook_received_at"] = datetime.utcnow().isoformat()
        
        sync_job = create_connector_sync_job(
            db=db,
            connector_id=connector_id,
            user_id=current_user.id,
            organization_id=connector.organization_id,
            knowledge_base_id=None,  # Will be created automatically
            sync_scope=sync_scope,
            priority=3  # Higher priority for webhook-triggered syncs
        )
        
        activity_logger.log_success({
            "job_id": sync_job.id,
            "connector_id": connector_id,
            "event_type": payload.event_type
        })
        
        return {
            "status": "queued",
            "job_id": sync_job.id,
            "message": f"Sync queued for {connector.connector_type.value}",
            "job": sync_job.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-sync/{connector_id}")
async def manual_sync_connector(
    connector_id: int,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger a sync for a connector.
    This will resume from the last sync point.
    """
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="manual_sync",
        endpoint=f"/api/webhooks/manual-sync/{connector_id}",
        method="POST",
        user_id=current_user.id,
        metadata={"connector_id": connector_id}
    )
    
    try:
        # Get connector
        connector = db.query(Connector).filter(
            Connector.id == connector_id,
            Connector.user_id == current_user.id
        ).first()
        
        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")
        
        if connector.status != ConnectorStatus.CONNECTED:
            raise HTTPException(
                status_code=400,
                detail=f"Connector is not connected (status: {connector.status.value})"
            )
        
        # Check for active sync jobs
        from app.models.connector import SyncJob, SyncJobStatus
        active_jobs = db.query(SyncJob).filter(
            SyncJob.connector_id == connector_id,
            SyncJob.status.in_([
                SyncJobStatus.PENDING,
                SyncJobStatus.QUEUED,
                SyncJobStatus.PROCESSING,
                SyncJobStatus.INDEXING
            ])
        ).count()
        
        if active_jobs > 0:
            raise HTTPException(
                status_code=400,
                detail="A sync is already in progress for this connector"
            )
        
        # Create sync job (will resume from last_sync_at)
        sync_job = create_connector_sync_job(
            db=db,
            connector_id=connector_id,
            user_id=current_user.id,
            organization_id=connector.organization_id,
            knowledge_base_id=None,
            sync_scope={"manual_trigger": True},
            priority=5
        )
        
        activity_logger.log_success({
            "job_id": sync_job.id,
            "connector_id": connector_id
        })
        
        return {
            "status": "queued",
            "job_id": sync_job.id,
            "message": f"Manual sync queued for {connector.connector_type.value}",
            "job": sync_job.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
