"""
Flask routes for the web interface
"""

import json
import logging
from flask import Blueprint, render_template, jsonify, current_app, request

logger = logging.getLogger(__name__)
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Main dashboard page."""
    bot = current_app.config['TRADING_BOT']
    config = current_app.config['CONFIG']
    
    return render_template('index.html', 
                         config=config,
                         trading_mode=config['trading']['mode'])


@main_bp.route('/api/status')
def api_status():
    """Get bot status and basic info."""
    bot = current_app.config['TRADING_BOT']
    config = current_app.config['CONFIG']
    
    try:
        status = {
            'running': bot.is_running(),
            'mode': config['trading']['mode'],
            'token': config['trading']['token_symbol'],
            'last_update': bot.get_last_update(),
            'uptime': bot.get_uptime()
        }
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/price')
def api_price():
    """Get current price data."""
    bot = current_app.config['TRADING_BOT']
    
    try:
        price_data = bot.get_current_price()
        return jsonify(price_data)
    except Exception as e:
        logger.error(f"Error getting price: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/portfolio')
def api_portfolio():
    """Get portfolio information."""
    bot = current_app.config['TRADING_BOT']
    
    try:
        portfolio = bot.get_portfolio()
        return jsonify(portfolio)
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/trades')
def api_trades():
    """Get recent trades."""
    bot = current_app.config['TRADING_BOT']
    limit = request.args.get('limit', 50, type=int)
    
    try:
        trades = bot.get_recent_trades(limit)
        return jsonify(trades)
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/price-history')
def api_price_history():
    """Get price history for charts."""
    bot = current_app.config['TRADING_BOT']
    hours = request.args.get('hours', 24, type=int)
    
    try:
        history = bot.get_price_history(hours)
        return jsonify(history)
    except Exception as e:
        logger.error(f"Error getting price history: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/trading/start', methods=['POST'])
def api_start_trading():
    """Start/resume trading."""
    bot = current_app.config['TRADING_BOT']
    
    try:
        success = bot.start_trading()
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Error starting trading: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/trading/stop', methods=['POST'])
def api_stop_trading():
    """Stop/pause trading."""
    bot = current_app.config['TRADING_BOT']
    
    try:
        success = bot.stop_trading()
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Error stopping trading: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/config')
def api_config():
    """Get current configuration (sanitized)."""
    config = current_app.config['CONFIG']
    
    # Remove sensitive information
    safe_config = {
        'trading': config['trading'],
        'price_feeds': config['price_feeds'],
        'risk': config['risk'],
        'web': config['web']
    }
    
    # Remove private key from response
    if 'wallet' in safe_config:
        safe_config['wallet'] = {
            'public_key': config.get('wallet', {}).get('public_key', '')
        }
    
    return jsonify(safe_config)


@main_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@main_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500
