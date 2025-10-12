from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Profile, ProfileRole, EmailConfig
from audit_logger import audit_logger

email_settings_bp = Blueprint("email_settings", __name__)


@email_settings_bp.route("", methods=["GET"])
@jwt_required()
def get_email_config():
    """Get email configuration (admin only)"""
    current_profile_id = get_jwt_identity()
    current_profile = Profile.query.get(current_profile_id)

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    config = EmailConfig.query.first()
    if not config:
        # Return default empty config
        return jsonify(
            {
                "provider": "smtp",
                "smtp_host": "",
                "smtp_port": 587,
                "smtp_username": "",
                "from_email": "",
                "from_name": "Asset Management System",
                "use_tls": True,
                "use_ssl": False,
                "enabled": False,
                "send_welcome_email": True,
                "has_smtp_password": False,
                "has_sendgrid_api_key": False,
            }
        )

    return jsonify(config.to_dict(include_secrets=False))


@email_settings_bp.route("", methods=["POST", "PUT"])
@jwt_required()
def update_email_config():
    """Create or update email configuration (admin only)"""
    current_profile_id = get_jwt_identity()
    current_profile = Profile.query.get(current_profile_id)

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    # Get provider (default to smtp for backward compatibility)
    provider = data.get("provider", "smtp")

    # Validate required fields based on provider
    if not data.get("from_email"):
        return jsonify({"message": "From email is required"}), 400

    if provider == "sendgrid":
        # SendGrid validation - no existing config check needed for new configs
        pass
    else:
        # SMTP validation
        if not data.get("smtp_host"):
            return jsonify({"message": "SMTP host is required"}), 400
        if not data.get("smtp_username"):
            return jsonify({"message": "SMTP username is required"}), 400

    config = EmailConfig.query.first()

    if not config:
        # Create new config
        config = EmailConfig(
            provider=provider,
            smtp_host=data.get("smtp_host", ""),
            smtp_port=data.get("smtp_port", 587),
            smtp_username=data.get("smtp_username", ""),
            smtp_password=data.get("smtp_password", ""),
            sendgrid_api_key=data.get("sendgrid_api_key", ""),
            from_email=data["from_email"],
            from_name=data.get("from_name", "Asset Management System"),
            use_tls=data.get("use_tls", True),
            use_ssl=data.get("use_ssl", False),
            enabled=data.get("enabled", False),
            send_welcome_email=data.get("send_welcome_email", True),
            updated_by=current_profile_id,
        )
        db.session.add(config)
        action = "create"
    else:
        # Update existing config
        old_values = config.to_dict()
        config.provider = provider
        config.smtp_host = data.get("smtp_host", "")
        config.smtp_port = data.get("smtp_port", 587)
        config.smtp_username = data.get("smtp_username", "")

        # Only update password if provided
        if data.get("smtp_password"):
            config.smtp_password = data["smtp_password"]

        # Only update SendGrid API key if provided
        if data.get("sendgrid_api_key"):
            config.sendgrid_api_key = data["sendgrid_api_key"]

        config.from_email = data["from_email"]
        config.from_name = data.get("from_name", "Asset Management System")
        config.use_tls = data.get("use_tls", True)
        config.use_ssl = data.get("use_ssl", False)
        config.enabled = data.get("enabled", False)
        config.send_welcome_email = data.get("send_welcome_email", True)
        config.updated_by = current_profile_id
        action = "update"

    db.session.commit()

    # Audit log
    audit_logger.log(
        user_id=current_profile_id,
        username=current_profile.username,
        action=action,
        entity_type="email_config",
        entity_id=config.id,
        old_values=old_values if action == "update" else None,
        new_values=config.to_dict(),
        details=f"{'Created' if action == 'create' else 'Updated'} email configuration",
        ip_address=request.remote_addr,
    )

    return jsonify(config.to_dict(include_secrets=False))


@email_settings_bp.route("/test", methods=["POST"])
@jwt_required()
def test_email_config():
    """Test email configuration by sending a test email"""
    current_profile_id = get_jwt_identity()
    current_profile = Profile.query.get(current_profile_id)

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    config = EmailConfig.query.first()
    if not config or not config.enabled:
        return jsonify({"message": "Email configuration not found or not enabled"}), 400

    # Import email utility
    from email_utils import send_test_email

    try:
        result = send_test_email(config, current_profile.email)
        if result:
            # Audit log
            audit_logger.log(
                user_id=current_profile_id,
                username=current_profile.username,
                action="test_email",
                entity_type="email_config",
                entity_id=config.id,
                details=f"Test email sent successfully to {current_profile.email}",
                ip_address=request.remote_addr,
            )
            return jsonify(
                {
                    "message": "Test email sent successfully",
                    "sent_to": current_profile.email,
                }
            )
        else:
            return jsonify({"message": "Failed to send test email"}), 500
    except Exception as e:
        # Audit log
        audit_logger.log(
            user_id=current_profile_id,
            username=current_profile.username,
            action="test_email_failed",
            entity_type="email_config",
            entity_id=config.id,
            details=f"Test email failed: {str(e)}",
            ip_address=request.remote_addr,
        )
        return jsonify({"message": f"Failed to send test email: {str(e)}"}), 500
