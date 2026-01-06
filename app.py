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
from llm_service import (
    create_llm_config,
    get_llm_configs,
    get_llm_config,
    update_llm_config,
    delete_llm_config
)
from chat_service import (
    create_conversation,
    get_conversations,
    get_conversation,
    update_conversation,
    delete_conversation,
    add_message,
    get_messages
)
from fastapi import UploadFile, File
import shutil
import tempfile
import os

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
    knowledge_base_name: Optional[str] = None


class LLMConfigRequest(BaseModel):
    provider: str  # 'openai', 'gemini', 'anthropic', 'custom'
    api_key: str
    model_name: Optional[str] = None
    base_url: Optional[str] = None  # For custom LLMs
    temperature: Optional[str] = "0"
    max_tokens: Optional[int] = None
    is_default: bool = False


class LLMConfigUpdateRequest(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[int] = None
    is_default: Optional[bool] = None


class ChatMessageRequest(BaseModel):
    content: str
    conversation_id: Optional[int] = None
    use_rag: bool = True
    llm_config_id: Optional[int] = None


class ConversationRequest(BaseModel):
    title: Optional[str] = None
    is_private: bool = True
    llm_config_id: Optional[int] = None
    use_rag: bool = True


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = None
    is_private: Optional[bool] = None
    llm_config_id: Optional[int] = None
    use_rag: Optional[bool] = None


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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db),
    llm_config_id: Optional[int] = None,
    use_rag: bool = True
):
    """Query the RAG system (requires authentication)."""
    # Logging is handled in ask_question function
    try:
        result = ask_question(
            query=request_body.query,
            user_id=current_user.id,
            db=db,
            request=fastapi_request,
            llm_config_id=llm_config_id,
            use_rag=use_rag
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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Ingest local files (requires authentication)."""
    try:
        success, kb_id = ingest_local_files(
            file_paths=request.file_paths,
            user_id=current_user.id,
            db=db,
            knowledge_base_name=request.knowledge_base_name
        )
        if success:
            return {
                "status": "success",
                "message": "Files ingested successfully",
                "knowledge_base_id": kb_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to ingest files")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    knowledge_base_name: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Upload and ingest files (requires authentication)."""
    try:
        # Save uploaded files to temp directory
        temp_dir = tempfile.mkdtemp()
        file_paths = []
        
        try:
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                file_paths.append(file_path)
            
            success, kb_id = ingest_local_files(
                file_paths=file_paths,
                user_id=current_user.id,
                db=db,
                knowledge_base_name=knowledge_base_name
            )
            
            if success:
                return {
                    "status": "success",
                    "message": "Files uploaded and ingested successfully",
                    "knowledge_base_id": kb_id
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to ingest files")
        finally:
            # Clean up temp files
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# LLM Configuration endpoints
@app.post("/api/llm-configs")
async def create_llm_config_endpoint(
    request: LLMConfigRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Create a new LLM configuration."""
    try:
        config_obj = create_llm_config(
            db=db,
            user_id=current_user.id,
            provider=request.provider,
            api_key=request.api_key,
            model_name=request.model_name,
            base_url=request.base_url,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            is_default=request.is_default
        )
        return config_obj.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/llm-configs")
async def list_llm_configs(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Get all LLM configurations for the current user."""
    configs = get_llm_configs(db, current_user.id)
    return [config.to_dict() for config in configs]


@app.get("/api/llm-configs/{config_id}")
async def get_llm_config_endpoint(
    config_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Get a specific LLM configuration."""
    config_obj = get_llm_config(db, current_user.id, config_id)
    if not config_obj:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    return config_obj.to_dict()


@app.put("/api/llm-configs/{config_id}")
async def update_llm_config_endpoint(
    config_id: int,
    request: LLMConfigUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Update an LLM configuration."""
    config_obj = update_llm_config(
        db=db,
        user_id=current_user.id,
        config_id=config_id,
        provider=request.provider,
        api_key=request.api_key,
        model_name=request.model_name,
        base_url=request.base_url,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        is_default=request.is_default
    )
    if not config_obj:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    return config_obj.to_dict()


@app.delete("/api/llm-configs/{config_id}")
async def delete_llm_config_endpoint(
    config_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Delete an LLM configuration."""
    success = delete_llm_config(db, current_user.id, config_id)
    if not success:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    return {"status": "success", "message": "LLM configuration deleted"}


# Knowledge Base endpoints
@app.get("/api/knowledge-bases")
async def list_knowledge_bases(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Get all knowledge bases for the current user."""
    kbs = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.user_id == current_user.id,
        models.KnowledgeBase.is_active == True
    ).all()
    return [kb.to_dict() for kb in kbs]


@app.get("/api/knowledge-bases/{kb_id}")
async def get_knowledge_base(
    kb_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Get a specific knowledge base."""
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == kb_id,
        models.KnowledgeBase.user_id == current_user.id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb.to_dict()


@app.delete("/api/knowledge-bases/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Soft delete a knowledge base."""
    kb = db.query(models.KnowledgeBase).filter(
        models.KnowledgeBase.id == kb_id,
        models.KnowledgeBase.user_id == current_user.id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    kb.is_active = False
    db.commit()
    return {"status": "success", "message": "Knowledge base deleted"}


# Chat endpoints
@app.post("/api/chat/conversations")
async def create_chat_conversation(
    request: ConversationRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Create a new chat conversation."""
    conversation = create_conversation(
        db=db,
        user_id=current_user.id,
        title=request.title,
        is_private=request.is_private,
        llm_config_id=request.llm_config_id,
        use_rag=request.use_rag
    )
    return conversation.to_dict()


@app.get("/api/chat/conversations")
async def list_chat_conversations(
    is_private: Optional[bool] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Get all chat conversations for the current user."""
    conversations = get_conversations(db, current_user.id, is_private)
    return [conv.to_dict() for conv in conversations]


@app.get("/api/chat/conversations/{conversation_id}")
async def get_chat_conversation(
    conversation_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Get a specific chat conversation with messages."""
    conversation = get_conversation(db, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    result = conversation.to_dict()
    messages = get_messages(db, conversation_id)
    result["messages"] = [msg.to_dict() for msg in messages]
    return result


@app.put("/api/chat/conversations/{conversation_id}")
async def update_chat_conversation(
    conversation_id: int,
    request: ConversationUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Update a chat conversation."""
    conversation = update_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        title=request.title,
        is_private=request.is_private,
        llm_config_id=request.llm_config_id,
        use_rag=request.use_rag
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation.to_dict()


@app.delete("/api/chat/conversations/{conversation_id}")
async def delete_chat_conversation(
    conversation_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Delete a chat conversation."""
    success = delete_conversation(db, current_user.id, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "message": "Conversation deleted"}


@app.post("/api/chat/messages")
async def send_chat_message(
    request: ChatMessageRequest,
    fastapi_request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Send a message in a chat conversation."""
    try:
        # Get or create conversation
        if request.conversation_id:
            conversation = get_conversation(db, current_user.id, request.conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            # Create new conversation
            conversation = create_conversation(
                db=db,
                user_id=current_user.id,
                is_private=True,
                llm_config_id=request.llm_config_id,
                use_rag=request.use_rag
            )
        
        # Add user message
        user_message = add_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=request.content
        )
        
        # Get assistant response
        result = ask_question(
            query=request.content,
            user_id=current_user.id,
            db=db,
            request=fastapi_request,
            llm_config_id=conversation.llm_config_id or request.llm_config_id,
            use_rag=conversation.use_rag if request.conversation_id else request.use_rag
        )
        
        # Add assistant message
        assistant_message = add_message(
            db=db,
            conversation_id=conversation.id,
            role="assistant",
            content=result["answer"],
            metadata={
                "sources": result.get("sources", []),
                "use_rag": result.get("use_rag", False)
            }
        )
        
        return {
            "conversation_id": conversation.id,
            "user_message": user_message.to_dict(),
            "assistant_message": assistant_message.to_dict(),
            "sources": result.get("sources", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/conversations/{conversation_id}/messages")
async def get_chat_messages(
    conversation_id: int,
    limit: Optional[int] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(models.get_db)
):
    """Get messages for a conversation."""
    conversation = get_conversation(db, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = get_messages(db, conversation_id, limit)
    return [msg.to_dict() for msg in messages]


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
        
        # Create database session for Gradio
        db = next(models.get_db())
        try:
            result = ask_question(
                query=query,
                user_id=user_id,
                db=db,
                use_rag=True
            )
            answer = result.get("answer", "No answer generated")
            sources = result.get("sources", [])
            
            if sources:
                answer += "\n\n**Sources:**\n"
                for i, source in enumerate(sources, 1):
                    answer += f"\n{i}. {source.get('metadata', {}).get('file_name', 'Unknown')}\n"
            
            return answer
        finally:
            db.close()
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
                
                # Create database session for Gradio
                db = next(models.get_db())
                try:
                    file_paths = [f.name for f in files if f]
                    success, kb_id = ingest_local_files(
                        file_paths=file_paths,
                        user_id=user_id,
                        db=db
                    )
                    return "Files ingested successfully!" if success else "Ingestion failed"
                finally:
                    db.close()
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
