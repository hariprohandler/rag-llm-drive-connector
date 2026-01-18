# Testing Guide

This document outlines the testing standards, structure, and best practices for the RAG LLM Drive Connector project.

## Test Structure

```
tests/
├── unit/              # Unit tests (isolated, fast)
│   ├── models/       # Model tests
│   ├── services/     # Service tests
│   ├── helpers/      # Helper function tests
│   └── repositories/ # Repository tests
├── integration/       # Integration tests (with dependencies)
│   ├── api/          # API endpoint tests
│   ├── database/     # Database operation tests
│   └── connectors/   # Connector integration tests
└── conftest.py       # Shared fixtures
```

## Running Tests

### Run All Tests

```bash
# Using pytest
pytest

# With coverage
pytest --cov=. --cov-report=html

# Verbose output
pytest -v
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_connector_models.py

# Specific test class
pytest tests/unit/test_connector_models.py::TestConnector

# Specific test method
pytest tests/unit/test_connector_models.py::TestConnector::test_connector_creation
```

### Run Tests with Markers

```bash
# Run only fast tests
pytest -m "not slow"

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

## Test Coverage Requirements

- **Target Coverage**: 80%+ for all modules
- **Critical Paths**: 90%+ coverage required
- **New Features**: Must include tests with PR

### Generate Coverage Report

```bash
# HTML report
pytest --cov=. --cov-report=html

# Console report
pytest --cov=. --cov-report=term-missing

# XML report (for CI/CD)
pytest --cov=. --cov-report=xml
```

## Writing Tests

### Test File Naming

- Unit tests: `test_*.py` (e.g., `test_connector_models.py`)
- Test files should mirror source structure

### Test Organization

**✅ Good Test Structure:**
```python
"""Tests for UserService."""
import pytest
from unittest.mock import Mock, patch
from app.services.user_service import UserService


class TestUserService:
    """Test suite for UserService."""
    
    @pytest.fixture
    def mock_user_repo(self):
        """Mock user repository."""
        return Mock()
    
    @pytest.fixture
    def user_service(self, mock_user_repo):
        """Create UserService instance."""
        return UserService(user_repo=mock_user_repo)
    
    def test_create_user_success(self, user_service, mock_user_repo):
        """Test successful user creation."""
        # Arrange
        user_data = {"email": "test@example.com"}
        mock_user_repo.find_by_email.return_value = None
        
        # Act
        result = user_service.create_user(user_data)
        
        # Assert
        assert result is not None
        mock_user_repo.save.assert_called_once()
```

### Test Principles (AAA Pattern)

1. **Arrange**: Set up test data and mocks
2. **Act**: Execute the code under test
3. **Assert**: Verify the results

### Fixtures

Use pytest fixtures for common setup:

```python
# conftest.py
@pytest.fixture
def db_session():
    """Database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def sample_user(db_session):
    """Sample user for testing."""
    user = User(id="test123", email="test@example.com")
    db_session.add(user)
    db_session.commit()
    return user
```

## Unit Tests

### What to Test

- ✅ Business logic
- ✅ Data transformations
- ✅ Validation logic
- ✅ Error handling
- ❌ Not: External dependencies (use mocks)

### Example

```python
class TestVectorDbHelper:
    """Test vector database helper functions."""
    
    def test_get_vector_table_name(self):
        """Test table name mapping."""
        assert get_vector_table_name("slack") == "vectors_slack"
        assert get_vector_table_name("teams") == "vectors_teams"
```

## Integration Tests

### What to Test

- ✅ API endpoints (end-to-end)
- ✅ Database operations
- ✅ External service integration (with test doubles)
- ✅ Complex workflows

### Example

```python
class TestApiEndpoints:
    """Test API endpoints."""
    
    def test_create_user_endpoint(self, client):
        """Test user creation via API."""
        response = client.post("/api/users", json={
            "email": "test@example.com",
            "name": "Test User"
        })
        assert response.status_code == 201
        assert response.json()["email"] == "test@example.com"
```

## Mocking Best Practices

### When to Mock

- ✅ External APIs (OpenAI, Google Drive, etc.)
- ✅ Database (for unit tests)
- ✅ File system operations
- ✅ Time-dependent operations

### Example

```python
@patch('app.services.ingest.OpenAIEmbeddings')
def test_ingest_documents(mock_embeddings):
    """Test document ingestion with mocked embeddings."""
    mock_embeddings.return_value.embed_documents.return_value = [[0.1] * 1536]
    
    # Test ingestion
    result = ingest_documents([Document(...)], "collection")
    
    assert result is True
```

## Test Data Management

### Use Fixtures for Test Data

```python
@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        Document(page_content="Test document 1", metadata={"source": "slack"}),
        Document(page_content="Test document 2", metadata={"source": "teams"}),
    ]
```

### Use Factories for Complex Data

```python
# tests/factories/user_factory.py
class UserFactory:
    @staticmethod
    def create(**kwargs) -> User:
        defaults = {
            "id": "test_user_123",
            "email": "test@example.com",
            "name": "Test User"
        }
        defaults.update(kwargs)
        return User(**defaults)
```

## Continuous Integration

Tests run automatically on:
- Pull requests
- Commits to main branch
- Manual trigger

### CI Test Commands

```yaml
# .github/workflows/tests.yml
- name: Run tests
  run: |
    pytest --cov=. --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Best Practices

1. **Test Independence**: Each test should be independent
2. **Test Naming**: Use descriptive names (`test_create_user_with_duplicate_email`)
3. **One Assert Per Test**: Focus each test on one behavior
4. **Fast Tests**: Unit tests should be fast (< 100ms)
5. **Clear Assertions**: Use descriptive assertion messages
6. **Test Edge Cases**: Include boundary conditions and error cases
7. **Avoid Test Interdependence**: Tests should not depend on execution order

## Common Patterns

### Testing Exceptions

```python
def test_create_user_duplicate_email(self, user_service):
    """Test user creation with duplicate email raises error."""
    with pytest.raises(ValueError, match="already exists"):
        user_service.create_user({"email": "existing@example.com"})
```

### Testing Async Code

```python
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operation."""
    result = await async_function()
    assert result is not None
```

### Parametrized Tests

```python
@pytest.mark.parametrize("source_type,expected_table", [
    ("slack", "vectors_slack"),
    ("teams", "vectors_teams"),
    ("onedrive", "vectors_onedrive"),
])
def test_table_name_mapping(source_type, expected_table):
    """Test table name mapping for different sources."""
    assert get_vector_table_name(source_type) == expected_table
```

## Troubleshooting

### Tests Failing Locally but Passing in CI

- Check environment variables
- Verify database state
- Check for missing dependencies

### Slow Tests

- Use mocks instead of real services
- Use in-memory database (SQLite) for tests
- Run tests in parallel: `pytest -n auto`
