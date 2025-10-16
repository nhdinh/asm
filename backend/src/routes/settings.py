from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from routes.helpers import require_admin_role
from models import db, SystemSetting
from audit_logger import audit_logger
from settings_cache import settings_cache

settings_bp = Blueprint("settings", __name__)


# Default settings
DEFAULT_SETTINGS = {
    "login_fail_limit": {
        "value": "5",
        "description": "Số lần đăng nhập thất bại trước khi bị khóa",
        "data_type": "int",
    },
    "login_block_minutes": {
        "value": "5",
        "description": "Thời gian khóa (phút) sau khi đăng nhập thất bại quá số lần",
        "data_type": "int",
    },
    "password_min_length": {
        "value": "8",
        "description": "Độ dài tối thiểu của mật khẩu",
        "data_type": "int",
    },
    "password_require_uppercase": {
        "value": "true",
        "description": "Yêu cầu chữ hoa trong mật khẩu",
        "data_type": "bool",
    },
    "password_require_lowercase": {
        "value": "true",
        "description": "Yêu cầu chữ thường trong mật khẩu",
        "data_type": "bool",
    },
    "password_require_digit": {
        "value": "true",
        "description": "Yêu cầu chữ số trong mật khẩu",
        "data_type": "bool",
    },
    "password_require_special": {
        "value": "true",
        "description": "Yêu cầu ký tự đặc biệt trong mật khẩu",
        "data_type": "bool",
    },
    "default_items_per_page": {
        "value": "20",
        "description": "Số mục hiển thị mỗi trang (mặc định toàn hệ thống)",
        "data_type": "int",
    },
    "audit_archive_days": {
        "value": "30",
        "description": "Số ngày sau đó hệ thống sẽ lưu audit log xuống file",
        "data_type": "int",
    },
    "bad_assets_department_id": {
        "value": "1",
        "description": "Phòng ban nhận tài sản hư hỏng/thanh lý (ID phòng ban)",
        "data_type": "int",
    },
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
                data_type=config["data_type"],
            )
            db.session.add(setting)
    db.session.commit()


@settings_bp.route("", methods=["GET"])
@jwt_required()
@require_admin_role
def get_settings(**kwargs):
    """Get all system settings (admin only)"""
    # Try to get from Redis cache first
    cached_settings = settings_cache.get_all_settings()
    if cached_settings is not None:
        return jsonify(cached_settings)

    # Initialize defaults if needed
    init_default_settings()

    # Get from database
    settings = SystemSetting.query.all()
    settings_list = [s.to_dict() for s in settings]

    # Cache the results in Redis
    settings_cache.set_all_settings(settings_list)

    return jsonify(settings_list)


@settings_bp.route("/<key>", methods=["GET"])
@jwt_required()
@require_admin_role
def get_setting(key, **kwargs):
    """Get a specific setting"""
    # Try to get from Redis cache first
    cached_setting = settings_cache.get_setting(key)
    if cached_setting is not None:
        return jsonify(cached_setting)

    # Get from database
    setting = SystemSetting.query.filter_by(key=key).first()
    if not setting:
        # Return default if exists
        if key in DEFAULT_SETTINGS:
            default_data = {
                "key": key,
                "value": DEFAULT_SETTINGS[key]["value"],
                "description": DEFAULT_SETTINGS[key]["description"],
                "data_type": DEFAULT_SETTINGS[key]["data_type"],
            }
            # Cache default setting
            settings_cache.set_setting(key, default_data)
            return jsonify(default_data)
        return jsonify({"message": "Setting not found"}), 404

    setting_data = setting.to_dict()
    # Cache the setting
    settings_cache.set_setting(key, setting_data)

    return jsonify(setting_data)


@settings_bp.route("/<key>", methods=["PUT"])
@jwt_required()
@require_admin_role
def update_setting(key, **kwargs):
    """Update a setting"""
    sess_profile = kwargs.get("sess_profile")

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
            updated_by=sess_profile.id,
        )
        db.session.add(setting)
        action = "create"
        old_value = None
    else:
        old_value = setting.value
        setting.value = str(new_value)
        setting.updated_by = sess_profile.id
        action = "update"

    # Commit to database first
    db.session.commit()

    # Get updated setting data
    setting_data = setting.to_dict()

    # Update Redis cache
    settings_cache.set_setting(key, setting_data)

    # Audit log
    audit_logger.log(
        user_id=sess_profile.id,
        username=sess_profile.username,
        action=action,
        entity_type="system_setting",
        entity_id=setting.id,
        old_values={"value": old_value} if old_value else None,
        new_values={"value": new_value},
        details=f"Updated system setting {key} to {new_value}",
        ip_address=request.remote_addr,
    )

    return jsonify(setting_data)


@settings_bp.route("/bulk", methods=["PUT"])
@jwt_required()
@require_admin_role
def update_settings_bulk(**kwargs):
    """Update multiple settings at once"""
    sess_profile = kwargs.get("sess_profile")

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
                updated_by=sess_profile.id,
            )
            db.session.add(setting)
            old_value = None
        else:
            old_value = setting.value
            setting.value = str(value)
            setting.updated_by = sess_profile.id

        # Audit log
        audit_logger.log(
            user_id=sess_profile.id,
            username=sess_profile.username,
            action="update",
            entity_type="system_setting",
            entity_id=setting.id if setting.id else None,
            old_values={"value": old_value} if old_value else None,
            new_values={"value": value},
            details=f"Updated system setting {key} to {value}",
            ip_address=request.remote_addr,
        )

        updated.append(key)

    # Commit to database first
    db.session.commit()

    # Invalidate all settings cache since multiple settings changed
    settings_cache.clear_all_caches()

    return jsonify({"message": f"Updated {len(updated)} settings", "updated": updated})
