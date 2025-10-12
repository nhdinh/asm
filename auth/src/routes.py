from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from .models import db, User, RefreshToken, LoginAttempt, UserType
from werkzeug.exceptions import BadRequest
import logging

logger = logging.getLogger(__name__)

auth_routes = Blueprint("auth", __name__)


@auth_routes.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "authentication"}), 200


@auth_routes.route("/login", methods=["POST"])
def login():
    """
    Authenticate user and issue tokens

    Request body:
    {
        "username": "string",
        "password": "string",
        "auth_type": "local|ad"  // optional, defaults to "local"
    }

    Response:
    {
        "access_token": "string",
        "refresh_token": "string",
        "expires_in": int,
        "user": {...}
    }
    """
    try:
        data = request.get_json()
        if not data:
            raise BadRequest("Request body is required")

        username = data.get("username")
        password = data.get("password")
        auth_type = data.get("auth_type", "local")

        if not username or not password:
            return jsonify({"message": "Username and password are required"}), 400

        # Check for account lockout
        if _is_account_locked(username):
            lockout_minutes = current_app.config["ACCOUNT_LOCKOUT_MINUTES"]
            _log_login_attempt(
                username, False, f"Account locked after too many failed attempts"
            )

            return (
                jsonify(
                    {
                        "message": f"Tài khoản tạm thời bị khóa do đăng nhập sai quá nhiều lần. Vui lòng thử lại sau {lockout_minutes} phút."
                    }
                ),
                401,
            )

        # Authenticate user
        user = None
        auth_success = False
        auth_error = None

        if auth_type == "ad" and current_app.config["AD_ENABLED"]:
            # Active Directory authentication
            ad_auth = current_app.ad_authenticator
            success, user_info, error = ad_auth.authenticate(username, password)

            if success:
                # Get or create user from AD info
                user = _get_or_create_ad_user(user_info)
                auth_success = True
            else:
                auth_error = error
        else:
            # Local database authentication
            user = User.query.filter_by(username=username, deleted_at=None).first()

            if (
                user
                and user.user_type == UserType.LOCAL
                and user.check_password(password)
            ):
                auth_success = True
            elif user and user.user_type != UserType.LOCAL:
                auth_error = (
                    f"User must authenticate via {user.user_type.value.upper()}"
                )
            else:
                auth_error = "Invalid credentials"

        if not auth_success or not user:
            _log_login_attempt(username, False, auth_error or "Invalid credentials")
            _increment_failed_attempts(username)

            return jsonify({"message": "Tên đăng nhập hoặc mật khẩu không đúng"}), 401

        # Generate tokens
        token_manager = current_app.token_manager
        tokens = token_manager.create_tokens(
            user_id=user.id,
            username=user.username,
            role=user.role,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", ""),
        )

        # Store refresh token in database
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_jti=tokens["refresh_token_jti"],
            access_token_jti=tokens["access_token_jti"],
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", ""),
            expires_at=datetime.utcnow()
            + current_app.config["JWT_REFRESH_TOKEN_EXPIRES"],
        )
        db.session.add(refresh_token_record)
        db.session.commit()

        # Log successful login
        _log_login_attempt(username, True, "Login successful")
        _clear_failed_attempts(username)

        logger.info(
            f"User {username} logged in successfully from {request.remote_addr}"
        )

        return (
            jsonify(
                {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "expires_in": tokens["expires_in"],
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "fullname": user.fullname,
                        "role": user.role,
                        "user_type": (
                            user.user_type.value
                            if isinstance(user.user_type, UserType)
                            else user.user_type
                        ),
                        "is_ad_user": user.is_ad_user,  # Backward compatibility
                    },
                }
            ),
            200,
        )

    except BadRequest as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500


@auth_routes.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token using refresh token

    Response:
    {
        "access_token": "string",
        "expires_in": int
    }
    """
    try:
        current_profile_id = get_jwt_identity()
        jwt_data = get_jwt()
        refresh_jti = jwt_data.get("jti")

        # Verify refresh token exists in database
        refresh_token = RefreshToken.query.filter_by(
            token_jti=refresh_jti, is_revoked=False
        ).first()

        if not refresh_token:
            return jsonify({"message": "Invalid or revoked refresh token"}), 401

        # Check if token is expired
        if refresh_token.expires_at < datetime.utcnow():
            return jsonify({"message": "Refresh token expired"}), 401

        # Generate new access token
        token_manager = current_app.token_manager
        new_tokens = token_manager.refresh_access_token(
            refresh_jti=refresh_jti,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", ""),
        )

        if not new_tokens:
            return jsonify({"message": "Failed to refresh token"}), 401

        # Update refresh token's access_token_jti
        refresh_token.access_token_jti = new_tokens["access_token_jti"]
        db.session.commit()

        logger.info(f"Access token refreshed for user ID: {current_profile_id}")

        return (
            jsonify(
                {
                    "access_token": new_tokens["access_token"],
                    "expires_in": new_tokens["expires_in"],
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500


@auth_routes.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """
    Logout user and revoke tokens

    Request body (optional):
    {
        "revoke_all": bool  // Revoke all user sessions
    }
    """
    try:
        current_profile_id = get_jwt_identity()
        jwt_data = get_jwt()
        access_jti = jwt_data.get("jti")

        data = request.get_json() or {}
        revoke_all = data.get("revoke_all", False)

        token_manager = current_app.token_manager

        if revoke_all:
            # Revoke all tokens for user
            count = token_manager.revoke_user_tokens(current_profile_id)

            # Mark all refresh tokens as revoked in database
            RefreshToken.query.filter_by(
                user_id=current_profile_id, is_revoked=False
            ).update({"is_revoked": True, "revoked_at": datetime.utcnow()})
            db.session.commit()

            logger.info(f"Revoked all {count} tokens for user ID: {current_profile_id}")
            return jsonify({"message": "All sessions logged out successfully"}), 200
        else:
            # Revoke current access token
            token_manager.revoke_token(access_jti, "access")

            # Find and revoke associated refresh token
            token_info = token_manager.get_token_info(access_jti, "access")
            if token_info and token_info.get("refresh_jti"):
                refresh_jti = token_info["refresh_jti"]
                token_manager.revoke_token(refresh_jti, "refresh")

                # Mark refresh token as revoked in database
                RefreshToken.query.filter_by(token_jti=refresh_jti).update(
                    {"is_revoked": True, "revoked_at": datetime.utcnow()}
                )
                db.session.commit()

            logger.info(f"User ID {current_profile_id} logged out")
            return jsonify({"message": "Logged out successfully"}), 200

    except Exception as e:
        logger.error(f"Logout error: {str(e)}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500


@auth_routes.route("/verify", methods=["POST"])
@jwt_required()
def verify():
    """
    Verify token validity

    Response:
    {
        "valid": bool,
        "user": {...}
    }
    """
    try:
        current_profile_id = get_jwt_identity()
        jwt_data = get_jwt()

        user = User.query.get(current_profile_id)
        if not user or user.deleted_at:
            return jsonify({"valid": False, "message": "User not found"}), 401

        return (
            jsonify(
                {
                    "valid": True,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "fullname": user.fullname,
                        "role": user.role,
                        "user_type": (
                            user.user_type.value
                            if isinstance(user.user_type, UserType)
                            else user.user_type
                        ),
                        "is_ad_user": user.is_ad_user,  # Backward compatibility
                    },
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Token verification error: {str(e)}", exc_info=True)
        return jsonify({"valid": False, "message": "Invalid token"}), 401


@auth_routes.route("/sessions", methods=["GET"])
@jwt_required()
def get_sessions():
    """Get all active sessions for current user"""
    try:
        current_profile_id = get_jwt_identity()

        token_manager = current_app.token_manager
        sessions = token_manager.get_user_active_sessions(current_profile_id)

        return jsonify({"sessions": sessions}), 200

    except Exception as e:
        logger.error(f"Get sessions error: {str(e)}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500


@auth_routes.route("/users/<username>", methods=["GET"])
@jwt_required()
def get_user_by_username(username):
    """
    Get user information by username

    Response:
    {
        "user": {
            "id": int,
            "username": "string",
            "email": "string",
            "fullname": "string",
            "role": "string",
            "user_type": "string",
            "is_ad_user": bool
        }
    }
    """
    try:
        # Get current user from JWT
        current_profile_id = get_jwt_identity()
        current_profile = User.query.get(current_profile_id)

        if not current_profile:
            return jsonify({"message": "Current user not found"}), 401

        # Find user by username (excluding deleted users)
        user = User.query.filter_by(username=username, deleted_at=None).first()

        if not user:
            return jsonify({"message": "User not found"}), 404

        # Return user information
        return (
            jsonify(
                {
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "fullname": user.fullname,
                        "role": user.role,
                        "user_type": (
                            user.user_type.value
                            if isinstance(user.user_type, UserType)
                            else user.user_type
                        ),
                        "is_ad_user": user.is_ad_user,
                    }
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Get user by username error: {str(e)}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500


@auth_routes.route("/users/id/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user_by_id(user_id):
    """
    Get user information by user ID

    Response:
    {
        "user": {
            "id": int,
            "username": "string",
            "email": "string",
            "fullname": "string",
            "role": "string",
            "user_type": "string",
            "is_ad_user": bool
        }
    }
    """
    try:
        # Get current user from JWT
        current_profile_id = get_jwt_identity()
        current_profile = User.query.get(current_profile_id)

        if not current_profile:
            return jsonify({"message": "Current user not found"}), 401

        # Find user by ID (excluding deleted users)
        user = User.query.filter_by(id=user_id, deleted_at=None).first()

        if not user:
            return jsonify({"message": "User not found"}), 404

        # Return user information
        return (
            jsonify(
                {
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "fullname": user.fullname,
                        "role": user.role,
                        "user_type": (
                            user.user_type.value
                            if isinstance(user.user_type, UserType)
                            else user.user_type
                        ),
                        "is_ad_user": user.is_ad_user,
                    }
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Get user by ID error: {str(e)}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500


@auth_routes.route("/users", methods=["GET"])
@jwt_required()
def list_users():
    """
    List all users (admin only)

    Query parameters:
    - include_deleted: bool (default: false)
    - user_type: string (filter by user type: local, ad, sso)
    - search: string (search by username, email, or fullname)

    Response:
    {
        "users": [
            {
                "id": int,
                "username": "string",
                "email": "string",
                "fullname": "string",
                "role": "string",
                "user_type": "string",
                "is_ad_user": bool
            }
        ],
        "total": int
    }
    """
    try:
        # Get current user from JWT
        current_profile_id = get_jwt_identity()
        current_profile = User.query.get(current_profile_id)

        if not current_profile:
            return jsonify({"message": "Current user not found"}), 401

        # Only admins can list all users
        if current_profile.role != "ADMIN":
            return jsonify({"message": "Unauthorized - admin only"}), 403

        # Build query
        query = User.query

        # Filter by deleted status
        include_deleted = request.args.get("include_deleted", "false").lower() == "true"
        if not include_deleted:
            query = query.filter_by(deleted_at=None)

        # Filter by user type
        user_type_filter = request.args.get("user_type")
        if user_type_filter:
            query = query.filter_by(user_type=user_type_filter)

        # Search filter
        search = request.args.get("search")
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                db.or_(
                    User.username.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.fullname.ilike(search_pattern),
                )
            )

        # Execute query
        users = query.all()

        # Build response
        users_data = [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "fullname": user.fullname,
                "role": user.role,
                "user_type": (
                    user.user_type.value
                    if isinstance(user.user_type, UserType)
                    else user.user_type
                ),
                "is_ad_user": user.is_ad_user,
            }
            for user in users
        ]

        return jsonify({"users": users_data, "total": len(users_data)}), 200

    except Exception as e:
        logger.error(f"List users error: {str(e)}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500


@auth_routes.route("/users", methods=["POST"])
@jwt_required()
def create_user():
    """
    Create a new user (admin only)

    Request body:
    {
        "username": "string" (required),
        "email": "string" (required),
        "password": "string" (required for local users),
        "fullname": "string" (optional),
        "role": "ADMIN|USER" (optional, default: USER),
        "user_type": "local|ad|sso" (optional, default: local)
    }

    Response:
    {
        "message": "User created successfully",
        "user": {
            "id": int,
            "username": "string",
            "email": "string",
            "fullname": "string",
            "role": "string",
            "user_type": "string",
            "is_ad_user": bool
        }
    }
    """
    try:
        # Get current user from JWT
        current_profile_id = get_jwt_identity()
        current_profile = User.query.get(current_profile_id)

        if not current_profile:
            return jsonify({"message": "Current user not found"}), 401

        # Only admins can create users
        if current_profile.role != "ADMIN":
            return jsonify({"message": "Unauthorized - admin only"}), 403

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"message": "Request body is required"}), 400

        # Validate required fields
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()

        if not username:
            return jsonify({"message": "Username is required"}), 400

        if not email:
            return jsonify({"message": "Email is required"}), 400

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"message": "Username already exists"}), 400

        # Check if email already exists
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            return jsonify({"message": "Email already exists"}), 400

        # Get optional fields
        fullname = data.get("fullname", "").strip() or None
        role = data.get("role", "USER").upper()
        user_type_str = data.get("user_type", "local").lower()

        # Validate role
        if role not in ["ADMIN", "USER"]:
            return jsonify({"message": "Invalid role. Must be ADMIN or USER"}), 400

        # Validate user_type
        if user_type_str not in ["local", "ad", "sso"]:
            return (
                jsonify({"message": "Invalid user_type. Must be local, ad, or sso"}),
                400,
            )

        # Map user_type string to enum
        user_type_map = {
            "local": UserType.LOCAL,
            "ad": UserType.ACTIVE_DIRECTORY,
            "sso": UserType.SSO,
        }
        user_type = user_type_map[user_type_str]

        # For local users, password is required
        if user_type == UserType.LOCAL and not password:
            return jsonify({"message": "Password is required for local users"}), 400

        # For AD/SSO users, password should not be provided
        if user_type != UserType.LOCAL and password:
            return (
                jsonify(
                    {
                        "message": f"{user_type_str.upper()} users should not have passwords in local database"
                    }
                ),
                400,
            )

        # Create new user
        new_user = User(
            username=username,
            email=email,
            fullname=fullname,
            role=role,
            user_type=user_type,
            is_ad_user=(user_type == UserType.ACTIVE_DIRECTORY),
        )

        # Set password for local users
        if user_type == UserType.LOCAL:
            new_user.set_password(password)

        # Save to database
        db.session.add(new_user)
        db.session.commit()

        logger.info(f"User {username} created by admin {current_profile.username}")

        # Return created user
        return (
            jsonify(
                {
                    "message": "User created successfully",
                    "user": {
                        "id": new_user.id,
                        "username": new_user.username,
                        "email": new_user.email,
                        "fullname": new_user.fullname,
                        "role": new_user.role,
                        "user_type": (
                            new_user.user_type.value
                            if isinstance(new_user.user_type, UserType)
                            else new_user.user_type
                        ),
                        "is_ad_user": new_user.is_ad_user,
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Create user error: {str(e)}", exc_info=True)
        return jsonify({"message": "Internal server error"}), 500


# Helper functions


def _is_account_locked(username):
    """Check if account is locked due to failed login attempts"""
    max_attempts = current_app.config["MAX_FAILED_LOGIN_ATTEMPTS"]
    lockout_minutes = current_app.config["ACCOUNT_LOCKOUT_MINUTES"]

    since_time = datetime.utcnow() - timedelta(minutes=lockout_minutes)

    failed_count = LoginAttempt.query.filter(
        LoginAttempt.username == username,
        LoginAttempt.success == False,
        LoginAttempt.attempt_time >= since_time,
    ).count()

    return failed_count >= max_attempts


def _log_login_attempt(username, success, reason=""):
    """Log login attempt"""
    attempt = LoginAttempt(
        username=username,
        ip_address=request.remote_addr,
        success=success,
        failure_reason=reason if not success else None,
    )
    db.session.add(attempt)
    db.session.commit()


def _increment_failed_attempts(username):
    """Track failed login attempts"""
    # Already logged in _log_login_attempt
    pass


def _clear_failed_attempts(username):
    """Clear failed login attempts after successful login"""
    # Keep for audit, but they'll age out based on time window
    pass


def _get_or_create_ad_user(user_info):
    """Get existing AD user or create new one"""
    user = User.query.filter_by(username=user_info["username"]).first()

    if not user:
        # Create new user from AD info
        user = User(
            username=user_info["username"],
            email=user_info["email"],
            fullname=user_info["fullname"],
            role="USER",  # Default role, can be updated by admin
            user_type=UserType.ACTIVE_DIRECTORY,
            is_ad_user=True,  # Backward compatibility
        )
        db.session.add(user)
        db.session.commit()
        logger.info(f"Created new AD user: {user.username}")
    else:
        # Update user info from AD
        user.email = user_info["email"]
        user.fullname = user_info["fullname"]
        user.user_type = UserType.ACTIVE_DIRECTORY
        user.is_ad_user = True  # Backward compatibility
        db.session.commit()

    return user
