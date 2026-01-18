"""Script to fix langchain_pg_embedding table schema for langchain_postgres compatibility."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from app.core.config import settings

def fix_pgvector_schema():
    """Fix the langchain_pg_embedding table schema to match langchain_postgres expectations."""
    try:
        db_url = settings.database_url.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        print("Checking langchain_pg_embedding table schema...")
        
        # Check current columns
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'langchain_pg_embedding'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        print(f"Current columns: {[c[0] for c in columns]}")
        
        # Check if cmetadata is json (needs to be jsonb)
        cur.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'langchain_pg_embedding' 
            AND column_name = 'cmetadata';
        """)
        meta_type = cur.fetchone()
        
        if meta_type and meta_type[0] == 'json':
            print("Converting cmetadata from json to jsonb...")
            # Convert json to jsonb
            cur.execute("""
                ALTER TABLE langchain_pg_embedding 
                ALTER COLUMN cmetadata TYPE jsonb USING cmetadata::jsonb;
            """)
            print("✓ Converted cmetadata to jsonb")
        elif meta_type and meta_type[0] == 'jsonb':
            print("✓ cmetadata is already jsonb")
        
        # Check if there's an 'id' column (old schema) that shouldn't be there
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'langchain_pg_embedding' 
            AND column_name = 'id';
        """)
        has_id = cur.fetchone()
        
        if has_id:
            print("WARNING: Table has 'id' column (old schema).")
            print("  langchain_postgres uses 'uuid' as primary key, not 'id'.")
            print("  You may need to drop and recreate the table.")
            print("  This will delete all existing embeddings!")
            response = input("  Do you want to drop and recreate the table? (yes/no): ")
            if response.lower() == 'yes':
                print("Dropping table...")
                cur.execute("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE;")
                print("✓ Table dropped. It will be recreated automatically on next use.")
            else:
                print("  Skipping table recreation. You may encounter errors.")
        
        # Verify uuid column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'langchain_pg_embedding' 
            AND column_name = 'uuid';
        """)
        has_uuid = cur.fetchone()
        
        if not has_uuid:
            print("ERROR: Table does not have 'uuid' column!")
            print("  This table needs to be recreated with langchain_postgres.")
            print("  Dropping table so it can be recreated...")
            cur.execute("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE;")
            print("✓ Table dropped. It will be recreated automatically on next use.")
        else:
            print("✓ Table has 'uuid' column (correct)")
        
        cur.close()
        conn.close()
        print("\n✓ Schema check complete!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    fix_pgvector_schema()

