# MEV Protection Guide for Solana DEX Arbitrage Bot

This guide explains how to protect your arbitrage bot from MEV (Maximal Extractable Value) extraction on the Solana blockchain.

## What is MEV?

MEV (Maximal Extractable Value) refers to the profit that can be extracted by manipulating transaction ordering in a block. For arbitrage bots, this can mean:

- **Frontrunning**: Other traders or validators see your pending arbitrage transaction and execute the same trade before yours is processed.
- **Sandwich Attacks**: Transactions are placed before and after yours to manipulate prices and extract value.
- **Backrunning**: After your transaction reveals a profitable opportunity, others execute trades to capture value you identified.

## Simple MEV Protection

The bot now includes simple MEV protection through two mechanisms:

1. **Priority Fees**: Adding fees to increase transaction priority
2. **Jito RPC Integration**: Using Jito's MEV-protected RPC endpoint

### Configuration

```yaml
# In config.yaml
solana:
  # Use Jito's MEV-protected RPC endpoint
  rpc_endpoint: "https://mainnet.block-engine.jito.wtf"
  
  # MEV protection settings
  mev_protection: true
  priority_fee: 5000  # 5000 micro-lamports per compute unit
```

### Priority Fee Settings

The `priority_fee` value can be adjusted based on network conditions:

- **1000-3000**: Low priority, cheaper but may be frontrun in congested periods
- **5000-10000**: Medium priority, good balance of cost and protection
- **20000+**: High priority, expensive but highest protection in congested periods

## Advanced Protection (Future Enhancement)

For even stronger protection, you can implement:

1. **Bundle submission** via Jito Labs
2. **Private RPC endpoints**
3. **Flashbots-style transactions**

These would require more significant code changes.

## Monitoring MEV Impact

When running with MEV protection enabled, monitor:

1. **Transaction success rate**
2. **Price slippage** vs expected
3. **Transaction confirmation time**

## Troubleshooting

If you experience issues with MEV protection:

1. **Transactions failing**: Try increasing the priority fee
2. **High costs**: Try decreasing the priority fee
3. **Connection issues**: Switch back to standard RPC endpoint temporarily

## References

- [Jito Labs Documentation](https://jito-labs.gitbook.io/mev/)
- [Solana Transaction Prioritization](https://docs.solana.com/proposals/fee_transaction_priority)
