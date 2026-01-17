from flask import Flask
from flask_session import Session
from flask_compress import Compress
import os
import logging
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get('KEY', 'dev_key')
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600
    app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
    
    if not os.path.exists(app.config['SESSION_FILE_DIR']):
        os.makedirs(app.config['SESSION_FILE_DIR'])

    # Initialize extensions
    Session(app)
    Compress(app)
    
    # Logging
    logging.basicConfig(level=logging.DEBUG)

    # Register Blueprints
    from app.routes.api import api_bp
    from app.routes.views import views_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)
    app.register_blueprint(admin_bp)

    return app
