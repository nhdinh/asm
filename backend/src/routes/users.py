from flask import Blueprint, current_app, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, UserRole, UserActivity, Department, ActivityStatus
from audit_logger import audit_logger
from pagination import paginate_query, create_pagination_response, get_sort_params
import csv
import io

users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["GET"])
@jwt_required()
def get_users():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    # Get sort parameters
    sort_by, sort_order = get_sort_params()

    # Build base query - exclude soft-deleted users by default
    include_deleted = request.args.get("include_deleted", "false").lower() == "true"
    query = User.query_all(include_deleted=include_deleted)

    # Apply filters
    search = request.args.get("search")
    role = request.args.get("role")
    department_id = request.args.get("department_id")

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                User.username.ilike(search_filter),
                User.email.ilike(search_filter),
                User.fullname.ilike(search_filter),
            )
        )

    if role:
        try:
            role_enum = UserRole[role.upper()]
            query = query.filter(User.role == role_enum)
        except KeyError:
            pass  # Invalid role, ignore

    if department_id:
        query = query.join(User.departments).filter(Department.id == int(department_id))

    # Apply sorting
    valid_sort_fields = {
        "username": User.username,
        "email": User.email,
        "fullname": User.fullname,
        "role": User.role,
        "created_at": User.created_at,
    }

    if sort_by in valid_sort_fields:
        sort_column = valid_sort_fields[sort_by]
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Default sorting
        query = query.order_by(User.created_at.desc())

    pagination_result = paginate_query(query, user=current_user)

    # Convert users to dict with error handling
    items = []
    for user in pagination_result['items']:
        try:
            items.append(user.to_dict())
        except Exception as e:
            current_app.logger.error(f"Error converting user {user.id} to dict: {e}")

    response = {
        "items": items,
        "pagination": {
            "page": pagination_result['page'],
            "per_page": pagination_result['per_page'],
            "total": pagination_result['total'],
            "total_pages": pagination_result['total_pages'],
            "has_next": pagination_result['has_next'],
            "has_prev": pagination_result['has_prev'],
            "next_page": pagination_result['next_page'],
            "prev_page": pagination_result['prev_page'],
        }
    }
    return jsonify(response)


@users_bp.route("", methods=["POST"])
@jwt_required()
def create_user():
    """Create a new user (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    # Validate required fields
    if not data.get("username"):
        return jsonify({"message": "Username is required"}), 400
    if not data.get("password"):
        return jsonify({"message": "Password is required"}), 400
    if not data.get("email"):
        return jsonify({"message": "Email is required"}), 400

    # Check if username already exists
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"message": "Username already exists"}), 400

    # Check if email already exists
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"message": "Email already exists"}), 400

    # Parse role
    role = UserRole.USER
    if data.get("role"):
        try:
            role = UserRole[data["role"].upper()]
        except KeyError:
            return jsonify({"message": "Invalid role"}), 400

    # Create user
    user = User(
        username=data["username"],
        email=data["email"],
        fullname=data.get("full_name", ""),
        role=role
    )
    user.set_password(data["password"])

    db.session.add(user)
    db.session.flush()  # Get user ID before handling departments

    # Handle department assignments
    if data.get("department_ids"):
        from models import UserDepartment
        for dept_id in data["department_ids"]:
            dept = Department.query.get(dept_id)
            if dept:
                # Check if this user should be a manager
                is_manager = False
                if data.get("manager_dept_ids") and dept_id in data["manager_dept_ids"]:
                    is_manager = True

                user_dept = UserDepartment(
                    user_id=user.id,
                    department_id=dept_id,
                    is_manager=is_manager
                )
                db.session.add(user_dept)

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
        action="create",
        entity_type="user",
        entity_id=user.id,
        details=f"Created user {user.username}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)

    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user_id,
        username=current_user.username,
        action="create",
        entity_type="user",
        entity_id=user.id,
        new_values={
            "username": user.username,
            "email": user.email,
            "fullname": user.fullname,
            "role": user.role.value,
        },
        details=f"Created user {user.username}",
        ip_address=request.remote_addr,
    )

    return jsonify(user.to_dict()), 201


@users_bp.route("/<int:id>", methods=["GET"])
@jwt_required()
def get_user(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN and current_user_id != id:
        return jsonify({"message": "Unauthorized"}), 403

    user = User.query.get_or_404(id)
    return jsonify(user.to_dict())


@users_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_user(id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)

        if current_user.role != UserRole.ADMIN:
            return jsonify({"message": "Unauthorized"}), 403

        user = User.query.get_or_404(id)
        data = request.json

        # Capture old values for audit
        old_values = user.to_dict()

        # Only admin can change username
        if "username" in data and data.get("username") != user.username:
            user.username = data["username"]

        user.fullname = data.get("fullname", user.fullname)
        user.email = data.get("email", user.email)
        if data.get("role"):
            user.role = UserRole[data["role"].upper()]

        # Update departments (many-to-many relationship)
        if "department_ids" in data:
            # Validate non-admins must belong to at least one department
            if user.role != UserRole.ADMIN and (
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
            from models import UserDepartment

            UserDepartment.query.filter_by(user_id=user.id).delete()

            # Get manager department IDs from request (format: {"dept_id": is_manager})
            manager_dept_ids = data.get("manager_department_ids", [])

            # Add new department associations with is_manager flag
            for dept_id in data["department_ids"]:
                dept = Department.query.get(dept_id)
                if dept:
                    is_manager = dept_id in manager_dept_ids
                    assoc = UserDepartment(
                        user_id=user.id, department_id=dept_id, is_manager=is_manager
                    )
                    db.session.add(assoc)

        # Log activity
        activity = UserActivity(
            user_id=current_user_id,
            username=current_user.username,
            action="update_user",
            entity_type="user",
            entity_id=user.id,
            details=f"Updated user {user.username}",
            status=ActivityStatus.SUCCESS,
        )
        db.session.add(activity)
        db.session.commit()

        # Audit log
        audit_logger.log(
            user_id=current_user_id,
            username=current_user.username,
            action="update",
            entity_type="user",
            entity_id=user.id,
            old_values=old_values,
            new_values=user.to_dict(),
            details=f"Updated user {user.username}",
            ip_address=request.remote_addr,
        )

        return jsonify(user.to_dict())
    except Exception as e:
        db.session.rollback()
        import traceback

        traceback.print_exc()
        return jsonify({"message": f"Error updating user: {str(e)}"}), 500


@users_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_user(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    if current_user_id == id:
        return jsonify({"message": "Cannot delete yourself"}), 400

    user = User.query.get_or_404(id)
    username = user.username
    old_values = user.to_dict()

    # Soft delete - set deleted_at timestamp
    from datetime import datetime

    user.deleted_at = datetime.utcnow()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
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
        user_id=current_user_id,
        username=current_user.username,
        action="delete",
        entity_type="user",
        entity_id=id,
        old_values=old_values,
        new_values={"deleted_at": user.deleted_at.isoformat()},
        details=f"Deleted user {username} (soft delete)",
        ip_address=request.remote_addr,
    )

    return "", 204


@users_bp.route("/<int:id>/force-logout", methods=["POST"])
@jwt_required()
def force_logout(id):
    """Force a user to logout by changing their password and requiring password change"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    # Prevent admin from logging out themselves
    if id == current_user_id:
        return jsonify({"message": "Cannot force logout yourself"}), 400

    user = User.query.get_or_404(id)

    # Generate a random temporary password
    import secrets
    import string
    temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

    # Set new password and force password change
    user.set_password(temp_password)
    user.must_change_password = True

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
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
        user_id=current_user_id,
        username=current_user.username,
        action="force_logout",
        entity_type="user",
        entity_id=id,
        details=f"Forced logout for user {user.username}",
        ip_address=request.remote_addr,
    )

    return jsonify({
        "message": f"User {user.username} has been logged out and must change password on next login"
    }), 200


@users_bp.route("/<int:id>/reset-password", methods=["POST"])
@jwt_required()
def reset_password(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    user = User.query.get_or_404(id)
    data = request.json

    if not data.get("password"):
        return jsonify({"message": "Password is required"}), 400

    user.set_password(data["password"])

    # Optionally force user to change password on next login
    if data.get("must_change_password", True):
        user.must_change_password = True

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
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
        user_id=current_user_id,
        username=current_user.username,
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
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
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
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    if "file" not in request.files:
        return jsonify({"message": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"message": "No file selected"}), 400

    if not file.filename.endswith(".csv"):
        return jsonify({"message": "File must be a CSV"}), 400

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
                if User.query.filter_by(username=row["username"]).first():
                    errors.append(
                        f"Row {row_num}: Username '{row['username']}' already exists"
                    )
                    continue

                if User.query.filter_by(email=row["email"]).first():
                    errors.append(
                        f"Row {row_num}: Email '{row['email']}' already exists"
                    )
                    continue

                # Parse role
                role_str = row.get("role", "user").lower()
                if role_str == "admin":
                    role = UserRole.ADMIN
                else:
                    role = UserRole.USER

                # Create user
                user = User(
                    username=row["username"],
                    fullname=row["fullname"],
                    email=row["email"],
                    role=role,
                    must_change_password=True,  # Force password change on first login
                )
                user.set_password(row["password"])

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
                    if role != UserRole.ADMIN and len(dept_ids) == 0:
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
                    user_id=current_user_id,
                    username=current_user.username,
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
