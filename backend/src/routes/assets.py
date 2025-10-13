from flask import Blueprint, current_app, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import (
    Profile,
    db,
    Asset,
    AssetStatus,
    AssetTransfer,
    ProfileRole,
    UserActivity,
    ActivityStatus,
    SystemSetting,
    Department,
)
from datetime import datetime
from audit_logger import audit_logger
from pagination import paginate_query, create_pagination_response, get_sort_params
import csv
import io

asset_bp = Blueprint("assets", __name__)


def user_has_access_to_department(user, department_id):
    """Check if user has access to a department (admin or manager of that department)"""
    if user.role == ProfileRole.ADMIN:
        return True
    user_dept_ids = [dept.id for dept in user.departments]
    return department_id in user_dept_ids


@asset_bp.route("", methods=["GET"])
@jwt_required()
def get_assets():
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Regular users (non-managers, non-admins) should use /api/my-assets endpoint
    if current_profile.role == ProfileRole.USER:
        # Check if user is a manager of any department
        is_manager = any(
            assoc.is_manager for assoc in current_profile.department_associations
        )
        if not is_manager:
            return (
                jsonify(
                    {"message": "Regular users should use /api/my-assets endpoint"}
                ),
                403,
            )

    # Build base query - exclude soft-deleted assets by default
    include_deleted = request.args.get("include_deleted", "false").lower() == "true"
    query = Asset.query_all(include_deleted=include_deleted)

    # Asset access control for non-admin users (managers)
    if current_profile.role == ProfileRole.USER:
        from models import ProfileDepartment

        # Get departments where user is manager
        managed_dept_ids = [
            assoc.department_id
            for assoc in current_profile.department_associations
            if assoc.is_manager
        ]

        if managed_dept_ids:
            # Manager can see:
            # 1. If assigned_to_user is NULL: assets in their departments
            # 2. If assigned_to_user is NOT NULL: ONLY assets assigned to users in their departments
            query = query.outerjoin(User, Asset.assigned_to_user == Profile.id)
            query = query.outerjoin(
                ProfileDepartment, Profile.id == ProfileDepartment.profile_id
            )

            query = query.filter(
                db.or_(
                    # Assets not assigned to any user but in manager's department
                    db.and_(
                        Asset.assigned_to_user.is_(None),
                        Asset.assigned_to_department.in_(managed_dept_ids),
                    ),
                    # Assets assigned to users in manager's departments
                    db.and_(
                        Asset.assigned_to_user.isnot(None),
                        ProfileDepartment.department_id.in_(managed_dept_ids),
                    ),
                )
            )
        else:
            # User is not a manager of any department, show no assets
            query = query.filter(db.false())

    # Apply filters
    department_id = request.args.get("department_id")
    status = request.args.get("status")
    category = request.args.get("category")
    search = request.args.get("search")
    assigned_to_id = request.args.get("assigned_to_id")
    show_inactive = request.args.get("show_inactive", "false").lower() == "true"

    # Hide inactive assets by default (unless show_inactive=true)
    if not show_inactive:
        query = query.filter(Asset.status == AssetStatus.ACTIVE)

    if department_id:
        from models import ProfileDepartment

        # Filter assets by department
        # Show assets that meet BOTH conditions:
        # 1. If assigned_to_user is NULL: show if assigned_to_department = department_id
        # 2. If assigned_to_user is NOT NULL: show ONLY if user belongs to department_id

        # Need fresh joins if not already joined
        if current_profile.role != ProfileRole.USER:
            query = query.outerjoin(Profile, Asset.assigned_to_user == Profile.id)
            query = query.outerjoin(
                ProfileDepartment, Profile.id == ProfileDepartment.profile_id
            )

        query = query.filter(
            db.or_(
                # Asset not assigned to any user but in this department
                db.and_(
                    Asset.assigned_to_user.is_(None),
                    Asset.assigned_to_department == department_id,
                ),
                # Asset assigned to user who belongs to this department
                db.and_(
                    Asset.assigned_to_user.isnot(None),
                    ProfileDepartment.department_id == department_id,
                ),
            )
        )
    if status:
        query = query.filter_by(status=AssetStatus[status.upper()])
    if category:
        query = query.filter_by(category=category)
    if assigned_to_id:
        query = query.filter(Asset.assigned_to_user == assigned_to_id)
    if search:
        # Search in code, name, description
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                Asset.code.ilike(search_filter),
                Asset.name.ilike(search_filter),
                Asset.description.ilike(search_filter),
            )
        )

    # Get sort parameters
    sort_by, sort_order = get_sort_params()

    # Apply sorting
    valid_sort_fields = {
        "code": Asset.code,
        "name": Asset.name,
        "category": Asset.category,
        "purchase_value": Asset.purchase_value,
        "purchase_date": Asset.purchase_date,
        "status": Asset.status,
        "created_at": Asset.created_at,
    }

    if sort_by in valid_sort_fields:
        sort_column = valid_sort_fields[sort_by]
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Default sorting
        query = query.order_by(Asset.created_at.desc())

    pagination_result = paginate_query(query, user=current_profile)

    return jsonify(create_pagination_response(pagination_result, lambda a: a.to_dict()))


@asset_bp.route("", methods=["POST"])
@jwt_required()
def create_asset():
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Regular users (non-managers) cannot create assets
    if current_profile.role == ProfileRole.USER:
        # Check if user is a manager of any department
        is_manager = any(
            assoc.is_manager for assoc in current_profile.department_associations
        )
        if not is_manager:
            return (
                jsonify(
                    {"message": "Unauthorized - regular users cannot create assets"}
                ),
                403,
            )

    data = request.json

    # Check permissions - Managers can only create assets for departments they manage
    if current_profile.role == ProfileRole.USER:
        managed_dept_ids = [
            assoc.department_id
            for assoc in current_profile.department_associations
            if assoc.is_manager
        ]
        if data.get("department_id") not in managed_dept_ids:
            return (
                jsonify(
                    {
                        "message": "Unauthorized - can only create assets for departments you manage"
                    }
                ),
                403,
            )

    if Asset.query.filter_by(code=data["code"]).first():
        return jsonify({"message": "Asset code already exists"}), 400

    # Validate that assigned user belongs to the asset's department
    assigned_to_user = data.get("assigned_to_id") or data.get("assigned_to_user")
    if assigned_to_user:
        assigned_user = Profile.query.get(assigned_to_user)
        if not assigned_user:
            return jsonify({"message": "Assigned user not found"}), 400

        user_dept_ids = [dept.id for dept in assigned_user.departments]
        assigned_to_department = data.get("department_id") or data.get(
            "assigned_to_department"
        )
        if assigned_to_department and assigned_to_department not in user_dept_ids:
            return (
                jsonify(
                    {
                        "message": "Cannot assign asset to user - user does not belong to the asset's department"
                    }
                ),
                400,
            )

    # Handle category - find or create
    category_id = None
    category_name = data.get("category")
    if category_name:
        from models import AssetCategory

        category = AssetCategory.query.filter_by(name=category_name).first()
        if not category:
            # Create new category automatically
            category = AssetCategory(
                name=category_name,
                description=f"Auto-created when adding asset {data['code']}",
            )
            db.session.add(category)
            db.session.flush()  # Get the ID
        category_id = category.id

    # Determine assigned_to_user and assigned_to_department
    assigned_to_user = data.get("assigned_to_id") or data.get("assigned_to_user")
    assigned_to_department = data.get("department_id") or data.get(
        "assigned_to_department"
    )

    asset = Asset(
        code=data["code"],
        name=data["name"],
        description=data.get("description"),
        category=data.get("category"),  # Keep for backward compatibility
        category_id=category_id,
        purchase_value=data.get("purchase_value"),
        purchase_date=(
            datetime.strptime(data["purchase_date"], "%Y-%m-%d").date()
            if data.get("purchase_date")
            else None
        ),
        assigned_to_department=assigned_to_department,
        status=AssetStatus[data.get("status", "ACTIVE").upper()],
        assigned_to_user=assigned_to_user,
        condition_notes=data.get("condition_notes"),
        location=data.get("location"),
    )

    db.session.add(asset)
    db.session.flush()  # Get asset.id before commit

    # Create transfer record if asset is assigned to a user
    if assigned_to_user:
        transfer = AssetTransfer(
            asset_id=asset.id,
            to_department_id=assigned_to_department,
            assigned_to_id=assigned_to_user,
            transferred_by=current_profile_id,
            notes=f"Bàn giao tài sản lần đầu tiên",
        )
        db.session.add(transfer)

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="create_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Created asset {asset.code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="create",
        entity_type="asset",
        entity_id=asset.id,
        new_values=asset.to_dict(),
        details=f"Created asset {asset.code}",
        ip_address=request.remote_addr,
    )

    return jsonify(asset.to_dict()), 201


@asset_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_asset(id):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Only admins can edit assets
    if current_profile.role != ProfileRole.ADMIN:
        return (
            jsonify({"message": "Unauthorized - only administrators can edit assets"}),
            403,
        )

    asset = Asset.query.get_or_404(id)

    # Capture old values for audit
    old_values = asset.to_dict()

    data = request.json

    asset.name = data.get("name", asset.name)
    asset.description = data.get("description", asset.description)

    # Handle category - find or create
    if "category" in data:
        category_name = data.get("category")
        if category_name:
            from models import AssetCategory

            category = AssetCategory.query.filter_by(name=category_name).first()
            if not category:
                # Create new category automatically
                category = AssetCategory(
                    name=category_name,
                    description=f"Auto-created when updating asset {asset.code}",
                )
                db.session.add(category)
                db.session.flush()  # Get the ID
            asset.category_id = category.id
        else:
            asset.category = None
            asset.category_id = None

    asset.purchase_value = data.get("purchase_value", asset.purchase_value)
    if data.get("purchase_date"):
        asset.purchase_date = datetime.strptime(
            data["purchase_date"], "%Y-%m-%d"
        ).date()
    if data.get("status"):
        asset.status = AssetStatus[data["status"].upper()]

    # Update department FIRST - support both parameter names
    # This must happen before assigned_to_user validation
    if "department_id" in data or "assigned_to_department" in data:
        new_dept_id = data.get("department_id") or data.get("assigned_to_department")
        if new_dept_id is not None:
            # Validate department exists
            department = Department.query.get(new_dept_id)
            if not department:
                return jsonify({"message": "Department not found"}), 400
            asset.assigned_to_department = new_dept_id

    # Track if assigned_to changed
    old_assigned_to = asset.assigned_to_user

    # Update new fields - support both old and new parameter names
    if ("assigned_to_id" in data or "assigned_to_user" in data) and (
        "assigned_to_department_id" in data or "assigned_to_department" in data
    ):
        new_assigned_to_profile = data.get("assigned_to_id") or data.get(
            "assigned_to_user"
        )
        new_assigned_to_department = data.get("assigned_to_department_id") or data.get(
            "assigned_to_department"
        )

        # Validate that assigned user belongs to the asset's department
        if (
            new_assigned_to_profile is not None
            and new_assigned_to_department is not None
        ):
            assigned_user = Profile.query.get(new_assigned_to_profile)
            if not assigned_user:
                return jsonify({"message": "Assigned user not found"}), 400

            profile_dept_ids = [dept.id for dept in assigned_user.departments]
            if new_assigned_to_department not in profile_dept_ids:
                current_app.logger.error(
                    "Cannot assign asset to user - user does not belong to the asset's department"
                )
                return (
                    jsonify(
                        {
                            "message": "Cannot assign asset to user - user does not belong to the asset's department"
                        }
                    ),
                    400,
                )

        asset.assigned_to_department = new_assigned_to_department
        asset.assigned_to_user = new_assigned_to_profile
    # elif (
    #     "department_id" in data or "assigned_to_department" in data
    # ) and asset.assigned_to_user is not None:
    #     # If only department is being updated (not assigned_to_user) and asset has an assigned user,
    #     # validate that the existing user belongs to the new department
    #     assigned_user = Profile.query.get(asset.assigned_to_user)
    #     if assigned_user:
    #         profile_dept_ids = [dept.id for dept in assigned_user.departments]
    #         new_dept = asset.assigned_to_department
    #         if new_dept and new_dept not in profile_dept_ids:
    #             # Unassign user if they don't belong to new department
    #             asset.assigned_to_user = None

    # Create transfer record if assignment changed
    if (
        new_assigned_to_profile != old_assigned_to
        and new_assigned_to_profile is not None
    ):
        transfer = AssetTransfer(
            asset_id=asset.id,
            to_department_id=asset.assigned_to_department,
            assigned_to_id=new_assigned_to_profile,
            transferred_by=current_profile_id,
            notes=f"Bàn giao tài sản {'lần đầu tiên' if old_assigned_to is None else 'cho người dùng mới'}",
        )
        db.session.add(transfer)

    if "condition_notes" in data:
        asset.condition_notes = data.get("condition_notes")

    if "location" in data:
        asset.location = data.get("location")

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="update_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Updated asset {asset.code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="update",
        entity_type="asset",
        entity_id=asset.id,
        old_values=old_values,
        new_values=asset.to_dict(),
        details=f"Updated asset {asset.code}",
        ip_address=request.remote_addr,
    )

    return jsonify(asset.to_dict())


@asset_bp.route("/<int:id>/transfer", methods=["POST"])
@jwt_required()
def transfer_asset(id):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Regular users (non-managers) cannot transfer assets
    if current_profile.role == ProfileRole.USER:
        is_manager = any(
            assoc.is_manager for assoc in current_profile.department_associations
        )
        if not is_manager:
            return (
                jsonify(
                    {"message": "Unauthorized - regular users cannot transfer assets"}
                ),
                403,
            )

    asset = Asset.query.get_or_404(id)
    data = request.json

    # Check permissions
    if current_profile.role == ProfileRole.USER:
        # Managers can only reassign assets within departments they manage
        # They CANNOT transfer assets to other departments
        managed_dept_ids = [
            assoc.department_id
            for assoc in current_profile.department_associations
            if assoc.is_manager
        ]

        if asset.assigned_to_department not in managed_dept_ids:
            return (
                jsonify(
                    {
                        "message": "Unauthorized - asset is not in a department you manage"
                    }
                ),
                403,
            )

        # Managers cannot change department - can only reassign to users within same department
        if data["to_department_id"] != asset.assigned_to_department:
            return (
                jsonify(
                    {
                        "message": "Managers cannot transfer assets to other departments. Only reassignment within your department is allowed."
                    }
                ),
                403,
            )

    # Require assigned_to_id or assigned_to_user when transferring
    assigned_to_user = data.get("assigned_to_id") or data.get("assigned_to_user")
    if not assigned_to_user:
        return (
            jsonify(
                {
                    "message": "assigned_to_id or assigned_to_user is required - asset must be assigned to a specific user"
                }
            ),
            400,
        )

    # Validate that assigned user belongs to the target department
    assigned_user = Profile.query.get(assigned_to_user)
    if not assigned_user:
        return jsonify({"message": "Assigned user not found"}), 400

    user_dept_ids = [dept.id for dept in assigned_user.departments]
    if data["to_department_id"] not in user_dept_ids:
        return (
            jsonify(
                {
                    "message": "Cannot assign asset to user - user does not belong to the target department"
                }
            ),
            400,
        )

    # Create transfer record
    transfer = AssetTransfer(
        asset_id=asset.id,
        from_department_id=asset.assigned_to_department,
        to_department_id=data["to_department_id"],
        assigned_to_id=assigned_to_user,
        transferred_by=current_profile_id,
        notes=data.get("notes"),
    )

    # Update asset department (only admins can change this)
    asset.assigned_to_department = data["to_department_id"]

    # Update asset assignment if specified
    if "assigned_to_id" in data or "assigned_to_user" in data:
        asset.assigned_to_user = assigned_to_user

    db.session.add(transfer)

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="transfer_asset",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Transferred asset {asset.code} from dept {transfer.from_department_id} to {transfer.to_department_id}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="transfer",
        entity_type="asset",
        entity_id=asset.id,
        old_values={"department_id": transfer.from_department_id},
        new_values={
            "department_id": transfer.to_department_id,
            "transfer_id": transfer.id,
        },
        details=f"Transferred asset {asset.code} from dept {transfer.from_department_id} to {transfer.to_department_id}",
        ip_address=request.remote_addr,
    )

    return jsonify(transfer.to_dict()), 201


@asset_bp.route("/<int:id>", methods=["GET"])
@jwt_required()
def get_asset(id):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    asset = Asset.query.get_or_404(id)
    asset_dict = asset.to_dict()
    current_app.logger.info(f"Asset: {asset_dict}")

    # Check permissions
    if not user_has_access_to_department(current_profile, asset.assigned_to_department):
        return (
            jsonify({"message": "Unauthorized - no access to this asset's department"}),
            403,
        )

    return jsonify(asset.to_dict())


@asset_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_asset(id):
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Only admins can delete assets
    if current_profile.role != ProfileRole.ADMIN:
        return (
            jsonify(
                {"message": "Unauthorized - only administrators can delete assets"}
            ),
            403,
        )

    asset = Asset.query.get_or_404(id)

    asset_code = asset.code
    old_values = asset.to_dict()

    # Soft delete - set deleted_at timestamp
    from datetime import datetime

    asset.deleted_at = datetime.utcnow()

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action="delete_asset",
        entity_type="asset",
        entity_id=id,
        details=f"Deleted asset {asset_code} (soft delete)",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="delete",
        entity_type="asset",
        entity_id=id,
        old_values=old_values,
        new_values={"deleted_at": asset.deleted_at.isoformat()},
        details=f"Deleted asset {asset_code} (soft delete)",
        ip_address=request.remote_addr,
    )

    return "", 204


@asset_bp.route("/<int:id>/history", methods=["GET"])
@jwt_required()
def get_asset_history(id):
    asset = Asset.query.get_or_404(id)
    transfers = asset.transfers.order_by(AssetTransfer.transfer_date.desc()).all()
    return jsonify([transfer.to_dict() for transfer in transfers])


@asset_bp.route("/sample-csv", methods=["GET"])
@jwt_required()
def download_sample_csv():
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    # Create sample CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "code",
            "name",
            "description",
            "category",
            "purchase_value",
            "purchase_date",
            "department_id",
            "assigned_to_id",
            "status",
            "condition_notes",
            "location",
        ]
    )

    # Write sample rows
    writer.writerow(
        [
            "LAPTOP-001",
            "Dell Latitude 5420",
            "Business laptop with i5 processor",
            "Laptop",
            "25000000",
            "2024-01-15",
            "1",
            "3",
            "active",
            "Good condition",
            "Office Room 301",
        ]
    )
    writer.writerow(
        [
            "DESK-001",
            "Standing Desk",
            "Adjustable height desk",
            "Furniture",
            "5000000",
            "2024-02-20",
            "2",
            "4",
            "active",
            "",
            "Warehouse A, Shelf 5",
        ]
    )

    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=assets_sample.csv"},
    )


@asset_bp.route("/upload-csv", methods=["POST"])
@jwt_required()
def upload_assets_csv():
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    if "file" not in request.files:
        return jsonify({"message": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"message": "No file selected"}), 400

    if not file.filename.endswith(".csv"):
        return jsonify({"message": "File must be a CSV"}), 400

    try:
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        created_assets = []
        errors = []

        for row_num, row in enumerate(
            csv_reader, start=2
        ):  # start=2 because row 1 is header
            try:
                # Validate required fields
                if (
                    not row.get("code")
                    or not row.get("name")
                    or not row.get("department_id")
                ):
                    errors.append(
                        f"Row {row_num}: Missing required fields (code, name, department_id)"
                    )
                    continue

                # Check if asset already exists
                if Asset.query.filter_by(code=row["code"]).first():
                    errors.append(
                        f"Row {row_num}: Asset code '{row['code']}' already exists"
                    )
                    continue

                # Parse status
                status_str = row.get("status", "active").lower()
                if status_str == "damaged":
                    status = AssetStatus.DAMAGED
                elif status_str == "disposed":
                    status = AssetStatus.DISPOSED
                else:
                    status = AssetStatus.ACTIVE

                # Parse purchase_date
                purchase_date = None
                if row.get("purchase_date"):
                    try:
                        purchase_date = datetime.strptime(
                            row["purchase_date"], "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        errors.append(
                            f"Row {row_num}: Invalid purchase_date format (use YYYY-MM-DD)"
                        )
                        continue

                # Validate department exists
                department_id = int(row["department_id"])
                from models import Department

                if not Department.query.get(department_id):
                    errors.append(
                        f"Row {row_num}: Department ID {department_id} not found"
                    )
                    continue

                # Validate assigned_to_id if provided
                assigned_to_id = None
                if row.get("assigned_to_id"):
                    assigned_to_id = int(row["assigned_to_id"])
                    assigned_user = Profile.query.get(assigned_to_id)
                    if not assigned_user:
                        errors.append(
                            f"Row {row_num}: User ID {assigned_to_id} not found"
                        )
                        continue

                    # Validate user belongs to department
                    user_dept_ids = [dept.id for dept in assigned_user.departments]
                    if department_id not in user_dept_ids:
                        errors.append(
                            f"Row {row_num}: User {assigned_to_id} does not belong to department {department_id}"
                        )
                        continue

                # Create asset
                asset = Asset(
                    code=row["code"],
                    name=row["name"],
                    description=row.get("description"),
                    category=row.get("category"),
                    purchase_value=(
                        float(row["purchase_value"])
                        if row.get("purchase_value")
                        else None
                    ),
                    purchase_date=purchase_date,
                    assigned_to_department=department_id,
                    assigned_to_user=assigned_to_id,
                    status=status,
                    condition_notes=row.get("condition_notes"),
                    location=row.get("location"),
                )

                db.session.add(asset)
                db.session.flush()  # Get asset.id

                # Create transfer record if assigned to a user
                if assigned_to_id:
                    transfer = AssetTransfer(
                        asset_id=asset.id,
                        to_department_id=department_id,
                        assigned_to_id=assigned_to_id,
                        transferred_by=current_profile_id,
                        notes=f"Initial assignment via CSV upload",
                    )
                    db.session.add(transfer)

                # Log activity
                activity = UserActivity(
                    user_id=current_profile.id,
                    username=current_profile.username,
                    action="create_asset_csv",
                    entity_type="asset",
                    entity_id=asset.id,
                    details=f"Created asset {asset.code} via CSV upload",
                    status=ActivityStatus.SUCCESS,
                )
                db.session.add(activity)

                created_assets.append(asset.code)

            except Exception as e:
                db.session.rollback()
                errors.append(f"Row {row_num}: {str(e)}")
                continue

        # Commit all successful assets
        if created_assets:
            db.session.commit()

        return jsonify(
            {
                "message": f"CSV processed successfully",
                "created": len(created_assets),
                "created_assets": created_assets,
                "errors": errors,
            }
        ), (
            200 if not errors else 207
        )  # 207 = Multi-Status

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error processing CSV: {str(e)}"}), 400


@asset_bp.route("/<int:id>/mark-inactive", methods=["POST"])
@jwt_required()
def mark_asset_inactive(id):
    """
    Mark asset as damaged or disposed and transfer to bad assets department.
    Only admins and managers can perform this action.
    """
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    # Regular users (non-managers) cannot mark assets as inactive
    if current_profile.role == ProfileRole.USER:
        is_manager = any(
            assoc.is_manager for assoc in current_profile.department_associations
        )
        if not is_manager:
            return (
                jsonify(
                    {
                        "message": "Unauthorized - regular users cannot mark assets as inactive"
                    }
                ),
                403,
            )

    asset = Asset.query.get_or_404(id)
    data = request.json

    # Get the new status from request
    new_status = data.get("status", "damaged")  # Default to damaged
    if new_status not in ["damaged", "disposed"]:
        return (
            jsonify({"message": "Invalid status. Must be 'damaged' or 'disposed'"}),
            400,
        )

    # Check permissions for managers
    if current_profile.role == ProfileRole.USER:
        managed_dept_ids = [
            assoc.department_id
            for assoc in current_profile.department_associations
            if assoc.is_manager
        ]
        if asset.assigned_to_department not in managed_dept_ids:
            return (
                jsonify(
                    {
                        "message": "Unauthorized - asset is not in a department you manage"
                    }
                ),
                403,
            )

    # Get bad assets department from system settings
    bad_dept_setting = SystemSetting.query.filter_by(
        key="bad_assets_department_id"
    ).first()
    if not bad_dept_setting:
        return (
            jsonify(
                {"message": "Bad assets department not configured in system settings"}
            ),
            500,
        )

    try:
        bad_dept_id = int(bad_dept_setting.value)
    except (ValueError, TypeError):
        return (
            jsonify({"message": "Invalid bad assets department ID in system settings"}),
            500,
        )

    # Store old values for audit
    old_status = asset.status.value
    old_department_id = asset.assigned_to_department
    old_assigned_to_id = asset.assigned_to_user

    # Update asset status
    asset.status = AssetStatus[new_status.upper()]

    # Only transfer if not already in bad assets department
    if asset.assigned_to_department != bad_dept_id:
        # Create transfer record
        transfer = AssetTransfer(
            asset_id=asset.id,
            from_department_id=asset.assigned_to_department,
            to_department_id=bad_dept_id,
            assigned_to_id=None,  # Unassign from user
            transferred_by=current_profile_id,
            notes=data.get(
                "notes",
                f"Asset marked as {new_status} and transferred to bad assets department",
            ),
        )
        db.session.add(transfer)

        # Update asset department
        asset.assigned_to_department = bad_dept_id

    # Unassign from user
    asset.assigned_to_user = None
    asset.condition_notes = data.get("condition_notes", asset.condition_notes)

    # Log activity
    activity = UserActivity(
        user_id=current_profile.id,
        username=current_profile.username,
        action=f"mark_asset_{new_status}",
        entity_type="asset",
        entity_id=asset.id,
        details=f"Marked asset {asset.code} as {new_status}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)

    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action="update",
        entity_type="asset",
        entity_id=asset.id,
        old_values={
            "status": old_status,
            "department_id": old_department_id,
            "assigned_to_id": old_assigned_to_id,
        },
        new_values={
            "status": new_status,
            "department_id": asset.assigned_to_department,
            "assigned_to_id": None,
        },
        details=f"Marked asset {asset.code} as {new_status} and transferred to bad assets department",
        ip_address=request.remote_addr,
    )

    return (
        jsonify(
            {
                "message": f"Asset marked as {new_status} and transferred successfully",
                "asset": asset.to_dict(),
            }
        ),
        200,
    )


@asset_bp.route("/<int:id>/propose-liquidation", methods=["POST"])
@jwt_required()
def propose_asset_for_liquidation(id):
    """Propose or unpropose an asset for liquidation (admin and department managers only)"""
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    asset = Asset.query.get_or_404(id)

    # Authorization: Admin or manager of the asset's department
    if current_profile.role != ProfileRole.ADMIN:
        # Check if user is manager of asset's department
        is_manager_of_dept = any(
            assoc.department_id == asset.assigned_to_department and assoc.is_manager
            for assoc in current_profile.department_associations
        )
        if not is_manager_of_dept:
            return (
                jsonify(
                    {
                        "message": "Unauthorized - only admins or department managers can propose assets for liquidation"
                    }
                ),
                403,
            )

    data = request.json
    propose = data.get("propose_for_liquidation", True)

    # Capture old value for audit
    old_value = asset.propose_for_liquidation

    # Update the flag
    asset.propose_for_liquidation = propose
    db.session.commit()

    # Log the activity
    action = (
        "propose_asset_for_liquidation"
        if propose
        else "unpropose_asset_for_liquidation"
    )
    audit_logger.log(
        user_id=current_profile.id,
        username=current_profile.username,
        action=action,
        entity_type="asset",
        entity_id=asset.id,
        old_values={"propose_for_liquidation": old_value},
        new_values={"propose_for_liquidation": propose},
        details=f"Asset {asset.code} {'proposed' if propose else 'unproposed'} for liquidation",
        ip_address=request.remote_addr,
    )

    message = (
        f"Asset {asset.code} proposed for liquidation"
        if propose
        else f"Asset {asset.code} removed from liquidation proposal"
    )
    return jsonify({"message": message, "asset": asset.to_dict()}), 200
