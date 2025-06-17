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
    hours = request.args.get('hours', 24, type=float)  # Allow decimal hours (e.g., 1.5)
    
    try:
        logger.info(f"Fetching price history for {hours} hours")
        history = bot.get_price_history(hours)
        
        if not history:
            logger.warning(f"No price history found for the last {hours} hours")
            # Return empty array instead of synthetic data
            return jsonify([])
            
        # Validate each point in the history
        valid_history = []
        for point in history:
            if not isinstance(point, dict):
                logger.warning(f"Skipping non-dict point: {point}")
                continue
                
            if 'price' not in point or 'timestamp' not in point:
                logger.warning(f"Skipping point missing price or timestamp: {point}")
                continue
                
            # Ensure price is a number
            try:
                point['price'] = float(point['price'])
            except (ValueError, TypeError):
                logger.warning(f"Skipping point with invalid price: {point}")
                continue
                
            valid_history.append(point)
                
        logger.info(f"Returning {len(valid_history)} valid price history points")
        return jsonify(valid_history)
    except Exception as e:
        logger.error(f"Error getting price history: {e}", exc_info=True)
        # Return error instead of synthetic data
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


@main_bp.route('/api/price-history-debug')
def api_price_history_debug():
    """Debug endpoint for price history."""
    bot = current_app.config['TRADING_BOT']
    hours = request.args.get('hours', 1.5, type=float)
    
    try:
        history = bot.get_price_history(int(hours))
        
        # Add debugging info
        debug_info = {
            'requested_hours': hours,
            'history_points': len(history) if history else 0,
            'has_price_data': any(point.get('price') is not None for point in history) if history else False,
            'timestamp_format': history[0].get('timestamp') if history and len(history) > 0 else None,
            'price_sample': history[0].get('price') if history and len(history) > 0 else None,
            'raw_history': history[:5]  # First 5 points for inspection
        }
        
        return jsonify({
            'debug_info': debug_info,
            'history': history
        })
    except Exception as e:
        logger.error(f"Error in price history debug endpoint: {e}")
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@main_bp.route('/api/test-trades', methods=['POST'])
def inject_test_trades():
    """Inject test trades for UI testing (single instance safe)."""
    bot = current_app.config.get('TRADING_BOT')
    if not bot:
        return jsonify({'error': 'Trading bot not available'}), 503
    
    try:
        # Get count from request, default to 5
        count = int(request.json.get('count', 5)) if request.json else 5
        count = max(1, min(count, 20))  # Limit between 1 and 20
        
        # Inject test trades
        bot.inject_test_trades(count)
        
        return jsonify({
            'success': True,
            'message': f'Successfully injected {count} test trades',
            'count': count
        })
    except Exception as e:
        logger.error(f"Error injecting test trades: {e}")
        return jsonify({'error': str(e)}), 500


@main_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@main_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500
