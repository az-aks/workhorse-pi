#!/usr/bin/env python3
"""
Test script for wallet balance boundary cases
This script tests how the bot handles zero or low balances
"""

import os
import sys
import yaml
import logging
import asyncio
from decimal import Decimal

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
        logging.FileHandler('balance_tests.log')
    ]
)

logger = logging.getLogger(__name__)

async def test_get_balance_with_wallet_file():
    """Test getting balance using the wallet file"""
    logger.info("=" * 70)
    logger.info("TEST: get_balance with actual wallet file")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Initialize client with the default config
    solana_client = SolanaClient(config)
    
    # Get SOL balance
    sol_balance = await solana_client.get_balance('SOL')
    logger.info(f"SOL balance: {sol_balance}")
    
    # Get USDC balance
    usdc_balance = await solana_client.get_balance('USDC')
    logger.info(f"USDC balance: {usdc_balance}")
    
    # Close client
    await solana_client.close()

async def test_zero_sol_balance():
    """Test how the bot handles zero SOL balance"""
    logger.info("=" * 70)
    logger.info("TEST: Zero SOL balance scenario")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration where balances will be mocked
    config_with_mock = config.copy()
    config_with_mock['trading']['mode'] = 'paper'
    
    # Initialize client and strategy
    solana_client = SolanaClient(config_with_mock)
    strategy = ArbitrageStrategy(config_with_mock)
    
    # Override the get_balance method
    original_get_balance = solana_client.get_balance
    
    async def mock_get_balance(token_symbol='SOL'):
        if token_symbol == 'SOL':
            logger.info("Mocking zero SOL balance")
            return 0.0
        else:
            logger.info(f"Mocking 100 {token_symbol} balance")
            return 100.0
    
    # Apply mock
    solana_client.get_balance = mock_get_balance
    
    # Test with a zero SOL balance
    sol_balance = await solana_client.get_balance('SOL')
    logger.info(f"Mocked SOL balance: {sol_balance}")
    
    # Create a test arbitrage signal
    signal = {
        'action': 'arbitrage',
        'token_pair': 'SOL/USDC',
        'buy': {
            'source': 'jupiter',
            'price': 46.5
        },
        'sell': {
            'source': 'openbook',
            'price': 47.1
        },
        'expected_profit': 1.2,
        'reason': 'Test arbitrage signal'
    }
    
    # Try to execute the trade
    logger.info("Attempting to execute arbitrage with zero SOL balance...")
    result = await strategy.execute_arbitrage_trade(signal, solana_client)
    
    # Log the result
    logger.info(f"Trade execution result with zero SOL: {result}")
    if result.get('success', False):
        logger.warning("⚠️ The trade executed successfully despite zero SOL balance!")
    else:
        logger.info("✅ The trade failed as expected with zero SOL balance")
    
    # Restore original method
    solana_client.get_balance = original_get_balance
    
    # Close client
    await solana_client.close()

async def test_zero_usdc_balance():
    """Test how the bot handles zero USDC balance"""
    logger.info("=" * 70)
    logger.info("TEST: Zero USDC balance scenario")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration where balances will be mocked
    config_with_mock = config.copy()
    config_with_mock['trading']['mode'] = 'paper'
    
    # Initialize client and strategy
    solana_client = SolanaClient(config_with_mock)
    strategy = ArbitrageStrategy(config_with_mock)
    
    # Override the get_balance method
    original_get_balance = solana_client.get_balance
    
    async def mock_get_balance(token_symbol='SOL'):
        if token_symbol == 'USDC':
            logger.info("Mocking zero USDC balance")
            return 0.0
        else:
            logger.info(f"Mocking {1.0 if token_symbol == 'SOL' else 100.0} {token_symbol} balance")
            return 1.0 if token_symbol == 'SOL' else 100.0
    
    # Apply mock
    solana_client.get_balance = mock_get_balance
    
    # Test with a zero USDC balance
    usdc_balance = await solana_client.get_balance('USDC')
    logger.info(f"Mocked USDC balance: {usdc_balance}")
    
    # Create a test arbitrage signal
    signal = {
        'action': 'arbitrage',
        'token_pair': 'SOL/USDC',
        'buy': {
            'source': 'jupiter',
            'price': 46.5
        },
        'sell': {
            'source': 'openbook',
            'price': 47.1
        },
        'expected_profit': 1.2,
        'reason': 'Test arbitrage signal'
    }
    
    # Try to execute the trade
    logger.info("Attempting to execute arbitrage with zero USDC balance...")
    result = await strategy.execute_arbitrage_trade(signal, solana_client)
    
    # Log the result
    logger.info(f"Trade execution result with zero USDC: {result}")
    if result.get('success', False):
        logger.warning("⚠️ The trade executed successfully despite zero USDC balance!")
    else:
        logger.info("✅ The trade failed as expected with zero USDC balance")
    
    # Restore original method
    solana_client.get_balance = original_get_balance
    
    # Close client
    await solana_client.close()

async def test_very_low_sol_balance():
    """Test how the bot handles very low SOL balance (insufficient for gas)"""
    logger.info("=" * 70)
    logger.info("TEST: Very low SOL balance scenario")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration where balances will be mocked
    config_with_mock = config.copy()
    config_with_mock['trading']['mode'] = 'paper'
    
    # Initialize client and strategy
    solana_client = SolanaClient(config_with_mock)
    strategy = ArbitrageStrategy(config_with_mock)
    
    # Override the get_balance method
    original_get_balance = solana_client.get_balance
    original_buy_token = solana_client.buy_token
    
    async def mock_get_balance(token_symbol='SOL'):
        if token_symbol == 'SOL':
            # Return a very low SOL balance (insufficient for gas fees)
            logger.info("Mocking very low SOL balance (0.000001 SOL)")
            return 0.000001
        else:
            logger.info(f"Mocking 100 {token_symbol} balance")
            return 100.0
    
    async def mock_buy_token(*args, **kwargs):
        # Simulate a transaction failure due to insufficient gas
        logger.info("Mocking buy_token to fail due to insufficient SOL for gas fees")
        return {
            'success': False,
            'error': 'Transaction failed: insufficient SOL for transaction fees',
            'token_symbol': kwargs.get('token_symbol', 'SOL'),
            'amount': kwargs.get('amount_usd', 0)
        }
    
    # Apply mocks
    solana_client.get_balance = mock_get_balance
    solana_client.buy_token = mock_buy_token
    
    # Test with a very low SOL balance
    sol_balance = await solana_client.get_balance('SOL')
    logger.info(f"Mocked SOL balance: {sol_balance}")
    
    # Create a test arbitrage signal
    signal = {
        'action': 'arbitrage',
        'token_pair': 'SOL/USDC',
        'buy': {
            'source': 'jupiter',
            'price': 46.5
        },
        'sell': {
            'source': 'openbook',
            'price': 47.1
        },
        'expected_profit': 1.2,
        'reason': 'Test arbitrage signal'
    }
    
    # Try to execute the trade
    logger.info("Attempting to execute arbitrage with very low SOL balance...")
    result = await strategy.execute_arbitrage_trade(signal, solana_client)
    
    # Log the result
    logger.info(f"Trade execution result with very low SOL: {result}")
    if result.get('success', False):
        logger.warning("⚠️ The trade executed successfully despite very low SOL balance!")
    else:
        logger.info("✅ The trade failed as expected with very low SOL balance")
    
    # Restore original methods
    solana_client.get_balance = original_get_balance
    solana_client.buy_token = original_buy_token
    
    # Close client
    await solana_client.close()

async def test_paper_trading_with_zero_balances():
    """Test how paper trading mode handles zero balances"""
    logger.info("=" * 70)
    logger.info("TEST: Paper trading with zero balances")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration for paper trading
    paper_config = config.copy()
    paper_config['trading']['mode'] = 'paper'
    paper_config['trading']['paper_balance'] = 1000.0
    
    # Initialize client and strategy
    solana_client = SolanaClient(paper_config)
    strategy = ArbitrageStrategy(paper_config)
    
    # Force getting a paper trading balance directly
    paper_sol_balance = await solana_client.get_balance('SOL')
    paper_usdc_balance = await solana_client.get_balance('USDC')
    
    logger.info(f"Paper trading SOL balance: {paper_sol_balance}")
    logger.info(f"Paper trading USDC balance: {paper_usdc_balance}")
    
    # Create a test arbitrage signal
    signal = {
        'action': 'arbitrage',
        'token_pair': 'SOL/USDC',
        'buy': {
            'source': 'jupiter',
            'price': 46.5
        },
        'sell': {
            'source': 'openbook',
            'price': 47.1
        },
        'expected_profit': 1.2,
        'reason': 'Test arbitrage signal'
    }
    
    # Try to execute the trade in paper trading mode
    logger.info("Attempting to execute arbitrage in paper trading mode...")
    result = await strategy.execute_arbitrage_trade(signal, solana_client)
    
    # Log the result
    logger.info(f"Trade execution result in paper trading: {result}")
    if result.get('success', True):
        logger.info("✅ Paper trade executed successfully as expected")
    else:
        logger.warning(f"⚠️ Paper trade failed: {result.get('error', 'Unknown error')}")
    
    # Close client
    await solana_client.close()

async def main():
    """Run all balance tests"""
    try:
        # Run the balance tests
        await test_get_balance_with_wallet_file()
        await test_zero_sol_balance()
        await test_zero_usdc_balance()
        await test_very_low_sol_balance()
        await test_paper_trading_with_zero_balances()
        
        logger.info("=" * 70)
        logger.info("✅ All balance tests completed")
        
    except Exception as e:
        logger.error(f"❌ Error in tests: {str(e)}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
