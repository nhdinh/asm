from app import create_app
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_file,
)
import requests
import os
from functools import wraps
from datetime import datetime
import io
import csv
from api_client import ApiClient

# Backend API URL
API_URL = os.getenv("API_URL", "http://backend:5000/api")

app = create_app()

def get_api_client():
    client = ApiClient(app)

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


def get_headers():
    return {"Authorization": f"Bearer {session.get('token')}"}


# Template filters
@app.template_filter("datetime")
def datetime_filter(value):
    if value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        except:
            return value
    return ""


@app.template_filter("date")
def date_filter(value):
    if value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y")
        except:
            return value
    return ""


@app.template_filter("currency")
def currency_filter(value):
    try:
        return "{:,.0f}".format(float(value))
    except:
        return "0"


# Routes
@app.route("/")
def index():
    if "access_token" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "access_token" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        data = {
            "username": request.form["username"],
            "password": request.form["password"],
        }

        try:
            response = requests.post(f"{API_URL}/auth/login", json=data, timeout=5)

            if response.status_code == 200:
                result = response.json()
                session["access_token"] = result["access_token"]
                session["user"] = result["user"]
                flash("Đăng nhập thành công!", "success")

                # Redirect to next page if exists
                next_page = request.args.get("next")
                if next_page:
                    return redirect(next_page)
                return redirect(url_for("dashboard"))
            else:
                flash("Tên đăng nhập hoặc mật khẩu không đúng", "danger")
        except requests.exceptions.RequestException as e:
            flash("Không thể kết nối đến server. Vui lòng thử lại sau.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất thành công", "info")
    return redirect(url_for("login"))


@app.route("/dashboard1")
@login_required
def dashboard1():
    try:
        response = requests.get(
            f"{API_URL}/reports/dashboard", headers=get_headers(), timeout=5
        )
        stats = response.json() if response.status_code == 200 else {}
    except:
        stats = {}
        flash("Không thể tải dữ liệu dashboard", "warning")

    return render_template("dashboard.html", stats=stats)

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
def assets():
    # Get filter parameters
    filters = {
        "search": request.args.get("search", ""),
        "category": request.args.get("category", ""),
        "status": request.args.get("status", ""),
        "department_id": request.args.get("department_id", ""),
    }

    try:
        # Get assets with filters
        response = requests.get(
            f"{API_URL}/assets", params=filters, headers=get_headers(), timeout=5
        )
        assets = response.json() if response.status_code == 200 else []

        # Get departments for filter
        response_dept = requests.get(
            f"{API_URL}/departments", headers=get_headers(), timeout=5
        )
        departments = response_dept.json() if response_dept.status_code == 200 else []
    except:
        assets = []
        departments = []
        flash("Không thể tải danh sách tài sản", "warning")

    return render_template(
        "assets.html", assets=assets, departments=departments, filters=filters
    )


@app.route("/departments")
@login_required
@admin_required
def departments():
    try:
        response = requests.get(
            f"{API_URL}/departments", headers=get_headers(), timeout=5
        )
        departments = response.json() if response.status_code == 200 else []

        # Get users for manager assignment
        response_users = requests.get(
            f"{API_URL}/users", headers=get_headers(), timeout=5
        )
        users = response_users.json() if response_users.status_code == 200 else []
    except:
        departments = []
        users = []
        flash("Không thể tải danh sách phòng ban", "warning")

    return render_template("departments.html", departments=departments, users=users)


@app.route("/users")
@login_required
@admin_required
def users():
    try:
        response = requests.get(f"{API_URL}/users", headers=get_headers(), timeout=5)
        users = response.json() if response.status_code == 200 else []

        response_dept = requests.get(
            f"{API_URL}/departments", headers=get_headers(), timeout=5
        )
        departments = response_dept.json() if response_dept.status_code == 200 else []
    except:
        users = []
        departments = []
        flash("Không thể tải danh sách người dùng", "warning")

    return render_template("users.html", users=users, departments=departments)


@app.route("/reports")
@login_required
def reports():
    report_type = request.args.get("type", "assets")
    filters = {k: v for k, v in request.args.items() if v and k != "type"}

    report_data = None
    departments = []

    try:
        # Get departments for filter
        response_dept = requests.get(
            f"{API_URL}/departments", headers=get_headers(), timeout=5
        )
        departments = response_dept.json() if response_dept.status_code == 200 else []

        # Get report data if filters are provided
        if filters:
            if report_type == "user-activities":
                endpoint = "/reports/user-activities"
            else:
                endpoint = "/reports/assets"

            response = requests.get(
                f"{API_URL}{endpoint}", params=filters, headers=get_headers(), timeout=5
            )
            report_data = response.json() if response.status_code == 200 else None
    except:
        flash("Không thể tải dữ liệu báo cáo", "warning")

    return render_template(
        "reports.html",
        report_data=report_data,
        departments=departments,
        filters=filters,
        report_type=report_type,
    )


# API proxy endpoints for AJAX calls
@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
@login_required
def proxy_api(path):
    url = f"{API_URL}/{path}"

    try:
        if request.method == "GET":
            response = requests.get(
                url, params=request.args, headers=get_headers(), timeout=5
            )
        elif request.method == "POST":
            response = requests.post(
                url, json=request.json, headers=get_headers(), timeout=5
            )
        elif request.method == "PUT":
            response = requests.put(
                url, json=request.json, headers=get_headers(), timeout=5
            )
        elif request.method == "DELETE":
            response = requests.delete(url, headers=get_headers(), timeout=5)

        # Handle response
        if response.headers.get("content-type", "").startswith("application/json"):
            return jsonify(response.json()), response.status_code
        else:
            return response.content, response.status_code, response.headers.items()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "API request failed"}), 500


# Export endpoints
@app.route("/api/assets/export")
@login_required
def export_assets():
    try:
        response = requests.get(f"{API_URL}/assets", headers=get_headers(), timeout=5)
        assets = response.json() if response.status_code == 200 else []

        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "code",
                "name",
                "category",
                "department_name",
                "purchase_value",
                "purchase_date",
                "status",
            ],
        )
        writer.writeheader()
        for asset in assets:
            writer.writerow(
                {
                    "code": asset["code"],
                    "name": asset["name"],
                    "category": asset.get("category", ""),
                    "department_name": asset.get("department_name", ""),
                    "purchase_value": asset.get("purchase_value", 0),
                    "purchase_date": asset.get("purchase_date", ""),
                    "status": asset.get("status", ""),
                }
            )

        # Create response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f'assets_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        )
    except:
        flash("Không thể xuất dữ liệu", "danger")
        return redirect(url_for("assets"))


@app.route("/api/reports/export")
@login_required
def export_report():
    report_type = request.args.get("type", "assets")
    filters = {k: v for k, v in request.args.items() if v and k != "type"}

    try:
        if report_type == "user-activities":
            endpoint = "/reports/user-activities"
        else:
            endpoint = "/reports/assets"

        response = requests.get(
            f"{API_URL}{endpoint}", params=filters, headers=get_headers(), timeout=5
        )
        data = response.json() if response.status_code == 200 else {}

        # Create Excel-compatible CSV
        output = io.StringIO()

        if report_type == "assets" and "assets" in data:
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "code",
                    "name",
                    "category",
                    "department_name",
                    "purchase_value",
                    "status",
                ],
            )
            writer.writeheader()
            for asset in data["assets"]:
                writer.writerow(
                    {
                        "code": asset["code"],
                        "name": asset["name"],
                        "category": asset.get("category", ""),
                        "department_name": asset.get("department_name", ""),
                        "purchase_value": asset.get("purchase_value", 0),
                        "status": asset.get("status", ""),
                    }
                )

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f'report_{report_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        )
    except:
        flash("Không thể xuất báo cáo", "danger")
        return redirect(url_for("reports"))


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500