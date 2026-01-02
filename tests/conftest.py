"""Pytest configuration and fixtures."""
import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator
import models
from config import settings

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def test_database_url():
    """Create a test database URL."""
    # Use in-memory SQLite for testing, or separate test PostgreSQL database
    return os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")


@pytest.fixture(scope="function")
def db_session(test_database_url):
    """Create a test database session."""
    # For SQLite
    if test_database_url.startswith("sqlite"):
        engine = create_engine(test_database_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(test_database_url)
    
    models.Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        models.Base.metadata.drop_all(bind=engine)
        if test_database_url.startswith("sqlite") and os.path.exists("./test.db"):
            os.remove("./test.db")


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = models.User(
        id="test_google_12345",
        email="test@example.com",
        name="Test User",
        provider="google",
        provider_id="12345",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def temp_directory():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_text_file(temp_directory):
    """Create a sample text file for testing."""
    file_path = os.path.join(temp_directory, "test.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("This is a test document. It contains some information about testing.")
    return file_path


@pytest.fixture
def sample_pdf_file(temp_directory):
    """Create a sample PDF file for testing (mock)."""
    # In real tests, you'd create an actual PDF
    # For now, we'll return a path that may not exist
    file_path = os.path.join(temp_directory, "test.pdf")
    # Create a simple text file as PDF mock
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("PDF content mock")
    return file_path


@pytest.fixture
def mock_openai_api_key(monkeypatch):
    """Mock OpenAI API key for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")
    return "test-key-12345"


@pytest.fixture
def mock_jwt_secret(monkeypatch):
    """Mock JWT secret key for testing."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-only")
    return "test-jwt-secret-key-for-testing-only"

