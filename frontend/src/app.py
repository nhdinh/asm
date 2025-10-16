import logging
from logging.handlers import RotatingFileHandler
import os
from flask import Flask
from dotenv import load_dotenv


load_dotenv()


# Backend API URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://backend:5000/api")


def create_app():
    template_folder = os.getenv("TEMPLATE_PATH", "/app/templates")

    app = Flask(__name__, template_folder=template_folder)
    app.secret_key = os.getenv("FRONTEND_APP_SECRET", "frontend-secret-key")
    app.config["API_BASE_URL"] = API_BASE_URL

    log_path = "../logs/"
    log_file = "frontend.log"

    # Setup logging
    if not app.debug:
        if not os.path.exists(log_path):
            os.mkdir(log_path)

        file_handler = RotatingFileHandler(
            os.path.join(log_path, log_file), maxBytes=10240, backupCount=10
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("Asset Management Frontend startup")

    return app
