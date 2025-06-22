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
        # Use the comprehensive status method that includes wallet info
        if hasattr(bot, 'get_status'):
            status = bot.get_status()
            return jsonify(status)
        else:
            # Fallback to basic status
            is_running = bot.is_running()
            status = {
                'running': is_running,
                'status': 'Running' if is_running else 'Stopped',
                'mode': config['trading']['mode'],
                'token': config['trading']['token_symbol'],
                'last_update': bot.get_last_update(),
                'uptime': bot.get_uptime(),
                'wallet_info': bot.get_wallet_info() if hasattr(bot, 'get_wallet_info') else None
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
    """Price history endpoint (disabled)."""
    logger.info("Price history endpoint accessed (chart disabled)")
    # Return empty array since chart functionality is disabled
    return jsonify([{"message": "Chart functionality has been disabled"}])


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
    """Debug endpoint for price history (disabled)."""
    logger.info("Price history debug endpoint accessed (chart disabled)")
    
    return jsonify({
        'debug_info': {
            'message': 'Chart functionality has been disabled'
        },
        'history': []
    })


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


@main_bp.route('/api/validate-funds')
def api_validate_funds():
    """Validate wallet funds for live trading."""
    bot = current_app.config['TRADING_BOT']
    
    try:
        # Run the async validation function
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            validation_result = loop.run_until_complete(bot.validate_trading_funds())
        finally:
            loop.close()
        
        return jsonify(validation_result)
    except Exception as e:
        logger.error(f"Error validating funds: {e}")
        return jsonify({
            'sufficient': False,
            'error': str(e),
            'mode': bot.config.get('trading', {}).get('mode', 'unknown')
        }), 500


@main_bp.route('/api/bot/start', methods=['POST'])
def api_bot_start():
    """Start the arbitrage bot."""
    bot = current_app.config['TRADING_BOT']
    
    try:
        logger.info(f"Bot start requested. Current status: {bot.is_running()}")
        
        if bot.is_running():
            logger.info("Bot is already running, returning error")
            return jsonify({
                'success': False,
                'error': 'Bot is already running',
                'status': 'running'
            })
        
        # Request bot to start
        success = bot.request_start()
        
        if success:
            logger.info("Bot start requested successfully")
            # Give it a moment to start
            import time
            time.sleep(0.5)
            
            # Trigger status change callback
            if hasattr(bot, '_emit_status_change'):
                logger.info("Emitting status change")
                bot._emit_status_change()
            
            return jsonify({
                'success': True,
                'message': 'Bot start requested successfully',
                'status': 'Starting'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to request bot start',
                'status': 'error'
            })
            
    except Exception as e:
        logger.error(f"Error requesting bot start: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'status': 'error'
        }), 500


@main_bp.route('/api/bot/stop', methods=['POST'])
def api_bot_stop():
    """Stop the arbitrage bot."""
    bot = current_app.config['TRADING_BOT']
    
    try:
        logger.info(f"Bot stop requested. Current status: {bot.is_running()}")
        
        if not bot.is_running():
            logger.info("Bot is not running, returning error")
            return jsonify({
                'success': False,
                'error': 'Bot is not running',
                'status': 'stopped'
            })
        
        # Request bot to stop
        success = bot.request_stop()
        
        if success:
            logger.info("Bot stop requested successfully")
            # Give it a moment to stop
            import time
            time.sleep(0.5)
            
            # Trigger status change callback
            if hasattr(bot, '_emit_status_change'):
                logger.info("Emitting status change")
                bot._emit_status_change()
            
            return jsonify({
                'success': True,
                'message': 'Bot stop requested successfully',
                'status': 'Stopping'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to request bot stop',
                'status': 'error'
            })
            
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'status': 'error'
        }), 500


@main_bp.route('/api/wallet-address')
def api_wallet_address():
    """Get the wallet address for funding."""
    bot = current_app.config['TRADING_BOT']
    
    try:
        # Get wallet info from the bot
        wallet_info = bot.get_wallet_info()
        
        if wallet_info and wallet_info.get('address'):
            return jsonify({
                'address': wallet_info['address'],
                'success': True
            })
        else:
            # Try to get address from solana client directly
            if hasattr(bot, 'solana_client') and hasattr(bot.solana_client, 'get_wallet_address'):
                try:
                    address = bot.solana_client.get_wallet_address()
                    if address:
                        return jsonify({
                            'address': address,
                            'success': True
                        })
                except Exception as e:
                    logger.error(f"Error getting address from solana client: {e}")
            
            return jsonify({
                'error': 'Wallet address not available',
                'success': False
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting wallet address: {e}")
        return jsonify({
            'error': str(e),
            'success': False
        }), 500


@main_bp.route('/api/wallet/refresh', methods=['POST'])
def api_wallet_refresh():
    """Refresh wallet balances and return updated balance information."""
    bot = current_app.config['TRADING_BOT']
    
    try:
        import asyncio
        
        async def do_refresh():
            # Call the refresh method on the bot
            return await bot.refresh_wallet_balance()
        
        # Run the refresh asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(do_refresh())
            
            if success:
                # Get the updated wallet info with all balances
                wallet_info = bot.get_wallet_info()
                return jsonify({
                    'success': True,
                    'wallet_info': wallet_info,
                    'message': 'Wallet balances refreshed successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to refresh wallet balances',
                    'message': 'Balance refresh failed'
                }), 500
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error refreshing wallet balances: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to refresh wallet balances'
        }), 500


@main_bp.route('/api/wallet-balance', methods=['GET'])
def refresh_wallet_balance():
    """Refresh the wallet balance."""
    bot = current_app.config['TRADING_BOT']  # Add this line
    
    try:
        import asyncio
        
        async def do_refresh():
            # Call the refresh method on your bot instance
            balance = await bot.refresh_wallet_balance()  # Change trading_bot to bot
            return balance
        
        # Run the refresh
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            balance = loop.run_until_complete(do_refresh())
            return jsonify({
                'success': True,
                'balance': balance,
                'message': f'Balance updated: {balance} SOL' if balance is not None else 'Failed to fetch balance'
            })
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error refreshing wallet balance: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to refresh balance'
        }), 500


@main_bp.route('/api/trading/mode', methods=['POST'])
def api_change_trading_mode():
    """Change trading mode between paper and mainnet."""
    bot = current_app.config['TRADING_BOT']
    config = current_app.config['CONFIG']
    
    try:
        data = request.get_json()
        new_mode = data.get('mode', '').lower()
        
        if new_mode not in ['paper', 'mainnet']:
            return jsonify({
                'success': False,
                'error': 'Invalid mode. Must be "paper" or "mainnet".'
            }), 400
        
        # Update the configuration
        old_mode = config['trading']['mode']
        config['trading']['mode'] = new_mode
        
        # If switching to mainnet and bot is running, validate funds
        if new_mode == 'mainnet' and bot.is_running():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                validation_result = loop.run_until_complete(bot.validate_trading_funds())
                if not validation_result.get('sufficient', False):
                    # Revert the mode change
                    config['trading']['mode'] = old_mode
                    return jsonify({
                        'success': False,
                        'error': 'Insufficient funds for mainnet trading',
                        'validation': validation_result
                    }), 400
            finally:
                loop.close()
        
        # Trigger wallet balance refresh after mode change
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            refresh_success = loop.run_until_complete(bot.refresh_wallet_balance())
            logger.info(f"Wallet balance refresh after mode change: {'success' if refresh_success else 'failed'}")
        except Exception as e:
            logger.error(f"Error refreshing wallet balance after mode change: {e}")
        finally:
            loop.close()
        
        # Emit status update to notify all connected clients
        if hasattr(bot, '_emit_status_change'):
            bot._emit_status_change()
        
        logger.info(f"Trading mode changed from {old_mode} to {new_mode}")
        
        return jsonify({
            'success': True,
            'old_mode': old_mode,
            'new_mode': new_mode,
            'message': f'Trading mode changed to {new_mode.upper()}'
        })
        
    except Exception as e:
        logger.error(f"Error changing trading mode: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@main_bp.route('/api/trading/mode', methods=['GET'])
def api_get_trading_mode():
    """Get current trading mode."""
    config = current_app.config['CONFIG']
    
    try:
        current_mode = config['trading']['mode']
        return jsonify({
            'mode': current_mode,
            'success': True
        })
    except Exception as e:
        logger.error(f"Error getting trading mode: {e}")
        return jsonify({
            'error': str(e),
            'success': False
        }), 500


@main_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@main_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500
