"""RabbitMQ service for job queue management."""
import json
import logging
import pika
from typing import Optional, Dict, Any, Callable
from pika.connection import URLParameters
from pika.exceptions import AMQPConnectionError, AMQPChannelError

from app.core.config import settings

logger = logging.getLogger(__name__)


class RabbitMQService:
    """Service for managing RabbitMQ connections and queues."""
    
    def __init__(self):
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.channel.Channel] = None
        self._connected = False
    
    def connect(self) -> bool:
        """Establish connection to RabbitMQ."""
        if self._connected and self._connection and not self._connection.is_closed:
            return True
        
        try:
            # Parse connection URL
            params = URLParameters(settings.rabbitmq_url)
            
            # Create connection
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()
            
            # Declare exchange (topic exchange for routing)
            self._channel.exchange_declare(
                exchange=settings.rabbitmq_exchange,
                exchange_type='topic',
                durable=True
            )
            
            # Declare queue (durable for persistence)
            self._channel.queue_declare(
                queue=settings.rabbitmq_queue_name,
                durable=True  # Queue survives broker restart
            )
            
            # Bind queue to exchange
            self._channel.queue_bind(
                exchange=settings.rabbitmq_exchange,
                queue=settings.rabbitmq_queue_name,
                routing_key='sync.job.*'  # Route all sync jobs
            )
            
            # Set QoS to process one message at a time per worker
            self._channel.basic_qos(prefetch_count=1)
            
            self._connected = True
            logger.info("Connected to RabbitMQ successfully")
            return True
            
        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to RabbitMQ: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Close RabbitMQ connection."""
        try:
            if self._channel and not self._channel.is_closed:
                self._channel.close()
            if self._connection and not self._connection.is_closed:
                self._connection.close()
            self._connected = False
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")
    
    def publish_job(self, job_id: int, job_data: Dict[str, Any]) -> bool:
        """
        Publish a sync job to the queue.
        
        Args:
            job_id: Sync job ID
            job_data: Job data dictionary
            
        Returns:
            True if published successfully, False otherwise
        """
        if not self.connect():
            return False
        
        try:
            message = {
                "job_id": job_id,
                **job_data
            }
            
            # Publish with routing key based on source type
            routing_key = f"sync.job.{job_data.get('source_type', 'unknown')}"
            
            self._channel.basic_publish(
                exchange=settings.rabbitmq_exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"Published job {job_id} to RabbitMQ queue")
            return True
            
        except AMQPChannelError as e:
            logger.error(f"Channel error publishing job {job_id}: {e}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Error publishing job {job_id}: {e}")
            return False
    
    def consume_jobs(self, callback: Callable[[Dict[str, Any]], None], auto_ack: bool = False):
        """
        Start consuming jobs from the queue.
        
        Args:
            callback: Function to call when a job is received
            auto_ack: If True, automatically acknowledge messages
        """
        if not self.connect():
            logger.error("Cannot consume jobs: not connected to RabbitMQ")
            return
        
        def on_message(channel, method, properties, body):
            """Handle incoming message."""
            try:
                message = json.loads(body.decode('utf-8'))
                logger.info(f"Received job {message.get('job_id')} from queue")
                
                # Call the callback
                callback(message)
                
                # Acknowledge message if not auto-ack
                if not auto_ack:
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode message: {e}")
                if not auto_ack:
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # Requeue on error (so it can be retried)
                if not auto_ack:
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        try:
            # Start consuming
            self._channel.basic_consume(
                queue=settings.rabbitmq_queue_name,
                on_message_callback=on_message,
                auto_ack=auto_ack
            )
            
            logger.info(f"Started consuming from queue: {settings.rabbitmq_queue_name}")
            self._channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Stopped consuming (interrupted)")
            self._channel.stop_consuming()
        except Exception as e:
            logger.error(f"Error consuming jobs: {e}")
            self._connected = False
    
    def stop_consuming(self):
        """Stop consuming messages."""
        if self._channel and not self._channel.is_closed:
            self._channel.stop_consuming()
            logger.info("Stopped consuming from queue")
    
    def is_connected(self) -> bool:
        """Check if connected to RabbitMQ."""
        if not self._connected:
            return False
        if not self._connection or self._connection.is_closed:
            self._connected = False
            return False
        return True


# Global RabbitMQ service instance
_rabbitmq_service: Optional[RabbitMQService] = None


def get_rabbitmq_service() -> RabbitMQService:
    """Get or create the global RabbitMQ service instance."""
    global _rabbitmq_service
    if _rabbitmq_service is None:
        _rabbitmq_service = RabbitMQService()
    return _rabbitmq_service
