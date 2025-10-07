"""
Email Worker - Background service for processing email queue
"""
import os
import sys
import time
import logging
import signal
from datetime import datetime
from typing import Dict, Any

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from email_queue import EmailQueue
from email_utils import send_welcome_email, send_test_email
from models import EmailConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/email_worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EmailWorker:
    """Background worker for processing email queue"""

    def __init__(self):
        self.running = True
        self.app = None
        self.email_queue = None

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def initialize(self):
        """Initialize Flask app and email queue"""
        logger.info("Initializing email worker...")

        # Create Flask app
        self.app = create_app()

        # Initialize email queue with Redis from app context
        with self.app.app_context():
            redis_client = self.app.extensions.get('redis')
            if not redis_client:
                logger.error("Redis client not found in app extensions")
                sys.exit(1)

            self.email_queue = EmailQueue(redis_client=redis_client)
            logger.info("Email worker initialized successfully")

    def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a single email task

        Args:
            task: Task dictionary from queue

        Returns:
            True if successful, False otherwise
        """
        task_type = task.get("type")
        task_data = task.get("data", {})

        logger.info(f"Processing task: type={task_type}, email={task_data.get('user_email')}")

        try:
            with self.app.app_context():
                # Check if email is enabled
                config = EmailConfig.query.first()
                if not config or not config.enabled:
                    logger.warning("Email configuration not enabled, skipping task")
                    # Don't retry if email is disabled
                    self.email_queue.mark_task_completed(task)
                    return True

                # Process based on task type
                if task_type == "welcome_email":
                    success = send_welcome_email(
                        user_email=task_data["user_email"],
                        username=task_data["username"],
                        password=task_data["password"],
                        fullname=task_data.get("fullname")
                    )

                elif task_type == "test_email":
                    success = send_test_email(
                        config=config,
                        recipient_email=task_data["user_email"]
                    )

                elif task_type == "password_reset":
                    # TODO: Implement password reset email
                    logger.warning(f"Password reset email not yet implemented")
                    success = False

                else:
                    logger.error(f"Unknown task type: {task_type}")
                    success = False

                if success:
                    logger.info(f"Successfully processed task: type={task_type}")
                    self.email_queue.mark_task_completed(task)
                    return True
                else:
                    logger.error(f"Failed to process task: type={task_type}")
                    self.email_queue.mark_task_failed(
                        task,
                        error_message="Email sending failed"
                    )
                    return False

        except Exception as e:
            logger.exception(f"Error processing task: {str(e)}")
            self.email_queue.mark_task_failed(
                task,
                error_message=str(e)
            )
            return False

    def run(self, poll_interval: int = 5, batch_size: int = 10):
        """
        Run the email worker main loop

        Args:
            poll_interval: Seconds to wait between queue polls
            batch_size: Maximum tasks to process per iteration
        """
        logger.info(f"Email worker started (poll_interval={poll_interval}s, batch_size={batch_size})")

        with self.app.app_context():
            while self.running:
                try:
                    # Get queue stats
                    queue_size = self.email_queue.get_queue_size()
                    processing_count = self.email_queue.get_processing_count()
                    failed_count = self.email_queue.get_failed_count()

                    if queue_size > 0:
                        logger.info(f"Queue stats - pending: {queue_size}, processing: {processing_count}, failed: {failed_count}")

                    # Process batch of tasks
                    processed = 0
                    while processed < batch_size and self.running:
                        task = self.email_queue.dequeue_task()

                        if not task:
                            break

                        self.process_task(task)
                        processed += 1

                    if processed > 0:
                        logger.info(f"Processed {processed} tasks")

                    # Wait before next poll
                    time.sleep(poll_interval)

                except Exception as e:
                    logger.exception(f"Error in worker main loop: {str(e)}")
                    time.sleep(poll_interval)

        logger.info("Email worker stopped")

    def run_once(self):
        """Process all pending tasks once and exit (useful for testing)"""
        logger.info("Running email worker in one-shot mode")

        with self.app.app_context():
            queue_size = self.email_queue.get_queue_size()
            logger.info(f"Processing {queue_size} pending tasks...")

            processed = 0
            while True:
                task = self.email_queue.dequeue_task()
                if not task:
                    break

                self.process_task(task)
                processed += 1

            logger.info(f"Processed {processed} tasks, exiting")


def main():
    """Main entry point for email worker"""
    # Parse command line arguments
    poll_interval = int(os.getenv("EMAIL_WORKER_POLL_INTERVAL", "5"))
    batch_size = int(os.getenv("EMAIL_WORKER_BATCH_SIZE", "10"))
    one_shot = os.getenv("EMAIL_WORKER_ONE_SHOT", "false").lower() == "true"

    # Create and initialize worker
    worker = EmailWorker()
    worker.initialize()

    # Run worker
    if one_shot:
        worker.run_once()
    else:
        worker.run(poll_interval=poll_interval, batch_size=batch_size)


if __name__ == "__main__":
    main()
