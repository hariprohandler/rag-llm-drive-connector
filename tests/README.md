# Test Suite

This directory contains unit and integration tests for the RAG LLM Drive Connector application.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=. --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_models.py
```

### Run specific test
```bash
pytest tests/test_models.py::test_user_creation
```

### Run by marker
```bash
pytest -m unit          # Run only unit tests
pytest -m integration   # Run only integration tests
pytest -m "not slow"    # Skip slow tests
```

### Run with verbose output
```bash
pytest -v
```

## Test Structure

- `conftest.py` - Pytest fixtures and configuration
- `test_models.py` - Database model tests
- `test_auth_service.py` - Authentication service tests
- `test_ingest.py` - Document ingestion tests (including local files)
- `test_rag.py` - RAG pipeline tests
- `test_api.py` - API endpoint tests
- `test_integration.py` - Integration tests

## Test Database

Tests use SQLite by default for faster execution. Set `TEST_DATABASE_URL` environment variable to use a different database:

```bash
export TEST_DATABASE_URL="postgresql://user:pass@localhost/testdb"
pytest
```

## Fixtures

Common fixtures available in `conftest.py`:

- `db_session` - Database session (created per test)
- `test_user` - Sample test user
- `temp_directory` - Temporary directory for test files
- `sample_text_file` - Sample text file
- `mock_openai_api_key` - Mocked OpenAI API key
- `mock_jwt_secret` - Mocked JWT secret

## Writing New Tests

1. Create a new file `test_<module>.py`
2. Import necessary fixtures from `conftest`
3. Use pytest markers to categorize tests:
   ```python
   @pytest.mark.unit
   def test_something():
       pass
   
   @pytest.mark.integration
   @pytest.mark.slow
   def test_something_else():
       pass
   ```

## Mocking

For tests that require external services (OpenAI, databases, etc.), use mocks:

```python
from unittest.mock import patch, Mock

@patch('module.external_service')
def test_with_mock(mock_service):
    mock_service.return_value = Mock()
    # Test code here
```

## Coverage

View coverage report:
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

Target: >80% coverage for production code.

