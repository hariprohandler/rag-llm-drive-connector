"""RAG pipeline using LangChain and PgVector with multi-LLM support."""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_postgres import PGVector
# Use LangChain Expression Language (LCEL) for RAG - compatible with LangChain 0.1.0+
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
USE_NEW_API = True
from langchain_core.language_models.chat_models import BaseChatModel
from typing import List, Dict, Any, Optional
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import LLMConfig, UserSettings
from app.services.activity_logger import get_logger, get_client_ip, get_user_agent
from app.middleware.tracing import get_tracing_id
from app.helpers.vector_db_helper import get_collection_name, get_user_vector_db_url
import time


def get_user_collection_name(user_id: str, knowledge_base_id: Optional[int] = None) -> str:
    """
    Get collection name for a user.
    
    For better organization, we organize collections by knowledge base:
    - If knowledge_base_id is provided: user_{user_id}_kb_{kb_id}
    - Otherwise: user_{user_id}_documents (searches across all KBs)
    """
    return get_collection_name(user_id, knowledge_base_id)


def get_llm_from_config(llm_config: LLMConfig) -> BaseChatModel:
    """
    Create an LLM instance from user configuration.
    
    Args:
        llm_config: LLMConfig model instance
        
    Returns:
        BaseChatModel instance
    """
    provider = llm_config.provider.lower()
    temperature = float(llm_config.temperature) if llm_config.temperature else 0.0
    model_name = llm_config.model_name or "gpt-4o-mini"
    
    if provider == "openai":
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=llm_config.api_key,
            max_tokens=llm_config.max_tokens
        )
    elif provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model_name or "gemini-pro",
            temperature=temperature,
            google_api_key=llm_config.api_key,
            max_output_tokens=llm_config.max_tokens
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=model_name or "claude-3-opus-20240229",
            temperature=temperature,
            anthropic_api_key=llm_config.api_key,
            max_tokens=llm_config.max_tokens or 4096
        )
    elif provider == "custom":
        # For custom hosted LLMs, use OpenAI-compatible interface
        # Normalize base_url for Ollama and similar services
        base_url = llm_config.base_url
        if base_url:
            # Clean up the base URL
            base_url = base_url.strip().rstrip("/")
            
            # If base_url ends with /api/chat, convert to /v1 format for OpenAI-compatible API
            # LangChain's ChatOpenAI expects base_url to be the base (e.g., http://localhost:11434/v1)
            # and will append /chat/completions automatically
            if base_url.endswith("/api/chat"):
                # Convert http://localhost:11434/api/chat to http://localhost:11434/v1
                base_url = base_url.replace("/api/chat", "/v1")
            elif base_url.endswith("/api/chat/"):
                base_url = base_url.replace("/api/chat/", "/v1")
            elif not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
                # If it's just the base URL without /v1, add it
                # e.g., http://localhost:11434 -> http://localhost:11434/v1
                base_url = base_url + "/v1"
        else:
            # Default to Ollama if no base_url provided
            base_url = "http://localhost:11434/v1"
        
        # For Ollama, API key is often optional, but LangChain may require it
        # Use a dummy key if not provided or if it's empty
        # Note: api_key here is already decrypted (or empty string if decryption failed)
        api_key = llm_config.api_key
        if not api_key or api_key.strip() == "":
            api_key = "ollama"  # Dummy key for Ollama (not actually used)
        
        # For Ollama, the model name should match the actual model name (e.g., "llama3", "llama2", "mistral")
        # If model_name is not provided or is "custom", try to use a sensible default
        if not model_name or model_name.lower() == "custom":
            model_name = "llama3"  # Default Ollama model
        
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=api_key,
            base_url=base_url,
            max_tokens=llm_config.max_tokens,
            timeout=60.0  # Increase timeout for local models
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def get_vectorstore(
    collection_name: str,
    api_key: Optional[str] = None,
    db_url: Optional[str] = None
) -> PGVector:
    """
    Get or create a PgVector vectorstore.
    
    Args:
        collection_name: Collection name
        api_key: Optional API key for embeddings (defaults to config)
        db_url: Optional database URL (uses default from settings if not provided)
    """
    embeddings = OpenAIEmbeddings(
        openai_api_key=api_key or settings.openai_api_key
    )
    
    # Use provided DB URL or default from settings
    vector_db_url = db_url or settings.database_url
    
    vectorstore = PGVector(
        collection_name=collection_name,
        connection=vector_db_url,
        embeddings=embeddings,
        use_jsonb=True,  # Use JSONB for metadata as recommended
    )
    
    # Ensure tables are created with the correct schema (langchain_postgres uses uuid, not id)
    try:
        vectorstore.create_tables_if_not_exists()
    except Exception as e:
        # Table might already exist, continue anyway
        pass
    
    return vectorstore


def get_qa_chain(
    collection_name: str,
    llm: BaseChatModel,
    use_rag: bool = True,
    source_filter: Optional[str] = None,
    db_url: Optional[str] = None
):
    """
    Create a QA chain for querying documents.
    
    Args:
        collection_name: Collection name for vectorstore
        llm: LLM instance to use
        use_rag: Whether to use RAG (if False, just uses LLM without retrieval)
        source_filter: Optional source filter - 'document', 'zendesk', or None for 'all'
        db_url: Optional database URL (uses default from settings if not provided)
    """
    if use_rag:
        # Return retriever and LLM separately - we'll create the chain when needed
        vectorstore = get_vectorstore(collection_name, db_url=db_url)
        
        # Build filter based on source_filter
        # With JSONB metadata, use simple equality for filters (no $eq operator needed)
        # For "document" filter (not zendesk), we'll filter after retrieval
        if source_filter == "zendesk":
            # Increase retrieval for Zendesk to get more context (e.g., for "how many tickets" questions)
            # This ensures the LLM has access to more relevant Zendesk tickets for comprehensive answers
            search_kwargs = {
                "k": settings.retrieval_k * 5,  # Get 5x more documents (20 instead of 4) for better context
                "filter": {"source": "zendesk"}
            }
        elif source_filter == "document":
            search_kwargs = {"k": settings.retrieval_k * 2}
        else:
            # For "all" sources, use default retrieval_k
            search_kwargs = {"k": settings.retrieval_k}
        # For "document" filter, we'll handle filtering in ask_question after retrieval
        
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs=search_kwargs
        )
        return (retriever, llm), True
    else:
        # For non-RAG queries, we'll use the LLM directly
        # We'll create a simple chain that just passes the query
        return llm, False


def get_user_llm_config(
    db: Session,
    user_id: str,
    llm_config_id: Optional[int] = None
) -> Optional[LLMConfig]:
    """
    Get user's LLM configuration.
    
    Args:
        db: Database session
        user_id: User ID
        llm_config_id: Optional specific config ID, otherwise uses default
        
    Returns:
        LLMConfig instance or None
    """
    if llm_config_id:
        return db.query(LLMConfig).filter(
            LLMConfig.id == llm_config_id,
            LLMConfig.user_id == user_id,
            LLMConfig.is_active == True
        ).first()
    else:
        # Get default config
        return db.query(LLMConfig).filter(
            LLMConfig.user_id == user_id,
            LLMConfig.is_default == True,
            LLMConfig.is_active == True
        ).first()


def get_default_llm() -> BaseChatModel:
    """
    Get default LLM using system configuration.
    Falls back to OpenAI with system API key if available.
    """
    if settings.openai_api_key:
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            openai_api_key=settings.openai_api_key
        )
    else:
        # If no API key, raise an error - user must configure
        raise ValueError(
            "No LLM configuration found. Please configure an API key in settings "
            "or add a user-specific LLM configuration."
        )


def ask_question(
    query: str,
    user_id: str,
    db: Session,
    request: Optional[Request] = None,
    llm_config_id: Optional[int] = None,
    use_rag: bool = True,
    source_filter: Optional[str] = None,
    knowledge_base_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Ask a question using the RAG pipeline for a specific user.
    
    Args:
        query: The question to ask
        user_id: User ID (required for user-specific collections)
        db: Database session
        request: FastAPI Request object for logging IP and user agent
        llm_config_id: Optional LLM config ID to use
        use_rag: Whether to use RAG (default True)
        source_filter: Optional source filter - 'document', 'zendesk', or None for 'all'
        knowledge_base_id: Optional knowledge base ID to search within (searches all KBs if None)
        
    Returns:
        Dictionary with 'answer' and 'sources'
    """
    logger = get_logger()
    
    # Get user's vector DB configuration if available
    from app.models.user_settings import safe_query_user_settings
    user_settings = safe_query_user_settings(db, user_id)
    user_vector_db_url = get_user_vector_db_url(user_settings)
    
    # Use knowledge_base-specific collection if provided, otherwise search across all KBs
    collection_name = get_user_collection_name(user_id, knowledge_base_id)
    
    start_time = time.time()
    
    try:
        # Get user's LLM configuration
        llm_config = get_user_llm_config(db, user_id, llm_config_id)
        
        if not llm_config:
            # Fallback to default system config if no user config
            try:
                llm = get_default_llm()
            except ValueError as e:
                # If no default config available, return error
                raise HTTPException(
                    status_code=400,
                    detail=str(e)
                )
        else:
            from app.services.llm_service import decrypt_api_key
            # Decrypt API key for use
            decrypted_key = ""
            try:
                if llm_config.api_key:
                    decrypted_key = decrypt_api_key(llm_config.api_key)
            except (ValueError, Exception) as decrypt_error:
                # If decryption fails (e.g., encryption key changed)
                error_msg = str(decrypt_error)
                print(f"Warning: Failed to decrypt API key: {error_msg}")
                
                # For custom/self-hosted LLMs (like Ollama), API key is optional
                if llm_config.provider == "custom":
                    decrypted_key = ""  # Ollama doesn't require API key, use empty string
                    print("Using empty API key for custom/self-hosted LLM (Ollama)")
                else:
                    # For other providers (OpenAI, Gemini, Anthropic), API key is required
                    raise ValueError(
                        f"Failed to decrypt API key for {llm_config.provider}. "
                        f"This may happen if the encryption key changed. "
                        f"Please update your LLM configuration with a new API key. "
                        f"Original error: {error_msg}"
                    )
            # Create a temporary config with decrypted key
            import copy
            temp_config = copy.copy(llm_config)
            temp_config.api_key = decrypted_key
            llm = get_llm_from_config(temp_config)
        
        # Get retriever and LLM (pass user's vector DB URL)
        retriever_llm, is_rag = get_qa_chain(
            collection_name, llm, use_rag, 
            source_filter=source_filter,
            db_url=user_vector_db_url
        )
        
        if is_rag:
            retriever, llm = retriever_llm
            
            # Get source documents
            # In LangChain 0.1.0+, retrievers are callable directly (retriever(query))
            # Try calling directly first, then try other methods for compatibility
            try:
                # Try calling directly (most common in newer LangChain versions)
                source_docs = retriever(query)
            except (TypeError, AttributeError):
                try:
                    # Try invoke() method (some LangChain versions)
                    source_docs = retriever.invoke(query)
                except (AttributeError, TypeError):
                    # Fallback to get_relevant_documents for older versions
                    if hasattr(retriever, 'get_relevant_documents'):
                        source_docs = retriever.get_relevant_documents(query)
                    else:
                        raise AttributeError(
                            "Retriever does not support invoke(), direct call, or get_relevant_documents(). "
                            "Please check your LangChain version compatibility."
                        )
            
            # Apply source filter if needed (for "document" filter - exclude zendesk)
            if source_filter == "document":
                source_docs = [
                    doc for doc in source_docs 
                    if doc.metadata.get("source") != "zendesk"
                ][:settings.retrieval_k]  # Limit to retrieval_k after filtering
            
            # Format context from documents
            context = "\n\n".join(doc.page_content for doc in source_docs)
            
            # Create prompt and invoke LLM
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful assistant. Use the following context to answer the question. If you don't know the answer, say so.\n\nContext: {context}"),
                ("human", "{question}")
            ])
            
            chain = prompt | llm | StrOutputParser()
            answer = chain.invoke({"context": context, "question": query})
            
            sources = [
                {
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in source_docs
            ]
        else:
            # Direct LLM query without RAG
            response = llm.invoke(query)
            answer = response.content if hasattr(response, 'content') else str(response)
            sources = []
        
        response_time_ms = (time.time() - start_time) * 1000
        
        # Log successful query
        logger.log_query_activity(
            query=query,
            user_id=user_id,
            collection_name=collection_name if use_rag else None,
            answer=answer,
            status="success",
            metadata={
                "answer_length": len(answer),
                "num_sources": len(sources),
                "sources": [src.get("metadata", {}).get("file_name", "unknown") for src in sources] if sources else [],
                "use_rag": use_rag,
                "llm_provider": llm_config.provider if llm_config else "default",
                "source_filter": source_filter or "all"
            },
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            response_time_ms=response_time_ms,
            tracing_id=get_tracing_id(request) if request else None
        )
        
        return {
            "answer": answer,
            "sources": sources,
            "use_rag": use_rag
        }
    except Exception as e:
        import traceback
        response_time_ms = (time.time() - start_time) * 1000
        
        # Get full error details
        error_message = str(e)
        error_traceback = traceback.format_exc()
        
        # Log failed query with full details
        print(f"RAG Error: {error_message}")
        print(f"RAG Traceback: {error_traceback}")
        
        logger.log_query_activity(
            query=query,
            user_id=user_id,
            collection_name=collection_name if use_rag else None,
            status="failure",
            error=error_message,
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            response_time_ms=response_time_ms,
            tracing_id=get_tracing_id(request) if request else None
        )
        
        # Re-raise with more context
        raise Exception(f"RAG query failed: {error_message}") from e
