"""
Redis-based Session Manager for tracking user login sessions
"""
import json
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import os


class SessionManager:
    """Manages user sessions in Redis"""

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

    def _session_key(self, token_jti: str) -> str:
        """Generate Redis key for session"""
        return f"session:{token_jti}"

    def _user_sessions_key(self, user_id: int) -> str:
        """Generate Redis key for user's session list"""
        return f"user_sessions:{user_id}"

    def create_session(
        self,
        user_id: int,
        token_jti: str,
        ip_address: str,
        user_agent: str,
        expires_in_hours: int = 24
    ) -> bool:
        """
        Create a new session in Redis

        Args:
            user_id: ID of the user
            token_jti: JWT token ID
            ip_address: Client IP address
            user_agent: Client user agent string
            expires_in_hours: Session expiration time in hours (default: 24)

        Returns:
            bool: True if session created successfully
        """
        if not self.redis_client:
            return False

        now = datetime.utcnow()
        expires_at = now + timedelta(hours=expires_in_hours)

        session_data = {
            'user_id': user_id,
            'token_jti': token_jti,
            'ip_address': ip_address,
            'user_agent': user_agent[:512],  # Limit user agent length
            'login_at': now.isoformat(),
            'last_activity': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'is_active': True
        }

        try:
            # Store session data with expiration
            session_key = self._session_key(token_jti)
            self.redis_client.setex(
                session_key,
                timedelta(hours=expires_in_hours),
                json.dumps(session_data)
            )

            # Add to user's session set
            user_sessions_key = self._user_sessions_key(user_id)
            self.redis_client.sadd(user_sessions_key, token_jti)
            # Set expiration on user sessions set (slightly longer than session)
            self.redis_client.expire(user_sessions_key, timedelta(hours=expires_in_hours + 1))

            return True
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error creating session: {e}")
            return False

    def get_session(self, token_jti: str) -> Optional[Dict[str, Any]]:
        """
        Get session data by token JTI

        Args:
            token_jti: JWT token ID

        Returns:
            dict: Session data or None if not found
        """
        if not self.redis_client:
            return None

        try:
            session_key = self._session_key(token_jti)
            session_json = self.redis_client.get(session_key)

            if session_json:
                session_data = json.loads(session_json)
                # Update last activity
                session_data['last_activity'] = datetime.utcnow().isoformat()
                self.redis_client.set(session_key, json.dumps(session_data), keepttl=True)
                return session_data
            return None
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error getting session: {e}")
            return None

    def get_all_sessions(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all sessions

        Args:
            active_only: If True, only return active sessions (default: True)

        Returns:
            list: List of session data dictionaries
        """
        if not self.redis_client:
            return []

        try:
            sessions = []
            # Get all session keys
            for key in self.redis_client.scan_iter("session:*"):
                session_json = self.redis_client.get(key)
                if session_json:
                    session_data = json.loads(session_json)
                    if not active_only or session_data.get('is_active', False):
                        sessions.append(session_data)

            # Sort by login time (most recent first)
            sessions.sort(key=lambda x: x.get('login_at', ''), reverse=True)
            return sessions
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error getting all sessions: {e}")
            return []

    def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all sessions for a specific user

        Args:
            user_id: User ID

        Returns:
            list: List of session data dictionaries
        """
        if not self.redis_client:
            return []

        try:
            sessions = []
            user_sessions_key = self._user_sessions_key(user_id)
            token_jtis = self.redis_client.smembers(user_sessions_key)

            for token_jti in token_jtis:
                session = self.get_session(token_jti)
                if session:
                    sessions.append(session)

            # Sort by login time (most recent first)
            sessions.sort(key=lambda x: x.get('login_at', ''), reverse=True)
            return sessions
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error getting user sessions: {e}")
            return []

    def terminate_session(self, token_jti: str) -> bool:
        """
        Terminate a specific session

        Args:
            token_jti: JWT token ID

        Returns:
            bool: True if session terminated successfully
        """
        if not self.redis_client:
            return False

        try:
            session = self.get_session(token_jti)
            if not session:
                return False

            # Mark as inactive and update logout time
            session['is_active'] = False
            session['logout_at'] = datetime.utcnow().isoformat()

            session_key = self._session_key(token_jti)
            # Store updated session with shorter TTL (keep for audit purposes)
            self.redis_client.setex(
                session_key,
                timedelta(days=7),  # Keep terminated sessions for 7 days
                json.dumps(session)
            )

            # Remove from user's active sessions
            user_id = session.get('user_id')
            if user_id:
                user_sessions_key = self._user_sessions_key(user_id)
                self.redis_client.srem(user_sessions_key, token_jti)

            return True
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error terminating session: {e}")
            return False

    def terminate_user_sessions(self, user_id: int) -> int:
        """
        Terminate all sessions for a specific user

        Args:
            user_id: User ID

        Returns:
            int: Number of sessions terminated
        """
        if not self.redis_client:
            return 0

        try:
            sessions = self.get_user_sessions(user_id)
            count = 0

            for session in sessions:
                if session.get('is_active'):
                    token_jti = session.get('token_jti')
                    if token_jti and self.terminate_session(token_jti):
                        count += 1

            return count
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error terminating user sessions: {e}")
            return 0

    def is_session_active(self, token_jti: str) -> bool:
        """
        Check if a session is active

        Args:
            token_jti: JWT token ID

        Returns:
            bool: True if session is active
        """
        session = self.get_session(token_jti)
        return session is not None and session.get('is_active', False)

    def get_session_stats(self) -> Dict[str, int]:
        """
        Get session statistics

        Returns:
            dict: Statistics including active_sessions, total_sessions, active_users
        """
        if not self.redis_client:
            return {'active_sessions': 0, 'total_sessions': 0, 'active_users': 0}

        try:
            all_sessions = self.get_all_sessions(active_only=False)
            active_sessions = [s for s in all_sessions if s.get('is_active', False)]
            active_users = len(set(s.get('user_id') for s in active_sessions if s.get('user_id')))

            return {
                'active_sessions': len(active_sessions),
                'total_sessions': len(all_sessions),
                'active_users': active_users
            }
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error getting session stats: {e}")
            return {'active_sessions': 0, 'total_sessions': 0, 'active_users': 0}

    def cleanup_expired_sessions(self):
        """
        Cleanup expired sessions (called by background task)
        Note: Redis TTL handles automatic cleanup, this is for manual cleanup
        """
        if not self.redis_client:
            return

        try:
            now = datetime.utcnow()
            count = 0

            for key in self.redis_client.scan_iter("session:*"):
                session_json = self.redis_client.get(key)
                if session_json:
                    session_data = json.loads(session_json)
                    expires_at = datetime.fromisoformat(session_data.get('expires_at', ''))

                    if expires_at < now:
                        self.redis_client.delete(key)
                        count += 1

            if self.app and count > 0:
                self.app.logger.info(f"Cleaned up {count} expired sessions")
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error cleaning up expired sessions: {e}")


# Global session manager instance
session_manager = SessionManager()
