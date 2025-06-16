# Mainnet Trading Implementation Guide

This document provides technical details on how mainnet trading is implemented in the DEX Arbitrage Bot.

## Key Components

### 1. SolanaClient Methods

The core swap functionality is implemented in the `SolanaClient` class:

- `get_jupiter_quote`: Gets a quote from Jupiter's API for a swap
- `get_jupiter_swap_instructions`: Gets transaction instructions based on a quote
- `execute_jupiter_swap`: Executes a Jupiter swap transaction
- `buy_token`: High-level method to buy tokens (wraps the Jupiter functionality)
- `sell_token`: High-level method to sell tokens (wraps the Jupiter functionality)

### 2. ArbitrageStrategy Integration

The `execute_arbitrage_trade` method in `ArbitrageStrategy` has been updated to:
- Calculate appropriate trade sizes
- Execute buy orders using the real DEX (via Jupiter)
- Execute sell orders on another DEX (via Jupiter)
- Calculate actual profits

### 3. Trading Mode Configuration

The trading mode is controlled by the `trading.mode` setting in `arbitrage_config.yaml`:
- `paper`: Simulates trades without sending actual transactions
- `mainnet`: Executes real trades using your wallet

## Implementation Details

### Jupiter API Integration

Our implementation uses Jupiter's v6 API endpoints:
- `/quote`: To get swap quotes
- `/swap`: To get swap instructions

### Transaction Handling

For mainnet transactions:
1. We request a quote from Jupiter
2. We request swap instructions based on the quote
3. We sign the transaction with the wallet's keypair
4. We send the transaction to the Solana network
5. We wait for transaction confirmation

### Error Handling

The system includes several layers of error handling:
- API request errors
- Transaction signing errors
- Transaction submission errors
- Confirmation timeouts

### Security Considerations

- Private keys are never logged
- Slippage protection is enabled (default 0.5%)
- Transaction sizes are limited
- Daily volume limits are enforced

## Wallet Configuration

The wallet can be configured in two ways:
1. Using a keypair JSON file (recommended)
2. Using a Base58-encoded private key (less secure)

## Debugging and Testing

For testing the Jupiter integration without executing real trades:
```bash
python test_swap.py
```

This will test the quote functionality but will not execute real trades.

## Deployment Considerations

When deploying to production:
1. Use a dedicated wallet with limited funds
2. Use a reliable RPC provider
3. Monitor execution logs closely
4. Have a mechanism to stop the bot quickly if needed
5. Implement alerting for errors or exceptional profits/losses

## Maintainer Notes

If updating the Jupiter integration:
1. Check the current API version at https://station.jup.ag/docs/apis/swap-api
2. Update the endpoint URLs as needed
3. Test thoroughly with paper trading before enabling mainnet
