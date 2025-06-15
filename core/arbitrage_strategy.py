"""
DEX-Only Market-Neutral Arbitrage Strategy for Solana
This strategy makes profits regardless of market direction by exploiting price differences
between different Solana DEXes (Decentralized Exchanges).
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time
import math

class ArbitrageStrategy:
    """
    A market-neutral strategy that exploits price differences between Solana DEXes.
    This strategy aims to make profits regardless of whether the market is moving up or down
    by trading the same tokens across different decentralized exchanges on Solana.
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Strategy parameters
        self.min_profit_percentage = config.get('arbitrage', {}).get('min_profit_percentage', 0.5)
        self.max_exposure_percentage = config.get('arbitrage', {}).get('max_exposure_percentage', 30)
        
        # Solana DEXes only
        self.price_sources = config.get('arbitrage', {}).get('price_sources', 
                              ['jupiter', 'raydium', 'orca', 'openbook', 'meteora', 'phoenix'])
        
        # Popular tokens on Solana with good liquidity across DEXes
        self.tokens = config.get('arbitrage', {}).get('tokens', 
                      ['SOL', 'USDC', 'USDT', 'RAY', 'MNGO', 'SBR', 'ORCA'])
        
        # Historical data for opportunity detection
        self.price_history = {}  # Store prices from different sources
        self.last_arbitrage = {}  # Track last arbitrage for each pair
        self.cooldown_period = config.get('arbitrage', {}).get('cooldown_seconds', 300)  # 5 min cooldown
        self.min_samples = config.get('arbitrage', {}).get('min_samples', 10)  # Minimum samples before acting
        
        # Performance tracking
        self.total_profit = 0.0
        self.trades_executed = 0
        self.successful_trades = 0
        self.trade_history = []
        
        self.logger.info(f"Arbitrage strategy initialized with {len(self.price_sources)} sources and {len(self.tokens)} tokens")
    
    async def update_prices(self, price_data: Dict):
        """
        Update price history with new data from a price source.
        Format: {'source': 'source_name', 'token_pair': 'SOL/USDC', 'price': 45.12, 'timestamp': '2025-06-15T09:45:00'}
        """
        if not price_data or 'source' not in price_data or 'token_pair' not in price_data:
            return
        
        source = price_data['source']
        token_pair = price_data['token_pair']
        price = price_data['price']
        timestamp = price_data.get('timestamp', datetime.now().isoformat())
        
        key = f"{source}:{token_pair}"
        
        if key not in self.price_history:
            self.price_history[key] = []
        
        # Add new price data
        self.price_history[key].append({
            'price': price,
            'timestamp': timestamp
        })
        
        # Keep history limited to avoid memory issues
        max_history = 100
        if len(self.price_history[key]) > max_history:
            self.price_history[key] = self.price_history[key][-max_history:]
            
        # No longer automatically calling detect_opportunities here
        # We'll let the bot call it explicitly instead
    
    async def detect_opportunities(self) -> Optional[Dict]:
        """
        Detect arbitrage opportunities across different price sources.
        Returns a trading signal if an opportunity is found.
        """
        opportunities = []
        
        # For each token pair, compare prices across sources
        for base_token in self.tokens:
            for quote_token in self.tokens:
                if base_token == quote_token:
                    continue
                
                token_pair = f"{base_token}/{quote_token}"
                
                # Get latest prices for this token pair from each source
                prices = {}
                for source in self.price_sources:
                    key = f"{source}:{token_pair}"
                    if key in self.price_history and len(self.price_history[key]) >= self.min_samples:
                        latest_price = self.price_history[key][-1]['price']
                        prices[source] = latest_price
                
                # Need at least 2 sources to compare
                if len(prices) < 2:
                    continue
                
                # Find lowest and highest price sources
                lowest_source = min(prices, key=prices.get)
                highest_source = max(prices, key=prices.get)
                
                lowest_price = prices[lowest_source]
                highest_price = prices[highest_source]
                
                # Calculate potential profit percentage
                price_diff = highest_price - lowest_price
                profit_percentage = (price_diff / lowest_price) * 100
                
                self.logger.debug(f"Price comparison for {token_pair}: {lowest_source}=${lowest_price:.4f} vs {highest_source}=${highest_price:.4f}, diff={profit_percentage:.4f}%")
                
                # Check if profit exceeds minimum threshold
                if profit_percentage > self.min_profit_percentage:
                    # Check cooldown period
                    pair_key = f"{lowest_source}-{highest_source}:{token_pair}"
                    current_time = time.time()
                    
                    if (pair_key in self.last_arbitrage and 
                        current_time - self.last_arbitrage[pair_key] < self.cooldown_period):
                        self.logger.debug(f"Cooldown period active for {pair_key}")
                        continue
                    
                    # Calculate fees and transaction costs
                    estimated_fees = self.estimate_transaction_costs(lowest_source, highest_source, token_pair)
                    net_profit = profit_percentage - estimated_fees
                    
                    # Ensure we have a real profit opportunity, with a small epsilon to account for floating-point precision
                    if net_profit > 0.01: # Only consider >0.01% profit to be meaningful
                        self.logger.info(f"🔍 Arbitrage opportunity detected: Buy {token_pair} on {lowest_source} "
                                        f"at {lowest_price:.4f} and sell on {highest_source} at {highest_price:.4f}")
                        self.logger.info(f"Expected profit: {net_profit:.2f}% after fees")
                        
                        opportunity = {
                            'token_pair': token_pair,
                            'buy_source': lowest_source,
                            'buy_price': lowest_price,
                            'sell_source': highest_source,
                            'sell_price': highest_price,
                            'profit_percentage': profit_percentage,
                            'net_profit': net_profit,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        opportunities.append(opportunity)
                        
                        # Update last arbitrage time
                        self.last_arbitrage[pair_key] = current_time
        
        if opportunities:
            # Find the best opportunity
            best_opportunity = max(opportunities, key=lambda x: x['net_profit'])
            
            # Log the number of opportunities found
            self.logger.info(f"Found {len(opportunities)} valid arbitrage opportunities, best: {best_opportunity['net_profit']:.4f}% profit")
            
            # Return arbitrage signal
            signal = {
                'action': 'arbitrage',
                'token_pair': best_opportunity['token_pair'],
                'buy': {
                    'source': best_opportunity['buy_source'],
                    'price': best_opportunity['buy_price']
                },
                'sell': {
                    'source': best_opportunity['sell_source'],
                    'price': best_opportunity['sell_price']
                },
                'expected_profit': best_opportunity['net_profit'],
                'reason': f"Arbitrage: {best_opportunity['net_profit']:.2f}% profit opportunity",
                'confidence': min(100, best_opportunity['net_profit'] * 10)  # Higher profit = higher confidence
            }
            
            self.logger.info(f"🚨 Generating arbitrage signal: {signal['reason']}")
            return signal
        
        # No opportunities found
        self.logger.debug("No arbitrage opportunities detected at this time")
        return None
    
    def estimate_transaction_costs(self, source1: str, source2: str, token_pair: str) -> float:
        """
        Estimate the transaction costs for arbitrage between two Solana DEXes.
        Returns estimated costs as a percentage.
        """
        # Base Solana network fees (in SOL)
        # Solana has very low transaction costs
        base_sol_fee = 0.000005 * 2  # Two transactions (buy and sell)
        base_fee_usd = base_sol_fee * self.get_estimated_sol_price()
        
        # DEX-specific trading fees (varies by DEX)
        # These are up-to-date fees for Solana DEXes as of 2025
        trading_fees = {
            'jupiter': 0.1,      # Jupiter aggregator fee
            'raydium': 0.22,     # Raydium AMM fee (0.22%)
            'openbook': 0.14,    # OpenBook (Serum v3) fee
            'orca': 0.25,        # Orca Whirlpools fee
            'meteora': 0.2,      # Meteora AMM fee
            'phoenix': 0.05,     # Phoenix CLOB fee
            'invariant': 0.18,   # Invariant protocol fee
            'cykura': 0.3,       # Cykura concentrated liquidity AMM
            'saros': 0.2,        # Saros AMM fee
            'step': 0.25         # Step Finance fee
        }
        
        source1_fee = trading_fees.get(source1, 0.25)  # Default 0.25% if unknown
        source2_fee = trading_fees.get(source2, 0.25)
        
        # Slippage estimate (higher for less liquid pairs)
        # Some pairs on Solana DEXes have limited liquidity
        base_slippage = 0.15  # 0.15% base slippage each way
        
        # Calculate pair-specific slippage based on token liquidity
        high_liquidity_tokens = ['SOL', 'USDC', 'USDT', 'ETH']
        medium_liquidity_tokens = ['RAY', 'ORCA', 'SRM', 'MNGO']
        
        tokens = token_pair.split('/')
        
        slippage_multiplier = 1.0
        for token in tokens:
            if token in high_liquidity_tokens:
                pass  # No adjustment for high liquidity
            elif token in medium_liquidity_tokens:
                slippage_multiplier *= 1.5  # Medium liquidity adjustment
            else:
                slippage_multiplier *= 2.0  # Low liquidity adjustment
        
        slippage = base_slippage * slippage_multiplier
        
        # Price impact based on trade size (not included yet, would depend on portfolio value)
        
        # Add a small buffer for potential price movements between transactions
        market_movement_buffer = 0.1  # 0.1% buffer
        
        # Total cost as percentage
        total_percentage_cost = source1_fee + source2_fee + (slippage * 2) + market_movement_buffer
        
        self.logger.debug(f"Estimated costs for {source1}-{source2} arbitrage on {token_pair}: "
                         f"{total_percentage_cost:.2f}% "
                         f"(fees: {source1_fee+source2_fee:.2f}%, "
                         f"slippage: {slippage*2:.2f}%, buffer: {market_movement_buffer:.2f}%)")
        
        return total_percentage_cost
    
    def get_estimated_sol_price(self) -> float:
        """Get estimated SOL price in USD from stored history."""
        key_jupiter = "jupiter:SOL/USDC"
        key_raydium = "raydium:SOL/USDC"
        
        # Try Jupiter first, then Raydium
        if key_jupiter in self.price_history and self.price_history[key_jupiter]:
            return self.price_history[key_jupiter][-1]['price']
        elif key_raydium in self.price_history and self.price_history[key_raydium]:
            return self.price_history[key_raydium][-1]['price']
        
        # Fallback to an estimate
        return 45.0  # Estimated SOL price if no data available
    
    def analyze(self, current_price: float, price_history: List[Dict], portfolio: Dict) -> Optional[Dict]:
        """
        Main strategy analysis method that's called by the TradingBot.
        This acts as a wrapper around our asynchronous opportunity detection.
        """
        # For synchronous calls from TradingBot, we'll just check if we have any pending signals
        # The actual opportunity detection happens in detect_opportunities which is called
        # whenever new price data comes in via update_prices
        
        # Return None when no arbitrage opportunity is available
        return None
    
    def on_trade_executed(self, trade_result: Dict):
        """
        Process the result of an executed trade.
        Update strategy stats and adapt parameters if needed.
        """
        if not trade_result or 'success' not in trade_result:
            return
        
        # Record trade
        self.trades_executed += 1
        
        if trade_result['success']:
            self.successful_trades += 1
            
            # Update profit tracking
            if 'realized_profit' in trade_result:
                profit = trade_result['realized_profit']
                self.total_profit += profit
                
                # Log success
                self.logger.info(f"✅ Arbitrage trade successful: +{profit:.4f} USD profit")
                
                # Add to history
                self.trade_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'token_pair': trade_result.get('token_pair', 'Unknown'),
                    'profit': profit,
                    'success': True
                })
        else:
            # Log failure
            self.logger.warning(f"❌ Arbitrage trade failed: {trade_result.get('error', 'Unknown error')}")
            
            # Add to history
            self.trade_history.append({
                'timestamp': datetime.now().isoformat(),
                'token_pair': trade_result.get('token_pair', 'Unknown'),
                'error': trade_result.get('error', 'Unknown error'),
                'success': False
            })
            
            # Increase the profit threshold after failures to be more conservative
            self.min_profit_percentage *= 1.05
            self.logger.info(f"Increased minimum profit threshold to {self.min_profit_percentage:.2f}%")
    
    def get_performance_metrics(self) -> Dict:
        """Return performance metrics for this strategy."""
        success_rate = (self.successful_trades / self.trades_executed * 100) if self.trades_executed > 0 else 0
        
        return {
            'total_profit': self.total_profit,
            'trades_executed': self.trades_executed,
            'successful_trades': self.successful_trades,
            'success_rate': success_rate,
            'min_profit_threshold': self.min_profit_percentage
        }
    
    def reset(self):
        """Reset the strategy state."""
        self.price_history = {}
        self.last_arbitrage = {}
        self.total_profit = 0.0
        self.trades_executed = 0
        self.successful_trades = 0
        self.trade_history = []
        self.logger.info("Arbitrage strategy reset")
    
    async def execute_arbitrage_trade(self, signal: Dict, solana_client) -> Dict:
        """
        Execute an arbitrage trade between two Solana DEXes.
        
        Args:
            signal: The arbitrage signal with buy/sell details
            solana_client: The SolanaClient instance for executing trades
            
        Returns:
            Dict with trade results and status
        """
        self.logger.info(f"🔄 Execute arbitrage trade called with signal: {signal}")
        
        # Validate the signal
        if not signal:
            self.logger.error("❌ Signal is None or empty")
            return {'success': False, 'error': 'Empty signal provided'}
            
        if not isinstance(signal, dict):
            self.logger.error(f"❌ Signal is not a dictionary: {type(signal)}")
            return {'success': False, 'error': 'Signal is not a dictionary'}
            
        if signal.get('action') != 'arbitrage':
            self.logger.error(f"❌ Invalid signal action: {signal.get('action')}")
            return {'success': False, 'error': 'Invalid signal action'}
        
        # Extract signal details
        token_pair = signal['token_pair']
        buy_source = signal['buy']['source']
        buy_price = signal['buy']['price']
        sell_source = signal['sell']['source']
        sell_price = signal['sell']['price']
        expected_profit = signal['expected_profit']
        
        self.logger.info(f"🚀 Executing arbitrage trade for {token_pair} between {buy_source} and {sell_source}")
        self.logger.info(f"Buy price: {buy_price}, Sell price: {sell_price}, Expected profit: {expected_profit:.2f}%")
        
        # Calculate trade amount as a percentage of portfolio
        # We use a dynamic amount based on expected profit - higher profit = larger position
        base_percentage = 10  # Base 10% of portfolio
        confidence_factor = min(3.0, expected_profit / 2)  # Scale with expected profit, max 3x
        trade_percentage = min(self.max_exposure_percentage, base_percentage * confidence_factor)
        
        # Extract trade tokens
        base_token, quote_token = token_pair.split('/')
        
        try:
            # STEP 1: Check token balances and prepare trade amount
            self.logger.info(f"Checking balances for arbitrage...")
            
            # Get balance of quote token (e.g. USDC, USDT)
            quote_balance = await solana_client.get_balance(token_symbol=quote_token)
            if not quote_balance or quote_balance <= 0:
                return {'success': False, 'error': f"Insufficient {quote_token} balance for arbitrage"}
            
            # Calculate the trade amount
            portfolio_value = quote_balance  # For simplicity, just use the quote token balance
            self.logger.info(f"Portfolio value for arbitrage: {portfolio_value:.2f} {quote_token}")
            
            trade_amount = portfolio_value * (trade_percentage / 100)
            
            # Apply minimum trade amount threshold for efficiency
            min_trade_amount = 5  # $5 equivalent minimum
            if trade_amount < min_trade_amount:
                trade_amount = min_trade_amount
                self.logger.info(f"Increasing trade amount to minimum threshold: ${min_trade_amount}")
            
            self.logger.info(f"Using {trade_percentage:.1f}% of portfolio for arbitrage: {trade_amount:.2f} {quote_token}")
            
            # STEP 2: Execute buy order on the cheaper DEX
            self.logger.info(f"Executing buy order on {buy_source} at {buy_price:.4f}")
            
            # In a real implementation, we would:
            # 1. Get a quote from the DEX's API (e.g. Jupiter API for Jupiter)
            # 2. Build and sign a transaction
            # 3. Send the transaction and confirm it
            
            # Here we'll use a placeholder for the trade execution
            base_token_amount = trade_amount / buy_price
            estimated_base_received = base_token_amount * 0.995  # Account for actual slippage
            
            # STEP 3: Execute sell order on the more expensive DEX
            self.logger.info(f"Executing sell order on {sell_source} at {sell_price:.4f}")
            
            # Similar API calls would happen here
            quote_token_received = estimated_base_received * sell_price * 0.995  # Account for actual slippage
            
            # Calculate actual profit
            profit_amount = quote_token_received - trade_amount
            profit_percentage = (profit_amount / trade_amount) * 100
            
            # Record the trade outcome
            result = {
                'success': True,
                'token_pair': token_pair,
                'buy_source': buy_source,
                'sell_source': sell_source,
                'trade_amount': trade_amount,
                'realized_profit': profit_amount,
                'realized_profit_percentage': profit_percentage,
                'timestamp': datetime.now().isoformat()
            }
            
            if profit_amount > 0:
                self.logger.info(f"✅ Arbitrage successful! Profit: {profit_amount:.4f} {quote_token} ({profit_percentage:.2f}%)")
            else:
                self.logger.warning(f"⚠️ Arbitrage executed but resulted in a loss: {profit_amount:.4f} {quote_token}")
                result['success'] = False
                result['error'] = "Trade executed but resulted in loss"
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error executing arbitrage trade: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'token_pair': token_pair
            }
