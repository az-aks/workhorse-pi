# 🚀 Mainnet Deployment Guide for Workhorse Trading Bot

## ✅ Current Status
Your system has passed all critical validations and is ready for mainnet deployment with some precautions.

**Wallet Address:** `CKu6VmahxjZAmWdEDWTvprckax3cJJQ4qwHpuuELkxgm`

## 🎯 Step-by-Step Mainnet Deployment

### 1. Fund Your Wallet (CRITICAL)

Send funds to your wallet: **CKu6VmahxjZAmWdEDWTvprckax3cJJQ4qwHpuuELkxgm**

**Minimum Requirements:**
- **SOL**: 0.1 SOL (for transaction fees) - ~$25-30
- **USDT**: Start with $50-100 for initial trading (you can always add more)

**Recommended for Testing:**
- **SOL**: 0.2 SOL (gives you buffer for fees)
- **USDT**: $100-200 (allows for 10-20 trades at $5-10 each)

### 2. Switch to Production Configuration

```bash
# Backup current config
cp config.yaml config_development_backup.yaml

# Use production config (already created for you)
cp config_production.yaml config.yaml
```

### 3. Update Configuration for Your Preferences

Edit `config.yaml` and adjust these values based on your risk tolerance:

```yaml
trading:
  trade_amount: 5.0     # Start with $5 per trade (increase later)
  max_trades_per_hour: 30  # Conservative frequency
  
risk:
  stop_loss: 0.08       # 8% stop loss (conservative)
  take_profit: 0.05     # 5% take profit (reasonable)
```

### 4. Security Hardening (IMPORTANT)

**A. Enable HTTPS (if running on server):**
```bash
# Generate SSL certificates (self-signed for testing)
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes
```

**B. Firewall Setup (if on VPS):**
```bash
# Allow only necessary ports
sudo ufw allow 22    # SSH
sudo ufw allow 5000  # Your app (adjust port as needed)
sudo ufw enable
```

### 5. Pre-Launch Testing

**A. Test wallet connection:**
```bash
python validate_mainnet.py
```

**B. Test with paper trading first:**
```bash
# Set mode to paper in config.yaml temporarily
python main.py
# Check UI, ensure everything works
```

### 6. Launch on Mainnet

**A. Final config check:**
```yaml
trading:
  mode: "live"  # Ensure this is set to live
```

**B. Start the bot:**
```bash
# Start with screen or tmux for persistence
screen -S workhorse
python main.py

# Detach with Ctrl+A, D
# Reattach with: screen -r workhorse
```

### 7. Monitoring and Safety

**A. Monitor closely for the first hour:**
- Watch the web UI at http://your-server:5000
- Check logs: `tail -f workhorse.log`
- Monitor trades: `tail -f trades.log`

**B. Emergency Stop:**
```bash
# Stop the bot immediately if needed
pkill -f main.py
# Or if using screen: screen -r workhorse, then Ctrl+C
```

## ⚠️ SAFETY RECOMMENDATIONS

### Start Small
- Begin with small trade amounts ($5-10)
- Use conservative stop losses (8-10%)
- Monitor for at least the first day

### Risk Management
- Never invest more than you can afford to lose
- Start with 1-5% of your total trading capital
- Gradually increase as you gain confidence

### Technical Safeguards
- Run on stable internet connection
- Use VPS/server for 24/7 operation
- Set up monitoring alerts
- Regular backups of config and logs

## 📊 Expected Performance

With current settings:
- **Trade Size**: $5-10 per trade
- **Frequency**: 1-2 trades per hour max
- **Risk**: 8% stop loss, 5% take profit
- **Daily Volume**: ~$50-200 depending on market conditions

## 🔧 Configuration Tuning

After you're comfortable with initial performance, you can adjust:

```yaml
# More aggressive (higher risk/reward)
trading:
  trade_amount: 20.0           # Larger trades
  min_price_change: 0.005      # More sensitive to price moves

risk:
  stop_loss: 0.05              # Tighter stop loss
  take_profit: 0.03            # Quicker profits

# More conservative (lower risk)
trading:
  trade_amount: 3.0            # Smaller trades
  min_trade_interval_minutes: 10  # Less frequent trading

risk:
  stop_loss: 0.12              # Wider stop loss
  max_position_size: 0.03      # Smaller position sizes
```

## 📱 Monitoring Dashboard

Access your trading dashboard at:
- Local: http://localhost:5000
- Server: http://your-server-ip:5000
- HTTPS: https://your-server-ip:5000 (after SSL setup)

## 🆘 Troubleshooting

### Common Issues:
1. **Insufficient SOL**: Add more SOL for transaction fees
2. **RPC Errors**: Switch to backup RPC endpoint
3. **Trade Failures**: Check USDT balance and network status
4. **Connection Issues**: Verify internet stability

### Emergency Contacts:
- Log files: `workhorse.log` and `trades.log`
- Configuration: `config.yaml`
- Wallet backup: Keep `kp.json` secure and backed up

## ✅ Final Checklist

Before funding wallet:
- [ ] Validated system with `python validate_mainnet.py`
- [ ] Reviewed and understood all configuration parameters
- [ ] Set up secure hosting environment (if applicable)
- [ ] Created backup of wallet keypair
- [ ] Prepared monitoring and emergency stop procedures
- [ ] Started with conservative settings

**🎯 You're ready to go live! Start small, monitor closely, and gradually scale up as you gain confidence.**

---

*Remember: Trading involves risk. This bot is a tool to assist your trading strategy, not a guarantee of profits. Always trade responsibly and within your risk tolerance.*
