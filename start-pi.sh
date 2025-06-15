#!/bin/bash

# Workhorse Python Trading Bot - Raspberry Pi Startup Script
# Optimized for low-memory environments

echo "🐎 Starting Workhorse Python Trading Bot for Raspberry Pi"

# Check if we're on Raspberry Pi
if [[ $(uname -m) == "arm"* ]] || [[ $(uname -m) == "aarch64" ]]; then
    echo "📱 Raspberry Pi detected - applying memory optimizations"
    
    # Set memory limits for Python
    export PYTHONHASHSEED=1
    export PYTHONDONTWRITEBYTECODE=1
    export PYTHONUNBUFFERED=1
    
    # Limit memory usage
    ulimit -v 512000  # 500MB virtual memory limit
    
    # Check available memory
    echo "💾 Available memory:"
    free -h
    
    # Check if swap is available
    if ! swapon --show | grep -q .; then
        echo "⚠️  No swap detected. Consider adding swap for better stability:"
        echo "   sudo dd if=/dev/zero of=/swapfile bs=1M count=512"
        echo "   sudo chmod 600 /swapfile"
        echo "   sudo mkswap /swapfile"
        echo "   sudo swapon /swapfile"
    fi
fi

# Check Python version
echo "🐍 Python version:"
python3 --version

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check configuration
if [ ! -f "config.yaml" ]; then
    echo "⚠️  Warning: config.yaml not found"
    echo "   Please copy and configure config.yaml before running in live mode"
    echo "   Paper trading mode will work without wallet configuration"
fi

# Start the bot
echo "🚀 Starting Workhorse..."
echo "   Web interface will be available at: http://localhost:5000"
echo "   Press Ctrl+C to stop"
echo ""

# Run with memory optimizations
exec python3 main.py
