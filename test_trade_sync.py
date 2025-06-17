#!/usr/bin/env python3
"""
Test script to verify that trades appear in both Recent Trades and Arbitrage Trades panels.
"""

import sys
import os
import yaml
from unittest.mock import Mock

# Add the project root to Python path
sys.path.insert(0, '/Users/bkbzl/code/proj/solana/workhorse-python')

from main import TradingBot
from core.arbitrage_strategy import ArbitrageStrategy

def test_trade_callback_mechanism():
    """Test that arbitrage trades trigger the proper callbacks."""
    
    print("🧪 Testing trade callback mechanism...")
    
    # Load config
    config_path = '/Users/bkbzl/code/proj/solana/workhorse-python/config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Mock the trading bot's callback mechanism
    callback_calls = []
    
    class MockTradingBot:
        def __init__(self):
            self.callbacks = {}
            
        def _emit_callback(self, event_type, data):
            callback_calls.append((event_type, data))
            print(f"📨 Callback emitted: {event_type}")
            print(f"   Data: {data.get('token_pair', 'Unknown')} - Success: {data.get('success', False)}")
    
    # Create mock trading bot and strategy
    mock_bot = MockTradingBot()
    strategy = ArbitrageStrategy(config, trading_bot=mock_bot)
    
    # Test successful trade callback
    print("\n1. Testing successful trade callback...")
    trade_result = {
        'token_pair': 'SOL/USDC',
        'buy_source': 'raydium',
        'sell_source': 'orca',
        'trade_amount': 1000,
        'realized_profit': 5.25,
        'buy_price': 100.5,
        'sell_price': 101.0
    }
    
    # Simulate the strategy processing a successful trade
    strategy._handle_trade_result(trade_result, success=True)
    
    # Test failed trade callback
    print("\n2. Testing failed trade callback...")
    failed_trade_result = {
        'token_pair': 'ETH/USDC',
        'buy_source': 'jupiter',
        'sell_source': 'openbook',
        'trade_amount': 500,
        'error': 'Slippage exceeded maximum tolerance',
        'buy_price': 2000.0,
        'sell_price': 2005.0
    }
    
    # Simulate the strategy processing a failed trade
    strategy._handle_trade_result(failed_trade_result, success=False)
    
    # Verify callbacks were called
    print(f"\n📊 Results:")
    print(f"   Total callbacks: {len(callback_calls)}")
    print(f"   Trade history length: {len(strategy.trade_history)}")
    
    for i, (event_type, data) in enumerate(callback_calls, 1):
        print(f"   Callback {i}: {event_type} - {data.get('token_pair', 'Unknown')} ({'Success' if data.get('success') else 'Failed'})")
    
    # Test the Recent Trades data source
    print(f"\n🔄 Testing Recent Trades data source...")
    trades = strategy.get_trade_history()
    print(f"   Available trades: {len(trades)}")
    for i, trade in enumerate(trades, 1):
        print(f"   Trade {i}: {trade.get('token_pair', 'Unknown')} - {'Success' if trade.get('success') else 'Failed'}")
    
    return len(callback_calls) == 2 and len(strategy.trade_history) == 2

if __name__ == '__main__':
    try:
        success = test_trade_callback_mechanism()
        
        print(f"\n{'✅' if success else '❌'} Test {'PASSED' if success else 'FAILED'}")
        
        if success:
            print("\n🎉 The fix should work! Arbitrage trades will now appear in both:")
            print("   📈 Arbitrage Trades panel (via arbitrage_update events)")
            print("   📊 Recent Trades panel (via trade_update events)")
        else:
            print("\n🚨 Something is wrong with the callback mechanism.")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
