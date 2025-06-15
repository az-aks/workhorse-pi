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
        
        self.logger.info("Trading bot initialized")
    
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
    
    def get_price_history(self, hours: int = 24) -> List[Dict]:
        """Get price history for specified hours."""
        if not self._price_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_history = []
        for point in self._price_history:
            point_time = datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00').replace('+00:00', ''))
            if point_time >= cutoff_time:
                filtered_history.append(point)
        
        return filtered_history
    
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
