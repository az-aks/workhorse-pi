# Solana DEX Arbitrage Bot - Comprehensive Testing Guide

This document provides an overview of the comprehensive test suite for the Solana DEX Arbitrage Bot. These tests ensure robust handling of various failure modes, edge cases, and error conditions.

## Testing Overview

The bot includes extensive test coverage to ensure reliability and resilience in production environments. The test suite includes:

1. **Trade Failure Tests**: Tests for scenarios where trades fail due to various reasons.
2. **Additional Trade Failure Tests**: More complex trade failure edge cases.
3. **Price Volatility Tests**: Tests for how the bot handles extreme price movements and discrepancies.
4. **Token Edge Case Tests**: Token-specific issues and edge cases.
5. **Trading Limits Tests**: Tests to ensure safety limits are properly enforced.
6. **Balance Tests**: Tests for wallet balance edge cases.
7. **Network Failure Tests**: Tests for handling network-related errors and recovery.

## Running Tests

You can run individual test scripts or execute the full test suite:

### Running the Complete Test Suite

```bash
python run_test_suite.py
```

This will execute all test scripts and provide a summary of results.

### Running Individual Test Scripts

```bash
python test_trade_failures.py
python test_additional_trade_failures.py
python test_price_volatility.py
python test_token_edge_cases.py
python test_trading_limits.py
python test_balances.py
python test_network_failures.py
```

## Test Categories

### 1. Trade Failure Tests (`test_trade_failures.py`)

Tests basic trade failure scenarios including:
- Zero SOL balance
- Zero USDC balance
- Jupiter quote API failures
- Swap instructions failures
- Transaction submission failures
- Transaction confirmation failures
- Buy success but sell failure
- Insufficient SOL for gas fees

### 2. Additional Trade Failure Tests (`test_additional_trade_failures.py`)

Tests more complex failure scenarios including:
- Invalid/malformed Jupiter quote data
- Slippage tolerance exceeded
- Invalid swap instruction data
- Partial buy with failed sell
- RPC rate limit exceeded
- Token account not found
- Blockhash expired

### 3. Price Volatility Tests (`test_price_volatility.py`)

Tests how the bot handles price fluctuations and discrepancies:
- Sudden price drops during execution
- Sudden price spikes during execution
- Extreme volatility during arbitrage
- Large price discrepancies between DEXes

### 4. Token Edge Case Tests (`test_token_edge_cases.py`)

Tests token-specific issues:
- Unknown/unsupported tokens
- Non-tradable tokens (locked, paused)
- Tokens with transfer fees
- Deprecated tokens requiring migration
- Low liquidity tokens
- Very small decimal amounts

### 5. Trading Limits Tests (`test_trading_limits.py`)

Tests safety limits and constraints:
- Maximum transaction size enforcement
- Daily volume limit enforcement
- Maximum slippage tolerance enforcement
- Minimum profit requirement enforcement

### 6. Balance Tests (`test_balances.py`)

Tests wallet balance scenarios:
- Zero token balances
- Very low SOL balance (insufficient for gas)
- Paper trading mode balances
- Balance update after trades

### 7. Network Failure Tests (`test_network_failures.py`)

Tests network-related issues:
- RPC connection failures
- API timeouts
- Malformed responses
- Server errors
- Recovery after failures

## Test Logs

Test logs are saved to the following files:
- `test_suite_results.log`: Overall test suite results
- `trade_failure_tests.log`: Basic trade failure tests
- `additional_trade_failures.log`: Additional trade failure tests
- `price_volatility_tests.log`: Price volatility tests
- `token_edge_cases.log`: Token edge case tests
- `trading_limits_tests.log`: Trading limits tests
- `balance_tests.log`: Balance tests
- `network_tests.log`: Network failure tests

## Security and Operational Features

### HTTPS Connection

The bot now uses HTTPS by default for secure communication:

- All traffic between the client and server is encrypted
- Prevents eavesdropping and man-in-the-middle attacks
- Uses self-signed certificates for development
- Certificate and key files are stored in the `ssl/` directory
- Uses standard HTTPS port 443 for proper browser recognition

To test HTTPS functionality:
```bash
# Generate a new certificate (optional, done automatically on first run)
python generate_cert.py

# Start the bot (may require sudo/administrator privileges for port 443)
sudo python main.py

# Access the UI via HTTPS
# You'll see a browser warning about the self-signed certificate (this is normal)
# Proceed to https://localhost
```

#### HTTP to HTTPS Redirection

The bot now includes automatic HTTP to HTTPS redirection:
- Listens on standard HTTP port 80 
- Automatically redirects all HTTP requests to the HTTPS version
- Makes the interface accessible via either protocol for convenience

To test the redirection functionality:
```bash
# Start the bot with sudo to enable port 80 listening
sudo python start.py  # Use start.py instead of main.py for redirection

# Try accessing via HTTP - you should be redirected to HTTPS
curl -I http://localhost
# It should return HTTP 301 with a Location header pointing to https://localhost
```

If you see the browser error "Warning: Potential Security Risk Ahead" when accessing the site:
1. This is normal and expected with self-signed certificates
2. Click "Advanced" or "Show Details" button
3. Click "Accept the Risk and Continue" or similar option
4. The bot interface should load normally

#### Port 443 and 80 Considerations

Using the standard HTTPS port 443 has several advantages:
- Browsers recognize it as a secure connection without specifying the port
- It follows web standards and best practices
- Some protocols and security scanners expect HTTPS on this port

However, ports below 1024 (including 80 and 443) require elevated privileges on Unix-like systems (Linux/macOS).
If you need to run without root/administrator access, modify config.yaml:
```yaml
web:
  port: 8443  # Alternative HTTPS port that doesn't require root
```

With this change, the HTTP redirection will not work, and you'll need to access the interface directly via HTTPS using the specified port: `https://localhost:8443`

#### Understanding Self-Signed Certificate Warnings

When accessing the bot's web interface, browsers will show security warnings with messages like:
- Firefox: "Warning: Potential Security Risk Ahead"
- Chrome: "Your connection is not private"
- Safari: "This Connection Is Not Private"

**This is normal and expected** when using self-signed certificates in development environments.

To proceed safely:
- **Firefox**: Click "Advanced..." then "Accept the Risk and Continue"
- **Chrome**: Click "Advanced" then "Proceed to localhost (unsafe)"
- **Safari**: Click "Show Details" then "visit this website"

In production, you should replace the self-signed certificates with proper certificates from a trusted CA like Let's Encrypt.

To disable HTTPS (not recommended for production):
```yaml
# In config.yaml:
web:
  use_https: false
```

### Single Session Limit

The bot now enforces a single client session limit for security reasons:

- Only one client can connect to the UI at a time
- Additional connection attempts will be rejected
- This prevents unauthorized access and reduces resource contention
- When a client disconnects, a new client can connect

To test this feature:
```bash
# Open two browsers and try to connect to the bot interface
# The second connection should be rejected
```

### Trade Logging

All trades (successful and failed) are now logged to a separate dedicated file:

- Trade data is logged in JSON format for easy parsing
- Configured via `trade_log_file` setting in config.yaml
- Default file is `trades.log`
- Includes all trade details and error information
- Can be used for auditing, performance analysis, and troubleshooting

To analyze the trade log:
```bash
# View the most recent trades
tail -n 20 trades.log

# Search for failed trades
grep "success\": false" trades.log

# Calculate profit statistics
grep "realized_profit" trades.log | jq '.realized_profit' | awk '{sum+=$1} END {print "Total profit: "sum; print "Average profit: "sum/NR}'
```

## Troubleshooting

### Socket.IO Connection Issues

If you encounter Socket.IO connection errors, especially with HTTPS enabled, try these solutions:

1. **Check for proper dependencies**:
   ```bash
   # Install required dependencies for Socket.IO over secure WebSockets
   pip install gevent gevent-websocket
   ```

2. **Use the start.py script**:
   ```bash
   # This script checks dependencies and sets up certificates automatically
   python start.py
   ```

3. **Connection error debugging**:
   ```bash
   # Set Flask and SocketIO to debug mode in config.yaml
   web:
     debug: true
   ```

4. **Verify SSL certificates**:
   ```bash
   # Regenerate SSL certificates if you suspect issues
   python generate_cert.py
   ```

5. **Browser console errors**:
   - If you see "websocket error" in browser console:
     - Ensure you're accessing the site using the same hostname as certificate
     - Try both `localhost` and `127.0.0.1` to see which works
     - Some browsers handle self-signed certificates differently

6. **Test with HTTP for comparison**:
   ```yaml
   # In config.yaml temporarily disable HTTPS to isolate the issue
   web:
     use_https: false
     port: 80  # Standard HTTP port (requires root on Unix systems)
     # or use port 8080 if you don't have root access
   ```

### Common Socket.IO Error Messages

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| `websocket error` | Self-signed certificate issues | Use the enhanced start.py script |
| `xhr poll error` | Connection timeout | Check network and increase timeout values |
| `transport error` | Mixed content or proxy issues | Ensure all resources use same protocol (http/https) |

## Safety Precautions

All tests run in paper trading mode by default to prevent real transactions. The configuration is modified during testing to ensure safety:

```python
# Ensure paper trading mode for safety
config['trading']['mode'] = 'paper'
```

Never run tests in mainnet trading mode with real funds unless explicitly testing a small, controlled production deployment.
