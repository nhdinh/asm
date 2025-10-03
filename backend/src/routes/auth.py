from datetime import datetime, time, timedelta
import os
from flask import Blueprint, json, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy import desc
from models import ActivityStatus, db, User, UserRole, UserActivity, Department

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    failed_login_limit = os.getenv("LIMITED_LOGIN_LIMIT", 5)
    login_blocked_minutes = os.getenv("LOGIN_BLOCKED_TIME", 1)

    # check for last failed login
    last_login = (
        UserActivity.query.filter_by(username=username)
        .order_by(desc(UserActivity.timestamp))
        .first()
    )

    if (
        last_login is not None
        and last_login.status == ActivityStatus.FAILED
        and last_login.failed_count >= failed_login_limit
        and datetime.now() - last_login.timestamp
        < timedelta(minutes=login_blocked_minutes)
    ):
        return (
            jsonify(
                {
                    "message": f"Login blocked after {failed_login_limit} failed. Try again after {login_blocked_minutes} minutes"
                }
            ),
            401,
        )

    # Create log activity record
    user = User.query.filter_by(username=username).first()
    activity = UserActivity(
        user_id=user.id,
        username=user.username,
        action="login",
        details="User logged in",
        status=ActivityStatus.SUCCESS,
        failed_count=0,
    )

    access_token = None
    if user and user.check_password(password):
        access_token = create_access_token(identity=user.id)
    else:
        # Log activity
        activity.status = ActivityStatus.FAILED
        activity.failed_count = (
            last_login.failed_count + 1
            if last_login is not None and last_login.status == ActivityStatus.FAILED
            else 1
        )

    db.session.add(activity)
    db.session.commit()

    if access_token:
        return jsonify({"access_token": access_token, "user": user.to_dict()}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401


@auth_bp.route("/register", methods=["POST"])
@jwt_required()
def register():
    curr_user_id = get_jwt_identity()
    curr_user = User.query.get(curr_user_id)

    if curr_user.role != UserRole.ADMIN:
        details = f"User {curr_user.username} try adding new user without admin role."
        log_auth_activity(action="create_user", details=details, commit=True)

        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    # Check if user exists
    if User.query.filter_by(username=data["username"]).first():
        details = f"Create user {data['username']} failed. Username already exists."
        log_auth_activity(action="create_user", details=details, commit=True)

        return jsonify({"message": "Username already exists"}), 400

    if User.query.filter_by(email=data["email"]).first():
        details = f"Create user {data['username']} failed. User email exists."
        log_auth_activity(action="create_user", details=details, commit=True)

        return jsonify({"message": "Email already exists"}), 400

    with current_app.app_context():
        user = User(
            username=data["username"],
            email=data["email"],
            role=UserRole[data["role"].upper()],
        )
        user.set_password(data["password"])

        # Add departments (many-to-many relationship)
        if "department_ids" in data:
            for dept_id in data["department_ids"]:
                dept = Department.query.get(dept_id)
                if dept:
                    user.departments.append(dept)

        db.session.add(user)

        log_auth_activity(
            action="create_user", details=f"Created user {user.username}", commit=False
        )
        db.session.commit()

        return jsonify(user.to_dict()), 201


@auth_bp.route("/reset_password", methods=["PUT"])
@jwt_required()
def reset_password():
    curr_user_id = get_jwt_identity()
    curr_user = User.query.get(curr_user_id)

    if curr_user.role != UserRole.ADMIN:
        details = f"User {curr_user.username} try adding new user without admin role."
        log_auth_activity(action="create_user", details=details, commit=True)

        return jsonify({"message": "Unauthorized"}), 403

    data = request.json


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return jsonify(user.to_dict())


@jwt_required()
def log_auth_activity(
    action: str,
    details: str,
    status: ActivityStatus = ActivityStatus.FAILED,
    commit: bool = False,
):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    # create activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
        action=action,
        entity_type="user",
        entity_id=current_user_id,
        details=details,
        status=status,
    )
    db.session.add(activity)

    # commit if outside app_context()
    if commit:
        db.session.commit()
