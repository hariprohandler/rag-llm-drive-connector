# Quick Start Guide

Get up and running in 5 minutes!

## Step 1: Start PostgreSQL with pgvector

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

## Step 2: Install Dependencies

### Option A: Using pip (virtual environment)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Option B: Using Conda (Recommended)

```bash
conda env create -f environment.yml
conda activate rag-llm-drive-connector
```

## Step 3: Configure Environment

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

## Step 4: Run the Application

```bash
python app.py
```

Then visit:
- **API Docs**: http://localhost:8000/docs
- **Gradio UI**: http://localhost:7860

## Testing Without OAuth

You can test the RAG system with local files first:

```python
from ingest import ingest_local_files

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

## Next Steps

1. Set up OAuth credentials (see README.md)
2. Connect your Google Drive or OneDrive
3. Ingest your documents
4. Start querying!

