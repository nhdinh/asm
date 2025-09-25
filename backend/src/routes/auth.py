from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User, UserRole, UserActivity

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        access_token = create_access_token(identity=user.id)

        # Log activity
        activity = UserActivity(
            user_id=user.id, action="login", details="User logged in"
        )
        db.session.add(activity)
        db.session.commit()

        return jsonify({"access_token": access_token, "user": user.to_dict()}), 200

    return jsonify({"message": "Invalid credentials"}), 401


@auth_bp.route("/register", methods=["POST"])
@jwt_required()
def register():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    # Check if user exists
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"message": "Username already exists"}), 400

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"message": "Email already exists"}), 400

    user = User(
        username=data["username"],
        email=data["email"],
        role=UserRole[data["role"].upper()],
        department_id=data.get("department_id"),
    )
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()

    # Log activity
    activity = UserActivity(
        user_id=current_user_id,
        action="create_user",
        entity_type="user",
        entity_id=user.id,
        details=f"Created user {user.username}",
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify(user.to_dict()), 201


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return jsonify(user.to_dict())
