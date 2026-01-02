"""Tests for RAG pipeline."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from rag import (
    get_user_collection_name,
    get_vectorstore,
    get_qa_chain,
    ask_question
)


def test_get_user_collection_name():
    """Test getting user collection name."""
    user_id = "google_12345"
    collection_name = get_user_collection_name(user_id)
    assert collection_name == "user_google_12345_documents"


def test_get_vectorstore(mock_openai_api_key, monkeypatch):
    """Test getting vectorstore."""
    with patch('rag.PGVector') as mock_pgvector:
        collection_name = "test_collection"
        vectorstore = get_vectorstore(collection_name)
        
        # Verify PGVector was called
        mock_pgvector.assert_called_once()


def test_get_qa_chain(mock_openai_api_key, monkeypatch):
    """Test getting QA chain."""
    with patch('rag.PGVector') as mock_pgvector, \
         patch('rag.ChatOpenAI') as mock_llm, \
         patch('rag.RetrievalQA') as mock_qa:
        
        collection_name = "test_collection"
        
        # Setup mocks
        mock_vectorstore = Mock()
        mock_vectorstore.as_retriever = Mock(return_value=Mock())
        mock_pgvector.return_value = mock_vectorstore
        
        qa_chain = get_qa_chain(collection_name)
        
        # Verify components were created
        mock_llm.assert_called_once()
        mock_qa.from_chain_type.assert_called_once()


@patch('rag.get_qa_chain')
def test_ask_question_success(mock_qa_chain, mock_openai_api_key):
    """Test asking a question successfully."""
    # Setup mock QA chain
    mock_qa = Mock()
    mock_result = {
        "result": "This is the answer",
        "source_documents": [
            Mock(page_content="Source 1 content", metadata={"file_name": "doc1.pdf"}),
            Mock(page_content="Source 2 content", metadata={"file_name": "doc2.pdf"})
        ]
    }
    mock_qa.return_value = mock_result
    mock_qa_chain.return_value = mock_qa
    
    query = "What is this about?"
    user_id = "test_user_123"
    
    result = ask_question(query, user_id)
    
    assert "answer" in result
    assert "sources" in result
    assert result["answer"] == "This is the answer"
    assert len(result["sources"]) == 2


@patch('rag.get_qa_chain')
def test_ask_question_no_sources(mock_qa_chain, mock_openai_api_key):
    """Test asking a question with no sources."""
    mock_qa = Mock()
    mock_result = {
        "result": "Answer without sources",
        "source_documents": []
    }
    mock_qa.return_value = mock_result
    mock_qa_chain.return_value = mock_qa
    
    query = "What is this?"
    user_id = "test_user_123"
    
    result = ask_question(query, user_id)
    
    assert result["answer"] == "Answer without sources"
    assert len(result["sources"]) == 0


@patch('rag.get_qa_chain')
def test_ask_question_error(mock_qa_chain, mock_openai_api_key):
    """Test asking a question when an error occurs."""
    # Setup mock to raise an error
    mock_qa_chain.side_effect = Exception("Database connection error")
    
    query = "What is this?"
    user_id = "test_user_123"
    
    with pytest.raises(Exception):
        ask_question(query, user_id)

