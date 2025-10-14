import os
from app import create_app

if __name__ == "__main__":
    app = create_app()
    port = os.getenv("APP_PORT", 5001)
    debug = os.getenv("FLASK_ENV") == "development"

    app.run(host="0.0.0.0", port=port, debug=debug)
