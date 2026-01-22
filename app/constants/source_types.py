"""Source type constants."""
from enum import Enum


class SourceType(str, Enum):
    """Source type enumeration for document ingestion."""
    
    # File storage sources
    LOCAL_FILE = "local_file"
    GOOGLE_DRIVE = "google_drive"
    ONEDRIVE = "onedrive"
    
    # Collaboration platforms
    SLACK = "slack"
    TEAMS = "teams"
    
    # Email platforms
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    
    # Support platforms
    ZENDESK = "zendesk"
    
    # External search
    WEB_SCRAPE = "web_scrape"
    
    # Fine-tuning data sources
    KNOWLEDGE_BASE = "knowledge_base"
    UPLOADED = "uploaded"
    CUSTOM = "custom"
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if value is a valid source type."""
        try:
            cls(value)
            return True
        except ValueError:
            return False
    
    @classmethod
    def get_all(cls) -> list:
        """Get all source type values."""
        return [item.value for item in cls]


# Source type metadata
SOURCE_TYPE_CONFIG = {
    SourceType.LOCAL_FILE: {
        "display_name": "Local Files",
        "supports_sync": False,
        "requires_oauth": False,
    },
    SourceType.GOOGLE_DRIVE: {
        "display_name": "Google Drive",
        "supports_sync": True,
        "requires_oauth": True,
        "provider": "google",
    },
    SourceType.ONEDRIVE: {
        "display_name": "OneDrive",
        "supports_sync": True,
        "requires_oauth": True,
        "provider": "microsoft",
    },
    SourceType.SLACK: {
        "display_name": "Slack",
        "supports_sync": True,
        "requires_oauth": True,
        "provider": "slack",
    },
    SourceType.TEAMS: {
        "display_name": "Microsoft Teams",
        "supports_sync": True,
        "requires_oauth": True,
        "provider": "microsoft",
    },
    SourceType.GMAIL: {
        "display_name": "Gmail",
        "supports_sync": True,
        "requires_oauth": True,
        "provider": "google",
    },
    SourceType.OUTLOOK: {
        "display_name": "Outlook",
        "supports_sync": True,
        "requires_oauth": True,
        "provider": "microsoft",
    },
    SourceType.ZENDESK: {
        "display_name": "Zendesk",
        "supports_sync": True,
        "requires_oauth": False,  # Uses API key
    },
    SourceType.WEB_SCRAPE: {
        "display_name": "Web Search",
        "supports_sync": False,
        "requires_oauth": False,
    },
}
