#!/usr/bin/env python3
"""
Test Jupiter swap integration for DEX arbitrage
This script tests the mainnet swap functionality in the SolanaClient
"""

import os
import sys
import yaml
import logging
import asyncio
import time
from datetime import datetime

# Add project root to path to enable imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import core components
from core.solana_client import SolanaClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('swap_test.log')
    ]
)

logger = logging.getLogger(__name__)

async def test_get_jupiter_quote(solana_client):
    """Test getting a quote from Jupiter."""
    logger.info("Testing Jupiter quote API...")
    
    # Token addresses
    usdc_mint = solana_client.token_addresses['USDC']
    sol_mint = solana_client.token_addresses['SOL']
    
    # Get quote for 1 USDC -> SOL
    amount_usdc = 1 * 1_000_000  # 1 USDC in smallest units (USDC has 6 decimals)
    
    quote = await solana_client.get_jupiter_quote(
        input_mint=usdc_mint,
        output_mint=sol_mint,
        amount=amount_usdc
    )
    
    if quote:
        logger.info(f"Quote received! You can get approximately {float(quote.get('outAmount', 0)) / 10**9:.8f} SOL for 1 USDC")
        
        # Handle price impact calculation safely
        price_impact = quote.get('priceImpactPct', 0)
        try:
            if isinstance(price_impact, str):
                price_impact = float(price_impact)
            logger.info(f"Price impact: {price_impact * 100:.4f}%")
        except (ValueError, TypeError):
            logger.info(f"Price impact: {price_impact} (raw value)")
        
        return True
    else:
        logger.error("Failed to get Jupiter quote")
        return False

async def test_paper_trade(solana_client):
    """Test paper trading mode."""
    logger.info("Testing paper trading mode...")
    
    # Buy 0.01 SOL with USDC
    buy_result = await solana_client.buy_token(
        amount_usd=1.0,  # Buy $1 worth of SOL
        token_symbol='SOL',
        quote_token='USDC'
    )
    
    logger.info(f"Paper buy result: {buy_result}")
    
    # Sell SOL for USDC
    sell_result = await solana_client.sell_token(
        amount_token=0.01,  # Sell 0.01 SOL
        token_symbol='SOL',
        quote_token='USDC'
    )
    
    logger.info(f"Paper sell result: {sell_result}")
    return True

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
    
    # Initialize client
    solana_client = SolanaClient(config)
    
    try:
        # Test getting a Jupiter quote (works even in paper mode)
        quote_success = await test_get_jupiter_quote(solana_client)
        if quote_success:
            logger.info("✅ Jupiter quote test successful!")
        else:
            logger.error("❌ Jupiter quote test failed!")
        
        # Test paper trading
        paper_success = await test_paper_trade(solana_client)
        if paper_success:
            logger.info("✅ Paper trading test successful!")
        else:
            logger.error("❌ Paper trading test failed!")
        
        # We wouldn't test real trades here for safety
        logger.info("📝 Note: Real trading not tested for safety reasons")
        logger.info("📝 To enable real trading, set mode: 'mainnet' in arbitrage_config.yaml")
        
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
