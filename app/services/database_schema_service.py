"""Database schema inspection service for learning database structures."""
from sqlalchemy import create_engine, inspect, text
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from app.services.llm_service import decrypt_api_key


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively convert datetime and date objects to ISO format strings
    for JSON serialization.
    
    Args:
        obj: Object to sanitize
    
    Returns:
        JSON-serializable object
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: sanitize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        # For other types, try to convert to string
        try:
            return str(obj)
        except Exception:
            return None


def get_database_engine(connection_string: str, db_type: str):
    """
    Create SQLAlchemy engine from connection string.
    
    Args:
        connection_string: Database connection string (may be encrypted)
        db_type: Database type ('postgresql', 'mysql', 'sqlite', 'mssql')
    
    Returns:
        SQLAlchemy engine
    """
    # Decrypt connection string if needed
    try:
        decrypted = decrypt_api_key(connection_string)
    except Exception:
        # If decryption fails, assume it's already plain text
        decrypted = connection_string
    
    # Normalize connection string format
    if db_type == "postgresql":
        # Ensure postgresql:// format
        if not decrypted.startswith("postgresql://"):
            decrypted = decrypted.replace("postgresql+psycopg2://", "postgresql://")
            decrypted = decrypted.replace("postgres://", "postgresql://")
    elif db_type == "mysql":
        if not decrypted.startswith("mysql://"):
            decrypted = decrypted.replace("mysql+pymysql://", "mysql://")
    elif db_type == "sqlite":
        # SQLite connection strings are file paths
        if not decrypted.startswith("sqlite:///"):
            decrypted = f"sqlite:///{decrypted}"
    
    return create_engine(decrypted, pool_pre_ping=True, echo=False)


def inspect_database_schema(connection_string: str, db_type: str) -> Dict[str, Any]:
    """
    Inspect database schema and return structured information.
    
    Args:
        connection_string: Database connection string (may be encrypted)
        db_type: Database type ('postgresql', 'mysql', 'sqlite', 'mssql')
    
    Returns:
        {
            "tables": [
                {
                    "name": "tickets",
                    "columns": [
                        {"name": "id", "type": "integer", "nullable": False},
                        {"name": "subject", "type": "varchar", "nullable": True},
                        ...
                    ],
                    "primary_key": ["id"],
                    "foreign_keys": [...]
                }
            ],
            "sample_data": {...}  # Optional: sample rows for context
        }
    """
    engine = get_database_engine(connection_string, db_type)
    inspector = inspect(engine)
    
    schema_info = {
        "tables": [],
        "database_type": db_type
    }
    
    try:
        # Get all tables
        tables = inspector.get_table_names()
        
        for table_name in tables:
            table_info = {
                "name": table_name,
                "columns": [],
                "primary_key": [],
                "foreign_keys": []
            }
            
            try:
                # Get columns
                columns = inspector.get_columns(table_name)
                for col in columns:
                    table_info["columns"].append({
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                        "default": str(col.get("default", "")) if col.get("default") else None
                    })
                
                # Get primary key
                try:
                    pk = inspector.get_pk_constraint(table_name)
                    if pk and pk.get("constrained_columns"):
                        table_info["primary_key"] = pk["constrained_columns"]
                except Exception as e:
                    print(f"Could not get primary key for {table_name}: {e}")
                
                # Get foreign keys
                try:
                    fks = inspector.get_foreign_keys(table_name)
                    for fk in fks:
                        table_info["foreign_keys"].append({
                            "constrained_columns": fk["constrained_columns"],
                            "referred_table": fk["referred_table"],
                            "referred_columns": fk["referred_columns"]
                        })
                except Exception as e:
                    print(f"Could not get foreign keys for {table_name}: {e}")
                
                schema_info["tables"].append(table_info)
            except Exception as e:
                print(f"Error inspecting table {table_name}: {e}")
                continue
        
        # Optionally: Get sample data (first row of each table) for better context
        # This helps LLM understand data format
        schema_info["sample_data"] = {}
        for table_name in tables[:5]:  # Limit to first 5 tables to avoid performance issues
            try:
                with engine.connect() as conn:
                    # Use parameterized query to prevent SQL injection
                    # Note: table names can't be parameterized, so we validate against inspector
                    if table_name in tables:
                        result = conn.execute(text(f'SELECT * FROM "{table_name}" LIMIT 1'))
                        row = result.fetchone()
                        if row:
                            # Convert row to dict
                            if hasattr(row, '_mapping'):
                                row_dict = dict(row._mapping)
                            else:
                                # Fallback for older SQLAlchemy versions
                                row_dict = {col: getattr(row, col) for col in row.keys()}
                            
                            schema_info["sample_data"][table_name] = {
                                "columns": list(row_dict.keys()),
                                "sample_row": row_dict
                            }
            except Exception as e:
                print(f"Could not fetch sample data for {table_name}: {e}")
                continue
    
    finally:
        engine.dispose()
    
    # Sanitize schema_info to ensure all datetime objects are converted to strings
    schema_info = sanitize_for_json(schema_info)
    
    return schema_info


def refresh_schema_cache(connection_string: str, db_type: str) -> Dict[str, Any]:
    """
    Refresh the schema cache by re-inspecting the database.
    
    Args:
        connection_string: Database connection string
        db_type: Database type
    
    Returns:
        Updated schema information
    """
    return inspect_database_schema(connection_string, db_type)

