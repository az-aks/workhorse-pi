#!/bin/bash
# Unix startup script for Solana DEX Arbitrage Bot

echo "🚀 Solana DEX Arbitrage Bot"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found! Please install Python 3.7 or higher."
    read -p "Press enter to continue..."
    exit 1
fi

# Check config.yaml for port settings
PORT=$(grep -A10 "web:" config.yaml 2>/dev/null | grep "port:" | head -n1 | cut -d ":" -f2 | tr -d " ")

# If port is less than 1024 and we're not root, suggest sudo
if [[ -n "$PORT" ]] && [[ "$PORT" -lt 1024 ]] && [[ "$EUID" -ne 0 ]]; then
    echo "⚠️ Warning: Port $PORT requires root privileges."
    echo "Would you like to:"
    echo "1. Continue anyway (might fail)"
    echo "2. Run with sudo"
    echo "3. Edit config.yaml first"
    read -p "Choose option (1/2/3): " CHOICE
    
    case $CHOICE in
        2)
            echo "Running with sudo..."
            sudo python3 start.py
            exit $?
            ;;
        3)
            echo "Please edit config.yaml and run again."
            exit 0
            ;;
        *)
            echo "Continuing without sudo..."
            ;;
    esac
fi

# Run the start script
python3 start.py

# Check exit code
if [ $? -ne 0 ]; then
    echo "❌ An error occurred. Please check the logs above."
    read -p "Press enter to continue..."
fi
