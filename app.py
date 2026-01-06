"""FastAPI application with OAuth authentication and REST API for React frontend."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
from app.api import auth_routes, ingest_routes, llm_config_routes, chat_routes, kb_routes, query_routes, settings_routes, drive_routes, tools_routes
from app.middleware.tracing import TracingMiddleware

# Initialize database
from app.models.base import init_db

init_db()

app = FastAPI(title="RAG LLM Drive Connector", version="1.0.0")

# Tracing middleware (must be added before CORS)
app.add_middleware(TracingMiddleware)

# CORS middleware
# Note: When allow_credentials=True, you cannot use allow_origins=["*"]
# Must specify explicit origins
frontend_url = settings.frontend_base_url
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        frontend_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router registration (modular API)
app.include_router(auth_routes.router)
app.include_router(query_routes.router)
app.include_router(ingest_routes.router)
app.include_router(llm_config_routes.router)
app.include_router(kb_routes.router)
app.include_router(chat_routes.router)
app.include_router(settings_routes.router)
app.include_router(drive_routes.router)
app.include_router(tools_routes.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "RAG LLM Drive Connector API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "auth": {
            "google": "/auth/login/google",
            "microsoft": "/auth/login/microsoft"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes/Docker."""
    try:
        # Check database connection
        import psycopg2
        db_url = settings.database_url.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(db_url, connect_timeout=5)
        conn.close()
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "service": "rag-llm-drive-connector"
    }


@app.get("/ready")
async def readiness_check():
    """Readiness probe for Kubernetes."""
    try:
        import psycopg2
        db_url = settings.database_url.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(db_url, connect_timeout=5)
        conn.close()
        return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="Service not ready")




if __name__ == "__main__":
    # In production or when not using reload, run directly
    # For development with reload, use: uvicorn app:app --reload --reload-dir ./app
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=False,
    )
