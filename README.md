# Workhorse - Lean Solana Trading Bot

A lightweight Python-based Solana trading bot optimized for Raspberry Pi with minimal memory usage.

## Features

- 🚀 **Lightweight Flask UI** - Simple, responsive web interface
- 📊 **Real-time Price Feeds** - WebSocket connections to multiple exchanges  
- 💰 **Solana Trading** - Direct blockchain integration
- 🔄 **Paper Trading** - Risk-free strategy testing
- 📈 **Basic Analytics** - Essential trading metrics
- 🎯 **Memory Optimized** - Designed for 1GB RAM Raspberry Pi

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure wallet:**
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings
   ```

3. **Run the bot:**
   ```bash
   python main.py
   ```

4. **Access UI:**
   ```
   http://localhost:5000
   ```

## Project Structure

```
workhorse-python/
├── main.py              # Application entry point
├── config.yaml          # Configuration file
├── requirements.txt     # Python dependencies
├── app/
│   ├── __init__.py      # Flask app factory
│   ├── routes.py        # Web routes
│   ├── socketio_events.py # Real-time events
│   └── templates/       # HTML templates
├── core/
│   ├── solana_client.py # Solana blockchain interface
│   ├── price_feeds.py   # Price data collection
│   ├── trading_bot.py   # Trading logic
│   └── strategy.py      # Trading strategies
└── static/
    ├── css/
    ├── js/
    └── favicon.ico
```

## Configuration

Key settings in `config.yaml`:
- Solana RPC endpoint
- Wallet configuration
- Trading parameters
- Risk management
- Performance tuning for Pi

## Raspberry Pi Optimizations

- Memory usage < 100MB
- Single-threaded design
- Efficient WebSocket handling
- Minimal DOM updates
- Caching for API calls
