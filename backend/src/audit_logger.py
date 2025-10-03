"""
Audit Logger for tracking all database changes
Logs are stored in Redis and archived to files every 30 days
"""
import json
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import os


class AuditLogger:
    def __init__(self, app=None):
        self.redis_client = None
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize Redis connection from Flask app config"""
        redis_host = os.getenv('REDIS_HOST', 'redis')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_password = None

        # Read Redis password from file if exists
        redis_password_file = os.getenv('REDIS_PASSWORD_FILE')
        if redis_password_file and os.path.exists(redis_password_file):
            with open(redis_password_file, 'r') as f:
                redis_password = f.read().strip()

        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True
        )
        self.app = app

    def log(
        self,
        user_id: int,
        username: str,
        action: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """
        Log an audit event to Redis

        Args:
            user_id: ID of user performing action
            username: Username performing action
            action: Action type (create, update, delete, etc.)
            entity_type: Type of entity (user, asset, department, etc.)
            entity_id: ID of entity being modified
            old_values: Dict of old field values (for updates)
            new_values: Dict of new field values (for creates/updates)
            details: Additional details about the action
            ip_address: IP address of user
        """
        if not self.redis_client:
            if self.app:
                self.app.logger.warning("Redis not configured for audit logging")
            return

        timestamp = datetime.utcnow()

        audit_entry = {
            'timestamp': timestamp.isoformat(),
            'user_id': user_id,
            'username': username,
            'action': action,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'old_values': old_values or {},
            'new_values': new_values or {},
            'details': details,
            'ip_address': ip_address
        }

        try:
            # Store in Redis sorted set with timestamp as score
            key = 'audit_logs'
            score = timestamp.timestamp()
            value = json.dumps(audit_entry, ensure_ascii=False)

            self.redis_client.zadd(key, {value: score})

            # Also maintain a count
            self.redis_client.incr('audit_logs:count')

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to log audit entry: {str(e)}")

    def get_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ):
        """
        Retrieve audit logs from Redis with filters

        Returns list of audit log entries
        """
        if not self.redis_client:
            return []

        try:
            # Get score range
            if start_date:
                min_score = start_date.timestamp()
            else:
                min_score = '-inf'

            if end_date:
                max_score = end_date.timestamp()
            else:
                max_score = '+inf'

            # Get logs from Redis sorted set
            raw_logs = self.redis_client.zrevrangebyscore(
                'audit_logs',
                max_score,
                min_score,
                start=offset,
                num=limit
            )

            logs = []
            for raw_log in raw_logs:
                log_entry = json.loads(raw_log)

                # Apply filters
                if user_id and log_entry.get('user_id') != user_id:
                    continue
                if action and log_entry.get('action') != action:
                    continue
                if entity_type and log_entry.get('entity_type') != entity_type:
                    continue

                logs.append(log_entry)

            return logs

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to retrieve audit logs: {str(e)}")
            return []

    def get_count(self):
        """Get total count of audit logs in Redis"""
        if not self.redis_client:
            return 0

        try:
            return int(self.redis_client.get('audit_logs:count') or 0)
        except:
            return 0

    def archive_old_logs(self, days: int = 30, archive_dir: str = '/app/logs/audit'):
        """
        Archive logs older than specified days to file

        Args:
            days: Archive logs older than this many days
            archive_dir: Directory to save archive files
        """
        if not self.redis_client:
            return 0

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            cutoff_score = cutoff_date.timestamp()

            # Get old logs
            old_logs = self.redis_client.zrangebyscore(
                'audit_logs',
                '-inf',
                cutoff_score
            )

            if not old_logs:
                return 0

            # Create archive directory
            os.makedirs(archive_dir, exist_ok=True)

            # Create archive file
            archive_filename = f"audit_logs_{cutoff_date.strftime('%Y%m%d')}.jsonl"
            archive_path = os.path.join(archive_dir, archive_filename)

            # Write to file (JSON Lines format)
            with open(archive_path, 'a', encoding='utf-8') as f:
                for log in old_logs:
                    f.write(log + '\n')

            # Remove from Redis
            removed = self.redis_client.zremrangebyscore(
                'audit_logs',
                '-inf',
                cutoff_score
            )

            if self.app:
                self.app.logger.info(
                    f"Archived {removed} audit logs to {archive_path}"
                )

            return removed

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to archive logs: {str(e)}")
            return 0

    def read_archived_logs(
        self,
        archive_file: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ):
        """
        Read logs from an archived file

        Args:
            archive_file: Path to archive file
            filters: Dict of filters (user_id, action, entity_type, etc.)
            limit: Maximum number of logs to return
        """
        logs = []
        filters = filters or {}

        try:
            with open(archive_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if len(logs) >= limit:
                        break

                    log_entry = json.loads(line.strip())

                    # Apply filters
                    match = True
                    for key, value in filters.items():
                        if log_entry.get(key) != value:
                            match = False
                            break

                    if match:
                        logs.append(log_entry)

            return logs

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to read archived logs: {str(e)}")
            return []


# Global instance
audit_logger = AuditLogger()
