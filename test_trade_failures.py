#!/usr/bin/env python3
"""
Test script for trade failure scenarios in DEX arbitrage bot
This script tests how the bot handles various trade failure scenarios
"""

import os
import sys
import yaml
import logging
import asyncio
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

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
        logging.FileHandler('trade_failure_tests.log')
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

class ZeroSolBalanceScenario(TestScenario):
    """Test how the bot handles zero SOL balance"""
    def __init__(self):
        super().__init__("zero_sol_balance", "Test with zero SOL balance in hot wallet")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the get_balance method to return 0 for SOL
        self.original_get_balance = solana_client.get_balance
        
        async def mock_get_balance(token_symbol='SOL'):
            if token_symbol == 'SOL':
                return 0.0
            return 100.0  # Return 100 USDC for other tokens
            
        solana_client.get_balance = mock_get_balance
        self.logger.info("Mocked get_balance to return zero SOL")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with zero SOL'
        }
        
        # Attempt to execute trade with zero SOL
        self.logger.info("Attempting arbitrage trade with zero SOL balance")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False):
            self.logger.info("✅ Test passed: Trade correctly failed with zero SOL")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with zero SOL")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.get_balance = self.original_get_balance
        self.logger.info("Restored original get_balance method")

class ZeroUsdcBalanceScenario(TestScenario):
    """Test how the bot handles zero USDC balance"""
    def __init__(self):
        super().__init__("zero_usdc_balance", "Test with zero USDC balance in hot wallet")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the get_balance method to return 0 for USDC
        self.original_get_balance = solana_client.get_balance
        
        async def mock_get_balance(token_symbol='SOL'):
            if token_symbol == 'USDC':
                return 0.0
            return 1.0  # Return 1 SOL for SOL
            
        solana_client.get_balance = mock_get_balance
        self.logger.info("Mocked get_balance to return zero USDC")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with zero USDC'
        }
        
        # Attempt to execute trade with zero USDC
        self.logger.info("Attempting arbitrage trade with zero USDC balance")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False):
            self.logger.info("✅ Test passed: Trade correctly failed with zero USDC")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with zero USDC")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.get_balance = self.original_get_balance
        self.logger.info("Restored original get_balance method")

class JupiterQuoteFailureScenario(TestScenario):
    """Test how the bot handles Jupiter quote API failures"""
    def __init__(self):
        super().__init__("jupiter_quote_failure", "Test with Jupiter quote API failure")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the get_jupiter_quote method to fail
        self.original_get_jupiter_quote = solana_client.get_jupiter_quote
        
        async def mock_get_jupiter_quote(*args, **kwargs):
            self.logger.info("Simulating Jupiter quote API failure")
            return None
            
        solana_client.get_jupiter_quote = mock_get_jupiter_quote
        self.logger.info("Mocked get_jupiter_quote to always fail")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with Jupiter quote failure'
        }
        
        # Attempt to execute trade with Jupiter quote failure
        self.logger.info("Attempting arbitrage trade with Jupiter quote failure")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "quote" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with Jupiter quote error")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with Jupiter quote error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.get_jupiter_quote = self.original_get_jupiter_quote
        self.logger.info("Restored original get_jupiter_quote method")

class SwapInstructionsFailureScenario(TestScenario):
    """Test how the bot handles swap instructions API failures"""
    def __init__(self):
        super().__init__("swap_instructions_failure", "Test with swap instructions API failure")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the get_jupiter_swap_instructions method to fail
        self.original_get_jupiter_swap_instructions = solana_client.get_jupiter_swap_instructions
        
        async def mock_get_jupiter_swap_instructions(*args, **kwargs):
            self.logger.info("Simulating swap instructions API failure")
            return None
            
        solana_client.get_jupiter_swap_instructions = mock_get_jupiter_swap_instructions
        self.logger.info("Mocked get_jupiter_swap_instructions to always fail")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with swap instructions failure'
        }
        
        # Attempt to execute trade with swap instructions failure
        self.logger.info("Attempting arbitrage trade with swap instructions failure")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "instruction" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with swap instructions error")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with swap instructions error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.get_jupiter_swap_instructions = self.original_get_jupiter_swap_instructions
        self.logger.info("Restored original get_jupiter_swap_instructions method")

class TransactionSubmissionFailureScenario(TestScenario):
    """Test how the bot handles transaction submission failures"""
    def __init__(self):
        super().__init__("transaction_submission_failure", "Test with transaction submission failure")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the execute_jupiter_swap method to fail during transaction submission
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        async def mock_execute_jupiter_swap(*args, **kwargs):
            self.logger.info("Simulating transaction submission failure")
            return {
                'success': False,
                'error': 'Transaction submission failed: RPC connection error',
                'signature': None
            }
            
        solana_client.execute_jupiter_swap = mock_execute_jupiter_swap
        self.logger.info("Mocked execute_jupiter_swap to simulate transaction submission failure")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with transaction submission failure'
        }
        
        # Attempt to execute trade with transaction submission failure
        self.logger.info("Attempting arbitrage trade with transaction submission failure")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "transaction" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with transaction submission error")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with transaction submission error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap
        self.logger.info("Restored original execute_jupiter_swap method")

class TransactionConfirmationFailureScenario(TestScenario):
    """Test how the bot handles transaction confirmation failures"""
    def __init__(self):
        super().__init__("transaction_confirmation_failure", "Test with transaction confirmation failure")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the execute_jupiter_swap method to fail during confirmation
        self.original_execute_jupiter_swap = solana_client.execute_jupiter_swap
        
        async def mock_execute_jupiter_swap(*args, **kwargs):
            self.logger.info("Simulating transaction confirmation failure")
            return {
                'success': False,
                'error': 'Transaction failed to confirm: timeout after 30s',
                'signature': 'simulated_tx_signature_that_failed_to_confirm'
            }
            
        solana_client.execute_jupiter_swap = mock_execute_jupiter_swap
        self.logger.info("Mocked execute_jupiter_swap to simulate confirmation failure")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with transaction confirmation failure'
        }
        
        # Attempt to execute trade with transaction confirmation failure
        self.logger.info("Attempting arbitrage trade with transaction confirmation failure")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "confirm" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with confirmation error")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with confirmation error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original method
        solana_client.execute_jupiter_swap = self.original_execute_jupiter_swap
        self.logger.info("Restored original execute_jupiter_swap method")

class BuySuccessSellFailureScenario(TestScenario):
    """Test how the bot handles successful buy but failed sell"""
    def __init__(self):
        super().__init__("buy_success_sell_failure", "Test with successful buy but failed sell")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the buy_token and sell_token methods
        self.original_buy_token = solana_client.buy_token
        self.original_sell_token = solana_client.sell_token
        
        async def mock_buy_token(*args, **kwargs):
            self.logger.info("Simulating successful buy transaction")
            return {
                'success': True,
                'signature': 'simulated_successful_buy_tx',
                'token_symbol': 'SOL',
                'output_amount': 0.1,
                'input_amount': 5.0
            }
            
        async def mock_sell_token(*args, **kwargs):
            self.logger.info("Simulating failed sell transaction")
            return {
                'success': False,
                'error': 'Sell transaction failed: slippage tolerance exceeded',
                'signature': None,
                'token_symbol': 'SOL'
            }
            
        solana_client.buy_token = mock_buy_token
        solana_client.sell_token = mock_sell_token
        self.logger.info("Mocked buy_token to succeed and sell_token to fail")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with buy success but sell failure'
        }
        
        # Attempt to execute trade with successful buy but failed sell
        self.logger.info("Attempting arbitrage trade with successful buy but failed sell")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "sell" in str(result.get('error', '')).lower() and "buy_result" in result:
            self.logger.info("✅ Test passed: Trade correctly handled successful buy but failed sell")
        else:
            self.logger.error("❌ Test failed: Trade should have reported buy success but sell failure")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original methods
        solana_client.buy_token = self.original_buy_token
        solana_client.sell_token = self.original_sell_token
        self.logger.info("Restored original buy_token and sell_token methods")

class InsufficientSOLForGasScenario(TestScenario):
    """Test how the bot handles insufficient SOL for gas fees"""
    def __init__(self):
        super().__init__("insufficient_sol_for_gas", "Test with insufficient SOL for gas fees")
    
    async def setup(self, config, solana_client, strategy):
        # Mock the get_balance method to return a very small amount of SOL
        self.original_get_balance = solana_client.get_balance
        self.original_buy_token = solana_client.buy_token
        
        async def mock_get_balance(token_symbol='SOL'):
            if token_symbol == 'SOL':
                return 0.000001  # Extremely low SOL balance, insufficient for gas
            return 100.0  # Return 100 USDC for other tokens
            
        async def mock_buy_token(*args, **kwargs):
            self.logger.info("Simulating failed buy due to insufficient SOL for gas")
            return {
                'success': False,
                'error': 'Transaction failed: Insufficient funds for gas',
                'token_symbol': 'SOL',
                'amount': kwargs.get('amount_usd', 0)
            }
            
        solana_client.get_balance = mock_get_balance
        solana_client.buy_token = mock_buy_token
        self.logger.info("Mocked get_balance to return tiny SOL amount and buy_token to fail with gas error")
        
    async def run(self, config, solana_client, strategy):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test arbitrage with insufficient SOL for gas'
        }
        
        # Attempt to execute trade with insufficient SOL for gas
        self.logger.info("Attempting arbitrage trade with insufficient SOL for gas")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        self.logger.info(f"Trade result: {result}")
        if not result.get('success', False) and "gas" in str(result.get('error', '')).lower():
            self.logger.info("✅ Test passed: Trade correctly failed with insufficient gas error")
        else:
            self.logger.error("❌ Test failed: Trade should have failed with insufficient gas error")
            
    async def cleanup(self, config, solana_client, strategy):
        # Restore original methods
        solana_client.get_balance = self.original_get_balance
        solana_client.buy_token = self.original_buy_token
        self.logger.info("Restored original get_balance and buy_token methods")

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
            ZeroSolBalanceScenario(),
            ZeroUsdcBalanceScenario(),
            JupiterQuoteFailureScenario(),
            SwapInstructionsFailureScenario(),
            TransactionSubmissionFailureScenario(),
            TransactionConfirmationFailureScenario(),
            BuySuccessSellFailureScenario(),
            InsufficientSOLForGasScenario()
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
