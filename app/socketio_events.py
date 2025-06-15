"""
SocketIO events for real-time updates
"""

import logging
from flask_socketio import emit

logger = logging.getLogger(__name__)


def setup_socketio_events(socketio, trading_bot):
    """Setup SocketIO event handlers."""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info("Client connected")
        emit('status', {'message': 'Connected to Workhorse'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        logger.info("Client disconnected")
    
    @socketio.on('request_update')
    def handle_request_update():
        """Handle request for immediate data update."""
        try:
            # Send current price
            price_data = trading_bot.get_current_price()
            emit('price_update', price_data)
            
            # Send portfolio
            portfolio = trading_bot.get_portfolio()
            emit('portfolio_update', portfolio)
            
            # Send recent trades
            trades = trading_bot.get_recent_trades(10)
            emit('trades_update', trades)
            
        except Exception as e:
            logger.error(f"Error handling request_update: {e}")
            emit('error', {'message': str(e)})
    
    # Register bot callbacks for real-time updates
    def on_price_update(price_data):
        """Callback for price updates."""
        socketio.emit('price_update', price_data)
    
    def on_trade_executed(trade_data):
        """Callback for new trades."""
        socketio.emit('trade_executed', trade_data)
        # Also send updated portfolio
        try:
            portfolio = trading_bot.get_portfolio()
            socketio.emit('portfolio_update', portfolio)
        except Exception as e:
            logger.error(f"Error sending portfolio update: {e}")
    
    def on_status_change(status_data):
        """Callback for status changes."""
        socketio.emit('status_update', status_data)
    
    # Register callbacks with trading bot
    trading_bot.set_callbacks({
        'price_update': on_price_update,
        'trade_executed': on_trade_executed,
        'status_change': on_status_change
    })
