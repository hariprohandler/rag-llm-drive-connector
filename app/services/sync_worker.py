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
from app.services.connector_services import (
    fetch_gmail_messages,
    fetch_outlook_messages,
    fetch_slack_messages,
    fetch_teams_messages,
    convert_messages_to_documents
)
from app.services.ingest import ingest_documents, get_user_collection_name
from app.services.llm_service import decrypt_api_key
from app.services.rabbitmq_service import get_rabbitmq_service
from app.services.oauth_credential_service import get_google_credentials, get_microsoft_access_token
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
        self._lock = threading.Lock()
        self._active_jobs: Dict[int, bool] = {}
    
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
            elif job.source_type in [SourceType.GMAIL.value, SourceType.OUTLOOK.value, 
                                     SourceType.SLACK.value, SourceType.TEAMS.value]:
                self._process_connector_sync(db, job)
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
            from app.models.user_settings import safe_query_user_settings
            try:
                user_settings = safe_query_user_settings(db, job.user_id)
            except Exception as e:
                print(f"Warning: Could not query user settings: {e}")
                db.rollback()
                user_settings = None
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
    
    def _process_connector_sync(self, db: Session, job: SyncJob):
        """Process a connector sync job (Gmail, Outlook, Teams, Slack)."""
        try:
            # Get connector
            connector = None
            if job.connector_id:
                connector = db.query(Connector).filter(Connector.id == job.connector_id).first()
                if not connector:
                    raise ValueError(f"Connector {job.connector_id} not found")
            
            # Determine last sync date for resume functionality
            after_date = None
            if connector and connector.last_sync_at:
                # Resume from last sync (add 1 second to avoid duplicates)
                after_date = connector.last_sync_at
            elif job.sync_scope and job.sync_scope.get('after_date'):
                # Use provided date from sync scope
                after_date = datetime.fromisoformat(job.sync_scope['after_date'])
            
            # Update progress
            job.current_step = f"Fetching {job.source_type} messages..."
            job.progress_percentage = 10
            db.commit()
            
            # Fetch messages based on source type
            messages = []
            max_results = job.sync_scope.get("max_results", 100) if job.sync_scope else 100
            
            if job.source_type == SourceType.GMAIL.value:
                # Get Google credentials
                credentials = get_google_credentials(db, job.user_id)
                if not credentials:
                    raise ValueError("Gmail not connected. Please connect your Gmail account.")
                
                messages = fetch_gmail_messages(
                    credentials=credentials,
                    user_id=job.user_id,
                    max_results=max_results,
                    after_date=after_date,
                    query=job.sync_scope.get("query") if job.sync_scope else None
                )
            elif job.source_type == SourceType.OUTLOOK.value:
                # Get Microsoft credentials
                access_token = get_microsoft_access_token(db, job.user_id)
                if not access_token:
                    raise ValueError("Outlook not connected. Please connect your Outlook account.")
                
                messages = fetch_outlook_messages(
                    access_token=access_token,
                    user_id=job.user_id,
                    max_results=max_results,
                    after_date=after_date,
                    folder_id=job.sync_scope.get("folder_id") if job.sync_scope else None
                )
            elif job.source_type == SourceType.SLACK.value:
                # Get Slack token from connector config
                if not connector or not connector.config:
                    raise ValueError("Slack connector not configured")
                
                access_token = connector.config.get("access_token")
                if not access_token:
                    raise ValueError("Slack access token not found")
                
                channel_ids = connector.config.get("channel_ids")
                after_timestamp = None
                if after_date:
                    after_timestamp = after_date.timestamp()
                
                messages = fetch_slack_messages(
                    access_token=access_token,
                    user_id=job.user_id,
                    channel_ids=channel_ids,
                    max_results=max_results,
                    after_timestamp=after_timestamp
                )
            elif job.source_type == SourceType.TEAMS.value:
                # Get Microsoft credentials
                access_token = get_microsoft_access_token(db, job.user_id)
                if not access_token:
                    raise ValueError("Teams not connected. Please connect your Microsoft account.")
                
                chat_ids = None
                if connector and connector.config:
                    chat_ids = connector.config.get("chat_ids")
                
                messages = fetch_teams_messages(
                    access_token=access_token,
                    user_id=job.user_id,
                    chat_ids=chat_ids,
                    max_results=max_results,
                    after_date=after_date
                )
            
            job.items_total = len(messages)
            job.current_step = f"Fetched {len(messages)} messages. Converting to documents..."
            job.progress_percentage = 30
            db.commit()
            
            # Convert to documents
            documents = convert_messages_to_documents(
                messages=messages,
                source_type=job.source_type,
                connector_id=job.connector_id,
                user_id=job.user_id,
                knowledge_base_id=job.knowledge_base_id
            )
            
            job.current_step = f"Converted {len(documents)} documents. Indexing..."
            job.progress_percentage = 50
            job.status = SyncJobStatus.INDEXING
            db.commit()
            
            # Get user's vector DB configuration
            from app.models import UserSettings
            from app.models.user_settings import safe_query_user_settings
            try:
                user_settings = safe_query_user_settings(db, job.user_id)
            except Exception as e:
                print(f"Warning: Could not query user settings: {e}")
                db.rollback()
                user_settings = None
            user_vector_db_url = get_user_vector_db_url(user_settings)
            
            # Create or get knowledge base
            kb = db.query(KnowledgeBase).filter(
                KnowledgeBase.id == job.knowledge_base_id
            ).first() if job.knowledge_base_id else None
            
            if not kb:
                kb_name = f"{job.source_type.title()} Messages ({datetime.utcnow().strftime('%Y-%m-%d')})"
                kb = KnowledgeBase(
                    user_id=job.user_id,
                    organization_id=job.organization_id,
                    name=kb_name,
                    source_type=job.source_type,
                    source_id=f"{job.source_type}_sync",
                    extra_metadata={
                        "sync_job_id": job.id,
                        "messages_count": len(messages),
                        "connector_id": job.connector_id
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
                "source": job.source_type,
                "source_type": job.source_type,
                "user_id": job.user_id,
                "knowledge_base_id": kb.id,
                "synced_at": datetime.utcnow().isoformat()
            }
            if job.connector_id:
                metadata["connector_id"] = job.connector_id
            
            # Update progress during ingestion
            job.progress_percentage = 60
            job.current_step = "Ingesting documents into vector database..."
            db.commit()
            
            success = ingest_documents(
                documents=documents,
                collection_name=collection_name,
                metadata=metadata,
                db_url=user_vector_db_url,
                source_type=job.source_type
            )
            
            if not success:
                raise Exception("Failed to ingest documents into vector database")
            
            # Update knowledge base
            kb.document_count = len(documents)
            
            # Add tags to knowledge base based on source type
            from app.models.tag import Tag, DocumentTag
            source_tag_map = {
                SourceType.GMAIL.value: "email",
                SourceType.OUTLOOK.value: "email",
                SourceType.SLACK.value: "messaging",
                SourceType.TEAMS.value: "messaging"
            }
            tag_name = source_tag_map.get(job.source_type)
            if tag_name:
                # Get or create tag
                tag = db.query(Tag).filter(
                    Tag.name == tag_name,
                    Tag.user_id == job.user_id,
                    Tag.is_system == True
                ).first()
                
                if not tag:
                    import re
                    tag_slug = re.sub(r'[^a-z0-9]+', '-', tag_name.lower()).strip('-')
                    tag = Tag(
                        name=tag_name,
                        slug=tag_slug,
                        user_id=job.user_id,
                        is_system=True,
                        is_active=True
                    )
                    db.add(tag)
                    db.flush()
                
                # Associate tag with knowledge base if not already associated
                existing_doc_tag = db.query(DocumentTag).filter(
                    DocumentTag.knowledge_base_id == kb.id,
                    DocumentTag.tag_id == tag.id
                ).first()
                
                if not existing_doc_tag:
                    doc_tag = DocumentTag(
                        knowledge_base_id=kb.id,
                        tag_id=tag.id,
                        added_by=job.user_id
                    )
                    db.add(doc_tag)
                    tag.usage_count += 1
            
            db.commit()
            
            # Complete job
            job.status = SyncJobStatus.COMPLETED
            job.progress_percentage = 100
            job.current_step = f"Successfully synced {len(messages)} messages"
            job.items_processed = len(messages)
            job.items_indexed = len(documents)
            job.completed_at = datetime.utcnow()
            db.commit()
            
            # Update connector last_sync_at
            if connector:
                connector.last_sync_at = datetime.utcnow()
                connector.status = ConnectorStatus.CONNECTED
                connector.error_message = None
                db.commit()
            
        except Exception as e:
            job.status = SyncJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            if connector:
                connector.status = ConnectorStatus.ERROR
                connector.error_message = str(e)
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


def create_connector_sync_job(
    db: Session,
    connector_id: int,
    user_id: str,
    organization_id: Optional[int] = None,
    knowledge_base_id: Optional[int] = None,
    sync_scope: Optional[Dict[str, Any]] = None,
    priority: int = 5
) -> SyncJob:
    """
    Create a connector sync job (Gmail, Outlook, Teams, Slack).
    
    Args:
        db: Database session
        connector_id: Connector ID
        user_id: User ID
        organization_id: Optional organization ID
        knowledge_base_id: Optional knowledge base ID (will create if not provided)
        sync_scope: Optional sync scope (e.g., max_results, after_date, query, folder_id, channel_ids)
        priority: Job priority (1-10, lower = higher priority)
        
    Returns:
        Created SyncJob instance
    """
    # Get connector to determine source type
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise ValueError(f"Connector {connector_id} not found")
    
    # Map connector type to source type
    source_type_map = {
        ConnectorType.GMAIL: SourceType.GMAIL.value,
        ConnectorType.OUTLOOK: SourceType.OUTLOOK.value,
        ConnectorType.SLACK: SourceType.SLACK.value,
        ConnectorType.TEAMS: SourceType.TEAMS.value,
    }
    
    source_type = source_type_map.get(connector.connector_type)
    if not source_type:
        raise ValueError(f"Connector type {connector.connector_type} does not support sync")
    
    # Create sync job
    job = SyncJob(
        connector_id=connector_id,
        user_id=user_id,
        organization_id=organization_id,
        source_type=source_type,
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
        logger.info(f"Published connector sync job {job.id} to RabbitMQ queue")
    else:
        logger.warning(f"Failed to publish job {job.id} to RabbitMQ, but job created in database")
    
    # Ensure worker is running
    get_sync_worker()
    
    return job
