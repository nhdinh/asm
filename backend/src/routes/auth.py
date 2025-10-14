from datetime import datetime, time, timedelta
import os
import uuid
from flask import Blueprint, json, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from sqlalchemy import desc
from models import (
    ActivityStatus,
    Profile,
    db,
    ProfileRole,
    UserActivity,
    Department,
    SystemSetting,
)
from audit_logger import audit_logger
from password_policy import PasswordPolicy
from auth_client import auth_client

auth_bp = Blueprint("auth", __name__)

# Flag to use auth service (set to True to enable)
USE_AUTH_SERVICE = True


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login endpoint - proxies to auth service
    Backend no longer handles authentication directly
    """
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # Always use auth microservice for authentication
    success, response_data, error_msg = auth_client.login(username, password)

    if success:
        # Audit log for successful login
        user_data = response_data.get("user", {})

        with current_app.app_context():
            # check if user has been saved in profile data
            profile = Profile.query.filter_by(username=user_data["username"]).first()
            if profile is None:
                # create new profile
                profile = Profile(
                    username=user_data["username"],
                    email=user_data["email"],
                    fullname=user_data.get("fullname", ""),
                    role=user_data["role"],
                    user_type=user_data["user_type"],
                    is_ad_user=(user_data["user_type"] == "ad"),
                )

                db.session.add(profile)
                db.session.flush()

            audit_logger.log(
                user_id=profile.id,
                username=username,
                action="login",
                entity_type="user",
                entity_id=user_data.get("id"),
                details="User logged in successfully via auth service",
                ip_address=request.remote_addr,
            )

            db.session.commit()

            return jsonify(response_data), 200
    else:
        # Audit log for failed login
        audit_logger.log(
            user_id=None,
            username=username,
            action="login_failed",
            entity_type="user",
            details=f"Failed login attempt: {error_msg}",
            ip_address=request.remote_addr,
        )
        return (
            jsonify({"message": error_msg or "Tên đăng nhập hoặc mật khẩu không đúng"}),
            401,
        )


@auth_bp.route("/register", methods=["POST"])
@jwt_required()
def register():
    sess_profile_id = get_jwt_identity()
    sess_profile = Profile.query.get(sess_profile_id)

    if sess_profile.role != ProfileRole.ADMIN:
        details = (
            f"User {sess_profile.username} try adding new user without admin role."
        )
        log_auth_activity(action="create_user", details=details, commit=True)

        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    log_data = data
    log_data["password"] = "*****"
    current_app.logger.info(f"Register request data: {log_data}")

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
            return (
                jsonify(
                    {
                        "message": "Mật khẩu không đáp ứng yêu cầu chính sách",
                        "errors": errors,
                    }
                ),
                400,
            )

    # check for user exists in auth service
    success, existing_user = auth_client.get_user_by_username(username=data["username"])
    if success:
        details = f"Create user {data['username']} failed. Username already exists."
        log_auth_activity(action="create_user", details=details, commit=True)

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
    role = ProfileRole[data["role"].upper()]
    department_ids = data.get("department_ids", [])

    if role != ProfileRole.ADMIN and (not department_ids or len(department_ids) == 0):
        return (
            jsonify(
                {
                    "message": "Non-admin users must be assigned to at least one department"
                }
            ),
            400,
        )

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

            db.session.add(user)
            db.session.flush()  # Get user.id before commit

            # Add departments (many-to-many relationship) with is_manager flag
            if "department_ids" in data:
                from models import ProfileDepartment

                manager_dept_ids = data.get("manager_department_ids", [])

                for dept_id in data["department_ids"]:
                    dept = Department.query.get(dept_id)
                    if dept:
                        is_manager = dept_id in manager_dept_ids
                        assoc = ProfileDepartment(
                            user_id=user.id,
                            department_id=dept_id,
                            is_manager=is_manager,
                        )
                        db.session.add(assoc)

            log_auth_activity(
                action="create_user",
                details=f"Created user {user.username}",
                commit=False,
            )
            db.session.commit()

            # Audit log
            audit_logger.log(
                user_id=sess_profile_id,
                username=sess_profile.username,
                action="create",
                entity_type="user",
                entity_id=user.id,
                new_values=user.to_dict(),
                details=f"Created user {user.username}",
                ip_address=request.remote_addr,
            )

            # Enqueue welcome email to be sent asynchronously
            try:
                from email_queue import email_queue

                email_queued = email_queue.enqueue_welcome_email(
                    user_email=user.email,
                    username=user.username,
                    password=data["password"],
                    fullname=user.fullname,
                )
                if email_queued:
                    current_app.logger.info(f"Welcome email queued for {user.email}")
                else:
                    current_app.logger.warning(
                        f"Failed to queue welcome email for {user.email}"
                    )
            except Exception as e:
                current_app.logger.error(f"Error queueing welcome email: {str(e)}")
                # Don't fail user creation if email queueing fails

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

    if curr_user.role != ProfileRole.ADMIN:
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


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    """Get current authenticated user details (alias for /profile)"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return jsonify(user.to_dict())


@auth_bp.route("/password-policy", methods=["GET"])
def get_password_policy():
    """Get password policy requirements (public endpoint)"""
    policy = PasswordPolicy.get_policy_settings()
    requirements = PasswordPolicy.get_policy_description()

    return jsonify(
        {
            "policy": policy,
            "requirements": requirements,
            "description": "Mật khẩu phải đáp ứng các yêu cầu: "
            + ", ".join(requirements),
        }
    )


@auth_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    profile_username = get_jwt_identity()
    profile = Profile.query.filter_by(username=profile_username).first()
    data = request.json

    old_values = profile.to_dict()

    # Users can update their own fullname, email, and items_per_page
    if "fullname" in data:
        profile.fullname = data["fullname"]
    if "email" in data:
        # Check if email already exists for another user
        existing_user = Profile.query.filter_by(email=data["email"]).first()
        if existing_user and existing_user.id != profile.id:
            return jsonify({"message": "Email already exists"}), 400
        profile.email = data["email"]
    if "items_per_page" in data:
        # Validate items_per_page value
        items_per_page = data["items_per_page"]
        if items_per_page is not None:
            try:
                items_per_page = int(items_per_page) if items_per_page != "" else None
                if items_per_page is not None and (
                    items_per_page < 5 or items_per_page > 100
                ):
                    return (
                        jsonify(
                            {"message": "Items per page must be between 5 and 100"}
                        ),
                        400,
                    )
            except (ValueError, TypeError):
                return jsonify({"message": "Invalid items per page value"}), 400
        profile.items_per_page = items_per_page

    # Log activity
    activity = UserActivity(
        user_id=profile_username,
        username=profile.username,
        action="update_profile",
        entity_type="user",
        entity_id=profile.id,
        details=f"User {profile.username} updated their profile",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=profile_username,
        username=profile.username,
        action="update_profile",
        entity_type="user",
        entity_id=profile.id,
        old_values=old_values,
        new_values=profile.to_dict(),
        details=f"User {profile.username} updated their profile",
        ip_address=request.remote_addr,
    )

    return jsonify(profile.to_dict())


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    profile_username = get_jwt_identity()
    profile = Profile.query.filter_by(username=profile_username).first()
    data = request.json

    # Validate new password is provided
    if not data.get("new_password"):
        return jsonify({"message": "New password is required"}), 400

    # Validate password against policy
    is_valid, errors = PasswordPolicy.validate_password(data["new_password"])
    if not is_valid:
        return (
            jsonify(
                {
                    "message": "Mật khẩu không đáp ứng yêu cầu chính sách",
                    "errors": errors,
                }
            ),
            400,
        )

    # If user must change password (first login), allow without old password
    if not profile.must_change_password:
        # Regular password change - verify old password
        if not profile.check_password(data.get("old_password", "")):
            # Log failed attempt
            activity = UserActivity(
                user_id=profile_username,
                username=profile.username,
                action="change_password",
                entity_type="user",
                entity_id=profile.id,
                details=f"Failed password change attempt - incorrect old password",
                status=ActivityStatus.FAILED,
            )
            db.session.add(activity)
            db.session.commit()

            # Audit log
            audit_logger.log(
                user_id=profile_username,
                username=profile.username,
                action="change_password_failed",
                entity_type="user",
                entity_id=profile.id,
                details="Failed password change attempt - incorrect old password",
                ip_address=request.remote_addr,
            )
            return jsonify({"message": "Mật khẩu cũ không đúng"}), 400

    # Set new password
    profile.set_password(data["new_password"])

    # Clear must_change_password flag if it was set
    was_first_change = profile.must_change_password
    if profile.must_change_password:
        profile.must_change_password = False

    # Log activity
    activity = UserActivity(
        user_id=profile_username,
        username=profile.username,
        action="change_password",
        entity_type="user",
        entity_id=profile.id,
        details=f"User {profile.username} changed their password"
        + (" (first login)" if was_first_change else ""),
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=profile_username,
        username=profile.username,
        action="change_password",
        entity_type="user",
        entity_id=profile.id,
        old_values={"password": "[REDACTED]"},
        new_values={"password": "[REDACTED]"},
        details=f"User {profile.username} changed their password"
        + (" (first login)" if was_first_change else ""),
        ip_address=request.remote_addr,
    )

    return jsonify(
        {"message": "Mật khẩu đã được thay đổi thành công", "user": profile.to_dict()}
    )


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Logout user and revoke tokens (when using auth service)"""
    if USE_AUTH_SERVICE:
        # Get access token from request header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            access_token = auth_header[7:]

            current_profile_username = get_jwt_identity()
            current_profile = Profile.query.filter_by(
                username=current_profile_username
            ).first()

            data = request.get_json() or {}
            revoke_all = data.get("revoke_all", False)

            success = auth_client.logout(access_token, revoke_all)
            current_app.logger.error(f"success = {success}")

            if success:
                audit_logger.log(
                    user_id=current_profile.id,
                    username=current_profile.username if current_profile else "unknown",
                    action="logout",
                    entity_type="user",
                    details=f"User logged out {'(all sessions)' if revoke_all else ''}",
                    ip_address=request.remote_addr,
                )

                return jsonify({"message": "Đăng xuất thành công"}), 200
            else:
                return (
                    jsonify({"message": "Đăng xuất thất bại"}),
                    500,
                )
        else:
            return jsonify({"message": "Invalid authorization header"}), 401
    else:
        # Legacy logout (just return success, token expires naturally)
        current_profile_username = get_jwt_identity()
        user = Profile.query.filter_by(current_profile=current_profile_username)

        audit_logger.log(
            user_id=current_profile.id,
            username=user.username if user else "unknown",
            action="logout",
            entity_type="user",
            details="User logged out",
            ip_address=request.remote_addr,
        )

        return jsonify({"message": "Đăng xuất thành công"}), 200


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """Refresh access token (when using auth service)"""
    if USE_AUTH_SERVICE:
        # Get refresh token from request header or body
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            refresh_token = auth_header[7:]

            success, token_data = auth_client.refresh_token(refresh_token)

            if success:
                return jsonify(token_data), 200
            else:
                return jsonify({"message": "Token refresh failed"}), 401
        else:
            return jsonify({"message": "Invalid authorization header"}), 401
    else:
        return jsonify({"message": "Token refresh not supported in legacy mode"}), 501


@auth_bp.route("/sessions", methods=["GET"])
@jwt_required()
def get_sessions():
    """Get active sessions for current user (when using auth service)"""
    if USE_AUTH_SERVICE:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            access_token = auth_header[7:]

            sessions_data = auth_client.get_sessions(access_token)

            if sessions_data:
                return jsonify(sessions_data), 200
            else:
                return jsonify({"message": "Failed to get sessions"}), 500
        else:
            return jsonify({"message": "Invalid authorization header"}), 401
    else:
        return jsonify({"message": "Sessions not supported in legacy mode"}), 501


@jwt_required()
def log_auth_activity(
    action: str,
    details: str,
    status: ActivityStatus = ActivityStatus.FAILED,
    commit: bool = False,
):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # create activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action=action,
        entity_type="user",
        entity_id=current_profile.id,
        details=details,
        status=status,
    )
    db.session.add(activity)

    # commit if outside app_context()
    if commit:
        db.session.commit()
