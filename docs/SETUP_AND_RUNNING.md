# Setup and Running Guide

Complete guide for setting up, installing, configuring, and running the RAG LLM Drive Connector application.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Installation Methods](#installation-methods)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Running the Application](#running-the-application)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [ArgoCD Deployment](#argocd-deployment)
- [Testing](#testing)
- [Database Migrations](#database-migrations)
- [Make Commands](#make-commands)
- [Troubleshooting](#troubleshooting)

## Prerequisites

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

## Quick Start

Get up and running in 5 minutes!

### Step 1: Start PostgreSQL with pgvector

```bash
docker-compose up -d
```

Or manually:
```bash
docker run -d \
  --name pgvector \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  ankane/pgvector
```

Then set up the extension:
```bash
python setup_db.py
```

### Step 2: Run Database Migrations

After setting up the database, run migrations to create the schema:

```bash
alembic upgrade head
```

Or using Make:
```bash
make migrate
```

**Note:** The `make migrate` command runs `alembic upgrade head` to apply all pending migrations.

### Step 3: Install Dependencies

See [Installation Methods](#installation-methods) below for detailed instructions.

### Step 4: Configure Environment

Create a `.env` file:
```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/postgres
OPENAI_API_KEY=your_key_here
```

For Google Drive (optional):
```env
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

For OneDrive (optional):
```env
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret
MICROSOFT_TENANT_ID=your_tenant_id
MICROSOFT_REDIRECT_URI=http://localhost:8000/auth/onedrive/callback
```

### Step 5: Run the Application

```bash
python app.py
```

Then visit:
- **API Docs**: http://localhost:8000/docs
- **Gradio UI**: http://localhost:7860

## Installation Methods

### Option A: Using pip (Virtual Environment)

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

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

### Option B: Using Conda (Recommended for Data Science Workflows)

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

6. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

7. **Run the application**
   ```bash
   python app.py
   ```

**Note**: To update the conda environment after changes:
```bash
conda env update -f environment.yml --prune
```

### Option C: Using Docker Compose (Recommended for Local Development)

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

5. **Run database migrations**
   ```bash
   docker-compose exec app alembic upgrade head
   ```

6. **Access the application**
   - API: http://localhost:8000/docs
   - Gradio UI: http://localhost:7860

## Environment Configuration

This project supports environment-specific configuration files to manage different settings for development, staging, and production environments.

### How It Works

The application automatically loads environment-specific `.env` files based on the `ENVIRONMENT` environment variable:

1. **Base configuration**: Always loads `.env` first (if it exists)
2. **Environment-specific**: Then loads `.env.{ENVIRONMENT}` (e.g., `.env.development`, `.env.production`)
3. **Override priority**: Environment-specific values override base `.env` values

### Available Environment Files

- `.env` - Base configuration (shared across all environments)
- `.env.development` - Development environment settings
- `.env.production` - Production environment settings
- `.env.staging` - Staging environment settings (optional)

### Usage

**For Development:**
```bash
export ENVIRONMENT=development
python app.py
```

**For Production:**
```bash
export ENVIRONMENT=production
python app.py
```

**In Docker Compose:**
```yaml
services:
  app:
    environment:
      - ENVIRONMENT=development
```

**In Kubernetes:**
```yaml
env:
  - name: ENVIRONMENT
    value: "production"
```

### Configuration Priority

Settings are loaded in this order (later values override earlier ones):

1. Default values in `app/core/config.py`
2. `.env` file (base configuration)
3. `.env.{ENVIRONMENT}` file (environment-specific)
4. Actual environment variables (highest priority)

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `DATABASE_READ_URL` | PostgreSQL read replica (optional) | - |
| `MONGODB_URL` | MongoDB connection string | mongodb://localhost:27017 |
| `MONGODB_DATABASE` | MongoDB database name | rag_activity_logs |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | - |
| `GOOGLE_REDIRECT_URI` | Google OAuth redirect URI | http://localhost:8000/auth/callback/google |
| `MICROSOFT_CLIENT_ID` | Microsoft OAuth client ID | - |
| `MICROSOFT_CLIENT_SECRET` | Microsoft OAuth client secret | - |
| `MICROSOFT_TENANT_ID` | Microsoft tenant ID | - |
| `MICROSOFT_REDIRECT_URI` | Microsoft OAuth redirect URI | http://localhost:8000/auth/callback/microsoft |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8000 |
| `GRADIO_PORT` | Gradio UI port | 7860 |
| `COLLECTION_NAME` | Vector collection name | documents |
| `CHUNK_SIZE` | Text chunk size | 1000 |
| `CHUNK_OVERLAP` | Chunk overlap | 200 |
| `RETRIEVAL_K` | Number of documents to retrieve | 4 |
| `LLM_MODEL` | OpenAI model name | gpt-4o-mini |
| `LLM_TEMPERATURE` | LLM temperature | 0 |
| `JWT_SECRET_KEY` | JWT secret key | - |
| `JWT_ALGORITHM` | JWT algorithm | HS256 |
| `JWT_EXPIRE_MINUTES` | JWT expiration (minutes) | 43200 |
| `ENCRYPTION_KEY` | Encryption key for API keys | - |
| `ENVIRONMENT` | Environment name (development/production) | - |
| `LOG_LEVEL` | Logging level | INFO |
| `FRONTEND_BASE_URL` | Base URL for React frontend | http://localhost:3000 |
| `BACKEND_BASE_URL` | Base URL for backend API | http://localhost:8000 |

## Database Setup

### Initial Setup

1. **Start PostgreSQL with pgvector**
   ```bash
   docker-compose up -d postgres
   ```

2. **Initialize database**
   ```bash
   python setup_db.py
   ```

   Or with Docker:
   ```bash
   docker-compose exec app python setup_db.py
   ```

3. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

   Or with Docker:
   ```bash
   docker-compose exec app alembic upgrade head
   ```

   Or using Make:
   ```bash
   make migrate
   ```

### Master-Slave Database Support

The application supports master-slave database configuration for read/write separation:

- **Master Database**: Used for all write operations
- **Slave Database**: Used for read operations (optional, falls back to master if not configured)

Configuration in `.env`:
```env
DATABASE_URL=postgresql+psycopg2://user:pass@master-db:5432/dbname
DATABASE_READ_URL=postgresql+psycopg2://user:pass@slave-db:5432/dbname  # Optional
```

## Running the Application

### Local Development

```bash
# Set environment (optional)
export ENVIRONMENT=development

# Run the application
python app.py
```

### Testing Without OAuth

You can test the RAG system with local files first:

```python
from app.services.ingest import ingest_local_files

ingest_local_files(
    file_paths=["data/sample.pdf"],
    collection_name="test",
    user_id="test_user"
)
```

Then query via API:
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this document about?", "collection_name": "test"}'
```

## Docker Deployment

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

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- Access to container registry
- Ingress controller installed

### Manual Deployment

#### 1. Create Namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

#### 2. Create Secrets

**Important:** Never commit `secret.yaml` to git!

```bash
# Copy template
cp k8s/secret.yaml.example k8s/secret.yaml

# Edit with your values
vim k8s/secret.yaml

# Apply
kubectl apply -f k8s/secret.yaml
```

Alternatively, create secrets via CLI:

```bash
kubectl create secret generic rag-app-secrets \
  --from-literal=OPENAI_API_KEY=your-key \
  --from-literal=POSTGRES_PASSWORD=your-password \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=DATABASE_URL=postgresql+psycopg2://postgres:password@postgres-service:5432/postgres \
  -n rag-system
```

#### 3. Create ConfigMap

```bash
kubectl apply -f k8s/configmap.yaml
```

#### 4. Deploy PostgreSQL

```bash
kubectl apply -f k8s/postgres-deployment.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n rag-system --timeout=300s
```

#### 5. Initialize Database

```bash
# Get PostgreSQL pod name
POD_NAME=$(kubectl get pod -l app=postgres -n rag-system -o jsonpath='{.items[0].metadata.name}')

# Execute setup
kubectl exec -it $POD_NAME -n rag-system -- psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 6. Build and Push Docker Image

```bash
# Build
docker build -t your-registry/rag-llm-drive-connector:latest .

# Push
docker push your-registry/rag-llm-drive-connector:latest
```

#### 7. Update Kustomization

Edit `k8s/kustomization.yaml`:

```yaml
images:
  - name: rag-llm-drive-connector
    newName: your-registry/rag-llm-drive-connector
    newTag: latest
```

#### 8. Deploy Application

```bash
kubectl apply -k k8s/

# Wait for deployment
kubectl rollout status deployment/rag-app -n rag-system
```

#### 9. Configure Ingress

Edit `k8s/ingress.yaml` with your domain:

```yaml
spec:
  rules:
  - host: rag-app.your-domain.com
```

Apply:

```bash
kubectl apply -f k8s/ingress.yaml
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

# Check events
kubectl get events -n rag-system --sort-by='.lastTimestamp'
```

### Using Kustomize

```bash
# Build manifests
kubectl kustomize k8s/

# Apply
kubectl apply -k k8s/
```

## ArgoCD Deployment (GitOps)

### Prerequisites

- ArgoCD installed in cluster
- Repository access configured
- ArgoCD CLI installed (optional)

### Setup

#### 1. Configure Repository in ArgoCD

Via UI:
1. Go to Settings > Repositories
2. Connect repository (HTTPS or SSH)
3. Add credentials if private

Via CLI:
```bash
argocd repo add https://github.com/your-org/rag-llm-drive-connector.git \
  --username your-username \
  --password your-token
```

#### 2. Update Application Manifest

Edit `argocd/application.yaml`:

```yaml
spec:
  source:
    repoURL: https://github.com/your-org/rag-llm-drive-connector.git
    targetRevision: main
    path: k8s
```

#### 3. Deploy Application

```bash
kubectl apply -f argocd/application.yaml -n argocd
```

#### 4. Sync Application

Via UI:
1. Open ArgoCD UI
2. Find `rag-llm-drive-connector` application
3. Click "Sync"

Via CLI:
```bash
argocd app sync rag-llm-drive-connector
```

#### 5. Enable Auto-Sync (Optional)

Edit application:

```yaml
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Or via CLI:
```bash
argocd app set rag-llm-drive-connector --sync-policy automated --auto-prune --self-heal
```

### App of Apps Pattern

For managing multiple applications:

```bash
kubectl apply -f argocd/app-of-apps.yaml -n argocd
```

## Testing

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

### Test Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_models.py

# Run specific test
pytest tests/test_models.py::test_user_creation

# Run by marker
pytest -m unit          # Run only unit tests
pytest -m integration   # Run only integration tests
pytest -m "not slow"    # Skip slow tests

# Run with verbose output
pytest -v
```

### Test Structure

- `conftest.py` - Pytest fixtures and configuration
- `test_models.py` - Database model tests
- `test_auth_service.py` - Authentication service tests
- `test_ingest.py` - Document ingestion tests
- `test_rag.py` - RAG pipeline tests
- `test_api.py` - API endpoint tests
- `test_integration.py` - Integration tests

### Test Database

Tests use SQLite by default for faster execution. Set `TEST_DATABASE_URL` environment variable to use a different database:

```bash
export TEST_DATABASE_URL="postgresql://user:pass@localhost/testdb"
pytest
```

## Database Migrations

Database schema changes are managed using [Alembic](https://alembic.sqlalchemy.org/), which provides version control for database schema changes.

### Common Commands

#### Create a New Migration

After modifying models, create a new migration:

```bash
alembic revision --autogenerate -m "Description of changes"
```

#### Apply Migrations

Apply all pending migrations:

```bash
alembic upgrade head
```

#### Rollback Migration

Rollback to a previous version:

```bash
alembic downgrade -1  # Rollback one version
alembic downgrade <revision_id>  # Rollback to specific revision
```

#### Check Migration Status

View current migration status:

```bash
alembic current
alembic history
```

#### Show SQL for Migration

Preview the SQL that will be executed:

```bash
alembic upgrade head --sql
```

### Configuration

The migration configuration is set up to:
- Use the database URL from `app/core/config.py`
- Automatically detect model changes
- Work with PostgreSQL and the pgvector extension
- Load configuration from `.env` file automatically

### Best Practices

1. **Always review autogenerated migrations** - Alembic's autogenerate feature is helpful but may not catch all changes. Review and test migrations before applying to production.

2. **Test migrations** - Test both upgrade and downgrade paths in a development environment.

3. **Commit migrations** - Migration files should be committed to version control.

4. **Use descriptive messages** - When creating migrations, use clear, descriptive messages that explain what the migration does.

5. **One logical change per migration** - Keep migrations focused on a single logical change when possible.

## Make Commands

The project includes a `Makefile` with convenient commands for common tasks. Use `make help` to see all available commands.

### Installation Commands

```bash
# Install dependencies (using pip/venv)
make install

# Install dependencies using conda
make install-conda

# Update conda environment
make install-conda-update
```

### Development Setup

```bash
# Complete development environment setup (install, docker-compose, setup-db)
make dev
```

### Testing Commands

```bash
# Run all tests with coverage
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run tests in watch mode
make test-watch
```

### Code Quality Commands

```bash
# Format code (black + isort)
make format

# Check code formatting
make format-check

# Run linter
make lint

# Run all pre-commit checks (format, lint, test)
make pre-commit
```

### Database Commands

```bash
# Setup database
make setup-db

# Run migrations
make migrate

# Create a new migration
make migrate-create MESSAGE="description of changes"

# Rollback last migration
make migrate-rollback

# Show migration status
make migrate-status
```

### Docker Commands

```bash
# Build Docker image
make docker-build

# Run Docker container
make docker-run

# Start services with docker-compose
make docker-compose-up

# Stop docker-compose services
make docker-compose-down

# View docker-compose logs
make docker-compose-logs
```

### Kubernetes Commands

```bash
# Deploy to Kubernetes
make k8s-deploy

# Delete Kubernetes resources
make k8s-delete

# View Kubernetes logs
make k8s-logs

# Check Kubernetes status
make k8s-status
```

### ArgoCD Commands

```bash
# Sync ArgoCD application
make argocd-sync
```

### Utility Commands

```bash
# Show help message
make help

# Clean up temporary files
make clean
```

### Common Workflows

**Initial Setup:**
```bash
make dev        # Installs dependencies, starts docker-compose, sets up database
make migrate    # Run database migrations
```

**Before Committing:**
```bash
make pre-commit  # Formats, lints, and tests code
```

**Daily Development:**
```bash
make docker-compose-up    # Start services
make test                 # Run tests
make docker-compose-logs  # View logs
```

**Production Deployment:**
```bash
make docker-build         # Build image
make k8s-deploy          # Deploy to Kubernetes
make k8s-status          # Check status
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n rag-system

# Check logs
kubectl logs <pod-name> -n rag-system

# Check events
kubectl get events -n rag-system
```

### Database Connection Issues

```bash
# Test connection
kubectl exec -it deployment/rag-app -n rag-system -- \
  python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')"

# Check PostgreSQL logs
kubectl logs -l app=postgres -n rag-system
```

### Image Pull Errors

```bash
# Check image pull secrets
kubectl get secrets -n rag-system

# Verify image exists
docker pull your-registry/rag-llm-drive-connector:latest

# Check registry credentials
kubectl create secret docker-registry regcred \
  --docker-server=your-registry \
  --docker-username=user \
  --docker-password=pass \
  -n rag-system
```

### Ingress Not Working

```bash
# Check ingress controller
kubectl get pods -n ingress-nginx

# Check ingress status
kubectl describe ingress rag-app-ingress -n rag-system

# Test service directly
kubectl port-forward svc/rag-app-service 8000:80 -n rag-system
```

### ArgoCD Sync Issues

```bash
# Check application status
argocd app get rag-llm-drive-connector

# Check sync history
argocd app history rag-llm-drive-connector

# Force refresh
argocd app get rag-llm-drive-connector --refresh
```

### Environment Configuration Issues

- Check that `ENVIRONMENT` variable is set correctly
- Verify the file exists: `.env.{ENVIRONMENT}`
- Check file permissions
- Look for startup messages indicating which files are loaded
- Remember: actual environment variables override `.env` files

### Migration Issues

1. **Check database connection** - Ensure `DATABASE_URL` is correctly set in your `.env` file
2. **Verify models are imported** - Make sure all models are properly imported
3. **Check for conflicts** - If migrations conflict, you may need to manually resolve them
4. **Review migration files** - Check the generated migration files for any unexpected changes

