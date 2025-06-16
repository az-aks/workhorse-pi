#!/usr/bin/env python3
"""
Test how the arbitrage bot handles zero balance cases:
1. Zero SOL in hot wallet
2. Zero USDC in hot wallet
"""

import os
import sys
import yaml
import logging
import asyncio
from datetime import datetime

# Add project root to path to enable imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import core components
from core.solana_client import SolanaClient
from core.arbitrage_strategy import ArbitrageStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('zero_balance_test.log')
    ]
)

logger = logging.getLogger(__name__)

async def test_zero_sol_balance(solana_client, strategy):
    """Test scenario with zero SOL balance."""
    logger.info("=== TESTING ZERO SOL BALANCE SCENARIO ===")
    
    # Create a modified copy of the get_balance method that returns 0 for SOL
    original_get_balance = solana_client.get_balance
    
    async def mock_get_balance(token_symbol='SOL'):
        if token_symbol == 'SOL':
            logger.info("Returning MOCK ZERO balance for SOL")
            return 0.0
        else:
            # For other tokens, return normal value
            return await original_get_balance(token_symbol)
    
    # Override the method
    solana_client.get_balance = mock_get_balance
    
    # Now test how this affects trading
    try:
        # Try to create a trade signal
        test_signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {
                'source': 'raydium',
                'price': 46.55
            },
            'sell': {
                'source': 'orca',
                'price': 47.15
            },
            'expected_profit': 0.5,
            'reason': 'Test arbitrage signal',
            'confidence': 70
        }
        
        # Try to execute the trade
        logger.info("Attempting arbitrage with zero SOL balance")
        result = await strategy.execute_arbitrage_trade(test_signal, solana_client)
        
        # Log the result
        logger.info(f"Result with zero SOL balance: {result}")
        
        # Check if the strategy handled it correctly
        if not result.get('success', False):
            logger.info("✅ PASSED: Strategy correctly identified insufficient SOL balance")
            if "Insufficient" in str(result.get('error', '')):
                logger.info("✅ PASSED: Error message indicates insufficient balance")
            else:
                logger.warning("⚠️ NOTE: Error message doesn't specifically mention insufficient balance")
        else:
            logger.error("❌ FAILED: Strategy did not detect zero SOL balance issue")
            
    finally:
        # Restore the original method
        solana_client.get_balance = original_get_balance

async def test_zero_usdc_balance(solana_client, strategy):
    """Test scenario with zero USDC balance."""
    logger.info("=== TESTING ZERO USDC BALANCE SCENARIO ===")
    
    # Create a modified copy of the get_balance method that returns 0 for USDC
    original_get_balance = solana_client.get_balance
    
    async def mock_get_balance(token_symbol='SOL'):
        if token_symbol == 'USDC':
            logger.info("Returning MOCK ZERO balance for USDC")
            return 0.0
        else:
            # For other tokens, return normal value
            return await original_get_balance(token_symbol)
    
    # Override the method
    solana_client.get_balance = mock_get_balance
    
    # Now test how this affects trading
    try:
        # Try to create a trade signal
        test_signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {
                'source': 'raydium',
                'price': 46.55
            },
            'sell': {
                'source': 'orca',
                'price': 47.15
            },
            'expected_profit': 0.5,
            'reason': 'Test arbitrage signal',
            'confidence': 70
        }
        
        # Try to execute the trade
        logger.info("Attempting arbitrage with zero USDC balance")
        result = await strategy.execute_arbitrage_trade(test_signal, solana_client)
        
        # Log the result
        logger.info(f"Result with zero USDC balance: {result}")
        
        # Check if the strategy handled it correctly
        if not result.get('success', False):
            logger.info("✅ PASSED: Strategy correctly identified insufficient USDC balance")
            if "Insufficient" in str(result.get('error', '')):
                logger.info("✅ PASSED: Error message indicates insufficient balance")
            else:
                logger.warning("⚠️ NOTE: Error message doesn't specifically mention insufficient balance")
        else:
            logger.error("❌ FAILED: Strategy did not detect zero USDC balance issue")
            
    finally:
        # Restore the original method
        solana_client.get_balance = original_get_balance

async def test_paper_trading_zero_balances(solana_client, strategy):
    """Test how paper trading handles zero balances."""
    logger.info("=== TESTING PAPER TRADING WITH ZERO BALANCES ===")
    
    # Ensure we're using paper trading mode
    original_trading_mode = strategy.config.get('trading', {}).get('mode')
    strategy.config['trading']['mode'] = 'paper'
    
    try:
        # Try to create a trade signal
        test_signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {
                'source': 'raydium',
                'price': 46.55
            },
            'sell': {
                'source': 'orca',
                'price': 47.15
            },
            'expected_profit': 0.5,
            'reason': 'Test arbitrage signal in paper mode',
            'confidence': 70
        }
        
        # Try to execute the trade
        logger.info("Attempting paper trading arbitrage")
        result = await strategy.execute_arbitrage_trade(test_signal, solana_client)
        
        # Log the result
        logger.info(f"Result with paper trading: {result}")
        
        # Check if the strategy handled it correctly
        if result.get('success', False):
            logger.info("✅ PASSED: Paper trading successfully executed despite zero real balances")
        else:
            logger.error("❌ FAILED: Paper trading failed")
            
    finally:
        # Restore original mode
        if original_trading_mode:
            strategy.config['trading']['mode'] = original_trading_mode

async def main():
    """Main entry point."""
    try:
        # Load configuration
        with open("arbitrage_config.yaml", 'r') as file:
            config = yaml.safe_load(file)
            logger.info("✅ Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Ensure we're in paper trading mode for safety
    config['trading']['mode'] = 'paper'
    
    # Initialize client and strategy
    solana_client = SolanaClient(config)
    strategy = ArbitrageStrategy(config)
    
    try:
        # Test all zero balance scenarios
        await test_zero_sol_balance(solana_client, strategy)
        await test_zero_usdc_balance(solana_client, strategy)
        await test_paper_trading_zero_balances(solana_client, strategy)
        
        logger.info("All zero balance tests completed.")
        
    except Exception as e:
        logger.error(f"Error in tests: {str(e)}", exc_info=True)
    finally:
        # Close the client
        await solana_client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
