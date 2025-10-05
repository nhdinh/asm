from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, UserRole, SystemSetting
from audit_logger import audit_logger

settings_bp = Blueprint("settings", __name__)


# Default settings
DEFAULT_SETTINGS = {
    "login_fail_limit": {
        "value": "5",
        "description": "Số lần đăng nhập thất bại trước khi bị khóa",
        "data_type": "int"
    },
    "login_block_minutes": {
        "value": "5",
        "description": "Thời gian khóa (phút) sau khi đăng nhập thất bại quá số lần",
        "data_type": "int"
    },
    "password_min_length": {
        "value": "8",
        "description": "Độ dài tối thiểu của mật khẩu",
        "data_type": "int"
    },
    "password_require_uppercase": {
        "value": "true",
        "description": "Yêu cầu chữ hoa trong mật khẩu",
        "data_type": "bool"
    },
    "password_require_lowercase": {
        "value": "true",
        "description": "Yêu cầu chữ thường trong mật khẩu",
        "data_type": "bool"
    },
    "password_require_digit": {
        "value": "true",
        "description": "Yêu cầu chữ số trong mật khẩu",
        "data_type": "bool"
    },
    "password_require_special": {
        "value": "true",
        "description": "Yêu cầu ký tự đặc biệt trong mật khẩu",
        "data_type": "bool"
    },
    "default_items_per_page": {
        "value": "20",
        "description": "Số mục hiển thị mỗi trang (mặc định toàn hệ thống)",
        "data_type": "int"
    },
    "audit_archive_days": {
        "value": "30",
        "description": "Số ngày sau đó hệ thống sẽ lưu audit log xuống file",
        "data_type": "int"
    }
}


def init_default_settings():
    """Initialize default settings if not exist"""
    for key, config in DEFAULT_SETTINGS.items():
        existing = SystemSetting.query.filter_by(key=key).first()
        if not existing:
            setting = SystemSetting(
                key=key,
                value=config["value"],
                description=config["description"],
                data_type=config["data_type"]
            )
            db.session.add(setting)
    db.session.commit()


@settings_bp.route("", methods=["GET"])
@jwt_required()
def get_settings():
    """Get all system settings (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    # Initialize defaults if needed
    init_default_settings()

    settings = SystemSetting.query.all()
    return jsonify([s.to_dict() for s in settings])


@settings_bp.route("/<key>", methods=["GET"])
@jwt_required()
def get_setting(key):
    """Get a specific setting"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    setting = SystemSetting.query.filter_by(key=key).first()
    if not setting:
        # Return default if exists
        if key in DEFAULT_SETTINGS:
            return jsonify({
                "key": key,
                "value": DEFAULT_SETTINGS[key]["value"],
                "description": DEFAULT_SETTINGS[key]["description"],
                "data_type": DEFAULT_SETTINGS[key]["data_type"]
            })
        return jsonify({"message": "Setting not found"}), 404

    return jsonify(setting.to_dict())


@settings_bp.route("/<key>", methods=["PUT"])
@jwt_required()
def update_setting(key):
    """Update a setting"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json
    new_value = data.get("value")

    if new_value is None:
        return jsonify({"message": "Value is required"}), 400

    setting = SystemSetting.query.filter_by(key=key).first()

    if not setting:
        # Create new setting
        if key not in DEFAULT_SETTINGS:
            return jsonify({"message": "Invalid setting key"}), 400

        setting = SystemSetting(
            key=key,
            value=str(new_value),
            description=DEFAULT_SETTINGS[key]["description"],
            data_type=DEFAULT_SETTINGS[key]["data_type"],
            updated_by=current_user_id
        )
        db.session.add(setting)
        action = "create"
        old_value = None
    else:
        old_value = setting.value
        setting.value = str(new_value)
        setting.updated_by = current_user_id
        action = "update"

    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_user_id,
        username=current_user.username,
        action=action,
        entity_type='system_setting',
        entity_id=setting.id,
        old_values={"value": old_value} if old_value else None,
        new_values={"value": new_value},
        details=f"Updated system setting {key} to {new_value}",
        ip_address=request.remote_addr
    )

    return jsonify(setting.to_dict())


@settings_bp.route("/bulk", methods=["PUT"])
@jwt_required()
def update_settings_bulk():
    """Update multiple settings at once"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json
    updates = data.get("settings", {})

    if not updates:
        return jsonify({"message": "No settings provided"}), 400

    updated = []
    for key, value in updates.items():
        if key not in DEFAULT_SETTINGS:
            continue

        setting = SystemSetting.query.filter_by(key=key).first()

        if not setting:
            setting = SystemSetting(
                key=key,
                value=str(value),
                description=DEFAULT_SETTINGS[key]["description"],
                data_type=DEFAULT_SETTINGS[key]["data_type"],
                updated_by=current_user_id
            )
            db.session.add(setting)
            old_value = None
        else:
            old_value = setting.value
            setting.value = str(value)
            setting.updated_by = current_user_id

        # Audit log
        audit_logger.log(
            user_id=current_user_id,
            username=current_user.username,
            action='update',
            entity_type='system_setting',
            entity_id=setting.id if setting.id else None,
            old_values={"value": old_value} if old_value else None,
            new_values={"value": value},
            details=f"Updated system setting {key} to {value}",
            ip_address=request.remote_addr
        )

        updated.append(key)

    db.session.commit()

    return jsonify({
        "message": f"Updated {len(updated)} settings",
        "updated": updated
    })
