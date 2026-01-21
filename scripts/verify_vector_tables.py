"""Script to verify that source-specific vector tables were created."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from app.core.config import settings
from app.constants.table_names import TableNames


def verify_vector_tables():
    """Verify that all source-specific vector tables exist."""
    try:
        db_url = settings.database_url.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        print("Checking for source-specific vector tables...\n")
        
        # Expected tables
        expected_tables = [
            TableNames.SLACK,
            TableNames.TEAMS,
            TableNames.ONEDRIVE,
            TableNames.GOOGLE_DRIVE,
            TableNames.LOCAL_FILE,
            TableNames.ZENDESK,
            TableNames.DEFAULT,  # langchain_pg_embedding
        ]
        
        # Check each table
        found_tables = []
        missing_tables = []
        
        for table_name in expected_tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (table_name,))
            exists = cur.fetchone()[0]
            
            if exists:
                # Get row count
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cur.fetchone()[0]
                
                # Get column info
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = %s
                    ORDER BY ordinal_position;
                """, (table_name,))
                columns = cur.fetchall()
                
                found_tables.append({
                    'name': table_name,
                    'count': count,
                    'columns': columns
                })
                print(f"✓ {table_name}: {count} rows")
                print(f"  Columns: {', '.join([f'{c[0]} ({c[1]})' for c in columns])}")
            else:
                missing_tables.append(table_name)
                print(f"✗ {table_name}: NOT FOUND")
        
        # Check for indexes
        print("\nChecking indexes on vector tables...\n")
        for table_info in found_tables:
            table_name = table_info['name']
            cur.execute("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = %s
                ORDER BY indexname;
            """, (table_name,))
            indexes = cur.fetchall()
            
            if indexes:
                print(f"{table_name} indexes:")
                for idx_name, idx_def in indexes:
                    print(f"  - {idx_name}")
                    # Show index type if it's a vector index
                    if 'hnsw' in idx_def.lower() or 'vector' in idx_def.lower():
                        print(f"    Type: Vector similarity index")
            else:
                print(f"{table_name}: No indexes found")
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Found tables: {len(found_tables)}/{len(expected_tables)}")
        if missing_tables:
            print(f"Missing tables: {', '.join(missing_tables)}")
            print("\n⚠️  Some tables are missing. Run migrations:")
            print("   make migrate")
        else:
            print("✓ All expected vector tables exist!")
        
        # Check pgvector extension
        cur.execute("SELECT * FROM pg_extension WHERE extname='vector';")
        has_pgvector = cur.fetchone()
        if has_pgvector:
            print("✓ pgvector extension is installed")
        else:
            print("✗ pgvector extension is NOT installed")
            print("  Run: CREATE EXTENSION vector;")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    verify_vector_tables()
