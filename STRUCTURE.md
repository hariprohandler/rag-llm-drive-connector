# Project Structure

This document describes the industry-standard folder structure for the RAG LLM Drive Connector project.

## Directory Structure

```
rag-llm-drive-connector/
├── app/                          # Main application package
│   ├── __init__.py
│   ├── models/                   # Database models
│   │   ├── __init__.py
│   │   ├── base.py              # Base model and DB configuration (master-slave support)
│   │   ├── user.py              # User model
│   │   ├── llm_config.py        # LLM configuration model
│   │   ├── knowledge_base.py    # Knowledge base model
│   │   └── chat.py              # Chat models (Conversation, Message)
│   ├── services/                 # Business logic services
│   │   ├── __init__.py
│   │   ├── rag.py               # RAG pipeline with multi-LLM support
│   │   ├── ingest.py            # Document ingestion
│   │   ├── llm_service.py       # LLM configuration management
│   │   └── chat_service.py     # Chat conversation management
│   ├── core/                     # Core application components
│   │   ├── __init__.py
│   │   └── config.py            # Configuration settings (supports master-slave DB)
│   └── api/                      # API routes (future expansion)
│       └── __init__.py
├── migrations/                   # Alembic database migrations
│   ├── env.py                   # Migration environment (uses .env)
│   ├── versions/                # Migration versions
│   └── README.md
├── tests/                        # Test suite
├── app.py                        # FastAPI application entry point
├── config.py                     # Legacy config (deprecated, use app/core/config.py)
├── models.py                     # Legacy models (deprecated, use app/models/)
├── requirements.txt              # Python dependencies
├── alembic.ini                   # Alembic configuration
└── .env                          # Environment variables
```

## Key Features

### 1. Master-Slave Database Support

The application supports master-slave database configuration for read/write separation:

- **Master Database**: Used for all write operations
- **Slave Database**: Used for read operations (optional, falls back to master if not configured)

Configuration in `.env`:
```env
DATABASE_URL=postgresql+psycopg2://user:pass@master-db:5432/dbname
DATABASE_READ_URL=postgresql+psycopg2://user:pass@slave-db:5432/dbname  # Optional
```

Usage in code:
```python
from app.models.base import get_db

# Write operation (uses master)
db = next(get_db(read_only=False))

# Read operation (uses slave if configured)
db = next(get_db(read_only=True))
```

### 2. Default LLM Configuration Fallback

Users can use the system's default LLM configuration if they haven't configured their own API keys:

- If user has no LLM config → uses system default (from `OPENAI_API_KEY` in `.env`)
- If system has no API key → returns helpful error message
- Users can still add their own LLM configurations for personal use

### 3. Alembic Uses .env File

Alembic migrations automatically load configuration from `.env` file:

- No need to hardcode database URLs in `alembic.ini`
- Uses `python-dotenv` to load environment variables
- Reads from `app/core/config.py` which uses pydantic-settings

### 4. Industry-Standard Structure

- **Models**: Separated into individual files in `app/models/`
- **Services**: Business logic in `app/services/`
- **Core**: Configuration and base components in `app/core/`
- **API**: Routes can be organized in `app/api/` (future)

## Migration Guide

### Updating Imports

Old imports:
```python
import models
import config
from rag import ask_question
from llm_service import create_llm_config
```

New imports:
```python
from app.models import User, LLMConfig
from app.core.config import settings
from app.services.rag import ask_question
from app.services.llm_service import create_llm_config
from app.models.base import get_db
```

### Database Sessions

Old:
```python
from models import get_db
db: Session = Depends(get_db)
```

New:
```python
from app.models.base import get_db
db: Session = Depends(get_db)  # Uses master by default
db: Session = Depends(lambda: get_db(read_only=True))  # Uses slave
```

## Environment Variables

Required in `.env`:
```env
# Database (Master)
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname

# Database (Slave - Optional)
DATABASE_READ_URL=postgresql+psycopg2://user:pass@slave-host:5432/dbname

# Default LLM (for users without config)
OPENAI_API_KEY=your-key-here

# Encryption (for API key storage)
ENCRYPTION_KEY=your-encryption-key

# Other settings...
```

## Running Migrations

```bash
# Alembic automatically uses .env file
alembic upgrade head
alembic revision --autogenerate -m "description"
```

