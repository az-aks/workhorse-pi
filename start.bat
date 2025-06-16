@echo off
REM Windows startup script for Solana DEX Arbitrage Bot

echo 🚀 Starting Solana DEX Arbitrage Bot...

REM Check if Python is installed
where python > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python not found! Please install Python 3.7 or higher.
    pause
    exit /b 1
)

REM Run the bot
python start.py

REM Keep the window open if there's an error
if %ERRORLEVEL% NEQ 0 (
    echo ❌ An error occurred. Please check the logs above.
    pause
)
