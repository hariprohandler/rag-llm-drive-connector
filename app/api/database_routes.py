"""API routes for external database connections and SQL queries."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.models import User, DatabaseConnection, LLMConfig
from app.models.base import get_db
from app.services.auth_service import get_current_user
from app.services.database_schema_service import inspect_database_schema, refresh_schema_cache
from app.services.sql_agent_service import execute_sql_query, get_best_sql_model, is_sql_query
from app.services.llm_service import encrypt_api_key, decrypt_api_key
from app.services.rag import get_llm_from_config
from app.helpers.logging_helper import ActivityLogger

router = APIRouter(prefix="/api/databases", tags=["databases"])


class DatabaseConnectionRequest(BaseModel):
    name: str
    db_type: str  # 'postgresql', 'mysql', 'sqlite', 'mssql'
    connection_string: str  # Will be encrypted before storage


class DatabaseConnectionUpdateRequest(BaseModel):
    name: Optional[str] = None
    connection_string: Optional[str] = None
    is_active: Optional[bool] = None


class SQLQueryRequest(BaseModel):
    database_connection_id: int
    query: str
    llm_config_id: Optional[int] = None


@router.post("/connections")
async def create_database_connection(
    request: DatabaseConnectionRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new database connection."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="database_connection_create",
        endpoint="/api/databases/connections",
        method="POST",
        user_id=current_user.id,
        metadata={"db_type": request.db_type, "name": request.name}
    )
    
    try:
        # Validate db_type
        valid_db_types = ["postgresql", "mysql", "sqlite", "mssql"]
        if request.db_type.lower() not in valid_db_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid db_type. Must be one of: {', '.join(valid_db_types)}"
            )
        
        # Encrypt connection string
        encrypted_conn_str = encrypt_api_key(request.connection_string)
        
        # Inspect schema
        try:
            schema_info = inspect_database_schema(request.connection_string, request.db_type.lower())
            # Schema info is already sanitized by inspect_database_schema
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to connect to database or inspect schema: {str(e)}"
            )
        
        # Create connection record
        db_conn = DatabaseConnection(
            user_id=current_user.id,
            name=request.name,
            db_type=request.db_type.lower(),
            connection_string=encrypted_conn_str,
            schema_info=schema_info,  # Already sanitized for JSON
            schema_updated_at=datetime.utcnow()
        )
        db.add(db_conn)
        db.commit()
        db.refresh(db_conn)
        
        activity_logger.log_success({"connection_id": db_conn.id})
        return db_conn.to_dict()
    except HTTPException:
        raise
    except ValueError as e:
        activity_logger.log_error(f"Configuration error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections")
async def list_database_connections(
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all database connections for the user."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="database_connection_list",
        endpoint="/api/databases/connections",
        method="GET",
        user_id=current_user.id,
        metadata={}
    )
    
    try:
        connections = db.query(DatabaseConnection).filter(
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.is_active == True
        ).all()
        
        activity_logger.log_success({"count": len(connections)})
        return [conn.to_dict() for conn in connections]
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections/{connection_id}")
async def get_database_connection(
    connection_id: int,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific database connection."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="database_connection_get",
        endpoint=f"/api/databases/connections/{connection_id}",
        method="GET",
        user_id=current_user.id,
        metadata={"connection_id": connection_id}
    )
    
    try:
        db_conn = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id
        ).first()
        
        if not db_conn:
            activity_logger.log_error("Database connection not found", status_code=404)
            raise HTTPException(status_code=404, detail="Database connection not found")
        
        activity_logger.log_success({"connection_id": connection_id, "db_type": db_conn.db_type})
        return db_conn.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/connections/{connection_id}")
async def update_database_connection(
    connection_id: int,
    request: DatabaseConnectionUpdateRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a database connection."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="database_connection_update",
        endpoint=f"/api/databases/connections/{connection_id}",
        method="PUT",
        user_id=current_user.id,
        metadata={"connection_id": connection_id}
    )
    
    try:
        db_conn = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id
        ).first()
        
        if not db_conn:
            raise HTTPException(status_code=404, detail="Database connection not found")
        
        if request.name is not None:
            db_conn.name = request.name
        
        if request.connection_string is not None:
            # Encrypt new connection string
            encrypted_conn_str = encrypt_api_key(request.connection_string)
            db_conn.connection_string = encrypted_conn_str
            
            # Refresh schema cache
            try:
                schema_info = inspect_database_schema(request.connection_string, db_conn.db_type)
                # Schema info is already sanitized by inspect_database_schema
                db_conn.schema_info = schema_info  # Already sanitized for JSON
                db_conn.schema_updated_at = datetime.utcnow()
            except Exception as e:
                print(f"Warning: Could not refresh schema cache: {e}")
        
        if request.is_active is not None:
            db_conn.is_active = request.is_active
        
        db_conn.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_conn)
        
        activity_logger.log_success({"connection_id": db_conn.id})
        return db_conn.to_dict()
    except HTTPException:
        raise
    except ValueError as e:
        activity_logger.log_error(f"Configuration error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/connections/{connection_id}")
async def delete_database_connection(
    connection_id: int,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a database connection."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="database_connection_delete",
        endpoint=f"/api/databases/connections/{connection_id}",
        method="DELETE",
        user_id=current_user.id,
        metadata={"connection_id": connection_id}
    )
    
    try:
        db_conn = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id
        ).first()
        
        if not db_conn:
            activity_logger.log_error("Database connection not found", status_code=404)
            raise HTTPException(status_code=404, detail="Database connection not found")
        
        db.delete(db_conn)
        db.commit()
        
        activity_logger.log_success({"connection_id": connection_id})
        return {"message": "Database connection deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connections/{connection_id}/refresh-schema")
async def refresh_database_schema(
    connection_id: int,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Refresh the schema cache for a database connection."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="database_schema_refresh",
        endpoint=f"/api/databases/connections/{connection_id}/refresh-schema",
        method="POST",
        user_id=current_user.id,
        metadata={"connection_id": connection_id}
    )
    
    try:
        db_conn = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id
        ).first()
        
        if not db_conn:
            raise HTTPException(status_code=404, detail="Database connection not found")
        
        # Refresh schema
        schema_info = refresh_schema_cache(db_conn.connection_string, db_conn.db_type)
        # Schema info is already sanitized by refresh_schema_cache -> inspect_database_schema
        
        # Update cache
        db_conn.schema_info = schema_info  # Already sanitized for JSON
        db_conn.schema_updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_conn)
        
        activity_logger.log_success({"connection_id": db_conn.id})
        return db_conn.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def execute_sql_query_endpoint(
    request: SQLQueryRequest,
    fastapi_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute a natural language query against a database."""
    activity_logger = ActivityLogger(
        request=fastapi_request,
        activity_type="sql_query",
        endpoint="/api/databases/query",
        method="POST",
        user_id=current_user.id,
        metadata={"database_connection_id": request.database_connection_id, "query": request.query}
    )
    
    try:
        # Get database connection
        db_conn = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == request.database_connection_id,
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.is_active == True
        ).first()
        
        if not db_conn:
            raise HTTPException(status_code=404, detail="Database connection not found")
        
        # Get LLM config
        if request.llm_config_id:
            llm_config = db.query(LLMConfig).filter(
                LLMConfig.id == request.llm_config_id,
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
        
        # Execute query
        result = execute_sql_query(
            query=request.query,
            connection_string=db_conn.connection_string,
            db_type=db_conn.db_type,
            llm=sql_llm,
            schema_info=db_conn.schema_info
        )
        
        activity_logger.log_success({
            "query": request.query,
            "sql_query": result.get("sql_query", ""),
            "has_error": "error" in result
        })
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        activity_logger.log_error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

