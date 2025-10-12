"""
Auth Service Client
Handles communication with the authentication microservice
"""

import requests
import logging
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


class AuthServiceClient:
    """Client for communicating with auth microservice"""

    def __init__(self, auth_service_url: str = "http://auth:5001/api/auth"):
        self.auth_service_url = auth_service_url
        self.timeout = 10  # seconds

    def login(self, username: str, password: str, auth_type: str = "local") -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Authenticate user via auth service

        Returns:
            Tuple[bool, Optional[Dict], Optional[str]]: (success, response_data, error_message)
        """
        try:
            response = requests.post(
                f"{self.auth_service_url}/login",
                json={
                    "username": username,
                    "password": password,
                    "auth_type": auth_type
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Auth service login successful for user: {username}")
                return True, data, None
            else:
                error_msg = response.json().get('message', 'Authentication failed')
                logger.warning(f"Auth service login failed for {username}: {error_msg}")
                return False, None, error_msg

        except requests.RequestException as e:
            logger.error(f"Auth service request error: {str(e)}")
            return False, None, f"Auth service unavailable: {str(e)}"

    def verify_token(self, access_token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Verify token with auth service

        Returns:
            Tuple[bool, Optional[Dict]]: (valid, user_data)
        """
        try:
            response = requests.post(
                f"{self.auth_service_url}/verify",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('valid'):
                    return True, data.get('user')

            return False, None

        except requests.RequestException as e:
            logger.error(f"Token verification error: {str(e)}")
            return False, None

    def refresh_token(self, refresh_token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Refresh access token

        Returns:
            Tuple[bool, Optional[Dict]]: (success, token_data)
        """
        try:
            response = requests.post(
                f"{self.auth_service_url}/refresh",
                headers={"Authorization": f"Bearer {refresh_token}"},
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                logger.info("Token refreshed successfully")
                return True, data
            else:
                logger.warning("Token refresh failed")
                return False, None

        except requests.RequestException as e:
            logger.error(f"Token refresh error: {str(e)}")
            return False, None

    def logout(self, access_token: str, revoke_all: bool = False) -> bool:
        """
        Logout and revoke tokens

        Returns:
            bool: Success status
        """
        try:
            response = requests.post(
                f"{self.auth_service_url}/logout",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"revoke_all": revoke_all},
                timeout=self.timeout
            )

            if response.status_code == 200:
                logger.info("Logout successful")
                return True
            else:
                logger.warning("Logout failed")
                return False

        except requests.RequestException as e:
            logger.error(f"Logout error: {str(e)}")
            return False

    def get_sessions(self, access_token: str) -> Optional[Dict]:
        """
        Get active sessions for user

        Returns:
            Optional[Dict]: Sessions data or None
        """
        try:
            response = requests.get(
                f"{self.auth_service_url}/sessions",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except requests.RequestException as e:
            logger.error(f"Get sessions error: {str(e)}")
            return None

    def create_user(self, access_token: str, user_data: Dict) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Create a new user in auth service

        Args:
            access_token: Admin JWT token
            user_data: Dict containing username, email, password, fullname, role, user_type

        Returns:
            Tuple[bool, Optional[Dict], Optional[str]]: (success, user_data, error_message)
        """
        try:
            response = requests.post(
                f"{self.auth_service_url}/users",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=user_data,
                timeout=self.timeout
            )

            if response.status_code == 201:
                data = response.json()
                logger.info(f"User created successfully in auth service: {user_data.get('username')}")
                return True, data.get('user'), None
            else:
                error_data = response.json()
                error_msg = error_data.get('message', 'User creation failed')
                logger.warning(f"Auth service user creation failed: {error_msg}")
                return False, None, error_msg

        except requests.RequestException as e:
            logger.error(f"Auth service user creation error: {str(e)}")
            return False, None, f"Auth service unavailable: {str(e)}"

    def get_user_by_username(self, access_token: str, username: str) -> Tuple[bool, Optional[Dict]]:
        """
        Get user information by username from auth service

        Returns:
            Tuple[bool, Optional[Dict]]: (success, user_data)
        """
        try:
            response = requests.get(
                f"{self.auth_service_url}/users/{username}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return True, data.get('user')
            else:
                return False, None

        except requests.RequestException as e:
            logger.error(f"Get user by username error: {str(e)}")
            return False, None


# Global auth client instance
auth_client = AuthServiceClient()
