#!/usr/bin/env python3

import sys
import os
import logging

# Add project root to path to enable imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import core components
from core.solana_client import SolanaClient
from core.arbitrage_strategy import ArbitrageStrategy

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[
                       logging.StreamHandler(sys.stdout),
                       logging.FileHandler('debug_arbitrage.log')
                   ])

logger = logging.getLogger(__name__)

# Load a signal and test trade execution
async def main():
    import yaml
    import asyncio
    
    try:
        with open("arbitrage_config.yaml", 'r') as file:
            config = yaml.safe_load(file)
            logger.info("✅ Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
        
    # Initialize required components
    solana_client = SolanaClient(config)
    strategy = ArbitrageStrategy(config)
    
    # Create a test signal
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
    
    logger.info("🔍 Testing arbitrage trade execution")
    logger.info(f"Signal: {test_signal}")
    
    # Get paper balance
    balance = await solana_client.get_balance(token_symbol="USDC")
    logger.info(f"Paper trading balance before: {balance} USDC")
    
    # Execute trade
    try:
        logger.info("Executing test arbitrage trade")
        result = await strategy.execute_arbitrage_trade(test_signal, solana_client)
        logger.info(f"Trade execution result: {result}")
        
        # Get updated balance
        new_balance = await solana_client.get_balance(token_symbol="USDC")
        logger.info(f"Paper trading balance after: {new_balance} USDC")
        
        if result.get('success', False):
            logger.info("✅ Trade execution successful!")
        else:
            logger.info(f"❌ Trade execution failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error executing test trade: {e}")
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
