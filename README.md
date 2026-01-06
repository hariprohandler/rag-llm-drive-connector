# Project Overview and Structure

Complete overview of the RAG LLM Drive Connector project, including architecture, structure, API documentation, and project information.

## Table of Contents

- [Project Description](#project-description)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Key Features](#key-features)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Security](#security)
- [Monitoring](#monitoring)
- [CI/CD Pipeline](#cicd-pipeline)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Support](#support)
- [Roadmap](#roadmap)

## Project Description

A production-ready RAG (Retrieval-Augmented Generation) application that connects to Google Drive and OneDrive, allowing users to query their documents using LLMs. Built with FastAPI, LangChain, PgVector, and Kubernetes.

## Features

- 🔐 **OAuth Authentication** - Secure user authentication for Google Drive and OneDrive
- 📄 **Multi-Source Ingestion** - Support for Google Drive, OneDrive, and local files
- 🔍 **Semantic Search** - Vector-based semantic search using PgVector
- 💬 **Natural Language Querying** - Query documents using LLMs (OpenAI)
- 🎨 **Web UI** - Gradio-based user interface
- 🔌 **RESTful API** - Complete FastAPI backend
- ☸️ **Kubernetes Ready** - Full Kubernetes deployment manifests
- 🔄 **ArgoCD Integration** - GitOps deployment with ArgoCD
- 🐳 **Docker Support** - Containerized application
- 🔒 **Production Ready** - Health checks, monitoring, and security best practices

## Architecture

```
┌─────────────────┐
│   User/Browser  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Ingress (Nginx)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌─────────────────┐
│  FastAPI App    │──────│  PostgreSQL     │
│  (Kubernetes)   │      │  (PgVector)     │
└────────┬────────┘      └─────────────────┘
         │
         ▼
┌─────────────────┐
│  LangChain RAG  │
│  + OpenAI       │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Google Drive   │
│  / OneDrive     │
└─────────────────┘
```

## Tech Stack

- **Backend**: FastAPI, Python 3.11
- **RAG Framework**: LangChain
- **Vector Database**: PgVector (PostgreSQL extension)
- **LLM**: OpenAI GPT-4o-mini
- **UI**: Gradio
- **Container**: Docker
- **Orchestration**: Kubernetes
- **GitOps**: ArgoCD
- **CI/CD**: GitHub Actions

## Project Structure

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
│   └── script.py.mako
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── test_models.py           # Model tests
│   ├── test_auth_service.py      # Auth service tests
│   ├── test_ingest.py           # Ingestion tests
│   ├── test_rag.py              # RAG tests
│   ├── test_api.py              # API tests
│   └── test_integration.py      # Integration tests
├── k8s/                          # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml.example
│   ├── postgres-deployment.yaml
│   ├── app-deployment.yaml
│   ├── ingress.yaml
│   └── kustomization.yaml
├── argocd/                       # ArgoCD manifests
│   ├── application.yaml
│   └── app-of-apps.yaml
├── app.py                        # FastAPI application entry point
├── config.py                     # Legacy config (deprecated, use app/core/config.py)
├── models.py                     # Legacy models (deprecated, use app/models/)
├── requirements.txt              # Python dependencies
├── environment.yml               # Conda environment file
├── alembic.ini                   # Alembic configuration
├── Dockerfile                    # Docker image definition
├── docker-compose.yml            # Docker Compose configuration
├── setup_db.py                   # Database setup script
└── .env.example                  # Environment variables template
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

### 3. Environment-Specific Configuration

The application supports environment-specific `.env` files:

- `.env` - Base configuration
- `.env.development` - Development settings
- `.env.production` - Production settings
- `.env.staging` - Staging settings (optional)

Set the `ENVIRONMENT` variable to load the appropriate configuration file.

### 4. Industry-Standard Structure

- **Models**: Separated into individual files in `app/models/`
- **Services**: Business logic in `app/services/`
- **Core**: Configuration and base components in `app/core/`
- **API**: Routes can be organized in `app/api/` (future)

### Migration Guide

#### Updating Imports

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

#### Database Sessions

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

## API Documentation

### Interactive API Docs

Once the application is running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Main Endpoints

#### Query Documents

```http
POST /api/query
Content-Type: application/json

{
  "query": "What is the main topic?",
  "collection_name": "documents",
  "user_id": "user123"
}
```

#### Connect Google Drive

```http
GET /auth/google?user_id=user123
```

#### Connect OneDrive

```http
GET /auth/onedrive?user_id=user123
```

#### Ingest from Google Drive

```http
POST /api/ingest/google-drive
Content-Type: application/json

{
  "folder_id": "folder_id_here",
  "user_id": "user123"
}
```

#### Ingest from OneDrive

```http
POST /api/ingest/onedrive
Content-Type: application/json

{
  "folder_path": "/Documents/MyFolder",
  "user_id": "user123"
}
```

#### Health Checks

- `/health` - Liveness probe (checks database connectivity)
- `/ready` - Readiness probe (checks if service is ready)

## Configuration

### Environment Variables

See `SETUP_AND_RUNNING.md` for complete environment variable documentation.

### Kubernetes Configuration

- **ConfigMap**: Non-sensitive configuration in `k8s/configmap.yaml`
- **Secrets**: Sensitive data in `k8s/secret.yaml` (not committed to git)

### Health Checks

The application provides health check endpoints:

- `/health` - Liveness probe (checks database connectivity)
- `/ready` - Readiness probe (checks if service is ready)

## Security

### Best Practices

1. **Secrets Management**
   - Use Kubernetes Secrets for sensitive data
   - Never commit secrets to git
   - Use sealed-secrets or external-secrets operator in production

2. **Network Security**
   - Use TLS/SSL for all external traffic
   - Configure CORS properly
   - Use network policies in Kubernetes

3. **Container Security**
   - Run containers as non-root user
   - Use minimal base images
   - Regularly scan images for vulnerabilities

4. **Authentication**
   - Implement proper user authentication
   - Store OAuth tokens securely
   - Use refresh tokens where possible

5. **Data Privacy**
   - Encrypt data at rest
   - Use secure connections
   - Implement access controls

### Security Scanning

The CI/CD pipeline includes:
- Trivy vulnerability scanning
- Dependency scanning
- Container image scanning

Run locally:
```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image rag-llm-drive-connector:latest
```

## Monitoring

### Health Checks

- Liveness: `/health`
- Readiness: `/ready`

### Metrics

The application is configured for Prometheus scraping:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

### Logging

- Structured logging (JSON format recommended)
- Log levels configurable via `LOG_LEVEL` environment variable
- Centralized logging with EFK stack or Loki

### Observability

Recommended tools:
- **Prometheus** - Metrics collection
- **Grafana** - Visualization
- **Loki** - Log aggregation
- **Jaeger** - Distributed tracing

## CI/CD Pipeline

The GitHub Actions workflow includes:

1. **Lint** - Code quality checks
2. **Test** - Unit and integration tests
3. **Build** - Docker image build
4. **Security Scan** - Vulnerability scanning
5. **Deploy** - Automatic deployment to staging/production

### Pipeline Triggers

- **Push to main** → Deploy to production
- **Push to develop** → Deploy to staging
- **Pull Request** → Run tests and scans
- **Manual dispatch** → Deploy to selected environment

### Secrets Required

Configure in GitHub Secrets:

- `OPENAI_API_KEY` - OpenAI API key
- `KUBECONFIG_STAGING` - Base64 encoded kubeconfig for staging
- `KUBECONFIG_PRODUCTION` - Base64 encoded kubeconfig for production

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Write tests for new features
- Update documentation
- Ensure CI/CD pipeline passes

### Code Quality

**Using Conda:**
```bash
conda activate rag-llm-drive-connector
pip install black isort flake8 mypy
black .
isort .
flake8 .
mypy .
```

**Using pip:**
```bash
# Install tools
pip install black isort flake8 mypy

# Format code
black .

# Sort imports
isort .

# Lint
flake8 .

# Type checking
mypy .
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain)
- [FastAPI](https://fastapi.tiangolo.com/)
- [PgVector](https://github.com/pgvector/pgvector)
- [Gradio](https://gradio.app/)

## Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/your-org/rag-llm-drive-connector/issues)
- Documentation: [Wiki](https://github.com/your-org/rag-llm-drive-connector/wiki)

## Roadmap

- [ ] Multi-turn conversations with chat history
- [ ] Support for more file types
- [ ] Incremental document updates
- [ ] Hybrid search (vector + keyword)
- [ ] User authentication and authorization
- [ ] Document-level access control
- [ ] Caching for embeddings and queries
- [ ] Async FastAPI endpoints
- [ ] WebSocket support for real-time updates
- [ ] Multi-language support

