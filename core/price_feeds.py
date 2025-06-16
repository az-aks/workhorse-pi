"""
Price feed manager with multiple sources for redundancy
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
import json

import aiohttp
import websockets


class PriceFeedManager:
    """Manages multiple price feed sources with fallback."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.sources = config.get('price_feeds', {}).get('sources', ['binance', 'coinbase'])
        self.update_interval = config.get('price_feeds', {}).get('update_interval', 10)
        self.websocket_timeout = config.get('price_feeds', {}).get('websocket_timeout', 30)
        
        # State
        self._running = False
        self._current_price = None
        self._last_update = None
        self._websocket_connections = {}
        
        # Trading pair
        token = config.get('trading', {}).get('token_symbol', 'SOL')
        base = config.get('trading', {}).get('base_currency', 'USDT')
        self.trading_pair = f"{token}{base}"
        
        self.logger.info(f"Price feed manager initialized for {self.trading_pair}")
    
    async def start(self):
        """Start price feed collection."""
        if self._running:
            return
        
        self._running = True
        self.logger.info("🔄 Starting price feeds")
        
        # Start with REST API fallback
        asyncio.create_task(self._rest_price_loop())
        
        # Skip WebSocket connections due to frequent failures
        # Focus on reliable REST API sources
        self.logger.info("Using REST API price feeds (WebSocket disabled for stability)")
    
    async def stop(self):
        """Stop price feed collection."""
        self._running = False
        
        # Close WebSocket connections
        for source, ws in self._websocket_connections.items():
            try:
                if ws and not ws.closed:
                    await ws.close()
            except Exception as e:
                self.logger.error(f"Error closing WebSocket {source}: {e}")
        
        self._websocket_connections.clear()
        self.logger.info("🛑 Price feeds stopped")
    
    async def get_current_price(self) -> Optional[Dict]:
        """Get current price from best available source."""
        if self._current_price and self._last_update:
            # Check if price is recent (within 2x update interval)
            age = time.time() - self._last_update
            if age < (self.update_interval * 2):
                return self._current_price
        
        # Fetch fresh price if cached data is stale
        await self._fetch_rest_prices()
        return self._current_price
    
    async def _rest_price_loop(self):
        """Backup REST API price fetching loop."""
        while self._running:
            try:
                await self._fetch_rest_prices()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                self.logger.error(f"Error in REST price loop: {e}")
                await asyncio.sleep(5)  # Short delay on error
    
    async def _fetch_rest_prices(self):
        """Fetch prices from REST APIs, including DEX prices for arbitrage."""
        prices = []
        
        # Get prices from DEXes for arbitrage opportunities
        dex_prices = await self.fetch_dex_prices()
        if dex_prices:
            # Emit DEX prices to callbacks for arbitrage strategy
            for source, price_data in dex_prices.items():
                # Create a copy to avoid modifying the original
                price_copy = price_data.copy()
                # Normalize the timestamp format
                if isinstance(price_copy['timestamp'], str):
                    price_copy['timestamp'] = time.time()
                self._emit_price_update(price_copy)
            
            # Log a summary of DEX prices
            self.logger.info(f"DEX prices: {', '.join([f'{s}: ${p['price']:.2f}' for s, p in dex_prices.items()])}")
        
        # Also get standard price sources as backup
        async with aiohttp.ClientSession() as session:
            # Try each source
            for source in self.sources:
                try:
                    price = await self._fetch_price_from_source(session, source)
                    if price:
                        prices.append({
                            'price': price,
                            'source': source,
                            'timestamp': time.time()
                        })
                except Exception as e:
                    self.logger.warning(f"Failed to fetch price from {source}: {e}")
        
        if prices:
            # Use price from preferred source or average
            best_price = self._select_best_price(prices)
            self._update_current_price(best_price)
            
    def _emit_price_update(self, price_data):
        """Emit price update to all registered callbacks."""
        if hasattr(self, "_callbacks") and self._callbacks:
            for callback in self._callbacks:
                try:
                    if price_data:
                        asyncio.create_task(callback(price_data))
                    else:
                        self.logger.warning("Skipping callback due to empty price data")
                except Exception as e:
                    self.logger.error(f"Error in price update callback: {e}")
                    self.logger.debug(f"Price data that caused the error: {price_data}")
    
    def add_callback(self, callback):
        """Add a callback for price updates."""
        if not hasattr(self, "_callbacks"):
            self._callbacks = []
        self._callbacks.append(callback)
    
    async def _fetch_price_from_source(self, session: aiohttp.ClientSession, source: str) -> Optional[float]:
        """Fetch price from specific source."""
        try:
            if source == 'binance':
                return await self._fetch_binance_price(session)
            elif source == 'coinbase':
                return await self._fetch_coinbase_price(session)
            elif source == 'jupiter':
                return await self._fetch_jupiter_price(session)
            elif source in ['raydium', 'orca', 'openbook', 'meteora', 'phoenix']:
                # For DEX sources, we'll use the fetch_dex_prices method
                # which simulates prices for these DEXes based on Jupiter price
                self.logger.debug(f"Using fetch_dex_prices for {source} (to be fetched as a group)")
                return None  # Will be handled by fetch_dex_prices
            else:
                self.logger.warning(f"Unknown price source: {source}")
                return None
        except Exception as e:
            # Reduce error logging frequency for common network issues
            error_key = f"{source}_error_count"
            if hasattr(self, error_key):
                setattr(self, error_key, getattr(self, error_key) + 1)
            else:
                setattr(self, error_key, 1)
            
            # Only log every 5th error to reduce noise
            if getattr(self, error_key) % 5 == 1:
                self.logger.warning(f"{source.title()} API temporarily unavailable (error #{getattr(self, error_key)})")
            
            return None
    
    async def _fetch_binance_price(self, session: aiohttp.ClientSession) -> Optional[float]:
        """Fetch price from Binance API."""
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {'symbol': self.trading_pair}
        
        async with session.get(url, params=params, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                return float(data['price'])
        return None
    
    async def _fetch_coinbase_price(self, session: aiohttp.ClientSession) -> Optional[float]:
        """Fetch price from Coinbase API."""
        # Convert trading pair format (SOL-USD vs SOLUSDT)
        token = self.config.get('trading', {}).get('token_symbol', 'SOL')
        base = 'USD' if self.config.get('trading', {}).get('base_currency', 'USDT') == 'USDT' else 'USDT'
        pair = f"{token}-{base}"
        
        url = f"https://api.coinbase.com/v2/exchange-rates"
        params = {'currency': token}
        
        async with session.get(url, params=params, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                rates = data.get('data', {}).get('rates', {})
                if base in rates:
                    return float(rates[base])
        return None
    
    async def _fetch_jupiter_price(self, session: aiohttp.ClientSession) -> Optional[float]:
        """Fetch price from Jupiter (Solana DEX aggregator)."""
        try:
            # Updated Jupiter API endpoint (v6)
            url = "https://price.jup.ag/v6/price"
            
            # SOL mint address
            sol_mint = "So11111111111111111111111111111111111111112"
            params = {'ids': sol_mint}
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data and sol_mint in data['data']:
                        return float(data['data'][sol_mint]['price'])
                    elif isinstance(data, dict) and sol_mint in data:
                        return float(data[sol_mint]['price'])
        except Exception as e:
            # Reduce error logging frequency
            if hasattr(self, '_jupiter_error_count'):
                self._jupiter_error_count += 1
            else:
                self._jupiter_error_count = 1
            
            # Only log every 10th error to reduce noise
            if self._jupiter_error_count % 10 == 1:
                self.logger.warning(f"Jupiter API unavailable (error #{self._jupiter_error_count})")
            
        return None
    
    async def fetch_dex_prices(self):
        """Fetch current prices from multiple Solana DEXes using production-ready methods."""
        # Import the production-ready implementation
        from core.fetch_dex_prices import fetch_all_dex_prices
        
        # Get prices from all configured DEXes
        dex_prices = await fetch_all_dex_prices(self.config, self.logger)
        
        return dex_prices
    
    def _select_best_price(self, prices: List[Dict]) -> Dict:
        """Select the best price from available sources."""
        if not prices:
            return None
        
        # Prefer sources in order of configuration
        for preferred_source in self.sources:
            for price_data in prices:
                if price_data['source'] == preferred_source:
                    return price_data
        
        # Fallback to first available
        return prices[0]
    
    def _update_current_price(self, price_data: Dict):
        """Update current price and timestamp."""
        if price_data:
            self._current_price = {
                'price': price_data['price'],
                'source': price_data['source'],
                'timestamp': datetime.now().isoformat()
            }
            self._last_update = time.time()
            
            self.logger.debug(f"Price updated: ${price_data['price']:.4f} from {price_data['source']}")
    
    async def _start_websocket(self, source: str):
        """Start WebSocket connection for real-time prices."""
        if source == 'binance':
            await self._binance_websocket()
        elif source == 'coinbase':
            await self._coinbase_websocket()
    
    async def _binance_websocket(self):
        """Binance WebSocket connection."""
        url = f"wss://stream.binance.com:9443/ws/{self.trading_pair.lower()}@ticker"
        
        while self._running:
            try:
                async with websockets.connect(url) as websocket:
                    self._websocket_connections['binance'] = websocket
                    self.logger.info("📡 Binance WebSocket connected")
                    
                    while self._running:
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(), 
                                timeout=self.websocket_timeout
                            )
                            
                            data = json.loads(message)
                            price = float(data['c'])  # Current price
                            
                            self._update_current_price({
                                'price': price,
                                'source': 'binance_ws',
                                'timestamp': time.time()
                            })
                            
                        except asyncio.TimeoutError:
                            # Send ping to keep connection alive
                            await websocket.ping()
                        except Exception as e:
                            self.logger.error(f"Binance WebSocket error: {e}")
                            break
                            
            except Exception as e:
                self.logger.error(f"Binance WebSocket connection failed: {e}")
                if self._running:
                    await asyncio.sleep(5)  # Retry delay
    
    async def _coinbase_websocket(self):
        """Coinbase WebSocket connection."""
        # Coinbase Pro WebSocket implementation
        url = "wss://ws-feed.pro.coinbase.com"
        
        token = self.config.get('trading', {}).get('token_symbol', 'SOL')
        base = 'USD'
        product_id = f"{token}-{base}"
        
        subscribe_message = {
            "type": "subscribe",
            "product_ids": [product_id],
            "channels": ["ticker"]
        }
        
        while self._running:
            try:
                async with websockets.connect(url) as websocket:
                    self._websocket_connections['coinbase'] = websocket
                    
                    # Subscribe to ticker
                    await websocket.send(json.dumps(subscribe_message))
                    self.logger.info("📡 Coinbase WebSocket connected")
                    
                    while self._running:
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(),
                                timeout=self.websocket_timeout
                            )
                            
                            data = json.loads(message)
                            
                            if data.get('type') == 'ticker' and 'price' in data:
                                price = float(data['price'])
                                
                                self._update_current_price({
                                    'price': price,
                                    'source': 'coinbase_ws',
                                    'timestamp': time.time()
                                })
                                
                        except asyncio.TimeoutError:
                            # Send ping
                            await websocket.ping()
                        except Exception as e:
                            self.logger.error(f"Coinbase WebSocket error: {e}")
                            break
                            
            except Exception as e:
                self.logger.error(f"Coinbase WebSocket connection failed: {e}")
                if self._running:
                    await asyncio.sleep(5)  # Retry delay
