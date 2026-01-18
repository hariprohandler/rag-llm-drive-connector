"""Table name constants for vector storage."""
from typing import Dict, Optional


class TableNames:
    """Table name constants for source-specific vector tables."""
    
    # Vector storage tables by source type
    SLACK = "vectors_slack"
    TEAMS = "vectors_teams"
    ONEDRIVE = "vectors_onedrive"
    GOOGLE_DRIVE = "vectors_google_drive"
    LOCAL_FILE = "vectors_local_file"
    ZENDESK = "vectors_zendesk"
    
    # Default/Legacy table
    DEFAULT = "langchain_pg_embedding"  # Default collection table
    
    # Mapping from source type to table name
    SOURCE_TO_TABLE: Dict[str, str] = {
        "slack": SLACK,
        "teams": TEAMS,
        "onedrive": ONEDRIVE,
        "google_drive": GOOGLE_DRIVE,
        "local_file": LOCAL_FILE,
        "zendesk": ZENDESK,
    }
    
    @classmethod
    def get_table_name(cls, source_type: str) -> Optional[str]:
        """
        Get table name for a source type.
        
        Args:
            source_type: Source type string
            
        Returns:
            Table name string or None if not mapped
        """
        # Normalize source type
        normalized = source_type.replace('-', '_').replace(' ', '_').lower()
        return cls.SOURCE_TO_TABLE.get(normalized)
    
    @classmethod
    def get_source_type(cls, table_name: str) -> Optional[str]:
        """
        Get source type from table name (reverse mapping).
        
        Args:
            table_name: Table name string
            
        Returns:
            Source type string or None if not mapped
        """
        table_to_source = {v: k for k, v in cls.SOURCE_TO_TABLE.items()}
        return table_to_source.get(table_name)
    
    @classmethod
    def get_all_tables(cls) -> list:
        """Get all table names."""
        return list(cls.SOURCE_TO_TABLE.values()) + [cls.DEFAULT]
