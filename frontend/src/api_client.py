from enum import StrEnum
from flask import Flask, session


class Keys:
    ACCESS_TOKEN = "access_token"
    USERNAME = "username"
    PASSWORD = "password"

    LOGIN_PATH = "/auth/login"
    LOGOUT_PATH = "/logout"


class Methods(StrEnum):
    POST = "POST"
    GET = "GET"
    PUT = "PUT"
    DELETE = "DELETE"


class ApiClient:
    def __init__(self, app: Flask):
        self.app = app
        self.base_url = app.config["API_BASE_URL"]
        self.session = session

    def url(self, key: str, *args) -> str:
        if not dir(Keys).__contains__(key):
            raise

        return f"{self.base_url}{key}"

    def set_token(self, token):
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def login(self, username, password):
        try:
            response = self.session.post(
                self.url(Keys.LOGIN_PATH),
                json={Keys.USERNAME: username, Keys.PASSWORD: password},
                timeout=10,
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            self.app.logger.error(f"Login error: {str(e)}")
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
                f"{self.base_url}/api/assets", json=asset_data, timeout=10
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
                f"{self.base_url}/api/assets/{asset_id}", json=asset_data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Update asset error: {str(e)}")
            raise

    def get_departments(self):
        try:
            response = self.session.get(f"{self.base_url}/api/departments", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get departments error: {str(e)}")
            raise

    def transfer_asset(self, asset_id, transfer_data):
        try:
            response = self.session.post(
                f"{self.base_url}/api/assets/{asset_id}/transfer",
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
                f"{self.base_url}/api/assets/{asset_id}/transfers", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get asset transfers error: {str(e)}")
            raise

    def get_reports_by_department(self):
        try:
            response = self.session.get(
                f"{self.base_url}/api/reports/assets-by-department", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get department report error: {str(e)}")
            raise

    def get_reports_by_status(self):
        try:
            response = self.session.get(
                f"{self.base_url}/api/reports/assets-by-status", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.app.logger.error(f"Get status report error: {str(e)}")
            raise
