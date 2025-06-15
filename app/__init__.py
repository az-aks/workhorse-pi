"""
Flask application factory and configuration
"""

import logging
from flask import Flask
from flask_socketio import SocketIO

from .routes import main_bp
from .socketio_events import setup_socketio_events


def create_app(config, trading_bot):
    """Create and configure Flask application."""
    app = Flask(__name__)
    
    # Flask configuration
    app.config['SECRET_KEY'] = 'workhorse-secret-key-change-in-production'
    app.config['DEBUG'] = config.get('web', {}).get('debug', False)
    
    # Initialize SocketIO
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False
    )
    
    # Store references for use in routes
    app.config['TRADING_BOT'] = trading_bot
    app.config['CONFIG'] = config
    app.config['SOCKETIO'] = socketio
    
    # Register blueprints
    app.register_blueprint(main_bp)
    
    # Setup SocketIO events
    setup_socketio_events(socketio, trading_bot)
    
    # Setup logging for Flask
    if not app.debug:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    return app
