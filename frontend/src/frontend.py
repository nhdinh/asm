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


def extract_items(response):
    """Extract items from paginated response, or return response as-is if not paginated"""
    if isinstance(response, dict) and 'items' in response:
        return response['items']
    return response if response else []


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "access_token" not in session:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("login"))

        # Check if user must change password (except on first_password_change and logout routes)
        if f.__name__ not in ['first_password_change', 'logout']:
            user = session.get("user", {})
            if user.get("must_change_password"):
                return redirect(url_for("first_password_change"))

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


def non_viewer_required(f):
    """Decorator to block viewer role from accessing certain features"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session or session["user"].get("role") == "viewer":
            flash("Chức năng này không khả dụng cho tài khoản Viewer.", "warning")
            return redirect(url_for("my_assets"))
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

            if response and response.status_code == 200:
                result = response.json()
                session["access_token"] = result["access_token"]
                session["user"] = result["user"]

                app.logger.info(session["user"])
                flash("Đăng nhập thành công!", "success")

                # Check if user must change password on first login
                if session["user"].get("must_change_password"):
                    flash("Bạn cần đổi mật khẩu trước khi tiếp tục.", "warning")
                    return redirect(url_for("first_password_change"))

                # Redirect to next page if exists
                next_page = request.args.get("next")
                if next_page:
                    return redirect(next_page)

                # Redirect viewers to my-assets page
                if session["user"].get("role") == "viewer":
                    return redirect(url_for("my_assets"))

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


@app.route("/first-password-change", methods=["GET", "POST"])
@login_required
def first_password_change():
    # Only allow if user must change password
    user = session.get("user", {})
    if not user.get("must_change_password"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        client = get_api_client()

        try:
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            # Validate passwords match
            if new_password != confirm_password:
                flash("Mật khẩu xác nhận không khớp!", "danger")
                return redirect(url_for("first_password_change"))

            # Call API without old_password since must_change_password is true
            data = {
                "new_password": new_password,
            }

            response = client.change_password(data)
            if response and response.get("user"):
                # Update session user data to clear must_change_password flag
                session["user"] = response["user"]
                flash(response.get("message", "Đổi mật khẩu thành công!"), "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Có lỗi xảy ra khi đổi mật khẩu", "danger")
        except Exception as e:
            app.logger.exception(e)
            flash(f"Có lỗi xảy ra: {str(e)}", "danger")

        return redirect(url_for("first_password_change"))

    # GET request - show first password change form
    return render_template("users/first_password_change.html", user=user)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    client = get_api_client()

    if request.method == "POST":
        try:
            # Get items_per_page and convert to int or None
            items_per_page = request.form.get("items_per_page", "").strip()
            if items_per_page:
                try:
                    items_per_page = int(items_per_page)
                except ValueError:
                    items_per_page = None
            else:
                items_per_page = None

            data = {
                "fullname": request.form.get("fullname"),
                "email": request.form.get("email"),
                "items_per_page": items_per_page,
            }

            response = client.update_profile(data)
            if response:
                # Update session user data
                session["user"] = response
                flash("Cập nhật thông tin thành công!", "success")
            else:
                flash("Có lỗi xảy ra khi cập nhật thông tin", "danger")
        except Exception as e:
            app.logger.exception(e)
            flash(f"Có lỗi xảy ra khi cập nhật thông tin: {str(e)}", "danger")

        return redirect(url_for("profile"))

    # GET request - show profile form
    user = session.get("user", {})

    # Get system default for items_per_page
    try:
        settings = client.get_settings()
        default_items_per_page = None
        for setting in settings:
            if setting.get('key') == 'default_items_per_page':
                default_items_per_page = int(setting.get('value', 20))
                break
        if default_items_per_page is None:
            default_items_per_page = 20
    except Exception as e:
        app.logger.exception(e)
        default_items_per_page = 20

    return render_template("users/profile.html", user=user, default_items_per_page=default_items_per_page)


@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    client = get_api_client()

    try:
        data = {
            "old_password": request.form.get("old_password"),
            "new_password": request.form.get("new_password"),
        }

        response = client.change_password(data)
        if response and response.get("user"):
            # Update session user data to clear must_change_password flag
            session["user"] = response["user"]
            flash(response.get("message", "Đổi mật khẩu thành công!"), "success")
        else:
            flash("Có lỗi xảy ra khi đổi mật khẩu", "danger")
    except Exception as e:
        app.logger.exception(e)
        error_msg = str(e)
        if "400" in error_msg or "Mật khẩu cũ không đúng" in error_msg:
            flash("Mật khẩu cũ không đúng", "danger")
        else:
            flash("Có lỗi xảy ra khi đổi mật khẩu", "danger")

    return redirect(url_for("profile"))


@app.route("/dashboard")
@login_required
def dashboard():
    # Redirect viewers to their my-assets page
    if session.get("user", {}).get("role") == "viewer":
        return redirect(url_for("my_assets"))

    try:
        client = get_api_client()

        # Get dashboard statistics from backend
        stats = client.get_dashboard_stats()

        # Get recent assets
        assets_response = client.get_assets()
        all_assets = extract_items(assets_response)
        recent_assets = all_assets[:10]

        departments = extract_items(client.get_departments())

        return render_template(
            "dashboard.html",
            total_assets=stats.get("total_assets", 0),
            total_value=stats.get("total_value", 0),
            total_departments=stats.get("total_departments", 0),
            damaged_count=stats.get("assets_by_status", {}).get("damaged", 0),
            recent_assets=recent_assets,
            departments=departments,
            assets_by_status=stats.get("assets_by_status", {}),
            assets_by_category=stats.get("assets_by_category", {}),
        )
    except Exception as e:
        app.logger.exception(e)
        flash(f"Lỗi tải dashboard: {str(e)}", "danger")
        return render_template(
            "dashboard.html",
            total_assets=0,
            total_value=0,
            total_departments=0,
            damaged_count=0,
            recent_assets=[],
            departments=[],
            assets_by_status={},
            assets_by_category={},
        )


@app.route("/my-assets")
@login_required
def my_assets():
    """Page for viewers to see their assigned assets"""
    try:
        client = get_api_client()
        assets = client.get_my_assets()
        stats = client.get_my_stats()

        return render_template(
            "my_assets.html",
            assets=assets,
            stats=stats,
        )
    except Exception as e:
        app.logger.exception(e)
        flash(f"Lỗi tải tài sản: {str(e)}", "danger")
        return render_template("my_assets.html", assets=[], stats={})


@app.route("/assets")
@login_required
@non_viewer_required
def assets():
    # Get filter parameters and page number
    page = request.args.get('page', 1, type=int)
    filters = {k: v for k, v in request.args.items() if v and k != 'page'}

    try:
        client = get_api_client()

        # Get assets with filters and pagination
        filters['page'] = page
        assets_response = client.get_assets(filters)

        # Extract items and pagination
        if isinstance(assets_response, dict) and 'items' in assets_response:
            assets = assets_response['items']
            pagination = assets_response.get('pagination', {})
        else:
            assets = assets_response if assets_response else []
            pagination = None

        # Get departments for filter
        departments = extract_items(client.get_departments())
    except Exception as e:
        app.logger.exception(e)
        assets = []
        departments = []
        pagination = None
        flash("Không thể tải danh sách tài sản", "warning")

    return render_template(
        "assets/list.html", assets=assets, departments=departments, filters=filters, pagination=pagination
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
        sort_by = request.args.get('sort_by', '')
        sort_order = request.args.get('sort_order', 'asc')
        search = request.args.get('search', '')

        client = get_api_client()

        # Build params dict
        params = {}
        if sort_by:
            params['sort_by'] = sort_by
        if sort_order:
            params['sort_order'] = sort_order
        if search:
            params['search'] = search

        departments = extract_items(client.get_departments(**params))
        users = extract_items(client.get_users())

        # Pass filters to template
        filters = {
            'sort_by': sort_by,
            'sort_order': sort_order,
            'search': search
        }
    except Exception as e:
        app.logger.exception(e)
        departments = []
        users = []
        filters = {}
        flash("Không thể tải danh sách phòng ban", "warning")

    return render_template(
        "departments/list.html", departments=departments, users=users, filters=filters
    )


@app.route("/users")
@login_required
@admin_required
def users():
    try:
        page = request.args.get('page', 1, type=int)
        sort_by = request.args.get('sort_by', '')
        sort_order = request.args.get('sort_order', 'asc')
        search = request.args.get('search', '')
        role = request.args.get('role', '')
        department_id = request.args.get('department_id', '')

        client = get_api_client()
        response = client.get_users(
            page=page,
            sort_by=sort_by,
            sort_order=sort_order,
            search=search,
            role=role,
            department_id=department_id
        )

        # Extract items and pagination from response
        if isinstance(response, dict) and 'items' in response:
            users_list = response['items']
            pagination = response.get('pagination', {})
        else:
            # Fallback for non-paginated response
            users_list = response
            pagination = None

        departments = extract_items(client.get_departments())

        # Pass filters to template
        filters = {
            'sort_by': sort_by,
            'sort_order': sort_order,
            'search': search,
            'role': role,
            'department_id': department_id
        }

    except Exception as e:
        app.logger.exception(e)
        users_list = []
        departments = []
        pagination = None
        filters = {}
        flash("Không thể tải danh sách người dùng", "warning")

    return render_template("users/list.html", users=users_list, departments=departments, pagination=pagination, filters=filters)


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
                "fullname": request.form.get("fullname", ""),
                "email": request.form["email"],
                "password": request.form["password"],
                "role": request.form["role"],
                "must_change_password": request.form.get("must_change_password") == "true",
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
        departments = extract_items(client.get_departments())
    except Exception as e:
        app.logger.exception(e)
        departments = []

    return render_template("users/create.html", departments=departments)


@app.route("/users/<int:id>")
@login_required
def user_detail(id):
    """View user details and their assigned assets"""
    try:
        client = get_api_client()
        user = client.get_user(id)

        # Get assets assigned to this user
        assets = extract_items(client.get_assets(filters={"assigned_to_id": id}))
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin người dùng", "danger")
        return redirect(url_for("users"))

    return render_template("users/detail.html", user=user, assets=assets)


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
                "fullname": request.form.get("fullname", ""),
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
        departments = extract_items(client.get_departments())
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin người dùng", "danger")
        return redirect(url_for("users"))

    return render_template("users/edit.html", user=user, departments=departments)


@app.route("/users/sample-csv")
@login_required
@admin_required
def download_users_sample_csv():
    try:
        client = get_api_client()
        response = client.session.get(
            f"{client.base_url}/users/sample-csv",
            timeout=10
        )

        if response.status_code == 200:
            output = io.BytesIO(response.content)
            output.seek(0)
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name='users_sample.csv'
            )
        else:
            flash("Không thể tải mẫu CSV", "danger")
            return redirect(url_for("users"))
    except Exception as e:
        app.logger.exception(e)
        flash(f"Lỗi: {str(e)}", "danger")
        return redirect(url_for("users"))


@app.route("/users/upload-csv", methods=["POST"])
@login_required
@admin_required
def upload_users_csv():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if not file.filename.endswith('.csv'):
            return jsonify({"error": "File must be a CSV"}), 400

        client = get_api_client()

        # Forward the file to the backend API
        files = {'file': (file.filename, file.stream, 'text/csv')}
        response = client.session.post(
            f"{client.base_url}/users/upload-csv",
            files=files,
            timeout=30
        )

        if response.status_code in [200, 201, 207]:  # 207 = Multi-Status (partial success)
            return jsonify(response.json())
        else:
            error_msg = response.json().get('message', 'Upload failed') if response.content else 'Upload failed'
            return jsonify({"error": error_msg}), response.status_code

    except Exception as e:
        app.logger.exception(e)
        return jsonify({"error": str(e)}), 500


@app.route("/assets/sample-csv")
@login_required
@admin_required
def download_assets_sample_csv():
    try:
        client = get_api_client()
        response = client.session.get(
            f"{client.base_url}/assets/sample-csv",
            timeout=10
        )

        if response.status_code == 200:
            output = io.BytesIO(response.content)
            output.seek(0)
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name='assets_sample.csv'
            )
        else:
            flash("Không thể tải mẫu CSV", "danger")
            return redirect(url_for("assets"))
    except Exception as e:
        app.logger.exception(e)
        flash(f"Lỗi: {str(e)}", "danger")
        return redirect(url_for("assets"))


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
        departments = extract_items(client.get_departments())
        users = extract_items(client.get_users())
        categories = extract_items(client.get_categories())
    except Exception as e:
        app.logger.exception(e)
        departments = []
        users = []
        categories = []

    return render_template("assets/create.html", departments=departments, users=users, categories=categories)


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
        departments = extract_items(client.get_departments())
        users = extract_items(client.get_users())
        categories = extract_items(client.get_categories())
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin tài sản", "danger")
        return redirect(url_for("assets"))

    return render_template(
        "assets/edit.html", asset=asset, departments=departments, users=users, categories=categories
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

            # Add assigned_to_id if provided
            assigned_to_id = request.form.get("assigned_to_id")
            if assigned_to_id:
                transfer_data["assigned_to_id"] = int(assigned_to_id)

            client.transfer_asset(id, transfer_data)
            flash("Chuyển tài sản thành công", "success")
            return redirect(url_for("asset_detail", id=id))
        except Exception as e:
            app.logger.exception(e)
            flash(f"Không thể chuyển tài sản: {str(e)}", "danger")

    try:
        client = get_api_client()
        asset = client.get_asset(id)
        departments = extract_items(client.get_departments())
        users = extract_items(client.get_users())
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin tài sản", "danger")
        return redirect(url_for("assets"))

    return render_template(
        "transfers/create.html", asset=asset, departments=departments, users=users
    )


@app.route("/departments/<int:id>")
@login_required
def department_detail(id):
    try:
        client = get_api_client()
        department = client.get_department(id)
        assets = extract_items(client.get_assets({"department_id": id}))
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

            # Get user IDs and manager IDs from form
            user_ids = request.form.getlist("user_ids")
            manager_ids = request.form.getlist("manager_ids")

            department_data = {
                "name": request.form["name"],
                "description": request.form.get("description", ""),
                "user_ids": [int(u) for u in user_ids if u],
                "manager_ids": [int(m) for m in manager_ids if m],
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
        users = extract_items(client.get_users())
    except Exception as e:
        app.logger.exception(e)
        flash("Không thể tải thông tin phòng ban", "danger")
        return redirect(url_for("departments"))

    return render_template("departments/edit.html", department=department, users=users)


@app.route("/departments/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_department(id):
    """Delete a department (only if it has no users and no assets)"""
    try:
        client = get_api_client()
        client.delete_department(id)
        flash("Xóa phòng ban thành công", "success")
    except Exception as e:
        app.logger.exception(e)
        error_msg = str(e)
        if "có tài sản" in error_msg or "có người" in error_msg:
            flash(error_msg, "warning")
        else:
            flash("Không thể xóa phòng ban", "danger")

    return redirect(url_for("departments"))


@app.route("/transfers")
@login_required
@non_viewer_required
def transfers():
    try:
        client = get_api_client()
        # Get all assets to show transfer history
        assets = extract_items(client.get_assets())

        # Collect all transfers from assets
        all_transfers = []
        for asset in assets:
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
@non_viewer_required
def reports():
    report_type = request.args.get("type", "assets")
    filters = {k: v for k, v in request.args.items() if v and k != "type"}

    report_data = None
    departments = []
    users_list = []

    try:
        client = get_api_client()

        # Get departments for filter
        departments = extract_items(client.get_departments())

        # Get users for user activity filter (admin only)
        if session.get("user", {}).get("role") == "admin":
            users_list = extract_items(client.get_users())

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
        assets = extract_items(client.get_assets())

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


# ===== Audit Logs =====
@app.route("/audit-logs")
@login_required
@admin_required
def audit_logs():
    """Display audit logs page with filters"""
    client = get_api_client()

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    offset = (page - 1) * per_page

    # Get filter parameters
    filters = {
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'action': request.args.get('action'),
        'entity_type': request.args.get('entity_type'),
        'limit': per_page,
        'offset': offset
    }

    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    try:
        response = client.get_audit_logs(filters)
        logs = response.get('logs', [])
        total_count = response.get('total_count', 0)

        # Calculate pagination
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None
        }

        return render_template(
            'audit_logs/list.html',
            logs=logs,
            total_count=total_count,
            filters=request.args,
            pagination=pagination
        )
    except Exception as e:
        app.logger.error(f"Error loading audit logs: {str(e)}")
        flash(f"Lỗi khi tải audit logs: {str(e)}", "danger")
        return render_template('audit_logs/list.html', logs=[], total_count=0, filters={}, pagination=None)


@app.route("/api/audit-logs/archived")
@login_required
@admin_required
def get_archived_logs_api():
    """Get list of archived log files"""
    client = get_api_client()
    try:
        result = client.get_archived_logs()
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error getting archived logs: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit-logs/archived/<filename>")
@login_required
@admin_required
def get_archived_log_content_api(filename):
    """Get content of an archived log file"""
    client = get_api_client()
    try:
        result = client.get_archived_log_content(filename)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error getting archived log content: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/audit-logs/archive", methods=["POST"])
@login_required
@admin_required
def trigger_archive_api():
    """Manually trigger log archival"""
    client = get_api_client()
    try:
        result = client.trigger_log_archive()
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error triggering archive: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ===== Settings =====
@app.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    """System settings page"""
    client = get_api_client()

    if request.method == "POST":
        try:
            # Get form data - handle checkboxes (they only send value if checked)
            settings_data = {
                "login_fail_limit": request.form.get("login_fail_limit"),
                "login_block_minutes": request.form.get("login_block_minutes"),
                "audit_archive_days": request.form.get("audit_archive_days"),
                "password_min_length": request.form.get("password_min_length"),
                "password_require_uppercase": "true" if request.form.get("password_require_uppercase") else "false",
                "password_require_lowercase": "true" if request.form.get("password_require_lowercase") else "false",
                "password_require_digit": "true" if request.form.get("password_require_digit") else "false",
                "password_require_special": "true" if request.form.get("password_require_special") else "false",
                "default_items_per_page": request.form.get("default_items_per_page")
            }

            # Update settings
            result = client.update_settings(settings_data)
            flash("Cập nhật cài đặt thành công", "success")
            return redirect(url_for("settings"))
        except Exception as e:
            app.logger.error(f"Error updating settings: {str(e)}")
            flash(f"Lỗi khi cập nhật cài đặt: {str(e)}", "danger")

    # Get current settings
    try:
        settings_list = client.get_settings()
        # Convert list to dict for easier access
        settings_dict = {s["key"]: s for s in settings_list}
    except Exception as e:
        app.logger.error(f"Error loading settings: {str(e)}")
        flash(f"Lỗi khi tải cài đặt: {str(e)}", "danger")
        settings_dict = {}

    return render_template("settings/index.html", settings=settings_dict)


@app.route("/categories")
@login_required
@admin_required
def categories():
    try:
        page = request.args.get('page', 1, type=int)
        sort_by = request.args.get('sort_by', '')
        sort_order = request.args.get('sort_order', 'asc')
        search = request.args.get('search', '')

        client = get_api_client()

        # Build params dict
        params = {}
        if page:
            params['page'] = page
        if sort_by:
            params['sort_by'] = sort_by
        if sort_order:
            params['sort_order'] = sort_order
        if search:
            params['search'] = search

        response = client.get_categories(**params)

        # Extract items and pagination
        if isinstance(response, dict) and 'items' in response:
            categories_list = response['items']
            pagination = response.get('pagination', {})
        else:
            categories_list = response if response else []
            pagination = None

        # Pass filters to template
        filters = {
            'sort_by': sort_by,
            'sort_order': sort_order,
            'search': search
        }

    except Exception as e:
        app.logger.exception(e)
        categories_list = []
        pagination = None
        filters = {}
        flash("Không thể tải danh sách loại tài sản", "warning")

    return render_template("categories/list.html", categories=categories_list, pagination=pagination, filters=filters)


@app.route("/categories/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_category():
    if request.method == "POST":
        try:
            client = get_api_client()
            category_data = {
                "name": request.form["name"],
                "description": request.form.get("description", "")
            }
            client.create_category(category_data)
            flash("Tạo loại tài sản thành công", "success")
            return redirect(url_for("categories"))
        except Exception as e:
            app.logger.exception(e)
            flash(f"Không thể tạo loại tài sản: {str(e)}", "danger")

    return render_template("categories/create.html")


@app.route("/categories/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_category(id):
    try:
        client = get_api_client()

        if request.method == "POST":
            category_data = {
                "name": request.form["name"],
                "description": request.form.get("description", "")
            }
            client.update_category(id, category_data)
            flash("Cập nhật loại tài sản thành công", "success")
            return redirect(url_for("categories"))

        # GET request
        category = client.get_category(id)
        return render_template("categories/edit.html", category=category)

    except Exception as e:
        app.logger.exception(e)
        flash(f"Lỗi: {str(e)}", "danger")
        return redirect(url_for("categories"))


@app.route("/categories/<int:id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_category(id):
    try:
        client = get_api_client()
        client.delete_category(id)
        flash("Xóa loại tài sản thành công", "success")
    except Exception as e:
        app.logger.exception(e)
        flash(f"Không thể xóa loại tài sản: {str(e)}", "danger")

    return redirect(url_for("categories"))


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500
