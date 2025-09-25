from enum import Enum
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify
from datetime import datetime, timedelta
import os
import logging
from dotenv import load_dotenv
from common import app

load_dotenv()


# Register blueprints
from routes.auth import auth_bp
from routes.departments import dept_bp
from routes.assets import asset_bp
from routes.reports import report_bp

app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(dept_bp, url_prefix="/api/departments")
app.register_blueprint(asset_bp, url_prefix="/api/assets")
app.register_blueprint(report_bp, url_prefix="/api/reports")


# Health check endpoint
@app.route("/api/health")
def health_check():
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
        }
    )


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)

    # Run the application
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"

    app.run(debug=debug, host="0.0.0.0", port=port)
