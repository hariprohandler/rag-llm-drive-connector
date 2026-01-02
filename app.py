"""FastAPI application with OAuth authentication and Gradio UI."""
from fastapi import FastAPI, Request, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import gradio as gr
import uvicorn
import config
import models
from auth_service import get_current_user
from auth_oauth import (
    get_google_auth_url,
    handle_google_callback,
    get_microsoft_auth_url,
    handle_microsoft_callback
)
from rag import ask_question
from ingest import ingest_google_drive, ingest_onedrive, ingest_local_files

# Initialize database
models.init_db()

app = FastAPI(title="RAG LLM Drive Connector", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Request models
class QueryRequest(BaseModel):
    query: str


class IngestDriveRequest(BaseModel):
    folder_id: str


class IngestOneDriveRequest(BaseModel):
    folder_path: str


class FileUploadRequest(BaseModel):
    file_paths: list[str]


# Authentication endpoints
@app.get("/auth/login/google")
async def google_login(request: Request):
    """Initiate Google OAuth login."""
    redirect_uri = str(request.url_for("google_callback"))
    auth_url, state = get_google_auth_url(redirect_uri, request=request)
    return RedirectResponse(url=auth_url)


@app.get("/auth/callback/google")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(models.get_db)
):
    """Handle Google OAuth callback."""
    try:
        user, access_token = handle_google_callback(code, state, db, request=request)
        
        # Redirect to frontend with token
        frontend_url = "http://localhost:7860"  # Update with your frontend URL
        return RedirectResponse(
            url=f"{frontend_url}?token={access_token}",
            status_code=302
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/login/microsoft")
async def microsoft_login(request: Request):
    """Initiate Microsoft OAuth login."""
    redirect_uri = str(request.url_for("microsoft_callback"))
    auth_url, state = get_microsoft_auth_url(redirect_uri, request=request)
    return RedirectResponse(url=auth_url)


@app.get("/auth/callback/microsoft")
async def microsoft_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(models.get_db)
):
    """Handle Microsoft OAuth callback."""
    try:
        user, access_token = handle_microsoft_callback(code, state, db, request=request)
        
        # Redirect to frontend with token
        frontend_url = "http://localhost:7860"  # Update with your frontend URL
        return RedirectResponse(
            url=f"{frontend_url}?token={access_token}",
            status_code=302
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/me")
async def get_current_user_info(current_user: models.User = Depends(get_current_user)):
    """Get current user information."""
    return current_user.to_dict()


# Protected API endpoints
@app.post("/api/query")
async def query(
    request_body: QueryRequest,
    fastapi_request: Request,
    current_user: models.User = Depends(get_current_user)
):
    """Query the RAG system (requires authentication)."""
    # Logging is handled in ask_question function
    try:
        result = ask_question(
            query=request_body.query,
            user_id=current_user.id,
            request=fastapi_request
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/google-drive")
async def ingest_google(
    request: IngestDriveRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Ingest documents from Google Drive (requires authentication)."""
    # TODO: Retrieve stored credentials for user (implement credential storage)
    # For now, this requires re-authentication
    raise HTTPException(
        status_code=501,
        detail="Google Drive ingestion requires credential storage implementation"
    )
    
    # collection_name = f"user_{current_user.id}_google"
    # success = ingest_google_drive(
    #     folder_id=request.folder_id,
    #     credentials=credentials,
    #     user_id=current_user.id
    # )
    # 
    # if success:
    #     return {"status": "success", "message": "Documents ingested successfully"}
    # else:
    #     raise HTTPException(status_code=500, detail="Failed to ingest documents")


@app.post("/api/ingest/onedrive")
async def ingest_onedrive_endpoint(
    request: IngestOneDriveRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Ingest documents from OneDrive (requires authentication)."""
    # TODO: Retrieve stored credentials for user (implement credential storage)
    raise HTTPException(
        status_code=501,
        detail="OneDrive ingestion requires credential storage implementation"
    )


@app.post("/api/ingest/files")
async def ingest_files(
    request: FileUploadRequest,
    current_user: models.User = Depends(get_current_user)
):
    """Ingest local files (requires authentication)."""
    try:
        success = ingest_local_files(
            file_paths=request.file_paths,
            user_id=current_user.id
        )
        if success:
            return {"status": "success", "message": "Files ingested successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to ingest files")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        db_url = config.settings.database_url.replace("postgresql+psycopg2://", "postgresql://")
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
        db_url = config.settings.database_url.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(db_url, connect_timeout=5)
        conn.close()
        return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="Service not ready")


# Gradio UI with authentication
def gradio_query(query: str, token: str = ""):
    """Gradio interface for querying (requires token)."""
    if not token:
        return "Please login first. Use the login buttons above."
    
    if not query.strip():
        return "Please enter a question."
    
    try:
        # Verify token and get user
        from auth_service import verify_token
        payload = verify_token(token)
        user_id = payload.get("sub")
        
        result = ask_question(query=query, user_id=user_id)
        answer = result.get("answer", "No answer generated")
        sources = result.get("sources", [])
        
        if sources:
            answer += "\n\n**Sources:**\n"
            for i, source in enumerate(sources, 1):
                answer += f"\n{i}. {source.get('metadata', {}).get('file_name', 'Unknown')}\n"
        
        return answer
    except Exception as e:
        return f"Error: {str(e)}. Please check your token."


def create_gradio_interface():
    """Create and return Gradio interface with authentication."""
    with gr.Blocks(title="RAG Drive Connector") as demo:
        gr.Markdown("# 📄 RAG LLM Drive Connector")
        gr.Markdown("🔒 **Authentication Required** - Please login to access your documents")
        
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 🔐 Authentication")
                with gr.Row():
                    google_login_btn = gr.Button("🔗 Login with Google", variant="primary")
                    microsoft_login_btn = gr.Button("🔗 Login with Microsoft", variant="primary")
                
                token_input = gr.Textbox(
                    label="Access Token",
                    type="password",
                    placeholder="Enter your access token (from OAuth callback)",
                    visible=False
                )
                
                gr.Markdown("### 📥 Ingest Documents")
                with gr.Column():
                    file_upload = gr.File(
                        label="Upload Files",
                        file_count="multiple"
                    )
                    ingest_files_btn = gr.Button("📥 Ingest Files")
                
                gr.Markdown("**Note:** Drive ingestion requires credential storage setup")
        
        gr.Markdown("### ❓ Ask Questions")
        with gr.Row():
            query_input = gr.Textbox(
                label="Your Question",
                placeholder="Ask anything about your documents...",
                lines=3
            )
        
        submit_btn = gr.Button("Ask", variant="primary")
        answer_output = gr.Markdown(label="Answer")
        
        # Event handlers
        def google_login():
            return "Please visit: /auth/login/google (or click the button to open in new tab)"
        
        def microsoft_login():
            return "Please visit: /auth/login/microsoft (or click the button to open in new tab)"
        
        def ingest_files_handler(files, token):
            if not token:
                return "Please login first"
            if not files:
                return "Please select files to upload"
            
            try:
                from auth_service import verify_token
                payload = verify_token(token)
                user_id = payload.get("sub")
                
                file_paths = [f.name for f in files if f]
                success = ingest_local_files(file_paths=file_paths, user_id=user_id)
                return "Files ingested successfully!" if success else "Ingestion failed"
            except Exception as e:
                return f"Error: {str(e)}"
        
        google_login_btn.click(
            fn=lambda: gr.update(value="Please visit: /auth/login/google"),
            outputs=answer_output
        )
        
        microsoft_login_btn.click(
            fn=lambda: gr.update(value="Please visit: /auth/login/microsoft"),
            outputs=answer_output
        )
        
        ingest_files_btn.click(
            fn=lambda files, token: ingest_files_handler(files, token),
            inputs=[file_upload, token_input],
            outputs=answer_output
        )
        
        submit_btn.click(
            fn=lambda q, t: gradio_query(q, t),
            inputs=[query_input, token_input],
            outputs=answer_output
        )
        
        query_input.submit(
            fn=lambda q, t: gradio_query(q, t),
            inputs=[query_input, token_input],
            outputs=answer_output
        )
    
    return demo


# Launch Gradio in a separate process/thread
gr_app = create_gradio_interface()


@app.on_event("startup")
async def startup_event():
    """Startup event - launch Gradio."""
    import threading
    
    def launch_gradio():
        gr_app.launch(
            server_name="0.0.0.0",
            server_port=config.settings.gradio_port,
            share=False,
            inbrowser=False
        )
    
    thread = threading.Thread(target=launch_gradio, daemon=True)
    thread.start()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=config.settings.host,
        port=config.settings.port
    )
