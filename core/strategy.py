"""
Trading strategies for the bot
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class SimpleStrategy:
    """Simple momentum and mean reversion strategy."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Strategy parameters
        trading_config = config.get('trading', {})
        self.trade_amount = trading_config.get('trade_amount', 10.0)
        self.min_price_change = trading_config.get('min_price_change', 0.02)  # 2%
        self.max_trades_per_hour = trading_config.get('max_trades_per_hour', 6)
        self.min_trade_interval_minutes = trading_config.get('min_trade_interval_minutes', 10)
        
        # Risk management
        risk_config = config.get('risk', {})
        self.stop_loss = risk_config.get('stop_loss', 0.05)  # 5%
        self.take_profit = risk_config.get('take_profit', 0.03)  # 3%
        self.max_position_size = risk_config.get('max_position_size', 0.1)  # 10%
        
        # State tracking
        self.recent_trades = []
        self.last_trade_time = None
        self.entry_price = None
        
        self.logger.info("Simple strategy initialized")
    
    def analyze(self, current_price: float, price_history: List[Dict], portfolio: Dict) -> Optional[Dict]:
        """
        Analyze market conditions and return trading signal.
        
        Args:
            current_price: Current token price
            price_history: Recent price history
            portfolio: Current portfolio state
            
        Returns:
            Trading signal dict with action, reason, confidence
        """
        try:
            # Check if we can trade (rate limiting)
            if not self._can_trade():
                return None
            
            # Extract prices from history
            if len(price_history) < 5:  # Reduced from 10 for faster trading
                self.logger.debug(f"Not enough price history: {len(price_history)} < 5")
                return None  # Need minimum history
            
            prices = [point['price'] for point in price_history]
            
            # Calculate indicators
            signals = []
            
            # 0. Simple test strategy (remove this after testing)
            import random
            if len(price_history) >= 3 and random.random() < 0.1:  # 10% chance per cycle
                action = 'buy' if portfolio.get('balance_token', 0) == 0 else 'sell'
                test_signal = {
                    'action': action,
                    'reason': f'Test {action} signal',
                    'confidence': 0.7,
                    'type': 'test'
                }
                self.logger.info(f"🎲 Test signal generated: {test_signal}")
                signals.append(test_signal)
            
            # 1. Check for stop loss or take profit if we have a position
            position_signal = self._check_position_management(current_price, portfolio)
            if position_signal:
                return position_signal
            
            # 2. Momentum strategy
            momentum_signal = self._momentum_strategy(current_price, prices)
            if momentum_signal:
                signals.append(momentum_signal)
            
            # 3. Mean reversion strategy
            mean_reversion_signal = self._mean_reversion_strategy(current_price, prices)
            if mean_reversion_signal:
                signals.append(mean_reversion_signal)
            
            # 4. Volume/volatility checks
            volatility_signal = self._volatility_strategy(prices)
            if volatility_signal:
                signals.append(volatility_signal)
            
            # Combine signals and make decision
            final_signal = self._combine_signals(signals, portfolio)
            
            if final_signal:
                self._record_signal(final_signal)
            
            return final_signal
            
        except Exception as e:
            self.logger.error(f"Error in strategy analysis: {e}")
            return None
    
    def _can_trade(self) -> bool:
        """Check if we can execute a trade (rate limiting)."""
        now = datetime.now()
        
        # Remove trades older than 1 hour
        cutoff_time = now - timedelta(hours=1)
        self.recent_trades = [
            trade for trade in self.recent_trades 
            if trade > cutoff_time
        ]
        
        # Check if we've exceeded max trades per hour
        if len(self.recent_trades) >= self.max_trades_per_hour:
            return False
        
        # Check minimum time between trades (configurable)
        if self.last_trade_time:
            time_since_last = now - self.last_trade_time
            if time_since_last < timedelta(minutes=self.min_trade_interval_minutes):
                return False
        
        return True
    
    def _check_position_management(self, current_price: float, portfolio: Dict) -> Optional[Dict]:
        """Check for stop loss or take profit conditions."""
        token_balance = portfolio.get('balance_token', 0)
        
        if token_balance <= 0 or not self.entry_price:
            return None  # No position to manage
        
        price_change = (current_price - self.entry_price) / self.entry_price
        
        # Stop loss
        if price_change <= -self.stop_loss:
            return {
                'action': 'sell',
                'reason': f'Stop loss triggered: {price_change:.2%}',
                'confidence': 1.0,
                'type': 'risk_management'
            }
        
        # Take profit
        if price_change >= self.take_profit:
            return {
                'action': 'sell',
                'reason': f'Take profit triggered: {price_change:.2%}',
                'confidence': 1.0,
                'type': 'risk_management'
            }
        
        return None
    
    def _momentum_strategy(self, current_price: float, prices: List[float]) -> Optional[Dict]:
        """Simple momentum strategy based on recent price movement."""
        if len(prices) < 5:  # Reduced from 20
            return None
        
        # Calculate short and long moving averages
        short_ma = np.mean(prices[-3:])  # 3-period MA (reduced from 5)
        long_ma = np.mean(prices[-5:])   # 5-period MA (reduced from 20)
        
        # Calculate price change from short MA
        price_change = (current_price - short_ma) / short_ma
        
        # Strong upward momentum
        if current_price > short_ma > long_ma and abs(price_change) > self.min_price_change:
            return {
                'action': 'buy',
                'reason': f'Upward momentum: {price_change:.2%}',
                'confidence': min(abs(price_change) / 0.05, 1.0),  # Scale to 5% max
                'type': 'momentum'
            }
        
        # Strong downward momentum (for selling)
        if current_price < short_ma < long_ma and abs(price_change) > self.min_price_change:
            return {
                'action': 'sell',
                'reason': f'Downward momentum: {price_change:.2%}',
                'confidence': min(abs(price_change) / 0.05, 1.0),
                'type': 'momentum'
            }
        
        return None
    
    def _mean_reversion_strategy(self, current_price: float, prices: List[float]) -> Optional[Dict]:
        """Mean reversion strategy - buy low, sell high relative to average."""
        if len(prices) < 5:  # Reduced from 20
            return None
        
        # Calculate mean and standard deviation
        mean_price = np.mean(prices)
        std_price = np.std(prices)
        
        if std_price == 0:
            return None  # No volatility
        
        # Z-score (how many standard deviations from mean)
        z_score = (current_price - mean_price) / std_price
        
        # Buy when price is below mean (more sensitive)
        if z_score < -0.8:  # More than 0.8 std below mean
            return {
                'action': 'buy',
                'reason': f'Mean reversion buy: {z_score:.2f} std below mean',
                'confidence': min(abs(z_score) / 2.0, 1.0),  # Scale to 2 std max
                'type': 'mean_reversion'
            }
        
        # Sell when price is above mean (more sensitive)
        if z_score > 0.8:  # More than 0.8 std above mean
            return {
                'action': 'sell',
                'reason': f'Mean reversion sell: {z_score:.2f} std above mean',
                'confidence': min(abs(z_score) / 2.0, 1.0),
                'type': 'mean_reversion'
            }
        
        return None
    
    def _volatility_strategy(self, prices: List[float]) -> Optional[Dict]:
        """Check volatility conditions - avoid trading in high volatility."""
        if len(prices) < 10:
            return None
        
        # Calculate recent volatility
        recent_returns = []
        for i in range(1, len(prices)):
            returns = (prices[i] - prices[i-1]) / prices[i-1]
            recent_returns.append(returns)
        
        volatility = np.std(recent_returns) if recent_returns else 0
        
        # If volatility is too high, suggest holding
        if volatility > 0.1:  # 10% volatility threshold
            return {
                'action': 'hold',
                'reason': f'High volatility: {volatility:.2%}',
                'confidence': 0.8,
                'type': 'volatility'
            }
        
        return None
    
    def _combine_signals(self, signals: List[Dict], portfolio: Dict) -> Optional[Dict]:
        """Combine multiple signals into a final trading decision."""
        if not signals:
            return None
        
        # Separate by action
        buy_signals = [s for s in signals if s['action'] == 'buy']
        sell_signals = [s for s in signals if s['action'] == 'sell']
        hold_signals = [s for s in signals if s['action'] == 'hold']
        
        # If any hold signal, don't trade
        if hold_signals:
            return max(hold_signals, key=lambda x: x['confidence'])
        
        # Check position constraints
        token_balance = portfolio.get('balance_token', 0)
        usd_balance = portfolio.get('balance_usd', 0)
        total_value = portfolio.get('total_value', 0)
        
        # Process buy signals
        if buy_signals and usd_balance >= self.trade_amount:
            # Check position size limit - use current price from latest signal
            current_price = 0
            if buy_signals:
                # Extract current price from signal context (would be passed in real implementation)
                current_price = total_value / (usd_balance + token_balance) if (usd_balance + token_balance) > 0 else 0
            
            position_value = token_balance * current_price
            position_ratio = position_value / total_value if total_value > 0 else 0
            
            if position_ratio < self.max_position_size:
                best_buy = max(buy_signals, key=lambda x: x['confidence'])
                return best_buy
        
        # Process sell signals
        if sell_signals and token_balance > 0:
            best_sell = max(sell_signals, key=lambda x: x['confidence'])
            return best_sell
        
        return None
    
    def _record_signal(self, signal: Dict):
        """Record that we're acting on a signal."""
        now = datetime.now()
        self.recent_trades.append(now)
        self.last_trade_time = now
        
        # Record entry price for position management
        if signal['action'] == 'buy':
            # This would be set by the trading bot when the trade executes
            pass
        elif signal['action'] == 'sell':
            self.entry_price = None  # Clear entry price after selling
    
    def set_entry_price(self, price: float):
        """Set entry price for position management."""
        self.entry_price = price
        self.logger.info(f"Entry price set: ${price:.4f}")
    
    def get_strategy_stats(self) -> Dict:
        """Get strategy performance statistics."""
        return {
            'recent_trades_count': len(self.recent_trades),
            'last_trade_time': self.last_trade_time.isoformat() if self.last_trade_time else None,
            'entry_price': self.entry_price,
            'parameters': {
                'min_price_change': self.min_price_change,
                'max_trades_per_hour': self.max_trades_per_hour,
                'min_trade_interval_minutes': self.min_trade_interval_minutes,
                'stop_loss': self.stop_loss,
                'take_profit': self.take_profit,
                'max_position_size': self.max_position_size
            }
        }


class PaperTradingStrategy(SimpleStrategy):
    """Extended strategy with paper trading specific features."""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.paper_trades = []
        self.total_return = 0.0
        self.win_rate = 0.0
        
    def record_paper_trade(self, trade: Dict):
        """Record a paper trade for performance tracking."""
        self.paper_trades.append(trade)
        self._calculate_performance()
    
    def _calculate_performance(self):
        """Calculate strategy performance metrics."""
        if not self.paper_trades:
            return
        
        # Calculate total return
        initial_balance = self.config['trading']['paper_balance']
        current_value = self.paper_trades[-1].get('portfolio_value', initial_balance)
        self.total_return = (current_value - initial_balance) / initial_balance
        
        # Calculate win rate
        profitable_trades = sum(1 for trade in self.paper_trades 
                               if trade.get('pnl', 0) > 0)
        self.win_rate = profitable_trades / len(self.paper_trades) if self.paper_trades else 0
    
    def get_performance_stats(self) -> Dict:
        """Get detailed performance statistics."""
        base_stats = self.get_strategy_stats()
        base_stats.update({
            'total_trades': len(self.paper_trades),
            'total_return': self.total_return,
            'win_rate': self.win_rate,
            'recent_trades': self.paper_trades[-10:] if self.paper_trades else []
        })
        return base_stats
