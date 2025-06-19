#!/usr/bin/env python3
"""
Test script to simulate what happens when switching to mainnet mode with zero funds
"""

import yaml
import json
import sys
import os
import asyncio
from typing import Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core.solana_client import SolanaClient
    from core.trading_bot import TradingBot
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"❌ Dependencies not available: {e}")
    DEPENDENCIES_AVAILABLE = False


class ZeroFundsSimulator:
    """Simulates what happens when mainnet mode is enabled with zero funds."""
    
    def __init__(self):
        self.config = None
    
    def load_config(self):
        """Load config and modify for testing."""
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Temporarily switch to live mode for testing
        self.config['trading']['mode'] = 'live'
        print("📋 Config loaded and modified for simulation")
        print(f"   Trading mode: {self.config['trading']['mode']}")
        print(f"   Trade amount: ${self.config['trading']['trade_amount']}")
        print(f"   Wallet: {self.config.get('wallet_path', 'Not specified')}")
    
    async def test_wallet_balance(self):
        """Test what happens when checking balance with zero funds."""
        print("\n💰 Testing wallet balance check...")
        
        try:
            solana_client = SolanaClient(self.config)
            
            # Test SOL balance
            sol_balance = await solana_client.get_balance('SOL')
            print(f"   SOL Balance: {sol_balance} SOL")
            
            # Test USDT balance (if available)
            usdt_balance = await solana_client.get_balance('USDT')
            print(f"   USDT Balance: {usdt_balance} USDT")
            
            return sol_balance, usdt_balance
            
        except Exception as e:
            print(f"   ❌ Error checking balance: {e}")
            return 0, 0
    
    async def test_trade_attempt(self):
        """Test what happens when attempting a trade with zero funds."""
        print("\n🔄 Testing trade attempt with zero funds...")
        
        try:
            solana_client = SolanaClient(self.config)
            trade_amount = self.config['trading']['trade_amount']
            
            print(f"   Attempting to buy ${trade_amount} worth of SOL...")
            
            # This is what would happen if a trading opportunity came up
            result = await solana_client.buy_token(
                amount_usd=trade_amount,
                token_symbol='SOL',
                quote_token='USDT'
            )
            
            print(f"   Result: {result}")
            
            if result.get('success'):
                print("   ✅ Trade would succeed (unexpected!)")
            else:
                print(f"   ❌ Trade would fail: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            print(f"   ❌ Exception during trade attempt: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_portfolio_logic(self):
        """Test the trading bot's portfolio balance logic."""
        print("\n📊 Testing trading bot portfolio logic...")
        
        try:
            # Create a minimal config for testing
            test_config = self.config.copy()
            
            # Initialize trading bot
            bot = TradingBot(test_config)
            
            print(f"   Initial paper portfolio balance: ${bot._portfolio['balance_usd']}")
            print(f"   Trading mode: {test_config['trading']['mode']}")
            print(f"   Trade amount: ${test_config['trading']['trade_amount']}")
            
            # Check if trade would be allowed based on portfolio balance
            trade_amount = test_config['trading']['trade_amount']
            
            if bot._portfolio['balance_usd'] >= trade_amount:
                print(f"   ✅ Portfolio has sufficient balance for trade (${trade_amount})")
            else:
                print(f"   ❌ Portfolio has insufficient balance for trade")
                print(f"       Required: ${trade_amount}")
                print(f"       Available: ${bot._portfolio['balance_usd']}")
            
            return bot._portfolio
            
        except Exception as e:
            print(f"   ❌ Error testing portfolio logic: {e}")
            return None
    
    def analyze_scenarios(self):
        """Analyze different scenarios with zero funds."""
        print("\n📋 SCENARIO ANALYSIS:")
        print("=" * 50)
        
        scenarios = [
            {
                'name': 'Zero SOL, Zero USDT',
                'sol': 0.0,
                'usdt': 0.0,
                'description': 'Completely empty wallet'
            },
            {
                'name': 'Some SOL, Zero USDT',
                'sol': 0.1,
                'usdt': 0.0,
                'description': 'Gas fees available, no trading funds'
            },
            {
                'name': 'Zero SOL, Some USDT',
                'sol': 0.0,
                'usdt': 100.0,
                'description': 'Trading funds available, no gas fees'
            }
        ]
        
        for scenario in scenarios:
            print(f"\n🎭 Scenario: {scenario['name']}")
            print(f"   {scenario['description']}")
            print(f"   SOL: {scenario['sol']}, USDT: {scenario['usdt']}")
            
            if scenario['sol'] == 0.0:
                print("   ❌ CRITICAL: No SOL for transaction fees")
                print("   ❌ ALL TRADES WOULD FAIL")
                print("   🚫 Bot would be completely non-functional")
            elif scenario['usdt'] == 0.0:
                print("   ❌ WARNING: No USDT for trading")
                print("   ❌ ALL BUY ORDERS WOULD FAIL")
                print("   ⚠️  Bot could only sell if it owned tokens")
            else:
                print("   ✅ Both SOL and USDT available")
                print("   ✅ Trading could proceed normally")
    
    def print_recommendations(self):
        """Print recommendations for zero funds scenario."""
        print("\n🎯 RECOMMENDATIONS:")
        print("=" * 30)
        print("1. 🚫 NEVER switch to live mode with zero funds")
        print("2. 💰 Fund wallet BEFORE switching to live mode:")
        print("   • SOL: 0.1-0.2 SOL minimum (for transaction fees)")
        print("   • USDT: $50-200 minimum (for trading)")
        print("3. 🧪 Test with paper mode first")
        print("4. 📊 Monitor balances continuously in live mode")
        print("5. 🔔 Set up alerts for low balance conditions")
        
        print("\n⚠️  WHAT WOULD HAPPEN WITH ZERO FUNDS:")
        print("• Bot would start successfully")
        print("• It would detect arbitrage opportunities")
        print("• Every trade attempt would fail")
        print("• Error messages would flood the logs")
        print("• No actual trading would occur")
        print("• You'd waste time and miss opportunities")
    
    async def run_simulation(self):
        """Run the complete simulation."""
        print("🧪 ZERO FUNDS MAINNET SIMULATION")
        print("=" * 40)
        print("This simulation shows what would happen if you switched")
        print("to mainnet mode with zero funds in your wallet.")
        print()
        
        if not DEPENDENCIES_AVAILABLE:
            print("❌ Cannot run simulation - dependencies not available")
            return
        
        # Load config
        self.load_config()
        
        # Test wallet balance
        sol_balance, usdt_balance = await self.test_wallet_balance()
        
        # Test trade attempt
        trade_result = await self.test_trade_attempt()
        
        # Test portfolio logic
        portfolio = self.test_portfolio_logic()
        
        # Analyze scenarios
        self.analyze_scenarios()
        
        # Print recommendations
        self.print_recommendations()
        
        # Final summary
        print(f"\n📊 SIMULATION SUMMARY:")
        print("=" * 25)
        print(f"Current wallet SOL balance: {sol_balance}")
        print(f"Current wallet USDT balance: {usdt_balance}")
        print(f"Trade attempt would succeed: {trade_result.get('success', False)}")
        print(f"Error message: {trade_result.get('error', 'N/A')}")
        
        if sol_balance == 0 and usdt_balance == 0:
            print("\n🚨 CRITICAL: Wallet is completely empty!")
            print("🚫 DO NOT switch to live mode!")
        elif sol_balance == 0:
            print("\n⚠️  WARNING: No SOL for transaction fees!")
            print("🚫 Trading would fail due to insufficient gas!")
        elif usdt_balance == 0:
            print("\n⚠️  WARNING: No USDT for trading!")
            print("🚫 Buy orders would fail!")
        else:
            print("\n✅ Wallet has funds - trading could proceed")


if __name__ == "__main__":
    simulator = ZeroFundsSimulator()
    asyncio.run(simulator.run_simulation())
