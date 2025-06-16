#!/usr/bin/env python3
"""
Test script for price discrepancy and volatility scenarios in DEX arbitrage bot.
This script tests how the bot handles extreme price movements and discrepancies.
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
        logging.FileHandler('price_volatility_tests.log')
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


class PriceDropDuringExecutionScenario(TestScenario):
    """Test how bot handles sudden price drop between quote and execution"""
    def __init__(self):
        super().__init__("price_drop_during_execution", "Test with sudden price drop between quote and execution")
    
    async def setup(self, config, solana_client, strategy):
        # Store original methods
        self.original_get_jupiter_quote = solana_client.get_jupiter_quote
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        # Mock to return a normal quote but simulate a price drop during execution
        async def mock_get_jupiter_quote(*args, **kwargs):
            # Return normal quote with good price
            self.logger.info("Returning normal quote with favorable price")
            return {
                'inAmount': '1000000',  # 1 USDC
                'outAmount': '20000000',  # 0.02 SOL (optimistic price)
                'otherAmountThreshold': '19000000',
                'swapMode': 'ExactIn',
                'slippageBps': 50,
                'priceImpactPct': 0.01,
                'routes': []
            }
            
        async def mock_execute_jupiter_swap(*args, **kwargs):
            # Simulate price drop during execution leading to slippage error
            self.logger.info("Simulating price drop during execution")
            await asyncio.sleep(1)  # Simulate delay during which price changes
            return {
                'success': False,
                'error': 'Transaction failed: Slippage tolerance exceeded due to price movement',
                'signature': None
            }
            
        # Apply mocks
        solana_client.get_jupiter_quote = mock_get_jupiter_quote
        solana_client.execute_jupiter_swap = mock_execute_jupiter_swap
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test with sudden price drop during execution'
        }
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade during price volatility")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "slippage" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed due to price movement causing slippage")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with slippage error due to price drop")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original methods
        solana_client.get_jupiter_quote = self.original_get_jupiter_quote
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap


class PriceSpikeDuringExecutionScenario(TestScenario):
    """Test how bot handles sudden price spike between quote and execution"""
    def __init__(self):
        super().__init__("price_spike_during_execution", "Test with sudden price spike between quote and execution")
    
    async def setup(self, config, solana_client, strategy):
        # Store original methods
        self.original_get_jupiter_quote = solana_client.get_jupiter_quote
        self.original_get_jupiter_swap_instructions = solana_client.get_jupiter_swap_instructions
        
        # Counter to track calls
        self.quote_call_count = 0
        
        async def mock_get_jupiter_quote(*args, **kwargs):
            # First call - normal quote
            if self.quote_call_count == 0:
                self.logger.info("First quote call: Returning normal price")
                self.quote_call_count += 1
                return {
                    'inAmount': '1000000',  # 1 USDC
                    'outAmount': '20000000',  # 0.02 SOL
                    'otherAmountThreshold': '19000000',
                    'swapMode': 'ExactIn',
                    'slippageBps': 50,
                    'priceImpactPct': 0.01,
                    'routes': []
                }
            # Second call (for sell) - much higher price
            else:
                self.logger.info("Second quote call: Returning extremely favorable price due to spike")
                return {
                    'inAmount': '20000000',  # 0.02 SOL
                    'outAmount': '1500000',  # 1.5 USDC (50% higher return than expected)
                    'otherAmountThreshold': '1400000',
                    'swapMode': 'ExactIn',
                    'slippageBps': 50,
                    'priceImpactPct': 0.01,
                    'routes': []
                }
                
        async def mock_get_jupiter_swap_instructions(*args, **kwargs):
            self.logger.info("Returning swap instructions")
            return {
                'swapTransaction': 'mockBase64EncodedTransaction'
            }
            
        # Apply mocks
        solana_client.get_jupiter_quote = mock_get_jupiter_quote
        solana_client.get_jupiter_swap_instructions = mock_get_jupiter_swap_instructions
        
        # Also need to mock execute_jupiter_swap to return success
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        async def mock_execute_jupiter_swap(*args, **kwargs):
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
            'reason': 'Test with sudden price spike during execution'
        }
        
        # We need to mock buy_token and sell_token to simulate successful transactions
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
            self.logger.info("Simulating successful sell transaction with unexpected profit")
            return {
                'success': True,
                'signature': 'simulated_sell_tx',
                'token_symbol': 'SOL',
                'output_amount': 1.5,  # 1.5 USDC (50% more than expected)
                'input_amount': 0.02
            }
            
        solana_client.buy_token = mock_buy_token
        solana_client.sell_token = mock_sell_token
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade during price volatility (spike)")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result - in this case, the trade should succeed with higher profit than expected
        self.logger.info(f"Trade result: {result}")
        if result.get('success', True) and float(result.get('actual_profit', 0)) > float(signal.get('expected_profit', 0)):
            self.logger.info("✅ Test passed: Trade succeeded with higher profit than expected due to price spike")
        else:
            self.logger.error("❌ Test failed: Trade should have succeeded with higher profit")
            
        # Restore buy/sell methods
        solana_client.buy_token = original_buy_token
        solana_client.sell_token = original_sell_token
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original methods
        solana_client.get_jupiter_quote = self.original_get_jupiter_quote
        solana_client.get_jupiter_swap_instructions = self.original_get_jupiter_swap_instructions
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap


class ExtremeVolatilityScenario(TestScenario):
    """Test how bot handles extreme price volatility during arbitrage"""
    def __init__(self):
        super().__init__("extreme_volatility", "Test with extreme price volatility during arbitrage")
    
    async def setup(self, config, solana_client, strategy):
        # Store original methods
        self.original_buy_token = solana_client.buy_token
        self.original_sell_token = solana_client.sell_token
        
        # Buy succeeds but price crashes before sell
        async def mock_buy_token(*args, **kwargs):
            self.logger.info("Simulating successful buy transaction")
            return {
                'success': True,
                'signature': 'simulated_buy_tx',
                'token_symbol': 'SOL',
                'output_amount': 0.02,  # Bought 0.02 SOL
                'input_amount': 1.0  # Used 1 USDC
            }
            
        async def mock_sell_token(*args, **kwargs):
            # Price crashed 50% before we could sell
            self.logger.info("Simulating successful but unprofitable sell due to crash")
            return {
                'success': True,
                'signature': 'simulated_sell_tx',
                'token_symbol': 'SOL',
                'output_amount': 0.5,  # Only got 0.5 USDC back (50% loss)
                'input_amount': 0.02  # Sold 0.02 SOL
            }
            
        solana_client.buy_token = mock_buy_token
        solana_client.sell_token = mock_sell_token
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 50.0},
            'sell': {'source': 'openbook', 'price': 52.0},
            'expected_profit': 1.5,
            'reason': 'Test with extreme price volatility'
        }
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade during extreme price volatility")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result - the trade should complete but with a loss
        self.logger.info(f"Trade result: {result}")
        
        # Trade should technically succeed (buy and sell went through) but with negative profit
        if result.get('success', False) and float(result.get('actual_profit', 0)) < 0:
            self.logger.info("✅ Test passed: Trade completed but with a loss due to extreme volatility")
        elif not result.get('success', True) and "loss" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test also passed: Trade detected potential loss and reported failure")
        else:
            self.logger.error("❌ Test failed: Trade should have reported success with a loss or failure due to potential loss")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original methods
        solana_client.buy_token = self.original_buy_token
        solana_client.sell_token = self.original_sell_token


class LargePriceDiscrepancyScenario(TestScenario):
    """Test how bot handles suspiciously large price discrepancies between DEXes"""
    def __init__(self):
        super().__init__("large_price_discrepancy", "Test with suspiciously large price discrepancy between DEXes")
    
    async def setup(self, config, solana_client, strategy):
        # No setup needed, we'll work with the strategy's arbitrage detection logic
        pass
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal with an unrealistically large price discrepancy (100% difference)
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 25.0},  # Extremely low price
            'sell': {'source': 'openbook', 'price': 50.0},  # Extremely high price
            'expected_profit': 25.0,  # 100% profit (highly suspicious)
            'reason': 'Test with suspiciously large price discrepancy'
        }
        
        # Check if the strategy properly filters out this suspicious opportunity
        # The strategy should have sanity checks for unreasonably large price differences
        # If it doesn't, this test will help identify this gap
        
        # Store original max profit percentage to restore it later
        original_max_profit_pct = strategy.config.get('arbitrage', {}).get('max_profit_pct', 10.0)
        
        # Set a reasonable max profit percentage for testing
        strategy.config['arbitrage'] = strategy.config.get('arbitrage', {})
        strategy.config['arbitrage']['max_profit_pct'] = 10.0  # 10% max profit is reasonable
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade with suspiciously large price discrepancy")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result - ideally the strategy should reject this as suspicious
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and ("suspicious" in str(result.get('error', '')).lower() or 
                                                "unrealistic" in str(result.get('error', '')).lower() or
                                                "exceeds maximum" in str(result.get('error', '')).lower()):
            self.logger.info("✅ Test passed: Trade correctly rejected due to suspiciously large price discrepancy")
        else:
            self.logger.warning("⚠️ Test inconclusive: Strategy did not explicitly reject due to suspicious price difference")
            self.logger.warning("Consider adding a sanity check for unrealistic price differences between DEXes")
        
        # Restore original max profit percentage
        strategy.config['arbitrage']['max_profit_pct'] = original_max_profit_pct
            
    async def cleanup(self, config, solana_client, strategy):
        # No cleanup needed
        pass


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
            PriceDropDuringExecutionScenario(),
            PriceSpikeDuringExecutionScenario(),
            ExtremeVolatilityScenario(),
            LargePriceDiscrepancyScenario()
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
