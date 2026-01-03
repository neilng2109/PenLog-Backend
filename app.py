import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import config

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Disable strict slashes to prevent 308 redirects
    app.url_map.strict_slashes = False
    
    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)
    
    # Configure CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:3000", 
                "http://localhost:3001", 
                "https://penlog.io",
                "https://www.penlog.io",
                "https://app.penlog.io",
                "https://6955e3e4--penlog-landing.netlify.app"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    
    # Ensure upload folder exists
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Serve uploaded files
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        from flask import send_from_directory
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.projects import projects_bp
    from routes.penetrations import penetrations_bp
    from routes.contractors import contractors_bp
    from routes.photos import photos_bp
    from routes.dashboard import dashboard_bp
    from routes.registration import registration_bp
    from routes.report import report_bp
    from routes.pdf import pdf_bp
    from routes.access import access_bp
    from routes.admin import admin_bp  # MOVE IT HERE!
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(projects_bp, url_prefix='/api/projects')
    app.register_blueprint(penetrations_bp, url_prefix='/api/penetrations')
    app.register_blueprint(contractors_bp, url_prefix='/api/contractors')
    app.register_blueprint(photos_bp, url_prefix='/api/photos')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(registration_bp, url_prefix='/api/registration')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(pdf_bp, url_prefix='/api/pdf')
    app.register_blueprint(access_bp, url_prefix='/api/access')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'PenLog API'}, 200
    
    return app