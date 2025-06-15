#!/usr/bin/env python3
"""
DEX Arbitrage Bot for Solana
This bot implements a market-neutral arbitrage strategy between different Solana DEXes.
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
from core.price_feeds import PriceFeedManager
from core.arbitrage_strategy import ArbitrageStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('arbitrage_bot.log')
    ]
)

logger = logging.getLogger(__name__)

class ArbitrageBot:
    """DEX Arbitrage Bot for automated trading on Solana."""
    
    def __init__(self, config_path):
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"🔄 Initializing Arbitrage Bot with config: {config_path}")
        
        # Load configuration
        try:
            with open(config_path, 'r') as file:
                self.config = yaml.safe_load(file)
                self.logger.info("✅ Configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"❌ Failed to load configuration: {e}")
            sys.exit(1)
        
        # Initialize components
        self.solana_client = SolanaClient(self.config)
        self.price_feed = PriceFeedManager(self.config)
        self.strategy = ArbitrageStrategy(self.config)
        
        # Bot state
        self.running = False
        self.start_time = None
        self.total_profits = 0.0
        self.trades_executed = 0
    
    async def start(self):
        """Start the arbitrage bot."""
        if self.running:
            self.logger.warning("⚠️ Bot is already running")
            return
        
        self.running = True
        self.start_time = datetime.now()
        self.logger.info("🚀 Starting DEX Arbitrage Bot")
        
        # Start price feeds
        await self.price_feed.start()
        
        # Register price update callback
        self.price_feed.add_callback(self.on_price_update)
        
        # Main loop
        try:
            while self.running:
                # Bot health check
                await self.health_check()
                
                # Sleep to prevent CPU usage
                update_interval = self.config.get('price_feeds', {}).get('update_interval', 10)
                await asyncio.sleep(update_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Bot operation cancelled")
        except Exception as e:
            self.logger.error(f"❌ Error in main bot loop: {e}")
        finally:
            await self.stop()
    
    async def on_price_update(self, price_data):
        """Handle price updates from the price feeds."""
        try:
            # Format the data for the strategy
            formatted_data = {
                'source': price_data.get('source', 'unknown'),
                'token_pair': f"{self.config['trading']['token_symbol']}/USDC",
                'price': price_data.get('price', 0),
                'timestamp': price_data.get('timestamp', datetime.now().isoformat())
            }
            
            # Update strategy with new price data
            await self.strategy.update_prices(formatted_data)
            
            # Check for arbitrage opportunities
            signal = await self.strategy.detect_opportunities()
            
            # Execute arbitrage if signal is generated
            if signal:
                self.logger.info(f"🔔 Arbitrage signal detected in bot: {signal['reason']}")
                self.logger.info(f"DEBUG: Full signal data: {signal}")
                
                # Get paper trading balance for logging
                if self.config.get('trading', {}).get('mode') == 'paper':
                    paper_balance = await self.solana_client.get_balance(token_symbol="USDC")
                    self.logger.info(f"Paper trading balance: {paper_balance} USDC")
                
                self.logger.info(f"📋 ABOUT TO EXECUTE ARBITRAGE - BUY ON {signal['buy']['source']} AT {signal['buy']['price']} AND SELL ON {signal['sell']['source']} AT {signal['sell']['price']}")
                
                # Execute the arbitrage trade
                self.logger.info(f"Executing arbitrage trade: Buy on {signal['buy']['source']} at ${signal['buy']['price']:.4f} and sell on {signal['sell']['source']} at ${signal['sell']['price']:.4f}")
                
                try:
                    result = await self.strategy.execute_arbitrage_trade(signal, self.solana_client)
                    self.logger.info(f"Trade execution result: {result}")
                except Exception as e:
                    self.logger.error(f"❌ Exception during trade execution: {str(e)}")
                    result = {'success': False, 'error': f"Exception: {str(e)}"}
                
                # Process trade result
                if result.get('success', False):
                    self.trades_executed += 1
                    profit = result.get('realized_profit', 0)
                    self.total_profits += profit
                    self.logger.info(f"💰 Trade executed successfully! Total profits: {self.total_profits:.4f} USDC")
                else:
                    self.logger.warning(f"❌ Trade execution failed: {result.get('error', 'Unknown error')}")
                
                # Update strategy with trade result
                self.strategy.on_trade_executed(result)
        
        except Exception as e:
            self.logger.error(f"❌ Error processing price update: {e}")
    
    async def health_check(self):
        """Perform health checks on the bot."""
        try:
            # Check if price feeds are working
            if hasattr(self.price_feed, '_last_update') and self.price_feed._last_update:
                time_since_update = time.time() - self.price_feed._last_update
                if time_since_update > 60:  # No updates for 1 minute
                    self.logger.warning(f"⚠️ No price updates received for {time_since_update:.1f} seconds")
            
            # Check wallet connectivity
            if self.config['trading']['mode'] == 'mainnet':
                balance = await self.solana_client.get_balance()
                if balance is None:
                    self.logger.warning("⚠️ Unable to fetch wallet balance")
            
            # Log status
            uptime = datetime.now() - self.start_time
            self.logger.info(f"✅ Bot running for {str(uptime).split('.')[0]}, "
                           f"trades: {self.trades_executed}, "
                           f"profits: {self.total_profits:.4f} USDC")
            
        except Exception as e:
            self.logger.error(f"❌ Error during health check: {e}")
    
    async def stop(self):
        """Stop the arbitrage bot."""
        if not self.running:
            return
        
        self.running = False
        self.logger.info("🛑 Stopping DEX Arbitrage Bot")
        
        # Stop price feeds
        await self.price_feed.stop()
        
        # Close Solana client connection
        if self.solana_client:
            await self.solana_client.close()
        
        # Final status
        uptime = datetime.now() - self.start_time if self.start_time else datetime.timedelta(0)
        self.logger.info(f"📊 Bot stopped. Uptime: {str(uptime).split('.')[0]}, "
                       f"Trades executed: {self.trades_executed}, "
                       f"Total profits: {self.total_profits:.4f} USDC")


async def main():
    """Main entry point for the DEX arbitrage bot."""
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "arbitrage_config.yaml"
    
    logger.info("🐎 Starting Solana DEX Arbitrage Bot")
    bot = ArbitrageBot(config_path)
    
    # Handle graceful shutdown
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        await bot.stop()
        logger.info("🐎 Solana DEX Arbitrage Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting...")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
