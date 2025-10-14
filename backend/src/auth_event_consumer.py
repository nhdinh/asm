"""
Auth Event Consumer for Backend
Listens to auth events and syncs profile data
"""

import json
import logging
from message_broker import MessageBroker
from models import db, Profile, ProfileRole
from flask import current_app

logger = logging.getLogger(__name__)


class AuthEventConsumer:
    """Consumes auth.user.* events and syncs to backend database"""

    def __init__(self, app):
        self.app = app
        self.broker = MessageBroker()

    def start(self):
        """Start consuming auth events"""
        try:
            # Connect to RabbitMQ
            if not self.broker.connect():
                logger.error("Failed to connect to RabbitMQ for auth event consumer")
                return False

            # Subscribe to auth.user.* events
            success = self.broker.subscribe(
                exchange=MessageBroker.AUTH_EVENTS_EXCHANGE,
                routing_keys=["auth.user.*"],
                queue_name="backend_auth_events_queue",
                callback=self.handle_auth_event
            )

            if success:
                logger.info("Auth event consumer subscribed successfully")
                # Start consuming in background thread
                self.broker.start_consuming_thread()
                return True
            else:
                logger.error("Failed to subscribe to auth events")
                return False

        except Exception as e:
            logger.error(f"Error starting auth event consumer: {str(e)}")
            return False

    def handle_auth_event(self, ch, method, properties, body):
        """
        Handle incoming auth event

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
                if event_type == "auth.user.updated":
                    self._handle_auth_user_updated(event_data)
                elif event_type == "auth.user.deleted":
                    self._handle_auth_user_deleted(event_data)
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
            logger.error(f"Error processing auth event: {str(e)}", exc_info=True)
            # Negative acknowledge and requeue for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _handle_auth_user_updated(self, event_data):
        """
        Handle auth.user.updated event
        Sync user info from auth to backend profile
        """
        username = event_data.get("username")
        old_username = event_data.get("old_username", username)

        # Find profile by old username (in case username was changed)
        profile = Profile.query.filter_by(username=old_username, deleted_at=None).first()

        if not profile:
            logger.warning(f"Profile {old_username} not found in backend database")
            return

        # Update profile fields
        changed = False

        if "username" in event_data and event_data["username"] != profile.username:
            # Check if new username already exists
            existing = Profile.query.filter_by(username=event_data["username"]).first()
            if existing and existing.id != profile.id:
                logger.error(f"Cannot update username to {event_data['username']}: already exists")
            else:
                profile.username = event_data["username"]
                changed = True

        if "email" in event_data and event_data["email"] != profile.email:
            profile.email = event_data["email"]
            changed = True

        if "fullname" in event_data and event_data.get("fullname") != profile.fullname:
            profile.fullname = event_data.get("fullname")
            changed = True

        if "role" in event_data:
            try:
                role = ProfileRole[event_data["role"].upper()]
                if role != profile.role:
                    profile.role = role
                    changed = True
            except KeyError:
                logger.error(f"Invalid role: {event_data['role']}")

        if changed:
            db.session.commit()
            logger.info(f"Updated profile {username} in backend database from auth event")
        else:
            logger.info(f"No changes needed for profile {username}")

    def _handle_auth_user_deleted(self, event_data):
        """
        Handle auth.user.deleted event
        Soft delete profile in backend database
        """
        username = event_data.get("username")
        soft_delete = event_data.get("soft_delete", True)

        profile = Profile.query.filter_by(username=username, deleted_at=None).first()

        if not profile:
            logger.warning(f"Profile {username} not found in backend database")
            return

        if soft_delete:
            # Soft delete
            from datetime import datetime
            profile.deleted_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"Soft deleted profile {username} in backend database")
        else:
            # Hard delete (not recommended)
            db.session.delete(profile)
            db.session.commit()
            logger.info(f"Hard deleted profile {username} in backend database")

    def stop(self):
        """Stop consuming events"""
        try:
            self.broker.stop_consuming()
            self.broker.disconnect()
            logger.info("Auth event consumer stopped")
        except Exception as e:
            logger.error(f"Error stopping auth event consumer: {str(e)}")


# Global consumer instance
auth_event_consumer = None


def init_auth_event_consumer(app):
    """Initialize and start auth event consumer"""
    global auth_event_consumer

    try:
        auth_event_consumer = AuthEventConsumer(app)
        success = auth_event_consumer.start()

        if success:
            logger.info("Auth event consumer initialized successfully")
        else:
            logger.error("Failed to initialize auth event consumer")

        return success

    except Exception as e:
        logger.error(f"Error initializing auth event consumer: {str(e)}")
        return False
