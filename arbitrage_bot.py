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
    
    def __init__(self, config_path: str):
        """Initialize the ArbitrageBot with configuration."""
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
        
        # Load real balance once during initialization
        self._load_initial_balance()
    
    def _load_initial_balance(self):
        """Load the real wallet balance once during initialization."""
        try:
            import asyncio
            
            async def fetch_balance():
                try:
                    balance = await self.solana_client.get_real_balance()
                    if balance is not None:
                        self.solana_client._cached_real_balance = balance
                        self.logger.info(f"💰 Loaded real wallet balance: {balance} SOL")
                        return balance
                    else:
                        self.logger.error("Failed to fetch wallet balance - RPC returned None")
                        return None
                except Exception as e:
                    self.logger.error(f"Error fetching wallet balance: {e}")
                    return None
            
            # Run the balance loading synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                balance = loop.run_until_complete(fetch_balance())
                if balance is None:
                    self.logger.warning("Could not load initial balance")
            finally:
                loop.close()
                
        except Exception as e:
            self.logger.error(f"Error in initial balance loading: {e}")

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
            # Ensure price_data is not None before processing
            if price_data is None:
                self.logger.warning("⚠️ Received None price data, skipping update")
                return
            
            # Format the data for the strategy - ensure it has all required fields
            formatted_data = {
                'source': price_data.get('source', 'unknown'),
                'token_pair': f"{price_data.get('token', self.config['trading']['token_symbol'])}/{price_data.get('quote_token', 'USDC')}",
                'price': price_data.get('price', 0),
                'timestamp': price_data.get('timestamp', datetime.now().isoformat())
            }
            
            # Validate the formatted data
            if formatted_data['price'] <= 0:
                self.logger.warning(f"Skipping price update with invalid price: {formatted_data}")
                return
                
            # Log the price update for debugging
            self.logger.debug(f"Price update received: {formatted_data['source']} - {formatted_data['token_pair']} - ${formatted_data['price']:.4f}")
            
            # Update strategy with new price data
            await self.strategy.update_prices(formatted_data)
            
            # Check for arbitrage opportunities
            signal = await self.strategy.detect_opportunities()
            
            # Execute arbitrage if signal is generated
            if signal and isinstance(signal, dict):
                self.logger.info(f"🔔 ARBITRAGE SIGNAL DETECTED: {signal.get('reason', 'No reason provided')}")
                
                if 'buy' in signal and 'sell' in signal:
                    self.logger.info(f"📊 Signal: Buy {signal['token_pair']} on {signal['buy'].get('source')} at ${signal['buy'].get('price', 0):.4f} and sell on {signal['sell'].get('source')} at ${signal['sell'].get('price', 0):.4f}")
                else:
                    self.logger.error(f"Signal structure invalid: {signal}")
                
                # Now proceed with trade execution
                
                # Get paper trading balance before trade
                initial_balance = 0
                if self.config.get('trading', {}).get('mode') == 'paper':
                    initial_balance = await self.solana_client.get_balance(token_symbol="USDC")
                    self.logger.info(f"💰 Paper trading balance before trade: {initial_balance} USDC")
                
                # Execute the arbitrage trade
                try:
                    self.logger.info(f"🔄 Executing arbitrage trade... THIS IS REALLY HAPPENING!")
                    result = await self.strategy.execute_arbitrage_trade(signal, self.solana_client)
                    self.logger.info(f"📝 Trade result: {result}")
                except Exception as e:
                    self.logger.error(f"❌ Exception during trade execution: {str(e)}")
                    result = {'success': False, 'error': f"Exception: {str(e)}"}
                
                # Process trade result
                if result.get('success', False):
                    self.trades_executed += 1
                    profit = result.get('realized_profit', 0)
                    self.total_profits += profit
                    
                    # Get updated balance after trade
                    if self.config.get('trading', {}).get('mode') == 'paper':
                        new_balance = await self.solana_client.get_balance(token_symbol="USDC")
                        self.logger.info(f"💰 Paper trading balance after trade: {new_balance} USDC")
                    
                    self.logger.info(f"✅ TRADE EXECUTED SUCCESSFULLY! Profit: {profit:.4f} USDC, Total profits: {self.total_profits:.4f} USDC")
                else:
                    self.logger.warning(f"❌ Trade execution failed: {result.get('error', 'Unknown error')}")
                
                # Update strategy with trade result
                self.strategy.on_trade_executed(result)
        
        except Exception as e:
            self.logger.error(f"❌ Error processing price update: {str(e)}")
    
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
    
    async def refresh_wallet_balance(self):
        """Refresh the wallet balance on demand."""
        try:
            self.logger.info("🔄 Refreshing wallet balances...")
            balances = await self.solana_client.get_real_balance()
            if balances is not None:
                self.solana_client._cached_real_balances = balances
                sol_balance = balances.get('SOL', 0)
                usdc_balance = balances.get('USDC', 0)
                usdt_balance = balances.get('USDT', 0)
                self.logger.info(f"💰 Updated wallet balances: {sol_balance} SOL, {usdc_balance} USDC, {usdt_balance} USDT")
                return True
            else:
                self.logger.error("Failed to refresh wallet balances - RPC returned None")
                return False
        except Exception as e:
            self.logger.error(f"Error refreshing wallet balances: {e}")
            return False

    def get_wallet_info(self):
        """Return information about the wallet for display in the UI.
        Always shows real on-chain wallet balances regardless of trading mode.
        """
        try:
            # Get wallet address safely
            address = None
            if hasattr(self.solana_client, 'get_wallet_address'):
                try:
                    address = self.solana_client.get_wallet_address()
                except Exception as e:
                    self.logger.error(f"Error getting wallet address: {e}")
                    
            if address is None and hasattr(self.solana_client, 'public_key') and self.solana_client.public_key:
                try:
                    address = str(self.solana_client.public_key)
                except Exception as e:
                    self.logger.error(f"Error converting public_key to string: {e}")
        
            # ALWAYS get real cached balances (actual on-chain wallet balances)
            real_balances = None
            if hasattr(self.solana_client, '_cached_real_balances'):
                real_balances = self.solana_client._cached_real_balances

            # Default to zero balances if none cached
            if real_balances is None:
                real_balances = {'SOL': 0.0, 'USDC': 0.0, 'USDT': 0.0}

            # Get trading mode for display purposes
            trading_mode = self.config.get('trading', {}).get('mode', 'live')
            is_paper_mode = trading_mode == 'paper'
            
            # Get paper trading profit/loss for display (separate from real balances)
            paper_pnl = 0.0
            if is_paper_mode and hasattr(self.strategy, '_paper_balance'):
                initial_paper_balance = self.config.get('trading', {}).get('paper_trading', {}).get('initial_balance', 1000)
                current_paper_balance = self.strategy._paper_balance
                paper_pnl = current_paper_balance - initial_paper_balance
                
            wallet_info = {
                'address': address,
                'balances': real_balances,  # Always show real on-chain balances
                'paper_mode': is_paper_mode,
                'pnl': paper_pnl  # Paper trading P&L (if applicable)
            }
            
            self.logger.debug(f"get_wallet_info returning real balances: {wallet_info}")
            return wallet_info
            
        except Exception as e:
            self.logger.error(f"Error in get_wallet_info: {e}")
            return {
                'address': None,
                'balances': {'SOL': 0.0, 'USDC': 0.0, 'USDT': 0.0},
                'paper_mode': self.config.get('trading', {}).get('mode', 'live') == 'paper',
                'pnl': 0.0
            }
        

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
