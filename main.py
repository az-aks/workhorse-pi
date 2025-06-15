#!/usr/bin/env python3
"""
Workhorse - Lean Solana Trading Bot
Main application entry point
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import yaml
from app import create_app
from core.trading_bot import TradingBot


def load_config():
    """Load configuration from YAML file."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("Error: config.yaml not found. Please copy config.example.yaml to config.yaml")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def setup_logging(config):
    """Setup logging configuration."""
    log_config = config.get('logging', {})
    level = getattr(logging, log_config.get('level', 'INFO'))
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_config.get('file', 'workhorse.log')),
            logging.StreamHandler(sys.stdout)
        ]
    )


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logging.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


async def main():
    """Main application function."""
    # Load configuration
    config = load_config()
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🐎 Starting Workhorse Solana Trading Bot")
    
    # Validate configuration
    if not config['wallet']['private_key'] and config['trading']['mode'] == 'live':
        logger.error("Private key required for live trading mode")
        sys.exit(1)
    
    # Initialize trading bot
    bot = TradingBot(config)
    
    # Create Flask app
    app = create_app(config, bot)
    
    # Start bot in background
    bot_task = asyncio.create_task(bot.start())
    
    # Give the bot a moment to start
    await asyncio.sleep(1)
    
    try:
        # Run Flask app in a thread to not block the event loop
        import threading
        from werkzeug.serving import make_server
        
        web_config = config.get('web', {})
        host = web_config.get('host', '0.0.0.0')
        port = web_config.get('port', 5000)
        
        logger.info(f"🌐 Starting web interface on http://{host}:{port}")
        
        server = make_server(host, port, app, threaded=True)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Keep the main loop running
        while True:
            await asyncio.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        # Cleanup
        logger.info("Stopping trading bot...")
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
        logger.info("🐎 Workhorse stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🐎 Workhorse stopped by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
