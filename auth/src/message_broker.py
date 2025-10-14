"""
Message Broker Client for RabbitMQ
Handles pub/sub events between backend and auth services
"""

import pika
import json
import logging
import os
from typing import Dict, Callable, Optional
from threading import Thread
import time

logger = logging.getLogger(__name__)


class MessageBroker:
    """RabbitMQ message broker client for event-driven architecture"""

    # Exchange names
    USER_EVENTS_EXCHANGE = "user_events"
    AUTH_EVENTS_EXCHANGE = "auth_events"

    # Event types
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"

    AUTH_USER_UPDATED = "auth.user.updated"
    AUTH_USER_DELETED = "auth.user.deleted"

    def __init__(self):
        """Initialize message broker connection"""
        self.host = os.getenv("RABBITMQ_HOST", "localhost")
        self.port = int(os.getenv("RABBITMQ_PORT", 5672))
        self.user = os.getenv("RABBITMQ_USER", "admin")
        self.password = os.getenv("RABBITMQ_PASSWORD", "admin123")
        self.vhost = os.getenv("RABBITMQ_VHOST", "/")

        self.connection = None
        self.channel = None
        self.consumer_thread = None
        self.is_consuming = False

        logger.info(f"MessageBroker initialized for {self.host}:{self.port}")

    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(self.user, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare exchanges
            self.channel.exchange_declare(
                exchange=self.USER_EVENTS_EXCHANGE,
                exchange_type="topic",
                durable=True
            )
            self.channel.exchange_declare(
                exchange=self.AUTH_EVENTS_EXCHANGE,
                exchange_type="topic",
                durable=True
            )

            logger.info("Connected to RabbitMQ successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            return False

    def disconnect(self):
        """Close RabbitMQ connection"""
        try:
            self.is_consuming = False
            if self.consumer_thread and self.consumer_thread.is_alive():
                self.consumer_thread.join(timeout=5)

            if self.channel and self.channel.is_open:
                self.channel.close()
            if self.connection and self.connection.is_open:
                self.connection.close()

            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {str(e)}")

    def publish(self, exchange: str, routing_key: str, message: Dict):
        """
        Publish a message to an exchange

        Args:
            exchange: Exchange name
            routing_key: Routing key (e.g., "user.created")
            message: Message payload as dict
        """
        try:
            if not self.channel or not self.channel.is_open:
                if not self.connect():
                    logger.error("Cannot publish: not connected to RabbitMQ")
                    return False

            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type="application/json"
                )
            )

            logger.info(f"Published {routing_key} to {exchange}: {message.get('username', 'N/A')}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            return False

    def subscribe(self, exchange: str, routing_keys: list, queue_name: str, callback: Callable):
        """
        Subscribe to messages from an exchange

        Args:
            exchange: Exchange name
            routing_keys: List of routing key patterns (e.g., ["user.*"])
            queue_name: Queue name for this subscriber
            callback: Callback function(ch, method, properties, body)
        """
        try:
            if not self.channel or not self.channel.is_open:
                if not self.connect():
                    logger.error("Cannot subscribe: not connected to RabbitMQ")
                    return False

            # Declare queue
            self.channel.queue_declare(queue=queue_name, durable=True)

            # Bind queue to exchange with routing keys
            for routing_key in routing_keys:
                self.channel.queue_bind(
                    exchange=exchange,
                    queue=queue_name,
                    routing_key=routing_key
                )

            # Set QoS
            self.channel.basic_qos(prefetch_count=1)

            # Set up consumer
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=callback,
                auto_ack=False
            )

            logger.info(f"Subscribed to {exchange} with routing keys: {routing_keys}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe: {str(e)}")
            return False

    def start_consuming(self):
        """Start consuming messages (blocking)"""
        try:
            self.is_consuming = True
            logger.info("Starting to consume messages...")
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Interrupted")
            self.stop_consuming()
        except Exception as e:
            logger.error(f"Error while consuming: {str(e)}")
            self.stop_consuming()

    def start_consuming_thread(self):
        """Start consuming messages in a separate thread"""
        self.consumer_thread = Thread(target=self.start_consuming, daemon=True)
        self.consumer_thread.start()
        logger.info("Consumer thread started")

    def stop_consuming(self):
        """Stop consuming messages"""
        try:
            self.is_consuming = False
            if self.channel and self.channel.is_open:
                self.channel.stop_consuming()
            logger.info("Stopped consuming messages")
        except Exception as e:
            logger.error(f"Error stopping consumer: {str(e)}")

    # Convenience methods for publishing specific events

    def publish_user_created(self, user_data: Dict):
        """Publish user.created event"""
        return self.publish(
            self.USER_EVENTS_EXCHANGE,
            self.USER_CREATED,
            user_data
        )

    def publish_user_updated(self, user_data: Dict):
        """Publish user.updated event"""
        return self.publish(
            self.USER_EVENTS_EXCHANGE,
            self.USER_UPDATED,
            user_data
        )

    def publish_user_deleted(self, user_data: Dict):
        """Publish user.deleted event"""
        return self.publish(
            self.USER_EVENTS_EXCHANGE,
            self.USER_DELETED,
            user_data
        )

    def publish_auth_user_updated(self, user_data: Dict):
        """Publish auth.user.updated event"""
        return self.publish(
            self.AUTH_EVENTS_EXCHANGE,
            self.AUTH_USER_UPDATED,
            user_data
        )

    def publish_auth_user_deleted(self, user_data: Dict):
        """Publish auth.user.deleted event"""
        return self.publish(
            self.AUTH_EVENTS_EXCHANGE,
            self.AUTH_USER_DELETED,
            user_data
        )


# Global message broker instance
message_broker = MessageBroker()
