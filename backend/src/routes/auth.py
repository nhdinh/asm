from datetime import datetime, time, timedelta
import os
from flask import Blueprint, json, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy import desc
from models import ActivityStatus, db, User, UserRole, UserActivity, Department, SystemSetting
from audit_logger import audit_logger
from password_policy import PasswordPolicy

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

    # Find user
    user = User.query.filter_by(username=username).first()

    # Check if user exists and password is correct
    access_token = None
    if user and user.check_password(password):
        access_token = create_access_token(identity=user.id)

        # Create success activity record
        activity = UserActivity(
            user_id=user.id,
            username=user.username,
            action="login",
            details="User logged in",
            status=ActivityStatus.SUCCESS,
            failed_count=0,
        )
        db.session.add(activity)
        db.session.commit()
    else:
        # Create failed activity record (only if user exists)
        if user:
            activity = UserActivity(
                user_id=user.id,
                username=user.username,
                action="login",
                details="Failed login attempt",
                status=ActivityStatus.FAILED,
                failed_count=(
                    last_login.failed_count + 1
                    if last_login is not None and last_login.status == ActivityStatus.FAILED
                    else 1
                ),
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
    current_app.logger.info(f"Register request data: {data}")

    # Validate required fields
    if not data.get("username"):
        return jsonify({"message": "Username is required"}), 400
    if not data.get("email"):
        return jsonify({"message": "Email is required"}), 400
    if not data.get("password"):
        return jsonify({"message": "Password is required"}), 400
    if not data.get("role"):
        return jsonify({"message": "Role is required"}), 400

    # Validate password against policy only if must_change_password is False
    # If must_change_password is True, user will be forced to set a policy-compliant password on first login
    must_change_password = data.get("must_change_password", False)
    if not must_change_password:
        is_valid, errors = PasswordPolicy.validate_password(data["password"])
        if not is_valid:
            return jsonify({
                "message": "Mật khẩu không đáp ứng yêu cầu chính sách",
                "errors": errors
            }), 400

    # Check if user exists
    if User.query.filter_by(username=data["username"]).first():
        details = f"Create user {data['username']} failed. Username already exists."
        log_auth_activity(action="create_user", details=details, commit=True)

        return jsonify({"message": "Username already exists"}), 400

    if User.query.filter_by(email=data["email"]).first():
        details = f"Create user {data['username']} failed. User email exists."
        log_auth_activity(action="create_user", details=details, commit=True)

        return jsonify({"message": "Email already exists"}), 400

    # Validate non-admins must belong to at least one department
    role = UserRole[data["role"].upper()]
    department_ids = data.get("department_ids", [])

    if role != UserRole.ADMIN and (not department_ids or len(department_ids) == 0):
        return jsonify({"message": "Non-admin users must be assigned to at least one department"}), 400

    try:
        with current_app.app_context():
            user = User(
                username=data["username"],
                fullname=data.get("fullname"),
                email=data["email"],
                role=role,
                must_change_password=data.get("must_change_password", False),
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
    except KeyError as e:
        current_app.logger.error(f"Missing required field: {str(e)}")
        return jsonify({"message": f"Missing required field: {str(e)}"}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error creating user: {str(e)}")
        return jsonify({"message": f"Error creating user: {str(e)}"}), 500


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


@auth_bp.route("/password-policy", methods=["GET"])
def get_password_policy():
    """Get password policy requirements (public endpoint)"""
    policy = PasswordPolicy.get_policy_settings()
    requirements = PasswordPolicy.get_policy_description()

    return jsonify({
        "policy": policy,
        "requirements": requirements,
        "description": "Mật khẩu phải đáp ứng các yêu cầu: " + ", ".join(requirements)
    })


@auth_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.json

    old_values = user.to_dict()

    # Users can update their own fullname, email, and items_per_page
    if "fullname" in data:
        user.fullname = data["fullname"]
    if "email" in data:
        # Check if email already exists for another user
        existing_user = User.query.filter_by(email=data["email"]).first()
        if existing_user and existing_user.id != user.id:
            return jsonify({"message": "Email already exists"}), 400
        user.email = data["email"]
    if "items_per_page" in data:
        # Validate items_per_page value
        items_per_page = data["items_per_page"]
        if items_per_page is not None:
            try:
                items_per_page = int(items_per_page) if items_per_page != '' else None
                if items_per_page is not None and (items_per_page < 5 or items_per_page > 100):
                    return jsonify({"message": "Items per page must be between 5 and 100"}), 400
            except (ValueError, TypeError):
                return jsonify({"message": "Invalid items per page value"}), 400
        user.items_per_page = items_per_page

    # Log activity
    activity = UserActivity(
        user_id=user_id,
        username=user.username,
        action="update_profile",
        entity_type="user",
        entity_id=user.id,
        details=f"User {user.username} updated their profile",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=user_id,
        username=user.username,
        action='update_profile',
        entity_type='user',
        entity_id=user.id,
        old_values=old_values,
        new_values=user.to_dict(),
        details=f"User {user.username} updated their profile",
        ip_address=request.remote_addr
    )

    return jsonify(user.to_dict())


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.json

    # Validate new password is provided
    if not data.get("new_password"):
        return jsonify({"message": "New password is required"}), 400

    # Validate password against policy
    is_valid, errors = PasswordPolicy.validate_password(data["new_password"])
    if not is_valid:
        return jsonify({
            "message": "Mật khẩu không đáp ứng yêu cầu chính sách",
            "errors": errors
        }), 400

    # If user must change password (first login), allow without old password
    if not user.must_change_password:
        # Regular password change - verify old password
        if not user.check_password(data.get("old_password", "")):
            # Log failed attempt
            activity = UserActivity(
                user_id=user_id,
                username=user.username,
                action="change_password",
                entity_type="user",
                entity_id=user.id,
                details=f"Failed password change attempt - incorrect old password",
                status=ActivityStatus.FAILED,
            )
            db.session.add(activity)
            db.session.commit()

            # Audit log
            audit_logger.log(
                user_id=user_id,
                username=user.username,
                action='change_password_failed',
                entity_type='user',
                entity_id=user.id,
                details="Failed password change attempt - incorrect old password",
                ip_address=request.remote_addr
            )
            return jsonify({"message": "Mật khẩu cũ không đúng"}), 400

    # Set new password
    user.set_password(data["new_password"])

    # Clear must_change_password flag if it was set
    was_first_change = user.must_change_password
    if user.must_change_password:
        user.must_change_password = False

    # Log activity
    activity = UserActivity(
        user_id=user_id,
        username=user.username,
        action="change_password",
        entity_type="user",
        entity_id=user.id,
        details=f"User {user.username} changed their password" + (" (first login)" if was_first_change else ""),
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=user_id,
        username=user.username,
        action='change_password',
        entity_type='user',
        entity_id=user.id,
        old_values={'password': '[REDACTED]'},
        new_values={'password': '[REDACTED]'},
        details=f"User {user.username} changed their password" + (" (first login)" if was_first_change else ""),
        ip_address=request.remote_addr
    )

    return jsonify({"message": "Mật khẩu đã được thay đổi thành công", "user": user.to_dict()})


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
