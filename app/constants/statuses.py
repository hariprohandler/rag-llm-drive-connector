"""Status enumeration constants."""
from enum import Enum


class ConnectorStatus(str, Enum):
    """Connector connection status."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"
    EXPIRED = "expired"


class SyncJobStatus(str, Enum):
    """Sync job status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    
    @classmethod
    def is_terminal(cls, status: str) -> bool:
        """Check if status is a terminal state."""
        terminal_statuses = {cls.COMPLETED, cls.FAILED, cls.CANCELLED}
        return status in [s.value for s in terminal_statuses]


class FineTuningStatus(str, Enum):
    """Fine-tuning job status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    PREPARING = "preparing"
    TRAINING = "training"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ShareType(str, Enum):
    """Document share type enumeration."""
    PUBLIC = "public"    # Share with all organization members
    MEMBER = "member"    # Share with specific member(s)
    GROUP = "group"      # Share with specific group(s)
    PRIVATE = "private"  # Only owner
