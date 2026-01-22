"""create_source_specific_vector_tables

Revision ID: f30e93aa71e
Revises: acb0a7ee2ae
Create Date: 2026-01-18 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f30e93aa71e'
down_revision: Union[str, None] = 'acb0a7ee2ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create source-specific vector tables for scalable vector storage.
    
    Each table follows the same schema as langchain_pg_embedding:
    - uuid: Primary key (UUID)
    - collection_id: Foreign key to langchain_pg_collection (UUID)
    - embedding: Vector type (1536 dimensions for OpenAI embeddings)
    - document: Text content
    - cmetadata: JSONB metadata
    
    This allows for:
    - Better query performance (smaller tables to scan)
    - Reduced lock contention (writes spread across tables)
    - Independent partitioning per source
    - Efficient indexing per source type
    """
    
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # Ensure langchain_pg_collection table exists (created by langchain_postgres)
    # If it doesn't exist, create it
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables 
                          WHERE table_name = 'langchain_pg_collection') THEN
                CREATE TABLE langchain_pg_collection (
                    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR NOT NULL,
                    cmetadata JSONB
                );
                CREATE INDEX ix_langchain_pg_collection_name 
                    ON langchain_pg_collection(name);
            END IF;
        END $$;
    """)
    
    # Source-specific vector tables
    # Each table mirrors the langchain_pg_embedding schema
    source_tables = [
        ("vectors_slack", "Slack messages and channels"),
        ("vectors_teams", "Microsoft Teams messages and channels"),
        ("vectors_onedrive", "OneDrive files and documents"),
        ("vectors_google_drive", "Google Drive files and documents"),
        ("vectors_local_file", "Locally uploaded files"),
        ("vectors_zendesk", "Zendesk tickets and articles"),
    ]
    
    for table_name, description in source_tables:
        # Check if table already exists
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.tables 
                              WHERE table_name = '{table_name}') THEN
                    CREATE TABLE {table_name} (
                        uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        collection_id UUID,
                        embedding vector(1536),
                        document TEXT,
                        cmetadata JSONB,
                        CONSTRAINT fk_{table_name}_collection 
                            FOREIGN KEY (collection_id) 
                            REFERENCES langchain_pg_collection(uuid) 
                            ON DELETE CASCADE
                    );
                    
                    -- Create indexes for performance
                    CREATE INDEX ix_{table_name}_collection_id 
                        ON {table_name}(collection_id);
                    
                    -- HNSW index for vector similarity search (cosine distance)
                    CREATE INDEX ix_{table_name}_embedding_hnsw 
                        ON {table_name} 
                        USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64);
                    
                    -- GIN index for JSONB metadata queries
                    CREATE INDEX ix_{table_name}_metadata_gin 
                        ON {table_name} 
                        USING gin (cmetadata);
                    
                    -- Index on common metadata fields for faster filtering
                    CREATE INDEX ix_{table_name}_metadata_user_id 
                        ON {table_name} 
                        ((cmetadata->>'user_id'));
                    
                    CREATE INDEX ix_{table_name}_metadata_kb_id 
                        ON {table_name} 
                        ((cmetadata->>'knowledge_base_id'));
                    
                    CREATE INDEX ix_{table_name}_metadata_source_type 
                        ON {table_name} 
                        ((cmetadata->>'source_type'));
                    
                    COMMENT ON TABLE {table_name} IS '{description}';
                END IF;
            END $$;
        """)
    
    # Create default langchain_pg_embedding table if it doesn't exist
    # This is for backward compatibility and sources without specific tables
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables 
                          WHERE table_name = 'langchain_pg_embedding') THEN
                CREATE TABLE langchain_pg_embedding (
                    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    collection_id UUID,
                    embedding vector(1536),
                    document TEXT,
                    cmetadata JSONB,
                    CONSTRAINT fk_langchain_pg_embedding_collection 
                        FOREIGN KEY (collection_id) 
                        REFERENCES langchain_pg_collection(uuid) 
                        ON DELETE CASCADE
                );
                
                -- Create indexes for default table
                CREATE INDEX ix_langchain_pg_embedding_collection_id 
                    ON langchain_pg_embedding(collection_id);
                
                CREATE INDEX ix_langchain_pg_embedding_embedding_hnsw 
                    ON langchain_pg_embedding 
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                
                CREATE INDEX ix_langchain_pg_embedding_metadata_gin 
                    ON langchain_pg_embedding 
                    USING gin (cmetadata);
                
                COMMENT ON TABLE langchain_pg_embedding IS 
                    'Default vector storage table for backward compatibility';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """
    Drop all source-specific vector tables.
    Note: This will delete all vector data in these tables!
    """
    
    source_tables = [
        "vectors_slack",
        "vectors_teams",
        "vectors_onedrive",
        "vectors_google_drive",
        "vectors_local_file",
        "vectors_zendesk",
    ]
    
    for table_name in source_tables:
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
