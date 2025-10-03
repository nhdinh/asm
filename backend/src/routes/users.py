from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, UserRole, UserActivity, Department, ActivityStatus
from audit_logger import audit_logger

users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["GET"])
@jwt_required()
def get_users():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    users = User.query.all()
    return jsonify([user.to_dict() for user in users])


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
