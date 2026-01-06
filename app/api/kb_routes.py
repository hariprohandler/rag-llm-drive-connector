from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models import User, KnowledgeBase
from app.models.base import get_db
from auth_service import get_current_user


router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


@router.get("")
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all knowledge bases for the current user."""
    kbs = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.user_id == current_user.id,
            KnowledgeBase.is_active == True,  # noqa: E712
        )
        .all()
    )
    return [kb.to_dict() for kb in kbs]


@router.get("/{kb_id}")
async def get_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific knowledge base."""
    kb = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id,
        )
        .first()
    )
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb.to_dict()


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft delete a knowledge base."""
    kb = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id,
        )
        .first()
    )
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    kb.is_active = False
    db.commit()
    return {"status": "success", "message": "Knowledge base deleted"}


