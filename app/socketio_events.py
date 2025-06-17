"""
SocketIO events for real-time updates
"""

import logging
from flask import request
from flask_socketio import emit
import asyncio # For async get_balance
import datetime

logger = logging.getLogger(__name__)

# Track connected clients
connected_clients = set()
MAX_CLIENTS = 2  # Allow multiple clients for testing (browser + test script)


def setup_socketio_events(socketio, trading_bot):
    """Setup SocketIO event handlers."""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        global connected_clients
        client_sid = request.sid
        
        # Check if we already have the maximum number of clients
        if len(connected_clients) >= MAX_CLIENTS and client_sid not in connected_clients:
            logger.warning(f"Connection rejected - maximum of {MAX_CLIENTS} client already connected")
            # Disconnect this client
            return False
        
        # Add this client to our set
        connected_clients.add(client_sid)
        logger.info(f"Client connected (SID: {client_sid}) - Total clients: {len(connected_clients)}")
        # Frontend will call request_update immediately after connection
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        global connected_clients
        client_sid = request.sid
        
        # Remove this client from our set
        if client_sid in connected_clients:
            connected_clients.remove(client_sid)
            
        logger.info(f"Client disconnected (SID: {client_sid}) - Total clients: {len(connected_clients)}")
    
    # Define the async task separately
    async def do_request_update_async():
        logger.info("Background task 'do_request_update_async' started.")
        try:
            # --- Wallet Info --- 
            wallet_address = None
            wallet_balance = None
            if hasattr(trading_bot, 'solana_client') and trading_bot.solana_client and trading_bot.solana_client.public_key:
                wallet_address = str(trading_bot.solana_client.public_key)
                logger.info(f"Wallet address for UI: {wallet_address}")
                try:
                    balance_value = await trading_bot.solana_client.get_balance() 
                    if balance_value is not None:
                        wallet_balance = float(balance_value)
                        if wallet_balance == 0:
                            logger.info(f"Wallet balance is zero - wallet has no SOL (verified empty)")
                        else:
                            logger.info(f"Wallet balance for UI: {wallet_balance} SOL")
                    else:
                        logger.warning("Wallet balance is None - this may indicate a connection issue.")
                except Exception as e:
                    logger.error(f"Error fetching wallet balance for UI: {e}", exc_info=True)
            elif hasattr(trading_bot, 'get_wallet_info'):
                # Use the newly added get_wallet_info method
                wallet_info = trading_bot.get_wallet_info()
                if wallet_info:
                    wallet_address = wallet_info.get('address')
                    logger.info(f"Wallet address from get_wallet_info: {wallet_address}")
                    
                    # Balance is probably None from get_wallet_info since it's async
                    # Still need to get it from solana_client directly if possible
                    if wallet_address and hasattr(trading_bot, 'solana_client') and trading_bot.solana_client:
                        try:
                            balance_value = await trading_bot.solana_client.get_balance()
                            if balance_value is not None:
                                wallet_balance = float(balance_value)
                                logger.info(f"Wallet balance for UI: {wallet_balance}")
                            else:
                                logger.warning("Wallet balance is None.")
                        except Exception as e:
                            logger.error(f"Error fetching wallet balance for UI: {e}")
                else:
                    logger.warning("get_wallet_info returned empty/None result")
            else:
                logger.warning("TradingBot does not have solana_client or get_wallet_info method for UI.")

            wallet_info_for_frontend = {
                "address": wallet_address,
                "balance": wallet_balance
            }
            logger.info(f"Wallet info prepared for frontend: {wallet_info_for_frontend}")

            # --- Get Comprehensive Status Info from TradingBot (uses get_status() that we just added) ---
            current_status = "Unknown"
            current_mode = "paper" 
            portfolio_value = 0.0
            total_pnl = 0.0
            uptime = "0s"
            trading_enabled = False
            
            # Now we should have a get_status method in TradingBot
            if hasattr(trading_bot, 'get_status'): 
                bot_status_details = trading_bot.get_status()
                current_status = bot_status_details.get('status', current_status)
                current_mode = bot_status_details.get('mode', current_mode)
                portfolio_value = bot_status_details.get('portfolio_value', portfolio_value)
                total_pnl = bot_status_details.get('total_pnl', total_pnl)
                uptime = bot_status_details.get('uptime', uptime)
                trading_enabled = bot_status_details.get('trading_enabled', trading_enabled)
                logger.info(f"Bot status details fetched from get_status(): {bot_status_details}")
            else:
                logger.warning("TradingBot still does not have get_status method. Using defaults.")

            # First try to use the comprehensive get_status for a complete payload
            status_payload = {}
            if hasattr(trading_bot, 'get_status'):
                try:
                    status_payload = trading_bot.get_status()
                    # Update with our freshly fetched wallet_info which includes the balance
                    if 'wallet_info' in status_payload:
                        status_payload['wallet_info'] = wallet_info_for_frontend
                    else:
                        status_payload['wallet_info'] = wallet_info_for_frontend
                    logger.info("Used get_status() as base for status_payload")
                    
                    # Add arbitrage trade information if available
                    if hasattr(trading_bot, 'strategy') and hasattr(trading_bot.strategy, 'get_trade_history'):
                        try:
                            trades = trading_bot.strategy.get_trade_history()
                            total_profit = trading_bot.strategy.total_profit if hasattr(trading_bot.strategy, 'total_profit') else 0.0
                            
                            # Calculate trades count and successful trades
                            trades_executed = len(trades) if trades else 0
                            successful_trades = sum(1 for trade in trades if trade.get('success', False)) if trades else 0
                            
                            arbitrage_data = {
                                'trades': trades,
                                'total_profit': total_profit,
                                'trades_executed': trades_executed,
                                'successful_trades': successful_trades
                            }
                            
                            # Emit arbitrage trade data separately (use socketio.emit for background tasks)
                            socketio.emit('arbitrage_update', arbitrage_data)
                            logger.info(f"Emitted arbitrage_update with {len(arbitrage_data['trades'])} trades, total profit: ${total_profit:.2f}")
                        except Exception as e:
                            logger.error(f"Error getting arbitrage trade data: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error using get_status() for status_payload: {e}")
                    # Fall back to manually constructed payload
                    status_payload = {
                        'wallet_info': wallet_info_for_frontend,
                        'status': current_status,
                        'mode': current_mode,
                        'portfolio_value': portfolio_value,
                        'total_pnl': total_pnl,
                        'uptime': uptime,
                        'trading_enabled': trading_enabled
                    }
            else:
                # Manually construct the payload if get_status doesn't exist
                status_payload = {
                    'wallet_info': wallet_info_for_frontend,
                    'status': current_status,
                    'mode': current_mode,
                    'portfolio_value': portfolio_value,
                    'total_pnl': total_pnl,
                    'uptime': uptime,
                    'trading_enabled': trading_enabled
                }
                
            logger.info(f"Emitting full status_update from do_request_update_async: {status_payload}")
            socketio.emit('status_update', status_payload) # Use socketio.emit for background tasks

            price_data = trading_bot.get_current_price()
            if price_data:
                logger.info(f"Emitting price_update from do_request_update_async: {price_data}")
                socketio.emit('price_update', price_data)
            
            logger.info("Background task 'do_request_update_async' finished.")
            
        except Exception as e:
            logger.error(f"Error in background task do_request_update_async: {e}", exc_info=True)
            # Emitting error back to client might be tricky from background task if not handled carefully
            # Consider logging mostly, or ensure emit is safe.
            # socketio.emit('error', {'message': str(e)}) 

    @socketio.on('request_update')
    def handle_request_update(): # Now a sync function
        logger.info("Handling request_update from client (sync wrapper).")
        socketio.start_background_task(do_request_update_async)
        logger.info("Background task for request_update started via socketio.start_background_task.")
    
    # --- Trading Control Events ---
    @socketio.on('start_trading')
    def handle_start_trading():
        logger.info("Received start_trading request from client.")
        try:
            if hasattr(trading_bot, 'start_trading'):  # Using start_trading instead of start
                trading_bot.start_trading()  # This method exists in TradingBot
                logger.info("Trading start command issued.")
                
                # Immediately emit a status update after starting trading
                if hasattr(trading_bot, 'get_status'):
                    new_status = trading_bot.get_status()
                    logger.info(f"Emitting immediate status update after start_trading: {new_status}")
                    socketio.emit('status_update', new_status)
            else:
                logger.error("TradingBot has no start_trading method.")
                emit('error', {'message': 'Bot cannot start trading.'})
        except Exception as e:
            logger.error(f"Error starting trading: {e}")
            emit('error', {'message': f'Error starting trading: {e}'})

    @socketio.on('stop_trading')
    def handle_stop_trading():
        logger.info("Received stop_trading request from client.")
        try:
            if hasattr(trading_bot, 'stop_trading'):  # Using stop_trading instead of stop
                trading_bot.stop_trading()  # This method exists in TradingBot
                logger.info("Trading stop command issued.")
                
                # Immediately emit a status update after stopping trading
                if hasattr(trading_bot, 'get_status'):
                    new_status = trading_bot.get_status()
                    logger.info(f"Emitting immediate status update after stop_trading: {new_status}")
                    socketio.emit('status_update', new_status)
            else:
                logger.error("TradingBot has no stop_trading method.")
                emit('error', {'message': 'Bot cannot stop trading.'})
        except Exception as e:
            logger.error(f"Error stopping trading: {e}")
            emit('error', {'message': f'Error stopping trading: {e}'})

    # Register bot callbacks for real-time updates
    def on_price_update(price_data):
        """Callback for price updates."""
        socketio.emit('price_update', price_data)
    
    def on_trade_executed(trade_data):
        """Callback for new trades."""
        socketio.emit('trade_update', trade_data) # Changed from trade_executed to match frontend
        # Also send updated portfolio and potentially overall status
        # This might be better handled by the bot emitting a full status_change
        # try:
        #     portfolio = trading_bot.get_portfolio()
        #     socketio.emit('portfolio_update', portfolio)
        # except Exception as e:
        #     logger.error(f"Error sending portfolio update: {e}")
    
    def on_status_change(status_data):
        """Callback for status changes from the bot."""
        logger.info(f"Received on_status_change from bot: {status_data}. Emitting to client.")
        # Get comprehensive status including wallet info that was just added to TradingBot
        if hasattr(trading_bot, 'get_status'):
            try:
                comprehensive_status = trading_bot.get_status()
                
                # Merge any specific status_data fields with our comprehensive status
                if isinstance(status_data, dict):
                    comprehensive_status.update(status_data)
                
                logger.info(f"Enhanced status_update being emitted: {comprehensive_status}")
                socketio.emit('status_update', comprehensive_status)
            except Exception as e:
                logger.error(f"Error getting comprehensive status: {e}")
                # Fall back to basic status_data if there was an error
                socketio.emit('status_update', status_data)
        else:
            # Fall back to original approach if get_status doesn't exist
            socketio.emit('status_update', status_data)
    
    # Register callbacks with trading bot
    if hasattr(trading_bot, 'set_callbacks'):
        trading_bot.set_callbacks({
            'price_update': on_price_update,
            'trade_executed': on_trade_executed,
            'status_change': on_status_change
        })
    else:
        logger.warning("TradingBot does not have set_callbacks method.")
    
    # Add a helper function for emitting trade errors
    def emit_trade_error(socketio, error_message, error_code=None, trade_details=None):
        """
        Emit a trade error event to the frontend with detailed information.
        
        Args:
            socketio: The SocketIO instance
            error_message: The error message to display
            error_code: Optional error code for categorization
            trade_details: Optional dict with details about the failed trade
        """
        error_data = {
            'message': error_message,
            'timestamp': datetime.datetime.now().isoformat(),
            'code': error_code
        }
        
        if trade_details:
            error_data['trade'] = trade_details
        
        logger.error(f"Emitting trade error to frontend: {error_message}")
        socketio.emit('trade_error', error_data)
    
    # Make the function available at the module level for easy import elsewhere
    trading_bot.socketio = socketio  # Store reference to socketio in trading_bot for error reporting
    
    # Function for other modules to report errors
    def report_trade_error(error_message, error_code=None, trade_details=None):
        """
        Public function that can be called from anywhere to report trade errors.
        Import this function in other files to report errors to the UI.
        """
        if hasattr(trading_bot, 'socketio'):
            emit_trade_error(trading_bot.socketio, error_message, error_code, trade_details)
        else:
            logger.error(f"SocketIO not available for error: {error_message}")
            
    # Make this function available to other modules
    trading_bot.report_trade_error = report_trade_error
    
    # Debug: Handle arbitrage_update events from clients (like test script)
    @socketio.on('arbitrage_update')
    def handle_client_arbitrage_update(data):
        """Handle arbitrage_update events from clients (e.g., test script)."""
        logger.info(f"🔄 Received arbitrage_update from client: {data}")
        # Re-emit to all other clients (including browser)
        socketio.emit('arbitrage_update', data)
        logger.info(f"🔄 Re-emitted arbitrage_update to all clients")
    
    @socketio.on('trade_error')  
    def handle_client_trade_error(data):
        """Handle trade_error events from clients (e.g., test script)."""
        logger.info(f"🔄 Received trade_error from client: {data}")
        # Re-emit to all other clients (including browser)
        socketio.emit('trade_error', data)
        logger.info(f"🔄 Re-emitted trade_error to all clients")
    
    # Debug: Log all incoming events from clients
    @socketio.on_error_default
    def default_error_handler(e):
        logger.error(f"SocketIO error: {e}")
    
    # This will catch any events not explicitly handled
    def catch_all_events(event, *args):
        logger.info(f"🔔 Received unknown event '{event}' with args: {args}")
    
    # Register catch-all for debugging
    socketio.on_event('*', catch_all_events)
