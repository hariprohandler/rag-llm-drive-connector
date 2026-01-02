"""RAG pipeline using LangChain and PgVector."""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain.chains import RetrievalQA
from typing import List, Dict, Any, Optional
from fastapi import Request
import config
from activity_logger import get_logger, get_client_ip, get_user_agent
import time


def get_user_collection_name(user_id: str) -> str:
    """Get collection name for a user."""
    return f"user_{user_id}_documents"


def get_vectorstore(collection_name: str) -> PGVector:
    """Get or create a PgVector vectorstore."""
    embeddings = OpenAIEmbeddings(openai_api_key=config.settings.openai_api_key)
    
    vectorstore = PGVector(
        collection_name=collection_name,
        connection_string=config.settings.database_url,
        embedding_function=embeddings,
    )
    return vectorstore


def get_qa_chain(collection_name: str):
    """Create a QA chain for querying documents."""
    vectorstore = get_vectorstore(collection_name)
    
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": config.settings.retrieval_k}
    )
    
    llm = ChatOpenAI(
        model=config.settings.llm_model,
        temperature=config.settings.llm_temperature,
        openai_api_key=config.settings.openai_api_key
    )
    
    qa = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        return_source_documents=True
    )
    
    return qa


def ask_question(query: str, user_id: str, request: Optional[Request] = None) -> Dict[str, Any]:
    """
    Ask a question using the RAG pipeline for a specific user.
    
    Args:
        query: The question to ask
        user_id: User ID (required for user-specific collections)
        request: FastAPI Request object for logging IP and user agent
        
    Returns:
        Dictionary with 'answer' and 'sources'
    """
    logger = get_logger()
    collection_name = get_user_collection_name(user_id)
    start_time = time.time()
    
    try:
        qa = get_qa_chain(collection_name)
        result = qa({"query": query})
        
        answer = result["result"]
        sources = [
            {
                "content": doc.page_content[:200] + "...",
                "metadata": doc.metadata
            }
            for doc in result.get("source_documents", [])
        ]
        
        response_time_ms = (time.time() - start_time) * 1000
        
        # Log successful query
        logger.log_query_activity(
            query=query,
            user_id=user_id,
            collection_name=collection_name,
            answer=answer,
            status="success",
            metadata={
                "answer_length": len(answer),
                "num_sources": len(sources),
                "sources": [src.get("metadata", {}).get("file_name", "unknown") for src in sources]
            },
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            response_time_ms=response_time_ms
        )
        
        return {
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        
        # Log failed query
        logger.log_query_activity(
            query=query,
            user_id=user_id,
            collection_name=collection_name,
            status="failure",
            error=str(e),
            ip_address=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            response_time_ms=response_time_ms
        )
        raise
