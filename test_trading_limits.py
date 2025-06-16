#!/usr/bin/env python3
"""
Test script for trading limits and safety mechanisms in DEX arbitrage bot.
This script tests how the bot enforces transaction size limits and daily trading limits.
"""

import os
import sys
import yaml
import logging
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

# Add project root to path to enable imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import core components
from core.solana_client import SolanaClient
from core.arbitrage_strategy import ArbitrageStrategy
from core.price_feeds import PriceFeedManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('trading_limits_tests.log')
    ]
)

logger = logging.getLogger(__name__)

class TestScenario:
    """Base class for test scenarios"""
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"test.{name}")
        
    async def setup(self, config, solana_client, strategy):
        """Setup the test scenario"""
        pass
        
    async def run(self, config, solana_client, strategy):
        """Run the test scenario"""
        pass
        
    async def cleanup(self, config, solana_client, strategy):
        """Cleanup after the test scenario"""
        pass


class MaxTransactionSizeScenario(TestScenario):
    """Test how bot enforces maximum transaction size limit"""
    def __init__(self):
        super().__init__("max_transaction_size", "Test enforcement of maximum transaction size limit")
    
    async def setup(self, config, solana_client, strategy):
        # Save original config values to restore later
        self.original_max_trade_size = config.get('trading', {}).get('max_trade_size', 100)
        self.original_typical_trade_size = config.get('trading', {}).get('typical_trade_size', 10)
        
        # Set a small max trade size for testing
        config['trading'] = config.get('trading', {})
        config['trading']['max_trade_size'] = 50.0  # $50 max
        config['trading']['typical_trade_size'] = 10.0  # $10 typical
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal with a large profit opportunity that might tempt larger trade size
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 50.0},  # Good profit margin
            'expected_profit': 5.0,  # Very high profit percentage
            'reason': 'Test with large profit opportunity'
        }
        
        # Mock the get_balance method to return a large balance
        original_get_balance = solana_client.get_balance
        
        async def mock_get_balance(token_symbol='SOL'):
            if token_symbol == 'USDC':
                return 10000.0  # Large USDC balance to ensure it's not a limiting factor
            return 100.0  # 100 SOL
            
        solana_client.get_balance = mock_get_balance
        
        # Monitor what size trade the strategy attempts to execute
        original_buy_token = solana_client.buy_token
        trade_size_used = None
        
        async def mock_buy_token(amount_usd=0, token_symbol='SOL', quote_token='USDC'):
            nonlocal trade_size_used
            trade_size_used = amount_usd
            self.logger.info(f"Strategy attempted to use trade size: ${amount_usd}")
            
            # Simulate successful trade
            return {
                'success': True,
                'signature': 'simulated_buy_tx',
                'token_symbol': token_symbol,
                'output_amount': amount_usd / 46.5,  # Convert to token amount
                'input_amount': amount_usd
            }
            
        solana_client.buy_token = mock_buy_token
        
        # Also mock sell_token to complete the trade
        original_sell_token = solana_client.sell_token
        
        async def mock_sell_token(amount_token=0, token_symbol='SOL', quote_token='USDC'):
            self.logger.info(f"Selling {amount_token} {token_symbol}")
            return {
                'success': True,
                'signature': 'simulated_sell_tx',
                'token_symbol': token_symbol,
                'output_amount': amount_token * 50.0,  # Higher sell price
                'input_amount': amount_token
            }
            
        solana_client.sell_token = mock_sell_token
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade with large profit opportunity")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result - trade should succeed but with a capped size
        self.logger.info(f"Trade result: {result}")
        
        # Restore original methods before assertions
        solana_client.get_balance = original_get_balance
        solana_client.buy_token = original_buy_token
        solana_client.sell_token = original_sell_token
        
        if result.get('success', False) and trade_size_used is not None:
            if trade_size_used <= config['trading']['max_trade_size']:
                self.logger.info(f"✅ Test passed: Trade size was limited to ${trade_size_used}, within max ${config['trading']['max_trade_size']}")
            else:
                self.logger.error(f"❌ Test failed: Trade size ${trade_size_used} exceeded max ${config['trading']['max_trade_size']}")
        else:
            self.logger.error("❌ Test failed: Trade didn't execute or size wasn't tracked")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original config values
        config['trading']['max_trade_size'] = self.original_max_trade_size
        config['trading']['typical_trade_size'] = self.original_typical_trade_size


class DailyVolumeLimitScenario(TestScenario):
    """Test how bot enforces daily trading volume limit"""
    def __init__(self):
        super().__init__("daily_volume_limit", "Test enforcement of daily trading volume limit")
    
    async def setup(self, config, solana_client, strategy):
        # Save original config values
        self.original_daily_volume_limit = config.get('trading', {}).get('daily_volume_limit', 1000)
        
        # Set a small daily limit for testing
        config['trading'] = config.get('trading', {})
        config['trading']['daily_volume_limit'] = 100.0  # $100 daily limit
        
        # Mock the strategy's trade tracking
        # First, check if the strategy has a trading history dictionary
        if not hasattr(strategy, 'trading_history') or not strategy.trading_history:
            strategy.trading_history = {}
            
        # Add some past trades to approach but not exceed the limit
        today = datetime.now().strftime('%Y-%m-%d')
        strategy.trading_history[today] = strategy.trading_history.get(today, 0) + 80.0  # $80 already traded today
        
        self.logger.info(f"Setup daily volume tracking: ${strategy.trading_history.get(today, 0)} / ${config['trading']['daily_volume_limit']}")
        
    async def run(self, config, solana_client, strategy):
        # Run two trades:
        # 1. A smaller trade that should still fit within the daily limit
        # 2. A larger trade that would exceed the daily limit and should be rejected
        
        # First trade - $15 which should still fit
        small_signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 0.6,
            'reason': 'Test small trade within daily limit'
        }
        
        # Mock methods to track what happens
        original_buy_token = solana_client.buy_token
        trade_attempts = []
        
        async def mock_buy_token(amount_usd=0, token_symbol='SOL', quote_token='USDC'):
            trade_attempts.append(amount_usd)
            self.logger.info(f"Strategy attempted trade: ${amount_usd}")
            
            return {
                'success': True,
                'signature': f'simulated_buy_tx_{len(trade_attempts)}',
                'token_symbol': token_symbol,
                'output_amount': amount_usd / 46.5,
                'input_amount': amount_usd
            }
            
        solana_client.buy_token = mock_buy_token
        
        # Also mock sell_token
        original_sell_token = solana_client.sell_token
        
        async def mock_sell_token(amount_token=0, token_symbol='SOL', quote_token='USDC'):
            return {
                'success': True,
                'signature': f'simulated_sell_tx_{len(trade_attempts)}',
                'token_symbol': token_symbol,
                'output_amount': amount_token * 47.1,
                'input_amount': amount_token
            }
            
        solana_client.sell_token = mock_sell_token
        
        # Execute small trade that should succeed
        self.logger.info("Attempting smaller trade (should succeed)")
        small_result = await strategy.execute_arbitrage_trade(small_signal, solana_client)
        self.logger.info(f"Small trade result: {small_result}")
        
        # Now attempt a larger trade that should be rejected due to daily limit
        large_signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 45.0},
            'sell': {'source': 'openbook', 'price': 48.0},
            'expected_profit': 3.0,
            'reason': 'Test large trade exceeding daily limit'
        }
        
        self.logger.info("Attempting larger trade (should be rejected or size-limited)")
        large_result = await strategy.execute_arbitrage_trade(large_signal, solana_client)
        self.logger.info(f"Large trade result: {large_result}")
        
        # Restore original methods
        solana_client.buy_token = original_buy_token
        solana_client.sell_token = original_sell_token
        
        # Verify the behavior
        if small_result.get('success', False):
            self.logger.info("✅ First test passed: Small trade was accepted within daily limit")
        else:
            self.logger.error("❌ First test failed: Small trade should have succeeded")
            
        today = datetime.now().strftime('%Y-%m-%d')
        current_volume = strategy.trading_history.get(today, 0)
        
        if current_volume <= config['trading']['daily_volume_limit']:
            self.logger.info(f"✅ Daily volume check passed: Current volume ${current_volume} is within limit ${config['trading']['daily_volume_limit']}")
        else:
            self.logger.error(f"❌ Daily volume check failed: Current volume ${current_volume} exceeds limit ${config['trading']['daily_volume_limit']}")
            
        # For the large trade, it should either be rejected or sized down
        if not large_result.get('success', False) and "daily limit" in str(large_result.get('error', '')).lower():
            self.logger.info("✅ Second test passed: Large trade was correctly rejected due to daily limit")
        elif large_result.get('success', False) and len(trade_attempts) > 1:
            # If it succeeded, the size must have been limited
            second_trade_size = trade_attempts[1] if len(trade_attempts) > 1 else 0
            remaining_allowance = config['trading']['daily_volume_limit'] - current_volume + second_trade_size
            
            if abs(second_trade_size - remaining_allowance) < 0.01:  # Allow for small rounding differences
                self.logger.info(f"✅ Second test passed: Large trade was correctly sized down to ${second_trade_size}")
            else:
                self.logger.error(f"❌ Second test failed: Large trade size ${second_trade_size} doesn't match remaining allowance ${remaining_allowance}")
        else:
            self.logger.error("❌ Second test failed: Large trade should have been rejected or sized down")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original config values
        config['trading']['daily_volume_limit'] = self.original_daily_volume_limit
        
        # Reset the trading history
        if hasattr(strategy, 'trading_history'):
            strategy.trading_history = {}


class MaxSlippageEnforcementScenario(TestScenario):
    """Test how bot enforces maximum slippage tolerance"""
    def __init__(self):
        super().__init__("max_slippage_enforcement", "Test enforcement of maximum slippage tolerance")
    
    async def setup(self, config, solana_client, strategy):
        # Save original Jupiter quote method
        self.original_get_jupiter_quote = solana_client.get_jupiter_quote
        
        # Mock the get_jupiter_quote method to verify slippage settings
        self.slippage_bps_used = None
        
        async def mock_get_jupiter_quote(input_mint=None, output_mint=None, amount=0, slippage_bps=50):
            # Capture the slippage_bps used
            self.slippage_bps_used = slippage_bps
            self.logger.info(f"Jupiter quote requested with slippage: {slippage_bps} bps")
            
            # Return a normal quote
            return {
                'inAmount': str(amount),
                'outAmount': str(int(amount * 0.02)),  # Simple conversion
                'otherAmountThreshold': str(int(amount * 0.019)),  # Slightly less for slippage
                'swapMode': 'ExactIn',
                'slippageBps': slippage_bps,
                'priceImpactPct': 0.01,
                'routes': []
            }
            
        solana_client.get_jupiter_quote = mock_get_jupiter_quote
        
        # Also need to mock other methods to complete the test
        self.original_get_jupiter_swap_instructions = solana_client.get_jupiter_swap_instructions
        
        async def mock_get_jupiter_swap_instructions(quote_response):
            self.logger.info("Returning mock swap instructions")
            return {
                'swapTransaction': 'mockBase64EncodedTransaction'
            }
            
        solana_client.get_jupiter_swap_instructions = mock_get_jupiter_swap_instructions
        
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        async def mock_execute_jupiter_swap(swap_transaction_base64):
            self.logger.info("Simulating successful swap execution")
            return {
                'success': True,
                'signature': 'mock_tx_signature_12345',
            }
            
        solana_client.execute_jupiter_swap = mock_execute_jupiter_swap
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test slippage enforcement'
        }
        
        # Mock buy_token and sell_token to track calls and enforce slippage
        original_buy_token = solana_client.buy_token
        original_sell_token = solana_client.sell_token
        
        async def mock_buy_token(*args, **kwargs):
            self.logger.info("Simulating successful buy transaction")
            return {
                'success': True,
                'signature': 'simulated_buy_tx',
                'token_symbol': 'SOL',
                'output_amount': 0.02,
                'input_amount': 1.0
            }
            
        async def mock_sell_token(*args, **kwargs):
            self.logger.info("Simulating successful sell transaction")
            return {
                'success': True,
                'signature': 'simulated_sell_tx',
                'token_symbol': 'SOL',
                'output_amount': 1.0,
                'input_amount': 0.02
            }
            
        solana_client.buy_token = mock_buy_token
        solana_client.sell_token = mock_sell_token
        
        # First verify the default max slippage in config
        max_slippage_bps = config.get('trading', {}).get('max_slippage_bps', 100)  # Default 1%
        self.logger.info(f"Maximum slippage set in config: {max_slippage_bps} bps")
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade to check slippage enforcement")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Restore original methods
        solana_client.buy_token = original_buy_token
        solana_client.sell_token = original_sell_token
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        
        if result.get('success', False) and self.slippage_bps_used is not None:
            if self.slippage_bps_used <= max_slippage_bps:
                self.logger.info(f"✅ Test passed: Used slippage {self.slippage_bps_used} bps is within max {max_slippage_bps} bps")
            else:
                self.logger.error(f"❌ Test failed: Used slippage {self.slippage_bps_used} bps exceeds max {max_slippage_bps} bps")
        else:
            self.logger.error("❌ Test failed: Trade didn't execute or slippage wasn't tracked")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original methods
        solana_client.get_jupiter_quote = self.original_get_jupiter_quote
        solana_client.get_jupiter_swap_instructions = self.original_get_jupiter_swap_instructions
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap


class MinimumProfitRequirementScenario(TestScenario):
    """Test how bot enforces minimum profit requirement"""
    def __init__(self):
        super().__init__("minimum_profit_requirement", "Test enforcement of minimum profit requirement")
    
    async def setup(self, config, solana_client, strategy):
        # Set a minimum profit requirement
        self.original_min_profit_usd = config.get('arbitrage', {}).get('min_profit_usd', 0.1)
        self.original_min_profit_pct = config.get('arbitrage', {}).get('min_profit_pct', 0.1)
        
        config['arbitrage'] = config.get('arbitrage', {})
        config['arbitrage']['min_profit_usd'] = 1.0  # $1 minimum profit
        config['arbitrage']['min_profit_pct'] = 1.0  # 1% minimum profit percentage
        
    async def run(self, config, solana_client, strategy):
        # Create three test signals:
        # 1. One with profit below the minimum USD requirement
        # 2. One with profit below the minimum percentage requirement
        # 3. One that meets both requirements
        
        low_usd_signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 100.0},
            'sell': {'source': 'openbook', 'price': 100.5},  # Only $0.50 profit per SOL
            'expected_profit': 0.5,
            'reason': 'Test with profit below min USD requirement'
        }
        
        low_pct_signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 100.0},
            'sell': {'source': 'openbook', 'price': 100.8},  # 0.8% profit, below 1% requirement
            'expected_profit': 0.8,
            'reason': 'Test with profit below min percentage requirement'
        }
        
        good_signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 100.0},
            'sell': {'source': 'openbook', 'price': 102.0},  # 2% profit, meets both requirements
            'expected_profit': 2.0,
            'reason': 'Test with profit meeting requirements'
        }
        
        # Set up tracking
        trade_attempts = []
        
        # Mock the buy_token method to track attempts
        original_buy_token = solana_client.buy_token
        
        async def mock_buy_token(amount_usd=0, token_symbol='SOL', quote_token='USDC'):
            trade_attempts.append({
                'amount_usd': amount_usd,
                'token_symbol': token_symbol,
                'quote_token': quote_token
            })
            self.logger.info(f"Buy attempt: ${amount_usd} of {token_symbol}")
            
            # Simulate successful trade
            return {
                'success': True,
                'signature': f'simulated_buy_tx_{len(trade_attempts)}',
                'token_symbol': token_symbol,
                'output_amount': amount_usd / 100.0,  # Buy at $100
                'input_amount': amount_usd
            }
            
        solana_client.buy_token = mock_buy_token
        
        # Also mock sell_token
        original_sell_token = solana_client.sell_token
        
        async def mock_sell_token(amount_token=0, token_symbol='SOL', quote_token='USDC'):
            self.logger.info(f"Sell attempt: {amount_token} {token_symbol}")
            
            # Determine sell price based on which signal is being processed
            if len(trade_attempts) == 1:  # First trade (low USD)
                sell_price = 100.5
            elif len(trade_attempts) == 2:  # Second trade (low percentage)
                sell_price = 100.8
            else:  # Third trade (good)
                sell_price = 102.0
                
            # Simulate successful sell
            return {
                'success': True,
                'signature': f'simulated_sell_tx_{len(trade_attempts)}',
                'token_symbol': token_symbol,
                'output_amount': amount_token * sell_price,
                'input_amount': amount_token
            }
            
        solana_client.sell_token = mock_sell_token
        
        # Run tests
        self.logger.info("\n--- Testing signal with profit below min USD ---")
        low_usd_result = await strategy.execute_arbitrage_trade(low_usd_signal, solana_client)
        self.logger.info(f"Result: {low_usd_result}")
        
        self.logger.info("\n--- Testing signal with profit below min percentage ---")
        low_pct_result = await strategy.execute_arbitrage_trade(low_pct_signal, solana_client)
        self.logger.info(f"Result: {low_pct_result}")
        
        self.logger.info("\n--- Testing signal with good profit ---")
        good_result = await strategy.execute_arbitrage_trade(good_signal, solana_client)
        self.logger.info(f"Result: {good_result}")
        
        # Restore original methods
        solana_client.buy_token = original_buy_token
        solana_client.sell_token = original_sell_token
        
        # Check results
        if not low_usd_result.get('success', False) and "profit" in str(low_usd_result.get('error', '')).lower():
            self.logger.info("✅ Test 1 passed: Trade correctly rejected due to insufficient USD profit")
        else:
            self.logger.error("❌ Test 1 failed: Trade with low USD profit should have been rejected")
            
        if not low_pct_result.get('success', False) and "profit" in str(low_pct_result.get('error', '')).lower():
            self.logger.info("✅ Test 2 passed: Trade correctly rejected due to insufficient percentage profit")
        else:
            self.logger.error("❌ Test 2 failed: Trade with low percentage profit should have been rejected")
            
        if good_result.get('success', True):
            self.logger.info("✅ Test 3 passed: Trade with good profit was accepted")
        else:
            self.logger.error("❌ Test 3 failed: Trade with good profit should have been accepted")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original config values
        config['arbitrage']['min_profit_usd'] = self.original_min_profit_usd
        config['arbitrage']['min_profit_pct'] = self.original_min_profit_pct


async def run_tests():
    """Run all test scenarios"""
    try:
        # Load configuration
        with open("arbitrage_config.yaml", 'r') as file:
            config = yaml.safe_load(file)
            logger.info("✅ Configuration loaded successfully")
        
        # Ensure we're in paper trading mode for safety
        config['trading']['mode'] = 'paper'
        
        # Initialize components
        solana_client = SolanaClient(config)
        strategy = ArbitrageStrategy(config)
        
        # Define test scenarios
        test_scenarios = [
            MaxTransactionSizeScenario(),
            DailyVolumeLimitScenario(),
            MaxSlippageEnforcementScenario(),
            MinimumProfitRequirementScenario()
        ]
        
        # Run each test scenario
        for scenario in test_scenarios:
            logger.info(f"\n{'=' * 70}")
            logger.info(f"🧪 Running test scenario: {scenario.name}")
            logger.info(f"📝 Description: {scenario.description}")
            logger.info(f"{'-' * 70}")
            
            try:
                # Setup
                await scenario.setup(config, solana_client, strategy)
                
                # Run test
                await scenario.run(config, solana_client, strategy)
                
            except Exception as e:
                logger.error(f"❌ Error in test scenario {scenario.name}: {str(e)}", exc_info=True)
            finally:
                # Cleanup
                try:
                    await scenario.cleanup(config, solana_client, strategy)
                except Exception as e:
                    logger.error(f"❌ Error during cleanup for {scenario.name}: {str(e)}", exc_info=True)
        
        logger.info(f"\n{'=' * 70}")
        logger.info("✅ All test scenarios completed")
        
    except Exception as e:
        logger.error(f"❌ Error in tests: {str(e)}", exc_info=True)
    finally:
        # Close the client
        if 'solana_client' in locals():
            await solana_client.close()

if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\nTests interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
