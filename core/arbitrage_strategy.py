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
    
    def __init__(self, config: Dict, trading_bot=None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.trading_bot = trading_bot  # Store reference to trading_bot for reporting errors
        
        # Strategy parameters
        self.min_profit_percentage = config.get('arbitrage', {}).get('min_profit_percentage', 0.5)
        self.max_exposure_percentage = config.get('arbitrage', {}).get('max_exposure_percentage', 30)
        self.max_slippage_pct = config.get('arbitrage', {}).get('max_slippage_pct', 1.0)
        
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
                
                # Check if profit exceeds minimum threshold
                if profit_percentage > self.min_profit_percentage:
                    # Check cooldown period
                    pair_key = f"{lowest_source}-{highest_source}:{token_pair}"
                    current_time = time.time()
                    
                    if (pair_key in self.last_arbitrage and 
                        current_time - self.last_arbitrage[pair_key] < self.cooldown_period):
                        continue
                    
                    # Calculate fees and transaction costs
                    estimated_fees = self.estimate_transaction_costs(lowest_source, highest_source, token_pair)
                    net_profit = profit_percentage - estimated_fees
                    
                    # Ensure we have a real profit opportunity with enough margin to account for execution variance
                    if net_profit > 0.05: # Only consider >0.05% profit to be meaningful (increased safety margin)
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
            best_profit = best_opportunity.get('net_profit', 0)
            self.logger.info(f"Found {len(opportunities)} valid arbitrage opportunities, best: {best_profit:.4f}% profit")
            
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
                'reason': f"Arbitrage: {best_profit:.2f}% profit opportunity",
                'confidence': min(100, best_opportunity['net_profit'] * 10)  # Higher profit = higher confidence
            }
            
            reason = signal.get('reason', 'No reason provided')
            self.logger.info(f"🚨 Generating arbitrage signal: {reason}")
            return signal
        
        # No opportunities found
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
        base_slippage = 0.05  # Reduced to 0.05% base slippage for high liquidity pairs
        
        # Calculate pair-specific slippage based on token liquidity
        high_liquidity_tokens = ['SOL', 'USDC', 'USDT', 'ETH']
        medium_liquidity_tokens = ['RAY', 'ORCA', 'SRM', 'MNGO']
        
        tokens = token_pair.split('/')
        
        slippage_multiplier = 1.0
        # Check if both tokens are high liquidity
        if all(token in high_liquidity_tokens for token in tokens):
            slippage_multiplier = 0.5  # Reduce slippage for pairs like SOL/USDC
        else:
            # Apply token-specific multipliers
            for token in tokens:
                if token in high_liquidity_tokens:
                    pass  # No adjustment for high liquidity
                elif token in medium_liquidity_tokens:
                    slippage_multiplier *= 1.25  # Medium liquidity adjustment (reduced)
                else:
                    slippage_multiplier *= 1.5  # Low liquidity adjustment (reduced)
        
        slippage = base_slippage * slippage_multiplier
        
        # Price impact based on trade size (depends on portfolio value)
        # For paper trading, assume small trades with minimal impact
        
        # Add a small buffer for potential price movements between transactions
        # Reduced for paper trading and high liquidity pairs
        market_movement_buffer = 0.03  # 0.03% buffer (reduced)
        
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
                trade_record = {
                    'timestamp': datetime.now().isoformat(),
                    'token_pair': trade_result.get('token_pair', 'Unknown'),
                    'profit': profit,
                    'success': True,
                    'buy_source': trade_result.get('buy_source', 'Unknown'),
                    'sell_source': trade_result.get('sell_source', 'Unknown'),
                    'trade_amount': trade_result.get('trade_amount', 0),
                    'realized_profit': profit,
                    'buy_price': trade_result.get('buy_price', 0),
                    'sell_price': trade_result.get('sell_price', 0)
                }
                self.trade_history.append(trade_record)
        else:
            # Get the error message
            error_msg = trade_result.get('error', 'Unknown error')
            self.logger.warning(f"❌ Arbitrage trade failed: {error_msg}")
            
            # Add to history
            trade_record = {
                'timestamp': datetime.now().isoformat(),
                'token_pair': trade_result.get('token_pair', 'Unknown'),
                'error': error_msg,
                'success': False,
                'buy_source': trade_result.get('buy_source', 'Unknown'),
                'sell_source': trade_result.get('sell_source', 'Unknown'),
                'trade_amount': trade_result.get('trade_amount', 0),
                'realized_profit': 0,
                'buy_price': trade_result.get('buy_price', 0),
                'sell_price': trade_result.get('sell_price', 0)
            }
            self.trade_history.append(trade_record)
            
            # Report the error to the UI if the function is available
            if hasattr(self, 'trading_bot') and hasattr(self.trading_bot, 'report_trade_error'):
                try:
                    # Format a user-friendly error message
                    formatted_error = f"Failed trade ({trade_record['token_pair']}): {error_msg}"
                    self.trading_bot.report_trade_error(formatted_error, 
                                                       trade_details={
                                                           'pair': trade_record['token_pair'],
                                                           'amount': trade_record['trade_amount'],
                                                           'buy_source': trade_record['buy_source'],
                                                           'sell_source': trade_record['sell_source']
                                                       })
                    self.logger.info("Trade error reported to UI")
                except Exception as e:
                    self.logger.error(f"Failed to report trade error to UI: {e}")
            
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
            
            # Determine if we're in paper or mainnet mode
            trading_mode = self.config.get('trading', {}).get('mode', 'paper')
            self.logger.info(f"Trading mode: {trading_mode}")
            
            # Get token addresses
            base_token_mint = solana_client.token_addresses.get(base_token)
            quote_token_mint = solana_client.token_addresses.get(quote_token)
            
            if not base_token_mint or not quote_token_mint:
                return {
                    'success': False,
                    'error': f'Missing token mint addresses for {base_token} or {quote_token}',
                    'token_pair': token_pair
                }
            
            # STEP 2: Execute buy order - use the source with the lower price
            self.logger.info(f"STEP 2: Executing buy order on {buy_source} at {buy_price:.4f}")
            
            # Get expected output amount based on current market price
            expected_base_token_amount = trade_amount / buy_price
            
            # First check if we can get a quote to validate slippage
            if hasattr(solana_client, 'get_jupiter_quote') and trading_mode == 'mainnet':
                self.logger.info("Checking slippage before executing trade...")
                
                # Get token addresses
                base_token_mint = solana_client.token_addresses.get(base_token)
                quote_token_mint = solana_client.token_addresses.get(quote_token)
                
                # Convert to smallest units for the API
                token_decimals = solana_client.token_decimals.get(quote_token, 6)
                amount_smallest_units = int(trade_amount * (10 ** token_decimals))
                
                # Get quote from Jupiter
                quote = await solana_client.get_jupiter_quote(
                    quote_token_mint,  # Input is quote token (e.g., USDC)
                    base_token_mint,   # Output is base token (e.g., SOL)
                    amount_smallest_units
                )
                
                # Validate the slippage
                max_allowed_slippage = self.config.get('arbitrage', {}).get('max_slippage_pct', 1.0)
                slippage_result = await self.validate_quote_slippage(
                    quote, 
                    expected_base_token_amount,
                    max_allowed_slippage
                )
                
                if not slippage_result['valid']:
                    self.logger.warning(f"❌ Trade rejected due to slippage: {slippage_result['error']}")
                    return {
                        'success': False,
                        'error': f"Excessive slippage detected: {slippage_result['error']}",
                        'slippage_pct': slippage_result['slippage_pct'],
                        'token_pair': token_pair
                    }
                else:
                    self.logger.info(f"✅ Slippage validation passed: {slippage_result['slippage_pct']:.2f}%")
            
            # Execute the buy transaction
            buy_result = await solana_client.buy_token(
                amount_usd=trade_amount, 
                token_symbol=base_token, 
                quote_token=quote_token
            )
            
            if not buy_result.get('success', False):
                self.logger.error(f"Buy transaction failed: {buy_result.get('error', 'Unknown error')}")
                return {
                    'success': False, 
                    'error': f"Buy transaction failed: {buy_result.get('error', 'Unknown error')}",
                    'token_pair': token_pair,
                    'details': buy_result
                }
                
            # Get the amount of base token received from the buy transaction
            base_token_amount = buy_result.get('output_amount', trade_amount / buy_price)
            self.logger.info(f"Buy transaction successful! Received {base_token_amount:.6f} {base_token}")
            
            # STEP 3: Execute sell order on the more expensive DEX
            self.logger.info(f"STEP 3: Executing sell order on {sell_source} at {sell_price:.4f}")
            
            # Get expected output amount based on current market price
            expected_quote_token_amount = base_token_amount * sell_price
            
            # Check slippage for the sell transaction too
            if hasattr(solana_client, 'get_jupiter_quote') and trading_mode == 'mainnet':
                self.logger.info("Checking slippage before selling...")
                
                # Convert to smallest units for the API
                base_token_decimals = solana_client.token_decimals.get(base_token, 9)
                amount_smallest_units = int(base_token_amount * (10 ** base_token_decimals))
                
                # Get quote from Jupiter for selling
                quote = await solana_client.get_jupiter_quote(
                    base_token_mint,   # Input is base token (e.g., SOL)
                    quote_token_mint,  # Output is quote token (e.g., USDC)
                    amount_smallest_units
                )
                
                # Validate the slippage
                max_allowed_slippage = self.config.get('arbitrage', {}).get('max_slippage_pct', 1.0)
                slippage_result = await self.validate_quote_slippage(
                    quote, 
                    expected_quote_token_amount,
                    max_allowed_slippage
                )
                
                if not slippage_result['valid']:
                    self.logger.warning(f"❌ Sell rejected due to slippage: {slippage_result['error']}")
                    return {
                        'success': False,
                        'error': f"Excessive slippage on sell: {slippage_result['error']}",
                        'slippage_pct': slippage_result['slippage_pct'],
                        'token_pair': token_pair,
                        'buy_result': buy_result,  # Include the buy result for reference
                    }
                else:
                    self.logger.info(f"✅ Sell slippage validation passed: {slippage_result['slippage_pct']:.2f}%")
            
            # Execute the sell transaction
            sell_result = await solana_client.sell_token(
                amount_token=base_token_amount,
                token_symbol=base_token,
                quote_token=quote_token
            )
            
            if not sell_result.get('success', False):
                self.logger.error(f"Sell transaction failed: {sell_result.get('error', 'Unknown error')}")
                return {
                    'success': False,
                    'error': f"Sell transaction failed: {sell_result.get('error', 'Unknown error')}",
                    'token_pair': token_pair,
                    'buy_result': buy_result,
                    'details': sell_result
                }
                
            # Get the amount of quote token received from the sell transaction
            quote_token_received = sell_result.get('output_amount', base_token_amount * sell_price)
            self.logger.info(f"Sell transaction successful! Received {quote_token_received:.4f} {quote_token}")
            
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
                'base_token_amount': base_token_amount,
                'quote_token_received': quote_token_received,
                'realized_profit': profit_amount,
                'realized_profit_percentage': profit_percentage,
                'timestamp': datetime.now().isoformat(),
                'buy_transaction': buy_result.get('signature', 'paper-trade'),
                'sell_transaction': sell_result.get('signature', 'paper-trade'),
                'trading_mode': trading_mode
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
    
    def get_dex_fee(self, dex_name: str) -> float:
        """Get the trading fee percentage for a specific DEX."""
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
        return trading_fees.get(dex_name, 0.25)  # Default 0.25% if unknown
        
    async def validate_quote_slippage(self, quote_response: Dict, expected_output_amount: float, max_slippage_pct: float = 1.0) -> Dict:
        """
        Validate a quote for excessive slippage.
        
        Args:
            quote_response: The DEX quote response
            expected_output_amount: The expected output amount based on market price
            max_slippage_pct: Maximum allowed slippage percentage (default 1.0%)
            
        Returns:
            Dict with validation result: {'valid': bool, 'slippage_pct': float, 'error': Optional[str]}
        """
        if not quote_response or not quote_response.get('data'):
            return {'valid': False, 'slippage_pct': 0, 'error': 'Invalid quote response'}
            
        try:
            # Extract output amount and slippage info from quote
            output_amount = float(quote_response['data'].get('outAmount', 0))
            
            # Calculate slippage percentage
            if expected_output_amount <= 0 or output_amount <= 0:
                return {'valid': False, 'slippage_pct': 0, 'error': 'Invalid output amounts'}
                
            # Check if quote explicitly provides price impact
            price_impact_pct = 0
            if 'priceImpactPct' in quote_response['data']:
                try:
                    price_impact_pct = float(quote_response['data']['priceImpactPct'])
                    self.logger.info(f"Quote contains price impact info: {price_impact_pct}%")
                except (ValueError, TypeError):
                    self.logger.warning("Failed to parse price impact from quote")
                
            # Calculate our own slippage percentage
            actual_slippage_pct = ((expected_output_amount - output_amount) / expected_output_amount) * 100
            
            # Use the larger of our calculated slippage or the reported price impact
            effective_slippage = max(actual_slippage_pct, price_impact_pct)
            
            self.logger.info(f"Quote slippage validation - expected: {expected_output_amount:.4f}, "
                             f"actual: {output_amount:.4f}, slippage: {effective_slippage:.2f}%")
            
            # Check if slippage exceeds maximum
            if effective_slippage > max_slippage_pct:
                return {
                    'valid': False,
                    'slippage_pct': effective_slippage,
                    'error': f"Excessive slippage of {effective_slippage:.2f}% exceeds maximum allowed {max_slippage_pct}%"
                }
                
            return {'valid': True, 'slippage_pct': effective_slippage, 'error': None}
            
        except Exception as e:
            self.logger.error(f"Error validating quote slippage: {str(e)}")
            return {'valid': False, 'slippage_pct': 0, 'error': f"Error validating slippage: {str(e)}"}
    
    def get_trade_history(self) -> List[Dict]:
        """
        Return the trade history for UI display.
        Enhanced with additional fields needed by the UI.
        """
        # Return a copy to avoid external modifications
        enhanced_history = []
        
        for trade in self.trade_history:
            # Create a copy with normalized fields
            enhanced_trade = {
                'timestamp': trade.get('timestamp', ''),
                'token_pair': trade.get('token_pair', 'Unknown'),
                'success': trade.get('success', False),
                'realized_profit': trade.get('profit', 0),
                # Default values for missing fields
                'buy_source': trade.get('buy_source', ''),
                'sell_source': trade.get('sell_source', ''),
                'trade_amount': trade.get('trade_amount', 0)
            }
            
            enhanced_history.append(enhanced_trade)
            
        return enhanced_history
