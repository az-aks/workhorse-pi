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
        
        # Set up callbacks for real-time updates
        def status_change_callback(status_data):
            """Callback for status changes from the bot."""
            logging.getLogger(__name__).info(f"Bot status changed, emitting update: {status_data}")
            socketio.emit('status_update', status_data)
        
        def trade_executed_callback(trade_data):
            """Callback for trade execution from the bot."""
            logging.getLogger(__name__).info(f"Trade executed, emitting update: {trade_data}")
            socketio.emit('trade_update', trade_data)
        
        def price_update_callback(price_data):
            """Callback for price updates from the bot."""
            logging.getLogger(__name__).debug(f"Price update from bot: {price_data}")
            socketio.emit('price_update', price_data)
        
        # Register callbacks with the trading bot
        trading_bot.set_callbacks({
            'status_change': status_change_callback,
            'trade_executed': trade_executed_callback,
            'price_update': price_update_callback
        })
    
    # Setup logging for Flask
    if not app.debug:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    return app
