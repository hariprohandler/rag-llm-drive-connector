"""Unit tests for vector database helper functions."""
import pytest
from app.helpers.vector_db_helper import (
    get_vector_table_name,
    get_source_type_from_table,
    get_collection_name,
    build_tag_filter,
    build_metadata_with_tags
)


class TestGetVectorTableName:
    """Test suite for get_vector_table_name function."""
    
    def test_slack_source(self):
        """Test Slack source type mapping."""
        result = get_vector_table_name("slack")
        assert result == "vectors_slack"
    
    def test_teams_source(self):
        """Test Teams source type mapping."""
        result = get_vector_table_name("teams")
        assert result == "vectors_teams"
    
    def test_onedrive_source(self):
        """Test OneDrive source type mapping."""
        result = get_vector_table_name("onedrive")
        assert result == "vectors_onedrive"
    
    def test_google_drive_source(self):
        """Test Google Drive source type mapping."""
        result = get_vector_table_name("google_drive")
        assert result == "vectors_google_drive"
    
    def test_local_file_source(self):
        """Test local file source type mapping."""
        result = get_vector_table_name("local_file")
        assert result == "vectors_local_file"
    
    def test_unknown_source(self):
        """Test unknown source type returns None."""
        result = get_vector_table_name("unknown_source")
        assert result is None
    
    def test_source_with_hyphens(self):
        """Test source type normalization (hyphens to underscores)."""
        result = get_vector_table_name("google-drive")
        assert result == "vectors_google_drive"
    
    def test_source_with_spaces(self):
        """Test source type normalization (spaces to underscores)."""
        result = get_vector_table_name("local file")
        assert result == "vectors_local_file"
    
    def test_disable_source_tables(self):
        """Test disabling source tables returns None."""
        result = get_vector_table_name("slack", use_source_tables=False)
        assert result is None


class TestGetSourceTypeFromTable:
    """Test suite for get_source_type_from_table function."""
    
    def test_reverse_mapping(self):
        """Test reverse mapping from table name to source type."""
        assert get_source_type_from_table("vectors_slack") == "slack"
        assert get_source_type_from_table("vectors_teams") == "teams"
        assert get_source_type_from_table("vectors_onedrive") == "onedrive"
        assert get_source_type_from_table("vectors_google_drive") == "google_drive"
        assert get_source_type_from_table("vectors_local_file") == "local_file"
    
    def test_unknown_table(self):
        """Test unknown table name returns None."""
        assert get_source_type_from_table("unknown_table") is None


class TestGetCollectionName:
    """Test suite for get_collection_name function."""
    
    def test_basic_user_collection(self):
        """Test basic user collection name."""
        result = get_collection_name("user123")
        assert result == "user_user123_documents"
    
    def test_collection_with_knowledge_base(self):
        """Test collection name with knowledge base ID."""
        result = get_collection_name("user123", knowledge_base_id=456)
        assert result == "user_user123_kb_456"
    
    def test_collection_with_source_type(self):
        """Test collection name with source type."""
        result = get_collection_name("user123", source_type="slack")
        assert result == "user_user123_source_slack"
    
    def test_collection_with_all_parameters(self):
        """Test collection name with all parameters."""
        result = get_collection_name("user123", knowledge_base_id=456, source_type="slack")
        assert result == "user_user123_source_slack_kb_456"
    
    def test_organization_collection(self):
        """Test organization collection name."""
        result = get_collection_name("user123", organization_id=789)
        assert result == "org_789_documents"
    
    def test_organization_with_source(self):
        """Test organization collection with source type."""
        result = get_collection_name("user123", organization_id=789, source_type="teams")
        assert result == "org_789_source_teams"
    
    def test_source_type_normalization(self):
        """Test source type normalization in collection names."""
        result = get_collection_name("user123", source_type="google-drive")
        assert result == "user_user123_source_google_drive"
        
        result = get_collection_name("user123", source_type="local file")
        assert result == "user_user123_source_local_file"


class TestBuildTagFilter:
    """Test suite for build_tag_filter function."""
    
    def test_tag_ids_filter(self):
        """Test filter with tag IDs."""
        result = build_tag_filter(tag_ids=[1, 2, 3])
        assert result is not None
        assert "tag_ids" in result
        assert result["tag_ids"] == {"$contains": [1, 2, 3]}
    
    def test_tag_slugs_filter(self):
        """Test filter with tag slugs."""
        result = build_tag_filter(tag_slugs=["important", "archived"])
        assert result is not None
        assert "tag_slugs" in result
        assert result["tag_slugs"] == {"$contains": ["important", "archived"]}
    
    def test_both_tag_filters(self):
        """Test filter with both tag IDs and slugs."""
        result = build_tag_filter(tag_ids=[1, 2], tag_slugs=["important"])
        assert result is not None
        assert "tag_ids" in result
        assert "tag_slugs" in result
    
    def test_no_filters(self):
        """Test filter with no tags returns None."""
        result = build_tag_filter()
        assert result is None


class TestBuildMetadataWithTags:
    """Test suite for build_metadata_with_tags function."""
    
    def test_add_tag_ids(self):
        """Test adding tag IDs to metadata."""
        base_metadata = {"source": "slack", "user_id": "123"}
        result = build_metadata_with_tags(base_metadata, tag_ids=[1, 2])
        
        assert "tag_ids" in result
        assert result["tag_ids"] == ["1", "2"]
        assert result["source"] == "slack"
    
    def test_add_tag_slugs(self):
        """Test adding tag slugs to metadata."""
        base_metadata = {"source": "teams"}
        result = build_metadata_with_tags(base_metadata, tag_slugs=["important", "qa"])
        
        assert "tag_slugs" in result
        assert result["tag_slugs"] == ["important", "qa"]
    
    def test_deduplicate_tags(self):
        """Test tag deduplication."""
        base_metadata = {"tag_ids": ["1", "2"]}
        result = build_metadata_with_tags(base_metadata, tag_ids=[2, 3, 3])
        
        assert set(result["tag_ids"]) == {"1", "2", "3"}
    
    def test_preserve_existing_metadata(self):
        """Test that existing metadata is preserved."""
        base_metadata = {
            "source": "slack",
            "channel": "general",
            "user_id": "123"
        }
        result = build_metadata_with_tags(base_metadata, tag_ids=[1])
        
        assert result["source"] == "slack"
        assert result["channel"] == "general"
        assert result["user_id"] == "123"
        assert "tag_ids" in result
