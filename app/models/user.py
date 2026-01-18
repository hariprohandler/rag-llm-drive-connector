"""User model."""
from sqlalchemy import Column, String, DateTime, Boolean
from datetime import datetime
from app.models.base import Base


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)  # User ID (email or OAuth ID)
    email = Column(String, unique=True, nullable=False, index=True)  # Encrypted email
    email_hash = Column(String, unique=True, nullable=True, index=True)  # Hash for lookups (deterministic)
    name = Column(String, nullable=True)
    provider = Column(String, nullable=False)  # 'google' or 'microsoft'
    provider_id = Column(String, nullable=False, index=True)  # OAuth provider user ID
    picture = Column(String, nullable=True)  # Profile picture URL
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self, decrypt_email_field: bool = True):
        """
        Convert user to dictionary.
        
        Args:
            decrypt_email_field: If True, decrypt email before returning (default: True)
        """
        email_value = self.email
        if decrypt_email_field and self.email:
            # Always attempt to decrypt - decrypt_email handles both encrypted and plain text emails
            # It will return plain text if already decrypted, or decrypt if encrypted
            try:
                from app.services.email_encryption import decrypt_email
                email_value = decrypt_email(self.email)
                
                # Verify decryption worked - if still encrypted (starts with gAAAAA), log error
                if email_value and email_value.startswith('gAAAAA'):
                    print(f"ERROR: Email decryption failed for user {self.id}. Email still appears encrypted.")
                    print(f"  This usually means the ENCRYPTION_KEY environment variable doesn't match the key used to encrypt.")
            except Exception as e:
                print(f"ERROR: Exception during email decryption for user {self.id}: {type(e).__name__}: {e}")
                # Keep encrypted value if decryption fails
                email_value = self.email
        
        return {
            "id": self.id,
            "email": email_value,
            "name": self.name,
            "provider": self.provider,
            "picture": self.picture,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

