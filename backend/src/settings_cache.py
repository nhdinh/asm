"""
Settings Cache Manager
Manages SystemSetting caching in Redis to reduce PostgreSQL load
"""
import json
import redis
from typing import Optional, Dict, Any, List
import os


class SettingsCache:
    """Manages SystemSetting caching in Redis"""

    CACHE_PREFIX = "system_setting:"
    ALL_SETTINGS_KEY = "system_settings:all"
    CACHE_TTL = 3600  # 1 hour TTL for cache

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

    def get_setting(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get a single setting from Redis cache

        Args:
            key: Setting key to retrieve

        Returns:
            Dict containing setting data or None if not found
        """
        if not self.redis_client:
            return None

        try:
            cache_key = f"{self.CACHE_PREFIX}{key}"
            cached_data = self.redis_client.get(cache_key)

            if cached_data:
                return json.loads(cached_data)

            return None

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to get setting from cache: {str(e)}")
            return None

    def set_setting(self, key: str, setting_data: Dict[str, Any]) -> bool:
        """
        Store a single setting in Redis cache

        Args:
            key: Setting key
            setting_data: Dict containing setting data (id, key, value, description, data_type, etc.)

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            cache_key = f"{self.CACHE_PREFIX}{key}"
            self.redis_client.setex(
                cache_key,
                self.CACHE_TTL,
                json.dumps(setting_data, ensure_ascii=False)
            )

            # Invalidate all settings cache when individual setting changes
            self.invalidate_all_settings()

            return True

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to cache setting: {str(e)}")
            return False

    def get_all_settings(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all settings from Redis cache

        Returns:
            List of setting dicts or None if not cached
        """
        if not self.redis_client:
            return None

        try:
            cached_data = self.redis_client.get(self.ALL_SETTINGS_KEY)

            if cached_data:
                return json.loads(cached_data)

            return None

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to get all settings from cache: {str(e)}")
            return None

    def set_all_settings(self, settings_list: List[Dict[str, Any]]) -> bool:
        """
        Store all settings in Redis cache

        Args:
            settings_list: List of setting dicts

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.setex(
                self.ALL_SETTINGS_KEY,
                self.CACHE_TTL,
                json.dumps(settings_list, ensure_ascii=False)
            )

            # Also cache individual settings
            for setting in settings_list:
                setting_key = setting.get('key')
                if setting_key:
                    cache_key = f"{self.CACHE_PREFIX}{setting_key}"
                    self.redis_client.setex(
                        cache_key,
                        self.CACHE_TTL,
                        json.dumps(setting, ensure_ascii=False)
                    )

            return True

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to cache all settings: {str(e)}")
            return False

    def invalidate_setting(self, key: str) -> bool:
        """
        Invalidate a single setting in cache

        Args:
            key: Setting key to invalidate

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            cache_key = f"{self.CACHE_PREFIX}{key}"
            self.redis_client.delete(cache_key)

            # Also invalidate all settings cache
            self.invalidate_all_settings()

            return True

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to invalidate setting cache: {str(e)}")
            return False

    def invalidate_all_settings(self) -> bool:
        """
        Invalidate all settings cache

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.delete(self.ALL_SETTINGS_KEY)
            return True

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to invalidate all settings cache: {str(e)}")
            return False

    def clear_all_caches(self) -> bool:
        """
        Clear all setting-related caches

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            # Delete all settings cache
            self.redis_client.delete(self.ALL_SETTINGS_KEY)

            # Delete individual setting caches
            pattern = f"{self.CACHE_PREFIX}*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)

            return True

        except Exception as e:
            if self.app:
                self.app.logger.error(f"Failed to clear all setting caches: {str(e)}")
            return False


# Global instance
settings_cache = SettingsCache()
