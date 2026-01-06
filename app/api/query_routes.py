from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import User
from app.models.base import get_db
from app.services.rag import ask_question
from app.services.auth_service import get_current_user
from app.helpers.logging_helper import ActivityLogger


class QueryRequest(BaseModel):
    query: str


router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query")
async def query(
    request_body: QueryRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_config_id: Optional[int] = None,
    use_rag: bool = True,
):
    """Query the RAG system (requires authentication)."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="rag_query",
        endpoint="/api/query",
        method="POST",
        user_id=current_user.id,
        metadata={"query": request_body.query, "use_rag": use_rag, "llm_config_id": llm_config_id}
    )
    try:
        result = ask_question(
            query=request_body.query,
            user_id=current_user.id,
            db=db,
            request=fastapi_request,
            llm_config_id=llm_config_id,
            use_rag=use_rag,
        )
        activity_logger.log_success({"answer_length": len(result.get("answer", "")) if isinstance(result, dict) else 0})
        return result
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


