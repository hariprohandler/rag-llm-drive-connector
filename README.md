# RAG LLM Drive Connector

A production-ready RAG (Retrieval-Augmented Generation) application that connects to Google Drive, OneDrive, Slack, and Teams, allowing users to query their documents using LLMs.

## Quick Start

```bash
# Setup database
make setup-db

# Run migrations
make migrate

# Start services
docker-compose up -d

# Run application
python app.py
```

## Documentation

- **[Setup Guide](docs/SETUP_AND_RUNNING.md)** - Installation and configuration
- **[Developer Standards](docs/DEVELOPER_STANDARDS.md)** - Coding standards and patterns
- **[Architecture](docs/architecture/)** - System architecture and design decisions
- **[API Documentation](docs/api/)** - API endpoints and usage
- **[Security](docs/SECURITY.md)** - Security guidelines
- **[Contributing](docs/CONTRIBUTING.md)** - Contribution guidelines

## Features

- 🔐 OAuth Authentication (Google, Microsoft, Slack, Teams)
- 📄 Multi-Source Ingestion (Drive, OneDrive, Slack, Teams, Local files)
- 🔍 Semantic Search with PgVector
- 💬 Multi-LLM Support (OpenAI, Gemini, Anthropic, Custom)
- 🏢 Institutional Accounts with role-based access
- 🏷️ Tagging System
- 🔧 Model Fine-Tuning
- 📊 Petabyte-Scale Architecture

## Project Structure

```
rag-llm-drive-connector/
├── app/                    # Application code
│   ├── models/            # Database models
│   ├── services/          # Business logic (SOLID principles)
│   ├── api/               # API routes
│   ├── core/              # Core configuration
│   └── helpers/           # Utility functions
├── docs/                   # Documentation
│   ├── architecture/      # Architecture docs
│   ├── api/               # API docs
│   ├── development/       # Development guides
│   └── deployment/        # Deployment guides
├── tests/                  # Test suite
├── migrations/             # Database migrations
└── k8s/                    # Kubernetes manifests
```

## Tech Stack

- **Backend**: FastAPI, Python 3.11
- **Vector DB**: PgVector (PostgreSQL)
- **RAG**: LangChain
- **LLMs**: OpenAI, Gemini, Anthropic
- **Deployment**: Docker, Kubernetes, ArgoCD

## License

MIT License - see [LICENSE](LICENSE) file for details.
