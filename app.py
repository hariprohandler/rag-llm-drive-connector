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
from app.core.config import settings
from app.models import User, Base, KnowledgeBase
from app.models.base import get_db
from auth_service import get_current_user
from auth_oauth import (
    get_google_auth_url,
    handle_google_callback,
    get_microsoft_auth_url,
    handle_microsoft_callback
)
from app.services.rag import ask_question
from app.services.ingest import ingest_google_drive, ingest_onedrive, ingest_local_files
from app.services.llm_service import (
    create_llm_config,
    get_llm_configs,
    get_llm_config,
    update_llm_config,
    delete_llm_config
)
from app.services.chat_service import (
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
from app.models.base import init_db
init_db()

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
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
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
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user.to_dict()


# Protected API endpoints
@app.post("/api/query")
async def query(
    request_body: QueryRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all LLM configurations for the current user."""
    configs = get_llm_configs(db, current_user.id)
    return [config.to_dict() for config in configs]


@app.get("/api/llm-configs/{config_id}")
async def get_llm_config_endpoint(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an LLM configuration."""
    success = delete_llm_config(db, current_user.id, config_id)
    if not success:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    return {"status": "success", "message": "LLM configuration deleted"}


# Knowledge Base endpoints
@app.get("/api/knowledge-bases")
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all knowledge bases for the current user."""
    kbs = db.query(KnowledgeBase).filter(
        KnowledgeBase.user_id == current_user.id,
        KnowledgeBase.is_active == True
    ).all()
    return [kb.to_dict() for kb in kbs]


@app.get("/api/knowledge-bases/{kb_id}")
async def get_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific knowledge base."""
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user.id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb.to_dict()


@app.delete("/api/knowledge-bases/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Soft delete a knowledge base."""
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user.id
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all chat conversations for the current user."""
    conversations = get_conversations(db, current_user.id, is_private)
    return [conv.to_dict() for conv in conversations]


@app.get("/api/chat/conversations/{conversation_id}")
async def get_chat_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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


# Gradio UI with modern design matching screenshots
def get_user_info(user_id: str, db: Session):
    """Get user information for display."""
    from app.models import User
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        provider_name = user.provider.capitalize() if user.provider else "Demo"
        return f"{user.name or 'Demo User'} ({provider_name})"
    return "Demo User (Google)"


def get_document_count(user_id: str, db: Session):
    """Get total document count for user."""
    from app.models import KnowledgeBase
    total = db.query(KnowledgeBase).filter(
        KnowledgeBase.user_id == user_id,
        KnowledgeBase.is_active == True
    ).count()
    return total


def get_default_model_name(user_id: str, db: Session):
    """Get default model name for user."""
    from app.services.llm_service import get_llm_configs
    configs = get_llm_configs(db, user_id)
    default_config = next((c for c in configs if c.is_default), None)
    if default_config:
        return f"{default_config.provider.capitalize()} - {default_config.model_name or 'default'}"
    return "Default model"


def update_status_text(user_state, db):
    """Update status text with current document count and model."""
    if not user_state or not user_state.get("authenticated"):
        return "Ask questions about your documents • 0 document(s) loaded • Using default model"
    
    user_id = user_state.get("user_id")
    if not user_id:
        return "Ask questions about your documents • 0 document(s) loaded • Using default model"
    
    try:
        doc_count = get_document_count(user_id, db)
        model_name = get_default_model_name(user_id, db)
        return f"Ask questions about your documents • {doc_count} document(s) loaded • Using {model_name}"
    except:
        return "Ask questions about your documents • 0 document(s) loaded • Using default model"


def create_gradio_interface():
    """Create modern Gradio interface matching the screenshots."""
    
    # Custom CSS for modern design matching screenshots
    custom_css = """
    .gradio-container {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .main-container {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        min-height: 100vh;
        padding: 20px;
    }
    .login-card {
        background: white;
        border-radius: 16px;
        padding: 50px 40px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        max-width: 450px;
        margin: 50px auto;
        text-align: center;
    }
    .logo-container {
        width: 100px;
        height: 100px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 30px;
        font-size: 48px;
    }
    .sidebar-dark {
        background: linear-gradient(180deg, #1a1a1a 0%, #2d2d2d 100%);
        color: white;
        padding: 20px;
        min-height: 100vh;
    }
    .main-content-light {
        background: #f5f5f5;
        padding: 30px;
        min-height: 100vh;
    }
    .demo-mode-text {
        color: #666;
        font-size: 14px;
        margin-top: 20px;
    }
    .status-text {
        color: #666;
        font-size: 14px;
        margin-bottom: 20px;
    }
    """
    
    with gr.Blocks(title="RAG Chat Platform", theme=gr.themes.Soft(), css=custom_css) as demo:
        # State to track authentication and user info
        user_state = gr.State(value={"authenticated": False, "user_id": None, "token": None})
        current_page = gr.State(value="login")  # login, chat, documents, settings
        
        # Login Page
        with gr.Column(visible=True, elem_classes="main-container") as login_page:
            with gr.Column(elem_classes="login-card"):
                gr.HTML("""
                    <div class="logo-container">🧠</div>
                """)
                
                gr.Markdown(
                    "# RAG Chat Platform\n\n"
                    "Sign in to access your intelligent document assistant",
                    elem_id="login-title"
                )
                
                with gr.Row():
                    google_btn = gr.Button(
                        "Continue with Google",
                        variant="secondary",
                        size="lg",
                        scale=1
                    )
                
                with gr.Row():
                    microsoft_btn = gr.Button(
                        "Continue with Microsoft",
                        variant="secondary",
                        size="lg",
                        scale=1
                    )
        
        # Main Application (hidden initially)
        with gr.Row(visible=False) as main_app:
            # Left Sidebar
            with gr.Column(scale=1, min_width=250, elem_classes="sidebar-dark") as sidebar:
                gr.Markdown("### RAG Chat Platform", elem_id="sidebar-title")
                user_display = gr.Markdown("Demo User (Google)", elem_id="user-info")
                
                chat_btn = gr.Button("💬 Chat", variant="primary", size="lg")
                documents_btn = gr.Button("📄 Documents", variant="secondary", size="lg")
                settings_btn = gr.Button("⚙️ LLM Settings", variant="secondary", size="lg")
                
                gr.Markdown("---")
                logout_btn = gr.Button("Logout", variant="stop", size="sm")
            
            # Main Content Area
            with gr.Column(scale=4, elem_classes="main-content-light") as main_content:
                # Chat Page
                with gr.Column(visible=True) as chat_page:
                    gr.Markdown("# Chat Assistant", elem_id="page-title")
                    status_text = gr.Markdown(
                        "Ask questions about your documents • 0 document(s) loaded • Using default model",
                        elem_classes="status-text"
                    )
                    
                    # Empty state message
                    empty_state = gr.Markdown(
                        "### 🧠\n\n**Start a conversation**\n\nUpload documents first to enable RAG-based queries.",
                        visible=True,
                        elem_id="empty-state"
                    )
                    
                    chat_history = gr.Chatbot(
                        label="",
                        height=500,
                        show_label=False,
                        container=True,
                        visible=False
                    )
                    
                    with gr.Row():
                        query_input = gr.Textbox(
                            placeholder="Ask a question about your documents...",
                            show_label=False,
                            scale=9,
                            container=False
                        )
                        send_btn = gr.Button("➤", variant="primary", scale=1, size="sm")
                
                # Documents Page
                with gr.Column(visible=False) as documents_page:
                    gr.Markdown("# Document Management", elem_id="page-title")
                    gr.Markdown("Upload and manage documents for RAG-based queries.")
                    
                    doc_tabs = gr.Tabs(selected=0)
                    with doc_tabs:
                        with gr.Tab("Local Upload"):
                            gr.Markdown("### Upload Local Files")
                            gr.Markdown("Upload documents from your computer (PDF, TXT, DOCX, MD).")
                            
                            file_upload = gr.File(
                                label="",
                                file_count="multiple",
                                file_types=[".pdf", ".txt", ".docx", ".md"],
                                height=300,
                                show_label=False
                            )
                            
                            upload_status = gr.Markdown("", visible=False)
                            gr.Markdown("Supported formats: PDF, TXT, DOCX, MD")
                        
                        with gr.Tab("Google Drive"):
                            gr.Markdown("### Connect Google Drive")
                            gr.Markdown("Connect your Google Drive to import documents.")
                            drive_folder_input = gr.Textbox(
                                label="Folder ID (optional - leave empty for root)",
                                placeholder="Enter Google Drive folder ID"
                            )
                            connect_drive_btn = gr.Button("Connect Google Drive", variant="primary")
                        
                        with gr.Tab("OneDrive"):
                            gr.Markdown("### Connect OneDrive")
                            gr.Markdown("Connect your OneDrive to import documents.")
                            onedrive_path_input = gr.Textbox(
                                label="Folder Path",
                                placeholder="/Documents/MyFolder"
                            )
                            connect_onedrive_btn = gr.Button("Connect OneDrive", variant="primary")
                
                # LLM Settings Page
                with gr.Column(visible=False) as settings_page:
                    gr.Markdown("# LLM Configuration", elem_id="page-title")
                    gr.Markdown("Configure your language model provider and settings.")
                    
                    save_status = gr.Markdown("", visible=False)
                    
                    llm_tabs = gr.Tabs(selected=0)
                    with llm_tabs:
                        with gr.Tab("Default"):
                            gr.Markdown("### Default Configuration")
                            gr.Markdown(
                                "Use the platform's default LLM configuration (demo mode)\n\n"
                                "The default configuration uses a simulated LLM for demonstration purposes. No API keys required."
                            )
                        
                        with gr.Tab("OpenAI"):
                            gr.Markdown("### OpenAI Configuration")
                            openai_api_key = gr.Textbox(
                                label="API Key",
                                type="password",
                                placeholder="sk-..."
                            )
                            openai_model = gr.Dropdown(
                                choices=["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
                                label="Model",
                                value="gpt-4o-mini"
                            )
                            openai_temp = gr.Slider(0, 2, value=0, step=0.1, label="Temperature")
                            openai_save = gr.Button("Save Configuration", variant="primary")
                        
                        with gr.Tab("Gemini"):
                            gr.Markdown("### Google Gemini Configuration")
                            gemini_api_key = gr.Textbox(
                                label="API Key",
                                type="password"
                            )
                            gemini_model = gr.Dropdown(
                                choices=["gemini-pro", "gemini-pro-vision"],
                                label="Model",
                                value="gemini-pro"
                            )
                            gemini_save = gr.Button("Save Configuration", variant="primary")
                        
                        with gr.Tab("Anthropic"):
                            gr.Markdown("### Anthropic Claude Configuration")
                            anthropic_api_key = gr.Textbox(
                                label="API Key",
                                type="password"
                            )
                            anthropic_model = gr.Dropdown(
                                choices=["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
                                label="Model",
                                value="claude-3-opus-20240229"
                            )
                            anthropic_save = gr.Button("Save Configuration", variant="primary")
                        
                        with gr.Tab("Local LLM"):
                            gr.Markdown("### Local LLM Configuration")
                            local_base_url = gr.Textbox(
                                label="Base URL",
                                placeholder="http://localhost:8000/v1"
                            )
                            local_model = gr.Textbox(
                                label="Model Name",
                                placeholder="local-llm"
                            )
                            local_save = gr.Button("Save Configuration", variant="primary")
        
        # Event Handlers
        def handle_login(provider: str):
            """Handle login - in demo mode, just authenticate."""
            # Update user display based on provider
            user_display_text = f"Demo User ({provider.capitalize()})"
            return (
                gr.update(visible=False),  # Hide login page
                gr.update(visible=True),   # Show main app
                {"authenticated": True, "user_id": "demo_user", "token": "demo_token", "provider": provider},
                "chat",  # Navigate to chat page
                user_display_text  # Update user display
            )
        
        def navigate_to_chat(user_state):
            """Navigate to chat page and update status."""
            status_update = "Ask questions about your documents • 0 document(s) loaded • Using default model"
            if user_state and user_state.get("authenticated"):
                user_id = user_state.get("user_id")
                if user_id and user_id != "demo_user":
                    try:
                        db = next(get_db())
                        try:
                            status_update = update_status_text(user_state, db)
                        finally:
                            db.close()
                    except:
                        pass
            return (
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
                "chat",
                status_update
            )
        
        def navigate_to_documents():
            return (
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=False),
                "documents"
            )
        
        def navigate_to_settings():
            return (
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
                "settings"
            )
        
        def handle_logout():
            return (
                gr.update(visible=True),   # Show login page
                gr.update(visible=False),  # Hide main app
                {"authenticated": False, "user_id": None, "token": None},
                "login"
            )
        
        def send_message(message, history, user_state):
            """Handle sending a chat message."""
            if not message.strip():
                return history, "", gr.update(visible=True), gr.update(visible=False)
            
            # Add user message
            if history is None:
                history = []
            history.append([message, None])
            
            # Get response from backend
            response = "This is a demo response. Please configure your LLM settings and upload documents to enable RAG-based queries."
            
            if user_state and user_state.get("authenticated"):
                user_id = user_state.get("user_id")
                if user_id and user_id != "demo_user":
                    try:
                        db = next(get_db())
                        try:
                            result = ask_question(
                                query=message,
                                user_id=user_id,
                                db=db,
                                use_rag=True
                            )
                            response = result.get("answer", "No answer generated")
                            sources = result.get("sources", [])
                            if sources:
                                response += "\n\n**Sources:**\n"
                                for i, source in enumerate(sources, 1):
                                    response += f"{i}. {source.get('metadata', {}).get('file_name', 'Unknown')}\n"
                        finally:
                            db.close()
                    except Exception as e:
                        response = f"Error: {str(e)}"
            
            history[-1][1] = response
            
            # Hide empty state, show chat
            return history, "", gr.update(visible=False), gr.update(visible=True)
        
        def upload_files_handler(files, user_state):
            """Handle file upload."""
            if not files:
                return "Please select files to upload", gr.update(visible=False), "Ask questions about your documents • 0 document(s) loaded • Using default model"
            
            if not user_state or not user_state.get("authenticated"):
                return "Please login first", gr.update(visible=False), "Ask questions about your documents • 0 document(s) loaded • Using default model"
            
            user_id = user_state.get("user_id")
            if not user_id or user_id == "demo_user":
                return f"Demo mode: Would upload {len(files)} file(s)!", gr.update(visible=True), "Ask questions about your documents • 0 document(s) loaded • Using default model"
            
            try:
                db = next(get_db())
                try:
                    file_paths = [f.name for f in files if f]
                    success, kb_id = ingest_local_files(
                        file_paths=file_paths,
                        user_id=user_id,
                        db=db
                    )
                    if success:
                        status_update = update_status_text(user_state, db)
                        return f"Successfully uploaded {len(files)} file(s)!", gr.update(visible=True), status_update
                    else:
                        return "Upload failed. Please try again.", gr.update(visible=True), "Ask questions about your documents • 0 document(s) loaded • Using default model"
                finally:
                    db.close()
            except Exception as e:
                return f"Error: {str(e)}", gr.update(visible=True), "Ask questions about your documents • 0 document(s) loaded • Using default model"
        
        # Bind events
        google_btn.click(
            fn=lambda: handle_login("google"),
            outputs=[login_page, main_app, user_state, current_page, user_display]
        )
        
        microsoft_btn.click(
            fn=lambda: handle_login("microsoft"),
            outputs=[login_page, main_app, user_state, current_page, user_display]
        )
        
        chat_btn.click(
            fn=navigate_to_chat,
            inputs=[user_state],
            outputs=[chat_page, documents_page, settings_page, current_page, status_text]
        )
        
        documents_btn.click(
            fn=navigate_to_documents,
            outputs=[chat_page, documents_page, settings_page, current_page]
        )
        
        settings_btn.click(
            fn=navigate_to_settings,
            outputs=[chat_page, documents_page, settings_page, current_page]
        )
        
        logout_btn.click(
            fn=handle_logout,
            outputs=[login_page, main_app, user_state, current_page]
        )
        
        send_btn.click(
            fn=send_message,
            inputs=[query_input, chat_history, user_state],
            outputs=[chat_history, query_input, empty_state, chat_history]
        )
        
        query_input.submit(
            fn=send_message,
            inputs=[query_input, chat_history, user_state],
            outputs=[chat_history, query_input, empty_state, chat_history]
        )
        
        file_upload.change(
            fn=upload_files_handler,
            inputs=[file_upload, user_state],
            outputs=[upload_status, upload_status, status_text]
        )
        
        def connect_google_drive(folder_id, user_state):
            """Handle Google Drive connection."""
            if not user_state or not user_state.get("authenticated"):
                return "Please login first"
            user_id = user_state.get("user_id")
            if not user_id or user_id == "demo_user":
                return "Demo mode: Google Drive connection (not persisted)"
            try:
                db = next(get_db())
                try:
                    success, kb_id = ingest_google_drive(
                        folder_id=folder_id if folder_id else None,
                        user_id=user_id,
                        db=db
                    )
                    if success:
                        return f"Google Drive connected successfully! Knowledge base ID: {kb_id}"
                    else:
                        return "Failed to connect Google Drive. Please check your credentials."
                finally:
                    db.close()
            except Exception as e:
                return f"Error: {str(e)}"
        
        def connect_onedrive(folder_path, user_state):
            """Handle OneDrive connection."""
            if not user_state or not user_state.get("authenticated"):
                return "Please login first"
            user_id = user_state.get("user_id")
            if not user_id or user_id == "demo_user":
                return "Demo mode: OneDrive connection (not persisted)"
            return "OneDrive integration requires credential storage implementation"
        
        connect_drive_btn.click(
            fn=connect_google_drive,
            inputs=[drive_folder_input, user_state],
            outputs=[upload_status]
        )
        
        connect_onedrive_btn.click(
            fn=connect_onedrive,
            inputs=[onedrive_path_input, user_state],
            outputs=[upload_status]
        )
        
        # LLM Configuration save handlers
        def save_openai_config(api_key, model, temp, user_state):
            if not user_state or not user_state.get("authenticated"):
                return "Please login first"
            user_id = user_state.get("user_id")
            if not user_id or user_id == "demo_user":
                return "Demo mode: Configuration saved (not persisted)"
            
            try:
                db = next(get_db())
                try:
                    from app.services.llm_service import create_llm_config
                    config = create_llm_config(
                        db=db,
                        user_id=user_id,
                        provider="openai",
                        api_key=api_key,
                        model_name=model,
                        temperature=temp,
                        is_default=True
                    )
                    return "OpenAI configuration saved successfully!"
                finally:
                    db.close()
            except Exception as e:
                return f"Error: {str(e)}"
        
        openai_save.click(
            fn=save_openai_config,
            inputs=[openai_api_key, openai_model, openai_temp, user_state],
            outputs=[save_status]
        )
        
        # Similar handlers for other LLM providers
        def save_gemini_config(api_key, model, user_state):
            if not user_state or not user_state.get("authenticated"):
                return "Please login first"
            user_id = user_state.get("user_id")
            if not user_id or user_id == "demo_user":
                return "Demo mode: Configuration saved (not persisted)"
            try:
                db = next(get_db())
                try:
                    from app.services.llm_service import create_llm_config
                    create_llm_config(
                        db=db,
                        user_id=user_id,
                        provider="gemini",
                        api_key=api_key,
                        model_name=model,
                        is_default=True
                    )
                    return "Gemini configuration saved successfully!"
                finally:
                    db.close()
            except Exception as e:
                return f"Error: {str(e)}"
        
        def save_anthropic_config(api_key, model, user_state):
            if not user_state or not user_state.get("authenticated"):
                return "Please login first"
            user_id = user_state.get("user_id")
            if not user_id or user_id == "demo_user":
                return "Demo mode: Configuration saved (not persisted)"
            try:
                db = next(get_db())
                try:
                    from app.services.llm_service import create_llm_config
                    create_llm_config(
                        db=db,
                        user_id=user_id,
                        provider="anthropic",
                        api_key=api_key,
                        model_name=model,
                        is_default=True
                    )
                    return "Anthropic configuration saved successfully!"
                finally:
                    db.close()
            except Exception as e:
                return f"Error: {str(e)}"
        
        def save_local_config(base_url, model, user_state):
            if not user_state or not user_state.get("authenticated"):
                return "Please login first"
            user_id = user_state.get("user_id")
            if not user_id or user_id == "demo_user":
                return "Demo mode: Configuration saved (not persisted)"
            try:
                db = next(get_db())
                try:
                    from app.services.llm_service import create_llm_config
                    create_llm_config(
                        db=db,
                        user_id=user_id,
                        provider="local",
                        base_url=base_url,
                        model_name=model,
                        is_default=True
                    )
                    return "Local LLM configuration saved successfully!"
                finally:
                    db.close()
            except Exception as e:
                return f"Error: {str(e)}"
        
        gemini_save.click(
            fn=save_gemini_config,
            inputs=[gemini_api_key, gemini_model, user_state],
            outputs=[save_status]
        )
        
        anthropic_save.click(
            fn=save_anthropic_config,
            inputs=[anthropic_api_key, anthropic_model, user_state],
            outputs=[save_status]
        )
        
        local_save.click(
            fn=save_local_config,
            inputs=[local_base_url, local_model, user_state],
            outputs=[save_status]
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
            server_port=settings.gradio_port,
            share=False,
            inbrowser=False
        )
    
    thread = threading.Thread(target=launch_gradio, daemon=True)
    thread.start()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port
    )
