from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from app import db
from models import (
    EquipmentRequest,
    EquipmentRequestItem,
    EquipmentRequestStatus,
    Profile,
    Department,
    ProfileDepartment,
    AssetCategory,
    UserActivity,
    ActivityStatus,
)
from audit_logger import audit_logger

bp = Blueprint("equipment_requests", __name__, url_prefix="/api/equipment-requests")


def generate_request_code():
    """Generate unique request code: REQ-YYYYMMDD-XXXX"""
    from datetime import datetime

    today = datetime.now().strftime("%Y%m%d")
    # Find the last request code for today
    last_request = (
        EquipmentRequest.query.filter(
            EquipmentRequest.request_code.like(f"REQ-{today}-%")
        )
        .order_by(EquipmentRequest.request_code.desc())
        .first()
    )

    if last_request:
        # Extract sequence number and increment
        last_seq = int(last_request.request_code.split("-")[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1

    return f"REQ-{today}-{new_seq:04d}"


@bp.route("", methods=["GET"])
@jwt_required()
def list_requests():
    """List equipment requests based on user role"""
    current_user_username = get_jwt_identity()
    current_user = Profile.query.filter_by(username=current_user_username).first()

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    # Get filter parameters
    status_filter = request.args.get("status")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    # Base query
    query = EquipmentRequest.query_all()

    # Apply filters based on user role
    if current_user.role.value == "ADMIN":
        # ADMIN sees all requests
        pass
    else:
        # Regular users see:
        # 1. Their own requests
        # 2. Requests from their department if they are manager
        user_dept_ids = [d.id for d in current_user.departments]
        is_manager_in_depts = [
            assoc.department_id
            for assoc in current_user.department_associations
            if assoc.is_manager
        ]

        if is_manager_in_depts:
            # User is manager: see own requests + department requests
            query = query.filter(
                db.or_(
                    EquipmentRequest.requester_id == current_user.id,
                    EquipmentRequest.department_id.in_(is_manager_in_depts),
                )
            )
        else:
            # Regular user: see only own requests
            query = query.filter(EquipmentRequest.requester_id == current_user.id)

    # Apply status filter
    if status_filter:
        query = query.filter(EquipmentRequest.status == status_filter)

    # Order by created date desc
    query = query.order_by(EquipmentRequest.created_at.desc())

    # Paginate
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "requests": [req.to_dict(include_items=False) for req in paginated.items],
            "total": paginated.total,
            "page": page,
            "per_page": per_page,
            "pages": paginated.pages,
        }
    )


@bp.route("/<int:request_id>", methods=["GET"])
@jwt_required()
def get_request(request_id):
    """Get equipment request details"""
    current_user_username = get_jwt_identity()
    current_user = Profile.query.filter_by(username=current_user_username).first()

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    eq_request = EquipmentRequest.query.get_or_404(request_id)

    # Check permission
    if current_user.role.value != "ADMIN":
        # Check if user is requester or manager of department
        is_manager_of_dept = any(
            assoc.department_id == eq_request.department_id and assoc.is_manager
            for assoc in current_user.department_associations
        )

        if (
            eq_request.requester_id != current_user.id
            and not is_manager_of_dept
        ):
            return jsonify({"error": "Permission denied"}), 403

    return jsonify(eq_request.to_dict(include_items=True))


@bp.route("", methods=["POST"])
@jwt_required()
def create_request():
    """Create new equipment request"""
    current_user_username = get_jwt_identity()
    current_user = Profile.query.filter_by(username=current_user_username).first()

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    data = request.json

    # Validate required fields
    required_fields = ["department_id", "request_title", "justification", "items"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    # Validate department
    department = Department.query.get(data["department_id"])
    if not department:
        return jsonify({"error": "Department not found"}), 404

    # Check if user belongs to this department
    user_dept_ids = [d.id for d in current_user.departments]
    if data["department_id"] not in user_dept_ids:
        return jsonify({"error": "You don't belong to this department"}), 403

    # Create request
    eq_request = EquipmentRequest(
        request_code=generate_request_code(),
        requester_id=current_user.id,
        department_id=data["department_id"],
        request_title=data["request_title"],
        justification=data["justification"],
        urgency_level=data.get("urgency_level", "normal"),
        expected_date=(
            datetime.fromisoformat(data["expected_date"])
            if data.get("expected_date")
            else None
        ),
        status=EquipmentRequestStatus.DRAFT,
    )

    db.session.add(eq_request)
    db.session.flush()  # Get the ID

    # Add items
    for item_data in data["items"]:
        item = EquipmentRequestItem(
            request_id=eq_request.id,
            equipment_name=item_data["equipment_name"],
            category_id=item_data.get("category_id"),
            specifications=item_data.get("specifications"),
            quantity=item_data.get("quantity", 1),
            estimated_price=item_data.get("estimated_price"),
            notes=item_data.get("notes"),
        )
        db.session.add(item)

    # Log activity
    activity = UserActivity(
        user_id=current_user.id,
        username=current_user.username,
        action="CREATE_EQUIPMENT_REQUEST",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        details=f"Created equipment request {eq_request.request_code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action="create",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        new_values=eq_request.to_dict(include_items=True),
        details=f"Created equipment request {eq_request.request_code}",
        ip_address=request.remote_addr,
    )

    return jsonify(eq_request.to_dict(include_items=True)), 201


@bp.route("/<int:request_id>", methods=["PUT"])
@jwt_required()
def update_request(request_id):
    """Update equipment request (only in DRAFT status)"""
    current_user_username = get_jwt_identity()
    current_user = Profile.query.filter_by(username=current_user_username).first()

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    eq_request = EquipmentRequest.query.get_or_404(request_id)

    # Check permission - only requester can update
    if eq_request.requester_id != current_user.id:
        return jsonify({"error": "Only requester can update request"}), 403

    # Can only update if in DRAFT status
    if eq_request.status != EquipmentRequestStatus.DRAFT:
        return jsonify({"error": "Can only update request in DRAFT status"}), 400

    data = request.json

    # Update fields
    if "request_title" in data:
        eq_request.request_title = data["request_title"]
    if "justification" in data:
        eq_request.justification = data["justification"]
    if "urgency_level" in data:
        eq_request.urgency_level = data["urgency_level"]
    if "expected_date" in data:
        eq_request.expected_date = (
            datetime.fromisoformat(data["expected_date"])
            if data["expected_date"]
            else None
        )

    # Update items if provided
    if "items" in data:
        # Delete existing items
        EquipmentRequestItem.query.filter_by(request_id=eq_request.id).delete()

        # Add new items
        for item_data in data["items"]:
            item = EquipmentRequestItem(
                request_id=eq_request.id,
                equipment_name=item_data["equipment_name"],
                category_id=item_data.get("category_id"),
                specifications=item_data.get("specifications"),
                quantity=item_data.get("quantity", 1),
                estimated_price=item_data.get("estimated_price"),
                notes=item_data.get("notes"),
            )
            db.session.add(item)

    # Log activity
    activity = UserActivity(
        user_id=current_user.id,
        username=current_user.username,
        action="UPDATE_EQUIPMENT_REQUEST",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        details=f"Updated equipment request {eq_request.request_code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action="update",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        new_values=eq_request.to_dict(include_items=True),
        details=f"Updated equipment request {eq_request.request_code}",
        ip_address=request.remote_addr,
    )

    return jsonify(eq_request.to_dict(include_items=True))


@bp.route("/<int:request_id>/sign", methods=["POST"])
@jwt_required()
def sign_request(request_id):
    """Sign equipment request (requester signature)"""
    current_user_username = get_jwt_identity()
    current_user = Profile.query.filter_by(username=current_user_username).first()

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    eq_request = EquipmentRequest.query.get_or_404(request_id)

    # Check permission - only requester can sign
    if eq_request.requester_id != current_user.id:
        return jsonify({"error": "Only requester can sign request"}), 403

    # Can only sign if in DRAFT status
    if eq_request.status != EquipmentRequestStatus.DRAFT:
        return jsonify({"error": "Request already signed or processed"}), 400

    data = request.json
    signature_data = data.get("signature")

    if not signature_data:
        return jsonify({"error": "Signature data required"}), 400

    # Store signature (base64 encoded image or signature data)
    eq_request.requester_signature = signature_data
    eq_request.requester_signed_at = datetime.utcnow()
    eq_request.status = EquipmentRequestStatus.PENDING_MANAGER_APPROVAL

    # Log activity
    activity = UserActivity(
        user_id=current_user.id,
        username=current_user.username,
        action="SIGN_EQUIPMENT_REQUEST",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        details=f"Signed equipment request {eq_request.request_code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action="sign",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        new_values={"status": eq_request.status.value},
        details=f"Signed equipment request {eq_request.request_code}",
        ip_address=request.remote_addr,
    )

    return jsonify(eq_request.to_dict(include_items=True))


@bp.route("/<int:request_id>/approve", methods=["POST"])
@jwt_required()
def approve_request(request_id):
    """Approve equipment request (manager approval)"""
    current_user_username = get_jwt_identity()
    current_user = Profile.query.filter_by(username=current_user_username).first()

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    eq_request = EquipmentRequest.query.get_or_404(request_id)

    # Check if user is manager of the department
    is_manager_of_dept = any(
        assoc.department_id == eq_request.department_id and assoc.is_manager
        for assoc in current_user.department_associations
    )

    if not is_manager_of_dept and current_user.role.value != "ADMIN":
        return jsonify({"error": "Only department manager can approve"}), 403

    # Can only approve if in PENDING_MANAGER_APPROVAL status
    if eq_request.status != EquipmentRequestStatus.PENDING_MANAGER_APPROVAL:
        return jsonify({"error": "Request not ready for approval"}), 400

    data = request.json
    signature_data = data.get("signature")
    manager_notes = data.get("notes", "")

    if not signature_data:
        return jsonify({"error": "Manager signature required"}), 400

    # Update request
    eq_request.manager_id = current_user.id
    eq_request.manager_signature = signature_data
    eq_request.manager_signed_at = datetime.utcnow()
    eq_request.manager_notes = manager_notes
    eq_request.status = EquipmentRequestStatus.APPROVED

    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user.id,
        username=current_user.username,
        action="APPROVE_EQUIPMENT_REQUEST",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        details=f"Approved equipment request {eq_request.request_code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action=activity.action.lower().replace("_equipment_request", ""),
        entity_type="equipment_request",
        entity_id=eq_request.id,
        new_values=eq_request.to_dict(include_items=True),
        details=activity.details,
        ip_address=request.remote_addr,
    )

    return jsonify(eq_request.to_dict(include_items=True))


@bp.route("/<int:request_id>/reject", methods=["POST"])
@jwt_required()
def reject_request(request_id):
    """Reject equipment request (manager rejection)"""
    current_user_username = get_jwt_identity()
    current_user = Profile.query.filter_by(username=current_user_username).first()

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    eq_request = EquipmentRequest.query.get_or_404(request_id)

    # Check if user is manager of the department
    is_manager_of_dept = any(
        assoc.department_id == eq_request.department_id and assoc.is_manager
        for assoc in current_user.department_associations
    )

    if not is_manager_of_dept and current_user.role.value != "ADMIN":
        return jsonify({"error": "Only department manager can reject"}), 403

    # Can only reject if in PENDING_MANAGER_APPROVAL status
    if eq_request.status != EquipmentRequestStatus.PENDING_MANAGER_APPROVAL:
        return jsonify({"error": "Request not ready for rejection"}), 400

    data = request.json
    manager_notes = data.get("notes", "")

    if not manager_notes:
        return jsonify({"error": "Rejection reason required"}), 400

    # Update request
    eq_request.manager_id = current_user.id
    eq_request.manager_notes = manager_notes
    eq_request.status = EquipmentRequestStatus.REJECTED

    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user.id,
        username=current_user.username,
        action="REJECT_EQUIPMENT_REQUEST",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        details=f"Rejected equipment request {eq_request.request_code}: {manager_notes}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action=activity.action.lower().replace("_equipment_request", ""),
        entity_type="equipment_request",
        entity_id=eq_request.id,
        new_values=eq_request.to_dict(include_items=True),
        details=activity.details,
        ip_address=request.remote_addr,
    )

    return jsonify(eq_request.to_dict(include_items=True))


@bp.route("/<int:request_id>/process", methods=["POST"])
@jwt_required()
def process_request(request_id):
    """Process equipment request (HR processing)"""
    current_user_username = get_jwt_identity()
    current_user = Profile.query.filter_by(username=current_user_username).first()

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    # Only ADMIN can process
    if current_user.role.value != "ADMIN":
        return jsonify({"error": "Only HR/Admin can process requests"}), 403

    eq_request = EquipmentRequest.query.get_or_404(request_id)

    # Can only process if APPROVED
    if eq_request.status != EquipmentRequestStatus.APPROVED:
        return jsonify({"error": "Request must be approved first"}), 400

    data = request.json
    hr_notes = data.get("notes", "")

    # Update request
    eq_request.hr_processor_id = current_user.id
    eq_request.hr_notes = hr_notes
    eq_request.hr_processed_at = datetime.utcnow()
    eq_request.status = EquipmentRequestStatus.COMPLETED

    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user.id,
        username=current_user.username,
        action="PROCESS_EQUIPMENT_REQUEST",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        details=f"Processed equipment request {eq_request.request_code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action=activity.action.lower().replace("_equipment_request", ""),
        entity_type="equipment_request",
        entity_id=eq_request.id,
        new_values=eq_request.to_dict(include_items=True),
        details=activity.details,
        ip_address=request.remote_addr,
    )

    return jsonify(eq_request.to_dict(include_items=True))


@bp.route("/<int:request_id>", methods=["DELETE"])
@jwt_required()
def delete_request(request_id):
    """Soft delete equipment request (only DRAFT or own requests)"""
    current_user_username = get_jwt_identity()
    current_user = Profile.query.filter_by(username=current_user_username).first()

    if not current_user:
        return jsonify({"error": "User not found"}), 404

    eq_request = EquipmentRequest.query.get_or_404(request_id)

    # Check permission
    if eq_request.requester_id != current_user.id and current_user.role.value != "ADMIN":
        return jsonify({"error": "Permission denied"}), 403

    # Can only delete if in DRAFT status
    if eq_request.status != EquipmentRequestStatus.DRAFT:
        return jsonify({"error": "Can only delete request in DRAFT status"}), 400

    # Soft delete
    eq_request.deleted_at = datetime.utcnow()
    eq_request.status = EquipmentRequestStatus.CANCELLED

    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user.id,
        username=current_user.username,
        action="DELETE_EQUIPMENT_REQUEST",
        entity_type="equipment_request",
        entity_id=eq_request.id,
        details=f"Deleted equipment request {eq_request.request_code}",
        status=ActivityStatus.SUCCESS,
    )
    db.session.add(activity)
    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user.id,
        username=current_user.username,
        action=activity.action.lower().replace("_equipment_request", ""),
        entity_type="equipment_request",
        entity_id=eq_request.id,
        new_values=eq_request.to_dict(include_items=True),
        details=activity.details,
        ip_address=request.remote_addr,
    )

    return jsonify({"message": "Request deleted successfully"})
