"""
Solana blockchain client for live trading
"""

import logging
import asyncio
from typing import Dict, Optional, List, TYPE_CHECKING, Any
from decimal import Decimal

if TYPE_CHECKING:
    from solders.pubkey import Pubkey

try:
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Commitment
    from solana.transaction import Transaction
    from solders.pubkey import Pubkey
    from solders.keypair import Keypair
    from spl.token.client import Token
    from spl.token.constants import TOKEN_PROGRAM_ID
    import base58
    SOLANA_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Solana dependencies not installed: {e}")
    logging.warning("Install with: pip install solana solders spl-token")
    SOLANA_AVAILABLE = False
    # Create dummy classes for when Solana is not available
    Pubkey = None
    AsyncClient = None
    Keypair = None


class SolanaClient:
    """Solana blockchain client for trading operations."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Solana configuration
        solana_config = config.get('solana', {})
        self.rpc_endpoint = solana_config.get('rpc_endpoint', 'https://api.mainnet-beta.solana.com')
        self.commitment = Commitment(solana_config.get('commitment', 'confirmed'))
        
        # Initialize client
        try:
            self.client = AsyncClient(self.rpc_endpoint, commitment=self.commitment)
        except Exception as e:
            self.logger.error(f"Failed to initialize Solana client: {e}")
            self.client = None
            return
        
        # Wallet setup
        wallet_config = config.get('wallet', {})
        private_key = wallet_config.get('private_key', '')
        
        if private_key:
            try:
                # Decode private key from base58
                private_key_bytes = base58.b58decode(private_key)
                self.keypair = Keypair.from_bytes(private_key_bytes)
                self.public_key = self.keypair.pubkey()
                self.logger.info(f"Wallet loaded: {self.public_key}")
            except Exception as e:
                self.logger.error(f"Failed to load wallet: {e}")
                self.keypair = None
                self.public_key = None
        else:
            self.logger.warning("No private key provided - live trading disabled")
            self.keypair = None
            self.public_key = None
        
        # Token addresses (mainnet)
        self.token_addresses = {
            'SOL': 'So11111111111111111111111111111111111111112',  # Wrapped SOL
            'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'USDT': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'
        }
        
        self.logger.info("Solana client initialized")
    
    async def get_balance(self, token_symbol: str = 'SOL') -> Optional[float]:
        """Get token balance for the wallet."""
        if not self.client or not self.public_key:
            return None
        
        try:
            if token_symbol == 'SOL':
                # Get SOL balance
                response = await self.client.get_balance(self.public_key)
                if response.value is not None:
                    # Convert lamports to SOL (1 SOL = 10^9 lamports)
                    return response.value / 1_000_000_000
            else:
                # Get SPL token balance
                token_address = self.token_addresses.get(token_symbol)
                if not token_address:
                    self.logger.error(f"Unknown token: {token_symbol}")
                    return None
                
                # Get token accounts
                response = await self.client.get_token_accounts_by_owner(
                    self.public_key,
                    {"mint": Pubkey.from_string(token_address)}
                )
                
                if response.value:
                    # Sum balances from all token accounts
                    total_balance = 0
                    for account in response.value:
                        account_info = await self.client.get_account_info(account.pubkey)
                        if account_info.value:
                            # Parse token account data
                            # This is simplified - in production, use proper SPL token parsing
                            total_balance += 0  # Placeholder
                    
                    return total_balance
            
        except Exception as e:
            self.logger.error(f"Error getting balance for {token_symbol}: {e}")
        
        return None
    
    async def get_transaction_history(self, limit: int = 10) -> List[Dict]:
        """Get recent transaction history."""
        if not self.client or not self.public_key:
            return []
        
        try:
            response = await self.client.get_signatures_for_address(
                self.public_key,
                limit=limit
            )
            
            transactions = []
            for sig_info in response.value:
                tx_detail = await self.client.get_transaction(
                    sig_info.signature,
                    encoding="json"
                )
                
                if tx_detail.value:
                    transactions.append({
                        'signature': str(sig_info.signature),
                        'timestamp': sig_info.block_time,
                        'status': 'success' if not sig_info.err else 'failed',
                        'fee': tx_detail.value.transaction.meta.fee if tx_detail.value.transaction.meta else 0
                    })
            
            return transactions
            
        except Exception as e:
            self.logger.error(f"Error getting transaction history: {e}")
            return []
    
    async def buy_token(self, amount_usd: float, token_symbol: str) -> bool:
        """
        Buy tokens with USD.
        This is a simplified implementation - in production, you'd use Jupiter or another DEX aggregator.
        """
        if not self.client or not self.keypair:
            self.logger.error("Cannot execute live trade - client not initialized")
            return False
        
        try:
            self.logger.info(f"Attempting to buy {amount_usd} USD worth of {token_symbol}")
            
            # In a real implementation, you would:
            # 1. Get current price from Jupiter
            # 2. Calculate slippage
            # 3. Build swap transaction using Jupiter API
            # 4. Sign and send transaction
            
            # For now, this is a placeholder that logs the trade
            self.logger.warning("Live trading not fully implemented - this would execute a real trade")
            
            # Simulate transaction delay
            await asyncio.sleep(1)
            
            # For demo purposes, return True (success)
            # In production, return actual transaction success
            return True
            
        except Exception as e:
            self.logger.error(f"Error buying {token_symbol}: {e}")
            return False
    
    async def sell_token(self, amount_token: float, token_symbol: str) -> bool:
        """
        Sell tokens for USD.
        This is a simplified implementation - in production, you'd use Jupiter or another DEX aggregator.
        """
        if not self.client or not self.keypair:
            self.logger.error("Cannot execute live trade - client not initialized")
            return False
        
        try:
            self.logger.info(f"Attempting to sell {amount_token} {token_symbol}")
            
            # In a real implementation, you would:
            # 1. Get current price from Jupiter
            # 2. Calculate slippage
            # 3. Build swap transaction using Jupiter API
            # 4. Sign and send transaction
            
            # For now, this is a placeholder that logs the trade
            self.logger.warning("Live trading not fully implemented - this would execute a real trade")
            
            # Simulate transaction delay
            await asyncio.sleep(1)
            
            # For demo purposes, return True (success)
            # In production, return actual transaction success
            return True
            
        except Exception as e:
            self.logger.error(f"Error selling {token_symbol}: {e}")
            return False
    
    async def get_jupiter_quote(self, input_mint: str, output_mint: str, amount: int) -> Optional[Dict]:
        """
        Get a quote from Jupiter for token swap.
        This would be used in the actual buy/sell implementations.
        """
        try:
            import aiohttp
            
            url = "https://quote-api.jup.ag/v6/quote"
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': 50  # 0.5% slippage
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting Jupiter quote: {e}")
            return None
    
    async def close(self):
        """Close the Solana client connection."""
        if self.client:
            await self.client.close()
            self.logger.info("Solana client closed")


# Utility functions for Solana integration
def pubkey_from_string(address: str) -> Optional[Any]:
    """Safely create Pubkey from string."""
    if not SOLANA_AVAILABLE or Pubkey is None:
        return None
    try:
        return Pubkey.from_string(address)
    except Exception:
        return None


def validate_solana_address(address: str) -> bool:
    """Validate if string is a valid Solana address."""
    if not SOLANA_AVAILABLE or Pubkey is None:
        return False
    try:
        Pubkey.from_string(address)
        return True
    except Exception:
        return False


def lamports_to_sol(lamports: int) -> float:
    """Convert lamports to SOL."""
    return lamports / 1_000_000_000


def sol_to_lamports(sol: float) -> int:
    """Convert SOL to lamports."""
    return int(sol * 1_000_000_000)
