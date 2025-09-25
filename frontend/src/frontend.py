#!/usr/bin/env python3
"""
Asset Management System - Web Frontend
Built with Python Flask
"""

# region dbpy_attach
# import debugpy

# (
#     (debugpy.listen(("0.0.0.0", 5679)), debugpy.wait_for_client())
#     if not debugpy.is_client_connected()
#     else None
# )
# endregion


from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
import requests
import os
from functools import wraps
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from .models import *

# Initialize Flask app
app = Flask(__name__, template_folder="/app/templates/")
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-this")

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://backend:5000")
app.config["API_BASE_URL"] = API_BASE_URL

# Setup logging
if not app.debug:
    if not os.path.exists("logs"):
        os.mkdir("logs")
    file_handler = RotatingFileHandler(
        "logs/frontend.log", maxBytes=10240, backupCount=10
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Asset Management Frontend startup")


class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()

    def set_token(self, token):
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def login(self, username, password):
        try:
            response = self.session.post(
                f"{self.base_url}/api/login",
                json={"username": username, "password": password},
                timeout=10,
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            app.logger.error(f"Login error: {str(e)}")
            return None

    def get_assets(self, filters=None):
        try:
            params = filters or {}
            response = self.session.get(
                f"{self.base_url}/api/assets", params=params, timeout=10
            )

            response.raise_for_status()
            return response.json()
        except Exception as e:
            app.logger.error(f"Get assets error: {str(e)}")
            raise

    def create_asset(self, asset_data: Asset):
        try:
            response = self.session.post(
                f"{self.base_url}/api/assets", json=asset_data, timeout=10
            )

            app.logger.info(self.session)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            app.logger.error(f"Create asset error: {str(e)}")
            raise

    def update_asset(self, asset_id, asset_data):
        try:
            response = self.session.put(
                f"{self.base_url}/api/assets/{asset_id}", json=asset_data, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            app.logger.error(f"Update asset error: {str(e)}")
            raise

    def get_departments(self):
        try:
            response = self.session.get(f"{self.base_url}/api/departments", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            app.logger.error(f"Get departments error: {str(e)}")
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
            app.logger.error(f"Transfer asset error: {str(e)}")
            raise

    def get_asset_transfers(self, asset_id):
        try:
            response = self.session.get(
                f"{self.base_url}/api/assets/{asset_id}/transfers", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            app.logger.error(f"Get asset transfers error: {str(e)}")
            raise

    def get_reports_by_department(self):
        try:
            response = self.session.get(
                f"{self.base_url}/api/reports/assets-by-department", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            app.logger.error(f"Get department report error: {str(e)}")
            raise

    def get_reports_by_status(self):
        try:
            response = self.session.get(
                f"{self.base_url}/api/reports/assets-by-status", timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            app.logger.error(f"Get status report error: {str(e)}")
            raise


def get_api_client():
    client = APIClient(app.config["API_BASE_URL"])
    if "access_token" in session:
        client.set_token(session["access_token"])
    return client


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "access_token" not in session:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session or session["user"].get("role") != "admin":
            flash("Bạn không có quyền truy cập chức năng này.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def index():
    if "access_token" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Vui lòng nhập đầy đủ thông tin đăng nhập.", "danger")
            return render_template("auth/login.html")

        client = get_api_client()
        result = client.login(username, password)

        if result and result.get("success"):
            session["access_token"] = result["access_token"]
            session["user"] = result["user"]
            flash(f'Chào mừng, {result["user"]["full_name"]}!', "success")
            return redirect(url_for("dashboard"))
        else:
            app.logger.debug(result)
            flash(result.get("message", "Đăng nhập thất bại."), "danger")

    return render_template("auth/login.html")
    # return os.getcwd()


@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất thành công.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    try:
        client = get_api_client()

        # Get summary statistics
        assets_response = client.get_assets()
        total_assets = assets_response.get("total", 0)

        departments = client.get_departments()
        total_departments = len(departments)

        # Get recent assets (last 10)
        recent_assets = assets_response.get("assets", [])[:10]

        return render_template(
            "dashboard/index.html",
            total_assets=total_assets,
            total_departments=total_departments,
            recent_assets=recent_assets,
            departments=departments,
        )
    except Exception as e:
        flash(f"Lỗi tải dashboard: {str(e)}", "danger")
        return render_template(
            "dashboard/index.html",
            total_assets=0,
            total_departments=0,
            recent_assets=[],
            departments=[],
        )


@app.route("/assets")
@login_required
def assets_list():
    try:
        client = get_api_client()

        # Get filter parameters
        search = request.args.get("search", "")
        category = request.args.get("category", "")
        status = request.args.get("status", "")
        department_id = request.args.get("department_id", "")
        page = int(request.args.get("page", 1))

        # Build filters
        filters = {"page": page}
        if search:
            filters["search"] = search
        if category:
            filters["category"] = category
        if status:
            filters["status"] = status
        if department_id:
            filters["department_id"] = department_id

        assets_data = client.get_assets(filters)
        departments = client.get_departments()

        return render_template(
            "assets/list.html",
            assets=assets_data.get("assets", []),
            total=assets_data.get("total", 0),
            pages=assets_data.get("pages", 1),
            current_page=assets_data.get("current_page", 1),
            departments=departments,
            filters={
                "search": search,
                "category": category,
                "status": status,
                "department_id": department_id,
            },
        )
    except Exception as e:
        flash(f"Lỗi tải danh sách tài sản: {str(e)}", "danger")
        return render_template(
            "assets/list.html",
            assets=[],
            total=0,
            pages=1,
            current_page=1,
            departments=[],
        )


@app.route("/assets/add", methods=["GET", "POST"])
@login_required
def asset_add():
    if request.method == "POST":
        try:
            client = get_api_client()

            asset_data = Asset(
                {
                    "code": request.form.get("code"),
                    "name": request.form.get("name"),
                    "description": request.form.get("description", ""),
                    "category": request.form.get("category"),
                    "value": float(request.form.get("value")),
                    "purchase_date": request.form.get("purchase_date"),
                    "current_department_id": int(
                        request.form.get("current_department_id")
                    ),
                    "status": request.form.get("status", "active"),
                }
            )

            result = client.create_asset(asset_data)
            if result.get("success"):
                flash("Thêm tài sản mới thành công!", "success")
                return redirect(url_for("assets_list"))
            else:
                flash(
                    result.get("message", "Có lỗi xảy ra khi thêm tài sản."), "danger"
                )
        except Exception as e:
            flash(f"Lỗi thêm tài sản: {str(e)}", "danger")

    try:
        client = get_api_client()
        departments = client.get_departments()
        return render_template(
            "assets/form.html",
            departments=departments,
            asset=None,
            action="add",
        )
    except Exception as e:
        flash(f"Lỗi tải form: {str(e)}", "danger")
        return redirect(url_for("assets_list"))


@app.route("/assets/edit/<int:asset_id>", methods=["GET", "POST"])
@login_required
def asset_edit(asset_id):
    if request.method == "POST":
        try:
            client = get_api_client()

            asset_data = {
                "code": request.form.get("code"),
                "name": request.form.get("name"),
                "description": request.form.get("description", ""),
                "category": request.form.get("category"),
                "value": float(request.form.get("value")),
                "purchase_date": request.form.get("purchase_date"),
                "status": request.form.get("status", "active"),
            }

            result = client.update_asset(asset_id, asset_data)
            if result.get("success"):
                flash("Cập nhật tài sản thành công!", "success")
                return redirect(url_for("assets_list"))
            else:
                flash(
                    result.get("message", "Có lỗi xảy ra khi cập nhật tài sản."),
                    "danger",
                )
        except Exception as e:
            flash(f"Lỗi cập nhật tài sản: {str(e)}", "danger")

    try:
        client = get_api_client()
        # Get asset details (you'll need to implement get_asset_by_id in API)
        departments = client.get_departments()

        # For now, we'll pass None and handle in template
        # In a real implementation, you'd get the asset data from API
        asset = None  # This should be the actual asset data

        return render_template(
            "templates/assets/form.html",
            departments=departments,
            asset=asset,
            action="edit",
        )
    except Exception as e:
        flash(f"Lỗi tải form: {str(e)}", "danger")
        return redirect(url_for("assets_list"))


@app.route("/assets/transfer/<int:asset_id>", methods=["GET", "POST"])
@login_required
def asset_transfer(asset_id):
    if request.method == "POST":
        try:
            client = get_api_client()

            transfer_data = {
                "to_department_id": int(request.form.get("to_department_id")),
                "reason": request.form.get("reason", ""),
                "notes": request.form.get("notes", ""),
            }

            result = client.transfer_asset(asset_id, transfer_data)
            if result.get("success"):
                flash("Điều chuyển tài sản thành công!", "success")
                return redirect(url_for("assets_list"))
            else:
                flash(
                    result.get("message", "Có lỗi xảy ra khi điều chuyển tài sản."),
                    "danger",
                )
        except Exception as e:
            flash(f"Lỗi điều chuyển tài sản: {str(e)}", "danger")

    try:
        client = get_api_client()
        departments = client.get_departments()

        return render_template(
            "templates/assets/transfer.html", departments=departments, asset_id=asset_id
        )
    except Exception as e:
        flash(f"Lỗi tải form điều chuyển: {str(e)}", "danger")
        return redirect(url_for("assets_list"))


@app.route("/reports")
@login_required
def reports_index():
    return render_template("reports/index.html")


@app.route("/reports/department")
@login_required
def reports_department():
    try:
        client = get_api_client()
        report_data = client.get_reports_by_department()
        return render_template("reports/department.html", report_data=report_data)
    except Exception as e:
        flash(f"Lỗi tạo báo cáo: {str(e)}", "danger")
        return render_template("reports/department.html", report_data=[])


@app.route("/reports/status")
@login_required
def reports_status():
    try:
        client = get_api_client()
        report_data = client.get_reports_by_status()
        return render_template("reports/status.html", report_data=report_data)
    except Exception as e:
        flash(f"Lỗi tạo báo cáo: {str(e)}", "danger")
        return render_template("reports/status.html", report_data=[])


@app.route("/departments")
@login_required
@admin_required
def departments_list():
    try:
        client = get_api_client()
        departments = client.get_departments()

        return render_template("departments/list.html", departments=departments)
    except Exception as e:
        flash(f"Lỗi tải danh sách phòng ban: {str(e)}", "danger")
        return render_template("departments/list.html", departments=[])


@app.route("/departments/add", methods=["GET", "POST"])
@login_required
@admin_required
def department_add():
    if request.method == "POST":
        try:
            client = get_api_client()

            department_data = Department(
                {
                    "name": request.form.get("name"),
                    "description": request.form.get("description", ""),
                }
            )

            result = client.create_department(department_data)
            if result.get("success"):
                flash("Thêm phòng ban mới thành công!", "success")
                return redirect(url_for("departments_list"))
            else:
                flash(
                    result.get("message", "Có lỗi xảy ra khi thêm phòng ban."), "danger"
                )
        except Exception as e:
            flash(f"Lỗi thêm phòng ban: {str(e)}", "danger")

    try:
        client = get_api_client()
        departments = client.get_departments()
        return render_template(
            "departments/form.html",
            departments=departments,
            asset=None,
            action="add",
        )
    except Exception as e:
        flash(f"Lỗi tải form: {str(e)}", "danger")
        return redirect(url_for("assets_list"))


# Health check endpoint
@app.route("/health")
def health_check():
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
        }
    )


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("errors/500.html"), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    debug = os.getenv("FLASK_ENV") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
