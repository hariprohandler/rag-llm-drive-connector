"""Email encryption service using Fernet symmetric encryption."""
from cryptography.fernet import Fernet
import os
import base64
import hashlib
from app.services.llm_service import get_encryption_key


def encrypt_email(email: str) -> str:
    """Encrypt an email address."""
    if not email:
        return email
    try:
        f = Fernet(get_encryption_key())
        return f.encrypt(email.encode()).decode()
    except Exception as e:
        print(f"Error encrypting email: {e}")
        # In case of encryption failure, return original (should not happen in production)
        return email


def decrypt_email(encrypted_email: str) -> str:
    """
    Decrypt an email address.
    
    If the email is already plain text (contains @), returns it as-is.
    If decryption fails for any reason, returns the original value.
    This ensures the function never raises an exception and always returns a value.
    """
    if not encrypted_email:
        return encrypted_email
    
    # If it contains @, it's likely already plain text
    if "@" in encrypted_email:
        return encrypted_email
    
    try:
        f = Fernet(get_encryption_key())
        decrypted = f.decrypt(encrypted_email.encode()).decode()
        return decrypted
    except Exception as e:
        # If decryption fails, return the original value
        # This handles cases where:
        # - Email is already plain text but doesn't contain @ (unlikely but possible)
        # - Encryption key changed
        # - Email is corrupted
        # In all cases, returning the original is safer than raising an exception
        print(f"Warning: Could not decrypt email (may already be plain text): {e}")
        return encrypted_email


def hash_email_for_lookup(email: str) -> str:
    """
    Create a deterministic hash of email for lookups.
    This allows us to find users by email without decrypting all emails.
    Uses SHA-256 with a salt from the encryption key.
    """
    if not email:
        return email
    # Use part of encryption key as salt for consistency
    try:
        key = get_encryption_key()
        # Use first 16 bytes of key as salt
        salt = key[:16] if len(key) >= 16 else key
        # Convert salt to string for hashing
        if isinstance(salt, bytes):
            salt_str = base64.urlsafe_b64encode(salt).decode()
        else:
            salt_str = str(salt)
        return hashlib.sha256((email.lower().strip() + salt_str).encode()).hexdigest()
    except Exception as e:
        print(f"Error hashing email: {e}")
        # Fallback to simple hash
        return hashlib.sha256(email.lower().strip().encode()).hexdigest()


def is_encrypted(email: str) -> bool:
    """Check if an email appears to be encrypted (base64 format check)."""
    if not email:
        return False
    try:
        # Encrypted emails are base64-encoded strings
        # Try to decode and check if it's valid base64
        decoded = base64.urlsafe_b64decode(email)
        # If it decodes successfully and doesn't contain @, it's likely encrypted
        return "@" not in email and len(decoded) > 0
    except:
        # If it's not valid base64 or contains @, it's likely plain text
        return False

