# RAG LLM Drive Connector

[![CI/CD Pipeline](https://github.com/your-org/rag-llm-drive-connector/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/your-org/rag-llm-drive-connector/actions/workflows/ci-cd.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

A production-ready RAG (Retrieval-Augmented Generation) application that connects to Google Drive and OneDrive, allowing users to query their documents using LLMs. Built with FastAPI, LangChain, PgVector, and Kubernetes.

## 🚀 Features

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

## 📋 Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Development](#development)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [ArgoCD Deployment](#argocd-deployment)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Security](#security)
- [Monitoring](#monitoring)
- [Contributing](#contributing)
- [License](#license)

## 🏗️ Architecture

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

### Tech Stack

- **Backend**: FastAPI, Python 3.11
- **RAG Framework**: LangChain
- **Vector Database**: PgVector (PostgreSQL extension)
- **LLM**: OpenAI GPT-4o-mini
- **UI**: Gradio
- **Container**: Docker
- **Orchestration**: Kubernetes
- **GitOps**: ArgoCD
- **CI/CD**: GitHub Actions

## 📦 Prerequisites

### For Local Development

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 14+ (or use Docker)
- OpenAI API Key

### For Kubernetes Deployment

- Kubernetes cluster (1.24+)
- kubectl configured
- ArgoCD installed (for GitOps)
- Container registry access
- Ingress controller (nginx recommended)
- cert-manager (for TLS certificates)

### OAuth Setup

#### Google Drive OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Drive API
4. Create OAuth 2.0 credentials (Web application)
5. Add authorized redirect URI: `https://your-domain.com/auth/google/callback`
6. Download credentials (Client ID and Client Secret)

#### Microsoft OneDrive OAuth

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to Azure Active Directory > App registrations
3. Create new registration
4. Add redirect URI: `https://your-domain.com/auth/onedrive/callback`
5. Add API permission: `Files.Read.All` (Microsoft Graph)
6. Create client secret
7. Note: Client ID, Client Secret, and Tenant ID

## 🚀 Quick Start

### Using Docker Compose (Recommended for Local Development)

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/rag-llm-drive-connector.git
   cd rag-llm-drive-connector
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services**
   ```bash
   docker-compose up -d
   ```

4. **Initialize database**
   ```bash
   docker-compose exec app python setup_db.py
   ```

5. **Access the application**
   - API: http://localhost:8000/docs
   - Gradio UI: http://localhost:7860

### Using Python Virtual Environment

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env file
   ```

4. **Start PostgreSQL** (using Docker)
   ```bash
   docker run -d --name pgvector -p 5432:5432 -e POSTGRES_PASSWORD=postgres ankane/pgvector
   python setup_db.py
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

### Using Conda (Recommended for Data Science Workflows)

1. **Install Conda** (if not already installed)
   - Download from [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/)

2. **Create conda environment**
   ```bash
   conda env create -f environment.yml
   ```

3. **Activate environment**
   ```bash
   conda activate rag-llm-drive-connector
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env file
   ```

5. **Start PostgreSQL** (using Docker)
   ```bash
   docker run -d --name pgvector -p 5432:5432 -e POSTGRES_PASSWORD=postgres ankane/pgvector
   python setup_db.py
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

**Note**: To update the conda environment after changes:
```bash
conda env update -f environment.yml --prune
```

## 💻 Development

### Project Structure

```
rag-llm-drive-connector/
├── app.py                  # FastAPI application
├── rag.py                  # RAG pipeline
├── ingest.py               # Document ingestion
├── auth.py                 # OAuth handlers
├── config.py               # Configuration
├── setup_db.py             # Database setup script
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose configuration
├── requirements.txt        # Python dependencies (pip)
├── environment.yml         # Conda environment file
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
├── k8s/                    # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml.example
│   ├── postgres-deployment.yaml
│   ├── app-deployment.yaml
│   ├── ingress.yaml
│   └── kustomization.yaml
├── argocd/                 # ArgoCD manifests
│   ├── application.yaml
│   └── app-of-apps.yaml
└── .github/
    └── workflows/
        ├── ci-cd.yml
        └── image-scan.yml
```

### Running Tests

**Using Conda:**
```bash
conda activate rag-llm-drive-connector
pip install pytest pytest-cov
pytest
pytest --cov=. --cov-report=html
```

**Using pip:**
```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest

# With coverage
pytest --cov=. --cov-report=html
```

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

## 🐳 Docker Deployment

### Build Docker Image

```bash
docker build -t rag-llm-drive-connector:latest .
```

### Run with Docker

```bash
docker run -d \
  --name rag-app \
  -p 8000:8000 \
  -p 7860:7860 \
  --env-file .env \
  rag-llm-drive-connector:latest
```

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## ☸️ Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- Access to container registry

### Manual Deployment

1. **Create namespace**
   ```bash
   kubectl apply -f k8s/namespace.yaml
   ```

2. **Create secrets**
   ```bash
   # Copy and edit secret template
   cp k8s/secret.yaml.example k8s/secret.yaml
   # Edit k8s/secret.yaml with your values
   kubectl apply -f k8s/secret.yaml
   ```

3. **Create configmap**
   ```bash
   kubectl apply -f k8s/configmap.yaml
   ```

4. **Deploy PostgreSQL**
   ```bash
   kubectl apply -f k8s/postgres-deployment.yaml
   ```

5. **Build and push Docker image**
   ```bash
   docker build -t your-registry/rag-llm-drive-connector:latest .
   docker push your-registry/rag-llm-drive-connector:latest
   ```

6. **Update kustomization.yaml** with your registry
   ```yaml
   images:
     - name: rag-llm-drive-connector
       newName: your-registry/rag-llm-drive-connector
       newTag: latest
   ```

7. **Deploy application**
   ```bash
   kubectl apply -k k8s/
   ```

8. **Deploy ingress** (update hostname in ingress.yaml)
   ```bash
   kubectl apply -f k8s/ingress.yaml
   ```

### Using Kustomize

```bash
# Build manifests
kubectl kustomize k8s/

# Apply
kubectl apply -k k8s/
```

### Verify Deployment

```bash
# Check pods
kubectl get pods -n rag-system

# Check services
kubectl get svc -n rag-system

# Check ingress
kubectl get ingress -n rag-system

# View logs
kubectl logs -f deployment/rag-app -n rag-system
```

## 🔄 ArgoCD Deployment (GitOps)

### Prerequisites

- ArgoCD installed in your cluster
- Repository access configured in ArgoCD

### Setup ArgoCD Application

1. **Update ArgoCD application manifest**
   
   Edit `argocd/application.yaml`:
   ```yaml
   spec:
     source:
       repoURL: https://github.com/your-org/rag-llm-drive-connector.git
       targetRevision: main
       path: k8s
   ```

2. **Apply ArgoCD application**
   ```bash
   kubectl apply -f argocd/application.yaml -n argocd
   ```

3. **Access ArgoCD UI**
   ```bash
   kubectl port-forward svc/argocd-server -n argocd 8080:443
   # Access: https://localhost:8080
   ```

4. **Sync application**
   - Via UI: Click "Sync" button
   - Via CLI: `argocd app sync rag-llm-drive-connector`

### App of Apps Pattern

For managing multiple applications:

```bash
kubectl apply -f argocd/app-of-apps.yaml -n argocd
```

## ⚙️ Configuration

### Environment Variables

See `.env.example` for all available configuration options:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | - |
| `MICROSOFT_CLIENT_ID` | Microsoft OAuth client ID | - |
| `MICROSOFT_CLIENT_SECRET` | Microsoft OAuth client secret | - |
| `MICROSOFT_TENANT_ID` | Microsoft tenant ID | - |
| `CHUNK_SIZE` | Text chunk size | 1000 |
| `CHUNK_OVERLAP` | Chunk overlap | 200 |
| `RETRIEVAL_K` | Number of documents to retrieve | 4 |
| `LLM_MODEL` | OpenAI model name | gpt-4o-mini |
| `LLM_TEMPERATURE` | LLM temperature | 0 |

### Kubernetes Configuration

- **ConfigMap**: Non-sensitive configuration in `k8s/configmap.yaml`
- **Secrets**: Sensitive data in `k8s/secret.yaml` (not committed to git)

### Health Checks

The application provides health check endpoints:

- `/health` - Liveness probe (checks database connectivity)
- `/ready` - Readiness probe (checks if service is ready)

## 📚 API Documentation

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

## 🔒 Security

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

## 📊 Monitoring

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

## 🔄 CI/CD Pipeline

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

## 🤝 Contributing

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

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain)
- [FastAPI](https://fastapi.tiangolo.com/)
- [PgVector](https://github.com/pgvector/pgvector)
- [Gradio](https://gradio.app/)

## 📞 Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/your-org/rag-llm-drive-connector/issues)
- Documentation: [Wiki](https://github.com/your-org/rag-llm-drive-connector/wiki)

## 🔮 Roadmap

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
