"""Background worker service for sync jobs with persistent progress tracking using RabbitMQ."""
import threading
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Connector, SyncJob, ToolConfig, KnowledgeBase
from app.models.connector import SyncJobStatus, ConnectorType, ConnectorStatus
from app.services.zendesk_service import (
    fetch_zendesk_tickets,
    convert_tickets_to_documents,
    get_zendesk_config
)
from app.services.ingest import ingest_documents, get_user_collection_name
from app.services.llm_service import decrypt_api_key
from app.services.rabbitmq_service import get_rabbitmq_service
from app.helpers.vector_db_helper import get_user_vector_db_url
from app.models.base import get_db
from app.constants import SourceType

logger = logging.getLogger(__name__)


class SyncWorker:
    """Background worker for processing sync jobs from RabbitMQ."""
    
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._rabbitmq = get_rabbitmq_service()
    
    def start(self):
        """Start the worker thread to consume from RabbitMQ."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logger.info("Sync worker started, consuming from RabbitMQ")
    
    def stop(self):
        """Stop the worker thread."""
        self._running = False
        if self._rabbitmq:
            self._rabbitmq.stop_consuming()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Sync worker stopped")
    
    def _worker_loop(self):
        """Main worker loop that consumes jobs from RabbitMQ."""
        def process_message(message: Dict[str, Any]):
            """Process a job message from RabbitMQ."""
            job_id = message.get('job_id')
            if not job_id:
                logger.error("Received message without job_id")
                return
            
            # Process job in a separate thread to avoid blocking
            thread = threading.Thread(
                target=self._process_job,
                args=(job_id,),
                daemon=True
            )
            thread.start()
        
        # Start consuming from RabbitMQ
        try:
            self._rabbitmq.consume_jobs(process_message, auto_ack=False)
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            # Try to reconnect and retry
            if self._running:
                logger.info("Attempting to reconnect to RabbitMQ...")
                import time
                time.sleep(5)
                if self._running:
                    self._worker_loop()  # Retry
    
    def _process_job(self, job_id: int):
        """Process a single sync job."""
        db = next(get_db())
        
        try:
            job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
            if not job:
                logger.warning(f"Job {job_id} not found in database")
                return
            
            # Check if job is already being processed or completed
            if job.status in [SyncJobStatus.PROCESSING, SyncJobStatus.INDEXING]:
                logger.info(f"Job {job_id} is already being processed")
                return
            if job.status in [SyncJobStatus.COMPLETED, SyncJobStatus.FAILED, SyncJobStatus.CANCELLED]:
                logger.info(f"Job {job_id} is already {job.status.value}")
                return
            
            # Update job status to processing
            job.status = SyncJobStatus.PROCESSING
            job.started_at = datetime.utcnow()
            job.progress_percentage = 0
            job.current_step = "Initializing sync..."
            db.commit()
            
            # Process based on source type
            if job.source_type == SourceType.ZENDESK.value:
                self._process_zendesk_sync(db, job)
            else:
                raise ValueError(f"Unsupported source type: {job.source_type}")
            
        except Exception as e:
            # Update job with error
            try:
                job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
                if job:
                    job.status = SyncJobStatus.FAILED
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    db.commit()
            except:
                pass
            
            print(f"Error processing job {job_id}: {e}")
        finally:
            db.close()
            with self._lock:
                self._active_jobs.pop(job_id, None)
    
    def _process_zendesk_sync(self, db: Session, job: SyncJob):
        """Process a Zendesk sync job."""
        try:
            # Update progress
            job.current_step = "Fetching Zendesk configuration..."
            job.progress_percentage = 5
            db.commit()
            
            # Get Zendesk config
            config = get_zendesk_config(db, job.user_id)
            if not config:
                raise ValueError("Zendesk not configured for this user")
            
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
            
            # Update progress
            job.current_step = "Fetching tickets from Zendesk..."
            job.progress_percentage = 10
            db.commit()
            
            # Fetch tickets
            max_tickets = job.sync_scope.get("max_tickets") if job.sync_scope else None
            tickets = fetch_zendesk_tickets(
                subdomain=subdomain,
                email=email,
                api_token=api_token,
                max_tickets=max_tickets
            )
            
            job.items_total = len(tickets)
            job.current_step = f"Fetched {len(tickets)} tickets. Converting to documents..."
            job.progress_percentage = 30
            db.commit()
            
            # Convert to documents
            documents = convert_tickets_to_documents(tickets)
            
            job.current_step = f"Converted {len(documents)} documents. Indexing..."
            job.progress_percentage = 50
            job.status = SyncJobStatus.INDEXING
            db.commit()
            
            # Get user's vector DB configuration
            from app.models import UserSettings
            user_settings = db.query(UserSettings).filter(
                UserSettings.user_id == job.user_id
            ).first()
            user_vector_db_url = get_user_vector_db_url(user_settings)
            
            # Create or get knowledge base
            kb = db.query(KnowledgeBase).filter(
                KnowledgeBase.id == job.knowledge_base_id
            ).first() if job.knowledge_base_id else None
            
            if not kb:
                kb = KnowledgeBase(
                    user_id=job.user_id,
                    organization_id=job.organization_id,
                    name=f"Zendesk Tickets ({datetime.utcnow().strftime('%Y-%m-%d')})",
                    source_type=SourceType.ZENDESK.value,
                    source_id="zendesk_sync",
                    extra_metadata={
                        "sync_job_id": job.id,
                        "tickets_count": len(tickets)
                    },
                    document_count=0,
                    is_active=True
                )
                db.add(kb)
                db.flush()
                job.knowledge_base_id = kb.id
                db.commit()
            
            # Ingest documents
            collection_name = get_user_collection_name(job.user_id, kb.id)
            metadata = {
                "source": "zendesk",
                "source_type": SourceType.ZENDESK.value,
                "user_id": job.user_id,
                "knowledge_base_id": kb.id,
                "synced_at": datetime.utcnow().isoformat()
            }
            
            # Update progress during ingestion
            job.progress_percentage = 60
            job.current_step = "Ingesting documents into vector database..."
            db.commit()
            
            success = ingest_documents(
                documents=documents,
                collection_name=collection_name,
                metadata=metadata,
                db_url=user_vector_db_url,
                source_type=SourceType.ZENDESK.value
            )
            
            if not success:
                raise Exception("Failed to ingest documents into vector database")
            
            # Update knowledge base
            kb.document_count = len(documents)
            db.commit()
            
            # Complete job
            job.status = SyncJobStatus.COMPLETED
            job.progress_percentage = 100
            job.current_step = f"Successfully synced {len(tickets)} tickets"
            job.items_processed = len(tickets)
            job.items_indexed = len(documents)
            job.completed_at = datetime.utcnow()
            db.commit()
            
            # Update connector last_sync_at if applicable
            if job.connector_id:
                connector = db.query(Connector).filter(Connector.id == job.connector_id).first()
                if connector:
                    connector.last_sync_at = datetime.utcnow()
                    connector.status = ConnectorStatus.CONNECTED
                    connector.error_message = None
                    db.commit()
            
        except Exception as e:
            job.status = SyncJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
            raise


# Global worker instance
_worker: Optional[SyncWorker] = None


def get_sync_worker() -> SyncWorker:
    """Get or create the global sync worker instance."""
    global _worker
    if _worker is None:
        _worker = SyncWorker()
        _worker.start()
    return _worker


def create_zendesk_sync_job(
    db: Session,
    user_id: str,
    organization_id: Optional[int] = None,
    connector_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    sync_scope: Optional[Dict[str, Any]] = None,
    priority: int = 5
) -> SyncJob:
    """
    Create a Zendesk sync job.
    
    Args:
        db: Database session
        user_id: User ID
        organization_id: Optional organization ID
        connector_id: Optional connector ID
        knowledge_base_id: Optional knowledge base ID (will create if not provided)
        sync_scope: Optional sync scope (e.g., max_tickets, date_range)
        priority: Job priority (1-10, lower = higher priority)
        
    Returns:
        Created SyncJob instance
    """
    # Create sync job
    # Note: connector_id is nullable for tools like Zendesk that use ToolConfig instead of Connector
    job = SyncJob(
        connector_id=connector_id,  # Can be None for Zendesk
        user_id=user_id,
        organization_id=organization_id,
        source_type=SourceType.ZENDESK.value,
        sync_scope=sync_scope or {},
        priority=priority,
        status=SyncJobStatus.QUEUED,
        progress_percentage=0,
        current_step="Queued for processing...",
        items_processed=0,
        items_total=None,
        knowledge_base_id=knowledge_base_id,
        items_indexed=0
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Publish job to RabbitMQ queue
    rabbitmq = get_rabbitmq_service()
    job_data = {
        "source_type": job.source_type,
        "user_id": job.user_id,
        "organization_id": job.organization_id,
        "connector_id": job.connector_id,
        "knowledge_base_id": job.knowledge_base_id,
        "sync_scope": job.sync_scope,
        "priority": job.priority
    }
    
    if rabbitmq.publish_job(job.id, job_data):
        logger.info(f"Published sync job {job.id} to RabbitMQ queue")
    else:
        logger.warning(f"Failed to publish job {job.id} to RabbitMQ, but job created in database")
        # Job will be picked up on next worker restart or can be manually triggered
    
    # Ensure worker is running
    get_sync_worker()
    
    return job
