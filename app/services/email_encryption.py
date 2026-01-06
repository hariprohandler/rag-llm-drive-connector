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
    If decryption fails for any reason, attempts to return a readable value.
    This ensures the function never raises an exception and always returns a value.
    """
    if not encrypted_email:
        return encrypted_email
    
    # If it contains @, it's likely already plain text
    if "@" in encrypted_email:
        return encrypted_email
    
    # Check if it looks like a Fernet token (starts with gAAAAA)
    if not encrypted_email.startswith('gAAAAA'):
        # Doesn't look encrypted, return as-is
        return encrypted_email
    
    # Try to decrypt - Fernet tokens are base64 encoded
    try:
        encryption_key = get_encryption_key()
        # Ensure key is bytes
        if isinstance(encryption_key, str):
            # Try to decode as base64 first (Fernet keys are base64-encoded)
            try:
                encryption_key = base64.urlsafe_b64decode(encryption_key)
            except:
                # If not base64, encode as bytes
                encryption_key = encryption_key.encode()
        
        f = Fernet(encryption_key)
        decrypted_bytes = f.decrypt(encrypted_email.encode())
        decrypted = decrypted_bytes.decode('utf-8')
        
        # Verify it looks like an email after decryption
        if "@" in decrypted and "." in decrypted and len(decrypted) > 5:
            return decrypted
        else:
            # Decrypted but doesn't look like email, might be corrupted
            # Try to return it anyway if it's reasonable length
            if len(decrypted) < 100:  # Reasonable email length
                return decrypted
            print(f"Warning: Decrypted value doesn't look like an email (length: {len(decrypted)}, value: {decrypted[:50]}...)")
            return encrypted_email
    except Exception as e:
        # Any error during decryption - log it for debugging
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"Error: Could not decrypt email. Type: {error_type}, Message: {error_msg}")
        print(f"Encrypted email (first 50 chars): {encrypted_email[:50]}...")
        
        # Return original encrypted value - this indicates a configuration issue
        # The encryption key might not match the one used to encrypt
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

