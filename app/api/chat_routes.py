from typing import Optional, AsyncGenerator
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import User
from app.models.base import get_db
from app.services.chat_service import (
    create_conversation,
    get_conversations,
    get_conversation,
    update_conversation,
    delete_conversation,
    add_message,
    get_messages,
)
from app.services.rag import ask_question
from app.services.auth_service import get_current_user
from app.services.sql_agent_service import is_sql_query, execute_sql_query, get_best_sql_model
from app.models import DatabaseConnection, LLMConfig
from app.services.rag import get_llm_from_config
from app.helpers.logging_helper import ActivityLogger


class ChatMessageRequest(BaseModel):
    content: str
    conversation_id: Optional[int] = None
    use_rag: bool = True
    llm_config_id: Optional[int] = None
    source_filter: Optional[str] = None  # 'all', 'document', 'zendesk'
    database_connection_id: Optional[int] = None  # Database connection to use for SQL queries


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


router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/conversations")
async def create_chat_conversation(
    fastapi_request: Request,
    request: ConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new chat conversation."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="conversation_create",
        endpoint="/api/chat/conversations",
        method="POST",
        user_id=current_user.id,
        metadata={"title": request.title, "is_private": request.is_private}
    )
    try:
        conversation = create_conversation(
            db=db,
            user_id=current_user.id,
            title=request.title,
            is_private=request.is_private,
            llm_config_id=request.llm_config_id,
            use_rag=request.use_rag,
        )
        activity_logger.log_success({"conversation_id": conversation.id})
        return conversation.to_dict()
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_chat_conversations(
    is_private: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all chat conversations for the current user."""
    conversations = get_conversations(db, current_user.id, is_private)
    return [conv.to_dict() for conv in conversations]


@router.get("/conversations/{conversation_id}")
async def get_chat_conversation_endpoint(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific chat conversation with messages."""
    conversation = get_conversation(db, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = conversation.to_dict()
    messages = get_messages(db, conversation_id)
    result["messages"] = [msg.to_dict() for msg in messages]
    return result


@router.put("/conversations/{conversation_id}")
async def update_chat_conversation(
    conversation_id: int,
    request: ConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a chat conversation."""
    conversation = update_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        title=request.title,
        is_private=request.is_private,
        llm_config_id=request.llm_config_id,
        use_rag=request.use_rag,
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation.to_dict()


@router.delete("/conversations/{conversation_id}")
async def delete_chat_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a chat conversation."""
    success = delete_conversation(db, current_user.id, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "message": "Conversation deleted"}


async def stream_chat_response(
    query: str,
    user_id: str,
    conversation_id: int,
    db: Session,
    fastapi_request: Request,
    llm_config_id: Optional[int] = None,
    use_rag: bool = True,
    source_filter: Optional[str] = None,
    database_connection_id: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """Stream chat response as Server-Sent Events."""
    from app.services.rag_streaming import stream_question
    
    # Check if this is a SQL query and we have a database connection
    # If database_connection_id is provided, use it (user explicitly selected a database)
    # Only use SQL if the query looks like a SQL query
    if database_connection_id and is_sql_query(query):
        # Handle SQL query with streaming
        activity_logger = None
        try:
            from app.models import DatabaseConnection, LLMConfig
            from app.services.rag import get_llm_from_config
            from app.helpers.logging_helper import ActivityLogger
            
            # Log SQL query execution
            activity_logger = ActivityLogger(
                request=fastapi_request,
                activity_type="sql_query_chat",
                endpoint="/api/chat/messages",
                method="POST",
                user_id=user_id,
                metadata={
                    "conversation_id": conversation_id,
                    "database_connection_id": database_connection_id,
                    "query": query
                }
            )
            
            # Get database connection
            db_conn = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == database_connection_id,
                DatabaseConnection.user_id == user_id
            ).first()
            
            if db_conn:
                # Get LLM config
                if llm_config_id:
                    llm_config = db.query(LLMConfig).filter(
                        LLMConfig.id == llm_config_id,
                        LLMConfig.user_id == user_id,
                        LLMConfig.is_active == True
                    ).first()
                else:
                    llm_config = db.query(LLMConfig).filter(
                        LLMConfig.user_id == user_id,
                        LLMConfig.is_default == True,
                        LLMConfig.is_active == True
                    ).first()
                
                if llm_config:
                    # Get best SQL model
                    all_llm_configs = db.query(LLMConfig).filter(
                        LLMConfig.user_id == user_id,
                        LLMConfig.is_active == True
                    ).all()
                    default_llm = get_llm_from_config(llm_config)
                    sql_llm = get_best_sql_model(all_llm_configs, default_llm)
                    
                    # Execute SQL query (non-streaming for now, but we can stream the result)
                    result = execute_sql_query(
                        query=query,
                        connection_string=db_conn.connection_string,
                        db_type=db_conn.db_type,
                        llm=sql_llm,
                        schema_info=db_conn.schema_info
                    )
                    
                    # Log SQL query result
                    if activity_logger:
                        activity_logger.log_success({
                            "sql_query": result.get("sql_query", ""),
                            "has_error": "error" in result,
                            "answer_length": len(result.get("answer", ""))
                        })
                    
                    # Stream the answer token by token (simulate streaming)
                    answer = result.get("answer", "")
                    for char in answer:
                        yield f"data: {json.dumps({'type': 'token', 'content': char})}\n\n"
                    
                    # Send sources
                    sources = result.get("sources", [])
                    if result.get("sql_query"):
                        sources.append({
                            "type": "sql",
                            "query": result.get("sql_query", ""),
                            "database": db_conn.name
                        })
                    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
                    
                    # Send done
                    yield f"data: {json.dumps({'type': 'done', 'answer': answer, 'sources': sources, 'sql_query': result.get('sql_query', '')})}\n\n"
                    return
        except Exception as e:
            # Log SQL query error if activity_logger was created
            if activity_logger:
                activity_logger.log_error(f"SQL query error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': f'SQL query error: {str(e)}'})}\n\n"
            return
    
    # Default to RAG streaming
    try:
        full_answer = ""
        sources = []
        
        async for chunk in stream_question(
            query=query,
            user_id=user_id,
            db=db,
            request=fastapi_request,
            llm_config_id=llm_config_id,
            use_rag=use_rag,
            source_filter=source_filter,
        ):
            if chunk.get("type") == "token":
                # Stream token to client
                full_answer += chunk.get("content", "")
                yield f"data: {json.dumps({'type': 'token', 'content': chunk.get('content', '')})}\n\n"
            elif chunk.get("type") == "sources":
                # Send sources when available
                sources = chunk.get("sources", [])
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            elif chunk.get("type") == "done":
                # Final message with full answer and sources
                yield f"data: {json.dumps({'type': 'done', 'answer': full_answer, 'sources': sources})}\n\n"
            elif chunk.get("type") == "error":
                # Send error
                yield f"data: {json.dumps({'type': 'error', 'error': chunk.get('error', 'Unknown error')})}\n\n"
                break
                
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


@router.post("/messages")
async def send_chat_message(
    request: ChatMessageRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message in a chat conversation with streaming support."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="chat_message",
        endpoint="/api/chat/messages",
        method="POST",
        user_id=current_user.id,
        metadata={"conversation_id": request.conversation_id, "use_rag": request.use_rag, "content_length": len(request.content)}
    )
    
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
                use_rag=request.use_rag,
            )

        # Add user message
        user_message = add_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=request.content,
        )

        # Check if query is SQL-related and user has database connections
        should_use_sql = False
        database_connection_id = None
        
        # Use provided database_connection_id if available, otherwise auto-detect
        if request.database_connection_id:
            # Validate that the provided connection belongs to the user
            db_conn = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == request.database_connection_id,
                DatabaseConnection.user_id == current_user.id,
                DatabaseConnection.is_active == True
            ).first()
            if db_conn:
                database_connection_id = request.database_connection_id
                # If user explicitly selected a database, use it for SQL queries
                # Check if query looks like SQL query (user selected DB, so likely wants SQL)
                should_use_sql = is_sql_query(request.content)
        elif is_sql_query(request.content):
            # Auto-detect: Check if user has active database connections
            db_connections = db.query(DatabaseConnection).filter(
                DatabaseConnection.user_id == current_user.id,
                DatabaseConnection.is_active == True
            ).all()
            
            if db_connections:
                # Use the first active connection if user didn't specify
                database_connection_id = db_connections[0].id
                should_use_sql = True

        # Check if client wants streaming (via query parameter or header)
        stream = fastapi_request.query_params.get("stream", "true").lower() == "true"
        
        # If SQL query and streaming is disabled, execute SQL directly
        if should_use_sql and not stream:
            # Get LLM config
            if conversation.llm_config_id or request.llm_config_id:
                llm_config_id = conversation.llm_config_id or request.llm_config_id
                llm_config = db.query(LLMConfig).filter(
                    LLMConfig.id == llm_config_id,
                    LLMConfig.user_id == current_user.id,
                    LLMConfig.is_active == True
                ).first()
            else:
                llm_config = db.query(LLMConfig).filter(
                    LLMConfig.user_id == current_user.id,
                    LLMConfig.is_default == True,
                    LLMConfig.is_active == True
                ).first()
            
            if not llm_config:
                raise HTTPException(status_code=404, detail="LLM configuration not found")
            
            # Get best SQL model
            all_llm_configs = db.query(LLMConfig).filter(
                LLMConfig.user_id == current_user.id,
                LLMConfig.is_active == True
            ).all()
            default_llm = get_llm_from_config(llm_config)
            sql_llm = get_best_sql_model(all_llm_configs, default_llm)
            
            # Get database connection
            db_conn = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == database_connection_id,
                DatabaseConnection.user_id == current_user.id
            ).first()
            
            if db_conn:
                # Execute SQL query
                result = execute_sql_query(
                    query=request.content,
                    connection_string=db_conn.connection_string,
                    db_type=db_conn.db_type,
                    llm=sql_llm,
                    schema_info=db_conn.schema_info
                )
                
                # Add assistant message
                assistant_message = add_message(
                    db=db,
                    conversation_id=conversation.id,
                    role="assistant",
                    content=result.get("answer", ""),
                    metadata={
                        "sources": result.get("sources", []),
                        "sql_query": result.get("sql_query", ""),
                        "use_sql": True,
                    },
                )
                
                activity_logger.log_success({
                    "conversation_id": conversation.id,
                    "answer_length": len(result.get("answer", "")),
                    "use_sql": True,
                    "database_connection_id": database_connection_id,
                    "sql_query": result.get("sql_query", ""),
                    "has_error": "error" in result
                })
                
                return {
                    "conversation_id": conversation.id,
                    "message_id": assistant_message.id,
                    "answer": result.get("answer", ""),
                    "sources": result.get("sources", []),
                    "sql_query": result.get("sql_query", ""),
                    "use_sql": True,
                }
        
        if stream:
            # Return streaming response
            async def generate_stream():
                full_answer = ""
                sources = []
                async for sse_chunk in stream_chat_response(
                    query=request.content,
                    user_id=current_user.id,
                    conversation_id=conversation.id,
                    db=db,
                    fastapi_request=fastapi_request,
                    llm_config_id=conversation.llm_config_id or request.llm_config_id,
                    use_rag=request.use_rag if request.use_rag is not None else (conversation.use_rag if request.conversation_id else False),
                    source_filter=request.source_filter,
                    database_connection_id=request.database_connection_id or (database_connection_id if should_use_sql else None),
                ):
                    # Parse SSE format: "data: {...}\n\n"
                    try:
                        # Extract JSON from SSE format
                        if sse_chunk.startswith("data: "):
                            json_str = sse_chunk[6:].strip()  # Remove "data: " and newlines
                            chunk = json.loads(json_str)
                        else:
                            # If not in SSE format, try to parse as JSON directly
                            chunk = json.loads(sse_chunk.strip())
                    except (json.JSONDecodeError, AttributeError, TypeError) as e:
                        # If parsing fails, yield the chunk as-is and continue
                        yield sse_chunk
                        continue
                    
                    # Process the parsed chunk
                    chunk_type = chunk.get("type") if isinstance(chunk, dict) else None
                    
                    if chunk_type == "token":
                        content = chunk.get("content", "")
                        full_answer += content
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                    elif chunk_type == "sources":
                        sources = chunk.get("sources", [])
                        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
                    elif chunk_type == "done":
                        # Update full_answer from chunk if provided
                        if "answer" in chunk:
                            full_answer = chunk.get("answer", full_answer)
                        if "sources" in chunk:
                            sources = chunk.get("sources", sources)
                        
                        # Save assistant message after streaming completes
                        assistant_message = add_message(
                            db=db,
                            conversation_id=conversation.id,
                            role="assistant",
                            content=full_answer,
                            metadata={
                                "sources": sources,
                                "use_rag": request.use_rag if request.use_rag is not None else (conversation.use_rag if request.conversation_id else False),
                            },
                        )
                        activity_logger.log_success({
                            "conversation_id": conversation.id,
                            "answer_length": len(full_answer),
                            "sources_count": len(sources)
                        })
                        yield f"data: {json.dumps({'type': 'done', 'answer': full_answer, 'sources': sources, 'conversation_id': conversation.id, 'assistant_message_id': assistant_message.id})}\n\n"
                    elif chunk_type == "error":
                        yield f"data: {json.dumps({'type': 'error', 'error': chunk.get('error', 'Unknown error')})}\n\n"
                        break
                    else:
                        # Unknown chunk type, yield as-is
                        yield sse_chunk
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                }
            )
        else:
            # Non-streaming fallback (for compatibility)
            use_rag = request.use_rag if request.use_rag is not None else (conversation.use_rag if request.conversation_id else False)
            
            from app.services.rag import ask_question
            result = ask_question(
                query=request.content,
                user_id=current_user.id,
                db=db,
                request=fastapi_request,
                llm_config_id=conversation.llm_config_id or request.llm_config_id,
                use_rag=use_rag,
                source_filter=request.source_filter,
            )

            # Add assistant message
            assistant_message = add_message(
                db=db,
                conversation_id=conversation.id,
                role="assistant",
                content=result["answer"],
                metadata={
                    "sources": result.get("sources", []),
                    "use_rag": result.get("use_rag", False),
                },
            )

            activity_logger.log_success({
                "conversation_id": conversation.id,
                "answer_length": len(result.get("answer", "")),
                "sources_count": len(result.get("sources", []))
            })
            return {
                "conversation_id": conversation.id,
                "user_message": user_message.to_dict(),
                "assistant_message": assistant_message.to_dict(),
                "sources": result.get("sources", []),
            }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e)
        error_traceback = traceback.format_exc()
        print(f"Error in chat message: {error_detail}")
        print(f"Traceback: {error_traceback}")
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/conversations/{conversation_id}/messages")
async def get_chat_messages(
    conversation_id: int,
    limit: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get messages for a conversation."""
    conversation = get_conversation(db, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = get_messages(db, conversation_id, limit)
    return [msg.to_dict() for msg in messages]


