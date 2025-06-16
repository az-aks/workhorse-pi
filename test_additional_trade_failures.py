#!/usr/bin/env python3
"""
Additional test script for trade failure scenarios in DEX arbitrage bot.
This script tests more complex and edge-case trade failure scenarios.
"""

import os
import sys
import yaml
import logging
import asyncio
import time
import json
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
        logging.FileHandler('additional_trade_failures.log')
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


class InvalidQuoteDataScenario(TestScenario):
    """Test how the bot handles malformed or invalid Jupiter quote data"""
    def __init__(self):
        super().__init__("invalid_quote_data", "Test with malformed/invalid Jupiter quote data")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the get_jupiter_quote method to return malformed data
        self.original_get_jupiter_quote = solana_client.get_jupiter_quote
        
        async def mock_get_jupiter_quote(*args, **kwargs):
            self.logger.info("Simulating malformed Jupiter quote data")
            return {
                # Missing essential fields like 'outAmount' or with incorrect types
                'inAmount': 'not-a-number',
                'slippageBps': 'fifty',  # Should be an integer
                'otherAmountThreshold': None,  # Should be a string
                'swapMode': 1234  # Should be a string
            }
            
        solana_client.get_jupiter_quote = mock_get_jupiter_quote
        self.logger.info("Mocked get_jupiter_quote to return malformed data")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with malformed Jupiter quote data'
        }
        
        # Attempt to execute trade with malformed Jupiter quote
        self.logger.info("Attempting arbitrage trade with malformed Jupiter quote data")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False):
            self.logger.info("✅ Test passed: Trade correctly failed with malformed quote data")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with malformed quote data")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.get_jupiter_quote = self.original_get_jupiter_quote
        self.logger.info("Restored original get_jupiter_quote method")


class SlippageExceededScenario(TestScenario):
    """Test how the bot handles slippage tolerance exceeded errors"""
    def __init__(self):
        super().__init__("slippage_exceeded", "Test with slippage tolerance exceeded")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the execute_jupiter_swap method to fail with slippage error
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        async def mock_execute_jupiter_swap(*args, **kwargs):
            self.logger.info("Simulating slippage tolerance exceeded error")
            return {
                'success': False,
                'error': 'Transaction failed: Slippage tolerance exceeded',
                'signature': 'simulated_failed_slippage_tx'
            }
            
        solana_client.execute_jupiter_swap = mock_execute_jupiter_swap
        self.logger.info("Mocked execute_jupiter_swap to fail with slippage error")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with slippage tolerance exceeded'
        }
        
        # Attempt to execute trade with slippage error
        self.logger.info("Attempting arbitrage trade with slippage tolerance exceeded")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "slippage" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with slippage error")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with slippage error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap
        self.logger.info("Restored original execute_jupiter_swap method")


class InvalidSwapInstructionScenario(TestScenario):
    """Test how the bot handles malformed swap instruction data"""
    def __init__(self):
        super().__init__("invalid_swap_instruction", "Test with malformed swap instructions")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the get_jupiter_swap_instructions method to return malformed data
        self.original_get_jupiter_swap_instructions = solana_client.get_jupiter_swap_instructions
        
        async def mock_get_jupiter_swap_instructions(*args, **kwargs):
            self.logger.info("Simulating malformed swap instructions")
            return {
                # Missing the swapTransaction field or with invalid data
                'otherData': 'some_value',
                'error': None
            }
            
        solana_client.get_jupiter_swap_instructions = mock_get_jupiter_swap_instructions
        self.logger.info("Mocked get_jupiter_swap_instructions to return malformed data")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with malformed swap instructions'
        }
        
        # Attempt to execute trade with malformed swap instructions
        self.logger.info("Attempting arbitrage trade with malformed swap instructions")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "instructions" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with malformed swap instructions")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with malformed swap instructions")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.get_jupiter_swap_instructions = self.original_get_jupiter_swap_instructions
        self.logger.info("Restored original get_jupiter_swap_instructions method")


class PartialBuyFailedSellScenario(TestScenario):
    """Test how the bot handles a partial buy that succeeded but with less tokens than expected"""
    def __init__(self):
        super().__init__("partial_buy_failed_sell", "Test with partial buy (less tokens than expected) that causes sell to fail")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the buy_token and sell_token methods
        self.original_buy_token = solana_client.buy_token
        self.original_sell_token = solana_client.sell_token
        
        async def mock_buy_token(*args, **kwargs):
            self.logger.info("Simulating successful but partial buy transaction (less tokens than expected)")
            return {
                'success': True,
                'signature': 'simulated_partial_buy_tx',
                'token_symbol': 'SOL',
                'output_amount': 0.001,  # Very small amount, not enough to profitably sell
                'input_amount': 5.0
            }
            
        async def mock_sell_token(*args, **kwargs):
            self.logger.info("Simulating failed sell transaction due to insufficient tokens")
            return {
                'success': False,
                'error': 'Sell transaction failed: Amount too small to cover fees',
                'signature': None,
                'token_symbol': 'SOL'
            }
            
        solana_client.buy_token = mock_buy_token
        solana_client.sell_token = mock_sell_token
        self.logger.info("Mocked buy_token to return partial amount and sell_token to fail")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with partial buy and failed sell'
        }
        
        # Attempt to execute trade
        self.logger.info("Attempting arbitrage trade with partial buy and failed sell")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "buy_result" in result and result.get('buy_result', {}).get('success', False):
            self.logger.info("✅ Test passed: Trade correctly handled partial buy and failed sell")
        else:
            self.logger.error("❌ Test failed: Trade should have reported partial buy and failed sell")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original methods
        solana_client.buy_token = self.original_buy_token
        solana_client.sell_token = self.original_sell_token
        self.logger.info("Restored original buy_token and sell_token methods")


class RpcRateLimitExceededScenario(TestScenario):
    """Test how the bot handles RPC rate limit exceeded errors"""
    def __init__(self):
        super().__init__("rpc_rate_limit_exceeded", "Test with RPC rate limit exceeded")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the client.send_transaction method to fail with rate limit error
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        async def mock_execute_jupiter_swap(*args, **kwargs):
            self.logger.info("Simulating RPC rate limit exceeded error")
            return {
                'success': False,
                'error': 'Transaction failed: RPC rate limit exceeded. Please retry after some time.',
                'signature': None
            }
            
        solana_client.execute_jupiter_swap = mock_execute_jupiter_swap
        self.logger.info("Mocked execute_jupiter_swap to fail with rate limit error")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with RPC rate limit exceeded'
        }
        
        # Attempt to execute trade with RPC rate limit error
        self.logger.info("Attempting arbitrage trade with RPC rate limit exceeded")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "rate limit" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with rate limit error")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with rate limit error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap
        self.logger.info("Restored original execute_jupiter_swap method")


class TokenAccountNotFoundScenario(TestScenario):
    """Test how the bot handles token account not found errors"""
    def __init__(self):
        super().__init__("token_account_not_found", "Test with token account not found error")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the execute_jupiter_swap method to fail with token account error
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        async def mock_execute_jupiter_swap(*args, **kwargs):
            self.logger.info("Simulating token account not found error")
            return {
                'success': False,
                'error': 'Transaction failed: Token account does not exist',
                'signature': None
            }
            
        solana_client.execute_jupiter_swap = mock_execute_jupiter_swap
        self.logger.info("Mocked execute_jupiter_swap to fail with token account not found")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with token account not found'
        }
        
        # Attempt to execute trade with token account not found
        self.logger.info("Attempting arbitrage trade with token account not found")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "token account" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with token account error")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with token account error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap
        self.logger.info("Restored original execute_jupiter_swap method")


class BlockhashExpiredScenario(TestScenario):
    """Test how the bot handles blockhash expired errors"""
    def __init__(self):
        super().__init__("blockhash_expired", "Test with blockhash expired error")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the execute_jupiter_swap method to fail with blockhash expired
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        async def mock_execute_jupiter_swap(*args, **kwargs):
            self.logger.info("Simulating blockhash expired error")
            return {
                'success': False,
                'error': 'Transaction failed: Blockhash expired',
                'signature': 'simulated_blockhash_expired_tx'
            }
            
        solana_client.execute_jupiter_swap = mock_execute_jupiter_swap
        self.logger.info("Mocked execute_jupiter_swap to fail with blockhash expired")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with blockhash expired'
        }
        
        # Attempt to execute trade with blockhash expired
        self.logger.info("Attempting arbitrage trade with blockhash expired")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "blockhash" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with blockhash expired error")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with blockhash expired error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap
        self.logger.info("Restored original execute_jupiter_swap method")


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
            InvalidQuoteDataScenario(),
            SlippageExceededScenario(),
            InvalidSwapInstructionScenario(),
            PartialBuyFailedSellScenario(),
            RpcRateLimitExceededScenario(),
            TokenAccountNotFoundScenario(),
            BlockhashExpiredScenario()
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
