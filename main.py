#!/usr/bin/env python3
"""
Workhorse - Solana DEX Arbitrage Bot
Main application entry point
"""

import asyncio
import logging
import logging.handlers
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
import os
import json
import threading

import yaml
from app import create_app
from core.solana_client import SolanaClient
from core.price_feeds import PriceFeedManager

# Import these conditionally when needed
# from gevent import pywsgi
# from geventwebsocket.handler import WebSocketHandler
from core.arbitrage_strategy import ArbitrageStrategy
# Replace TradingBot with ArbitrageBot
from core.arbitrage_strategy import ArbitrageStrategy
from core.price_feeds import PriceFeedManager
from core.solana_client import SolanaClient


def load_config():
    """Load configuration from YAML file."""
    # Load both configs - main config and arbitrage config
    config_path = Path("config.yaml")
    arbitrage_config_path = Path("arbitrage_config.yaml")
    
    if not config_path.exists():
        print("Error: config.yaml not found. Please copy config.example.yaml to config.yaml")
        sys.exit(1)
    
    if not arbitrage_config_path.exists():
        print("Error: arbitrage_config.yaml not found. Please ensure arbitrage configuration is set up")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    with open(arbitrage_config_path, 'r') as f:
        arbitrage_config = yaml.safe_load(f)
    
    # Merge configs, with arbitrage config taking precedence
    config.update(arbitrage_config)
    
    # Debug print the wallet path
    print(f"DEBUG: wallet_path from config: {config.get('wallet_path')}, type: {type(config.get('wallet_path'))}")
    
    return config


def setup_logging(config):
    """Setup logging configuration."""
    log_config = config.get('logging', {})
    level = getattr(logging, log_config.get('level', 'INFO'))
    
    # Get the log file path, ensure it's a string
    log_file = log_config.get('file')
    if not isinstance(log_file, str) or not log_file:
        log_file = 'workhorse.log'
        print(f"Warning: Invalid log file path in config, using default: {log_file}")
    
    # Setup main logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Setup separate trade logger if configured
    trade_logger = None
    if log_config.get('log_trades', True):
        trade_log_file = log_config.get('trade_log_file', 'trades.log')
        
        # Create a special logger just for trades
        trade_logger = logging.getLogger('trade_logger')
        trade_logger.setLevel(level)
        
        # Prevent the trade logger from propagating to the root logger
        trade_logger.propagate = False
        
        # Add a file handler for the trade log
        trade_handler = logging.FileHandler(trade_log_file)
        trade_formatter = logging.Formatter('%(asctime)s - %(message)s')
        trade_handler.setFormatter(trade_formatter)
        trade_logger.addHandler(trade_handler)
        
        print(f"Trade logging enabled, writing to: {trade_log_file}")
    
    # Return the trade logger so it can be used by the bot
    return trade_logger


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logging.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


class ArbitrageBot:
    """DEX Arbitrage Bot for automated trading on Solana."""
    
    def __init__(self, config, trade_logger=None):
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🔄 Initializing Arbitrage Bot")
        
        # Trade logger for separate trade logging
        self.trade_logger = trade_logger
        
        # Config
        self.config = config
        
        # Initialize components
        self.solana_client = SolanaClient(self.config)
        self.price_feed = PriceFeedManager(self.config)
        self.strategy = ArbitrageStrategy(self.config, trading_bot=self)  # Pass self to allow error reporting
        
        # Bot state
        self.running = False
        self.start_time = None
        self.loop = None  # Store event loop for uptime calculations
        self.total_profits = 0.0
        self.trades_executed = 0
        self.bot_task = None  # Store the async task
        self._should_start = False  # Flag to indicate bot should start
        self._should_stop = False   # Flag to indicate bot should stop
        
        # Callbacks
        self.callbacks = {}
    
    async def start(self):
        """Start the arbitrage bot."""
        if self.running:
            self.logger.warning("⚠️ Bot is already running")
            return
        
        self.running = True
        self.loop = asyncio.get_event_loop()  # Store the event loop
        self.start_time = time.time()    # Use system time for consistent uptime calculation
        self.logger.info("🚀 Starting DEX Arbitrage Bot")
        
        # Emit immediate status change to notify UI that bot is starting
        self._emit_status_change()
        
        # Start price feeds
        await self.price_feed.start()
        
        # Register price update callback
        self.price_feed.add_callback(self.on_price_update)
        
        # Main loop
        try:
            while self.running and not self._should_stop:
                # Check if we should stop
                if self._should_stop:
                    self.logger.info("Stop flag detected, breaking main loop")
                    break
                
                # Bot health check
                await self.health_check()
                
                # Sleep to prevent CPU usage
                update_interval = self.config.get('price_feeds', {}).get('update_interval', 10)
                await asyncio.sleep(update_interval)
                
                # Emit status update via callback
                self._emit_status_change()
                
        except asyncio.CancelledError:
            self.logger.info("Bot operation cancelled")
        except Exception as e:
            self.logger.error(f"❌ Error in main bot loop: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the arbitrage bot."""
        if not self.running:
            self.logger.warning("⚠️ Bot is not running")
            return
        
        self.logger.info("🛑 Stopping DEX Arbitrage Bot")
        self.running = False
        self._should_stop = True
        
        # Stop price feeds
        await self.price_feed.stop()
        
        # Close Solana client
        await self.solana_client.close()
        
        # Calculate and log final stats
        uptime = self._get_uptime_str()
        self.logger.info(f"📊 Bot stopped. Uptime: {uptime}, Trades executed: {self.trades_executed}, Total profits: {self.total_profits:.4f} USDC")
        
        # Reset state
        self.start_time = None
        self._should_stop = False
        
        # Emit final status change
        self._emit_status_change()
    
    async def on_price_update(self, price_data):
        """Handle price updates from the price feeds."""
        try:
            # Ensure price_data is not None before processing
            if price_data is None:
                self.logger.warning("⚠️ Received None price data, skipping update")
                return
            
            # Format the data for the strategy - ensure it has all required fields
            formatted_data = {
                'source': price_data.get('source', 'unknown'),
                'token_pair': f"{price_data.get('token', self.config.get('trading', {}).get('token_symbol', 'SOL'))}/{price_data.get('quote_token', 'USDC')}",
                'price': price_data.get('price', 0),
                'timestamp': price_data.get('timestamp', None)
            }
            
            # Validate the formatted data
            if formatted_data['price'] <= 0:
                self.logger.warning(f"Skipping price update with invalid price: {formatted_data}")
                return
                
            # Log the price update for debugging
            source = formatted_data.get('source', 'unknown')
            token_pair = formatted_data.get('token_pair', 'UNKNOWN/UNKNOWN')
            price = formatted_data.get('price', 0)
            self.logger.debug(f"Price update received: {source} - {token_pair} - ${price:.4f}")
            
            # Update strategy with new price data
            await self.strategy.update_prices(formatted_data)
            
            # Check for arbitrage opportunities
            signal = await self.strategy.detect_opportunities()
            
            # Execute arbitrage if signal is generated
            if signal and isinstance(signal, dict):
                self.logger.info(f"🔔 ARBITRAGE SIGNAL DETECTED: {signal.get('reason', 'No reason provided')}")
                
                if 'buy' in signal and 'sell' in signal:
                    token_pair = signal.get('token_pair', 'Unknown')
                    buy_source = signal.get('buy', {}).get('source', 'Unknown')
                    buy_price = signal.get('buy', {}).get('price', 0)
                    sell_source = signal.get('sell', {}).get('source', 'Unknown')
                    sell_price = signal.get('sell', {}).get('price', 0)
                    self.logger.info(f"📊 Signal: Buy {token_pair} on {buy_source} at ${buy_price:.4f} and sell on {sell_source} at ${sell_price:.4f}")
                else:
                    self.logger.error(f"Signal structure invalid: {signal}")
                
                # Execute the arbitrage trade
                try:
                    self.logger.info(f"🔄 Executing arbitrage trade...")
                    result = await self.strategy.execute_arbitrage_trade(signal, self.solana_client)
                    self.logger.info(f"📝 Trade result: {result}")
                except Exception as e:
                    self.logger.error(f"❌ Exception during trade execution: {str(e)}")
                    result = {'success': False, 'error': f"Exception: {str(e)}"}
                
                # Process trade result
                if result.get('success', False):
                    self.trades_executed += 1
                    profit = result.get('realized_profit', 0)
                    self.total_profits += profit
                    
                    self.logger.info(f"✅ TRADE EXECUTED SUCCESSFULLY! Profit: {profit:.4f} USDC, Total profits: {self.total_profits:.4f} USDC")
                else:
                    self.logger.warning(f"❌ Trade execution failed: {result.get('error', 'Unknown error')}")
                
                # Update strategy with trade result (this will trigger the callback)
                self.strategy.on_trade_executed(result)
                
                # Emit updated status
                self._emit_status_change()
        
        except Exception as e:
            self.logger.error(f"❌ Error processing price update: {str(e)}")
    
    async def health_check(self):
        """Perform health checks on the bot."""
        try:
            # Check if price feeds are working
            if hasattr(self.price_feed, '_last_update') and self.price_feed._last_update:
                from time import time
                time_since_update = time() - self.price_feed._last_update
                if time_since_update > 60:  # No updates for 1 minute
                    self.logger.warning(f"⚠️ No price updates received for {time_since_update:.1f} seconds")
            
            # Log status
            uptime = self._get_uptime_str()
            self.logger.info(f"✅ Bot running for {uptime}, "
                           f"trades: {self.trades_executed}, "
                           f"profits: {self.total_profits:.4f} USDC")
            
        except Exception as e:
            self.logger.error(f"❌ Error during health check: {e}")
    
    def get_current_price(self):
        """Get current price data for the UI."""
        try:
            latest_prices = self.price_feed.get_latest_prices() if hasattr(self.price_feed, 'get_latest_prices') else {}
            if latest_prices and 'price' in latest_prices:
                self.logger.debug(f"Current price from feed: ${latest_prices['price']:.2f}")
                return latest_prices
            else:
                # Fallback to test data for development
                self.logger.warning("No current price from feeds, returning test data")
                import random
                return {
                    'price': round(180.0 + random.uniform(-10, 10), 2),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'test',
                    'pair': 'SOL/USDC'
                }
        except Exception as e:
            self.logger.error(f"Error getting current price: {e}")
            return {}
    
    # Add this to your main bot class (wherever it's defined)
    async def refresh_wallet_balance(self):
        """Refresh the wallet balance on demand."""
        try:
            self.logger.info("🔄 Refreshing wallet balances...")
            
            # First try to use the existing get_real_balance method
            balances = await self.solana_client.get_real_balance()
            
            # If that fails (None or empty), try a more direct approach with fallback RPC
            if balances is None or not any(balances.values() if isinstance(balances, dict) else []):
                self.logger.warning("get_real_balance returned empty/None, trying direct balance fetch with fallback RPC...")
                
                # Try to create a temporary client with a working RPC endpoint
                try:
                    from solana.rpc.async_api import AsyncClient
                    from solana.rpc.commitment import Commitment
                    
                    # Try standard Solana RPC first
                    fallback_endpoints = [
                        'https://api.mainnet-beta.solana.com',
                        'https://rpc.ankr.com/solana',
                        'https://solana-api.projectserum.com'
                    ]
                    
                    for endpoint in fallback_endpoints:
                        try:
                            self.logger.info(f"Trying fallback RPC endpoint: {endpoint}")
                            temp_client = AsyncClient(endpoint, commitment=Commitment("confirmed"))
                            
                            if self.solana_client.public_key:
                                response = await temp_client.get_balance(self.solana_client.public_key)
                                if response and hasattr(response, 'value') and response.value is not None:
                                    sol_balance = response.value / 1_000_000_000
                                    balances = {
                                        'SOL': sol_balance,
                                        'USDC': 0.0,  # For now, just focus on SOL
                                        'USDT': 0.0
                                    }
                                    self.logger.info(f"Successfully fetched SOL balance from {endpoint}: {sol_balance}")
                                    break
                            
                            await temp_client.close()
                        except Exception as e:
                            self.logger.warning(f"Fallback endpoint {endpoint} failed: {e}")
                            continue
                    
                except Exception as e:
                    self.logger.error(f"Error with fallback RPC approach: {e}")
            
            if balances is not None and any(balances.values() if isinstance(balances, dict) else []):
                self.solana_client._cached_real_balances = balances
                sol_balance = balances.get('SOL', 0)
                usdc_balance = balances.get('USDC', 0)
                usdt_balance = balances.get('USDT', 0)
                self.logger.info(f"💰 Updated wallet balances: {sol_balance} SOL, {usdc_balance} USDC, {usdt_balance} USDT")
                return True
            else:
                self.logger.error("Failed to refresh wallet balances - all methods returned None/empty")
                return False
        except Exception as e:
            self.logger.error(f"Error refreshing wallet balances: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    
    def get_wallet_info(self):
        """Return information about the wallet for display in the UI.
        Always shows real on-chain wallet balances regardless of trading mode.
        """
        try:
            # Get wallet address safely
            address = None
            if hasattr(self.solana_client, 'get_wallet_address'):
                try:
                    address = self.solana_client.get_wallet_address()
                except Exception as e:
                    self.logger.error(f"Error getting wallet address: {e}")
                    
            if address is None and hasattr(self.solana_client, 'public_key') and self.solana_client.public_key:
                try:
                    address = str(self.solana_client.public_key)
                except Exception as e:
                    self.logger.error(f"Error converting public_key to string: {e}")
        
            # ALWAYS get real cached balances (actual on-chain wallet balances)
            real_balances = None
            if hasattr(self.solana_client, '_cached_real_balances'):
                real_balances = self.solana_client._cached_real_balances

            # If no cached balances or they're empty, trigger a refresh in the background
            if real_balances is None or not any(real_balances.values() if isinstance(real_balances, dict) else []):
                self.logger.info("No cached balances found, they may need refreshing")
                # For now, return zeros but log that refresh is needed
                real_balances = {'SOL': 0.0, 'USDC': 0.0, 'USDT': 0.0}
            
            # Ensure real_balances is a proper dictionary
            if not isinstance(real_balances, dict):
                real_balances = {'SOL': 0.0, 'USDC': 0.0, 'USDT': 0.0}

            # Get trading mode for display purposes
            trading_mode = self.config.get('trading', {}).get('mode', 'live')
            is_paper_mode = trading_mode == 'paper'
            
            # Get paper trading profit/loss for display (separate from real balances)
            paper_pnl = 0.0
            if is_paper_mode and hasattr(self.strategy, '_paper_balance'):
                initial_paper_balance = self.config.get('trading', {}).get('paper_trading', {}).get('initial_balance', 1000)
                current_paper_balance = self.strategy._paper_balance
                paper_pnl = current_paper_balance - initial_paper_balance
            elif hasattr(self, 'total_profits'):
                paper_pnl = self.total_profits
                
            wallet_info = {
                'address': address,
                'balances': real_balances,  # Always show real on-chain balances
                'pnl': paper_pnl,  # Paper trading P&L or live trading profits
                'paper_mode': is_paper_mode
            }
            
            self.logger.debug(f"get_wallet_info returning real balances: {wallet_info}")
            return wallet_info
            
        except Exception as e:
            self.logger.error(f"Error in get_wallet_info: {e}")
            return {
                'address': None,
                'balances': {'SOL': 0.0, 'USDC': 0.0, 'USDT': 0.0},
                'pnl': 0.0,
                'paper_mode': self.config.get('trading', {}).get('mode', 'live') == 'paper'
            }
    
    def _get_uptime_str(self):
        """Get bot uptime as a formatted string."""
        if not self.start_time:
            return "0s"
        
        try:
            # Always use system time for consistent uptime calculation
            current_time = time.time()
            uptime_seconds = int(current_time - self.start_time)
        except Exception as e:
            self.logger.warning(f"Error calculating uptime: {e}")
            return "Error"
        
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_status(self):
        """Get comprehensive status information."""
        return {
            'status': 'Running' if self.running else 'Stopped',
            'mode': self.config.get('trading', {}).get('mode', 'paper'),
            'uptime': self._get_uptime_str(),
            'portfolio_value': self.strategy.portfolio_value if hasattr(self.strategy, 'portfolio_value') else 0.0,
            'total_pnl': self.total_profits,
            'trades_executed': self.trades_executed,
            'wallet_info': self.get_wallet_info(),
            'trading_enabled': self.running,
            'recent_trades': self.get_recent_trades(10)  # Include the 10 most recent trades
        }
    
    def set_callbacks(self, callbacks):
        """Set callbacks for events."""
        self.callbacks = callbacks
    
    def _emit_status_change(self):
        """Emit status change event via callback."""
        if 'status_change' in self.callbacks and callable(self.callbacks['status_change']):
            self.callbacks['status_change'](self.get_status())
    
    def _emit_trade_executed(self, trade_data):
        """Emit trade executed event via callback."""
        self.logger.info(f"🔔 _emit_trade_executed called with: {trade_data}")
        self.logger.info(f"🔔 Available callbacks: {list(self.callbacks.keys())}")
        
        if 'trade_executed' in self.callbacks and callable(self.callbacks['trade_executed']):
            # Make sure all the needed fields are present
            enriched_data = {
                'timestamp': trade_data.get('timestamp', datetime.now().isoformat()),
                'token_pair': trade_data.get('token_pair', 'Unknown'),
                'buy_source': trade_data.get('buy_source', 'Unknown'),
                'sell_source': trade_data.get('sell_source', 'Unknown'),
                'trade_amount': trade_data.get('trade_amount', 0),
                'realized_profit': trade_data.get('realized_profit', 0),
                'success': trade_data.get('success', False),
                'action': 'Arbitrage',  # Set explicit action for UI
                'buy_price': trade_data.get('buy_price', 0),
                'sell_price': trade_data.get('sell_price', 0)
            }
            # Add any error information
            if 'error' in trade_data:
                enriched_data['error'] = trade_data['error']
            
            # Emit the enriched data
            self.logger.info(f"🔔 Calling trade_executed callback with: {enriched_data}")
            self.callbacks['trade_executed'](enriched_data)
            
            # Log trade to separate trade log if available
            if self.trade_logger:
                try:
                    # Format the trade data as JSON for structured logging
                    trade_json = json.dumps(enriched_data)
                    self.trade_logger.info(trade_json)
                except Exception as e:
                    self.logger.error(f"Failed to log trade to trade_log: {e}")
        else:
            self.logger.warning(f"❌ trade_executed callback not available or not callable!")
            
    def _emit_price_update(self, price_data):
        """Emit price update event via callback."""
        if 'price_update' in self.callbacks and callable(self.callbacks['price_update']):
            self.callbacks['price_update'](price_data)
    
    def is_running(self):
        """Check if the bot is running."""
        return self.running
    
    def request_start(self):
        """Request bot to start (thread-safe)."""
        if self.running:
            self.logger.info("Bot is already running, ignoring start request")
            return False
        
        # Check if we have access to the event loop
        if hasattr(self, 'loop') and self.loop:
            try:
                import asyncio
                self.logger.info(f"Scheduling bot start in stored event loop (running: {self.loop.is_running()})")
                # Schedule the start in the main event loop
                future = asyncio.run_coroutine_threadsafe(self.start(), self.loop)
                # Add a callback to check the result
                def check_result(fut):
                    try:
                        result = fut.result()
                        self.logger.info(f"Bot start completed with result: {result}")
                    except Exception as e:
                        self.logger.error(f"Bot start failed with exception: {e}")
                future.add_done_callback(check_result)
                self.logger.info("Bot start scheduled successfully")
                return True
            except Exception as e:
                self.logger.error(f"Error scheduling bot start: {e}")
                return False
        else:
            # Try to get the current event loop
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop and loop.is_running():
                    self.logger.info(f"Using current event loop for bot start (running: {loop.is_running()})")
                    future = asyncio.run_coroutine_threadsafe(self.start(), loop)
                    # Add a callback to check the result
                    def check_result(fut):
                        try:
                            result = fut.result()
                            self.logger.info(f"Bot start completed with result: {result}")
                        except Exception as e:
                            self.logger.error(f"Bot start failed with exception: {e}")
                    future.add_done_callback(check_result)
                    self.logger.info("Bot start scheduled successfully")
                    return True
                else:
                    self.logger.error("No running event loop available for bot start")
                    return False
            except Exception as e:
                self.logger.error(f"Error getting event loop for bot start: {e}")
                return False
    
    def request_stop(self):
        """Request bot to stop (thread-safe)."""
        if not self.running:
            return False
        
        # Simply set the running flag to False, the bot loop will stop
        self.running = False
        return True
    
    def get_last_update(self):
        """Get timestamp of last price update."""
        return self.price_feed._last_update if hasattr(self.price_feed, '_last_update') else 0
    
    def get_uptime(self):
        """Get bot uptime as a formatted string."""
        return self._get_uptime_str()
    
    def get_portfolio(self):
        """Get portfolio information."""
        return {
            'value': self.strategy.portfolio_value if hasattr(self.strategy, 'portfolio_value') else 0.0,
            'profit': self.total_profits
        }
    
    def get_recent_trades(self, limit=50):
        """Get recent trades."""
        if hasattr(self.strategy, 'get_trade_history'):
            trades = self.strategy.get_trade_history()
            # Return most recent trades first, limiting to 'limit'
            return sorted(trades, key=lambda x: x.get('timestamp', ''), reverse=True)[:limit] if trades else []
        return []
    
    async def validate_trading_funds(self):
        """Validate that wallet has sufficient funds for trading in live mode."""
        if self.config['trading']['mode'] != 'live':
            return {'sufficient': True, 'mode': 'paper', 'message': 'Paper trading mode - no funds required'}
        
        try:
            # Get current balances using the solana client
            sol_balance = await self.solana_client.get_balance('SOL')
            usdt_balance = await self.solana_client.get_balance('USDT')
            
            # Define minimum requirements
            min_sol_required = 0.05  # Minimum SOL for transaction fees
            min_trading_balance = self.config['trading']['trade_amount'] * 2  # At least 2 trades worth
            
            issues = []
            warnings = []
            
            # Check SOL balance for transaction fees
            if sol_balance is None or sol_balance < min_sol_required:
                issues.append(f"Insufficient SOL for transaction fees. Required: {min_sol_required} SOL, Available: {sol_balance or 0}")
            elif sol_balance < 0.1:
                warnings.append(f"Low SOL balance. Recommended: 0.1+ SOL for fees, Available: {sol_balance}")
            
            # Check trading balance
            if usdt_balance is None or usdt_balance < min_trading_balance:
                issues.append(f"Insufficient USDT for trading. Required: ${min_trading_balance}, Available: ${usdt_balance or 0}")
            elif usdt_balance < self.config['trading']['trade_amount'] * 5:
                warnings.append(f"Low USDT balance. Recommended: ${self.config['trading']['trade_amount'] * 5}+ for sustained trading")
            
            # Determine overall status
            sufficient = len(issues) == 0
            
            result = {
                'sufficient': sufficient,
                'sol_balance': sol_balance,
                'usdt_balance': usdt_balance,
                'min_sol_required': min_sol_required,
                'min_trading_balance': min_trading_balance,
                'issues': issues,
                'warnings': warnings,
                'mode': 'live'
            }
            
            # Log results
            if not sufficient:
                self.logger.error("🚨 INSUFFICIENT FUNDS FOR LIVE TRADING:")
                for issue in issues:
                    self.logger.error(f"   ❌ {issue}")
                for warning in warnings:
                    self.logger.warning(f"   ⚠️ {warning}")
            elif warnings:
                self.logger.warning("⚠️ TRADING FUNDS WARNING:")
                for warning in warnings:
                    self.logger.warning(f"   ⚠️ {warning}")
            else:
                self.logger.info("✅ Sufficient funds for live trading")
                self.logger.info(f"   SOL: {sol_balance}, USDT: ${usdt_balance}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error validating trading funds: {e}")
            return {
                'sufficient': False,
                'error': str(e),
                'mode': 'live',
                'issues': [f"Failed to check wallet balance: {e}"]
            }

    def inject_test_trades(self, count=5):
        """Inject test trades for UI testing (single instance safe)."""
        import random
        import datetime
        
        self.logger.info(f"🧪 Injecting {count} test trades for UI testing")
        
        tokens = ['SOL/USDC', 'ETH/USDC', 'BTC/USDC', 'BONK/USDC', 'JTO/USDC', 'WIF/USDC']
        venues = ['jupiterV6', 'raydium', 'orca', 'openbook', 'phoenix', 'meteora']
        errors = [
            'Slippage exceeded maximum tolerance',
            'Insufficient liquidity for trade size',
            'RPC node timeout during transaction',
            'Price moved too quickly, arbitrage opportunity lost'
        ]
        
        for i in range(count):
            is_success = random.random() > 0.2  # 80% success rate
            token_pair = random.choice(tokens)
            buy_venue = random.choice(venues)
            sell_venue = random.choice([v for v in venues if v != buy_venue])
            amount = round(random.uniform(500, 5000), 2)
            profit = round(amount * random.uniform(0.0005, 0.005), 4) if is_success else 0
            
            trade = {
                'timestamp': datetime.datetime.now().isoformat(),
                'token_pair': token_pair,
                'buy_source': buy_venue,
                'sell_source': sell_venue,
                'success': is_success,
                'realized_profit': profit,
                'trade_amount': amount,
                'buy_price': round(random.uniform(10, 1000), 3),
                'sell_price': round(random.uniform(10, 1000), 3),
            }
            
            if not is_success:
                trade['error'] = random.choice(errors)
            
            # Add to strategy's trade history and update counters
            if hasattr(self.strategy, 'trade_history'):
                self.strategy.trade_history.append(trade)
                if hasattr(self.strategy, 'total_profit'):
                    self.strategy.total_profit += profit
                if hasattr(self.strategy, 'trades_executed'):
                    self.strategy.trades_executed += 1
                if is_success and hasattr(self.strategy, 'successful_trades'):
                    self.strategy.successful_trades += 1
                
                # Emit the trade_executed callback for real-time UI updates
                self._emit_trade_executed(trade)
                
            self.logger.info(f"🧪 Injected test trade {i+1}: {token_pair} - {'Success' if is_success else 'Failed'}")
        
        self.logger.info(f"🧪 Test trade injection complete. UI should now show trades via callback.")
    
    def start_trading(self):
        """API compatibility method for starting trading."""
        self.logger.info("start_trading() called, delegating to request_start()")
        return self.request_start()
        
    def stop_trading(self):
        """API compatibility method for stopping trading."""
        self.logger.info("stop_trading() called, delegating to request_stop()")
        return self.request_stop()
    
    def report_trade_error(self, error_message, error_code=None, trade_details=None):
        """
        Report a trade error to the UI if SocketIO is available.
        This is called by the strategy when a trade fails.
        
        Args:
            error_message: The error message to display
            error_code: Optional error code
            trade_details: Optional dict with details about the failed trade
        """
        self.logger.error(f"Trade error: {error_message}")
        
        # Prepare error data
        error_data = {
            'message': error_message,
            'timestamp': datetime.now().isoformat(),
            'code': error_code,
            'type': 'error',
            'success': False
        }
        
        if trade_details:
            error_data['trade'] = trade_details
        
        # Log to trade log if available
        if self.trade_logger:
            try:
                # Format the trade error data as JSON for structured logging
                error_json = json.dumps(error_data)
                self.trade_logger.error(error_json)
            except Exception as e:
                self.logger.error(f"Failed to log trade error to trade_log: {e}")
        
        # If we're in a Flask context with SocketIO, emit the error
        if hasattr(self, 'socketio'):
            try:
                self.socketio.emit('trade_error', error_data)
                self.logger.info("Trade error reported to UI via SocketIO")
            except Exception as e:
                self.logger.error(f"Failed to emit trade error: {e}")
        else:
            self.logger.warning("SocketIO not available to report trade error")
    
    def get_price_history(self, hours: int = 24):
        """
        Get price history for the specified number of hours.
        Used by the UI for the price chart.
        
        Args:
            hours: Number of hours of history to return
            
        Returns:
            List of price data points with timestamps
        """
        self.logger.debug(f"Getting price history for {hours} hours")
        
        try:
            # Get history from price feed if available
            if hasattr(self, 'price_feed') and self.price_feed:
                history = self.price_feed.get_history(hours)
                self.logger.info(f"Price feed returned {len(history) if history else 0} price points")
                if history:
                    return history
                    
            # Fallback if no history available
            current_price = self.get_current_price()
            self.logger.info(f"Current price data: {current_price}")
            
            if current_price and 'price' in current_price:
                # Return at least one data point (current price)
                fallback_data = [{
                    'timestamp': datetime.now().isoformat(),
                    'price': current_price['price'],
                    'source': current_price.get('source', 'current')
                }]
                self.logger.info(f"Returning fallback data with current price: {fallback_data}")
                return fallback_data
                
            # If no current price either, generate some test data for development
            self.logger.warning("No price data available, generating test data for chart")
            return self._generate_test_price_data(hours)
            
        except Exception as e:
            self.logger.error(f"Error getting price history: {e}")
            # Return test data as last resort
            return self._generate_test_price_data(hours)
            
    def _generate_test_price_data(self, hours: int = 12):
        """Generate test price data for development/debugging."""
        import random
        from datetime import timedelta
        
        test_data = []
        base_price = 180.0  # SOL base price
        current_time = datetime.now()
        
        # Generate data points every 30 minutes for the requested hours
        intervals = int(hours * 2)  # 2 intervals per hour (30 min each)
        
        for i in range(intervals):
            point_time = current_time - timedelta(minutes=30 * (intervals - i))
            # Add some realistic price variation
            variation = random.uniform(-0.05, 0.05)  # ±5%
            price = base_price * (1 + variation)
            
            test_data.append({
                'timestamp': point_time.isoformat(),
                'price': round(price, 2),
                'source': 'test'
            })
            
        self.logger.info(f"Generated {len(test_data)} test price points")
        return test_data


async def main():
    """Main application function."""
    # Load configuration
    config = load_config()
    
    # Setup logging
    trade_logger = setup_logging(config)
    logger = logging.getLogger(__name__)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🐎 Starting Workhorse Solana Arbitrage Bot")
    
    # Validate configuration
    wallet_private_key = config.get('wallet', {}).get('private_key', '')
    if not wallet_private_key and config.get('trading', {}).get('mode') == 'live':
        logger.error("Private key required for live trading mode")
        sys.exit(1)
    
    # Initialize arbitrage bot
    bot = ArbitrageBot(config, trade_logger)
    bot.loop = asyncio.get_event_loop()  # Store the main loop reference
    
    # Create Flask app
    app = create_app(config, bot)
    
    # Don't start bot automatically - user must start it manually
    # bot_task = asyncio.create_task(bot.start())
    
    # Give the app a moment to initialize
    await asyncio.sleep(1)
    
    try:
        # Run Flask app with gevent+socketio support
        import ssl
        import importlib.util
        
        web_config = config.get('web', {})
        host = web_config.get('host', '0.0.0.0')
        port = web_config.get('port', 5000)
        use_https = web_config.get('use_https', False)
        
        # HTTPS setup
        ssl_context = None
        cert_path = web_config.get('cert_path', 'ssl/cert.pem')
        key_path = web_config.get('key_path', 'ssl/key.pem')
            
        if use_https:
            # Check if certificate files exist
            if not (os.path.exists(cert_path) and os.path.exists(key_path)):
                logger.warning("SSL certificate files not found. Generating self-signed certificate...")
                try:
                    from generate_cert import generate_self_signed_cert
                    generate_self_signed_cert(cert_path, key_path)
                except ImportError:
                    logger.error("Could not generate SSL certificate. Make sure cryptography package is installed.")
                    logger.error("Run: pip install cryptography pyopenssl")
                    logger.warning("Falling back to HTTP (not secure).")
                    use_https = False
            else:
                logger.info(f"Using existing SSL certificates: {cert_path} and {key_path}")
            
        # Check if gevent is available
        gevent_available = importlib.util.find_spec('gevent') is not None
        websocket_handler_available = importlib.util.find_spec('geventwebsocket') is not None
        
        # Function to run the server
        def run_server():
            if gevent_available and websocket_handler_available:
                # Use gevent with websocket support
                from gevent import pywsgi
                from geventwebsocket.handler import WebSocketHandler
                
                if use_https and os.path.exists(cert_path) and os.path.exists(key_path):
                    logger.info(f"🔒 Starting secure web interface with gevent on https://{host}:{port}")
                    server = pywsgi.WSGIServer(
                        (host, port),
                        app,
                        handler_class=WebSocketHandler,
                        keyfile=key_path,
                        certfile=cert_path
                    )
                else:
                    logger.info(f"🌐 Starting web interface with gevent on http://{host}:{port} (not secure)")
                    server = pywsgi.WSGIServer(
                        (host, port),
                        app,
                        handler_class=WebSocketHandler
                    )
                    
                server.serve_forever()
                
            else:
                # Fallback to werkzeug server
                from werkzeug.serving import make_server
                
                if use_https and os.path.exists(cert_path) and os.path.exists(key_path):
                    try:
                        # Create SSL context with modern settings
                        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                        # Set modern cipher suites and protocols
                        ssl_context.options |= ssl.OP_NO_SSLv2
                        ssl_context.options |= ssl.OP_NO_SSLv3
                        ssl_context.options |= ssl.OP_NO_TLSv1
                        ssl_context.options |= ssl.OP_NO_TLSv1_1
                        
                        ssl_context.load_cert_chain(cert_path, key_path)
                        logger.info("SSL context created successfully.")
                        logger.info("Note: Browsers will show security warnings about the self-signed certificate.")
                        logger.info("This is normal - you'll need to click 'Advanced' and 'Accept the Risk' to proceed.")
                        
                        logger.info(f"🔒 Starting secure web interface on https://{host}:{port}")
                        server = make_server(host, port, app, threaded=True, ssl_context=ssl_context)
                    except Exception as e:
                        logger.error(f"Error setting up SSL: {str(e)}")
                        logger.warning("Falling back to HTTP (not secure).")
                        logger.info(f"🌐 Starting web interface on http://{host}:{port} (not secure)")
                        server = make_server(host, port, app, threaded=True)
                else:
                    logger.info(f"🌐 Starting web interface on http://{host}:{port} (not secure)")
                    server = make_server(host, port, app, threaded=True)
                    
                server.serve_forever()
        
        # Start the server in a daemon thread
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        
        if not gevent_available:
            logger.warning("gevent not found. For optimal socketio performance, install with: pip install gevent gevent-websocket")
        
        logger.info(f"Bot web interface started on {'https' if use_https else 'http'}://{host}:{port}")
        
        # Keep the main loop running
        while True:
            await asyncio.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        # Cleanup
        logger.info("Stopping trading bot...")
        if bot.is_running():
            await bot.stop()
        logger.info("🐎 Workhorse stopped")


if __name__ == "__main__":
    try:
        try:
            asyncio.run(main())
        except Exception as e:
            print(f"\n💥 Error details: {e}")
            print("Traceback:")
            import traceback
            traceback.print_exc()
    except KeyboardInterrupt:
        print("\n🐎 Workhorse stopped by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
