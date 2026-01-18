"""Unit tests for connector models."""
import pytest
from datetime import datetime
from app.models import Connector, SyncJob, ConnectorType, ConnectorStatus, SyncJobStatus
from app.models.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session():
    """Create in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "test_user_123"


class TestConnector:
    """Test suite for Connector model."""
    
    def test_connector_creation(self, db_session, sample_user_id):
        """Test creating a connector."""
        connector = Connector(
            user_id=sample_user_id,
            connector_type=ConnectorType.SLACK,
            connector_name="My Slack Workspace",
            status=ConnectorStatus.CONNECTED,
            auto_sync_enabled=True,
            sync_interval_hours=24
        )
        
        db_session.add(connector)
        db_session.commit()
        
        assert connector.id is not None
        assert connector.connector_type == ConnectorType.SLACK
        assert connector.status == ConnectorStatus.CONNECTED
        assert connector.auto_sync_enabled is True
    
    def test_connector_to_dict(self, db_session, sample_user_id):
        """Test connector to_dict method."""
        connector = Connector(
            user_id=sample_user_id,
            connector_type=ConnectorType.TEAMS,
            connector_name="My Teams",
            status=ConnectorStatus.CONNECTED
        )
        
        db_session.add(connector)
        db_session.commit()
        
        result = connector.to_dict()
        
        assert "id" in result
        assert result["connector_type"] == "teams"
        assert result["status"] == "connected"
        assert result["user_id"] == sample_user_id
    
    def test_connector_status_enum(self, db_session, sample_user_id):
        """Test connector status enum values."""
        statuses = [
            ConnectorStatus.DISCONNECTED,
            ConnectorStatus.CONNECTED,
            ConnectorStatus.ERROR,
            ConnectorStatus.EXPIRED
        ]
        
        for status in statuses:
            connector = Connector(
                user_id=sample_user_id,
                connector_type=ConnectorType.ONEDRIVE,
                connector_name=f"Test {status.value}",
                status=status
            )
            db_session.add(connector)
        
        db_session.commit()
        
        connectors = db_session.query(Connector).all()
        assert len(connectors) == 4


class TestSyncJob:
    """Test suite for SyncJob model."""
    
    def test_sync_job_creation(self, db_session, sample_user_id):
        """Test creating a sync job."""
        # First create a connector
        connector = Connector(
            user_id=sample_user_id,
            connector_type=ConnectorType.SLACK,
            connector_name="Test Connector",
            status=ConnectorStatus.CONNECTED
        )
        db_session.add(connector)
        db_session.flush()
        
        sync_job = SyncJob(
            connector_id=connector.id,
            user_id=sample_user_id,
            source_type="slack",
            status=SyncJobStatus.PENDING,
            priority=5
        )
        
        db_session.add(sync_job)
        db_session.commit()
        
        assert sync_job.id is not None
        assert sync_job.status == SyncJobStatus.PENDING
        assert sync_job.progress_percentage == 0
    
    def test_sync_job_progress_update(self, db_session, sample_user_id):
        """Test updating sync job progress."""
        connector = Connector(
            user_id=sample_user_id,
            connector_type=ConnectorType.SLACK,
            connector_name="Test",
            status=ConnectorStatus.CONNECTED
        )
        db_session.add(connector)
        db_session.flush()
        
        sync_job = SyncJob(
            connector_id=connector.id,
            user_id=sample_user_id,
            source_type="slack",
            status=SyncJobStatus.PROCESSING
        )
        db_session.add(sync_job)
        db_session.commit()
        
        # Update progress
        sync_job.progress_percentage = 50
        sync_job.current_step = "Indexing documents"
        sync_job.items_processed = 100
        sync_job.items_total = 200
        db_session.commit()
        
        updated = db_session.query(SyncJob).filter_by(id=sync_job.id).first()
        assert updated.progress_percentage == 50
        assert updated.current_step == "Indexing documents"
        assert updated.items_processed == 100
    
    def test_sync_job_status_transitions(self, db_session, sample_user_id):
        """Test sync job status transitions."""
        connector = Connector(
            user_id=sample_user_id,
            connector_type=ConnectorType.SLACK,
            connector_name="Test",
            status=ConnectorStatus.CONNECTED
        )
        db_session.add(connector)
        db_session.flush()
        
        sync_job = SyncJob(
            connector_id=connector.id,
            user_id=sample_user_id,
            source_type="slack",
            status=SyncJobStatus.PENDING
        )
        db_session.add(sync_job)
        db_session.commit()
        
        # Transition: PENDING -> QUEUED -> PROCESSING -> COMPLETED
        assert sync_job.status == SyncJobStatus.PENDING
        
        sync_job.status = SyncJobStatus.QUEUED
        db_session.commit()
        assert sync_job.status == SyncJobStatus.QUEUED
        
        sync_job.status = SyncJobStatus.PROCESSING
        sync_job.started_at = datetime.utcnow()
        db_session.commit()
        assert sync_job.status == SyncJobStatus.PROCESSING
        
        sync_job.status = SyncJobStatus.COMPLETED
        sync_job.completed_at = datetime.utcnow()
        db_session.commit()
        assert sync_job.status == SyncJobStatus.COMPLETED
