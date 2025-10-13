from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, AssetCategory, Profile, ProfileRole, UserActivity, ActivityStatus
from audit_logger import audit_logger
from pagination import paginate_query, create_pagination_response, get_sort_params

category_bp = Blueprint("categories", __name__)


@category_bp.route("", methods=["GET"])
@jwt_required()
def get_categories():
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Get sort parameters
    sort_by, sort_order = get_sort_params()

    # Build base query
    query = AssetCategory.query

    # Apply search filter
    search = request.args.get("search")
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                AssetCategory.name.ilike(search_filter),
                AssetCategory.description.ilike(search_filter),
            )
        )

    # Apply sorting
    valid_sort_fields = {
        "name": AssetCategory.name,
        "created_at": AssetCategory.created_at,
    }

    if sort_by in valid_sort_fields:
        sort_column = valid_sort_fields[sort_by]
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Default sorting
        query = query.order_by(AssetCategory.name)

    pagination_result = paginate_query(query, user=current_profile)

    return jsonify(create_pagination_response(pagination_result, lambda c: c.to_dict()))


@category_bp.route("/<int:id>", methods=["GET"])
@jwt_required()
def get_category(id):
    category = AssetCategory.query.get_or_404(id)
    return jsonify(category.to_dict())


@category_bp.route("", methods=["POST"])
@jwt_required()
def create_category():
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Only admins can create categories
    if current_profile.role != ProfileRole.ADMIN:
        return (
            jsonify(
                {"message": "Unauthorized - only administrators can create categories"}
            ),
            403,
        )

    data = request.json

    # Check if category already exists
    if AssetCategory.query.filter_by(name=data["name"]).first():
        return jsonify({"message": "Category already exists"}), 400

    category = AssetCategory(name=data["name"], description=data.get("description"))

    db.session.add(category)
    db.session.flush()  # Get category.id before commit

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="create_category",
        entity_type="asset_category",
        entity_id=category.id,
        details=f"Created category {category.name}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="create",
        entity_type="asset_category",
        entity_id=category.id,
        new_values=category.to_dict(),
        details=f"Created category {category.name}",
        ip_address=request.remote_addr,
    )

    return jsonify(category.to_dict()), 201


@category_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_category(id):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Only admins can update categories
    if current_profile.role != ProfileRole.ADMIN:
        return (
            jsonify(
                {"message": "Unauthorized - only administrators can update categories"}
            ),
            403,
        )

    category = AssetCategory.query.get_or_404(id)
    data = request.json

    # Capture old values for audit
    old_values = category.to_dict()

    # Check if name is being changed to an existing name
    if "name" in data and data["name"] != category.name:
        if AssetCategory.query.filter_by(name=data["name"]).first():
            return jsonify({"message": "Category name already exists"}), 400
        category.name = data["name"]

    if "description" in data:
        category.description = data.get("description")

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="update_category",
        entity_type="asset_category",
        entity_id=category.id,
        details=f"Updated category {category.name}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="update",
        entity_type="asset_category",
        entity_id=category.id,
        old_values=old_values,
        new_values=category.to_dict(),
        details=f"Updated category {category.name}",
        ip_address=request.remote_addr,
    )

    return jsonify(category.to_dict())


@category_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_category(id):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Only admins can delete categories
    if current_profile.role != ProfileRole.ADMIN:
        return (
            jsonify(
                {"message": "Unauthorized - only administrators can delete categories"}
            ),
            403,
        )

    category = AssetCategory.query.get_or_404(id)

    # Check if category has assets
    if category.assets.count() > 0:
        return jsonify({"message": "Cannot delete category with existing assets"}), 400

    category_name = category.name
    old_values = category.to_dict()

    db.session.delete(category)

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="delete_category",
        entity_type="asset_category",
        entity_id=id,
        details=f"Deleted category {category_name}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="delete",
        entity_type="asset_category",
        entity_id=id,
        old_values=old_values,
        new_values={},
        details=f"Deleted category {category_name}",
        ip_address=request.remote_addr,
    )

    return "", 204
