from flask import Blueprint, current_app, request, jsonify, Response
from flask_jwt_extended import get_current_user, jwt_required, get_jwt_identity
from models import Profile, db, ProfileRole, UserActivity, Department, ActivityStatus
from audit_logger import audit_logger
from pagination import paginate_query, get_sort_params
from message_broker import message_broker
import csv
import io

users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["GET"])
@jwt_required()
def get_users():
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    # Get sort parameters
    sort_by, sort_order = get_sort_params()

    # Build base query - exclude soft-deleted users by default
    include_deleted = request.args.get("include_deleted", "false").lower() == "true"
    query = Profile.query_all(include_deleted=include_deleted)

    # Apply filters
    search = request.args.get("search")
    role = request.args.get("role")
    department_id = request.args.get("department_id")

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                Profile.username.ilike(search_filter),
                Profile.email.ilike(search_filter),
                Profile.fullname.ilike(search_filter),
            )
        )

    if role:
        try:
            role_enum = ProfileRole[role.upper()]
            query = query.filter(Profile.role == role_enum)
        except KeyError:
            pass  # Invalid role, ignore

    if department_id:
        query = query.join(Profile.departments).filter(
            Department.id == int(department_id)
        )

    # Apply sorting
    valid_sort_fields = {
        "username": Profile.username,
        "email": Profile.email,
        "fullname": Profile.fullname,
        "role": Profile.role,
        "created_at": Profile.created_at,
    }

    if sort_by in valid_sort_fields:
        sort_column = valid_sort_fields[sort_by]
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Default sorting
        query = query.order_by(Profile.created_at.desc())

    pagination_result = paginate_query(query, user=current_profile)

    # Convert users to dict with error handling
    items = []
    for user in pagination_result["items"]:
        try:
            items.append(user.to_dict())
        except Exception as e:
            current_app.logger.error(f"Error converting user {user.id} to dict: {e}")

    response = {
        "items": items,
        "pagination": {
            "page": pagination_result["page"],
            "per_page": pagination_result["per_page"],
            "total": pagination_result["total"],
            "total_pages": pagination_result["total_pages"],
            "has_next": pagination_result["has_next"],
            "has_prev": pagination_result["has_prev"],
            "next_page": pagination_result["next_page"],
            "prev_page": pagination_result["prev_page"],
        },
    }
    return jsonify(response)


@users_bp.route("", methods=["POST"])
@jwt_required()
def create_user():
    """Create a new user (admin only) - integrates with auth service"""
    from flask import current_app
    from auth_client import auth_client

    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    # Validate required fields
    if not data.get("username"):
        return jsonify({"message": "Username is required"}), 400
    if not data.get("password"):
        return jsonify({"message": "Password is required"}), 400
    if not data.get("email"):
        return jsonify({"message": "Email is required"}), 400

    # Check if username already exists in backend database
    if Profile.query.filter_by(username=data["username"]).first():
        return jsonify({"message": "Username already exists"}), 400

    # Check if email already exists in backend database
    if Profile.query.filter_by(email=data["email"]).first():
        return jsonify({"message": "Email already exists"}), 400

    # Parse role
    role = ProfileRole.USER
    if data.get("role"):
        try:
            role = ProfileRole[data["role"].upper()]
        except KeyError:
            return jsonify({"message": "Invalid role"}), 400

    # Get user_type (default: local)
    user_type = data.get("user_type", "local")
    if user_type not in ["local", "ad", "sso"]:
        return jsonify({"message": "Invalid user_type. Must be local, ad, or sso"}), 400

    # Step 1: Create user in auth service (stores credentials)
    # Get current user's access token from request header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"message": "Authorization token required"}), 401

    access_token = auth_header.split(" ")[1]

    # Prepare auth service user data
    auth_user_data = {
        "username": data["username"],
        "email": data["email"],
        "fullname": data.get("fullname", data.get("full_name", "")),
        "role": role.value,
        "user_type": user_type,
    }

    # Only include password for local users
    if user_type == "local":
        auth_user_data["password"] = data["password"]

    # Call auth service to create user
    success, _, error_msg = auth_client.create_user(access_token, auth_user_data)

    if not success:
        current_app.logger.error(f"Failed to create user in auth service: {error_msg}")
        return (
            jsonify({"message": f"Failed to create user credentials: {error_msg}"}),
            400,
        )

    # Step 2: Create user profile in backend database (stores user information)
    try:
        profile = Profile(
            username=data["username"],
            email=data["email"],
            fullname=data.get("fullname", ""),
            role=role,
            user_type=user_type,
            is_ad_user=(user_type == "ad"),
        )
        # Note: Password is NOT stored in backend, only in auth service

        db.session.add(profile)
        db.session.flush()  # Get user ID before handling departments

        # Handle department assignments
        if data.get("department_ids"):
            from models import ProfileDepartment

            for dept_id in data["department_ids"]:
                dept = Department.query.get(dept_id)
                if dept:
                    # Check if this user should be a manager
                    is_manager = False
                    if (
                        data.get("manager_dept_ids")
                        and dept_id in data["manager_dept_ids"]
                    ):
                        is_manager = True

                    user_dept = ProfileDepartment(
                        user_id=profile.id, department_id=dept_id, is_manager=is_manager
                    )
                    db.session.add(user_dept)

        # Log activity
        activity = UserActivity(
            user_id=current_profile.id,
            username=current_profile.username,
            action="create",
            entity_type="user",
            entity_id=profile.id,
            details=f"Created user {profile.username} (auth_type: {user_type})",
            status=ActivityStatus.SUCCESS,
        )
        db.session.add(activity)

        db.session.commit()

        # Audit log
        audit_logger.log(
            user_id=current_profile.id,
            username=current_profile.username,
            action="create",
            entity_type="user",
            entity_id=profile.id,
            new_values={
                "username": profile.username,
                "email": profile.email,
                "fullname": profile.fullname,
                "role": profile.role.value,
                "user_type": profile.user_type,
            },
            details=f"Created user {profile.username} (auth_type: {user_type})",
            ip_address=request.remote_addr,
        )

        current_app.logger.info(
            f"User {profile.username} created successfully in both auth and backend databases"
        )
        return jsonify(profile.to_dict()), 201

    except Exception as e:
        # Rollback backend database changes
        db.session.rollback()
        current_app.logger.error(f"Error creating user in backend database: {str(e)}")

        # TODO: Consider implementing rollback for auth service
        # For now, the user exists in auth service but not in backend
        # This could be handled by a cleanup job or manual intervention

        return (
            jsonify(
                {
                    "message": f"User credentials created but profile creation failed: {str(e)}",
                    "note": "Please contact administrator to complete user setup",
                }
            ),
            500,
        )


@users_bp.route("/<int:id>", methods=["GET"])
@jwt_required()
def get_user(id):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN and current_profile.id != id:
        return jsonify({"message": "Unauthorized"}), 403

    user = Profile.query.get_or_404(id)
    return jsonify(user.to_dict())


@users_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_user(id: int):
    """Update user information - syncs with auth service"""
    from flask import current_app
    from auth_client import auth_client

    try:
        current_profile_username = get_jwt_identity()
        current_profile = Profile.query.filter_by(
            username=current_profile_username
        ).first()

        if current_profile.role != ProfileRole.ADMIN:
            return jsonify({"message": "Unauthorized"}), 403

        profile = Profile.query.get_or_404(id)
        data = request.json

        # Capture old values for audit
        old_values = profile.to_dict()

        # Get access token for auth service
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"message": "Authorization token required"}), 401

        access_token = auth_header.split(" ")[1]

        # Prepare data for auth service update
        auth_update_data = {}

        # Fields to sync with auth service
        if "username" in data and data.get("username") != profile.username:
            auth_update_data["username"] = data["username"]
            profile.username = data["username"]

        if "fullname" in data:
            auth_update_data["fullname"] = data["fullname"]
            profile.fullname = data["fullname"]

        if "email" in data:
            auth_update_data["email"] = data["email"]
            profile.email = data["email"]

        if "role" in data:
            role = ProfileRole[data["role"].upper()]
            auth_update_data["role"] = role.value
            profile.role = role

        # Step 1: Update user in auth service if there are changes
        # IMPORTANT: Use username as the key, not ID, because backend Profile.id != auth User.id
        if auth_update_data:
            # Get the original username before update (in case username is being changed)
            original_username = profile.username if "username" not in data else Profile.query.get(id).username

            success, _, error_msg = auth_client.update_user_by_username(
                access_token, original_username, auth_update_data
            )

            if not success:
                current_app.logger.error(
                    f"Failed to update user in auth service: {error_msg}"
                )
                return (
                    jsonify(
                        {
                            "message": f"Failed to sync user credentials: {error_msg}",
                            "note": "User profile not updated in backend to maintain consistency",
                        }
                    ),
                    400,
                )

            current_app.logger.info(
                f"User {original_username} updated successfully in auth service"
            )

        # Step 2: Update departments (many-to-many relationship) in backend only
        if "department_ids" in data:
            # Validate non-admins must belong to at least one department
            if profile.role != ProfileRole.ADMIN and (
                not data["department_ids"] or len(data["department_ids"]) == 0
            ):
                return (
                    jsonify(
                        {
                            "message": "Non-admin users must be assigned to at least one department"
                        }
                    ),
                    400,
                )

            # Clear existing associations
            from models import ProfileDepartment

            ProfileDepartment.query.filter_by(profile_id=profile.id).delete()

            # Get manager department IDs from request
            manager_dept_ids = data.get("manager_department_ids", [])

            # Add new department associations with is_manager flag
            for dept_id in data["department_ids"]:
                dept = Department.query.get(dept_id)
                if dept:
                    is_manager = dept_id in manager_dept_ids
                    assoc = ProfileDepartment(
                        profile_id=profile.id,
                        department_id=dept_id,
                        is_manager=is_manager,
                    )
                    db.session.add(assoc)

        # Log activity
        activity = UserActivity(
            user_id=current_profile.id,
            username=current_profile.username,
            action="update_user",
            entity_type="user",
            entity_id=profile.id,
            details=f"Updated user {profile.username}",
            status=ActivityStatus.SUCCESS,
        )
        db.session.add(activity)
        db.session.commit()

        # Audit log
        audit_logger.log(
            user_id=current_profile.id,
            username=current_profile.username,
            action="update",
            entity_type="user",
            entity_id=profile.id,
            old_values=old_values,
            new_values=profile.to_dict(),
            details=f"Updated user {profile.username} (synced with auth service)",
            ip_address=request.remote_addr,
        )

        current_app.logger.info(
            f"User {profile.username} updated successfully in both auth and backend databases"
        )
        return jsonify(profile.to_dict())

    except Exception as e:
        db.session.rollback()
        import traceback

        traceback.print_exc()
        current_app.logger.error(f"Error updating user: {str(e)}")
        return jsonify({"message": f"Error updating user: {str(e)}"}), 500


@users_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_user(id):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    if current_profile.id == id:
        return jsonify({"message": "Cannot delete yourself"}), 400

    profile = Profile.query.get_or_404(id)
    username = profile.username
    old_values = profile.to_dict()

    # Soft delete - set deleted_at timestamp
    from datetime import datetime

    profile.deleted_at = datetime.utcnow()

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="delete_user",
        entity_type="user",
        entity_id=id,
        details=f"Deleted user {username} (soft delete)",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="delete",
        entity_type="user",
        entity_id=id,
        old_values=old_values,
        new_values={"deleted_at": profile.deleted_at.isoformat()},
        details=f"Deleted user {username} (soft delete)",
        ip_address=request.remote_addr,
    )

    return "", 204


@users_bp.route("/<int:id>/force-logout", methods=["POST"])
@jwt_required()
def force_logout(id):
    """Force a user to logout by changing their password and requiring password change"""
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    # Prevent admin from logging out themselves
    if id == current_profile_id:
        return jsonify({"message": "Cannot force logout yourself"}), 400

    user = Profile.query.get_or_404(id)

    # Generate a random temporary password
    import secrets
    import string

    temp_password = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
    )

    # Set new password and force password change
    user.set_password(temp_password)
    user.must_change_password = True

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="force_logout",
        entity_type="user",
        entity_id=id,
        details=f"Forced logout for user {user.username}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)

    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="force_logout",
        entity_type="user",
        entity_id=id,
        details=f"Forced logout for user {user.username}",
        ip_address=request.remote_addr,
    )

    return (
        jsonify(
            {
                "message": f"User {user.username} has been logged out and must change password on next login"
            }
        ),
        200,
    )


@users_bp.route("/<int:id>/reset-password", methods=["POST"])
@jwt_required()
def reset_password(id):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    user = Profile.query.get_or_404(id)
    data = request.json

    if not data.get("password"):
        return jsonify({"message": "Password is required"}), 400

    user.set_password(data["password"])

    # Optionally force user to change password on next login
    if data.get("must_change_password", True):
        user.must_change_password = True

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="reset_password",
        entity_type="user",
        entity_id=user.id,
        details=f"Reset password for user {user.username}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="reset_password",
        entity_type="user",
        entity_id=user.id,
        old_values={"password": "[REDACTED]"},
        new_values={
            "password": "[REDACTED]",
            "must_change_password": user.must_change_password,
        },
        details=f"Reset password for user {user.username}",
        ip_address=request.remote_addr,
    )

    return (
        jsonify({"message": "Password reset successfully", "user": user.to_dict()}),
        200,
    )


@users_bp.route("/sample-csv", methods=["GET"])
@jwt_required()
def download_sample_csv():
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    # Create sample CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        ["username", "fullname", "email", "password", "role", "department_ids"]
    )

    # Write sample rows
    writer.writerow(
        ["john.doe", "John Doe", "john.doe@example.com", "password123", "viewer", "1,2"]
    )
    writer.writerow(
        [
            "jane.smith",
            "Jane Smith",
            "jane.smith@example.com",
            "password456",
            "manager",
            "1",
        ]
    )

    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_sample.csv"},
    )


@users_bp.route("/upload-csv", methods=["POST"])
@jwt_required()
def upload_csv():
    """Upload CSV to create multiple users - integrates with auth service"""
    from flask import current_app
    from auth_client import auth_client

    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    if "file" not in request.files:
        return jsonify({"message": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"message": "No file selected"}), 400

    if not file.filename.endswith(".csv"):
        return jsonify({"message": "File must be a CSV"}), 400

    # Get access token for auth service calls
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"message": "Authorization token required"}), 401

    access_token = auth_header.split(" ")[1]

    try:
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        created_users = []
        errors = []

        for row_num, row in enumerate(
            csv_reader, start=2
        ):  # start=2 because row 1 is header
            try:
                # Validate required fields
                if (
                    not row.get("username")
                    or not row.get("fullname")
                    or not row.get("email")
                    or not row.get("password")
                ):
                    errors.append(
                        f"Row {row_num}: Missing required fields (username, fullname, email, password)"
                    )
                    continue

                # Check if user already exists
                if Profile.query.filter_by(username=row["username"]).first():
                    errors.append(
                        f"Row {row_num}: Username '{row['username']}' already exists"
                    )
                    continue

                if Profile.query.filter_by(email=row["email"]).first():
                    errors.append(
                        f"Row {row_num}: Email '{row['email']}' already exists"
                    )
                    continue

                # Parse role
                role_str = row.get("role", "user").lower()
                if role_str == "admin":
                    role = ProfileRole.ADMIN
                else:
                    role = ProfileRole.USER

                # Get user_type (default: local)
                user_type = row.get("user_type", "local").lower()
                if user_type not in ["local", "ad", "sso"]:
                    user_type = "local"

                # Step 1: Create user in auth service
                auth_user_data = {
                    "username": row["username"],
                    "email": row["email"],
                    "fullname": row["fullname"],
                    "role": role.value,
                    "user_type": user_type,
                }

                # Only include password for local users
                if user_type == "local":
                    auth_user_data["password"] = row["password"]

                success, _, error_msg = auth_client.create_user(
                    access_token, auth_user_data
                )

                if not success:
                    errors.append(f"Row {row_num}: Auth service error - {error_msg}")
                    continue

                # Step 2: Create user in backend database
                user = User(
                    username=row["username"],
                    fullname=row["fullname"],
                    email=row["email"],
                    role=role,
                    user_type=user_type,
                    is_ad_user=(user_type == "ad"),
                )
                # Note: Password NOT stored in backend, only in auth service

                db.session.add(user)
                db.session.flush()  # Get user.id

                # Parse and assign departments
                if row.get("department_ids"):
                    dept_ids = [
                        int(did.strip())
                        for did in row["department_ids"].split(",")
                        if did.strip()
                    ]

                    # Validate non-admin users must have at least one department
                    if role != ProfileRole.ADMIN and len(dept_ids) == 0:
                        db.session.rollback()
                        errors.append(
                            f"Row {row_num}: Non-admin users must be assigned to at least one department"
                        )
                        continue

                    departments = Department.query.filter(
                        Department.id.in_(dept_ids)
                    ).all()
                    if len(departments) != len(dept_ids):
                        db.session.rollback()
                        errors.append(f"Row {row_num}: Some department IDs not found")
                        continue

                    user.departments = departments

                # Log activity
                activity = UserActivity(
                    user_id=current_profile.id,
                    username=current_profile.username,
                    action="create_user_csv",
                    entity_type="user",
                    entity_id=user.id,
                    details=f"Created user {user.username} via CSV upload",
                    status=ActivityStatus.SUCCESS,
                )
                db.session.add(activity)

                # Store user info for email queueing after commit
                created_users.append(
                    {
                        "username": user.username,
                        "email": user.email,
                        "fullname": user.fullname,
                        "password": row["password"],
                    }
                )

            except Exception as e:
                db.session.rollback()
                errors.append(f"Row {row_num}: {str(e)}")
                continue

        # Commit all successful users
        if created_users:
            db.session.commit()

            # Queue welcome emails asynchronously after successful commit
            try:
                from email_queue import email_queue

                for user_info in created_users:
                    email_queue.enqueue_welcome_email(
                        user_email=user_info["email"],
                        username=user_info["username"],
                        password=user_info["password"],
                        fullname=user_info["fullname"],
                    )
            except Exception as e:
                # Log error but don't fail the CSV upload
                import logging

                logging.error(f"Error queueing welcome emails for CSV users: {str(e)}")

        return jsonify(
            {
                "message": f"CSV processed successfully",
                "created": len(created_users),
                "created_users": [u["username"] for u in created_users],
                "errors": errors,
            }
        ), (
            200 if not errors else 207
        )  # 207 = Multi-Status

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error processing CSV: {str(e)}"}), 400
