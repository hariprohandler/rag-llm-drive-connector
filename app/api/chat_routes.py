from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
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
from auth_service import get_current_user


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


router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/conversations")
async def create_chat_conversation(
    request: ConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new chat conversation."""
    conversation = create_conversation(
        db=db,
        user_id=current_user.id,
        title=request.title,
        is_private=request.is_private,
        llm_config_id=request.llm_config_id,
        use_rag=request.use_rag,
    )
    return conversation.to_dict()


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


@router.post("/messages")
async def send_chat_message(
    request: ChatMessageRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
                use_rag=request.use_rag,
            )

        # Add user message
        user_message = add_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=request.content,
        )

        # Get assistant response
        result = ask_question(
            query=request.content,
            user_id=current_user.id,
            db=db,
            request=fastapi_request,
            llm_config_id=conversation.llm_config_id or request.llm_config_id,
            use_rag=conversation.use_rag if request.conversation_id else request.use_rag,
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

        return {
            "conversation_id": conversation.id,
            "user_message": user_message.to_dict(),
            "assistant_message": assistant_message.to_dict(),
            "sources": result.get("sources", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


