# Developer Standards and Best Practices

This document outlines coding standards, design patterns, and best practices for the RAG LLM Drive Connector project.

## Table of Contents

- [SOLID Principles](#solid-principles)
- [Design Patterns](#design-patterns)
- [Code Organization](#code-organization)
- [Naming Conventions](#naming-conventions)
- [Testing Standards](#testing-standards)
- [Documentation Requirements](#documentation-requirements)
- [Error Handling](#error-handling)
- [Security Best Practices](#security-best-practices)
- [Performance Considerations](#performance-considerations)

## SOLID Principles

### Single Responsibility Principle (SRP)

Each class/module should have **one reason to change**.

**✅ Good:**
```python
class UserService:
    """Handles user-related business logic only."""
    def create_user(self, user_data: dict) -> User:
        ...
    def update_user(self, user_id: str, user_data: dict) -> User:
        ...

class UserRepository:
    """Handles database operations for users only."""
    def save(self, user: User) -> User:
        ...
    def find_by_id(self, user_id: str) -> Optional[User]:
        ...
```

**❌ Bad:**
```python
class UserManager:
    """Does everything - violates SRP."""
    def create_user(self, ...):  # Business logic
        ...
    def save_to_db(self, ...):   # Data access
        ...
    def send_email(self, ...):   # Email sending
        ...
```

### Open/Closed Principle (OCP)

Open for extension, closed for modification.

**✅ Good:**
```python
# Base class
class VectorStore(ABC):
    @abstractmethod
    def store(self, document: Document) -> None:
        ...

class PgVectorStore(VectorStore):
    def store(self, document: Document) -> None:
        # Implementation for PostgreSQL
        ...

class PineconeVectorStore(VectorStore):
    def store(self, document: Document) -> None:
        # Implementation for Pinecone
        ...
```

**❌ Bad:**
```python
class VectorStore:
    def store(self, document: Document, backend: str):
        if backend == "postgres":
            # PostgreSQL logic
        elif backend == "pinecone":
            # Pinecone logic
        # Adding new backend requires modifying this class
```

### Liskov Substitution Principle (LSP)

Subtypes must be substitutable for their base types.

**✅ Good:**
```python
class Connector(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """Returns True if connection successful."""
        ...

class SlackConnector(Connector):
    def connect(self) -> bool:
        # Always returns bool, maintains contract
        return self._authenticate()
```

**❌ Bad:**
```python
class SlackConnector(Connector):
    def connect(self) -> Dict[str, Any]:  # Changed return type!
        return {"status": "connected"}  # Violates LSP
```

### Interface Segregation Principle (ISP)

Clients should not depend on interfaces they don't use.

**✅ Good:**
```python
class Readable(ABC):
    @abstractmethod
    def read(self) -> str:
        ...

class Writable(ABC):
    @abstractmethod
    def write(self, data: str) -> None:
        ...

class Document(Readable, Writable):
    def read(self) -> str: ...
    def write(self, data: str) -> None: ...
```

**❌ Bad:**
```python
class DocumentInterface(ABC):
    @abstractmethod
    def read(self) -> str: ...
    @abstractmethod
    def write(self, data: str) -> None: ...
    @abstractmethod
    def delete(self) -> None: ...
    @abstractmethod
    def encrypt(self) -> None: ...
    # Client that only reads is forced to implement all methods
```

### Dependency Inversion Principle (DIP)

Depend on abstractions, not concretions.

**✅ Good:**
```python
class IngestionService:
    def __init__(self, vector_store: VectorStore, text_splitter: TextSplitter):
        self._vector_store = vector_store  # Depends on abstraction
        self._text_splitter = text_splitter

# Usage
service = IngestionService(
    vector_store=PgVectorStore(...),
    text_splitter=RecursiveCharacterTextSplitter(...)
)
```

**❌ Bad:**
```python
class IngestionService:
    def __init__(self):
        self._vector_store = PgVectorStore(...)  # Depends on concretion
        # Hard to test or swap implementations
```

## Design Patterns

### Repository Pattern

Separate data access logic from business logic.

**Implementation:**
```python
# app/repositories/base.py
class BaseRepository(Generic[T]):
    def __init__(self, session: Session):
        self._session = session
    
    def find_by_id(self, id: str) -> Optional[T]:
        return self._session.query(self._model).filter_by(id=id).first()
    
    def save(self, entity: T) -> T:
        self._session.add(entity)
        self._session.commit()
        return entity

# app/repositories/user_repository.py
class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session):
        super().__init__(session)
        self._model = User
    
    def find_by_email(self, email: str) -> Optional[User]:
        return self._session.query(User).filter_by(email=email).first()
```

### Service Layer Pattern

Business logic in service classes, not in API routes or models.

**Implementation:**
```python
# app/services/user_service.py
class UserService:
    def __init__(self, user_repo: UserRepository, email_service: EmailService):
        self._user_repo = user_repo
        self._email_service = email_service
    
    def create_user(self, user_data: dict) -> User:
        # Business logic
        if self._user_repo.find_by_email(user_data["email"]):
            raise ValueError("Email already exists")
        
        user = User(**user_data)
        user = self._user_repo.save(user)
        
        # Side effects
        self._email_service.send_welcome_email(user.email)
        
        return user
```

### Factory Pattern

Create objects without specifying exact classes.

**Implementation:**
```python
# app/services/llm_factory.py
class LLMFactory:
    @staticmethod
    def create(provider: str, config: dict) -> BaseChatModel:
        if provider == "openai":
            return ChatOpenAI(**config)
        elif provider == "gemini":
            return ChatGoogleGenerativeAI(**config)
        elif provider == "anthropic":
            return ChatAnthropic(**config)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
```

### Strategy Pattern

Define family of algorithms and make them interchangeable.

**Implementation:**
```python
# app/services/ingestion/strategy.py
class IngestionStrategy(ABC):
    @abstractmethod
    def ingest(self, source: str, config: dict) -> List[Document]:
        ...

class SlackIngestionStrategy(IngestionStrategy):
    def ingest(self, source: str, config: dict) -> List[Document]:
        # Slack-specific ingestion
        ...

class TeamsIngestionStrategy(IngestionStrategy):
    def ingest(self, source: str, config: dict) -> List[Document]:
        # Teams-specific ingestion
        ...

class IngestionService:
    def __init__(self):
        self._strategies = {
            "slack": SlackIngestionStrategy(),
            "teams": TeamsIngestionStrategy(),
        }
    
    def ingest(self, source_type: str, source: str, config: dict):
        strategy = self._strategies.get(source_type)
        if not strategy:
            raise ValueError(f"Unknown source type: {source_type}")
        return strategy.ingest(source, config)
```

### Observer Pattern

Define one-to-many dependency between objects.

**Implementation:**
```python
# app/services/event_publisher.py
class EventPublisher:
    def __init__(self):
        self._subscribers = defaultdict(list)
    
    def subscribe(self, event_type: str, callback: Callable):
        self._subscribers[event_type].append(callback)
    
    def publish(self, event_type: str, data: dict):
        for callback in self._subscribers[event_type]:
            callback(data)

# Usage
publisher = EventPublisher()
publisher.subscribe("document.ingested", lambda data: logger.info(f"Document ingested: {data}"))
publisher.subscribe("document.ingested", lambda data: update_index(data))
```

## Code Organization

### Directory Structure

```
app/
├── models/              # Database models (data layer)
├── repositories/        # Data access layer (Repository pattern)
├── services/           # Business logic (Service layer)
│   ├── ingestion/     # Ingestion services (Strategy pattern)
│   ├── connectors/    # Connector services
│   └── rag/           # RAG services
├── api/                # API routes (presentation layer)
│   ├── v1/            # API versioning
│   └── middleware/    # Request/response middleware
├── core/               # Core configuration
└── helpers/           # Utility functions (not business logic)
```

### File Organization

**Service File Template:**
```python
"""Module docstring explaining purpose."""

from typing import Optional, List
from app.repositories.base import BaseRepository
from app.models import User


class UserService:
    """
    Service for user-related business logic.
    
    Responsibilities:
    - User creation and validation
    - User updates
    - User authentication
    """
    
    def __init__(self, user_repo: BaseRepository[User]):
        """
        Initialize UserService.
        
        Args:
            user_repo: Repository for user data access
        """
        self._user_repo = user_repo
    
    def create_user(self, user_data: dict) -> User:
        """
        Create a new user.
        
        Args:
            user_data: User data dictionary
            
        Returns:
            Created User instance
            
        Raises:
            ValueError: If email already exists
        """
        # Implementation
        ...
```

## Naming Conventions

### Classes and Modules

- **Classes**: PascalCase (`UserService`, `VectorStore`)
- **Modules**: snake_case (`user_service.py`, `vector_store.py`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_RETRIES`, `DEFAULT_CHUNK_SIZE`)

### Functions and Variables

- **Functions/Methods**: snake_case (`create_user`, `get_vector_store`)
- **Private methods**: Leading underscore (`_validate_user`, `_calculate_score`)
- **Variables**: snake_case (`user_id`, `collection_name`)

### Files and Directories

- **Python files**: snake_case (`user_service.py`)
- **Directories**: snake_case (`user_services/`)
- **Test files**: `test_*.py` or `*_test.py`

## Testing Standards

### Test Structure

```python
"""Tests for UserService."""
import pytest
from unittest.mock import Mock, patch
from app.services.user_service import UserService
from app.models import User


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
        user_data = {"email": "test@example.com", "name": "Test User"}
        mock_user_repo.find_by_email.return_value = None
        mock_user_repo.save.return_value = User(**user_data)
        
        # Act
        result = user_service.create_user(user_data)
        
        # Assert
        assert result.email == user_data["email"]
        mock_user_repo.save.assert_called_once()
    
    def test_create_user_duplicate_email(self, user_service, mock_user_repo):
        """Test user creation with duplicate email."""
        # Arrange
        user_data = {"email": "existing@example.com"}
        mock_user_repo.find_by_email.return_value = User(email=user_data["email"])
        
        # Act & Assert
        with pytest.raises(ValueError, match="already exists"):
            user_service.create_user(user_data)
```

### Test Coverage Requirements

- **Unit Tests**: All services, repositories, helpers
- **Integration Tests**: API endpoints, database operations
- **Target Coverage**: 80%+ code coverage

### Test Organization

```
tests/
├── unit/               # Unit tests
│   ├── services/      # Service tests
│   ├── repositories/  # Repository tests
│   └── helpers/       # Helper tests
├── integration/        # Integration tests
│   ├── api/           # API endpoint tests
│   └── database/      # Database tests
└── conftest.py        # Pytest fixtures
```

## Documentation Requirements

### Code Documentation

**All public classes and functions must have docstrings:**

```python
def process_documents(
    documents: List[Document],
    chunk_size: int = 1000,
    overlap: int = 200
) -> List[Document]:
    """
    Process documents by chunking text.
    
    Args:
        documents: List of Document objects to process
        chunk_size: Size of each chunk in characters
        overlap: Overlap between chunks in characters
        
    Returns:
        List of chunked Document objects
        
    Raises:
        ValueError: If chunk_size <= 0 or overlap < 0
        
    Example:
        >>> docs = [Document(page_content="Long text...")]
        >>> chunks = process_documents(docs, chunk_size=500)
        >>> len(chunks) > 1
        True
    """
    ...
```

### API Documentation

- OpenAPI/Swagger specs for all endpoints
- Request/response examples
- Error response documentation

## Error Handling

### Exception Hierarchy

```python
# app/core/exceptions.py
class ApplicationError(Exception):
    """Base application error."""
    pass

class ValidationError(ApplicationError):
    """Data validation error."""
    pass

class NotFoundError(ApplicationError):
    """Resource not found error."""
    pass

class AuthenticationError(ApplicationError):
    """Authentication error."""
    pass
```

### Error Handling Pattern

```python
try:
    result = service.process_data(data)
except ValidationError as e:
    logger.warning(f"Validation failed: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except NotFoundError as e:
    logger.info(f"Resource not found: {e}")
    raise HTTPException(status_code=404, detail=str(e))
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

## Security Best Practices

1. **Never log sensitive data** (passwords, tokens, PII)
2. **Validate all inputs** (use Pydantic models)
3. **Use parameterized queries** (prevent SQL injection)
4. **Encrypt sensitive data** (API keys, credentials)
5. **Implement rate limiting** (prevent abuse)
6. **Use HTTPS** (encrypt in transit)
7. **Regular dependency updates** (security patches)

## Performance Considerations

1. **Database indexing**: Index frequently queried columns
2. **Query optimization**: Use `select_related()` / `joinedload()` to avoid N+1 queries
3. **Caching**: Cache expensive operations (Redis, in-memory)
4. **Batch processing**: Process items in batches
5. **Async operations**: Use async/await for I/O-bound operations
6. **Connection pooling**: Reuse database connections

## Git Workflow

### Branch Naming

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `refactor/description` - Code refactoring
- `docs/description` - Documentation updates
- `test/description` - Test additions/updates

### Commit Messages

Format: `type(scope): description`

```
feat(connectors): add Slack connector support
fix(ingest): handle empty document lists
refactor(services): apply Repository pattern to UserService
docs(api): update authentication endpoints
test(services): add tests for IngestionService
```

### Code Review Checklist

- [ ] Follows SOLID principles
- [ ] Has tests (unit + integration)
- [ ] Documentation updated
- [ ] No hardcoded values
- [ ] Error handling implemented
- [ ] Security considerations addressed
- [ ] Performance optimized
- [ ] Code follows style guide (black, isort, flake8)

## Additional Resources

- [Python Style Guide (PEP 8)](https://pep8.org/)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [SOLID Principles Explained](https://en.wikipedia.org/wiki/SOLID)
- [Design Patterns in Python](https://refactoring.guru/design-patterns/python)
