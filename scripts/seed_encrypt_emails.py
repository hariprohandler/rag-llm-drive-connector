#!/usr/bin/env python3
"""
Seeder script to encrypt existing user emails in the database.

This script:
1. Reads all users from the database
2. Encrypts emails that are not already encrypted
3. Updates the database with encrypted emails

Usage:
    python scripts/seed_encrypt_emails.py [--dry-run]
    
Note: This script requires all project dependencies to be installed.
      If running locally, ensure you're in the project's virtual environment.
      Alternatively, run this inside the Docker container where all dependencies are available.
"""
import sys
import os

# Check for required dependencies BEFORE importing app modules
missing_deps = []

try:
    import psycopg2
except ImportError:
    missing_deps.append("psycopg2-binary")

try:
    from jose import jwt
except ImportError:
    missing_deps.append("python-jose[cryptography]")

try:
    from cryptography.fernet import Fernet
except ImportError:
    missing_deps.append("cryptography")

if missing_deps:
    print("=" * 60)
    print("ERROR: Missing required dependencies.")
    print("=" * 60)
    print(f"\nMissing packages: {', '.join(missing_deps)}")
    print("\nPlease install dependencies:")
    print("  pip install -r requirements.txt")
    print("\nOr install specific packages:")
    for dep in missing_deps:
        print(f"  pip install {dep}")
    print("\nAlternatively, run this inside the Docker container:")
    print("  docker exec -it rag-app python scripts/seed_encrypt_emails.py --dry-run")
    print("=" * 60)
    sys.exit(1)

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from sqlalchemy.orm import Session
    from app.models.base import get_db
    from app.models import User
    from app.services.email_encryption import encrypt_email, is_encrypted, decrypt_email, hash_email_for_lookup
except ImportError as e:
    print("=" * 60)
    print(f"ERROR: Failed to import required modules: {e}")
    print("=" * 60)
    print("\nMake sure:")
    print("  1. You're running this from the project root directory")
    print("  2. All dependencies are installed: pip install -r requirements.txt")
    print("  3. You're in the correct Python environment")
    print("\nAlternatively, run this inside the Docker container:")
    print("  docker exec -it rag-app python scripts/seed_encrypt_emails.py --dry-run")
    print("=" * 60)
    sys.exit(1)


def seed_encrypt_emails(dry_run: bool = False):
    """
    Encrypt all unencrypted user emails in the database.
    
    Args:
        dry_run: If True, only show what would be changed without making changes
    """
    print("=" * 60)
    print("Email Encryption Seeder")
    print("=" * 60)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
    
    # Get database session
    db: Session = next(get_db())
    
    try:
        # Check if email_hash column exists (migration must be run first)
        from sqlalchemy import inspect, text
        inspector = inspect(db.bind)
        columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'email_hash' not in columns:
            print("=" * 60)
            print("ERROR: Database migration not applied")
            print("=" * 60)
            print("\nThe 'email_hash' column does not exist in the 'users' table.")
            print("You need to run the database migration first:")
            print("\n  alembic upgrade head")
            print("\nOr inside Docker:")
            print("  docker exec -it rag-app alembic upgrade head")
            print("=" * 60)
            return False
        
        # Get all users
        users = db.query(User).all()
        total_users = len(users)
        
        print(f"Found {total_users} users in database")
        print()
        
        encrypted_count = 0
        already_encrypted_count = 0
        error_count = 0
        
        for user in users:
            try:
                # Check if email is already encrypted
                if is_encrypted(user.email):
                    already_encrypted_count += 1
                    try:
                        decrypted = decrypt_email(user.email)
                        print(f"✓ User {user.id}: Already encrypted (email: {decrypted[:3]}***)")
                    except:
                        print(f"✓ User {user.id}: Already encrypted (decryption test failed)")
                    continue
                
                # Email is not encrypted, encrypt it
                original_email = user.email
                encrypted_email = encrypt_email(original_email)
                email_hash = hash_email_for_lookup(original_email)
                
                if dry_run:
                    print(f"🔍 Would encrypt: User {user.id}")
                    print(f"   Original: {original_email}")
                    print(f"   Encrypted: {encrypted_email[:50]}...")
                    print(f"   Hash: {email_hash[:16]}...")
                else:
                    user.email = encrypted_email
                    user.email_hash = email_hash
                    db.add(user)
                    print(f"✓ Encrypted: User {user.id} ({original_email[:3]}***)")
                
                encrypted_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"✗ Error processing user {user.id}: {e}")
        
        if not dry_run:
            # Commit all changes
            db.commit()
            print()
            print("=" * 60)
            print("✅ Successfully committed all changes to database")
        else:
            print()
            print("=" * 60)
            print("🔍 Dry run complete - no changes made")
        
        print()
        print("Summary:")
        print(f"  Total users: {total_users}")
        print(f"  Already encrypted: {already_encrypted_count}")
        print(f"  {'Would encrypt' if dry_run else 'Encrypted'}: {encrypted_count}")
        print(f"  Errors: {error_count}")
        print("=" * 60)
        
    except Exception as e:
        if not dry_run:
            db.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Encrypt existing user emails in the database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (show what would be changed without making changes)"
    )
    
    args = parser.parse_args()
    
    success = seed_encrypt_emails(dry_run=args.dry_run)
    sys.exit(0 if success else 1)

