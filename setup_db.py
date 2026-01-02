"""Helper script to set up the PostgreSQL database with pgvector extension and user tables."""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import config
import models

def setup_database():
    """Create the pgvector extension and user tables."""
    try:
        # Parse database URL from config
        db_url = config.settings.database_url
        # Replace postgresql+psycopg2:// with postgresql:// for psycopg2
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://")
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Create extension
        print("Creating pgvector extension...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("✓ pgvector extension created successfully!")
        
        # Verify extension installation
        cursor.execute("SELECT * FROM pg_extension WHERE extname='vector';")
        result = cursor.fetchone()
        if result:
            print("✓ Extension verified")
        else:
            print("⚠ Extension may not be installed correctly")
        
        cursor.close()
        conn.close()
        
        # Create user tables
        print("\nCreating user tables...")
        models.init_db()
        print("✓ User tables created successfully!")
        
        print("\n✅ Database setup complete!")
        
    except psycopg2.OperationalError as e:
        print(f"❌ Connection error: {e}")
        print("\nMake sure PostgreSQL is running:")
        print("  docker run -d --name pgvector -p 5432:5432 -e POSTGRES_PASSWORD=postgres ankane/pgvector")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    setup_database()
