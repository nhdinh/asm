"""
User Event Consumer for Auth Service
Listens to user events from Backend and syncs user data
"""

import json
import logging
from message_broker import MessageBroker
from models import db, User, UserType
from flask import current_app

logger = logging.getLogger(__name__)


class UserEventConsumer:
    """Consumes user.* events from backend and syncs to auth database"""

    def __init__(self, app):
        self.app = app
        self.broker = MessageBroker()

    def start(self):
        """Start consuming user events"""
        try:
            # Connect to RabbitMQ
            if not self.broker.connect():
                logger.error("Failed to connect to RabbitMQ for user event consumer")
                return False

            # Subscribe to user.* events
            success = self.broker.subscribe(
                exchange=MessageBroker.USER_EVENTS_EXCHANGE,
                routing_keys=["user.*"],
                queue_name="auth_user_events_queue",
                callback=self.handle_user_event
            )

            if success:
                logger.info("User event consumer subscribed successfully")
                # Start consuming in background thread
                self.broker.start_consuming_thread()
                return True
            else:
                logger.error("Failed to subscribe to user events")
                return False

        except Exception as e:
            logger.error(f"Error starting user event consumer: {str(e)}")
            return False

    def handle_user_event(self, ch, method, properties, body):
        """
        Handle incoming user event

        Args:
            ch: Channel
            method: Delivery method
            properties: Message properties
            body: Message body
        """
        try:
            # Parse message
            event_data = json.loads(body)
            event_type = method.routing_key
            username = event_data.get("username")

            logger.info(f"Received {event_type} event for user: {username}")

            # Process event based on type
            with self.app.app_context():
                if event_type == "user.created":
                    self._handle_user_created(event_data)
                elif event_type == "user.updated":
                    self._handle_user_updated(event_data)
                elif event_type == "user.deleted":
                    self._handle_user_deleted(event_data)
                else:
                    logger.warning(f"Unknown event type: {event_type}")

            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Successfully processed {event_type} for {username}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse event message: {str(e)}")
            # Reject and don't requeue malformed messages
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        except Exception as e:
            logger.error(f"Error processing user event: {str(e)}", exc_info=True)
            # Negative acknowledge and requeue for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _handle_user_created(self, event_data):
        """
        Handle user.created event
        Note: User should already exist in auth DB (created via auth service first)
        This is a no-op but we log it for audit purposes
        """
        username = event_data.get("username")

        # Check if user exists in auth database
        user = User.query.filter_by(username=username).first()

        if user:
            logger.info(f"User {username} already exists in auth DB (expected)")
        else:
            logger.warning(
                f"User {username} does not exist in auth DB. "
                "This should not happen - user should be created in auth service first."
            )

    def _handle_user_updated(self, event_data):
        """
        Handle user.updated event
        Sync user info from backend to auth database
        """
        username = event_data.get("username")
        old_username = event_data.get("old_username", username)

        # Find user by old username (in case username was changed)
        user = User.query.filter_by(username=old_username, deleted_at=None).first()

        if not user:
            logger.warning(f"User {old_username} not found in auth database")
            return

        # Update user fields
        changed = False

        if "username" in event_data and event_data["username"] != user.username:
            # Check if new username already exists
            existing = User.query.filter_by(username=event_data["username"]).first()
            if existing and existing.id != user.id:
                logger.error(f"Cannot update username to {event_data['username']}: already exists")
            else:
                user.username = event_data["username"]
                changed = True

        if "email" in event_data and event_data["email"] != user.email:
            user.email = event_data["email"]
            changed = True

        if "fullname" in event_data and event_data.get("fullname") != user.fullname:
            user.fullname = event_data.get("fullname")
            changed = True

        if "role" in event_data and event_data["role"] != user.role:
            user.role = event_data["role"]
            changed = True

        if changed:
            db.session.commit()
            logger.info(f"Updated user {username} in auth database from event")
        else:
            logger.info(f"No changes needed for user {username}")

    def _handle_user_deleted(self, event_data):
        """
        Handle user.deleted event
        Soft delete user in auth database
        """
        username = event_data.get("username")
        soft_delete = event_data.get("soft_delete", True)

        user = User.query.filter_by(username=username, deleted_at=None).first()

        if not user:
            logger.warning(f"User {username} not found in auth database")
            return

        if soft_delete:
            # Soft delete
            from datetime import datetime
            user.deleted_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"Soft deleted user {username} in auth database")
        else:
            # Hard delete (not recommended)
            db.session.delete(user)
            db.session.commit()
            logger.info(f"Hard deleted user {username} in auth database")

    def stop(self):
        """Stop consuming events"""
        try:
            self.broker.stop_consuming()
            self.broker.disconnect()
            logger.info("User event consumer stopped")
        except Exception as e:
            logger.error(f"Error stopping user event consumer: {str(e)}")


# Global consumer instance
user_event_consumer = None


def init_user_event_consumer(app):
    """Initialize and start user event consumer"""
    global user_event_consumer

    try:
        user_event_consumer = UserEventConsumer(app)
        success = user_event_consumer.start()

        if success:
            logger.info("User event consumer initialized successfully")
        else:
            logger.error("Failed to initialize user event consumer")

        return success

    except Exception as e:
        logger.error(f"Error initializing user event consumer: {str(e)}")
        return False
