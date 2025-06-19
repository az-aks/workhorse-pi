#!/usr/bin/env python3
"""
Mainnet Readiness Validation Script for Workhorse Trading Bot
"""

import yaml
import json
import os
import sys
from typing import Dict, List, Optional

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    import base58
    SOLANA_AVAILABLE = True
except ImportError:
    print("❌ Solana dependencies not installed. Install with: pip install solana solders spl-token")
    SOLANA_AVAILABLE = False


class MainnetValidator:
    """Validates the system for mainnet trading readiness."""
    
    def __init__(self):
        self.config = None
        self.warnings = []
        self.errors = []
        self.wallet_address = None
        
    def load_config(self) -> bool:
        """Load the configuration file."""
        try:
            with open('config.yaml', 'r') as f:
                self.config = yaml.safe_load(f)
            print("✅ Configuration loaded successfully")
            return True
        except FileNotFoundError:
            self.errors.append("Config file 'config.yaml' not found")
            return False
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in config file: {e}")
            return False
    
    def validate_trading_config(self) -> bool:
        """Validate trading configuration."""
        print("\n🔍 Validating Trading Configuration...")
        
        trading_config = self.config.get('trading', {})
        
        # Check trading mode
        mode = trading_config.get('mode', 'paper')
        if mode == 'paper':
            self.warnings.append("Trading mode is set to 'paper' - switch to 'live' for real trading")
        elif mode == 'live':
            print("✅ Trading mode set to 'live'")
        else:
            self.errors.append(f"Invalid trading mode: {mode}. Must be 'paper' or 'live'")
        
        # Check trade amount
        trade_amount = trading_config.get('trade_amount', 0)
        if trade_amount <= 0:
            self.errors.append("Trade amount must be greater than 0")
        elif trade_amount < 5:
            self.warnings.append(f"Trade amount is very small: ${trade_amount}. Consider increasing for meaningful trades")
        else:
            print(f"✅ Trade amount: ${trade_amount}")
        
        # Check risk management
        risk_config = self.config.get('risk', {})
        stop_loss = risk_config.get('stop_loss', 0)
        take_profit = risk_config.get('take_profit', 0)
        
        if stop_loss <= 0:
            self.warnings.append("Stop loss not configured - consider setting for risk management")
        else:
            print(f"✅ Stop loss: {stop_loss * 100}%")
            
        if take_profit <= 0:
            self.warnings.append("Take profit not configured - consider setting for profit taking")
        else:
            print(f"✅ Take profit: {take_profit * 100}%")
        
        return len(self.errors) == 0
    
    def validate_wallet(self) -> bool:
        """Validate wallet configuration and extract address."""
        print("\n💰 Validating Wallet Configuration...")
        
        if not SOLANA_AVAILABLE:
            self.errors.append("Solana dependencies not available - cannot validate wallet")
            return False
        
        # Check wallet file
        wallet_path = self.config.get('wallet_path', './kp.json')
        
        if not os.path.exists(wallet_path):
            self.errors.append(f"Wallet file not found: {wallet_path}")
            return False
        
        try:
            with open(wallet_path, 'r') as f:
                wallet_data = json.load(f)
            
            if isinstance(wallet_data, list) and len(wallet_data) == 64:
                # Array format keypair
                keypair = Keypair.from_bytes(bytes(wallet_data))
                self.wallet_address = str(keypair.pubkey())
                print(f"✅ Wallet loaded from file: {wallet_path}")
                print(f"📍 Wallet address: {self.wallet_address}")
                return True
            else:
                self.errors.append("Invalid wallet file format - should be 64-byte array")
                return False
                
        except Exception as e:
            self.errors.append(f"Error loading wallet: {e}")
            return False
    
    def validate_network_config(self) -> bool:
        """Validate Solana network configuration."""
        print("\n🌐 Validating Network Configuration...")
        
        solana_config = self.config.get('solana', {})
        rpc_endpoint = solana_config.get('rpc_endpoint', '')
        
        if 'mainnet' not in rpc_endpoint.lower():
            self.warnings.append(f"RPC endpoint doesn't appear to be mainnet: {rpc_endpoint}")
        else:
            print(f"✅ Mainnet RPC endpoint: {rpc_endpoint}")
        
        # Check MEV protection
        mev_protection = solana_config.get('mev_protection', False)
        if not mev_protection:
            self.warnings.append("MEV protection is disabled - consider enabling for better execution")
        else:
            priority_fee = solana_config.get('priority_fee', 0)
            print(f"✅ MEV protection enabled with priority fee: {priority_fee} micro-lamports")
        
        return True
    
    def validate_price_feeds(self) -> bool:
        """Validate price feed configuration."""
        print("\n📊 Validating Price Feed Configuration...")
        
        price_feeds = self.config.get('price_feeds', {})
        sources = price_feeds.get('sources', [])
        
        if not sources:
            self.errors.append("No price feed sources configured")
            return False
        
        reliable_sources = ['coinbase', 'binance']
        has_reliable = any(source in reliable_sources for source in sources)
        
        if not has_reliable:
            self.warnings.append("No reliable price sources (Coinbase/Binance) configured")
        else:
            print(f"✅ Price sources: {', '.join(sources)}")
        
        update_interval = price_feeds.get('update_interval', 30)
        if update_interval < 5:
            self.warnings.append("Very short price update interval may cause API rate limiting")
        
        return True
    
    def validate_security(self) -> bool:
        """Validate security configurations."""
        print("\n🔒 Validating Security Configuration...")
        
        # Check if private key is in config (should not be for security)
        wallet_config = self.config.get('wallet', {})
        if wallet_config.get('private_key'):
            self.warnings.append("Private key found in config file - consider using wallet file instead")
        
        # Check web UI security
        web_config = self.config.get('web', {})
        debug = web_config.get('debug', False)
        if debug:
            self.warnings.append("Web debug mode is enabled - disable for production")
        
        use_https = web_config.get('use_https', False)
        if not use_https:
            self.warnings.append("HTTPS is disabled - enable for production security")
        
        return True
    
    def generate_checklist(self) -> List[str]:
        """Generate a pre-mainnet checklist."""
        checklist = [
            "☐ Fund wallet with SOL for transaction fees (minimum ~0.1 SOL recommended)",
            "☐ Fund wallet with USDC/USDT for trading (start with small amount for testing)",
            "☐ Test with small amounts first (paper trading or minimal real trades)",
            "☐ Monitor the bot closely for the first few trades",
            "☐ Ensure stable internet connection for VPS/server hosting",
            "☐ Set up monitoring and alerts for trade failures",
            "☐ Have emergency stop procedure ready",
            "☐ Backup wallet keypair securely (offline storage)",
            "☐ Review and understand all configuration parameters",
            "☐ Consider starting with lower risk settings (larger stop loss, smaller position sizes)"
        ]
        
        if self.wallet_address:
            checklist.insert(0, f"☐ Send funds to wallet: {self.wallet_address}")
        
        return checklist
    
    def run_validation(self) -> bool:
        """Run complete validation."""
        print("🚀 Workhorse Trading Bot - Mainnet Readiness Validation")
        print("=" * 60)
        
        success = True
        
        # Load config
        if not self.load_config():
            success = False
        else:
            # Run all validations
            success &= self.validate_trading_config()
            success &= self.validate_wallet()
            success &= self.validate_network_config()
            success &= self.validate_price_feeds()
            success &= self.validate_security()
        
        # Print results
        print("\n" + "=" * 60)
        print("📋 VALIDATION RESULTS")
        print("=" * 60)
        
        if self.errors:
            print("\n❌ ERRORS (Must fix before mainnet):")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS (Recommended to address):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All validations passed!")
        
        # Show checklist
        print("\n📝 PRE-MAINNET CHECKLIST:")
        print("=" * 30)
        checklist = self.generate_checklist()
        for item in checklist:
            print(item)
        
        # Final recommendation
        print("\n🎯 FINAL RECOMMENDATION:")
        print("=" * 25)
        if success and not self.errors:
            if not self.warnings:
                print("✅ System appears ready for mainnet trading!")
                print("🟡 Start with small amounts and monitor closely.")
            else:
                print("🟡 System is mostly ready, but please review warnings above.")
                print("🟡 Consider addressing warnings before going live.")
        else:
            print("❌ System is NOT ready for mainnet trading.")
            print("🔧 Please fix all errors before proceeding.")
        
        return success and len(self.errors) == 0


if __name__ == "__main__":
    validator = MainnetValidator()
    is_ready = validator.run_validation()
    sys.exit(0 if is_ready else 1)
