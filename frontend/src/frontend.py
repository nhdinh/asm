from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
import requests
import os
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder="/app/templates/")
app.secret_key = os.getenv("SECRET_KEY", "frontend-secret-key")

# Backend API URL
API_URL = os.getenv("API_URL", "http://backend:5000/api")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "token" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def get_headers():
    return {"Authorization": f"Bearer {session.get('token')}"}


@app.route("/")
def index():
    if "token" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = {
            "username": request.form["username"],
            "password": request.form["password"],
        }
        response = requests.post(f"{API_URL}/auth/login", json=data)

        if response.status_code == 200:
            result = response.json()
            session["token"] = result["access_token"]
            session["user"] = result["user"]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    response = requests.get(f"{API_URL}/reports/dashboard", headers=get_headers())
    stats = response.json() if response.status_code == 200 else {}
    return render_template("dashboard.html", stats=stats, user=session["user"])


@app.route("/departments")
@login_required
def departments():
    response = requests.get(f"{API_URL}/departments", headers=get_headers())
    departments = response.json() if response.status_code == 200 else []
    return render_template(
        "departments.html", departments=departments, user=session["user"]
    )


@app.route("/assets")
@login_required
def assets():
    response = requests.get(f"{API_URL}/assets", headers=get_headers())
    assets = response.json() if response.status_code == 200 else []

    response_dept = requests.get(f"{API_URL}/departments", headers=get_headers())
    departments = response_dept.json() if response_dept.status_code == 200 else []

    return render_template(
        "assets.html", assets=assets, departments=departments, user=session["user"]
    )


@app.route("/reports")
@login_required
def reports():
    report_type = request.args.get("type", "assets")
    filters = {k: v for k, v in request.args.items() if k != "type"}

    if report_type == "user-activities":
        endpoint = "/reports/user-activities"
    else:
        endpoint = "/reports/assets"

    response = requests.get(
        f"{API_URL}{endpoint}", params=filters, headers=get_headers()
    )
    report_data = response.json() if response.status_code == 200 else {}

    return render_template(
        "reports.html", report_data=report_data, user=session["user"]
    )


# API endpoints for AJAX calls
@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
@login_required
def proxy_api(path):
    url = f"{API_URL}/{path}"

    if request.method == "GET":
        response = requests.get(url, params=request.args, headers=get_headers())
    elif request.method == "POST":
        response = requests.post(url, json=request.json, headers=get_headers())
    elif request.method == "PUT":
        response = requests.put(url, json=request.json, headers=get_headers())
    elif request.method == "DELETE":
        response = requests.delete(url, headers=get_headers())

    return response.content, response.status_code, response.headers.items()


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
    return (render_template("errors/500.html"),)
