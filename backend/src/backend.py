import os
from app import create_app
from scheduler import start_scheduler, stop_scheduler
import atexit

if __name__ == "__main__":
    app = create_app()
    port = os.getenv("APP_PORT", 5000)
    debug = os.getenv("FLASK_ENV") == "development"

    # Start background scheduler for audit log archival
    start_scheduler()

    # Ensure scheduler stops when app exits
    atexit.register(stop_scheduler)

    app.run(host="0.0.0.0", port=port, debug=debug)
