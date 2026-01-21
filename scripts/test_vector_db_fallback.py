"""Test script to verify vector DB URL fallback logic."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.helpers.vector_db_helper import get_user_vector_db_url
from app.core.config import settings

# Create mock user settings objects
class MockUserSettings:
    def __init__(self, vector_db_url=None, vector_db_enabled=False):
        self.vector_db_url = vector_db_url
        self.vector_db_enabled = vector_db_enabled

print("Testing vector DB URL fallback logic:\n")

# Test 1: None settings
result = get_user_vector_db_url(None)
print(f"1. None settings: {result}")
assert result is None, "Should return None for None settings"

# Test 2: Settings with no URL
settings_no_url = MockUserSettings(vector_db_url=None, vector_db_enabled=False)
result = get_user_vector_db_url(settings_no_url)
print(f"2. Settings with no URL: {result}")
assert result is None, "Should return None when no URL is set"

# Test 3: Settings with URL but disabled (backward compatibility)
settings_url_disabled = MockUserSettings(
    vector_db_url="postgresql://custom:5432/testdb",
    vector_db_enabled=False
)
result = get_user_vector_db_url(settings_url_disabled)
print(f"3. Settings with URL but disabled: {result}")
assert result == "postgresql://custom:5432/testdb", "Should return URL even if disabled (backward compatibility)"

# Test 4: Settings with URL and enabled
settings_url_enabled = MockUserSettings(
    vector_db_url="postgresql://custom:5432/testdb",
    vector_db_enabled=True
)
result = get_user_vector_db_url(settings_url_enabled)
print(f"4. Settings with URL and enabled: {result}")
assert result == "postgresql://custom:5432/testdb", "Should return URL when enabled"

print("\n✓ All tests passed!")
print("\nFallback behavior:")
print(f"  - If get_user_vector_db_url returns None, system uses: {settings.database_url[:50]}...")
print("  - This ensures existing configurations are preserved")
