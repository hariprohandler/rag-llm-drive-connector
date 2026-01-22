from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.models import User, KnowledgeBase
from app.models.base import get_db
from app.models.knowledge_base import safe_query_knowledge_bases
from app.services.auth_service import get_current_user
from app.helpers.logging_helper import ActivityLogger


router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


@router.get("")
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all knowledge bases for the current user."""
    try:
        kbs = safe_query_knowledge_bases(
            db,
            {
                "user_id": current_user.id,
                "is_active": True
            }
        )
    except Exception as e:
        # Fallback to direct query if safe_query fails
        db.rollback()
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
    fastapi_request: Request,
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft delete a knowledge base."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="kb_delete",
        endpoint=f"/api/knowledge-bases/{kb_id}",
        method="DELETE",
        user_id=current_user.id,
        metadata={"kb_id": kb_id}
    )
    try:
        kb = (
            db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.user_id == current_user.id,
            )
            .first()
        )
        if not kb:
            activity_logger.log_error("Knowledge base not found", 404)
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        kb.is_active = False
        db.commit()
        activity_logger.log_success()
        return {"status": "success", "message": "Knowledge base deleted"}
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local/files")
async def list_local_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all local files from knowledge bases in a structured format."""
    from typing import Dict, List
    import os
    from pathlib import Path
    
    # Get all local file knowledge bases
    try:
        kbs = safe_query_knowledge_bases(
            db,
            {
                "user_id": current_user.id,
                "source_type": "local_file",
                "is_active": True
            }
        )
    except Exception as e:
        # Fallback to direct query if safe_query fails
        db.rollback()
        kbs = (
            db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.user_id == current_user.id,
                KnowledgeBase.source_type == "local_file",
                KnowledgeBase.is_active == True,  # noqa: E712
            )
            .all()
        )
    
    # Build file tree structure
    file_tree: Dict[str, Dict] = {}
    files_list: List[Dict] = []
    
    for kb in kbs:
        if kb.extra_metadata and "files" in kb.extra_metadata:
            for file_info in kb.extra_metadata["files"]:
                file_path = file_info.get("file_path", "")
                file_name = file_info.get("file_name", "")
                
                # Skip if file path contains NUL characters or is invalid
                if '\x00' in file_path or not file_path:
                    continue
                
                # Create file item
                file_item = {
                    "id": f"local_{kb.id}_{file_name}",
                    "name": file_name,
                    "type": "file",
                    "path": file_path,
                    "size": file_info.get("file_size", 0),
                    "modified_time": None,
                    "kb_id": kb.id,
                    "kb_name": kb.name,
                }
                files_list.append(file_item)
                
                # Build tree structure from file path
                # Extract directory structure if path exists
                if os.path.exists(file_path):
                    dir_path = os.path.dirname(file_path)
                    if dir_path:
                        # Create folder structure
                        parts = Path(dir_path).parts
                        current = file_tree
                        for part in parts:
                            if part not in current:
                                current[part] = {"type": "folder", "children": {}, "files": []}
                            current = current[part]["children"]
                        # Add file to the deepest folder
                        folder_name = os.path.basename(dir_path) if dir_path != "/" else "root"
                        if folder_name not in file_tree:
                            file_tree[folder_name] = {"type": "folder", "children": {}, "files": []}
                        file_tree[folder_name]["files"].append(file_item)
                    else:
                        # File in root
                        if "root" not in file_tree:
                            file_tree["root"] = {"type": "folder", "children": {}, "files": []}
                        file_tree["root"]["files"].append(file_item)
    
    # Convert tree to flat list for frontend (similar to Google Drive/OneDrive format)
    def flatten_tree(tree: Dict, parent_path: str = "") -> List[Dict]:
        result = []
        for name, node in tree.items():
            folder_path = f"{parent_path}/{name}" if parent_path else name
            # Add folder
            result.append({
                "id": f"folder_{folder_path}",
                "name": name,
                "type": "folder",
                "path": folder_path,
            })
            # Add files in this folder
            result.extend(node.get("files", []))
            # Recursively add subfolders
            if node.get("children"):
                result.extend(flatten_tree(node["children"], folder_path))
        return result
    
    # If no tree structure, just return flat list
    if not file_tree:
        return {"files": files_list}
    
    # Return flattened structure
    structured_files = flatten_tree(file_tree)
    return {"files": structured_files}


