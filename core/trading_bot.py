"""
Core trading bot implementation
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable

from .price_feeds import PriceFeedManager
from .solana_client import SolanaClient
from .strategy import SimpleStrategy


class TradingBot:
    """Main trading bot class with memory-optimized design."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Bot state
        self._running = False
        self._trading_enabled = False
        self._start_time = None
        self._last_update = None
        
        # Trading components
        self.price_feed_manager = PriceFeedManager(config)
        # Always create SolanaClient, regardless of mode, for wallet info
        self.solana_client = SolanaClient(config)
        self.strategy = SimpleStrategy(config)
        
        # Data storage (memory optimized)
        max_history = config.get('performance', {}).get('max_price_history', 1000)
        max_trades = config.get('performance', {}).get('max_trade_history', 100)
        
        self._price_history = []
        self._trade_history = []
        self._max_price_history = max_history
        self._max_trade_history = max_trades
        
        # Portfolio (for paper trading)
        self._portfolio = {
            'balance_usd': config['trading']['paper_balance'],
            'balance_token': 0.0,
            'total_value': config['trading']['paper_balance'],
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0
        }
        
        # Callbacks for UI updates
        self._callbacks = {}
        
        # Alert system for insufficient funds
        self._last_funds_alert = None
        self._funds_alert_cooldown = 300  # 5 minutes between alerts
    
    def set_callbacks(self, callbacks: Dict[str, Callable]):
        """Set callback functions for real-time updates."""
        self._callbacks = callbacks
    
    def _emit_callback(self, event: str, data: Dict):
        """Emit callback if registered."""
        if event in self._callbacks:
            try:
                self._callbacks[event](data)
            except Exception as e:
                self.logger.error(f"Error in callback {event}: {e}")
    
    async def start(self):
        """Start the trading bot."""
        if self._running:
            return
        
        # Validate funds for live trading mode
        if self.config['trading']['mode'] == 'live':
            self.logger.info("🔍 Validating funds for live trading mode...")
            funds_validation = await self.validate_trading_funds()
            
            if not funds_validation['sufficient']:
                self.logger.error("🚨 CANNOT START: Insufficient funds for live trading")
                self._emit_callback('funds_alert', {
                    'type': 'startup_blocked',
                    'severity': 'critical',
                    'message': 'Cannot start bot in live mode: insufficient funds',
                    'details': funds_validation,
                    'timestamp': datetime.now().isoformat()
                })
                # Don't start the bot if funds are insufficient
                raise ValueError("Insufficient funds for live trading. Please fund wallet or switch to paper mode.")
            
            if funds_validation.get('warnings'):
                self.logger.warning("⚠️ Starting with low funds - monitor closely")
                self._send_funds_alert(funds_validation)
        
        self._running = True
        self._start_time = datetime.now()
        self.logger.info("🚀 Trading bot started")
        
        self._emit_callback('status_change', {
            'status': 'running',
            'message': 'Bot started successfully'
        })
        
        # Start price feed
        await self.price_feed_manager.start()
        
        # Main trading loop
        try:
            while self._running:
                await self._trading_cycle()
                
                # Update interval from config
                interval = self.config.get('price_feeds', {}).get('update_interval', 10)
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            self.logger.info("Trading bot cancelled")
        except Exception as e:
            self.logger.error(f"Error in trading loop: {e}")
        finally:
            await self._cleanup()
    
    async def _trading_cycle(self):
        """Execute one trading cycle."""
        try:
            # Get current price
            current_price = await self.price_feed_manager.get_current_price()
            
            if current_price:
                # Store price history (with memory limit)
                price_point = {
                    'timestamp': datetime.now().isoformat(),
                    'price': current_price['price'],
                    'source': current_price.get('source', 'unknown')
                }
                
                self._price_history.append(price_point)
                if len(self._price_history) > self._max_price_history:
                    self._price_history.pop(0)  # Remove oldest
                
                self._last_update = datetime.now()
                
                # Emit price update
                self._emit_callback('price_update', current_price)
                
                # Execute trading strategy if enabled
                if self._trading_enabled:
                    await self._execute_strategy(current_price)
        
        except Exception as e:
            self.logger.error(f"Error in trading cycle: {e}")
    
    async def _execute_strategy(self, price_data: Dict):
        """Execute trading strategy."""
        try:
            # Get trading signal from strategy
            signal = self.strategy.analyze(
                current_price=price_data['price'],
                price_history=self._price_history[-100:],  # Last 100 points
                portfolio=self._portfolio
            )
            
            if signal and signal['action'] != 'hold':
                await self._execute_trade(signal, price_data)
        
        except Exception as e:
            self.logger.error(f"Error executing strategy: {e}")
    
    async def _execute_trade(self, signal: Dict, price_data: Dict):
        """Execute a trade based on signal."""
        try:
            # Pre-trade funds validation for live mode
            if self.config['trading']['mode'] == 'live':
                funds_validation = await self.validate_trading_funds()
                if not funds_validation['sufficient']:
                    self.logger.error(f"🚨 Trade blocked due to insufficient funds:")
                    for issue in funds_validation['issues']:
                        self.logger.error(f"   ❌ {issue}")
                    self._send_funds_alert(funds_validation)
                    return  # Skip this trade
                elif funds_validation.get('warnings'):
                    # Log warnings but continue with trade
                    for warning in funds_validation['warnings']:
                        self.logger.warning(f"   ⚠️ {warning}")
            
            trade_amount = self.config['trading']['trade_amount']
            current_price = price_data['price']
            
            if signal['action'] == 'buy':
                # Calculate tokens to buy
                tokens_to_buy = trade_amount / current_price
                
                if self._portfolio['balance_usd'] >= trade_amount:
                    # Execute trade (paper or live)
                    if self.config['trading']['mode'] == 'paper':
                        # Paper trading
                        self._portfolio['balance_usd'] -= trade_amount
                        self._portfolio['balance_token'] += tokens_to_buy
                        success = True
                    else:
                        # Live trading
                        success = await self.solana_client.buy_token(
                            amount_usd=trade_amount,
                            token_symbol=self.config['trading']['token_symbol']
                        )
                    
                    if success:
                        trade_record = {
                            'timestamp': datetime.now().isoformat(),
                            'action': 'buy',
                            'amount_usd': trade_amount,
                            'amount_token': tokens_to_buy,
                            'price': current_price,
                            'signal': signal.get('reason', 'Strategy signal')
                        }
                        
                        self._add_trade_record(trade_record)
                        self._update_portfolio()
                        
                        self.logger.info(f"✅ Buy executed: {tokens_to_buy:.6f} tokens at ${current_price:.4f}")
                        self._emit_callback('trade_executed', trade_record)
            
            elif signal['action'] == 'sell':
                if self._portfolio['balance_token'] > 0:
                    # Sell all tokens
                    tokens_to_sell = self._portfolio['balance_token']
                    usd_received = tokens_to_sell * current_price
                    
                    if self.config['trading']['mode'] == 'paper':
                        # Paper trading
                        self._portfolio['balance_usd'] += usd_received
                        self._portfolio['balance_token'] = 0
                        success = True
                    else:
                        # Live trading
                        success = await self.solana_client.sell_token(
                            amount_token=tokens_to_sell,
                            token_symbol=self.config['trading']['token_symbol']
                        )
                    
                    if success:
                        trade_record = {
                            'timestamp': datetime.now().isoformat(),
                            'action': 'sell',
                            'amount_usd': usd_received,
                            'amount_token': tokens_to_sell,
                            'price': current_price,
                            'signal': signal.get('reason', 'Strategy signal')
                        }
                        
                        self._add_trade_record(trade_record)
                        self._update_portfolio()
                        
                        self.logger.info(f"✅ Sell executed: {tokens_to_sell:.6f} tokens at ${current_price:.4f}")
                        self._emit_callback('trade_executed', trade_record)
        
        except Exception as e:
            self.logger.error(f"Error executing trade: {e}")
    
    def _add_trade_record(self, trade: Dict):
        """Add trade to history with memory limit."""
        self._trade_history.append(trade)
        if len(self._trade_history) > self._max_trade_history:
            self._trade_history.pop(0)  # Remove oldest
    
    def _update_portfolio(self):
        """Update portfolio values."""
        if self._price_history:
            current_price = self._price_history[-1]['price']
            token_value = self._portfolio['balance_token'] * current_price
            self._portfolio['total_value'] = self._portfolio['balance_usd'] + token_value
            
            # Calculate unrealized PnL
            initial_balance = self.config['trading']['paper_balance']
            self._portfolio['unrealized_pnl'] = self._portfolio['total_value'] - initial_balance
    
    async def _cleanup(self):
        """Cleanup resources."""
        self._running = False
        await self.price_feed_manager.stop()
        self.logger.info("🛑 Trading bot stopped")
    
    # Public interface methods
    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._running
    
    def start_trading(self) -> bool:
        """Enable trading."""
        self._trading_enabled = True
        self.logger.info("📈 Trading enabled")
        self._emit_callback('status_change', {
            'status': 'trading',
            'message': 'Trading enabled'
        })
        return True
    
    def stop_trading(self) -> bool:
        """Disable trading."""
        self._trading_enabled = False
        self.logger.info("⏸️ Trading disabled")
        self._emit_callback('status_change', {
            'status': 'paused',
            'message': 'Trading disabled'
        })
        return True
    
    def get_current_price(self) -> Optional[Dict]:
        """Get current price data."""
        if self._price_history:
            latest = self._price_history[-1]
            return {
                'price': latest['price'],
                'timestamp': latest['timestamp'],
                'source': latest['source']
            }
        return None
    
    def get_portfolio(self) -> Dict:
        """Get current portfolio."""
        self._update_portfolio()
        return self._portfolio.copy()
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades."""
        return self._trade_history[-limit:] if self._trade_history else []
    
    def get_price_history(self, hours: float = 24) -> List[Dict]:
        """Get price history for specified hours."""
        self.logger.debug(f"Retrieving price history for {hours} hours")
        
        # If we have no price history, ask the price feed manager directly
        if not self._price_history and hasattr(self, '_price_feed_manager'):
            self.logger.info("No local price history, fetching from price feed manager")
            try:
                history = self._price_feed_manager.get_history(hours)
                self.logger.info(f"Got {len(history)} price points from price feed manager")
                
                # If we still don't have any price history, return empty list
                if not history:
                    self.logger.warning("No price history available from price feed manager")
                    return []
                    
                return history
            except Exception as e:
                self.logger.error(f"Error getting history from price feed manager: {e}")
                return []
        
        if not self._price_history:
            self.logger.warning("No price history available, returning empty list")
            return []
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            filtered_history = []
            for point in self._price_history:
                try:
                    if 'timestamp' not in point:
                        continue
                        
                    if isinstance(point['timestamp'], str):
                        # Handle ISO format timestamps with various suffixes
                        timestamp_str = point['timestamp']
                        if 'Z' in timestamp_str:
                            timestamp_str = timestamp_str.replace('Z', '+00:00')
                        point_time = datetime.fromisoformat(timestamp_str)
                    else:
                        point_time = point['timestamp']
                        
                    if point_time >= cutoff_time:
                        filtered_history.append(point)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid timestamp format in price point: {e}")
                    continue
            
            self.logger.info(f"Found {len(filtered_history)} price history points for {hours} hours")
            
            # If we don't have enough data points, just return what we have
            if len(filtered_history) < 5:
                self.logger.warning(f"Insufficient price history ({len(filtered_history)} points), returning available data")
                
            return filtered_history
        except Exception as e:
            self.logger.error(f"Error processing price history: {e}", exc_info=True)
            return []
            
    def _generate_synthetic_price_history(self, hours: float = 24) -> List[Dict]:
        """Generate synthetic price history when real data is not available."""
        from datetime import datetime, timedelta
        import random
        
        self.logger.warning(f"Generating {hours} hours of synthetic price history")
        
        # Use current price as baseline if available, otherwise use a reasonable default
        base_price = 100.0  # Default price if no reference is available
        
        # Try to get the current price from various sources
        if hasattr(self, '_current_price') and self._current_price:
            base_price = self._current_price
        elif hasattr(self, '_price_feed_manager') and getattr(self._price_feed_manager, '_current_price', None):
            base_price = self._price_feed_manager._current_price.get('price', 100.0)
            
        self.logger.info(f"Using base price {base_price} for synthetic data")
            
        # Generate synthetic price data
        now = datetime.now()
        history = []
        
        # Create a point every 5 minutes (12 per hour)
        intervals = int(hours * 12)
        
        for i in range(intervals):
            point_time = now - timedelta(minutes=5 * (intervals - i))
            
            # Add some random variation to the price to make it look realistic
            # Earlier points have more variation to create a realistic trend
            time_factor = i / intervals  # 0 to 1 as we approach now
            variation_range = 0.05 * (1 - time_factor) + 0.01  # Decreases from 5% to 1% variation
            variation = random.uniform(-variation_range, variation_range)
            
            # Create a slight trend
            trend = 0.01 * time_factor  # 0 to 1% upward trend
            
            point_price = base_price * (1 + variation + trend)
            
            history.append({
                'timestamp': point_time.isoformat(),
                'price': point_price,
                'source': 'synthetic'
            })
        
        # Add the current price as the latest point
        history.append({
            'timestamp': now.isoformat(),
            'price': base_price,
            'source': 'current'
        })
        
        self.logger.info(f"Generated {len(history)} synthetic price history points")
        return history
    
    def get_last_update(self) -> Optional[str]:
        """Get timestamp of last update."""
        return self._last_update.isoformat() if self._last_update else None
    
    def get_uptime(self) -> Optional[str]:
        """Get bot uptime."""
        if not self._start_time:
            return None
        
        uptime = datetime.now() - self._start_time
        return str(uptime).split('.')[0]  # Remove microseconds

    def get_status(self) -> Dict:
        """Get comprehensive bot status including wallet info."""
        # Basic status (running, trading)
        status = "running" if self._running else "stopped"
        if self._running and self._trading_enabled:
            status = "trading"
        elif self._running and not self._trading_enabled:
            status = "paused"
        
        # Trading mode from config
        trading_mode = self.config.get('trading', {}).get('mode', 'paper') 
        
        # Portfolio data
        self._update_portfolio()
        portfolio = self._portfolio.copy()
        
        # Wallet info
        wallet_info = self.get_wallet_info()
        
        # Return comprehensive status object
        return {
            'status': status,
            'mode': trading_mode,
            'wallet_info': wallet_info,
            'portfolio_value': portfolio.get('total_value', 0.0),
            'total_pnl': portfolio.get('unrealized_pnl', 0.0),
            'uptime': self.get_uptime() or "0s",
            'message': f"Bot is {status}",
            'trading_enabled': self._trading_enabled
        }
    
    def get_wallet_info(self) -> Dict:
        """Get wallet address and balance."""
        address = None
        balance = None
        
        # Check if we have a Solana client with a public key
        if self.solana_client and self.solana_client.public_key:
            address = str(self.solana_client.public_key)
            # Balance requires async, cannot get here
            # We'll handle balance in socketio_events.py's async function
        
        return {
            'address': address,
            'balance': balance
        }
    
    async def validate_trading_funds(self) -> Dict:
        """Validate that wallet has sufficient funds for trading in live mode."""
        if self.config['trading']['mode'] != 'live':
            return {'sufficient': True, 'mode': 'paper', 'message': 'Paper trading mode - no funds required'}
        
        try:
            # Get current balances
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
    
    def _should_send_funds_alert(self) -> bool:
        """Check if we should send a funds alert (rate limiting)."""
        if self._last_funds_alert is None:
            return True
        
        time_since_last = time.time() - self._last_funds_alert
        return time_since_last > self._funds_alert_cooldown
    
    def _send_funds_alert(self, validation_result: Dict):
        """Send funds alert through callback system."""
        if not self._should_send_funds_alert():
            return
        
        self._last_funds_alert = time.time()
        
        alert_data = {
            'type': 'insufficient_funds',
            'severity': 'critical' if not validation_result['sufficient'] else 'warning',
            'message': 'Insufficient funds for live trading',
            'details': validation_result,
            'timestamp': datetime.now().isoformat(),
            'action_required': 'Fund wallet before continuing live trading'
        }
        
        self.logger.critical(f"🚨 FUNDS ALERT: {alert_data['message']}")
        self._emit_callback('funds_alert', alert_data)
