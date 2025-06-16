#!/usr/bin/env python3
"""
Test script for slippage-related failures in DEX arbitrage bot
This script tests how the bot handles slippage impacts and order book depth issues
"""

import os
import sys
import yaml
import logging
import asyncio
import time
import json
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

# Add project root to path to enable imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import core components
from core.solana_client import SolanaClient
from core.arbitrage_strategy import ArbitrageStrategy
from core.price_feeds import PriceFeedManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('slippage_tests.log')
    ]
)

logger = logging.getLogger(__name__)

class SlippageTestScenario:
    """Base class for slippage test scenarios"""
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"test.{name}")
        
    async def setup(self, config, solana_client, strategy):
        """Setup the test scenario"""
        self.logger.info(f"Setting up test: {self.name}")
        self.logger.info(f"Description: {self.description}")
        
    async def run(self, config, solana_client, strategy):
        """Run the test scenario"""
        self.logger.info(f"Running test: {self.name}")
        await self.execute(config, solana_client, strategy)
        self.logger.info(f"Completed test: {self.name}")
        
    async def execute(self, config, solana_client, strategy):
        """Execute the actual test logic"""
        pass


class HighSlippageScenario(SlippageTestScenario):
    """Test scenario for unexpected high slippage"""
    
    async def execute(self, config, solana_client, strategy):
        """Execute high slippage test"""
        self.logger.info("Testing high slippage scenario")
        
        # Store original methods
        original_get_quote = solana_client.get_jupiter_quote
        original_execute_swap = solana_client.execute_jupiter_swap
        
        # Create mock for Jupiter quote that shows high slippage
        async def mock_get_quote(input_mint, output_mint, amount, slippage_bps=50):
            # Get the original quote
            original_quote = await original_get_quote(input_mint, output_mint, amount, slippage_bps)
            
            # Modify the quote to show high slippage
            if original_quote and 'data' in original_quote:
                # Increase slippage by reducing output amount by 5%
                if 'outAmount' in original_quote['data']:
                    original_out_amount = int(original_quote['data']['outAmount'])
                    reduced_out_amount = int(original_out_amount * 0.95)  # 5% reduction
                    
                    self.logger.info(f"Original out amount: {original_out_amount}")
                    self.logger.info(f"Reduced out amount (high slippage): {reduced_out_amount}")
                    
                    original_quote['data']['outAmount'] = str(reduced_out_amount)
                    
                    # Also adjust price impact if present
                    if 'priceImpactPct' in original_quote['data']:
                        original_price_impact = float(original_quote['data']['priceImpactPct'])
                        # Increase price impact to 5%
                        original_quote['data']['priceImpactPct'] = "5.0"
                        self.logger.info(f"Original price impact: {original_price_impact}%")
                        self.logger.info(f"Modified price impact: 5.0%")
            
            return original_quote
        
        # Inject our mocks
        solana_client.get_jupiter_quote = mock_get_quote
        
        # Test the arbitrage strategy with high slippage
        try:
            # Simulate a trade opportunity
            test_opportunity = {
                'token_symbol': 'SOL',
                'buy_dex': 'jupiter',
                'sell_dex': 'jupiter',
                'buy_price': 100.0,
                'sell_price': 102.0,  # 2% price difference
                'trade_amount_usd': 100.0,
                'profit_percentage': 2.0,
                'timestamp': datetime.now().isoformat(),
            }
            
            # This should detect the high slippage and reject the trade
            result = await strategy.execute_arbitrage(test_opportunity)
            
            # Check if the trade was rejected due to slippage
            if not result['success']:
                self.logger.info("✅ Test PASSED: High slippage trade was correctly rejected")
                self.logger.info(f"Error message: {result['error']}")
                assert "slippage" in result['error'].lower(), "Error message should mention slippage"
            else:
                self.logger.error("❌ Test FAILED: High slippage trade was incorrectly executed")
                
        finally:
            # Restore original methods
            solana_client.get_jupiter_quote = original_get_quote
            self.logger.info("Restored original methods")


class LowLiquidityScenario(SlippageTestScenario):
    """Test scenario for low liquidity on DEX"""
    
    async def execute(self, config, solana_client, strategy):
        """Execute low liquidity test"""
        self.logger.info("Testing low liquidity scenario")
        
        # Store original methods
        original_get_quote = solana_client.get_jupiter_quote
        
        # Create mock for Jupiter quote that shows low liquidity
        async def mock_get_quote(input_mint, output_mint, amount, slippage_bps=50):
            # For large trade amounts, simulate low liquidity by returning error
            if amount > 50:  # If trade is larger than $50 equivalent
                self.logger.info(f"Simulating low liquidity for large trade amount: {amount}")
                return {
                    "success": False,
                    "error": "Not enough liquidity to fulfill the request",
                    "data": None
                }
            else:
                # Otherwise return normal quote
                return await original_get_quote(input_mint, output_mint, amount, slippage_bps)
        
        # Inject our mock
        solana_client.get_jupiter_quote = mock_get_quote
        
        # Test the arbitrage strategy with low liquidity
        try:
            # Simulate a trade opportunity with large amount
            test_opportunity = {
                'token_symbol': 'SOL',
                'buy_dex': 'jupiter',
                'sell_dex': 'jupiter',
                'buy_price': 100.0,
                'sell_price': 102.0,
                'trade_amount_usd': 200.0,  # Large amount to trigger low liquidity
                'profit_percentage': 2.0,
                'timestamp': datetime.now().isoformat(),
            }
            
            # This should detect the low liquidity and reject the trade
            result = await strategy.execute_arbitrage(test_opportunity)
            
            # Check if the trade was rejected due to liquidity
            if not result['success']:
                self.logger.info("✅ Test PASSED: Low liquidity trade was correctly rejected")
                self.logger.info(f"Error message: {result['error']}")
                assert "liquidity" in result['error'].lower(), "Error message should mention liquidity"
            else:
                self.logger.error("❌ Test FAILED: Low liquidity trade was incorrectly executed")
                
        finally:
            # Restore original methods
            solana_client.get_jupiter_quote = original_get_quote
            self.logger.info("Restored original methods")


class PriceMovementDuringSwapScenario(SlippageTestScenario):
    """Test scenario for price movement during swap execution"""
    
    async def execute(self, config, solana_client, strategy):
        """Execute price movement test"""
        self.logger.info("Testing price movement during swap scenario")
        
        # Store original methods
        original_get_quote = solana_client.get_jupiter_quote
        original_execute_swap = solana_client.execute_jupiter_swap
        
        # Create mock for Jupiter quote and swap that simulates price movement during execution
        async def mock_execute_swap(quote_response):
            self.logger.info("Simulating price movement during swap execution")
            
            # Simulate a delay
            await asyncio.sleep(0.5)
            
            # Return a swap result with lower than expected amount received
            expected_amount = int(quote_response['data']['outAmount'])
            actual_amount = int(expected_amount * 0.97)  # 3% worse than expected
            
            self.logger.info(f"Expected out amount: {expected_amount}")
            self.logger.info(f"Actual out amount (after price movement): {actual_amount}")
            
            return {
                'success': True,
                'txid': 'mock_tx_id_price_movement',
                'input_amount': quote_response['data']['inAmount'],
                'output_amount': actual_amount,
                'expected_output': expected_amount,
                'slippage_percentage': 3.0
            }
        
        # Inject our mock
        solana_client.execute_jupiter_swap = mock_execute_swap
        
        # Test the arbitrage strategy with price movement
        try:
            # Simulate a trade opportunity
            test_opportunity = {
                'token_symbol': 'SOL',
                'buy_dex': 'jupiter',
                'sell_dex': 'jupiter',
                'buy_price': 100.0,
                'sell_price': 102.0,
                'trade_amount_usd': 100.0,
                'profit_percentage': 2.0,
                'timestamp': datetime.now().isoformat(),
            }
            
            # This should detect the price movement during execution
            result = await strategy.execute_arbitrage(test_opportunity)
            
            if result['success']:
                # The trade might succeed but should report the price movement
                self.logger.info("Trade executed but should report price movement")
                assert result['slippage_impact'] >= 2.5, "Should report significant slippage impact"
                self.logger.info(f"✅ Test PASSED: Price movement detected and reported with impact: {result.get('slippage_impact')}%")
            else:
                # Or it might fail due to exceeding maximum allowed slippage
                self.logger.info("✅ Test PASSED: Trade rejected due to excessive price movement")
                self.logger.info(f"Error message: {result['error']}")
                
        finally:
            # Restore original methods
            solana_client.execute_jupiter_swap = original_execute_swap
            self.logger.info("Restored original methods")


async def load_config():
    """Load configuration from YAML file"""
    try:
        with open('arbitrage_config.yaml', 'r') as file:
            config = yaml.safe_load(file)
            return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return None


async def run_tests():
    """Run all slippage-related test scenarios"""
    logger.info("Starting slippage test scenarios")
    
    # Load config
    config = await load_config()
    if not config:
        logger.error("Failed to load configuration. Exiting.")
        return
        
    # Force paper trading mode for tests
    config['trading']['mode'] = 'paper'
    
    try:
        # Initialize components
        solana_client = SolanaClient(config)
        
        # Initialize strategy with paper trading
        strategy = ArbitrageStrategy(config)
        
        # Define test scenarios
        test_scenarios = [
            HighSlippageScenario(
                "high_slippage", 
                "Test handling of unexpectedly high slippage during quote"
            ),
            LowLiquidityScenario(
                "low_liquidity", 
                "Test handling of insufficient liquidity for trade size"
            ),
            PriceMovementDuringSwapScenario(
                "price_movement_during_swap", 
                "Test handling of price movement during swap execution"
            )
        ]
        
        # Run each test scenario
        for scenario in test_scenarios:
            logger.info(f"\n{'=' * 80}")
            await scenario.setup(config, solana_client, strategy)
            await scenario.run(config, solana_client, strategy)
            logger.info(f"{'=' * 80}\n")
            
            # Small delay between tests
            await asyncio.sleep(1)
            
        logger.info("All slippage test scenarios completed")
        
    except Exception as e:
        logger.exception(f"Error during test execution: {e}")


if __name__ == "__main__":
    logger.info("DEX Arbitrage Bot - Slippage Test Suite")
    asyncio.run(run_tests())
