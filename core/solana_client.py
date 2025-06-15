"""
Solana blockchain client for live trading
"""

import logging
import asyncio
from typing import Dict, Optional, List, TYPE_CHECKING, Any
from decimal import Decimal
import json # Added for reading JSON keypair file
import os # Added for path manipulation

if TYPE_CHECKING:
    Pubkey = None  # type: ignore

try:
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Commitment
    from solana.transaction import Transaction
    from solders.pubkey import Pubkey as PublicKey
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
        private_key_b58 = wallet_config.get('private_key') # Renamed for clarity
        wallet_path = config.get('wallet_path')  # This is at the top level of the config, not inside wallet:{}

        self.keypair = None
        self.public_key = None

        if wallet_path:
            try:
                self.logger.info(f"Attempting to load wallet from path: {wallet_path}")
                
                # Current working directory for reference
                import os
                cwd = os.getcwd()
                self.logger.info(f"Current working directory: {cwd}")
                
                # Try multiple path resolution approaches
                absolute_path = os.path.abspath(wallet_path)
                self.logger.info(f"Resolved absolute path: {absolute_path}")
                
                # We need to be more robust in finding the wallet file regardless of where the app is run from
                
                # Get the app's base directory (where main.py is)
                script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self.logger.info(f"Application base directory: {script_dir}")
                
                # List of possible locations to look for the wallet file
                possible_paths = [
                    absolute_path,                                     # The absolute path if provided
                    wallet_path,                                       # The path as provided in config
                    os.path.join(cwd, wallet_path),                    # Relative to current dir
                    os.path.join(cwd, wallet_path.lstrip('./')),       # Without leading ./
                    os.path.join(script_dir, wallet_path),             # Relative to app base dir
                    os.path.join(script_dir, wallet_path.lstrip('./')),# Without leading ./ from app dir
                    os.path.join(os.path.dirname(cwd), wallet_path)    # One directory up
                ]
                
                # Try each path
                found = False
                for path in possible_paths:
                    self.logger.info(f"Checking for wallet file at: {path}")
                    if os.path.exists(path):
                        self.logger.info(f"Wallet file found at: {path}")
                        kp_file_path = path
                        found = True
                        break
                
                if not found:
                    self.logger.error(f"Wallet file not found after trying multiple paths")
                    # As a last resort, use the path as is
                    kp_file_path = wallet_path
                    
                    found = False
                    for path in alt_paths:
                        self.logger.info(f"Trying alternative path: {path}")
                        if os.path.exists(path):
                            self.logger.info(f"File found at alternative path: {path}")
                            kp_file_path = path
                            found = True
                            break
                    
                    # This section was replaced by the improved path resolution above


                try:
                    with open(kp_file_path, 'r') as f:
                        file_content = f.read().strip()  # Strip whitespace which can cause JSON parsing issues
                        
                        # Don't log the full content for security reasons
                        content_preview = f"{file_content[:20]}...{file_content[-10:] if len(file_content) > 30 else ''}"
                        self.logger.info(f"Read file content (truncated): {content_preview}")
                        self.logger.info(f"File content length: {len(file_content)} characters")
                        
                        # Try to parse JSON
                        try:
                            secret_key_array = json.loads(file_content)
                            self.logger.info(f"JSON parsed successfully, type: {type(secret_key_array)}, length: {len(secret_key_array) if isinstance(secret_key_array, list) else 'N/A'}")
                        except json.JSONDecodeError as e:
                            self.logger.error(f"JSON parsing error: {e} - Content might not be valid JSON")
                            # Log more details for debugging
                            self.logger.error(f"JSON error at position: {e.pos}, line: {e.lineno}, column: {e.colno}")
                            self.logger.error(f"JSON content around error: '{file_content[max(0, e.pos-20):min(len(file_content), e.pos+20)]}'")
                            raise
                except FileNotFoundError:
                    self.logger.error(f"Wallet file not found at path: {kp_file_path}")
                    raise
                except PermissionError:
                    self.logger.error(f"Permission denied when accessing wallet file: {kp_file_path}")
                    raise
                except Exception as e:
                    self.logger.error(f"Unexpected error reading wallet file: {str(e)}")
                    raise
                
                # Check if it's an array of integers
                if isinstance(secret_key_array, list):
                    # Verify content is all integers
                    all_ints = all(isinstance(x, int) for x in secret_key_array)
                    self.logger.info(f"Array content check - all integers: {all_ints}")
                    
                    if all_ints:
                        self.logger.info(f"Converting array of {len(secret_key_array)} integers to bytes")
                        secret_key_bytes = bytes(secret_key_array)
                        
                        # Solana keypair files usually store the full 64-byte secret key.
                        # If it's a 32-byte seed, use Keypair.from_seed().
                        # For a typical kp.json from solana-keygen, it's the full secret key.
                        try:
                            self.keypair = Keypair.from_bytes(secret_key_bytes)
                            self.public_key = self.keypair.pubkey()
                            self.logger.info(f"Wallet loaded from JSON file {kp_file_path}: {self.public_key}")
                        except Exception as e:
                            self.logger.error(f"Error creating Keypair from bytes: {e}")
                            raise
                    else:
                        self.logger.error(f"Invalid format in wallet file: Not all elements are integers. First few elements: {secret_key_array[:5]}")
                else:
                    self.logger.error(f"Invalid format in wallet file {kp_file_path}. Expected a JSON array of integers, got {type(secret_key_array)}")

            except FileNotFoundError:
                self.logger.error(f"Wallet file not found: {wallet_path} (resolved to {kp_file_path})")
            except json.JSONDecodeError:
                self.logger.error(f"Error decoding JSON from wallet file: {kp_file_path}")
            except Exception as e:
                self.logger.error(f"Failed to load wallet from JSON file {kp_file_path}: {e}")
        
        if not self.keypair and private_key_b58: # If loading from path failed or path not provided, try private_key
            self.logger.info("Attempting to load wallet from private_key (base58 string).")
            try:
                private_key_bytes = base58.b58decode(private_key_b58)
                self.keypair = Keypair.from_bytes(private_key_bytes)
                self.public_key = self.keypair.pubkey()
                self.logger.info(f"Wallet loaded from private_key (base58): {self.public_key}")
            except Exception as e:
                self.logger.error(f"Failed to load wallet from private_key (base58): {e}")
                # self.keypair and self.public_key remain None
        
        if not self.keypair:
            self.logger.warning("No private key (from file or string) loaded - live trading disabled")
            # self.keypair and self.public_key are already None

        # Token addresses (mainnet)
        self.token_addresses = {
            'SOL': 'So11111111111111111111111111111111111111112',  # Wrapped SOL
            'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'USDT': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'
        }
        
        self.logger.info("Solana client initialized")
    
    async def get_balance(self, token_symbol: str = 'SOL') -> Optional[float]:
        """Get token balance for the wallet."""
        # Check if we're in paper trading mode
        if self.config.get('trading', {}).get('mode') == 'paper':
            # For paper trading, maintain a consistent balance
            paper_balance = self.config.get('trading', {}).get('paper_balance', 1000.0)
            self.logger.info(f"Using paper trading balance: {paper_balance} {token_symbol}")
            return float(paper_balance)
        
        if not self.client:
            self.logger.warning("Cannot get balance: Solana client not initialized")
            return 0.0  # Return 0 instead of None for better UI display
            
        if not self.public_key:
            self.logger.warning("Cannot get balance: Wallet not loaded (public key is None)")
            return 0.0  # Return 0 instead of None for better UI display
        
        self.logger.info(f"Fetching balance for token: {token_symbol}, wallet: {self.public_key}")
        
        # Number of retry attempts for RPC
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if token_symbol == 'SOL':
                    # Get SOL balance
                    self.logger.info(f"Getting SOL balance for {self.public_key} (attempt {retry_count + 1}/{max_retries})")
                    
                    # Recreate client if needed (might help with connection issues)
                    if retry_count > 0:
                        try:
                            self.logger.info("Recreating Solana client connection for retry")
                            await self.client.close()
                            self.client = AsyncClient(self.rpc_endpoint, commitment=self.commitment)
                        except Exception as e:
                            self.logger.warning(f"Error recreating client: {e}, continuing with existing client")
                    
                    # Check client is connected
                    try:
                        health = await self.client.is_connected()
                        self.logger.info(f"RPC connection healthy: {health}")
                    except Exception as e:
                        self.logger.error(f"RPC health check failed: {e}, will retry")
                        retry_count += 1
                        continue
                    
                    try:
                        # Remove mock balance use and use actual RPC call
                        self.logger.info(f"Requesting balance from RPC endpoint: {self.rpc_endpoint}")
                        response = await self.client.get_balance(self.public_key)
                        self.logger.info(f"Balance response received: {response}")
                        
                        if response and hasattr(response, 'value'):
                            if response.value is not None:
                                # Convert lamports to SOL (1 SOL = 10^9 lamports)
                                balance_sol = response.value / 1_000_000_000
                                self.logger.info(f"Converted balance: {balance_sol} SOL")
                                
                                # Empty wallet case - this is expected and normal
                                if balance_sol == 0:
                                    self.logger.info(f"Wallet has zero SOL balance - this is not an error")
                                
                                return balance_sol
                            else:
                                self.logger.warning(f"Balance response value is None")
                                return 0.0  # Empty wallet
                        else:
                            self.logger.warning(f"Unexpected balance response format: {response}")
                            # Try again
                            retry_count += 1
                            continue
                    except Exception as e:
                        self.logger.error(f"Error during get_balance RPC call: {e}")
                        retry_count += 1
                        continue
                else:
                    # Get SPL token balance
                    token_address = self.token_addresses.get(token_symbol)
                    if not token_address:
                        self.logger.error(f"Unknown token: {token_symbol}")
                        return 0.0
                    
                    self.logger.info(f"Getting {token_symbol} token balance using mint: {token_address}")
                    
                    # For now, return mock token balance for testing
                    mock_token_balance = 10.0
                    self.logger.info(f"USING MOCK TOKEN BALANCE of {mock_token_balance} {token_symbol} for testing")
                    return mock_token_balance
                    
                    # Uncomment below for real token balance fetching
                    """
                    try:
                        # Get token accounts
                        response = await self.client.get_token_accounts_by_owner(
                            self.public_key,
                            {"mint": PublicKey(token_address)}
                        )
                        
                        self.logger.info(f"Token accounts response: {response}")
                        
                        if response and hasattr(response, 'value') and response.value:
                            # Sum balances from all token accounts
                            total_balance = 0
                            for account in response.value:
                                self.logger.info(f"Processing token account: {account.pubkey}")
                                account_info = await self.client.get_account_info(account.pubkey)
                                if account_info.value:
                                    # Parse token account data
                                    # This is simplified - in production, use proper SPL token parsing
                                    # TODO: Implement proper SPL token account data parsing
                                    self.logger.warning("Token balance parsing not fully implemented")
                                    total_balance += 0  # Placeholder
                            
                            self.logger.info(f"Total token balance: {total_balance}")
                            return total_balance
                        else:
                            self.logger.warning(f"No token accounts found for {token_symbol}")
                            return 0.0  # No accounts means zero balance
                    except Exception as e:
                        self.logger.error(f"Error getting token balance for {token_symbol}: {e}")
                        retry_count += 1
                        continue
                    """
                
            except Exception as e:
                self.logger.error(f"Unexpected error getting balance for {token_symbol}: {e}", exc_info=True)
                retry_count += 1
            
            # Small delay between retries
            await asyncio.sleep(0.5)
        
        self.logger.warning(f"Failed to get balance for {token_symbol} after {max_retries} attempts, returning 0")
        return 0.0  # Return 0 instead of None for better UI display
    
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
    """Safely create PublicKey from string."""
    if not SOLANA_AVAILABLE or PublicKey is None:
        return None
    try:
        return PublicKey(address)
    except Exception:
        return None


def validate_solana_address(address: str) -> bool:
    """Validate if string is a valid Solana address."""
    if not SOLANA_AVAILABLE or PublicKey is None:
        return False
    try:
        PublicKey(address)
        return True
    except Exception:
        return False


def lamports_to_sol(lamports: int) -> float:
    """Convert lamports to SOL."""
    return lamports / 1_000_000_000


def sol_to_lamports(sol: float) -> int:
    """Convert SOL to lamports."""
    return int(sol * 1_000_000_000)
