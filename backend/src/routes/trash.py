from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Department, Asset, UserRole
from datetime import datetime
from audit_logger import audit_logger

trash_bp = Blueprint("trash", __name__)


@trash_bp.route("/users", methods=["GET"])
@jwt_required()
def get_deleted_users():
    """Get all soft-deleted users (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    deleted_users = User.query.filter(User.deleted_at.isnot(None)).all()

    return jsonify({
        "items": [
            {
                **user.to_dict(),
                "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None
            }
            for user in deleted_users
        ]
    }), 200


@trash_bp.route("/departments", methods=["GET"])
@jwt_required()
def get_deleted_departments():
    """Get all soft-deleted departments (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    deleted_departments = Department.query.filter(Department.deleted_at.isnot(None)).all()

    return jsonify({
        "items": [
            {
                **dept.to_dict(),
                "deleted_at": dept.deleted_at.isoformat() if dept.deleted_at else None
            }
            for dept in deleted_departments
        ]
    }), 200


@trash_bp.route("/assets", methods=["GET"])
@jwt_required()
def get_deleted_assets():
    """Get all soft-deleted assets (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    deleted_assets = Asset.query.filter(Asset.deleted_at.isnot(None)).all()

    return jsonify({
        "items": [
            {
                **asset.to_dict(),
                "deleted_at": asset.deleted_at.isoformat() if asset.deleted_at else None
            }
            for asset in deleted_assets
        ]
    }), 200


@trash_bp.route("/users/<int:id>/restore", methods=["POST"])
@jwt_required()
def restore_user(id):
    """Restore a soft-deleted user (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    user = User.query.get_or_404(id)

    if user.deleted_at is None:
        return jsonify({"message": "User is not deleted"}), 400

    user.deleted_at = None
    db.session.commit()

    # Log the activity
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action="restore_user",
        entity_type="user",
        entity_id=user.id,
        details=f"Restored user {user.username} from trash",
        ip_address=request.remote_addr,
    )

    return jsonify({"message": f"User {user.username} restored successfully", "user": user.to_dict()}), 200


@trash_bp.route("/departments/<int:id>/restore", methods=["POST"])
@jwt_required()
def restore_department(id):
    """Restore a soft-deleted department (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    department = Department.query.get_or_404(id)

    if department.deleted_at is None:
        return jsonify({"message": "Department is not deleted"}), 400

    department.deleted_at = None
    db.session.commit()

    # Log the activity
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action="restore_department",
        entity_type="department",
        entity_id=department.id,
        details=f"Restored department {department.name} from trash",
        ip_address=request.remote_addr,
    )

    return jsonify({"message": f"Department {department.name} restored successfully", "department": department.to_dict()}), 200


@trash_bp.route("/assets/<int:id>/restore", methods=["POST"])
@jwt_required()
def restore_asset(id):
    """Restore a soft-deleted asset (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    asset = Asset.query.get_or_404(id)

    if asset.deleted_at is None:
        return jsonify({"message": "Asset is not deleted"}), 400

    asset.deleted_at = None
    db.session.commit()

    # Log the activity
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action="restore_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Restored asset {asset.code} from trash",
        ip_address=request.remote_addr,
    )

    return jsonify({"message": f"Asset {asset.code} restored successfully", "asset": asset.to_dict()}), 200


@trash_bp.route("/users/<int:id>/permanent-delete", methods=["DELETE"])
@jwt_required()
def permanent_delete_user(id):
    """Permanently delete a user (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    user = User.query.get_or_404(id)

    if user.deleted_at is None:
        return jsonify({"message": "User must be soft-deleted first"}), 400

    username = user.username
    db.session.delete(user)
    db.session.commit()

    # Log the activity
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action="permanent_delete_user",
        entity_type="user",
        entity_id=id,
        details=f"Permanently deleted user {username}",
        ip_address=request.remote_addr,
    )

    return jsonify({"message": f"User {username} permanently deleted"}), 200


@trash_bp.route("/departments/<int:id>/permanent-delete", methods=["DELETE"])
@jwt_required()
def permanent_delete_department(id):
    """Permanently delete a department (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    department = Department.query.get_or_404(id)

    if department.deleted_at is None:
        return jsonify({"message": "Department must be soft-deleted first"}), 400

    dept_name = department.name
    db.session.delete(department)
    db.session.commit()

    # Log the activity
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action="permanent_delete_department",
        entity_type="department",
        entity_id=id,
        details=f"Permanently deleted department {dept_name}",
        ip_address=request.remote_addr,
    )

    return jsonify({"message": f"Department {dept_name} permanently deleted"}), 200


@trash_bp.route("/assets/<int:id>/permanent-delete", methods=["DELETE"])
@jwt_required()
def permanent_delete_asset(id):
    """Permanently delete an asset (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    asset = Asset.query.get_or_404(id)

    if asset.deleted_at is None:
        return jsonify({"message": "Asset must be soft-deleted first"}), 400

    asset_code = asset.code
    db.session.delete(asset)
    db.session.commit()

    # Log the activity
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action="permanent_delete_asset",
        entity_type="asset",
        entity_id=id,
        details=f"Permanently deleted asset {asset_code}",
        ip_address=request.remote_addr,
    )

    return jsonify({"message": f"Asset {asset_code} permanently deleted"}), 200
