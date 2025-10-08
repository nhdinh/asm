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

    # Regular users (non-managers) can only see their own assets
    # Managers and admins can use regular asset endpoints
    if current_user.role == UserRole.USER:
        is_manager = any(assoc.is_manager for assoc in current_user.department_associations)
        if not is_manager:
            # Regular users can only see ACTIVE assets assigned to them
            from models import AssetStatus

            assets = Asset.query.filter_by(
                assigned_to_user=current_user_id, status=AssetStatus.ACTIVE
            ).all()
        else:
            # Managers show all assets from departments they manage
            from models import UserDepartment
            managed_dept_ids = [assoc.department_id for assoc in current_user.department_associations if assoc.is_manager]
            if managed_dept_ids:
                query = Asset.query
                query = query.outerjoin(User, Asset.assigned_to_user == User.id)
                query = query.outerjoin(UserDepartment, User.id == UserDepartment.user_id)
                query = query.filter(
                    db.or_(
                        # Assets not assigned to any user but in manager's department
                        db.and_(
                            Asset.assigned_to_user.is_(None),
                            Asset.assigned_to_department.in_(managed_dept_ids)
                        ),
                        # Assets assigned to users in manager's departments
                        db.and_(
                            Asset.assigned_to_user.isnot(None),
                            UserDepartment.department_id.in_(managed_dept_ids)
                        )
                    )
                )
                assets = query.all()
            else:
                assets = []
    else:
        # Admins see all assets
        assets = Asset.query.all()

    return jsonify([asset.to_dict() for asset in assets])


@my_assets_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_my_stats():
    """Get statistics for current user's assigned assets"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role == UserRole.USER:
        is_manager = any(assoc.is_manager for assoc in current_user.department_associations)
        if not is_manager:
            # Regular users see only their assigned assets
            assets = Asset.query.filter_by(assigned_to_user=current_user_id).all()
        else:
            # Managers see assets from departments they manage
            from models import UserDepartment
            managed_dept_ids = [assoc.department_id for assoc in current_user.department_associations if assoc.is_manager]
            if managed_dept_ids:
                query = Asset.query
                query = query.outerjoin(User, Asset.assigned_to_user == User.id)
                query = query.outerjoin(UserDepartment, User.id == UserDepartment.user_id)
                query = query.filter(
                    db.or_(
                        # Assets not assigned to any user but in manager's department
                        db.and_(
                            Asset.assigned_to_user.is_(None),
                            Asset.assigned_to_department.in_(managed_dept_ids)
                        ),
                        # Assets assigned to users in manager's departments
                        db.and_(
                            Asset.assigned_to_user.isnot(None),
                            UserDepartment.department_id.in_(managed_dept_ids)
                        )
                    )
                )
                assets = query.all()
            else:
                assets = []
    else:
        # Admins see all assets
        assets = Asset.query.all()

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

    return jsonify(
        {
            "total_count": total_count,
            "total_value": total_value,
            "by_status": by_status,
            "by_category": by_category,
            "role": current_user.role.value,
        }
    )
