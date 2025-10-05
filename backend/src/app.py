from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate
from datetime import timedelta
import os
from dotenv import load_dotenv, set_key
import logging

ENV_PATH = "./.env"

# load dotenv
load_dotenv(dotenv_path=ENV_PATH)

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()

# Import audit logger
from audit_logger import audit_logger

db_user = None
db_password = None
db_host = None
db_name = None

with open(os.environ["POSTGRES_USER_FILE"], "r") as f:
    db_user = f.read()

with open(os.environ["POSTGRES_PASSWORD_FILE"], "r") as f:
    db_password = f.read()

db_host = os.getenv("POSTGRES_HOST", "postgres")
db_name = os.getenv("POSTGRES_DB", "asset_man")


if db_user is None or db_password is None:
    exit(10)


def save_env(key: str, val: str):
    set_key(dotenv_path=ENV_PATH, key_to_set=key, value_to_set=val)

    load_dotenv()


def create_app():
    app = Flask(__name__)

    # Configuration
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
    app.config["JWT_VERIFY_SUB"] = False

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    audit_logger.init_app(app)

    CORS(app)

    # Setup logging
    if not app.debug:
        if not os.path.exists("logs"):
            os.mkdir("logs")
        file_handler = RotatingFileHandler(
            "logs/backend.log", maxBytes=10240, backupCount=10
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("Asset Management API startup")

    # Register blueprints
    from routes.auth import auth_bp
    from routes.departments import dept_bp
    from routes.assets import asset_bp
    from routes.reports import report_bp
    from routes.users import users_bp
    from routes.my_assets import my_assets_bp
    from routes.audit_logs import audit_logs_bp
    from routes.settings import settings_bp
    from routes.categories import category_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(dept_bp, url_prefix="/api/departments")
    app.register_blueprint(asset_bp, url_prefix="/api/assets")
    app.register_blueprint(report_bp, url_prefix="/api/reports")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(my_assets_bp, url_prefix="/api/my-assets")
    app.register_blueprint(audit_logs_bp, url_prefix="/api/audit-logs")
    app.register_blueprint(settings_bp, url_prefix="/api/settings")
    app.register_blueprint(category_bp, url_prefix="/api/categories")

    # Health check endpoint
    @app.route("/api/health")
    def health_check():
        return {"status": "healthy", "service": "asset-management-api"}, 200

    with app.app_context():
        db.create_all()

    return app
