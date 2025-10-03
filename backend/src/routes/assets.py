from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Asset, AssetStatus, AssetTransfer, User, UserRole, UserActivity, ActivityStatus
from datetime import datetime

asset_bp = Blueprint("assets", __name__)


def user_has_access_to_department(user, department_id):
    """Check if user has access to a department (admin or manager of that department)"""
    if user.role == UserRole.ADMIN:
        return True
    user_dept_ids = [dept.id for dept in user.departments]
    return department_id in user_dept_ids


@asset_bp.route("", methods=["GET"])
@jwt_required()
def get_assets():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    query = Asset.query

    # Filter by department for managers - only show assets from their departments
    if current_user.role == UserRole.MANAGER:
        user_dept_ids = [dept.id for dept in current_user.departments]
        if user_dept_ids:
            query = query.filter(Asset.department_id.in_(user_dept_ids))

    # Apply filters
    department_id = request.args.get("department_id")
    status = request.args.get("status")
    category = request.args.get("category")

    if department_id:
        query = query.filter_by(department_id=department_id)
    if status:
        query = query.filter_by(status=AssetStatus[status.upper()])
    if category:
        query = query.filter_by(category=category)

    assets = query.all()
    return jsonify([asset.to_dict() for asset in assets])


@asset_bp.route("", methods=["POST"])
@jwt_required()
def create_asset():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    data = request.json

    # Check permissions - Manager can only create assets for their departments
    if current_user.role == UserRole.MANAGER:
        user_dept_ids = [dept.id for dept in current_user.departments]
        if data.get("department_id") not in user_dept_ids:
            return jsonify({"message": "Unauthorized - can only create assets for your departments"}), 403

    if Asset.query.filter_by(code=data["code"]).first():
        return jsonify({"message": "Asset code already exists"}), 400

    asset = Asset(
        code=data["code"],
        name=data["name"],
        description=data.get("description"),
        category=data.get("category"),
        purchase_value=data.get("purchase_value"),
        purchase_date=(
            datetime.strptime(data["purchase_date"], "%Y-%m-%d").date()
            if data.get("purchase_date")
            else None
        ),
        department_id=data["department_id"],
        status=AssetStatus[data.get("status", "ACTIVE").upper()],
        assigned_to_id=data.get("assigned_to_id"),
        condition_notes=data.get("condition_notes"),
    )

    db.session.add(asset)

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
        action="create_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Created asset {asset.code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify(asset.to_dict()), 201


@asset_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_asset(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    asset = Asset.query.get_or_404(id)

    # Check permissions
    if not user_has_access_to_department(current_user, asset.department_id):
        return jsonify({"message": "Unauthorized - no access to this asset's department"}), 403

    data = request.json

    asset.name = data.get("name", asset.name)
    asset.description = data.get("description", asset.description)
    asset.category = data.get("category", asset.category)
    asset.purchase_value = data.get("purchase_value", asset.purchase_value)
    if data.get("purchase_date"):
        asset.purchase_date = datetime.strptime(
            data["purchase_date"], "%Y-%m-%d"
        ).date()
    if data.get("status"):
        asset.status = AssetStatus[data["status"].upper()]

    # Update new fields
    if "assigned_to_id" in data:
        asset.assigned_to_id = data.get("assigned_to_id")
    if "condition_notes" in data:
        asset.condition_notes = data.get("condition_notes")

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
        action="update_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Updated asset {asset.code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify(asset.to_dict())


@asset_bp.route("/<int:id>/transfer", methods=["POST"])
@jwt_required()
def transfer_asset(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    asset = Asset.query.get_or_404(id)
    data = request.json

    # Check permissions - manager must have access to source or destination department
    if current_user.role == UserRole.MANAGER:
        has_source_access = user_has_access_to_department(current_user, asset.department_id)
        has_dest_access = user_has_access_to_department(current_user, data["to_department_id"])
        if not (has_source_access or has_dest_access):
            return jsonify({"message": "Unauthorized - no access to source or destination department"}), 403

    # Create transfer record
    transfer = AssetTransfer(
        asset_id=asset.id,
        from_department_id=asset.department_id,
        to_department_id=data["to_department_id"],
        transferred_by=current_user_id,
        notes=data.get("notes"),
    )

    # Update asset department
    asset.department_id = data["to_department_id"]

    db.session.add(transfer)

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
        action="transfer_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Transferred asset {asset.code} from dept {transfer.from_department_id} to {transfer.to_department_id}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify(transfer.to_dict()), 201


@asset_bp.route("/<int:id>", methods=["GET"])
@jwt_required()
def get_asset(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    asset = Asset.query.get_or_404(id)

    # Check permissions
    if not user_has_access_to_department(current_user, asset.department_id):
        return jsonify({"message": "Unauthorized - no access to this asset's department"}), 403

    return jsonify(asset.to_dict())


@asset_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_asset(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    asset = Asset.query.get_or_404(id)

    # Check permissions
    if not user_has_access_to_department(current_user, asset.department_id):
        return jsonify({"message": "Unauthorized - no access to this asset's department"}), 403

    asset_code = asset.code
    db.session.delete(asset)

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        username=current_user.username,
        action="delete_asset",
        entity_type="asset",
        entity_id=id,
        details=f"Deleted asset {asset_code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    return "", 204


@asset_bp.route("/<int:id>/history", methods=["GET"])
@jwt_required()
def get_asset_history(id):
    asset = Asset.query.get_or_404(id)
    transfers = asset.transfers.order_by(AssetTransfer.transfer_date.desc()).all()
    return jsonify([transfer.to_dict() for transfer in transfers])
