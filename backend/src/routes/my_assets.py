from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Asset, User, UserRole

my_assets_bp = Blueprint("my_assets", __name__)


@my_assets_bp.route("", methods=["GET"])
@jwt_required()
def get_my_assets():
    """Get assets assigned to the current user (for viewers)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    # Viewers can only see their own assets
    # Managers and admins can use regular asset endpoints
    if current_user.role == UserRole.VIEWER:
        assets = Asset.query.filter_by(assigned_to_id=current_user_id).all()
    else:
        # For non-viewers, show all assets they have access to
        if current_user.role == UserRole.ADMIN:
            assets = Asset.query.all()
        else:  # MANAGER
            user_dept_ids = [dept.id for dept in current_user.departments]
            if user_dept_ids:
                assets = Asset.query.filter(Asset.department_id.in_(user_dept_ids)).all()
            else:
                assets = []

    return jsonify([asset.to_dict() for asset in assets])


@my_assets_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_my_stats():
    """Get statistics for current user's assigned assets"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role == UserRole.VIEWER:
        assets = Asset.query.filter_by(assigned_to_id=current_user_id).all()
    else:
        # For other roles, return general stats
        if current_user.role == UserRole.ADMIN:
            assets = Asset.query.all()
        else:  # MANAGER
            user_dept_ids = [dept.id for dept in current_user.departments]
            if user_dept_ids:
                assets = Asset.query.filter(Asset.department_id.in_(user_dept_ids)).all()
            else:
                assets = []

    total_value = sum(asset.purchase_value or 0 for asset in assets)
    total_count = len(assets)

    by_status = {}
    by_category = {}

    for asset in assets:
        # Count by status
        status = asset.status.value
        by_status[status] = by_status.get(status, 0) + 1

        # Count by category
        category = asset.category or "Other"
        by_category[category] = by_category.get(category, 0) + 1

    return jsonify({
        "total_count": total_count,
        "total_value": total_value,
        "by_status": by_status,
        "by_category": by_category,
        "role": current_user.role.value
    })
