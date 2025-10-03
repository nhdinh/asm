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
import os
from functools import wraps
from datetime import datetime
import io
import csv
import requests
from api_client import ApiClient
import traceback

app = create_app()
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")


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
    access_token = session.get("access_token")
    return {"Authorization": f"Bearer {access_token}"}


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
        username = request.form["username"]
        password = request.form["password"]

        try:
            client = get_api_client()
            response = client.login(username, password)

            if response.status_code == 200:
                result = response.json()
                session["access_token"] = result["access_token"]
                session["user"] = result["user"]

                app.logger.info(session["user"])
                flash("Đăng nhập thành công!", "success")

                # Redirect to next page if exists
                next_page = request.args.get("next")
                if next_page:
                    return redirect(next_page)
                return redirect(url_for("dashboard"))
            else:
                flash("Tên đăng nhập hoặc mật khẩu không đúng", "danger")
        except Exception as e:
            app.logger.exception(e)
            flash("Xảy ra lỗi khi đăng nhập", "danger")

    return render_template("users/login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất thành công", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    try:
        client = get_api_client()

        # Get dashboard statistics from backend
        stats = client.get_dashboard_stats()

        # Get recent assets
        assets_response = client.get_assets()
        all_assets = assets_response if isinstance(assets_response, list) else []
        recent_assets = all_assets[:10]

        departments = client.get_departments()

        return render_template(
            "dashboard.html",
            total_assets=stats.get("total_assets", 0),
            total_value=sum(
                asset.get("purchase_value", 0) or 0 for asset in all_assets
            ),
            total_departments=stats.get("total_departments", 0),
            recent_assets=recent_assets,
            departments=departments,
            assets_by_status=stats.get("assets_by_status", {}),
        )
    except Exception as e:
        app.logger.exception(e)
        flash(f"Lỗi tải dashboard: {str(e)}", "danger")
        return render_template(
            "dashboard.html",
            total_assets=0,
            total_value=0,
            total_departments=0,
            recent_assets=[],
            departments=[],
            assets_by_status={},
        )


@app.route("/assets")
@login_required
def assets():
    # Get filter parameters
    filters = {k: v for k, v in request.args.items() if v}

    try:
        client = get_api_client()

        # Get assets with filters
        assets = client.get_assets(filters)
        assets = assets if isinstance(assets, list) else []

        # Get departments for filter
        departments = client.get_departments()
    except Exception as e:
        app.logger.exception(e)
        assets = []
        departments = []
        flash("Không thể tải danh sách tài sản", "warning")

    return render_template(
        "assets/list.html", assets=assets, departments=departments, filters=filters
    )


@app.route("/departments", methods=["GET", "POST"])
@login_required
@admin_required
def departments():
    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]

        try:
            client = get_api_client()
            client.create_department(
                {
                    "name": name,
                    "description": description,
                }
            )
            flash("Tạo phòng ban thành công", "success")
            return redirect(url_for("departments"))
        except Exception as e:
            app.logger.exception(e)
            flash("Không thể tạo phòng ban", "danger")

    try:
        client = get_api_client()
        departments = client.get_departments()
        users = client.get_users()
    except Exception as e:
        app.logger.exception(e)
        departments = []
        users = []
        flash("Không thể tải danh sách phòng ban", "warning")

    return render_template(
        "departments/list.html", departments=departments, users=users
    )


@app.route("/users")
@login_required
@admin_required
def users():
    try:
        client = get_api_client()
        users = client.get_users()
        departments = client.get_departments()
    except Exception as e:
        app.logger.exception(e)
        users = []
        departments = []
        flash("Không thể tải danh sách người dùng", "warning")

    return render_template("users/list.html", users=users, departments=departments)


@app.route("/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    if request.method == "POST":
        try:
            client = get_api_client()

            # Get department IDs from form
            department_ids = request.form.getlist("department_ids")

            user_data = {
                "username": request.form["username"],
                "email": request.form["email"],
                "password": request.form["password"],
                "role": request.form["role"],
                "department_ids": [int(d) for d in department_ids if d],
            }

            client.create_user(user_data)
            flash("Tạo người dùng thành công", "success")
            return redirect(url_for("users"))
        except Exception as e:
            app.logger.exception(e)
            flash(f"Không thể tạo người dùng: {str(e)}", "danger")

    try:
        client = get_api_client()
        departments = client.get_departments()
    except Exception as e:
        app.logger.exception(e)
        departments = []

    return render_template("users/create.html", departments=departments)


@app.route("/users/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(id):
    if request.method == "POST":
        try:
            client = get_api_client()

            # Get department IDs from form
            department_ids = request.form.getlist("department_ids")

            user_data = {
                "username": request.form["username"],
                "email": request.form["email"],
                "role": request.form["role"],
                "department_ids": [int(d) for d in department_ids if d],
            }

            client.update_user(id, user_data)
            flash("Cập nhật người dùng thành công", "success")
            return redirect(url_for("users"))
        except Exception as e:
            app.logger.exception(e)
            flash(f"Không thể cập nhật người dùng: {str(e)}", "danger")

    try:
        client = get_api_client()
        user = client.get_user(id)
        departments = client.get_departments()
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin người dùng", "danger")
        return redirect(url_for("users"))

    return render_template("users/edit.html", user=user, departments=departments)


@app.route("/assets/create", methods=["GET", "POST"])
@login_required
def create_asset():
    if request.method == "POST":
        try:
            client = get_api_client()

            asset_data = {
                "code": request.form["code"],
                "name": request.form["name"],
                "description": request.form.get("description", ""),
                "category": request.form.get("category", ""),
                "purchase_value": float(request.form.get("purchase_value", 0)),
                "purchase_date": request.form.get("purchase_date"),
                "department_id": int(request.form["department_id"]),
                "status": request.form.get("status", "active"),
                "assigned_to_id": (
                    int(request.form["assigned_to_id"])
                    if request.form.get("assigned_to_id")
                    else None
                ),
                "condition_notes": request.form.get("condition_notes", ""),
            }

            client.create_asset(asset_data)
            flash("Tạo tài sản thành công", "success")
            return redirect(url_for("assets"))
        except Exception as e:
            app.logger.exception(e)
            flash(f"Không thể tạo tài sản: {str(e)}", "danger")

    try:
        client = get_api_client()
        departments = client.get_departments()
        users = client.get_users()
    except Exception as e:
        app.logger.exception(e)
        departments = []
        users = []

    return render_template("assets/create.html", departments=departments, users=users)


@app.route("/assets/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_asset(id):
    if request.method == "POST":
        try:
            client = get_api_client()

            asset_data = {
                "name": request.form["name"],
                "description": request.form.get("description", ""),
                "category": request.form.get("category", ""),
                "purchase_value": float(request.form.get("purchase_value", 0)),
                "purchase_date": request.form.get("purchase_date"),
                "status": request.form.get("status", "active"),
                "assigned_to_id": (
                    int(request.form["assigned_to_id"])
                    if request.form.get("assigned_to_id")
                    else None
                ),
                "condition_notes": request.form.get("condition_notes", ""),
            }

            client.update_asset(id, asset_data)
            flash("Cập nhật tài sản thành công", "success")
            return redirect(url_for("assets"))
        except Exception as e:
            app.logger.exception(e)
            flash(f"Không thể cập nhật tài sản: {str(e)}", "danger")

    try:
        client = get_api_client()
        asset = client.get_asset(id)
        departments = client.get_departments()
        users = client.get_users()
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin tài sản", "danger")
        return redirect(url_for("assets"))

    return render_template(
        "assets/edit.html", asset=asset, departments=departments, users=users
    )


@app.route("/assets/<int:id>/detail")
@login_required
def asset_detail(id):
    try:
        client = get_api_client()
        asset = client.get_asset(id)
        history = client.get_asset_history(id)
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin tài sản", "danger")
        return redirect(url_for("assets"))

    return render_template("assets/detail.html", asset=asset, history=history)


@app.route("/assets/<int:id>/transfer", methods=["GET", "POST"])
@login_required
def transfer_asset(id):
    if request.method == "POST":
        try:
            client = get_api_client()

            transfer_data = {
                "to_department_id": int(request.form["to_department_id"]),
                "notes": request.form.get("notes", ""),
            }

            client.transfer_asset(id, transfer_data)
            flash("Chuyển tài sản thành công", "success")
            return redirect(url_for("asset_detail", id=id))
        except Exception as e:
            app.logger.exception(e)
            flash(f"Không thể chuyển tài sản: {str(e)}", "danger")

    try:
        client = get_api_client()
        asset = client.get_asset(id)
        departments = client.get_departments()
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin tài sản", "danger")
        return redirect(url_for("assets"))

    return render_template(
        "transfers/create.html", asset=asset, departments=departments
    )


@app.route("/departments/<int:id>")
@login_required
def department_detail(id):
    try:
        client = get_api_client()
        department = client.get_department(id)
        assets = client.get_assets({"department_id": id})
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin phòng ban", "danger")
        return redirect(url_for("departments"))

    return render_template(
        "departments/detail.html", department=department, assets=assets
    )


@app.route("/departments/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_department(id):
    if request.method == "POST":
        try:
            client = get_api_client()

            # Get user IDs from form
            user_ids = request.form.getlist("user_ids")

            department_data = {
                "name": request.form["name"],
                "description": request.form.get("description", ""),
                "user_ids": [int(u) for u in user_ids if u],
            }

            client.update_department(id, department_data)
            flash("Cập nhật phòng ban thành công", "success")
            return redirect(url_for("departments"))
        except Exception as e:
            app.logger.exception(e)
            flash(f"Không thể cập nhật phòng ban: {str(e)}", "danger")

    try:
        client = get_api_client()
        department = client.get_department(id)
        users = client.get_users()
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin phòng ban", "danger")
        return redirect(url_for("departments"))

    return render_template("departments/edit.html", department=department, users=users)


@app.route("/transfers")
@login_required
def transfers():
    try:
        client = get_api_client()
        # Get all assets to show transfer history
        assets = client.get_assets()

        # Collect all transfers from assets
        all_transfers = []
        for asset in assets if isinstance(assets, list) else []:
            try:
                history = client.get_asset_history(asset["id"])
                for transfer in history:
                    transfer["asset"] = asset
                    all_transfers.append(transfer)
            except:
                pass

        # Sort by date
        all_transfers.sort(key=lambda x: x.get("transfer_date", ""), reverse=True)

    except Exception as e:
        app.logger.exception(e)
        all_transfers = []
        flash("Không thể tải lịch sử điều chuyển", "warning")

    return render_template("transfers/list.html", transfers=all_transfers)


@app.route("/reports")
@login_required
def reports():
    report_type = request.args.get("type", "assets")
    filters = {k: v for k, v in request.args.items() if v and k != "type"}

    report_data = None
    departments = []
    users_list = []

    try:
        client = get_api_client()

        # Get departments for filter
        departments = client.get_departments()

        # Get users for user activity filter (admin only)
        if session.get("user", {}).get("role") == "admin":
            users_list = client.get_users()

        # Get report data if filters are provided
        if filters or report_type:
            if report_type == "user-activities":
                report_data = client.get_user_activity_report(filters)
            else:
                report_data = client.get_asset_report(filters)
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải dữ liệu báo cáo", "warning")

    return render_template(
        "reports/index.html",
        report_data=report_data,
        departments=departments,
        users=users_list,
        filters=filters,
        report_type=report_type,
    )


# API proxy endpoints for AJAX calls
@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
@login_required
def proxy_api(path):
    url = f"{API_BASE_URL}/{path}"
    app.logger.info(f"Calling path {url} with method {request.method}")

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
        client = get_api_client()
        assets = client.get_assets()
        assets = assets if isinstance(assets, list) else []

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
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể xuất dữ liệu", "danger")
        return redirect(url_for("assets"))


@app.route("/api/reports/export")
@login_required
def export_report():
    report_type = request.args.get("type", "assets")
    filters = {k: v for k, v in request.args.items() if v and k != "type"}

    try:
        client = get_api_client()

        if report_type == "user-activities":
            data = client.get_user_activity_report(filters)
        else:
            data = client.get_asset_report(filters)

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
        elif report_type == "user-activities" and "activities" in data:
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "username",
                    "action",
                    "entity_type",
                    "timestamp",
                    "details",
                ],
            )
            writer.writeheader()
            for activity in data["activities"]:
                writer.writerow(
                    {
                        "username": activity.get("username", ""),
                        "action": activity.get("action", ""),
                        "entity_type": activity.get("entity_type", ""),
                        "timestamp": activity.get("timestamp", ""),
                        "details": activity.get("details", ""),
                    }
                )

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f'report_{report_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        )
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể xuất báo cáo", "danger")
        return redirect(url_for("reports"))


# Health check endpoint
@app.route("/health")
def health_check():
    return {"status": "healthy", "service": "asset-management-frontend"}, 200


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500
