"""Streaming RAG pipeline for real-time chat responses."""
from typing import AsyncGenerator, Optional, Dict, Any
import asyncio
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.services.rag import (
    get_user_collection_name,
    get_user_llm_config,
    get_default_llm,
    get_llm_from_config,
    get_qa_chain,
    get_logger,
    get_client_ip,
    get_user_agent,
)
from app.core.config import settings
from app.services.llm_service import decrypt_api_key
from app.middleware.tracing import get_tracing_id
import time


async def stream_question(
    query: str,
    user_id: str,
    db: Session,
    request: Optional[Request] = None,
    llm_config_id: Optional[int] = None,
    use_rag: bool = True,
    source_filter: Optional[str] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream a question response using the RAG pipeline.
    
    Yields:
        Dictionary with 'type' ('token', 'sources', 'done', 'error') and relevant data
    """
    logger = get_logger()
    collection_name = get_user_collection_name(user_id)
    start_time = time.time()
    
    try:
        # Get user's LLM configuration
        llm_config = get_user_llm_config(db, user_id, llm_config_id)
        
        if not llm_config:
            try:
                llm = get_default_llm()
            except ValueError as e:
                yield {"type": "error", "error": str(e)}
                return
        else:
            from app.services.llm_service import decrypt_api_key
            decrypted_key = ""
            try:
                if llm_config.api_key:
                    decrypted_key = decrypt_api_key(llm_config.api_key)
            except (ValueError, Exception) as decrypt_error:
                error_msg = str(decrypt_error)
                if llm_config.provider == "custom":
                    decrypted_key = ""
                else:
                    yield {"type": "error", "error": f"Failed to decrypt API key: {error_msg}"}
                    return
            
            import copy
            temp_config = copy.copy(llm_config)
            temp_config.api_key = decrypted_key
            llm = get_llm_from_config(temp_config)
        
        # Get retriever and LLM
        retriever_llm, is_rag = get_qa_chain(collection_name, llm, use_rag, source_filter=source_filter)
        
        if is_rag:
            retriever, llm = retriever_llm
            
            # Get source documents
            try:
                source_docs = retriever(query)
            except (TypeError, AttributeError):
                try:
                    source_docs = retriever.invoke(query)
                except (AttributeError, TypeError):
                    if hasattr(retriever, 'get_relevant_documents'):
                        source_docs = retriever.get_relevant_documents(query)
                    else:
                        yield {"type": "error", "error": "Retriever not compatible"}
                        return
            
            # Apply source filter if needed
            if source_filter == "document":
                source_docs = [
                    doc for doc in source_docs 
                    if doc.metadata.get("source") != "zendesk"
                ][:settings.retrieval_k]
            
            # Format context from documents
            context = "\n\n".join(doc.page_content for doc in source_docs)
            
            # Send sources first
            sources = [
                {
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in source_docs
            ]
            yield {"type": "sources", "sources": sources}
            
            # Create prompt and stream LLM response
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful assistant. Use the following context to answer the question. If you don't know the answer, say so.\n\nContext: {context}"),
                ("human", "{question}")
            ])
            
            chain = prompt | llm | StrOutputParser()
            
            # Stream the response - use async streaming (native for async generators)
            full_answer = ""
            try:
                # Use async streaming (preferred for async generators)
                async for chunk in chain.astream({"context": context, "question": query}):
                    full_answer += chunk
                    yield {"type": "token", "content": chunk}
            except (AttributeError, TypeError):
                # Fallback: run sync stream in executor
                try:
                    import concurrent.futures
                    loop = asyncio.get_event_loop()
                    
                    def sync_stream():
                        result = []
                        for chunk in chain.stream({"context": context, "question": query}):
                            result.append(chunk)
                        return result
                    
                    # Run sync stream in thread pool
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        chunks = await loop.run_in_executor(executor, sync_stream)
                        for chunk in chunks:
                            full_answer += chunk
                            yield {"type": "token", "content": chunk}
                except Exception:
                    # Last resort: invoke and yield in chunks (simulated streaming)
                    answer = chain.invoke({"context": context, "question": query})
                    # Simulate streaming by yielding in chunks for better UX
                    chunk_size = 5
                    for i in range(0, len(answer), chunk_size):
                        chunk = answer[i:i+chunk_size]
                        full_answer += chunk
                        yield {"type": "token", "content": chunk}
                        await asyncio.sleep(0.01)  # Small delay for smoother UX
            
            # Log successful query
            response_time_ms = (time.time() - start_time) * 1000
            logger.log_query_activity(
                query=query,
                user_id=user_id,
                collection_name=collection_name,
                answer=full_answer,
                status="success",
                metadata={
                    "answer_length": len(full_answer),
                    "num_sources": len(sources),
                    "use_rag": use_rag,
                    "llm_provider": llm_config.provider if llm_config else "default",
                    "source_filter": source_filter or "all"
                },
                ip_address=get_client_ip(request) if request else None,
                user_agent=get_user_agent(request) if request else None,
                response_time_ms=response_time_ms,
                tracing_id=get_tracing_id(request) if request else None
            )
            
            yield {"type": "done", "answer": full_answer, "sources": sources}
            
        else:
            # Direct LLM query without RAG - stream response
            full_answer = ""
            try:
                # Use async streaming (preferred)
                async for chunk in llm.astream(query):
                    content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_answer += content
                    yield {"type": "token", "content": content}
            except (AttributeError, TypeError):
                # Fallback: run sync stream in executor
                try:
                    import concurrent.futures
                    loop = asyncio.get_event_loop()
                    
                    def sync_llm_stream():
                        result = []
                        for chunk in llm.stream(query):
                            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                            result.append(content)
                        return result
                    
                    # Run sync stream in thread pool
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        chunks = await loop.run_in_executor(executor, sync_llm_stream)
                        for content in chunks:
                            full_answer += content
                            yield {"type": "token", "content": content}
                except Exception:
                    # Last resort: invoke and yield in chunks (simulated streaming)
                    response = llm.invoke(query)
                    answer = response.content if hasattr(response, 'content') else str(response)
                    chunk_size = 5
                    for i in range(0, len(answer), chunk_size):
                        chunk = answer[i:i+chunk_size]
                        full_answer += chunk
                        yield {"type": "token", "content": chunk}
                        await asyncio.sleep(0.01)  # Small delay for smoother UX
            
            response_time_ms = (time.time() - start_time) * 1000
            logger.log_query_activity(
                query=query,
                user_id=user_id,
                collection_name=None,
                answer=full_answer,
                status="success",
                metadata={
                    "answer_length": len(full_answer),
                    "use_rag": False,
                    "llm_provider": llm_config.provider if llm_config else "default"
                },
                ip_address=get_client_ip(request) if request else None,
                user_agent=get_user_agent(request) if request else None,
                response_time_ms=response_time_ms,
                tracing_id=get_tracing_id(request) if request else None
            )
            
            yield {"type": "done", "answer": full_answer, "sources": []}
            
    except Exception as e:
        import traceback
        response_time_ms = (time.time() - start_time) * 1000
        error_message = str(e)
        error_traceback = traceback.format_exc()
        
        print(f"RAG Streaming Error: {error_message}")
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
        
        yield {"type": "error", "error": error_message}

