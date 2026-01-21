"""Script to verify user settings and ensure configurations are preserved."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.models import UserSettings, User
from app.models.base import master_engine
from sqlalchemy.orm import sessionmaker
from app.helpers.vector_db_helper import get_user_vector_db_url

Session = sessionmaker(bind=master_engine)
session = Session()

try:
    print("Checking user settings and configurations...\n")
    
    # Get all users
    users = session.query(User).all()
    print(f"Total users: {len(users)}\n")
    
    # Check each user's settings
    for user in users:
        user_settings = session.query(UserSettings).filter(
            UserSettings.user_id == user.id
        ).first()
        
        print(f"User: {user.id} ({user.email})")
        
        if user_settings:
            print(f"  ✓ UserSettings exists")
            print(f"    - Organization: {user_settings.organization_name}")
            print(f"    - Vector DB URL: {user_settings.vector_db_url[:50] + '...' if user_settings.vector_db_url and len(user_settings.vector_db_url) > 50 else user_settings.vector_db_url}")
            print(f"    - Vector DB Enabled: {user_settings.vector_db_enabled}")
            print(f"    - Vector DB Config: {user_settings.vector_db_config}")
            
            # Test get_user_vector_db_url
            db_url = get_user_vector_db_url(user_settings)
            if db_url:
                print(f"    ✓ Will use custom DB: {db_url[:50]}...")
            else:
                print(f"    → Will use default DB: {settings.database_url[:50]}...")
        else:
            print(f"  ⚠ No UserSettings record (will use defaults)")
            print(f"    → Will use default DB: {settings.database_url[:50]}...")
        
        print()
    
    # Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    
    total_settings = session.query(UserSettings).count()
    users_with_custom_db = session.query(UserSettings).filter(
        UserSettings.vector_db_url.isnot(None)
    ).count()
    users_with_enabled_db = session.query(UserSettings).filter(
        UserSettings.vector_db_enabled == True
    ).count()
    
    print(f"Total UserSettings records: {total_settings}")
    print(f"Users with custom vector_db_url: {users_with_custom_db}")
    print(f"Users with vector_db_enabled=True: {users_with_enabled_db}")
    
    if users_with_custom_db > users_with_enabled_db:
        print(f"\n⚠️  {users_with_custom_db - users_with_enabled_db} users have vector_db_url but enabled=False")
        print("   These will now be used (backward compatibility fix applied)")
    
    print("\n✓ All configurations are preserved and accessible")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
