"""Base database configuration."""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

Base = declarative_base()

# Helper function to normalize database URL
def normalize_db_url(url: str) -> str:
    """Normalize database URL to postgresql:// format for SQLAlchemy."""
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql://")
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://")
    return url

# Master database engine (for writes)
# Use echo=False for production, but can enable for debugging
master_engine = create_engine(
    normalize_db_url(settings.database_url),
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_size=10,
    max_overflow=20,
    echo=False  # Set to True for SQL query debugging
)

# Slave database engine (for reads) - falls back to master if not configured
slave_engine = (
    create_engine(
        normalize_db_url(settings.database_read_url),
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20
    ) if settings.database_read_url else master_engine
)

# Session makers
MasterSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=master_engine)
SlaveSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=slave_engine)


def get_db(read_only: bool = False):
    """
    Get database session.
    
    Args:
        read_only: If True, use slave database for reads (default: False, uses master)
        
    Yields:
        Database session
    """
    if read_only:
        db = SlaveSessionLocal()
    else:
        db = MasterSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=master_engine)

