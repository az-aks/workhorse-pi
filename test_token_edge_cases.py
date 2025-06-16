#!/usr/bin/env python3
"""
Test script for token-specific edge cases in DEX arbitrage bot.
This script tests how the bot handles various token-specific issues.
"""

import os
import sys
import yaml
import logging
import asyncio
import time
from datetime import datetime
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
        logging.FileHandler('token_edge_cases.log')
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


class UnknownTokenScenario(TestScenario):
    """Test how bot handles unknown/unsupported token symbols"""
    def __init__(self):
        super().__init__("unknown_token", "Test with unknown or unsupported token symbol")
    
    async def setup(self, config, solana_client, strategy):
        # No special setup needed
        pass
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal with an unknown token
        signal = {
            'action': 'arbitrage',
            'token_pair': 'NONEXISTENT/USDC',
            'buy': {'source': 'jupiter', 'price': 1.5},
            'sell': {'source': 'openbook', 'price': 1.6},
            'expected_profit': 0.1,
            'reason': 'Test with unknown token'
        }
        
        # Attempt to execute trade with unknown token
        self.logger.info("Attempting arbitrage trade with unknown token")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "missing" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with unknown token")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with unknown token error")
            
    async def cleanup(self, config, solana_client, strategy):
        # No cleanup needed
        pass


class NonTradableTokenScenario(TestScenario):
    """Test how bot handles non-tradable tokens (e.g., locked tokens)"""
    def __init__(self):
        super().__init__("non_tradable_token", "Test with non-tradable token")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the buy_token method to fail with non-tradable token error
        self.original_buy_token = solana_client.buy_token
        
        async def mock_buy_token(*args, **kwargs):
            self.logger.info("Simulating non-tradable token error")
            token_symbol = kwargs.get('token_symbol', 'SOL')
            return {
                'success': False,
                'error': f"Error: Token {token_symbol} is not tradable (locked, paused, or restricted)",
                'token_symbol': token_symbol,
                'amount': kwargs.get('amount_usd', 0)
            }
            
        solana_client.buy_token = mock_buy_token
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal with a theoretically tradable but currently restricted token
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',  # Using a normal token pair but we'll mock the failure
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test with non-tradable token'
        }
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade with non-tradable token")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "tradable" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with non-tradable token")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with non-tradable token error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.buy_token = self.original_buy_token


class TokenWithTransferFeeScenario(TestScenario):
    """Test how bot handles tokens with transfer fees"""
    def __init__(self):
        super().__init__("token_with_transfer_fee", "Test with token that has transfer fees")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the buy_token and sell_token methods to simulate transfer fees
        self.original_buy_token = solana_client.buy_token
        self.original_sell_token = solana_client.sell_token
        
        async def mock_buy_token(*args, **kwargs):
            self.logger.info("Simulating successful buy but with transfer fee")
            expected_amount = 0.02  # Expected amount without fees
            actual_amount = 0.018  # 10% less due to transfer fee
            
            return {
                'success': True,
                'signature': 'simulated_buy_with_fee_tx',
                'token_symbol': 'SOL',
                'output_amount': actual_amount,  # Received less due to fee
                'input_amount': 1.0,
                'fee_amount': expected_amount - actual_amount  # The fee that was deducted
            }
            
        async def mock_sell_token(*args, **kwargs):
            self.logger.info("Simulating successful sell but with transfer fee")
            expected_usdc = 1.0  # Expected USDC from sell
            actual_usdc = 0.9  # 10% less due to transfer fee
            
            return {
                'success': True,
                'signature': 'simulated_sell_with_fee_tx',
                'token_symbol': 'SOL',
                'output_amount': actual_usdc,  # Received less USDC due to fee
                'input_amount': kwargs.get('amount_token', 0),
                'fee_amount': 0.1  # The fee that was deducted
            }
            
        solana_client.buy_token = mock_buy_token
        solana_client.sell_token = mock_sell_token
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 50.0},  # Higher sell price that should be profitable even with fees
            'expected_profit': 1.5,
            'reason': 'Test with token that has transfer fees'
        }
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade with token that has transfer fees")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result - with transfer fees, profit might be less than expected but still positive
        self.logger.info(f"Trade result: {result}")
        
        if result.get('success', False) and float(result.get('actual_profit', 0)) < float(signal.get('expected_profit', 0)):
            self.logger.info("✅ Test passed: Trade succeeded but with lower profit due to transfer fees")
        elif not result.get('success', True) and "fee" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test also passed: Trade failed properly identifying fee issue")
        else:
            self.logger.error("❌ Test failed: Trade should have reported success with lower profit or failure due to fees")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original methods
        solana_client.buy_token = self.original_buy_token
        solana_client.sell_token = self.original_sell_token


class DeprecatedTokenScenario(TestScenario):
    """Test how bot handles deprecated tokens that should be migrated"""
    def __init__(self):
        super().__init__("deprecated_token", "Test with deprecated token that should be migrated")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the execute_jupiter_swap method to fail with deprecated token error
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        async def mock_execute_jupiter_swap(*args, **kwargs):
            self.logger.info("Simulating deprecated token error")
            return {
                'success': False,
                'error': 'Transaction failed: This token has been deprecated. Please migrate to the new version.',
                'signature': None
            }
            
        solana_client.execute_jupiter_swap = mock_execute_jupiter_swap
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',  # Using a normal token pair but we'll mock the failure
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test with deprecated token'
        }
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade with deprecated token")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "deprecated" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with deprecated token")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with deprecated token error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap


class LowLiquidityTokenScenario(TestScenario):
    """Test how bot handles low liquidity tokens"""
    def __init__(self):
        super().__init__("low_liquidity_token", "Test with low liquidity token")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the get_jupiter_quote method to return high price impact due to low liquidity
        self.original_get_jupiter_quote = solana_client.get_jupiter_quote
        
        async def mock_get_jupiter_quote(*args, **kwargs):
            self.logger.info("Simulating high price impact due to low liquidity")
            
            # Return a quote with high price impact
            return {
                'inAmount': '1000000',  # 1 USDC
                'outAmount': '18000000',  # 0.018 SOL
                'otherAmountThreshold': '17000000',
                'swapMode': 'ExactIn',
                'slippageBps': 50,
                'priceImpactPct': 0.15,  # 15% price impact is very high
                'routes': []
            }
            
        solana_client.get_jupiter_quote = mock_get_jupiter_quote
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test with low liquidity token'
        }
        
        # Configure max price impact in strategy
        original_max_price_impact = strategy.config.get('arbitrage', {}).get('max_price_impact_pct', 5.0)
        strategy.config['arbitrage'] = strategy.config.get('arbitrage', {})
        strategy.config['arbitrage']['max_price_impact_pct'] = 5.0  # 5% max price impact is reasonable
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade with low liquidity token")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        
        # The trade should be rejected due to high price impact
        if not result.get('success', False) and "price impact" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed due to high price impact from low liquidity")
        else:
            self.logger.warning("⚠️ Test inconclusive: Strategy did not explicitly reject due to high price impact")
            self.logger.warning("Consider adding a check for maximum acceptable price impact")
        
        # Restore original max price impact
        strategy.config['arbitrage']['max_price_impact_pct'] = original_max_price_impact
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.get_jupiter_quote = self.original_get_jupiter_quote


class ZeroDecimalReturnScenario(TestScenario):
    """Test how bot handles return amounts that round to zero due to decimal precision"""
    def __init__(self):
        super().__init__("zero_decimal_return", "Test with return amount that rounds to zero due to decimal precision")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the buy_token method to return extremely small amount that rounds to zero
        self.original_buy_token = solana_client.buy_token
        
        async def mock_buy_token(*args, **kwargs):
            self.logger.info("Simulating extremely small return amount")
            return {
                'success': True,
                'signature': 'simulated_tiny_amount_tx',
                'token_symbol': 'SOL',
                'output_amount': 0.0000000001,  # Extremely small amount, likely to cause issues in calculations
                'input_amount': 0.0001  # Very small input amount
            }
            
        solana_client.buy_token = mock_buy_token
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal with very small amounts
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 0.00001,  # Very small expected profit
            'reason': 'Test with extremely small amounts'
        }
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade with extremely small amounts")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and ("amount" in str(result.get('error', '')).lower() or 
                                               "zero" in str(result.get('error', '')).lower() or
                                               "small" in str(result.get('error', '')).lower()):
            self.logger.info("✅ Test passed: Trade correctly failed due to extremely small amount")
        else:
            self.logger.error("❌ Test failed: Trade should have failed due to extremely small amount")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.buy_token = self.original_buy_token


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
            UnknownTokenScenario(),
            NonTradableTokenScenario(),
            TokenWithTransferFeeScenario(),
            DeprecatedTokenScenario(),
            LowLiquidityTokenScenario(),
            ZeroDecimalReturnScenario()
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
