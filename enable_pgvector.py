#!/usr/bin/env python3
"""Utility script to enable pgvector extension in PostgreSQL database.

This script can be run independently to ensure the pgvector extension is enabled
in your PostgreSQL database. It doesn't require the full application configuration.
"""
import psycopg2
import sys
import os
from urllib.parse import urlparse

def enable_pgvector_extension(db_url: str = None):
    """
    Enable pgvector extension in the specified database.
    
    Args:
        db_url: PostgreSQL connection URL. If not provided, will try to get from:
                1. DATABASE_URL environment variable
                2. Default: postgresql://postgres:postgres@localhost:5432/postgres
    """
    if not db_url:
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/postgres')
    
    # Normalize database URL format
    if db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://")
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://")
    
    try:
        print(f"Connecting to database...")
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Get database name for display
        cursor.execute("SELECT current_database();")
        db_name = cursor.fetchone()[0]
        print(f"Connected to database: {db_name}")
        
        # Check if extension already exists
        cursor.execute("SELECT * FROM pg_extension WHERE extname='vector';")
        if cursor.fetchone():
            print("✓ pgvector extension is already enabled")
        else:
            # Create extension
            print("Creating pgvector extension...")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            print("✓ pgvector extension enabled successfully!")
        
        # Verify extension
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector';")
        result = cursor.fetchone()
        if result:
            print(f"✓ Extension version: {result[0]}")
        
        # Test the extension
        cursor.execute("SELECT l2_distance('[1,2,3]'::vector, '[4,5,6]'::vector);")
        test_result = cursor.fetchone()[0]
        print(f"✓ Extension test passed: l2_distance = {test_result:.4f}")
        
        cursor.close()
        conn.close()
        
        print("\n✅ pgvector extension is ready to use!")
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ Connection error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check your DATABASE_URL connection string")
        print("3. Verify pgvector is installed: brew install pgvector (macOS)")
        return False
    except psycopg2.errors.UndefinedFunction as e:
        print(f"❌ Error: {e}")
        print("\nThe pgvector extension may not be installed in PostgreSQL.")
        print("Install it with: brew install pgvector (macOS)")
        print("Or use the Docker image: ankane/pgvector")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    # Allow database URL as command line argument
    db_url = sys.argv[1] if len(sys.argv) > 1 else None
    success = enable_pgvector_extension(db_url)
    sys.exit(0 if success else 1)

