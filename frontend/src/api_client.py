from enum import StrEnum
from flask import Flask
import requests


class Methods(StrEnum):
    POST = "POST"
    GET = "GET"
    PUT = "PUT"
    DELETE = "DELETE"


class ApiClient:
    def __init__(self, app: Flask):
        self.app = app
        self.base_url = app.config["API_BASE_URL"]
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "AssetTracker-Frontend/1.0"})


        self.app.logger.info(
            f"ApiClient initialized with " + app.config["API_BASE_URL"]
        )

    def set_token(self, token):
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def get(self, path, params=None, timeout=10):
        """Generic GET request"""
        try:
            url = (
                f"{self.base_url}{path}"
                if path.startswith("/")
                else f"{self.base_url}/{path}"
            )
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            self.app.logger.error(f"GET {path} error: {str(e)}")
            raise

    def post(self, path, json=None, data=None, timeout=10):
        """Generic POST request"""
        try:
            url = (
                f"{self.base_url}{path}"
                if path.startswith("/")
                else f"{self.base_url}/{path}"
            )
            response = self.session.post(url, json=json, data=data, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            self.app.logger.error(f"POST {path} error: {str(e)}")
            raise

    def put(self, path, json=None, data=None, timeout=10):
        """Generic PUT request"""
        try:
            url = (
                f"{self.base_url}{path}"
                if path.startswith("/")
                else f"{self.base_url}/{path}"
            )
            response = self.session.put(url, json=json, data=data, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            self.app.logger.error(f"PUT {path} error: {str(e)}")
            raise

    def delete(self, path, timeout=10):
        """Generic DELETE request"""
        try:
            url = (
                f"{self.base_url}{path}"
                if path.startswith("/")
                else f"{self.base_url}/{path}"
            )
            response = self.session.delete(url, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            self.app.logger.error(f"DELETE {path} error: {str(e)}")
            raise

    def login(self, username, password, auth_type='local'):
        """
        Login user with specified authentication type

        Args:
            username (str): Username
            password (str): Password
            auth_type (str): Authentication type - 'local' or 'ad' (default: 'local')

        Returns:
            Response object or None on error
        """
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={
                    "username": username,
                    "password": password,
                    "auth_type": auth_type
                },
                timeout=10,
            )
            return response
        except Exception as e:
            self.app.logger.exception(e)
            return None

    def get_assets(self, filters=None):
        try:
            params = filters or {}
            response = self.session.get(
                f"{self.base_url}/assets", params=params, timeout=10
            )

            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get assets error: {str(e)}")
            raise

    def create_asset(self, asset_data: "Asset"):
        try:
            response = self.session.post(
                f"{self.base_url}/assets", json=asset_data, timeout=10
            )

            self.app.logger.info(self.session)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Create asset error: {str(e)}")
            raise

    def update_asset(self, asset_id, asset_data):
        try:
            response = self.session.put(
                f"{self.base_url}/assets/{asset_id}", json=asset_data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Update asset error: {str(e)}")
            raise

    def get_departments(
        self, page=None, per_page=None, sort_by=None, sort_order=None, search=None
    ):
        try:
            params = {}
            if page:
                params["page"] = page
            if per_page:
                params["per_page"] = per_page
            if sort_by:
                params["sort_by"] = sort_by
            if sort_order:
                params["sort_order"] = sort_order
            if search:
                params["search"] = search

            response = self.session.get(
                f"{self.base_url}/departments", params=params, timeout=10
            )
            response.raise_for_status()

            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get departments error: {str(e)}")
            raise

    def create_department(self, department_data):
        try:
            response = self.session.post(
                f"{self.base_url}/departments", json=department_data, timeout=10
            )

            self.app.logger.info(self.session)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Create department error: {str(e)}")
            raise

    def transfer_asset(self, asset_id, transfer_data):
        try:
            response = self.session.post(
                f"{self.base_url}/assets/{asset_id}/transfer",
                json=transfer_data,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Transfer asset error: {str(e)}")
            raise

    def get_asset_transfers(self, asset_id):
        try:
            response = self.session.get(
                f"{self.base_url}/assets/{asset_id}/transfers", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get asset transfers error: {str(e)}")
            raise

    def get_reports_by_department(self):
        try:
            response = self.session.get(
                f"{self.base_url}/reports/assets-by-department", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get department report error: {str(e)}")
            raise

    def get_reports_by_status(self):
        try:
            response = self.session.get(
                f"{self.base_url}/reports/assets-by-status", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get status report error: {str(e)}")
            raise

    # Users API
    def get_users(
        self,
        page=None,
        per_page=None,
        sort_by=None,
        sort_order=None,
        search=None,
        role=None,
        department_id=None,
        include_deleted=None,
    ):
        try:
            params = {}
            if page:
                params["page"] = page
            if per_page:
                params["per_page"] = per_page
            if sort_by:
                params["sort_by"] = sort_by
            if sort_order:
                params["sort_order"] = sort_order
            if search:
                params["search"] = search
            if role:
                params["role"] = role
            if department_id:
                params["department_id"] = department_id
            if include_deleted is not None:
                params["include_deleted"] = include_deleted

            response = self.session.get(
                f"{self.base_url}/users", params=params, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get users error: {str(e)}")
            raise

    def get_user(self, user_id):
        try:
            response = self.session.get(f"{self.base_url}/users/{user_id}", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get user error: {str(e)}")
            raise

    def create_user(self, user_data):
        try:
            response = self.session.post(
                f"{self.base_url}/auth/register", json=user_data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Try to extract error message from response
            try:
                error_data = e.response.json()
                error_message = error_data.get("message", str(e))
            except:
                error_message = str(e)
            self.app.logger.error(f"Create user error: {error_message}")
            raise Exception(error_message)
        except Exception as e:
            self.app.logger.error(f"Create user error: {str(e)}")
            raise

    def update_user(self, user_id, user_data):
        try:
            response = self.session.put(
                f"{self.base_url}/users/{user_id}", json=user_data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Update user error: {str(e)}")
            raise

    def delete_user(self, user_id):
        try:
            response = self.session.delete(
                f"{self.base_url}/users/{user_id}", timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.app.logger.error(f"Delete user error: {str(e)}")
            raise

    def reset_user_password(self, user_id, password_data):
        try:
            response = self.session.post(
                f"{self.base_url}/users/{user_id}/reset-password",
                json=password_data,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Reset password error: {str(e)}")
            raise

    # Department API
    def get_department(self, department_id):
        try:
            response = self.session.get(
                f"{self.base_url}/departments/{department_id}", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get department error: {str(e)}")
            raise

    def update_department(self, department_id, department_data):
        try:
            response = self.session.put(
                f"{self.base_url}/departments/{department_id}",
                json=department_data,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Update department error: {str(e)}")
            raise

    def delete_department(self, department_id):
        try:
            response = self.session.delete(
                f"{self.base_url}/departments/{department_id}", timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.app.logger.error(f"Delete department error: {str(e)}")
            raise

    # Asset API
    def get_asset(self, asset_id):
        try:
            response = self.session.get(
                f"{self.base_url}/assets/{asset_id}", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get asset error: {str(e)}")
            raise

    def delete_asset(self, asset_id):
        try:
            response = self.session.delete(
                f"{self.base_url}/assets/{asset_id}", timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.app.logger.error(f"Delete asset error: {str(e)}")
            raise

    def mark_asset_inactive(self, asset_id, status, notes=None, condition_notes=None):
        """Mark asset as damaged or disposed and transfer to bad assets department"""
        try:
            data = {"status": status}
            if notes:
                data["notes"] = notes
            if condition_notes:
                data["condition_notes"] = condition_notes

            response = self.session.post(
                f"{self.base_url}/assets/{asset_id}/mark-inactive",
                json=data,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Mark asset inactive error: {str(e)}")
            raise

    def propose_asset_for_liquidation(self, asset_id, propose=True):
        """Propose or unpropose an asset for liquidation"""
        try:
            data = {"propose_for_liquidation": propose}
            response = self.session.post(
                f"{self.base_url}/assets/{asset_id}/propose-liquidation",
                json=data,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Propose asset for liquidation error: {str(e)}")
            raise

    def get_asset_history(self, asset_id):
        try:
            response = self.session.get(
                f"{self.base_url}/assets/{asset_id}/history", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get asset history error: {str(e)}")
            raise

    # Reports API
    def get_asset_report(self, filters=None):
        try:
            params = filters or {}
            response = self.session.get(
                f"{self.base_url}/reports/assets", params=params, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get asset report error: {str(e)}")
            raise

    def get_user_activity_report(self, filters=None):
        try:
            params = filters or {}
            response = self.session.get(
                f"{self.base_url}/reports/user-activities", params=params, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get user activity report error: {str(e)}")
            raise

    def get_dashboard_stats(self):
        try:
            response = self.session.get(
                f"{self.base_url}/reports/dashboard", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get dashboard stats error: {str(e)}")
            raise

    def get_my_assets(self):
        """Get assets assigned to current user (for viewers)"""
        try:
            response = self.session.get(f"{self.base_url}/my-assets", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get my assets error: {str(e)}")
            raise

    def get_my_stats(self):
        """Get stats for current user's assigned assets"""
        try:
            response = self.session.get(f"{self.base_url}/my-assets/stats", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get my stats error: {str(e)}")
            raise

    # Audit Logs API
    def get_audit_logs(self, filters=None):
        """Get audit logs from Redis with optional filters"""
        try:
            params = filters or {}
            response = self.session.get(
                f"{self.base_url}/audit-logs", params=params, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get audit logs error: {str(e)}")
            raise

    def get_archived_logs(self):
        """Get list of archived audit log files"""
        try:
            response = self.session.get(
                f"{self.base_url}/audit-logs/archived", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get archived logs error: {str(e)}")
            raise

    def get_archived_log_content(self, filename):
        """Get content of a specific archived log file"""
        try:
            response = self.session.get(
                f"{self.base_url}/audit-logs/archived/{filename}", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get archived log content error: {str(e)}")
            raise

    def trigger_log_archive(self):
        """Manually trigger archival of old logs"""
        try:
            response = self.session.post(
                f"{self.base_url}/audit-logs/archive", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Trigger archive error: {str(e)}")
            raise

    # Settings API
    def get_settings(self):
        """Get all system settings"""
        try:
            response = self.session.get(f"{self.base_url}/settings", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get settings error: {str(e)}")
            raise

    def update_settings(self, settings_data):
        """Update system settings"""
        try:
            response = self.session.put(
                f"{self.base_url}/settings/bulk",
                json={"settings": settings_data},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Update settings error: {str(e)}")
            raise

    # Profile API
    def update_profile(self, profile_data):
        """Update current user's profile"""
        try:
            response = self.session.put(
                f"{self.base_url}/auth/profile", json=profile_data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Update profile error: {str(e)}")
            raise

    def change_password(self, password_data):
        """Change current user's password"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/change-password", json=password_data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Try to extract error message from response
            try:
                error_data = e.response.json()
                error_message = error_data.get("message", str(e))
            except:
                error_message = str(e)
            self.app.logger.error(f"Change password error: {error_message}")
            raise Exception(error_message)
        except Exception as e:
            self.app.logger.error(f"Change password error: {str(e)}")
            raise

    # Category API
    def get_categories(
        self, page=None, per_page=None, sort_by=None, sort_order=None, search=None
    ):
        try:
            params = {}
            if page:
                params["page"] = page
            if per_page:
                params["per_page"] = per_page
            if sort_by:
                params["sort_by"] = sort_by
            if sort_order:
                params["sort_order"] = sort_order
            if search:
                params["search"] = search

            response = self.session.get(
                f"{self.base_url}/categories", params=params, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get categories error: {str(e)}")
            raise

    def get_category(self, category_id):
        try:
            response = self.session.get(
                f"{self.base_url}/categories/{category_id}", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get category error: {str(e)}")
            raise

    def create_category(self, category_data):
        try:
            response = self.session.post(
                f"{self.base_url}/categories", json=category_data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Create category error: {str(e)}")
            raise

    def update_category(self, category_id, category_data):
        try:
            response = self.session.put(
                f"{self.base_url}/categories/{category_id}",
                json=category_data,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Update category error: {str(e)}")
            raise

    def delete_category(self, category_id):
        try:
            response = self.session.delete(
                f"{self.base_url}/categories/{category_id}", timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.app.logger.error(f"Delete category error: {str(e)}")
            raise

    # Trash Management
    def get_trash_users(self):
        """Get all deleted users"""
        try:
            response = self.session.get(f"{self.base_url}/trash/users", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get trash users error: {str(e)}")
            raise

    def get_trash_departments(self):
        """Get all deleted departments"""
        try:
            response = self.session.get(
                f"{self.base_url}/trash/departments", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get trash departments error: {str(e)}")
            raise

    def get_trash_assets(self):
        """Get all deleted assets"""
        try:
            response = self.session.get(f"{self.base_url}/trash/assets", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get trash assets error: {str(e)}")
            raise

    def restore_user(self, user_id):
        """Restore a deleted user"""
        try:
            response = self.session.post(
                f"{self.base_url}/trash/users/{user_id}/restore", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Restore user error: {str(e)}")
            raise

    def restore_department(self, dept_id):
        """Restore a deleted department"""
        try:
            response = self.session.post(
                f"{self.base_url}/trash/departments/{dept_id}/restore", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Restore department error: {str(e)}")
            raise

    def restore_asset(self, asset_id):
        """Restore a deleted asset"""
        try:
            response = self.session.post(
                f"{self.base_url}/trash/assets/{asset_id}/restore", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Restore asset error: {str(e)}")
            raise

    def permanent_delete_user(self, user_id):
        """Permanently delete a user"""
        try:
            response = self.session.delete(
                f"{self.base_url}/trash/users/{user_id}/permanent-delete", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Permanent delete user error: {str(e)}")
            raise

    def permanent_delete_department(self, dept_id):
        """Permanently delete a department"""
        try:
            response = self.session.delete(
                f"{self.base_url}/trash/departments/{dept_id}/permanent-delete",
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Permanent delete department error: {str(e)}")
            raise

    def permanent_delete_asset(self, asset_id):
        """Permanently delete an asset"""
        try:
            response = self.session.delete(
                f"{self.base_url}/trash/assets/{asset_id}/permanent-delete", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Permanent delete asset error: {str(e)}")
            raise
