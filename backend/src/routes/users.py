from flask import Blueprint, request, jsonify, Response
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

    # Build base query
    query = User.query

    # Apply filters
    search = request.args.get('search')
    role = request.args.get('role')
    department_id = request.args.get('department_id')

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                User.username.ilike(search_filter),
                User.email.ilike(search_filter),
                User.fullname.ilike(search_filter)
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
        'username': User.username,
        'email': User.email,
        'fullname': User.fullname,
        'role': User.role,
        'created_at': User.created_at
    }

    if sort_by in valid_sort_fields:
        sort_column = valid_sort_fields[sort_by]
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Default sorting
        query = query.order_by(User.created_at.desc())

    pagination_result = paginate_query(query, user=current_user)

    return jsonify(create_pagination_response(pagination_result, lambda u: u.to_dict()))


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
            if user.role != UserRole.ADMIN and (not data["department_ids"] or len(data["department_ids"]) == 0):
                return jsonify({"message": "Non-admin users must be assigned to at least one department"}), 400

            user.departments = []
            for dept_id in data["department_ids"]:
                dept = Department.query.get(dept_id)
                if dept:
                    user.departments.append(dept)

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
            action='update',
            entity_type='user',
            entity_id=user.id,
            old_values=old_values,
            new_values=user.to_dict(),
            details=f"Updated user {user.username}",
            ip_address=request.remote_addr
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

    db.session.delete(user)

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
        action="delete_user",
        entity_type="user",
        entity_id=id,
        details=f"Deleted user {username}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user_id,
        username=current_user.username,
        action='delete',
        entity_type='user',
        entity_id=id,
        old_values=old_values,
        new_values={},
        details=f"Deleted user {username}",
        ip_address=request.remote_addr
    )

    return "", 204


@users_bp.route("/<int:id>/reset-password", methods=["POST"])
@jwt_required()
def reset_password(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    user = User.query.get_or_404(id)
    data = request.json

    user.set_password(data["password"])

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
        action='reset_password',
        entity_type='user',
        entity_id=user.id,
        old_values={'password': '[REDACTED]'},
        new_values={'password': '[REDACTED]'},
        details=f"Reset password for user {user.username}",
        ip_address=request.remote_addr
    )

    return jsonify({"message": "Password reset successfully"}), 200


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
    writer.writerow(['username', 'fullname', 'email', 'password', 'role', 'department_ids'])

    # Write sample rows
    writer.writerow(['john.doe', 'John Doe', 'john.doe@example.com', 'password123', 'viewer', '1,2'])
    writer.writerow(['jane.smith', 'Jane Smith', 'jane.smith@example.com', 'password456', 'manager', '1'])

    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=users_sample.csv'}
    )


@users_bp.route("/upload-csv", methods=["POST"])
@jwt_required()
def upload_csv():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    if 'file' not in request.files:
        return jsonify({"message": "No file provided"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"message": "No file selected"}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({"message": "File must be a CSV"}), 400

    try:
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        created_users = []
        errors = []

        for row_num, row in enumerate(csv_reader, start=2):  # start=2 because row 1 is header
            try:
                # Validate required fields
                if not row.get('username') or not row.get('fullname') or not row.get('email') or not row.get('password'):
                    errors.append(f"Row {row_num}: Missing required fields (username, fullname, email, password)")
                    continue

                # Check if user already exists
                if User.query.filter_by(username=row['username']).first():
                    errors.append(f"Row {row_num}: Username '{row['username']}' already exists")
                    continue

                if User.query.filter_by(email=row['email']).first():
                    errors.append(f"Row {row_num}: Email '{row['email']}' already exists")
                    continue

                # Parse role
                role_str = row.get('role', 'viewer').lower()
                if role_str == 'admin':
                    role = UserRole.ADMIN
                elif role_str == 'manager':
                    role = UserRole.MANAGER
                else:
                    role = UserRole.VIEWER

                # Create user
                user = User(
                    username=row['username'],
                    fullname=row['fullname'],
                    email=row['email'],
                    role=role,
                    must_change_password=True  # Force password change on first login
                )
                user.set_password(row['password'])

                db.session.add(user)
                db.session.flush()  # Get user.id

                # Parse and assign departments
                if row.get('department_ids'):
                    dept_ids = [int(did.strip()) for did in row['department_ids'].split(',') if did.strip()]

                    # Validate non-admin users must have at least one department
                    if role != UserRole.ADMIN and len(dept_ids) == 0:
                        db.session.rollback()
                        errors.append(f"Row {row_num}: Non-admin users must be assigned to at least one department")
                        continue

                    departments = Department.query.filter(Department.id.in_(dept_ids)).all()
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

                created_users.append(user.username)

            except Exception as e:
                db.session.rollback()
                errors.append(f"Row {row_num}: {str(e)}")
                continue

        # Commit all successful users
        if created_users:
            db.session.commit()

        return jsonify({
            "message": f"CSV processed successfully",
            "created": len(created_users),
            "created_users": created_users,
            "errors": errors
        }), 200 if not errors else 207  # 207 = Multi-Status

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error processing CSV: {str(e)}"}), 400
