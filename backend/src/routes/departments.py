from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Department, User, UserRole, UserActivity, ActivityStatus
from audit_logger import audit_logger
from pagination import paginate_query, create_pagination_response, get_sort_params

dept_bp = Blueprint("departments", __name__)


@dept_bp.route("", methods=["GET"])
@jwt_required()
def get_departments():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    # Get sort parameters
    sort_by, sort_order = get_sort_params()

    # Build base query
    query = Department.query

    # Apply search filter
    search = request.args.get('search')
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                Department.name.ilike(search_filter),
                Department.description.ilike(search_filter),
                Department.code.ilike(search_filter)
            )
        )

    # Apply sorting
    valid_sort_fields = {
        'name': Department.name,
        'user_count': Department.user_count,
        'asset_count': Department.asset_count,
        'total_value': Department.total_value,
        'created_at': Department.created_at
    }

    if sort_by in valid_sort_fields:
        sort_column = valid_sort_fields[sort_by]
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Default sorting
        query = query.order_by(Department.name)

    pagination_result = paginate_query(query, user=current_user)

    return jsonify(create_pagination_response(pagination_result, lambda d: d.to_dict()))


@dept_bp.route("/<int:id>", methods=["GET"])
@jwt_required()
def get_department(id):
    dept = Department.query.get_or_404(id)
    return jsonify(dept.to_dict(include_details=True))


@dept_bp.route("", methods=["POST"])
@jwt_required()
def create_department():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    if Department.query.filter_by(name=data["name"]).first():
        return jsonify({"message": "Department already exists"}), 400

    dept = Department(
        name=data["name"],
        description=data.get("description"),
        user_count=0,
        asset_count=0,
        total_value=0,
    )

    db.session.add(dept)
    db.session.flush()  # Get dept.id before commit

    # Add managers (many-to-many relationship)
    if "manager_ids" in data:
        for manager_id in data["manager_ids"]:
            manager = User.query.get(manager_id)
            if manager and manager not in dept.managers:
                dept.managers.append(manager)

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
        action="create_department",
        entity_type="department",
        entity_id=dept.id,
        details=f"Created department {dept.name}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user_id,
        username=current_user.username,
        action='create',
        entity_type='department',
        entity_id=dept.id,
        new_values=dept.to_dict(),
        details=f"Created department {dept.name}",
        ip_address=request.remote_addr
    )

    return jsonify(dept.to_dict()), 201


@dept_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_department(id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)

        if current_user.role != UserRole.ADMIN:
            return jsonify({"message": "Unauthorized"}), 403

        dept = Department.query.get_or_404(id)
        data = request.json

        # Capture old values for audit
        old_values = dept.to_dict()

        dept.name = data.get("name", dept.name)
        dept.description = data.get("description", dept.description)

        # Update managers (many-to-many relationship)
        if "manager_ids" in data:
            # Clear existing managers
            dept.managers = []

            # Add new managers
            for manager_id in data["manager_ids"]:
                manager = User.query.get(manager_id)
                if manager and manager not in dept.managers:
                    dept.managers.append(manager)

        # Update users (many-to-many relationship)
        if "user_ids" in data:
            # Clear existing relationships by removing department from all current users
            current_users = list(dept.users.all())
            for user in current_users:
                if dept in user.departments:
                    user.departments.remove(dept)

            # Add new relationships
            for user_id in data["user_ids"]:
                user = User.query.get(user_id)
                if user and dept not in user.departments:
                    user.departments.append(dept)

        # Log activity
        activity = UserActivity(
            user_id=current_user_id,
            username=current_user.username,
            action="update_department",
            entity_type="department",
            entity_id=dept.id,
            details=f"Updated department {dept.name}",
            status=ActivityStatus.SUCCESS,
        )
        db.session.add(activity)
        db.session.commit()

        # Audit log
        audit_logger.log(
            user_id=current_user_id,
            username=current_user.username,
            action='update',
            entity_type='department',
            entity_id=dept.id,
            old_values=old_values,
            new_values=dept.to_dict(),
            details=f"Updated department {dept.name}",
            ip_address=request.remote_addr
        )

        return jsonify(dept.to_dict())
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"Error updating department: {str(e)}"}), 500


@dept_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_department(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    dept = Department.query.get_or_404(id)

    # Check if department has assets
    if dept.assets.count() > 0:
        return jsonify({"message": "Không thể xóa phòng ban có tài sản"}), 400

    # Check if department has users
    if dept.users.count() > 0:
        return jsonify({"message": "Không thể xóa phòng ban có người"}), 400

    dept_name = dept.name
    old_values = dept.to_dict()

    db.session.delete(dept)

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
        action="delete_department",
        entity_type="department",
        entity_id=id,
        details=f"Deleted department {dept_name}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user_id,
        username=current_user.username,
        action='delete',
        entity_type='department',
        entity_id=id,
        old_values=old_values,
        new_values={},
        details=f"Deleted department {dept_name}",
        ip_address=request.remote_addr
    )

    return "", 204
