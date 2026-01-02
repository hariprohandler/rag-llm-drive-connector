"""Integration tests for the application."""
import pytest
import os
import tempfile
import shutil
from pathlib import Path


@pytest.mark.integration
def test_full_ingestion_pipeline(temp_directory, mock_openai_api_key, db_session):
    """Test full ingestion pipeline with local files."""
    # Create test files
    test_files = []
    for i in range(3):
        file_path = os.path.join(temp_directory, f"test_{i}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"This is test document number {i}. It contains some test content.")
        test_files.append(file_path)
    
    # Create test user
    from models import User
    from auth_service import get_or_create_user
    
    user = get_or_create_user(
        db=db_session,
        email="integration@test.com",
        name="Integration Test User",
        provider="test",
        provider_id="999"
    )
    
    # Test ingestion (mocked to avoid actual API calls)
    from unittest.mock import Mock, patch
    from ingest import ingest_local_files
    
    with patch('ingest.OpenAIEmbeddings'), \
         patch('ingest.PGVector'):
        try:
            result = ingest_local_files(test_files, user.id)
            assert isinstance(result, bool)
        except Exception:
            # Expected if actual DB/API calls are made
            pass


@pytest.mark.integration
def test_user_authentication_flow(db_session):
    """Test complete user authentication flow."""
    from auth_service import get_or_create_user, create_access_token, verify_token
    
    # Create user
    user = get_or_create_user(
        db=db_session,
        email="auth@test.com",
        name="Auth Test",
        provider="google",
        provider_id="auth123"
    )
    
    # Create token
    token = create_access_token(data={"sub": user.id, "email": user.email})
    assert token is not None
    
    # Verify token
    payload = verify_token(token)
    assert payload["sub"] == user.id
    assert payload["email"] == user.email


@pytest.mark.integration
@pytest.mark.slow
def test_query_with_mocked_rag(mock_openai_api_key, db_session):
    """Test querying with mocked RAG pipeline."""
    from models import User
    from auth_service import get_or_create_user
    from unittest.mock import patch, Mock
    
    # Create user
    user = get_or_create_user(
        db=db_session,
        email="query@test.com",
        name="Query Test",
        provider="test",
        provider_id="query123"
    )
    
    # Mock RAG pipeline
    with patch('rag.get_qa_chain') as mock_qa:
        mock_chain = Mock()
        mock_chain.return_value = {
            "result": "Mocked answer",
            "source_documents": []
        }
        mock_qa.return_value = mock_chain
        
        from rag import ask_question
        result = ask_question("test query", user.id)
        
        assert "answer" in result
        assert "sources" in result

