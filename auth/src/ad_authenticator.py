from ldap3 import Server, Connection, ALL, NTLM, SIMPLE
from ldap3.core.exceptions import LDAPException
import logging

logger = logging.getLogger(__name__)


class ActiveDirectoryAuthenticator:
    """Handle Active Directory authentication"""

    def __init__(self, config):
        self.config = config
        self.enabled = config.get('AD_ENABLED', False) if isinstance(config, dict) else config.AD_ENABLED
        self.server = None

        if self.enabled:
            try:
                ad_server = config.get('AD_SERVER') if isinstance(config, dict) else config.AD_SERVER
                ad_port = config.get('AD_PORT', 389) if isinstance(config, dict) else config.AD_PORT
                ad_use_ssl = config.get('AD_USE_SSL', False) if isinstance(config, dict) else config.AD_USE_SSL

                self.server = Server(
                    ad_server,
                    port=ad_port,
                    use_ssl=ad_use_ssl,
                    get_info=ALL
                )
                logger.info(f"AD Server configured: {ad_server}:{ad_port}")
            except Exception as e:
                logger.error(f"Failed to configure AD server: {str(e)}")
                self.enabled = False

    def authenticate(self, username, password):
        """
        Authenticate user against Active Directory

        Returns:
            tuple: (success: bool, user_info: dict or None, error: str or None)
        """
        if not self.enabled:
            return False, None, "Active Directory is not enabled"

        if not username or not password:
            return False, None, "Username and password are required"

        try:
            # Build user DN
            user_dn = self._build_user_dn(username)

            # Try to bind with user credentials
            conn = Connection(
                self.server,
                user=user_dn,
                password=password,
                authentication=SIMPLE,
                auto_bind=True
            )

            if conn.bound:
                # Get user information
                user_info = self._get_user_info(conn, username)
                conn.unbind()

                logger.info(f"AD authentication successful for user: {username}")
                return True, user_info, None
            else:
                logger.warning(f"AD authentication failed for user: {username}")
                return False, None, "Invalid credentials"

        except LDAPException as e:
            logger.error(f"AD authentication error for {username}: {str(e)}")
            return False, None, f"Authentication error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during AD authentication: {str(e)}")
            return False, None, "Authentication failed"

    def _build_user_dn(self, username):
        """Build user distinguished name"""
        ad_user_dn = self.config.get('AD_USER_DN') if isinstance(self.config, dict) else self.config.AD_USER_DN
        ad_base_dn = self.config.get('AD_BASE_DN') if isinstance(self.config, dict) else self.config.AD_BASE_DN

        if ad_user_dn:
            # Use configured user DN template
            return ad_user_dn.format(username=username)
        else:
            # Default: username@domain or cn=username,base_dn
            if '@' in ad_base_dn:
                return f"{username}@{ad_base_dn}"
            else:
                return f"cn={username},{ad_base_dn}"

    def _get_user_info(self, conn, username):
        """Retrieve user information from AD"""
        try:
            # Search for user
            search_filter_template = self.config.get('AD_USER_SEARCH_FILTER', '(sAMAccountName={username})') if isinstance(self.config, dict) else self.config.AD_USER_SEARCH_FILTER
            ad_base_dn = self.config.get('AD_BASE_DN') if isinstance(self.config, dict) else self.config.AD_BASE_DN

            search_filter = search_filter_template.format(username=username)
            conn.search(
                search_base=ad_base_dn,
                search_filter=search_filter,
                attributes=['cn', 'mail', 'displayName', 'memberOf', 'sAMAccountName']
            )

            if conn.entries:
                entry = conn.entries[0]
                user_info = {
                    'username': str(entry.sAMAccountName) if hasattr(entry, 'sAMAccountName') else username,
                    'email': str(entry.mail) if hasattr(entry, 'mail') else f"{username}@domain.local",
                    'fullname': str(entry.displayName) if hasattr(entry, 'displayName') else str(entry.cn),
                    'groups': [str(group) for group in entry.memberOf] if hasattr(entry, 'memberOf') else []
                }
                return user_info

        except Exception as e:
            logger.error(f"Error retrieving user info for {username}: {str(e)}")

        # Return basic info if search fails
        return {
            'username': username,
            'email': f"{username}@domain.local",
            'fullname': username,
            'groups': []
        }

    def search_users(self, search_term):
        """Search for users in AD"""
        if not self.enabled:
            return []

        try:
            # Use bind user for search
            ad_bind_user = self.config.get('AD_BIND_USER') if isinstance(self.config, dict) else self.config.AD_BIND_USER
            ad_bind_password = self.config.get('AD_BIND_PASSWORD') if isinstance(self.config, dict) else self.config.AD_BIND_PASSWORD
            ad_base_dn = self.config.get('AD_BASE_DN') if isinstance(self.config, dict) else self.config.AD_BASE_DN

            conn = Connection(
                self.server,
                user=ad_bind_user,
                password=ad_bind_password,
                auto_bind=True
            )

            search_filter = f"(&(objectClass=user)(|(sAMAccountName=*{search_term}*)(displayName=*{search_term}*)(mail=*{search_term}*)))"
            conn.search(
                search_base=ad_base_dn,
                search_filter=search_filter,
                attributes=['sAMAccountName', 'mail', 'displayName']
            )

            users = []
            for entry in conn.entries:
                users.append({
                    'username': str(entry.sAMAccountName),
                    'email': str(entry.mail) if hasattr(entry, 'mail') else '',
                    'fullname': str(entry.displayName) if hasattr(entry, 'displayName') else ''
                })

            conn.unbind()
            return users

        except Exception as e:
            logger.error(f"Error searching AD users: {str(e)}")
            return []

    def get_user_groups(self, username):
        """Get user's AD groups"""
        if not self.enabled:
            return []

        try:
            ad_bind_user = self.config.get('AD_BIND_USER') if isinstance(self.config, dict) else self.config.AD_BIND_USER
            ad_bind_password = self.config.get('AD_BIND_PASSWORD') if isinstance(self.config, dict) else self.config.AD_BIND_PASSWORD
            ad_base_dn = self.config.get('AD_BASE_DN') if isinstance(self.config, dict) else self.config.AD_BASE_DN
            search_filter_template = self.config.get('AD_USER_SEARCH_FILTER', '(sAMAccountName={username})') if isinstance(self.config, dict) else self.config.AD_USER_SEARCH_FILTER

            conn = Connection(
                self.server,
                user=ad_bind_user,
                password=ad_bind_password,
                auto_bind=True
            )

            search_filter = search_filter_template.format(username=username)
            conn.search(
                search_base=ad_base_dn,
                search_filter=search_filter,
                attributes=['memberOf']
            )

            groups = []
            if conn.entries:
                entry = conn.entries[0]
                if hasattr(entry, 'memberOf'):
                    groups = [str(group) for group in entry.memberOf]

            conn.unbind()
            return groups

        except Exception as e:
            logger.error(f"Error getting user groups: {str(e)}")
            return []
