"""
Migration script to add user_settings table for organization settings.

Run this script to add the user_settings table to your database.
This can be run manually or integrated into your migration system.

Usage:
    python migrations/add_user_settings_table.py
"""
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.models.base import master_engine
from app.core.config import settings


def run_migration():
    """Create user_settings table if it doesn't exist."""
    print("Running migration: Add user_settings table...")
    
    with master_engine.connect() as conn:
        # Check if table already exists
        check_table = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_settings'
            );
        """)
        result = conn.execute(check_table)
        table_exists = result.scalar()
        
        if table_exists:
            print("✓ user_settings table already exists. Skipping migration.")
            return
        
        # Create user_settings table
        create_table = text("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id VARCHAR NOT NULL PRIMARY KEY,
                user_id VARCHAR NOT NULL UNIQUE,
                organization_name VARCHAR DEFAULT 'RAG Chat Platform',
                preferences TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_user_settings_user_id 
                    FOREIGN KEY (user_id) 
                    REFERENCES users(id) 
                    ON DELETE CASCADE
            );
        """)
        
        conn.execute(create_table)
        
        # Create index on user_id (already unique, but explicit index for performance)
        create_index = text("""
            CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);
        """)
        conn.execute(create_index)
        conn.commit()
        
        print("✓ user_settings table created successfully!")
        print("✓ Index created on user_id")
        
        # Add comment to table
        add_comment = text("""
            COMMENT ON TABLE user_settings IS 'User preferences and settings including organization name';
        """)
        conn.execute(add_comment)
        conn.commit()
        
        print("✓ Migration completed successfully!")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)

