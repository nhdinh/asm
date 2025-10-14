from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from config import Config
from ad_authenticator import ActiveDirectoryAuthenticator
from token_manager import TokenManager
import logging
from logging.handlers import RotatingFileHandler
import os

db = SQLAlchemy()
jwt = JWTManager()


def create_app():
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configure logging
    if not os.path.exists("logs"):
        os.makedirs("logs")

    file_handler = RotatingFileHandler(
        "logs/auth_service.log", maxBytes=10485760, backupCount=10  # 10MB
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Authentication Service startup")

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"])

    # Initialize Active Directory authenticator
    app.ad_authenticator = ActiveDirectoryAuthenticator(app.config)

    # Initialize Token Manager
    app.token_manager = TokenManager(app.config)

    # Create database tables
    with app.app_context():
        db.create_all()
        app.logger.info("Database tables created/verified")

    # JWT callbacks
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        """Check if token has been revoked"""
        jti = jwt_payload["jti"]
        token_type = jwt_payload.get("type", "access")
        return not app.token_manager.verify_token(jti, token_type)

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        """Handle expired token"""
        return jsonify({"message": "Token has expired", "error": "token_expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        """Handle invalid token"""
        return jsonify({"message": "Invalid token", "error": "invalid_token"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        """Handle missing token"""
        return (
            jsonify(
                {
                    "message": "Authorization token is missing",
                    "error": "authorization_required",
                }
            ),
            401,
        )

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        """Handle revoked token"""
        return (
            jsonify({"message": "Token has been revoked", "error": "token_revoked"}),
            401,
        )

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"message": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal server error: {error}")
        db.session.rollback()
        return jsonify({"message": "Internal server error"}), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        app.logger.error(f"Unhandled exception: {error}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred"}), 500

    # Register blueprints
    from routes import auth_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    # Root endpoint
    @app.route("/")
    def index():
        return (
            jsonify(
                {
                    "service": "Authentication Service",
                    "version": "1.0.0",
                    "status": "running",
                }
            ),
            200,
        )

    # Initialize event consumer for user events from backend
    try:
        from user_event_consumer import init_user_event_consumer
        init_user_event_consumer(app)
        app.logger.info("User event consumer initialized")
    except Exception as e:
        app.logger.error(f"Failed to initialize user event consumer: {str(e)}")

    return app
