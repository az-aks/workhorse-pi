#!/usr/bin/env python3
"""
Test script for network failures and timeouts
This script tests how the bot handles network issues, RPC failures, and timeouts
"""

import os
import sys
import yaml
import logging
import asyncio
import time
import aiohttp
from unittest.mock import patch, MagicMock

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
        logging.FileHandler('network_tests.log')
    ]
)

logger = logging.getLogger(__name__)

class MockResponse:
    """Mock for aiohttp response"""
    def __init__(self, status, json_data=None, text_data=None):
        self.status = status
        self._json_data = json_data
        self._text_data = text_data
        
    async def json(self):
        if self._json_data is None:
            raise aiohttp.ContentTypeError(None, None)
        return self._json_data
        
    async def text(self):
        return self._text_data or ""
    
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

async def mock_aiohttp_request_timeout(*args, **kwargs):
    await asyncio.sleep(0.5)  # Short delay for realism
    raise asyncio.TimeoutError("Request timed out")

async def mock_aiohttp_request_connection_error(*args, **kwargs):
    await asyncio.sleep(0.5)  # Short delay for realism
    raise aiohttp.ClientConnectionError("Connection refused")

async def mock_aiohttp_request_bad_response(*args, **kwargs):
    return MockResponse(500, text_data="Internal Server Error")

async def mock_aiohttp_request_malformed_json(*args, **kwargs):
    return MockResponse(200, text_data="{malformed json}")

async def test_rpc_endpoint_timeout():
    """Test how the bot handles RPC endpoint timeouts"""
    logger.info("=" * 70)
    logger.info("TEST: RPC endpoint timeout")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration
    test_config = config.copy()
    test_config['trading']['mode'] = 'paper'
    
    # Initialize client
    solana_client = SolanaClient(test_config)
    
    # Patch the client's RPC request
    original_request = solana_client.client._provider.request
    
    async def mock_timeout_request(method, *args, **kwargs):
        logger.info(f"Mocking RPC timeout for method: {method}")
        await asyncio.sleep(1)
        raise asyncio.TimeoutError("RPC request timed out")
    
    # Apply mock
    solana_client.client._provider.request = mock_timeout_request
    
    # Test getting balance with timeout
    logger.info("Attempting to get balance with RPC timeout...")
    balance = await solana_client.get_balance('SOL')
    
    # Check result
    logger.info(f"Result of get_balance with RPC timeout: {balance}")
    if balance == 0.0:
        logger.info("✅ get_balance correctly returned 0.0 on RPC timeout")
    else:
        logger.warning(f"⚠️ get_balance returned {balance} on RPC timeout, expected 0.0")
    
    # Restore original request function
    solana_client.client._provider.request = original_request
    
    # Close client
    await solana_client.close()

async def test_jupiter_api_timeout():
    """Test how the bot handles Jupiter API timeouts"""
    logger.info("=" * 70)
    logger.info("TEST: Jupiter API timeout")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration
    test_config = config.copy()
    test_config['trading']['mode'] = 'mainnet'  # Use mainnet mode to test actual API calls
    
    # Initialize client and strategy
    solana_client = SolanaClient(test_config)
    strategy = ArbitrageStrategy(test_config)
    
    # Mock aiohttp.ClientSession.get to simulate timeout
    with patch('aiohttp.ClientSession.get', side_effect=mock_aiohttp_request_timeout):
        # Test Jupiter quote with timeout
        logger.info("Attempting to get Jupiter quote with API timeout...")
        quote = await solana_client.get_jupiter_quote(
            input_mint=solana_client.token_addresses['USDC'],
            output_mint=solana_client.token_addresses['SOL'],
            amount=1000000  # 1 USDC
        )
        
        # Check result
        logger.info(f"Result of get_jupiter_quote with timeout: {quote}")
        if quote is None:
            logger.info("✅ get_jupiter_quote correctly returned None on timeout")
        else:
            logger.warning(f"⚠️ get_jupiter_quote returned {quote} on timeout, expected None")
    
    # Test executing a trade with Jupiter quote timeout
    with patch('aiohttp.ClientSession.get', side_effect=mock_aiohttp_request_timeout):
        # Create a test signal
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test with Jupiter API timeout'
        }
        
        # Try to execute the trade
        logger.info("Attempting to execute arbitrage with Jupiter quote timeout...")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        logger.info(f"Trade execution result with Jupiter quote timeout: {result}")
        if not result.get('success', False) and 'quote' in str(result.get('error', '')).lower():
            logger.info("✅ Trade correctly failed due to Jupiter quote timeout")
        else:
            logger.warning(f"⚠️ Unexpected trade result with Jupiter quote timeout: {result}")
    
    # Close client
    await solana_client.close()

async def test_jupiter_swap_instructions_timeout():
    """Test how the bot handles Jupiter swap instructions API timeouts"""
    logger.info("=" * 70)
    logger.info("TEST: Jupiter swap instructions API timeout")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration
    test_config = config.copy()
    test_config['trading']['mode'] = 'mainnet'  # Use mainnet mode to test actual API calls
    
    # Initialize client and strategy
    solana_client = SolanaClient(test_config)
    strategy = ArbitrageStrategy(test_config)
    
    # Mock get_jupiter_quote to return a valid quote but swap instructions to timeout
    original_get_jupiter_quote = solana_client.get_jupiter_quote
    original_get_jupiter_swap_instructions = solana_client.get_jupiter_swap_instructions
    
    async def mock_get_jupiter_quote(*args, **kwargs):
        return {
            'inAmount': '1000000',
            'outAmount': '6500000',
            'otherAmountThreshold': '6435000',
            'swapMode': 'ExactIn',
            'slippageBps': 50,
            'priceImpactPct': 0.01,
            'routes': []
        }
    
    solana_client.get_jupiter_quote = mock_get_jupiter_quote
    
    # Mock aiohttp.ClientSession.post to simulate timeout
    with patch('aiohttp.ClientSession.post', side_effect=mock_aiohttp_request_timeout):
        # Test Jupiter swap instructions with timeout
        logger.info("Attempting to get Jupiter swap instructions with API timeout...")
        swap_instructions = await solana_client.get_jupiter_swap_instructions({})
        
        # Check result
        logger.info(f"Result of get_jupiter_swap_instructions with timeout: {swap_instructions}")
        if swap_instructions is None:
            logger.info("✅ get_jupiter_swap_instructions correctly returned None on timeout")
        else:
            logger.warning(f"⚠️ get_jupiter_swap_instructions returned {swap_instructions} on timeout, expected None")
        
        # Try to execute a trade with swap instructions timeout
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test with Jupiter swap instructions timeout'
        }
        
        # Try to execute the trade
        logger.info("Attempting to execute arbitrage with Jupiter swap instructions timeout...")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        logger.info(f"Trade execution result with swap instructions timeout: {result}")
        if not result.get('success', False) and 'instruction' in str(result.get('error', '')).lower():
            logger.info("✅ Trade correctly failed due to swap instructions timeout")
        else:
            logger.warning(f"⚠️ Unexpected trade result with swap instructions timeout: {result}")
    
    # Restore original methods
    solana_client.get_jupiter_quote = original_get_jupiter_quote
    solana_client.get_jupiter_swap_instructions = original_get_jupiter_swap_instructions
    
    # Close client
    await solana_client.close()

async def test_connection_errors():
    """Test how the bot handles connection errors"""
    logger.info("=" * 70)
    logger.info("TEST: Connection errors")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration
    test_config = config.copy()
    test_config['trading']['mode'] = 'mainnet'  # Use mainnet mode to test actual API calls
    
    # Initialize client and strategy
    solana_client = SolanaClient(test_config)
    strategy = ArbitrageStrategy(test_config)
    
    # Mock aiohttp.ClientSession.get to simulate connection error
    with patch('aiohttp.ClientSession.get', side_effect=mock_aiohttp_request_connection_error):
        # Test Jupiter quote with connection error
        logger.info("Attempting to get Jupiter quote with connection error...")
        quote = await solana_client.get_jupiter_quote(
            input_mint=solana_client.token_addresses['USDC'],
            output_mint=solana_client.token_addresses['SOL'],
            amount=1000000  # 1 USDC
        )
        
        # Check result
        logger.info(f"Result of get_jupiter_quote with connection error: {quote}")
        if quote is None:
            logger.info("✅ get_jupiter_quote correctly returned None on connection error")
        else:
            logger.warning(f"⚠️ get_jupiter_quote returned {quote} on connection error, expected None")
    
        # Try to execute a trade with connection error
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test with connection error'
        }
        
        # Try to execute the trade
        logger.info("Attempting to execute arbitrage with connection error...")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        logger.info(f"Trade execution result with connection error: {result}")
        if not result.get('success', False):
            logger.info("✅ Trade correctly failed due to connection error")
        else:
            logger.warning(f"⚠️ Unexpected trade result with connection error: {result}")
    
    # Close client
    await solana_client.close()

async def test_server_errors():
    """Test how the bot handles server errors (500, etc.)"""
    logger.info("=" * 70)
    logger.info("TEST: Server errors")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration
    test_config = config.copy()
    test_config['trading']['mode'] = 'mainnet'  # Use mainnet mode to test actual API calls
    
    # Initialize client and strategy
    solana_client = SolanaClient(test_config)
    strategy = ArbitrageStrategy(test_config)
    
    # Mock aiohttp.ClientSession.get to simulate server error
    with patch('aiohttp.ClientSession.get', side_effect=lambda *args, **kwargs: mock_aiohttp_request_bad_response()):
        # Test Jupiter quote with server error
        logger.info("Attempting to get Jupiter quote with server error (500)...")
        quote = await solana_client.get_jupiter_quote(
            input_mint=solana_client.token_addresses['USDC'],
            output_mint=solana_client.token_addresses['SOL'],
            amount=1000000  # 1 USDC
        )
        
        # Check result
        logger.info(f"Result of get_jupiter_quote with server error: {quote}")
        if quote is None:
            logger.info("✅ get_jupiter_quote correctly returned None on server error")
        else:
            logger.warning(f"⚠️ get_jupiter_quote returned {quote} on server error, expected None")
    
        # Try to execute a trade with server error
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test with server error'
        }
        
        # Try to execute the trade
        logger.info("Attempting to execute arbitrage with server error...")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        logger.info(f"Trade execution result with server error: {result}")
        if not result.get('success', False):
            logger.info("✅ Trade correctly failed due to server error")
        else:
            logger.warning(f"⚠️ Unexpected trade result with server error: {result}")
    
    # Close client
    await solana_client.close()

async def test_malformed_json_response():
    """Test how the bot handles malformed JSON responses"""
    logger.info("=" * 70)
    logger.info("TEST: Malformed JSON response")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration
    test_config = config.copy()
    test_config['trading']['mode'] = 'mainnet'  # Use mainnet mode to test actual API calls
    
    # Initialize client and strategy
    solana_client = SolanaClient(test_config)
    strategy = ArbitrageStrategy(test_config)
    
    # Mock aiohttp.ClientSession.get to simulate malformed JSON
    with patch('aiohttp.ClientSession.get', side_effect=lambda *args, **kwargs: mock_aiohttp_request_malformed_json()):
        # Test Jupiter quote with malformed JSON
        logger.info("Attempting to get Jupiter quote with malformed JSON response...")
        quote = await solana_client.get_jupiter_quote(
            input_mint=solana_client.token_addresses['USDC'],
            output_mint=solana_client.token_addresses['SOL'],
            amount=1000000  # 1 USDC
        )
        
        # Check result
        logger.info(f"Result of get_jupiter_quote with malformed JSON: {quote}")
        if quote is None:
            logger.info("✅ get_jupiter_quote correctly returned None on malformed JSON")
        else:
            logger.warning(f"⚠️ get_jupiter_quote returned {quote} on malformed JSON, expected None")
    
        # Try to execute a trade with malformed JSON
        signal = {
            'action': 'arbitrage',
            'token_pair': 'SOL/USDC',
            'buy': {'source': 'jupiter', 'price': 46.5},
            'sell': {'source': 'openbook', 'price': 47.1},
            'expected_profit': 1.2,
            'reason': 'Test with malformed JSON'
        }
        
        # Try to execute the trade
        logger.info("Attempting to execute arbitrage with malformed JSON...")
        result = await strategy.execute_arbitrage_trade(signal, solana_client)
        
        # Check result
        logger.info(f"Trade execution result with malformed JSON: {result}")
        if not result.get('success', False):
            logger.info("✅ Trade correctly failed due to malformed JSON")
        else:
            logger.warning(f"⚠️ Unexpected trade result with malformed JSON: {result}")
    
    # Close client
    await solana_client.close()

async def test_recovery_after_errors():
    """Test if the bot can recover after experiencing errors"""
    logger.info("=" * 70)
    logger.info("TEST: Recovery after errors")
    
    # Load configuration
    with open("arbitrage_config.yaml", 'r') as file:
        config = yaml.safe_load(file)
    
    # Create a modified configuration
    test_config = config.copy()
    test_config['trading']['mode'] = 'paper'
    
    # Initialize client and strategy
    solana_client = SolanaClient(test_config)
    strategy = ArbitrageStrategy(test_config)
    
    # Mock methods to fail
    original_get_jupiter_quote = solana_client.get_jupiter_quote
    
    async def failing_get_jupiter_quote(*args, **kwargs):
        logger.info("Simulating Jupiter quote API failure")
        return None
        
    # Apply mock
    solana_client.get_jupiter_quote = failing_get_jupiter_quote
    
    # First try - this should fail
    signal = {
        'action': 'arbitrage',
        'token_pair': 'SOL/USDC',
        'buy': {'source': 'jupiter', 'price': 46.5},
        'sell': {'source': 'openbook', 'price': 47.1},
        'expected_profit': 1.2,
        'reason': 'Test recovery'
    }
    
    logger.info("STEP 1: Making initial call that should fail")
    result1 = await strategy.execute_arbitrage_trade(signal, solana_client)
    logger.info(f"Result of first attempt (should fail): {result1}")
    
    # Restore original method to simulate recovery
    logger.info("STEP 2: Restoring working method to simulate recovery")
    solana_client.get_jupiter_quote = original_get_jupiter_quote
    
    # Create a mocked simple working get_jupiter_quote that returns a fixed response
    async def working_get_jupiter_quote(*args, **kwargs):
        logger.info("Using working mock of Jupiter quote API")
        return {
            'inAmount': '1000000',
            'outAmount': '6500000',
            'otherAmountThreshold': '6435000',
            'swapMode': 'ExactIn',
            'slippageBps': 50,
            'priceImpactPct': 0.01,
            'routes': []
        }
    
    solana_client.get_jupiter_quote = working_get_jupiter_quote
    
    # Try again - this should succeed at least partially
    logger.info("STEP 3: Making second call that should work")
    result2 = await strategy.execute_arbitrage_trade(signal, solana_client)
    logger.info(f"Result of second attempt (should at least partially succeed): {result2}")
    
    if not result1.get('success', False) and result2.get('success', False):
        logger.info("✅ System recovered successfully after error")
    else:
        logger.warning(f"⚠️ System did not recover as expected: first={result1.get('success')}, second={result2.get('success')}")
    
    # Restore original method
    solana_client.get_jupiter_quote = original_get_jupiter_quote
    
    # Close client
    await solana_client.close()

async def main():
    """Run all network tests"""
    try:
        # Run the tests
        await test_rpc_endpoint_timeout()
        await test_jupiter_api_timeout()
        await test_jupiter_swap_instructions_timeout()
        await test_connection_errors()
        await test_server_errors()
        await test_malformed_json_response()
        await test_recovery_after_errors()
        
        logger.info("=" * 70)
        logger.info("✅ All network tests completed")
        
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
