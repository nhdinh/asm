"""
Scheduled jobs for background tasks
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from audit_logger import audit_logger
import logging

# Create scheduler instance
scheduler = BackgroundScheduler()

# Setup logging for scheduler
logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.INFO)


def archive_monthly_logs():
    """
    Archive audit logs older than 30 days
    Runs on the 1st of every month at midnight
    """
    try:
        count = audit_logger.archive_old_logs(days=30)
        print(f"[Scheduler] Archived {count} audit logs")
    except Exception as e:
        print(f"[Scheduler] Failed to archive logs: {str(e)}")


def start_scheduler():
    """Start the background scheduler"""
    # Archive logs on the 1st of every month at midnight
    scheduler.add_job(
        func=archive_monthly_logs,
        trigger=CronTrigger(day=1, hour=0, minute=0),
        id='archive_monthly_logs',
        name='Archive audit logs monthly',
        replace_existing=True
    )

    scheduler.start()
    print("[Scheduler] Background scheduler started")


def stop_scheduler():
    """Stop the background scheduler"""
    scheduler.shutdown()
    print("[Scheduler] Background scheduler stopped")
