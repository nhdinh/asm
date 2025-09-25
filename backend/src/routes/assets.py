from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Asset, AssetStatus, AssetTransfer, User, UserRole, UserActivity
from datetime import datetime

asset_bp = Blueprint("assets", __name__)


@asset_bp.route("", methods=["GET"])
@jwt_required()
def get_assets():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    query = Asset.query

    # Filter by department for managers
    if current_user.role == UserRole.MANAGER:
        query = query.filter_by(department_id=current_user.department_id)

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

    # Check permissions
    if current_user.role == UserRole.MANAGER:
        if data.get("department_id") != current_user.department_id:
            return jsonify({"message": "Unauthorized"}), 403

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
    )

    db.session.add(asset)
    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="create_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Created asset {asset.code}",
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
    if current_user.role == UserRole.MANAGER:
        if asset.department_id != current_user.department_id:
            return jsonify({"message": "Unauthorized"}), 403

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

    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="update_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Updated asset {asset.code}",
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

    # Check permissions
    if current_user.role == UserRole.MANAGER:
        if (
            asset.department_id != current_user.department_id
            and data["to_department_id"] != current_user.department_id
        ):
            return jsonify({"message": "Unauthorized"}), 403

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
    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="transfer_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Transferred asset {asset.code} from dept {transfer.from_department_id} to {transfer.to_department_id}",
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify(transfer.to_dict()), 201


@asset_bp.route("/<int:id>/history", methods=["GET"])
@jwt_required()
def get_asset_history(id):
    asset = Asset.query.get_or_404(id)
    transfers = asset.transfers.order_by(AssetTransfer.transfer_date.desc()).all()
    return jsonify([transfer.to_dict() for transfer in transfers])
