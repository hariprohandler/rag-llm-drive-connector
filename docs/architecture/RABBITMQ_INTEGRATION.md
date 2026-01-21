# RabbitMQ Integration for Sync Jobs

## Overview

The system now uses RabbitMQ for reliable, scalable job queue management. This replaces the previous in-memory/threading approach with a production-ready message queue system.

## Architecture

### Components

1. **RabbitMQ Service** (`app/services/rabbitmq_service.py`)
   - Manages RabbitMQ connections
   - Publishes jobs to queues
   - Consumes jobs from queues
   - Handles reconnection and error recovery

2. **Sync Worker** (`app/services/sync_worker.py`)
   - Consumes jobs from RabbitMQ
   - Processes sync jobs (Zendesk, etc.)
   - Updates progress in database
   - Handles job failures and retries

3. **Job Creation** (`app/api/tools_routes.py`)
   - Creates `SyncJob` record in database
   - Publishes job to RabbitMQ queue
   - Returns immediately with job_id

## Benefits

### 1. **Persistent Queues**
- Jobs survive application restarts
- No job loss if worker crashes
- Messages are durable by default

### 2. **Scalability**
- Multiple workers can consume from the same queue
- Load balancing across workers
- Easy horizontal scaling

### 3. **Reliability**
- Automatic message acknowledgments
- Failed jobs can be requeued
- Dead letter queue for failed messages

### 4. **Decoupling**
- Job creation separated from processing
- Workers can be scaled independently
- Better resource utilization

## Configuration

### Environment Variables

```bash
# RabbitMQ connection URL
RABBITMQ_URL=amqp://rabbitmq:rabbitmq@localhost:5672/

# Queue and exchange names (optional, defaults provided)
RABBITMQ_QUEUE_NAME=sync_jobs
RABBITMQ_EXCHANGE=sync_exchange
```

### Docker Compose

RabbitMQ is included in `docker-compose.yml`:

```yaml
rabbitmq:
  image: rabbitmq:3-management-alpine
  ports:
    - "5672:5672"      # AMQP port
    - "15672:15672"    # Management UI
  environment:
    - RABBITMQ_DEFAULT_USER=rabbitmq
    - RABBITMQ_DEFAULT_PASS=rabbitmq
```

## Usage

### Starting a Sync Job

```python
# Job is created in database and published to RabbitMQ
job = create_zendesk_sync_job(
    db=db,
    user_id=user_id,
    sync_scope={"max_tickets": 100},
    priority=5
)
```

### Checking Job Status

```python
# Query database for job status
job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
print(f"Status: {job.status}, Progress: {job.progress_percentage}%")
```

### API Endpoints

- `POST /api/tools/sync` - Start a sync job
- `GET /api/tools/sync/jobs` - List all sync jobs
- `GET /api/tools/sync/jobs/{job_id}` - Get job status

## Queue Structure

### Exchange
- **Name**: `sync_exchange`
- **Type**: `topic`
- **Durable**: Yes

### Queue
- **Name**: `sync_jobs`
- **Durable**: Yes (survives broker restart)
- **Binding**: `sync.job.*`

### Routing Keys
- `sync.job.zendesk` - Zendesk sync jobs
- `sync.job.slack` - Slack sync jobs (future)
- `sync.job.teams` - Teams sync jobs (future)

## Worker Process

The worker automatically starts when the application starts:

```python
# In app.py
from app.services.sync_worker import get_sync_worker
get_sync_worker()  # Starts consuming from RabbitMQ
```

### Worker Behavior

1. Connects to RabbitMQ on startup
2. Consumes messages from `sync_jobs` queue
3. Processes each job in a separate thread
4. Updates progress in database
5. Acknowledges message after successful processing
6. Requeues message on failure (for retry)

## Monitoring

### RabbitMQ Management UI

Access the management UI at: `http://localhost:15672`

- **Username**: `rabbitmq` (default)
- **Password**: `rabbitmq` (default)

### Metrics Available

- Queue depth (pending jobs)
- Message rates (publish/consume)
- Consumer count
- Connection status

## Error Handling

### Connection Failures

- Worker attempts to reconnect automatically
- Jobs remain in queue if worker is down
- No job loss during connection issues

### Processing Failures

- Failed jobs are requeued (up to retry limit)
- Error messages stored in `SyncJob.error_message`
- Job status set to `FAILED` after max retries

## Scaling

### Multiple Workers

To run multiple workers:

1. Deploy multiple application instances
2. Each instance runs a worker
3. RabbitMQ distributes jobs across workers
4. Load balanced automatically

### Worker Configuration

```python
# In docker-compose or k8s
# Run multiple worker containers
worker:
  image: rag-llm-drive-connector:latest
  command: python -m app.services.sync_worker
  environment:
    - RABBITMQ_URL=amqp://rabbitmq:rabbitmq@rabbitmq:5672/
```

## Migration from Threading

The previous threading-based approach has been replaced:

### Before
- Jobs polled from database
- In-memory task tracking
- No persistence if app restarts

### After
- Jobs published to RabbitMQ
- Persistent message queue
- Survives restarts and crashes

## Future Enhancements

1. **Priority Queues**: Different queues for different priorities
2. **Dead Letter Queue**: Handle permanently failed jobs
3. **Scheduled Jobs**: Delay job processing
4. **Job Cancellation**: Cancel jobs in queue
5. **Job Retry Policies**: Configurable retry strategies
