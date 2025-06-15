#!/usr/bin/env python3
"""
Test script for DEX price feeds
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
from core.price_feeds import PriceFeedManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def price_callback(price_data):
    """Callback to handle price updates."""
    source = price_data.get('source', 'unknown')
    price = price_data.get('price', 0)
    token_pair = price_data.get('token_pair', 'unknown')
    
    logger.info(f"Price update received: {source} {token_pair} = ${price:.4f}")

async def test_dex_feeds():
    """Test DEX price feeds."""
    logger.info("Starting DEX price feed test")
    
    # Load configuration
    try:
        config_path = "arbitrage_config.yaml"
        if not os.path.exists(config_path):
            config_path = "config.yaml"  # Fallback to default config
            
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            logger.info(f"Configuration loaded from {config_path}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        # Use minimal config
        config = {
            'trading': {
                'token_symbol': 'SOL',
                'base_currency': 'USDC'
            },
            'price_feeds': {
                'update_interval': 10,
                'sources': ['jupiter', 'raydium', 'orca']
            }
        }
        logger.info("Using minimal default configuration")
    
    # Initialize price feed manager
    price_feed = PriceFeedManager(config)
    
    # Register callback
    price_feed.add_callback(price_callback)
    
    # Start price feeds
    await price_feed.start()
    
    try:
        # Run for 1 minute
        logger.info("Running DEX price feed test for 60 seconds...")
        start_time = time.time()
        while time.time() - start_time < 60:
            # Manually test fetch_dex_prices every 10 seconds
            if int(time.time() - start_time) % 10 == 0:
                prices = await price_feed.fetch_dex_prices()
                if prices:
                    logger.info(f"Fetched {len(prices)} DEX prices directly")
                    for source, data in prices.items():
                        logger.info(f"  {source}: ${data['price']:.4f}")
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        # Stop price feeds
        await price_feed.stop()
        logger.info("DEX price feed test completed")

if __name__ == "__main__":
    try:
        asyncio.run(test_dex_feeds())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
