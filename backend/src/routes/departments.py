from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Department, User, UserRole, UserActivity

dept_bp = Blueprint("departments", __name__)


@dept_bp.route("", methods=["GET"])
@jwt_required()
def get_departments():
    departments = Department.query.all()
    return jsonify([dept.to_dict() for dept in departments])


@dept_bp.route("", methods=["POST"])
@jwt_required()
def create_department():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    if Department.query.filter_by(name=data["name"]).first():
        return jsonify({"message": "Department already exists"}), 400

    dept = Department(
        name=data["name"],
        description=data.get("description"),
        user_count=0,
        asset_count=0,
        total_value=0,
    )

    db.session.add(dept)
    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="create_department",
        entity_type="department",
        entity_id=dept.id,
        details=f"Created department {dept.name}",
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify(dept.to_dict()), 201


@dept_bp.route("/<int:id>", methods=["PUT"])
@jwt_required()
def update_department(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    dept = Department.query.get_or_404(id)
    data = request.json

    dept.name = data.get("name", dept.name)
    dept.description = data.get("description", dept.description)

    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="update_department",
        entity_type="department",
        entity_id=dept.id,
        details=f"Updated department {dept.name}",
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify(dept.to_dict())


@dept_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_department(id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    dept = Department.query.get_or_404(id)

    if dept.assets.count() > 0:
        return jsonify({"message": "Cannot delete department with assets"}), 400

    db.session.delete(dept)
    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="delete_department",
        entity_type="department",
        entity_id=id,
        details=f"Deleted department {dept.name}",
    )
    db.session.add(activity)
    db.session.commit()

    return "", 204
