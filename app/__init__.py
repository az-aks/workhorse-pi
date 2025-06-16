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
        logger=config.get('web', {}).get('debug', False),
        engineio_logger=config.get('web', {}).get('debug', False),
        ping_timeout=30,
        ping_interval=15,
        async_mode='gevent'  # More reliable for HTTPS connections
    )
    
    # Store references for use in routes
    app.config['TRADING_BOT'] = trading_bot
    app.config['CONFIG'] = config
    app.config['SOCKETIO'] = socketio
    
    # Register blueprints
    app.register_blueprint(main_bp)
    
    # Setup SocketIO events
    setup_socketio_events(socketio, trading_bot)
    
    # Store socketio reference in trading bot for error reporting
    if hasattr(trading_bot, '__class__') and trading_bot.__class__.__name__ == 'ArbitrageBot':
        trading_bot.socketio = socketio
    
    # Setup logging for Flask
    if not app.debug:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    return app
