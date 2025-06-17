"""
Test script to add sample trades to the ArbitrageStrategy for UI testing

This script connects to the running bot instance via Socket.IO
and injects sample trades to test the UI's Arbitrage Trades panel.
"""

import logging
import time
import datetime
import json
import random
import asyncio
import socketio
import ssl
from urllib3.exceptions import InsecureRequestWarning
import warnings

# Suppress SSL warnings
warnings.simplefilter('ignore', InsecureRequestWarning)
import yaml
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Socket.IO client
# Create a socketio client with SSL verification disabled
sio = socketio.Client(ssl_verify=False)

# Sample tokens and trading venues
TOKENS = ['SOL/USDC', 'ETH/USDC', 'BTC/USDC', 'BONK/USDC', 'JTO/USDC', 'WIF/USDC']
VENUES = ['jupiterV6', 'raydium', 'orca', 'openbook', 'phoenix', 'meteora']

# Error messages for failed trades
ERROR_MESSAGES = [
    'Slippage exceeded maximum tolerance',
    'Insufficient liquidity for trade size',
    'RPC node timeout during transaction',
    'Transaction confirmation failed',
    'Price moved too quickly, arbitrage opportunity lost',
    'Fee calculation error',
    'DEX API temporary unavailable',
    'Maximum concurrent transaction limit reached',
    'Wallet balance insufficient for transaction',
    'Network congestion caused transaction delay'
]

@sio.event
def connect():
    logger.info("Connected to Socket.IO server")

@sio.event
def disconnect():
    logger.info("Disconnected from Socket.IO server")

@sio.event
def connect_error(data):
    logger.error(f"Connection failed: {data}")

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate sample trades for UI testing')
    parser.add_argument('--server', default='http://localhost:5000', help='Server URL (default: http://localhost:5000)')
    parser.add_argument('--count', type=int, default=5, help='Number of trades to generate (default: 5)')
    parser.add_argument('--error-rate', type=float, default=0.3, help='Percentage of trades that should fail (0.0-1.0, default: 0.3)')
    parser.add_argument('--wait', type=int, default=3, help='Seconds to wait between trades (default: 3)')
    args = parser.parse_args()

    # Connect to the Socket.IO server
    try:
        logger.info(f"Connecting to Socket.IO server at {args.server}")
        # Ensure any previous connections are closed
        if sio.connected:
            logger.info("Disconnecting existing Socket.IO connection")
            sio.disconnect()
            
        # Connect with a longer timeout and explicit transport
        logger.info("Connecting with explicit websocket transport")
        sio.connect(args.server, wait_timeout=10, transports=['websocket'])
    except Exception as e:
        logger.error(f"Failed to connect to server: {e}")
        logger.error(f"Connection error details: {str(e)}")
        return

    total_profit = 0.0
    successful_trades = 0
    trades_executed = 0
    trades = []

    # Generate sample trades
    for i in range(args.count):
        trades_executed += 1
        
        # Determine if this trade will succeed based on error rate
        is_success = random.random() > args.error_rate
        
        # Random token pair and venues
        token_pair = random.choice(TOKENS)
        buy_venue = random.choice(VENUES)
        sell_venue = random.choice([v for v in VENUES if v != buy_venue])
        
        # Random trade amount between $500 and $5000
        amount = round(random.uniform(500, 5000), 2)
        
        # Calculate prices and profit for successful trades
        buy_price = round(random.uniform(10, 1000), 3)  # Random base price
        
        # Successful trades have a positive profit
        profit = 0
        if is_success:
            # Generate a small profit (0.05% to 0.5% of trade amount)
            profit_percentage = random.uniform(0.0005, 0.005)
            profit = round(amount * profit_percentage, 4)
            sell_price = round(buy_price * (1 + profit_percentage), 3)
            total_profit += profit
            successful_trades += 1
        else:
            # Failed trades might have a potential profit that wasn't realized
            potential_profit_percentage = random.uniform(0.0005, 0.005)
            sell_price = round(buy_price * (1 + potential_profit_percentage), 3)
            
        # Create trade data that matches the structure expected by the frontend
        trade = {
            'timestamp': datetime.datetime.now().isoformat(),
            'token_pair': token_pair,
            'buy_source': buy_venue,
            'sell_source': sell_venue,
            'success': is_success,
            'realized_profit': profit,
            'trade_amount': amount,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'action': 'Arbitrage'  # Explicitly set action for UI consistency
        }
        
        # Add error message for failed trades
        if not is_success:
            trade['error'] = random.choice(ERROR_MESSAGES)
            # Ensure error is also available in error_message field (frontend may look for either)
            trade['error_message'] = trade['error']
        
        # Add to trade history
        trades.append(trade)
        
        # Create arbitrage update data
        arbitrage_data = {
            'trades': trades,
            'total_profit': total_profit,
            'trades_executed': trades_executed,
            'successful_trades': successful_trades
        }
        
        # Emit the update
        logger.info(f"Emitting trade {i+1}/{args.count}: {token_pair} - {'Success' if is_success else 'Failed'}")
        sio.emit('arbitrage_update', arbitrage_data)
        
        # Also emit trade_error event for failed trades to test toast notifications
        if not is_success:
            error_data = {
                'message': trade['error'],
                'timestamp': trade['timestamp'],
                'trade': {
                    'token_pair': token_pair,
                    'amount': amount
                }
            }
            logger.info(f"Emitting trade error notification")
            sio.emit('trade_error', error_data)
        
        # Wait between trades
        logger.info(f"Waiting {args.wait} seconds before next trade...")
        await asyncio.sleep(args.wait)
    
    logger.info(f"All {args.count} sample trades sent. Summary:")
    logger.info(f"- Successful: {successful_trades}")
    logger.info(f"- Failed: {trades_executed - successful_trades}")
    logger.info(f"- Total profit: ${total_profit:.4f}")
    
    # Keep connection open for a moment to ensure all data is received
    await asyncio.sleep(3)
    sio.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
