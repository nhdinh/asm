from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Asset, AssetStatus, AssetTransfer, User, UserRole, UserActivity, ActivityStatus
from datetime import datetime
from audit_logger import audit_logger
from pagination import paginate_query, create_pagination_response, get_sort_params
import csv
import io

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

    # Viewers should use /api/my-assets endpoint
    if current_user.role == UserRole.VIEWER:
        return jsonify({"message": "Viewers should use /api/my-assets endpoint"}), 403

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
    search = request.args.get("search")

    if department_id:
        query = query.filter_by(department_id=department_id)
    if status:
        query = query.filter_by(status=AssetStatus[status.upper()])
    if category:
        query = query.filter_by(category=category)
    if search:
        # Search in code, name, description
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                Asset.code.ilike(search_filter),
                Asset.name.ilike(search_filter),
                Asset.description.ilike(search_filter)
            )
        )

    # Get sort parameters
    sort_by, sort_order = get_sort_params()

    # Apply sorting
    valid_sort_fields = {
        'code': Asset.code,
        'name': Asset.name,
        'category': Asset.category,
        'purchase_value': Asset.purchase_value,
        'purchase_date': Asset.purchase_date,
        'status': Asset.status,
        'created_at': Asset.created_at
    }

    if sort_by in valid_sort_fields:
        sort_column = valid_sort_fields[sort_by]
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Default sorting
        query = query.order_by(Asset.created_at.desc())

    pagination_result = paginate_query(query, user=current_user)

    return jsonify(create_pagination_response(pagination_result, lambda a: a.to_dict()))


@asset_bp.route("", methods=["POST"])
@jwt_required()
def create_asset():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    # Viewers cannot create assets
    if current_user.role == UserRole.VIEWER:
        return jsonify({"message": "Unauthorized - viewers cannot create assets"}), 403

    data = request.json

    # Check permissions - Manager can only create assets for their departments
    if current_user.role == UserRole.MANAGER:
        user_dept_ids = [dept.id for dept in current_user.departments]
        if data.get("department_id") not in user_dept_ids:
            return jsonify({"message": "Unauthorized - can only create assets for your departments"}), 403

    if Asset.query.filter_by(code=data["code"]).first():
        return jsonify({"message": "Asset code already exists"}), 400

    # Validate that assigned user belongs to the asset's department
    if data.get("assigned_to_id"):
        assigned_user = User.query.get(data["assigned_to_id"])
        if not assigned_user:
            return jsonify({"message": "Assigned user not found"}), 400

        user_dept_ids = [dept.id for dept in assigned_user.departments]
        if data["department_id"] not in user_dept_ids:
            return jsonify({"message": "Cannot assign asset to user - user does not belong to the asset's department"}), 400

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
                description=f"Auto-created when adding asset {data['code']}"
            )
            db.session.add(category)
            db.session.flush()  # Get the ID
        category_id = category.id

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
        department_id=data["department_id"],
        status=AssetStatus[data.get("status", "ACTIVE").upper()],
        assigned_to_id=data.get("assigned_to_id"),
        condition_notes=data.get("condition_notes"),
    )

    db.session.add(asset)
    db.session.flush()  # Get asset.id before commit

    # Create transfer record if asset is assigned to a user
    if data.get("assigned_to_id"):
        transfer = AssetTransfer(
            asset_id=asset.id,
            to_department_id=data["department_id"],
            assigned_to_id=data["assigned_to_id"],
            transferred_by=current_user_id,
            notes=f"Bàn giao tài sản lần đầu tiên"
        )
        db.session.add(transfer)

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

    # Audit log
    audit_logger.log(
        user_id=current_user_id,
        username=current_user.username,
        action='create',
        entity_type='asset',
        entity_id=asset.id,
        new_values=asset.to_dict(),
        details=f"Created asset {asset.code}",
        ip_address=request.remote_addr
    )

    return jsonify(asset.to_dict()), 201


@asset_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_asset(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    # Only admins can edit assets
    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - only administrators can edit assets"}), 403

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
                    description=f"Auto-created when updating asset {asset.code}"
                )
                db.session.add(category)
                db.session.flush()  # Get the ID
            asset.category = category_name  # Keep for backward compatibility
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

    # Track if assigned_to changed
    old_assigned_to = asset.assigned_to_id

    # Update new fields
    if "assigned_to_id" in data:
        new_assigned_to = data.get("assigned_to_id")

        # Validate that assigned user belongs to the asset's department
        if new_assigned_to is not None:
            assigned_user = User.query.get(new_assigned_to)
            if not assigned_user:
                return jsonify({"message": "Assigned user not found"}), 400

            user_dept_ids = [dept.id for dept in assigned_user.departments]
            if asset.department_id not in user_dept_ids:
                return jsonify({"message": "Cannot assign asset to user - user does not belong to the asset's department"}), 400

        asset.assigned_to_id = new_assigned_to

        # Create transfer record if assignment changed
        if new_assigned_to != old_assigned_to and new_assigned_to is not None:
            transfer = AssetTransfer(
                asset_id=asset.id,
                to_department_id=asset.department_id,
                assigned_to_id=new_assigned_to,
                transferred_by=current_user_id,
                notes=f"Bàn giao tài sản {'lần đầu tiên' if old_assigned_to is None else 'cho người dùng mới'}"
            )
            db.session.add(transfer)

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

    # Audit log
    audit_logger.log(
        user_id=current_user_id,
        username=current_user.username,
        action='update',
        entity_type='asset',
        entity_id=asset.id,
        old_values=old_values,
        new_values=asset.to_dict(),
        details=f"Updated asset {asset.code}",
        ip_address=request.remote_addr
    )

    return jsonify(asset.to_dict())


@asset_bp.route("/<int:id>/transfer", methods=["POST"])
@jwt_required()
def transfer_asset(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    # Viewers cannot transfer assets
    if current_user.role == UserRole.VIEWER:
        return jsonify({"message": "Unauthorized - viewers cannot transfer assets"}), 403

    asset = Asset.query.get_or_404(id)
    data = request.json

    # Check permissions
    if current_user.role == UserRole.MANAGER:
        # Manager can only reassign assets within their own department
        # They CANNOT transfer assets to other departments
        user_dept_ids = [dept.id for dept in current_user.departments]

        if asset.department_id not in user_dept_ids:
            return jsonify({"message": "Unauthorized - asset is not in your department"}), 403

        # Manager cannot change department - can only reassign to users within same department
        if data["to_department_id"] != asset.department_id:
            return jsonify({"message": "Managers cannot transfer assets to other departments. Only reassignment within your department is allowed."}), 403

    # Require assigned_to_id when transferring
    if not data.get("assigned_to_id"):
        return jsonify({"message": "assigned_to_id is required - asset must be assigned to a specific user"}), 400

    # Validate that assigned user belongs to the target department
    assigned_user = User.query.get(data["assigned_to_id"])
    if not assigned_user:
        return jsonify({"message": "Assigned user not found"}), 400

    user_dept_ids = [dept.id for dept in assigned_user.departments]
    if data["to_department_id"] not in user_dept_ids:
        return jsonify({"message": "Cannot assign asset to user - user does not belong to the target department"}), 400

    # Create transfer record
    transfer = AssetTransfer(
        asset_id=asset.id,
        from_department_id=asset.department_id,
        to_department_id=data["to_department_id"],
        assigned_to_id=data.get("assigned_to_id"),  # Support assigning to specific user
        transferred_by=current_user_id,
        notes=data.get("notes"),
    )

    # Update asset department (only admins can change this)
    asset.department_id = data["to_department_id"]

    # Update asset assignment if specified
    if "assigned_to_id" in data:
        asset.assigned_to_id = data.get("assigned_to_id")

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

    # Audit log
    audit_logger.log(
        user_id=current_user_id,
        username=current_user.username,
        action='transfer',
        entity_type='asset',
        entity_id=asset.id,
        old_values={'department_id': transfer.from_department_id},
        new_values={'department_id': transfer.to_department_id, 'transfer_id': transfer.id},
        details=f"Transferred asset {asset.code} from dept {transfer.from_department_id} to {transfer.to_department_id}",
        ip_address=request.remote_addr
    )

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

    # Only admins can delete assets
    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - only administrators can delete assets"}), 403

    asset = Asset.query.get_or_404(id)

    asset_code = asset.code
    old_values = asset.to_dict()

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

    # Audit log
    audit_logger.log(
        user_id=current_user_id,
        username=current_user.username,
        action='delete',
        entity_type='asset',
        entity_id=id,
        old_values=old_values,
        new_values={},
        details=f"Deleted asset {asset_code}",
        ip_address=request.remote_addr
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
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    # Create sample CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['code', 'name', 'description', 'category', 'purchase_value', 'purchase_date', 'department_id', 'assigned_to_id', 'status', 'condition_notes'])

    # Write sample rows
    writer.writerow(['LAPTOP-001', 'Dell Latitude 5420', 'Business laptop with i5 processor', 'Laptop', '25000000', '2024-01-15', '1', '3', 'active', 'Good condition'])
    writer.writerow(['DESK-001', 'Standing Desk', 'Adjustable height desk', 'Furniture', '5000000', '2024-02-20', '2', '4', 'active', ''])

    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=assets_sample.csv'}
    )


@asset_bp.route("/upload-csv", methods=["POST"])
@jwt_required()
def upload_assets_csv():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized - admin only"}), 403

    if 'file' not in request.files:
        return jsonify({"message": "No file provided"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"message": "No file selected"}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({"message": "File must be a CSV"}), 400

    try:
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        created_assets = []
        errors = []

        for row_num, row in enumerate(csv_reader, start=2):  # start=2 because row 1 is header
            try:
                # Validate required fields
                if not row.get('code') or not row.get('name') or not row.get('department_id'):
                    errors.append(f"Row {row_num}: Missing required fields (code, name, department_id)")
                    continue

                # Check if asset already exists
                if Asset.query.filter_by(code=row['code']).first():
                    errors.append(f"Row {row_num}: Asset code '{row['code']}' already exists")
                    continue

                # Parse status
                status_str = row.get('status', 'active').lower()
                if status_str == 'damaged':
                    status = AssetStatus.DAMAGED
                elif status_str == 'disposed':
                    status = AssetStatus.DISPOSED
                else:
                    status = AssetStatus.ACTIVE

                # Parse purchase_date
                purchase_date = None
                if row.get('purchase_date'):
                    try:
                        purchase_date = datetime.strptime(row['purchase_date'], "%Y-%m-%d").date()
                    except ValueError:
                        errors.append(f"Row {row_num}: Invalid purchase_date format (use YYYY-MM-DD)")
                        continue

                # Validate department exists
                department_id = int(row['department_id'])
                from models import Department
                if not Department.query.get(department_id):
                    errors.append(f"Row {row_num}: Department ID {department_id} not found")
                    continue

                # Validate assigned_to_id if provided
                assigned_to_id = None
                if row.get('assigned_to_id'):
                    assigned_to_id = int(row['assigned_to_id'])
                    assigned_user = User.query.get(assigned_to_id)
                    if not assigned_user:
                        errors.append(f"Row {row_num}: User ID {assigned_to_id} not found")
                        continue

                    # Validate user belongs to department
                    user_dept_ids = [dept.id for dept in assigned_user.departments]
                    if department_id not in user_dept_ids:
                        errors.append(f"Row {row_num}: User {assigned_to_id} does not belong to department {department_id}")
                        continue

                # Create asset
                asset = Asset(
                    code=row['code'],
                    name=row['name'],
                    description=row.get('description'),
                    category=row.get('category'),
                    purchase_value=float(row['purchase_value']) if row.get('purchase_value') else None,
                    purchase_date=purchase_date,
                    department_id=department_id,
                    assigned_to_id=assigned_to_id,
                    status=status,
                    condition_notes=row.get('condition_notes')
                )

                db.session.add(asset)
                db.session.flush()  # Get asset.id

                # Create transfer record if assigned to a user
                if assigned_to_id:
                    transfer = AssetTransfer(
                        asset_id=asset.id,
                        to_department_id=department_id,
                        assigned_to_id=assigned_to_id,
                        transferred_by=current_user_id,
                        notes=f"Initial assignment via CSV upload"
                    )
                    db.session.add(transfer)

                # Log activity
                activity = UserActivity(
                    user_id=current_user_id,
                    username=current_user.username,
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

        return jsonify({
            "message": f"CSV processed successfully",
            "created": len(created_assets),
            "created_assets": created_assets,
            "errors": errors
        }), 200 if not errors else 207  # 207 = Multi-Status

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error processing CSV: {str(e)}"}), 400
