from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate
from datetime import timedelta
import os
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL1', 
        'postgresql://asmdbu:pasdfmlkasdf@postgres:5432/asset_man')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.departments import dept_bp
    from routes.assets import asset_bp
    from routes.reports import report_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(dept_bp, url_prefix='/api/departments')
    app.register_blueprint(asset_bp, url_prefix='/api/assets')
    app.register_blueprint(report_bp, url_prefix='/api/reports')
    
    with app.app_context():
        db.create_all()
    
    return app
