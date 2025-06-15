# DEX Arbitrage Strategy for Solana

This project implements a market-neutral arbitrage strategy for Solana that profits from price differences between different decentralized exchanges (DEXes).

## Overview

The arbitrage strategy continuously monitors prices of tokens across different Solana DEXes and identifies opportunities where the same token can be bought on one DEX at a lower price and sold on another DEX at a higher price. This approach can generate profits regardless of whether the overall market is moving up or down.

## Features

- **Market-neutral strategy** - Make profits in any market condition
- **Multiple DEXes support** - Monitor Jupiter, Raydium, Orca, OpenBook, and more
- **Simulated price feeds** - Test the strategy with simulated price differences
- **Risk management** - Configurable profit thresholds and position sizes
- **Paper trading** - Test without risking real funds

## Setup

1. Ensure you have Python 3.9+ installed
2. Install dependencies: `pip install -r requirements.txt`
3. Configure the strategy in `arbitrage_config.yaml`

## Usage

Run the arbitrage bot:

```
python arbitrage_bot.py
```

The bot will:
1. Connect to Solana RPC endpoint
2. Monitor prices across different DEXes
3. Identify arbitrage opportunities
4. Execute trades when profitable opportunities are found (in paper or live mode)

## Configuration

The strategy can be configured in `arbitrage_config.yaml`:

- `min_profit_percentage`: Minimum profit required to execute a trade (after fees)
- `max_exposure_percentage`: Maximum percentage of portfolio to use in a single trade
- `cooldown_seconds`: Time to wait between trades for the same token pair
- `price_sources`: List of DEXes to monitor
- `tokens`: List of tokens to watch for arbitrage opportunities

## Example Configuration

```yaml
# DEX Arbitrage Strategy Configuration
arbitrage:
  min_profit_percentage: 0.8  # 0.8% minimum profit after fees
  max_exposure_percentage: 30  # Up to 30% of portfolio in a single trade
  cooldown_seconds: 300  # 5 minutes cooldown
  price_sources:
    - "jupiter"
    - "raydium"
    - "orca"
    - "openbook"
  tokens:
    - "SOL"
    - "USDC"
    - "USDT"
    - "ETH"
    - "RAY"
```

## Trading Mode

Set the trading mode in `arbitrage_config.yaml`:

```yaml
trading:
  mode: "paper"  # Use "paper" for testing, "mainnet" for real trading
```

## Notes

- DEX arbitrage may become less profitable during high volatility due to increased slippage
- Transactions on Solana can occasionally fail during network congestion
- Always start with paper trading to validate the strategy's effectiveness
