from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token, create_refresh_token
import redis
import json
import uuid
import logging

logger = logging.getLogger(__name__)


class TokenManager:
    """Manage JWT access and refresh tokens"""

    def __init__(self, config):
        self.config = config
        self.redis_client = None

        # Initialize Redis connection
        try:
            redis_host = config.get('REDIS_HOST', 'redis') if isinstance(config, dict) else config.REDIS_HOST
            redis_port = config.get('REDIS_PORT', 6379) if isinstance(config, dict) else config.REDIS_PORT
            redis_password = config.get('REDIS_PASSWORD', '') if isinstance(config, dict) else config.REDIS_PASSWORD

            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            logger.info("Redis connection established for token management")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    def create_tokens(self, user_id, username, role, ip_address=None, user_agent=None):
        """
        Create access and refresh token pair

        Returns:
            dict: {
                'access_token': str,
                'refresh_token': str,
                'access_token_jti': str,
                'refresh_token_jti': str,
                'expires_in': int (seconds)
            }
        """
        # Generate unique JTIs
        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())

        # Create tokens with additional claims
        access_token = create_access_token(
            identity=user_id,
            additional_claims={
                'jti': access_jti,
                'username': username,
                'role': role,
                'type': 'access'
            }
        )

        refresh_token = create_refresh_token(
            identity=user_id,
            additional_claims={
                'jti': refresh_jti,
                'username': username,
                'role': role,
                'type': 'refresh',
                'access_jti': access_jti
            }
        )

        # Store token metadata in Redis
        jwt_access_expires = self.config.get('JWT_ACCESS_TOKEN_EXPIRES') if isinstance(self.config, dict) else self.config.JWT_ACCESS_TOKEN_EXPIRES
        jwt_refresh_expires = self.config.get('JWT_REFRESH_TOKEN_EXPIRES') if isinstance(self.config, dict) else self.config.JWT_REFRESH_TOKEN_EXPIRES

        access_expires = int(jwt_access_expires.total_seconds())
        refresh_expires = int(jwt_refresh_expires.total_seconds())

        # Store access token metadata
        access_key = f"access_token:{access_jti}"
        access_data = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'ip_address': ip_address or '',
            'user_agent': user_agent or '',
            'refresh_jti': refresh_jti,
            'created_at': datetime.utcnow().isoformat()
        }
        self.redis_client.setex(access_key, access_expires, json.dumps(access_data))

        # Store refresh token metadata
        refresh_key = f"refresh_token:{refresh_jti}"
        refresh_data = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'access_jti': access_jti,
            'ip_address': ip_address or '',
            'user_agent': user_agent or '',
            'created_at': datetime.utcnow().isoformat()
        }
        self.redis_client.setex(refresh_key, refresh_expires, json.dumps(refresh_data))

        # Store user's active tokens (for revocation)
        user_tokens_key = f"user_tokens:{user_id}"
        self.redis_client.sadd(user_tokens_key, access_jti, refresh_jti)
        self.redis_client.expire(user_tokens_key, refresh_expires)

        logger.info(f"Created token pair for user {username} (ID: {user_id})")

        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'access_token_jti': access_jti,
            'refresh_token_jti': refresh_jti,
            'expires_in': access_expires
        }

    def refresh_access_token(self, refresh_jti, ip_address=None, user_agent=None):
        """
        Create new access token from refresh token

        Returns:
            dict or None: New token info or None if refresh token is invalid
        """
        # Get refresh token metadata
        refresh_key = f"refresh_token:{refresh_jti}"
        refresh_data_str = self.redis_client.get(refresh_key)

        if not refresh_data_str:
            logger.warning(f"Refresh token not found or expired: {refresh_jti}")
            return None

        refresh_data = json.loads(refresh_data_str)

        # Revoke old access token
        old_access_jti = refresh_data.get('access_jti')
        if old_access_jti:
            self.revoke_token(old_access_jti)

        # Create new access token
        new_access_jti = str(uuid.uuid4())
        access_token = create_access_token(
            identity=refresh_data['user_id'],
            additional_claims={
                'jti': new_access_jti,
                'username': refresh_data['username'],
                'role': refresh_data['role'],
                'type': 'access'
            }
        )

        # Store new access token metadata
        jwt_access_expires = self.config.get('JWT_ACCESS_TOKEN_EXPIRES') if isinstance(self.config, dict) else self.config.JWT_ACCESS_TOKEN_EXPIRES
        access_expires = int(jwt_access_expires.total_seconds())
        access_key = f"access_token:{new_access_jti}"
        access_data = {
            'user_id': refresh_data['user_id'],
            'username': refresh_data['username'],
            'role': refresh_data['role'],
            'ip_address': ip_address or refresh_data.get('ip_address', ''),
            'user_agent': user_agent or refresh_data.get('user_agent', ''),
            'refresh_jti': refresh_jti,
            'created_at': datetime.utcnow().isoformat()
        }
        self.redis_client.setex(access_key, access_expires, json.dumps(access_data))

        # Update refresh token to reference new access token
        refresh_data['access_jti'] = new_access_jti
        refresh_ttl = self.redis_client.ttl(refresh_key)
        self.redis_client.setex(refresh_key, refresh_ttl, json.dumps(refresh_data))

        # Add new access token to user's active tokens
        user_tokens_key = f"user_tokens:{refresh_data['user_id']}"
        self.redis_client.sadd(user_tokens_key, new_access_jti)

        logger.info(f"Refreshed access token for user {refresh_data['username']}")

        return {
            'access_token': access_token,
            'access_token_jti': new_access_jti,
            'expires_in': access_expires
        }

    def verify_token(self, jti, token_type='access'):
        """Verify if token is valid and not revoked"""
        key = f"{token_type}_token:{jti}"
        return self.redis_client.exists(key) > 0

    def revoke_token(self, jti, token_type='access'):
        """Revoke a specific token"""
        key = f"{token_type}_token:{jti}"
        data_str = self.redis_client.get(key)

        if data_str:
            data = json.loads(data_str)
            self.redis_client.delete(key)

            # Remove from user's active tokens
            user_tokens_key = f"user_tokens:{data['user_id']}"
            self.redis_client.srem(user_tokens_key, jti)

            logger.info(f"Revoked {token_type} token: {jti}")
            return True

        return False

    def revoke_user_tokens(self, user_id):
        """Revoke all tokens for a user"""
        user_tokens_key = f"user_tokens:{user_id}"
        token_jtis = self.redis_client.smembers(user_tokens_key)

        count = 0
        for jti in token_jtis:
            # Try both access and refresh
            if self.revoke_token(jti, 'access'):
                count += 1
            elif self.revoke_token(jti, 'refresh'):
                count += 1

        # Clear user tokens set
        self.redis_client.delete(user_tokens_key)

        logger.info(f"Revoked {count} tokens for user ID: {user_id}")
        return count

    def get_token_info(self, jti, token_type='access'):
        """Get token metadata"""
        key = f"{token_type}_token:{jti}"
        data_str = self.redis_client.get(key)

        if data_str:
            return json.loads(data_str)

        return None

    def get_user_active_sessions(self, user_id):
        """Get all active sessions for a user"""
        user_tokens_key = f"user_tokens:{user_id}"
        token_jtis = self.redis_client.smembers(user_tokens_key)

        sessions = []
        for jti in token_jtis:
            # Check if it's a refresh token (refresh tokens represent sessions)
            token_info = self.get_token_info(jti, 'refresh')
            if token_info:
                sessions.append({
                    'jti': jti,
                    'ip_address': token_info.get('ip_address'),
                    'user_agent': token_info.get('user_agent'),
                    'created_at': token_info.get('created_at')
                })

        return sessions
