# Solana DEX Arbitrage Bot - Mainnet Trading Mode

This guide explains how to enable mainnet trading mode for the Solana DEX Arbitrage Bot, allowing it to execute real trades on Solana DEXes when profitable arbitrage opportunities are detected.

## ⚠️ IMPORTANT WARNINGS ⚠️

- **REAL FUNDS AT RISK**: Mainnet mode uses real funds and executes actual trades on Solana.
- **FINANCIAL RISK**: You can lose money if market conditions change rapidly.
- **USE AT YOUR OWN RISK**: This software is provided as-is without warranty.
- **START SMALL**: Begin with small amounts to test the system.

## Prerequisites

1. A funded Solana wallet with SOL (for gas fees) and stablecoins (USDC/USDT for trades)
2. Your wallet keypair JSON file (created with `solana-keygen`)
3. Working paper trading mode (test this first!)

## Configuration Steps

### 1. Set Up Your Wallet

Make sure you have a wallet keypair file. Place it in the project directory or specify its path:

```yaml
# In arbitrage_config.yaml
wallet_path: "./kp.json"  # Path to your Solana keypair JSON file
```

**SECURITY REMINDER**: Keep your keypair file secure and never share it!

### 2. Configure RPC Endpoint

The public RPC endpoints have rate limits. For reliable mainnet trading, use a paid RPC provider:

```yaml
# In arbitrage_config.yaml
solana:
  rpc_endpoint: "https://your-paid-rpc-provider-url.com"
  commitment: "confirmed"
```

Recommended RPC providers:
- [QuickNode](https://www.quicknode.com)
- [Helius](https://helius.xyz)
- [Alchemy](https://www.alchemy.com)

### 3. Configure Trading Parameters

Adjust trading settings based on your risk tolerance:

```yaml
# In arbitrage_config.yaml
trading:
  mode: "mainnet"  # Change from "paper" to "mainnet"
  
  mainnet:
    max_trade_size: 20    # Maximum USD per trade
    min_trade_size: 5     # Minimum USD per trade
    max_daily_volume: 100 # Daily trading limit in USD
```

### 4. Adjust Arbitrage Settings

Fine-tune the arbitrage parameters:

```yaml
arbitrage:
  min_profit_percentage: 0.5   # Higher for safer trades (0.5%)
  max_exposure_percentage: 10   # Lower for reduced risk (10%)
  max_slippage_pct: 1.0        # Maximum allowed slippage (1.0%)
  # Other settings...
```

## Advanced Protection Features

### Slippage Protection

The bot includes advanced slippage protection to ensure trades are only executed when conditions are favorable:

1. **Pre-Trade Slippage Check**: Before executing trades, the bot checks for potential slippage by getting a quote from Jupiter.

2. **Configurable Slippage Tolerance**:
   ```yaml
   arbitrage:
     max_slippage_pct: 1.0  # Maximum allowed slippage percentage
   ```
   
3. **Automatic Trade Rejection**: If slippage exceeds your configured threshold, trades will be automatically rejected.

4. **Real-Time Monitoring**: The system monitors slippage during both the buy and sell phases of arbitrage.

5. **Slippage Impact Tracking**: Trade results include data on actual slippage experienced, helping you tune your settings.

For DEX-only arbitrage, slippage is especially important as it can quickly erode potential profits. Start with conservative settings (like 1.0%) and adjust based on your experience and market conditions.

### Liquidity Checks

Low liquidity can cause high slippage. The bot automatically:

1. Checks available liquidity on DEXes before trades
2. Rejects trades when liquidity is insufficient 
3. Adapts trade sizes based on available depth

## Testing and Deployment

### Testing Swap Integration

Before trading with real funds, test the Jupiter integration:

```bash
python test_swap.py
```

This will test the Jupiter quote API in paper trading mode.

### Switching to Mainnet Mode

When you're ready to enable real trading:

1. Edit `arbitrage_config.yaml` and set `trading.mode` to "mainnet"
2. Double-check all parameters and wallet configuration
3. Start with a small amount of funds
4. Run the bot and monitor its performance

```bash
python arbitrage_bot.py
```

### Monitoring and Safety

When in mainnet mode:

- Monitor your trades and balances closely
- Watch the logs for any errors or issues
- Be prepared to stop the bot if market conditions change dramatically
- Implement a stop-loss mechanism if losses exceed a threshold

## Troubleshooting

If you encounter issues in mainnet mode:

1. Check wallet balance and permissions
2. Verify RPC endpoint connectivity
3. Look for rate limiting issues in the logs
4. Check for transaction errors or rejections

## Switching Back to Paper Trading

To return to paper trading mode:

1. Edit `arbitrage_config.yaml` and set `trading.mode` back to "paper"
2. Restart the bot

This allows safe testing of strategy changes without risk.

---

Remember: Crypto markets can be volatile. Always start with small amounts and increase gradually as you gain confidence in the system.
