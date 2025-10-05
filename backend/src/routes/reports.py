from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Asset, Department, UserActivity, User, UserRole, AssetStatus
from sqlalchemy import func
from datetime import datetime

report_bp = Blueprint("reports", __name__)


def user_has_access_to_department(user, department_id):
    """Check if user has access to a department (admin or manager of that department)"""
    if user.role == UserRole.ADMIN:
        return True
    user_dept_ids = [dept.id for dept in user.departments]
    return department_id in user_dept_ids


@report_bp.route("/assets", methods=["GET"])
@jwt_required()
def asset_report():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    # Get filters
    department_id = request.args.get("department_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    status = request.args.get("status")
    category = request.args.get("category")

    query = Asset.query

    # Apply permission filter - managers only see assets from their departments
    if current_user.role == UserRole.MANAGER:
        user_dept_ids = [dept.id for dept in current_user.departments]
        if user_dept_ids:
            query = query.filter(Asset.department_id.in_(user_dept_ids))

    # Apply filters
    if department_id:
        query = query.filter_by(department_id=department_id)
    if status:
        query = query.filter_by(status=AssetStatus[status.upper()])
    if category:
        query = query.filter_by(category=category)
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(Asset.purchase_date >= start.date())
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d")
        query = query.filter(Asset.purchase_date <= end.date())

    assets = query.all()

    # Calculate statistics
    total_value = sum(asset.purchase_value or 0 for asset in assets)
    status_counts = {}
    category_counts = {}

    for asset in assets:
        status_counts[asset.status.value] = status_counts.get(asset.status.value, 0) + 1
        if asset.category:
            category_counts[asset.category] = category_counts.get(asset.category, 0) + 1

    return jsonify(
        {
            "assets": [asset.to_dict() for asset in assets],
            "statistics": {
                "total_count": len(assets),
                "total_value": total_value,
                "by_status": status_counts,
                "by_category": category_counts,
            },
        }
    )


@report_bp.route("/asset/<int:id>", methods=["GET"])
@jwt_required()
def single_asset_report(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    asset = Asset.query.get_or_404(id)

    # Check permissions
    if not user_has_access_to_department(current_user, asset.department_id):
        return jsonify({"message": "Unauthorized - no access to this asset's department"}), 403

    # Get transfer history
    transfers = asset.transfers.order_by(AssetTransfer.transfer_date.desc()).all()

    # Get related activities
    activities = (
        UserActivity.query.filter_by(entity_type="asset", entity_id=asset.id)
        .order_by(UserActivity.timestamp.desc())
        .all()
    )

    return jsonify(
        {
            "asset": asset.to_dict(),
            "transfer_history": [t.to_dict() for t in transfers],
            "activities": [a.to_dict() for a in activities],
        }
    )


@report_bp.route("/user-activities", methods=["GET"])
@jwt_required()
def user_activity_report():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    # Get filters
    user_id = request.args.get("user_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = UserActivity.query

    if user_id:
        query = query.filter_by(user_id=user_id)
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(UserActivity.timestamp >= start)
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d")
        query = query.filter(UserActivity.timestamp <= end)

    activities = query.order_by(UserActivity.timestamp.desc()).all()

    # Group by user
    user_stats = {}
    for activity in activities:
        user_id = activity.user_id
        if user_id not in user_stats:
            user_stats[user_id] = {
                "username": activity.user.username,
                "total_activities": 0,
                "actions": {},
            }
        user_stats[user_id]["total_activities"] += 1
        action = activity.action
        user_stats[user_id]["actions"][action] = (
            user_stats[user_id]["actions"].get(action, 0) + 1
        )

    return jsonify(
        {"activities": [a.to_dict() for a in activities], "statistics": user_stats}
    )


@report_bp.route("/dashboard", methods=["GET"])
@jwt_required()
def dashboard_stats():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role == UserRole.ADMIN:
        total_assets = Asset.query.count()
        total_departments = Department.query.count()
        total_users = User.query.count()

        # Calculate total value
        total_value = db.session.query(func.sum(Asset.purchase_value)).scalar() or 0

        # Get assets by status with counts
        assets_by_status = (
            db.session.query(Asset.status, func.count(Asset.id))
            .group_by(Asset.status)
            .all()
        )

        # Get assets by category with counts and values
        assets_by_category = (
            db.session.query(
                Asset.category,
                func.count(Asset.id),
                func.sum(Asset.purchase_value)
            )
            .group_by(Asset.category)
            .all()
        )

        recent_activities = (
            UserActivity.query.order_by(UserActivity.timestamp.desc()).limit(10).all()
        )
    else:
        # Manager stats - aggregate from all their departments
        user_dept_ids = [dept.id for dept in current_user.departments]

        if user_dept_ids:
            total_assets = Asset.query.filter(Asset.department_id.in_(user_dept_ids)).count()

            # Calculate total value for manager's departments
            total_value = db.session.query(func.sum(Asset.purchase_value)).filter(
                Asset.department_id.in_(user_dept_ids)
            ).scalar() or 0

            assets_by_status = (
                db.session.query(Asset.status, func.count(Asset.id))
                .filter(Asset.department_id.in_(user_dept_ids))
                .group_by(Asset.status)
                .all()
            )

            # Get assets by category for manager's departments
            assets_by_category = (
                db.session.query(
                    Asset.category,
                    func.count(Asset.id),
                    func.sum(Asset.purchase_value)
                )
                .filter(Asset.department_id.in_(user_dept_ids))
                .group_by(Asset.category)
                .all()
            )
        else:
            total_assets = 0
            total_value = 0
            assets_by_status = []
            assets_by_category = []

        total_departments = len(current_user.departments)
        total_users = sum(dept.users.count() for dept in current_user.departments)

        recent_activities = (
            UserActivity.query.filter_by(user_id=current_user_id)
            .order_by(UserActivity.timestamp.desc())
            .limit(10)
            .all()
        )

    return jsonify(
        {
            "total_assets": total_assets,
            "total_value": total_value,
            "total_departments": total_departments,
            "total_users": total_users,
            "assets_by_status": {
                status.value: count for status, count in assets_by_status
            },
            "assets_by_category": {
                category or "Khác": {"count": count, "value": value or 0}
                for category, count, value in assets_by_category
            },
            "recent_activities": [a.to_dict() for a in recent_activities],
        }
    )
