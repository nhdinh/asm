import logging
from logging.handlers import RotatingFileHandler
import os
from flask import Flask
from dotenv import load_dotenv


load_dotenv()

def create_app():
    template_folder = os.getenv("TEMPLATE_PATH", "/app/templates")

    app = Flask(__name__, template_folder=template_folder)
    app.secret_key = os.getenv("SECRET_KEY", "frontend-secret-key")

    # Setup logging
    if not app.debug:
        if not os.path.exists("logs"):
            os.mkdir("logs")
        file_handler = RotatingFileHandler(
            "logs/frontend.log", maxBytes=10240, backupCount=10
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