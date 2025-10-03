from datetime import datetime, time, timedelta
import os
from flask import Blueprint, json, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy import desc
from models import ActivityStatus, db, User, UserRole, UserActivity, Department, SystemSetting
from audit_logger import audit_logger

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # Get settings from database or fallback to env/defaults
    fail_limit_setting = SystemSetting.query.filter_by(key="login_fail_limit").first()
    block_time_setting = SystemSetting.query.filter_by(key="login_block_minutes").first()

    failed_login_limit = fail_limit_setting.get_typed_value() if fail_limit_setting else int(os.getenv("LIMITED_LOGIN_LIMIT", "5"))
    login_blocked_minutes = block_time_setting.get_typed_value() if block_time_setting else int(os.getenv("LOGIN_BLOCKED_TIME", "5"))

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
        # Audit log for blocked login attempt
        audit_logger.log(
            user_id=last_login.user_id,
            username=username,
            action='login_blocked',
            entity_type='user',
            details=f"Login blocked for {username} after {failed_login_limit} failed attempts. Attempts: {last_login.failed_count}",
            ip_address=request.remote_addr
        )

        return (
            jsonify(
                {
                    "message": f"Tài khoản tạm thời bị khóa sau {failed_login_limit} lần đăng nhập sai. Vui lòng thử lại sau {login_blocked_minutes} phút."
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

    # Audit log for successful login
    if access_token:
        audit_logger.log(
            user_id=user.id,
            username=user.username,
            action='login',
            entity_type='user',
            entity_id=user.id,
            details="User logged in successfully",
            ip_address=request.remote_addr
        )
        return jsonify({"access_token": access_token, "user": user.to_dict()}), 200
    else:
        # Audit log for failed login
        audit_logger.log(
            user_id=user.id if user else None,
            username=username,
            action='login_failed',
            entity_type='user',
            details=f"Failed login attempt for username: {username}. Failed count: {activity.failed_count}/{failed_login_limit}",
            ip_address=request.remote_addr
        )
        return jsonify({"message": "Tên đăng nhập hoặc mật khẩu không đúng"}), 401


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
            fullname=data.get("fullname"),
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
        db.session.flush()  # Get user.id before commit

        log_auth_activity(
            action="create_user", details=f"Created user {user.username}", commit=False
        )
        db.session.commit()

        # Audit log
        audit_logger.log(
            user_id=curr_user_id,
            username=curr_user.username,
            action='create',
            entity_type='user',
            entity_id=user.id,
            new_values=user.to_dict(),
            details=f"Created user {user.username}",
            ip_address=request.remote_addr
        )

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
