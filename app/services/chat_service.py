"""Service for managing chat conversations and messages."""
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models import ChatConversation, ChatMessage


def create_conversation(
    db: Session,
    user_id: str,
    title: Optional[str] = None,
    is_private: bool = True,
    llm_config_id: Optional[int] = None,
    use_rag: bool = True
) -> ChatConversation:
    """
    Create a new chat conversation.
    
    Args:
        db: Database session
        user_id: User ID
        title: Optional conversation title
        is_private: Whether conversation is private
        llm_config_id: Optional LLM config ID
        use_rag: Whether to use RAG
        
    Returns:
        Created ChatConversation instance
    """
    conversation = ChatConversation(
        user_id=user_id,
        title=title,
        is_private=is_private,
        llm_config_id=llm_config_id,
        use_rag=use_rag
    )
    
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    return conversation


def get_conversations(
    db: Session,
    user_id: str,
    is_private: Optional[bool] = None
) -> List[ChatConversation]:
    """
    Get conversations for a user.
    
    Args:
        db: Database session
        user_id: User ID
        is_private: Optional filter by privacy (None = all)
    """
    query = db.query(ChatConversation).filter(
        ChatConversation.user_id == user_id
    )
    
    if is_private is not None:
        query = query.filter(ChatConversation.is_private == is_private)
    
    return query.order_by(ChatConversation.updated_at.desc()).all()


def get_conversation(
    db: Session,
    user_id: str,
    conversation_id: int
) -> Optional[ChatConversation]:
    """Get a specific conversation."""
    return db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == user_id
    ).first()


def update_conversation(
    db: Session,
    user_id: str,
    conversation_id: int,
    title: Optional[str] = None,
    is_private: Optional[bool] = None,
    llm_config_id: Optional[int] = None,
    use_rag: Optional[bool] = None
) -> Optional[ChatConversation]:
    """Update a conversation."""
    conversation = get_conversation(db, user_id, conversation_id)
    if not conversation:
        return None
    
    if title is not None:
        conversation.title = title
    if is_private is not None:
        conversation.is_private = is_private
    if llm_config_id is not None:
        conversation.llm_config_id = llm_config_id
    if use_rag is not None:
        conversation.use_rag = use_rag
    
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)
    
    return conversation


def delete_conversation(db: Session, user_id: str, conversation_id: int) -> bool:
    """Delete a conversation (cascade deletes messages)."""
    conversation = get_conversation(db, user_id, conversation_id)
    if not conversation:
        return False
    
    db.delete(conversation)
    db.commit()
    
    return True


def add_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> ChatMessage:
    """
    Add a message to a conversation.
    
    Args:
        db: Database session
        conversation_id: Conversation ID
        role: Message role ('user' or 'assistant')
        content: Message content
        metadata: Optional metadata (sources, tokens, etc.)
        
    Returns:
        Created ChatMessage instance
    """
    message = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        message_metadata=metadata
    )
    
    db.add(message)
    
    # Update conversation timestamp
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id
    ).first()
    if conversation:
        conversation.updated_at = datetime.utcnow()
        # Auto-generate title from first user message if not set
        if not conversation.title and role == "user":
            conversation.title = content[:50] + ("..." if len(content) > 50 else "")
    
    db.commit()
    db.refresh(message)
    
    return message


def get_messages(
    db: Session,
    conversation_id: int,
    limit: Optional[int] = None
) -> List[ChatMessage]:
    """Get messages for a conversation."""
    query = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(ChatMessage.created_at.asc())
    
    if limit:
        query = query.limit(limit)
    
    return query.all()

