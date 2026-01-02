"""MongoDB activity logging with sensitive data protection."""
from pymongo import MongoClient
from pymongo.collection import Collection
from datetime import datetime
from typing import Optional, Dict, Any, List
import config
import json
import re
from cryptography.fernet import Fernet
import base64
import hashlib
import os


class SensitiveDataHandler:
    """Handles sensitive data redaction and encryption."""
    
    # Patterns to identify sensitive data
    SENSITIVE_PATTERNS = [
        r'password["\s:=]+([^"\'}\s,]+)',
        r'api[_-]?key["\s:=]+([^"\'}\s,]+)',
        r'token["\s:=]+([^"\'}\s,]+)',
        r'secret["\s:=]+([^"\'}\s,]+)',
        r'authorization["\s:=]+([^"\'}\s,]+)',
        r'bearer\s+([a-zA-Z0-9\-._~+/]+)',
        r'access[_-]?token["\s:=]+([^"\'}\s,]+)',
        r'refresh[_-]?token["\s:=]+([^"\'}\s,]+)',
    ]
    
    # Fields that should always be redacted
    REDACTED_FIELDS = [
        'password', 'api_key', 'apiKey', 'access_token', 'refresh_token',
        'token', 'secret', 'authorization', 'credentials', 'client_secret',
        'jwt', 'bearer_token', 'oauth_token'
    ]
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize with optional encryption key."""
        if encryption_key:
            self.encryption_key = encryption_key.encode()
        else:
            # Generate or use default key from config
            key_str = os.getenv('LOG_ENCRYPTION_KEY', config.settings.jwt_secret_key or 'default-key-change-in-production')
            # Generate a key from the string (for consistency)
            key_hash = hashlib.sha256(key_str.encode()).digest()
            self.encryption_key = base64.urlsafe_b64encode(key_hash)
        
        try:
            self.cipher = Fernet(self.encryption_key)
            self.encryption_enabled = True
        except Exception:
            self.cipher = None
            self.encryption_enabled = False
    
    def redact_string(self, text: str) -> str:
        """Redact sensitive patterns from a string."""
        if not text:
            return text
        
        result = text
        for pattern in self.SENSITIVE_PATTERNS:
            result = re.sub(pattern, lambda m: m.group(0).split(m.group(1))[0] + '[REDACTED]', result, flags=re.IGNORECASE)
        
        return result
    
    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact sensitive fields from a dictionary."""
        if not isinstance(data, dict):
            return data
        
        redacted = {}
        for key, value in data.items():
            # Check if key should be redacted
            key_lower = key.lower()
            should_redact = any(field in key_lower for field in self.REDACTED_FIELDS)
            
            if should_redact:
                redacted[key] = '[REDACTED]'
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [self.redact_dict(item) if isinstance(item, dict) else self.redact_string(str(item)) for item in value]
            elif isinstance(value, str):
                redacted[key] = self.redact_string(value)
            else:
                redacted[key] = value
        
        return redacted
    
    def encrypt_sensitive(self, data: str) -> str:
        """Encrypt sensitive data (optional, for fields that need to be encrypted)."""
        if not self.encryption_enabled or not data:
            return data
        
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception:
            return '[ENCRYPTION_FAILED]'
    
    def sanitize_for_logging(self, data: Any) -> Any:
        """Main method to sanitize data for logging."""
        if isinstance(data, dict):
            return self.redact_dict(data)
        elif isinstance(data, str):
            return self.redact_string(data)
        elif isinstance(data, list):
            return [self.sanitize_for_logging(item) for item in data]
        else:
            return data


class ActivityLogger:
    """MongoDB-based activity logger."""
    
    def __init__(self):
        """Initialize MongoDB connection and collections."""
        self.mongodb_url = config.settings.mongodb_url
        self.database_name = config.settings.mongodb_database
        self.client: Optional[MongoClient] = None
        self.db = None
        self.auth_logs: Optional[Collection] = None
        self.query_logs: Optional[Collection] = None
        self.data_handler = SensitiveDataHandler()
        
        try:
            self.client = MongoClient(self.mongodb_url, serverSelectionTimeoutMS=5000)
            self.db = self.client[self.database_name]
            self.auth_logs = self.db['auth_activities']
            self.query_logs = self.db['query_activities']
            
            # Create indexes
            self.auth_logs.create_index("user_id")
            self.auth_logs.create_index("timestamp")
            self.auth_logs.create_index("auth_action")
            
            self.query_logs.create_index("user_id")
            self.query_logs.create_index("timestamp")
            self.query_logs.create_index("collection_name")
            
        except Exception as e:
            # If MongoDB is not available, log to console (for development)
            print(f"Warning: MongoDB connection failed: {e}. Logging disabled.")
            self.client = None
    
    def is_connected(self) -> bool:
        """Check if MongoDB is connected."""
        if not self.client:
            return False
        try:
            self.client.server_info()
            return True
        except Exception:
            return False
    
    def log_auth_activity(
        self,
        auth_action: str,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        provider: Optional[str] = None,
        status: str = "success",
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log authentication activity."""
        if not self.is_connected():
            return
        
        log_entry = {
            "timestamp": datetime.utcnow(),
            "auth_action": auth_action,  # e.g., 'login', 'logout', 'token_created', 'token_verified'
            "user_id": user_id,
            "status": status,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "provider": provider,
        }
        
        # Sanitize and add metadata
        if metadata:
            log_entry["metadata"] = self.data_handler.sanitize_for_logging(metadata)
        
        # Add error if present (redacted)
        if error:
            log_entry["error"] = self.data_handler.redact_string(str(error))
        
        # Sanitize user_agent (may contain sensitive info)
        if user_agent:
            log_entry["user_agent"] = self.data_handler.redact_string(user_agent)
        
        # Don't log email directly, use hash if needed
        if email:
            log_entry["email_hash"] = hashlib.sha256(email.encode()).hexdigest()[:16]
        
        try:
            self.auth_logs.insert_one(log_entry)
        except Exception as e:
            print(f"Error logging auth activity: {e}")
    
    def log_query_activity(
        self,
        query: str,
        user_id: str,
        collection_name: Optional[str] = None,
        answer: Optional[str] = None,
        status: str = "success",
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_time_ms: Optional[float] = None
    ):
        """Log query activity."""
        if not self.is_connected():
            return
        
        log_entry = {
            "timestamp": datetime.utcnow(),
            "user_id": user_id,
            "query": query,  # Query text is safe to log
            "status": status,
            "collection_name": collection_name,
            "ip_address": ip_address,
            "response_time_ms": response_time_ms,
        }
        
        # Sanitize metadata (may contain file paths, etc.)
        if metadata:
            log_entry["metadata"] = self.data_handler.sanitize_for_logging(metadata)
        
        # Log answer length instead of full answer (to save space and avoid sensitive data)
        if answer:
            log_entry["answer_length"] = len(answer)
            # Store truncated answer (first 200 chars) for debugging, but sanitized
            log_entry["answer_preview"] = self.data_handler.redact_string(answer[:200])
        
        # Add error if present (redacted)
        if error:
            log_entry["error"] = self.data_handler.redact_string(str(error))
        
        # Sanitize user_agent
        if user_agent:
            log_entry["user_agent"] = self.data_handler.redact_string(user_agent)
        
        try:
            self.query_logs.insert_one(log_entry)
        except Exception as e:
            print(f"Error logging query activity: {e}")
    
    def get_user_auth_logs(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Get authentication logs for a user."""
        if not self.is_connected():
            return []
        
        try:
            logs = list(self.auth_logs.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit))
            
            # Convert ObjectId to string
            for log in logs:
                log['_id'] = str(log['_id'])
            
            return logs
        except Exception as e:
            print(f"Error retrieving auth logs: {e}")
            return []
    
    def get_user_query_logs(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Get query logs for a user."""
        if not self.is_connected():
            return []
        
        try:
            logs = list(self.query_logs.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit))
            
            # Convert ObjectId to string
            for log in logs:
                log['_id'] = str(log['_id'])
            
            return logs
        except Exception as e:
            print(f"Error retrieving query logs: {e}")
            return []
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()


# Global logger instance
_logger_instance: Optional[ActivityLogger] = None


def get_logger() -> ActivityLogger:
    """Get global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ActivityLogger()
    return _logger_instance


def get_client_ip(request) -> Optional[str]:
    """Extract client IP from request."""
    if not request:
        return None
    
    # Check for forwarded IPs (from proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client IP
    if hasattr(request.client, 'host'):
        return request.client.host
    
    return None


def get_user_agent(request) -> Optional[str]:
    """Extract user agent from request."""
    if not request:
        return None
    return request.headers.get("User-Agent")

