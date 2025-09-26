from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, UserRole, UserActivity

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
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    user = User.query.get_or_404(id)
    data = request.json

    user.username = data.get("username", user.username)
    user.email = data.get("email", user.email)
    if data.get("role"):
        user.role = UserRole[data["role"].upper()]
    user.department_id = data.get("department_id", user.department_id)

    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="update_user",
        entity_type="user",
        entity_id=user.id,
        details=f"Updated user {user.username}",
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify(user.to_dict())


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
    db.session.delete(user)
    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="delete_user",
        entity_type="user",
        entity_id=id,
        details=f"Deleted user {user.username}",
    )
    db.session.add(activity)
    db.session.commit()

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
    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="reset_password",
        entity_type="user",
        entity_id=user.id,
        details=f"Reset password for user {user.username}",
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify({"message": "Password reset successfully"}), 200
