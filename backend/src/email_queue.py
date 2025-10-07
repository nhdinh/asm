"""
Email Queue Module - Manages async email sending via Redis queue
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import redis
from flask import current_app

logger = logging.getLogger(__name__)


class EmailQueue:
    """Redis-based email queue for asynchronous email sending"""

    QUEUE_KEY = "email:queue"
    PROCESSING_KEY = "email:processing"
    FAILED_KEY = "email:failed"

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize email queue with Redis client"""
        self.redis = redis_client

    def _get_redis(self) -> redis.Redis:
        """Get Redis client from app context or instance"""
        if self.redis:
            return self.redis

        # Try to get from Flask app context
        try:
            return current_app.extensions.get('redis')
        except RuntimeError:
            # No app context available
            raise RuntimeError("Redis client not available. Initialize EmailQueue with redis_client or call from Flask app context")

    def enqueue_welcome_email(
        self,
        user_email: str,
        username: str,
        password: str,
        fullname: Optional[str] = None,
        priority: int = 5
    ) -> bool:
        """
        Enqueue a welcome email to be sent asynchronously

        Args:
            user_email: Recipient email address
            username: Username for login
            password: Temporary password
            fullname: User's full name
            priority: Priority level (1=highest, 10=lowest)

        Returns:
            True if successfully enqueued, False otherwise
        """
        email_task = {
            "type": "welcome_email",
            "data": {
                "user_email": user_email,
                "username": username,
                "password": password,
                "fullname": fullname
            },
            "priority": priority,
            "enqueued_at": datetime.utcnow().isoformat(),
            "retry_count": 0
        }

        return self._enqueue_task(email_task)

    def enqueue_password_reset_email(
        self,
        user_email: str,
        username: str,
        reset_token: str,
        fullname: Optional[str] = None,
        priority: int = 3
    ) -> bool:
        """
        Enqueue a password reset email

        Args:
            user_email: Recipient email address
            username: Username
            reset_token: Password reset token
            fullname: User's full name
            priority: Priority level (1=highest, 10=lowest)

        Returns:
            True if successfully enqueued, False otherwise
        """
        email_task = {
            "type": "password_reset",
            "data": {
                "user_email": user_email,
                "username": username,
                "reset_token": reset_token,
                "fullname": fullname
            },
            "priority": priority,
            "enqueued_at": datetime.utcnow().isoformat(),
            "retry_count": 0
        }

        return self._enqueue_task(email_task)

    def enqueue_test_email(
        self,
        user_email: str,
        priority: int = 1
    ) -> bool:
        """
        Enqueue a test email (high priority)

        Args:
            user_email: Recipient email address
            priority: Priority level (default 1 for immediate sending)

        Returns:
            True if successfully enqueued, False otherwise
        """
        email_task = {
            "type": "test_email",
            "data": {
                "user_email": user_email
            },
            "priority": priority,
            "enqueued_at": datetime.utcnow().isoformat(),
            "retry_count": 0
        }

        return self._enqueue_task(email_task)

    def _enqueue_task(self, task: Dict[str, Any]) -> bool:
        """
        Internal method to enqueue a task to Redis

        Args:
            task: Task dictionary with type, data, priority, etc.

        Returns:
            True if successfully enqueued, False otherwise
        """
        try:
            redis_client = self._get_redis()
            task_json = json.dumps(task)

            # Use sorted set for priority queue
            # Score = priority (lower = higher priority) + timestamp for FIFO within same priority
            score = task["priority"] * 1000000000 + int(datetime.utcnow().timestamp())

            redis_client.zadd(self.QUEUE_KEY, {task_json: score})

            logger.info(f"Enqueued email task: type={task['type']}, email={task['data'].get('user_email')}")
            return True

        except Exception as e:
            logger.error(f"Failed to enqueue email task: {str(e)}")
            return False

    def dequeue_task(self, processing_timeout: int = 300) -> Optional[Dict[str, Any]]:
        """
        Dequeue the highest priority task from the queue

        Args:
            processing_timeout: Timeout in seconds for task processing

        Returns:
            Task dictionary or None if queue is empty
        """
        try:
            redis_client = self._get_redis()

            # Get highest priority task (lowest score)
            tasks = redis_client.zrange(self.QUEUE_KEY, 0, 0, withscores=True)

            if not tasks:
                return None

            task_json, score = tasks[0]
            task = json.loads(task_json)

            # Move to processing queue
            redis_client.zrem(self.QUEUE_KEY, task_json)
            redis_client.setex(
                f"{self.PROCESSING_KEY}:{task['data'].get('user_email')}:{int(datetime.utcnow().timestamp())}",
                processing_timeout,
                task_json
            )

            return task

        except Exception as e:
            logger.error(f"Failed to dequeue email task: {str(e)}")
            return None

    def mark_task_completed(self, task: Dict[str, Any]) -> bool:
        """
        Mark a task as completed (remove from processing queue)

        Args:
            task: Task dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client = self._get_redis()
            task_json = json.dumps(task)

            # Remove from processing (pattern match)
            processing_keys = redis_client.keys(f"{self.PROCESSING_KEY}:*")
            for key in processing_keys:
                value = redis_client.get(key)
                if value == task_json.encode():
                    redis_client.delete(key)
                    logger.info(f"Marked task as completed: type={task['type']}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to mark task as completed: {str(e)}")
            return False

    def mark_task_failed(self, task: Dict[str, Any], error_message: str, max_retries: int = 3) -> bool:
        """
        Mark a task as failed and optionally retry

        Args:
            task: Task dictionary
            error_message: Error message for logging
            max_retries: Maximum retry attempts before giving up

        Returns:
            True if task will be retried, False if permanently failed
        """
        try:
            redis_client = self._get_redis()
            task["retry_count"] = task.get("retry_count", 0) + 1
            task["last_error"] = error_message
            task["last_failed_at"] = datetime.utcnow().isoformat()

            # Remove from processing queue
            self.mark_task_completed(task)

            if task["retry_count"] < max_retries:
                # Re-enqueue with lower priority (higher score)
                task["priority"] = task.get("priority", 5) + 2  # Decrease priority
                self._enqueue_task(task)
                logger.warning(f"Task failed, retrying ({task['retry_count']}/{max_retries}): {error_message}")
                return True
            else:
                # Move to failed queue for manual review
                task_json = json.dumps(task)
                redis_client.lpush(self.FAILED_KEY, task_json)
                redis_client.ltrim(self.FAILED_KEY, 0, 999)  # Keep last 1000 failures
                logger.error(f"Task permanently failed after {max_retries} retries: {error_message}")
                return False

        except Exception as e:
            logger.error(f"Failed to mark task as failed: {str(e)}")
            return False

    def get_queue_size(self) -> int:
        """Get the number of tasks in the queue"""
        try:
            redis_client = self._get_redis()
            return redis_client.zcard(self.QUEUE_KEY)
        except Exception as e:
            logger.error(f"Failed to get queue size: {str(e)}")
            return 0

    def get_processing_count(self) -> int:
        """Get the number of tasks currently being processed"""
        try:
            redis_client = self._get_redis()
            return len(redis_client.keys(f"{self.PROCESSING_KEY}:*"))
        except Exception as e:
            logger.error(f"Failed to get processing count: {str(e)}")
            return 0

    def get_failed_count(self) -> int:
        """Get the number of permanently failed tasks"""
        try:
            redis_client = self._get_redis()
            return redis_client.llen(self.FAILED_KEY)
        except Exception as e:
            logger.error(f"Failed to get failed count: {str(e)}")
            return 0

    def clear_failed_tasks(self) -> bool:
        """Clear all permanently failed tasks"""
        try:
            redis_client = self._get_redis()
            redis_client.delete(self.FAILED_KEY)
            logger.info("Cleared failed tasks queue")
            return True
        except Exception as e:
            logger.error(f"Failed to clear failed tasks: {str(e)}")
            return False


# Global email queue instance
email_queue = EmailQueue()
