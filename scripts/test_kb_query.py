"""Test script to verify KnowledgeBase queries work with organization_id."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import KnowledgeBase
from app.models.base import master_engine
from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=master_engine)
session = Session()

try:
    # Test query similar to what ingest.py does
    kbs = session.query(KnowledgeBase).filter(
        KnowledgeBase.user_id == 'test_user',
        KnowledgeBase.source_type == 'local_file',
        KnowledgeBase.is_active == True
    ).all()
    print(f"✓ Query successful - organization_id column is accessible")
    print(f"  Found {len(kbs)} knowledge bases")
    if kbs:
        print(f"  First KB organization_id: {kbs[0].organization_id}")
except Exception as e:
    print(f"✗ Query error: {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
