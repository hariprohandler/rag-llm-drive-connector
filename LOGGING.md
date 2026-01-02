# Activity Logging Documentation

This application uses MongoDB to log all user activities, including authentication and query operations. All sensitive information is redacted or encrypted before being stored.

## Overview

- **Storage**: MongoDB
- **Collections**: 
  - `auth_activities` - Authentication and authorization events
  - `query_activities` - Query and RAG operations

## Sensitive Data Protection

### Redaction

The following types of sensitive data are automatically redacted from logs:

- Passwords, API keys, tokens, secrets
- Authorization headers
- OAuth tokens
- Client secrets
- JWT tokens (only metadata logged, not the token itself)

### Encryption (Optional)

Sensitive fields can be encrypted using Fernet (symmetric encryption) by setting `LOG_ENCRYPTION_KEY` environment variable.

### Email Handling

Email addresses are hashed (SHA-256, first 16 chars) rather than stored in plain text for privacy.

## Logged Activities

### Authentication Activities

The following authentication events are logged:

- `oauth_initiated` - OAuth flow started
- `oauth_callback` - OAuth callback received
- `token_created` - JWT token created
- `token_verified` - JWT token verified
- `user_created` - New user registered
- `user_updated` - User information updated
- `user_retrieval` - User lookup (only failures logged)

**Logged Fields:**
- `timestamp` - When the event occurred
- `auth_action` - Type of authentication action
- `user_id` - User identifier (if available)
- `email_hash` - Hashed email (first 16 chars of SHA-256)
- `provider` - OAuth provider (google/microsoft)
- `status` - success/failure
- `error` - Error message (redacted, if failure)
- `ip_address` - Client IP address
- `user_agent` - User agent string (redacted)
- `metadata` - Additional metadata (redacted)

### Query Activities

All RAG queries are logged:

- `timestamp` - When the query was made
- `user_id` - User who made the query
- `query` - The query text (safe to log)
- `collection_name` - Vector collection used
- `status` - success/failure
- `answer_length` - Length of the answer (not the full answer)
- `answer_preview` - First 200 characters (redacted)
- `metadata` - Sources, file names, etc. (redacted)
- `error` - Error message (redacted, if failure)
- `ip_address` - Client IP address
- `user_agent` - User agent string (redacted)
- `response_time_ms` - Query response time in milliseconds

## Configuration

### Environment Variables

```bash
# MongoDB connection
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=rag_activity_logs

# Optional: Encryption key for sensitive fields
LOG_ENCRYPTION_KEY=your-secret-key-here
```

### MongoDB Setup

**Using Docker:**
```bash
docker run -d --name mongodb \
  -p 27017:27017 \
  -e MONGO_INITDB_DATABASE=rag_activity_logs \
  mongo:latest
```

**Using Docker Compose:**
Add to your `docker-compose.yml`:
```yaml
services:
  mongodb:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db

volumes:
  mongodb_data:
```

## Querying Logs

### Get User Authentication Logs

```python
from activity_logger import get_logger

logger = get_logger()
logs = logger.get_user_auth_logs(user_id="google_12345", limit=100)
```

### Get User Query Logs

```python
from activity_logger import get_logger

logger = get_logger()
logs = logger.get_user_query_logs(user_id="google_12345", limit=100)
```

### Using MongoDB Shell

```javascript
// Get recent auth logs
db.auth_activities.find().sort({timestamp: -1}).limit(10)

// Get logs for a specific user
db.auth_activities.find({user_id: "google_12345"}).sort({timestamp: -1})

// Get failed queries
db.query_activities.find({status: "failure"}).sort({timestamp: -1})

// Get slow queries (>5 seconds)
db.query_activities.find({response_time_ms: {$gt: 5000}}).sort({timestamp: -1})
```

## Data Retention

Consider implementing data retention policies:

```javascript
// Delete logs older than 90 days
db.auth_activities.deleteMany({
  timestamp: { $lt: new Date(Date.now() - 90*24*60*60*1000) }
})

db.query_activities.deleteMany({
  timestamp: { $lt: new Date(Date.now() - 90*24*60*60*1000) }
})
```

Or create a TTL index:

```javascript
// Auto-delete after 90 days
db.auth_activities.createIndex(
  { "timestamp": 1 },
  { expireAfterSeconds: 7776000 }  // 90 days
)
```

## Security Best Practices

1. **Encryption Key**: Use a strong, random encryption key in production
2. **MongoDB Security**: 
   - Enable authentication on MongoDB
   - Use TLS/SSL for connections
   - Restrict network access
3. **Access Control**: Limit who can access logs
4. **Regular Backups**: Backup MongoDB regularly
5. **Monitoring**: Monitor log size and performance

## Privacy Compliance

- No sensitive credentials stored in plain text
- Email addresses are hashed
- IP addresses logged for security (can be anonymized if needed)
- User agents sanitized
- All metadata redacted before storage

## Troubleshooting

### MongoDB Not Connected

If MongoDB is not available, the application will continue to work but logging will be disabled. Check:

1. MongoDB service is running
2. Connection string is correct
3. Network connectivity
4. Authentication credentials (if enabled)

### High Log Volume

If log volume is high:

1. Increase MongoDB resources
2. Implement log rotation
3. Reduce log retention period
4. Use MongoDB sharding for large deployments

## Example Log Entry

```json
{
  "_id": ObjectId("..."),
  "timestamp": ISODate("2024-01-15T10:30:00Z"),
  "auth_action": "oauth_callback",
  "user_id": "google_12345",
  "email_hash": "a1b2c3d4e5f6g7h8",
  "provider": "google",
  "status": "success",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0 [REDACTED]",
  "metadata": {
    "redirect_uri": "http://localhost:8000/auth/callback/google"
  }
}
```

