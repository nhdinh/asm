from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Asset, Department, UserActivity, User, UserRole, AssetStatus
from sqlalchemy import func
from datetime import datetime

report_bp = Blueprint("reports", __name__)


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

    # Apply permission filter
    if current_user.role == UserRole.MANAGER:
        query = query.filter_by(department_id=current_user.department_id)

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
    if current_user.role == UserRole.MANAGER:
        if asset.department_id != current_user.department_id:
            return jsonify({"message": "Unauthorized"}), 403

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

        assets_by_status = (
            db.session.query(Asset.status, func.count(Asset.id))
            .group_by(Asset.status)
            .all()
        )

        recent_activities = (
            UserActivity.query.order_by(UserActivity.timestamp.desc()).limit(10).all()
        )
    else:
        total_assets = Asset.query.filter_by(
            department_id=current_user.department_id
        ).count()
        total_departments = 1
        total_users = User.query.filter_by(
            department_id=current_user.department_id
        ).count()

        assets_by_status = (
            db.session.query(Asset.status, func.count(Asset.id))
            .filter_by(department_id=current_user.department_id)
            .group_by(Asset.status)
            .all()
        )

        recent_activities = (
            UserActivity.query.filter_by(user_id=current_user_id)
            .order_by(UserActivity.timestamp.desc())
            .limit(10)
            .all()
        )

    return jsonify(
        {
            "total_assets": total_assets,
            "total_departments": total_departments,
            "total_users": total_users,
            "assets_by_status": {
                status.value: count for status, count in assets_by_status
            },
            "recent_activities": [a.to_dict() for a in recent_activities],
        }
    )
