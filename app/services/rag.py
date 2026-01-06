"""RAG pipeline using LangChain and PgVector with multi-LLM support."""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_community.vectorstores.pgvector import PGVector
from langchain.chains import RetrievalQA
from langchain_core.language_models.chat_models import BaseChatModel
from typing import List, Dict, Any, Optional
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import LLMConfig
from activity_logger import get_logger, get_client_ip, get_user_agent
import time


def get_user_collection_name(user_id: str) -> str:
    """Get collection name for a user."""
    return f"user_{user_id}_documents"


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
        return ChatOpenAI(
            model=model_name or "gpt-3.5-turbo",
            temperature=temperature,
            openai_api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            max_tokens=llm_config.max_tokens
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def get_vectorstore(collection_name: str, api_key: Optional[str] = None) -> PGVector:
    """
    Get or create a PgVector vectorstore.
    
    Args:
        collection_name: Collection name
        api_key: Optional API key for embeddings (defaults to config)
    """
    embeddings = OpenAIEmbeddings(
        openai_api_key=api_key or settings.openai_api_key
    )
    
    vectorstore = PGVector(
        collection_name=collection_name,
        connection_string=settings.database_url,
        embedding_function=embeddings,
    )
    return vectorstore


def get_qa_chain(
    collection_name: str,
    llm: BaseChatModel,
    use_rag: bool = True
):
    """
    Create a QA chain for querying documents.
    
    Args:
        collection_name: Collection name for vectorstore
        llm: LLM instance to use
        use_rag: Whether to use RAG (if False, just uses LLM without retrieval)
    """
    if use_rag:
        vectorstore = get_vectorstore(collection_name)
        
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": settings.retrieval_k}
        )
        
        qa = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=retriever,
            chain_type="stuff",
            return_source_documents=True
        )
        
        return qa, True
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
    use_rag: bool = True
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
        
    Returns:
        Dictionary with 'answer' and 'sources'
    """
    logger = get_logger()
    collection_name = get_user_collection_name(user_id)
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
            decrypted_key = decrypt_api_key(llm_config.api_key)
            # Create a temporary config with decrypted key
            import copy
            temp_config = copy.copy(llm_config)
            temp_config.api_key = decrypted_key
            llm = get_llm_from_config(temp_config)
        
        # Get QA chain
        qa_chain, is_rag = get_qa_chain(collection_name, llm, use_rag)
        
        if is_rag:
            result = qa_chain({"query": query})
            answer = result["result"]
            sources = [
                {
                    "content": doc.page_content[:200] + "...",
                    "metadata": doc.metadata
                }
                for doc in result.get("source_documents", [])
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
                "llm_provider": llm_config.provider if llm_config else "default"
            },
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            response_time_ms=response_time_ms
        )
        
        return {
            "answer": answer,
            "sources": sources,
            "use_rag": use_rag
        }
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        
        # Log failed query
        logger.log_query_activity(
            query=query,
            user_id=user_id,
            collection_name=collection_name if use_rag else None,
            status="failure",
            error=str(e),
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            response_time_ms=response_time_ms
        )
        raise
