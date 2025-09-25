from datetime import timedelta
import logging
from logging.handlers import RotatingFileHandler
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate


app = Flask(__name__)
# app.config.from_object(BasicConfig)
basedir = os.path.abspath(os.path.dirname(__file__))
# Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "postgresql://asmdbu:p0stgfpass!@postgres:5432/asset_man"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your-secret-key")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)

# Enable CORS for all origins
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


db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
