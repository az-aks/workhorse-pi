#!/usr/bin/env python3
"""
Startup Script for Solana DEX Arbitrage Bot
This script ensures all dependencies are installed before starting the bot.
"""

import sys
import os
import subprocess
import threading
import yaml
import time

def check_dependency(package_name):
    """Check if a Python package is installed."""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

def load_config():
    """Load configuration from config.yaml"""
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        print(f"❌ Configuration file not found: {config_path}")
        return {}
    
    with open(config_path, 'r') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"❌ Error parsing config file: {e}")
            return {}

def main():
    """Main entry point for the startup script."""
    import os  # Ensure os is imported here
    print("🚀 Starting Solana DEX Arbitrage Bot Setup...")
    
    # Check for critical dependencies
    missing_deps = []
    critical_deps = ['flask', 'flask_socketio']
    optional_deps = ['cryptography', 'gevent', 'geventwebsocket']
    
    for dep in critical_deps:
        if not check_dependency(dep):
            missing_deps.append(dep)
    
    for dep in optional_deps:
        if not check_dependency(dep):
            print(f"⚠️  Optional dependency {dep} is not installed. Some features may not work.")
    
    # Install missing dependencies
    if missing_deps:
        print(f"❌ Missing required dependencies: {', '.join(missing_deps)}")
        print("📦 Installing missing dependencies...")
        
        cmd = [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt']
        try:
            subprocess.check_call(cmd)
            print("✅ Dependencies installed successfully!")
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies. Please run: pip install -r requirements.txt")
            sys.exit(1)
    
    # Generate SSL certificate if needed
    if not os.path.exists('ssl/cert.pem') or not os.path.exists('ssl/key.pem'):
        print("🔒 SSL certificates not found. Generating self-signed certificates...")
        
        try:
            if check_dependency('cryptography'):
                # Create ssl directory if it doesn't exist
                if not os.path.exists('ssl'):
                    os.makedirs('ssl')
                    
                # Import generate_cert and run it
                from generate_cert import generate_self_signed_cert
                generate_self_signed_cert()
                print("✅ SSL certificates generated successfully!")
            else:
                print("⚠️  Cryptography package not installed. HTTPS will not be available.")
        except Exception as e:
            print(f"❌ Failed to generate SSL certificates: {e}")
            print("⚠️  The bot will start without HTTPS.")
    
    # Check port permissions
    import yaml
    config = {}
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️ Warning: Could not read config.yaml: {e}")
        
    web_config = config.get('web', {})
    port = web_config.get('port', 443)
    use_https = web_config.get('use_https', True)
    
    # Check if we're trying to use a privileged port
    if port < 1024:
        import os
        if os.name != 'nt':  # Unix-like systems require root for ports < 1024
            if os.geteuid() != 0:
                print(f"⚠️ Port {port} requires root privileges on Unix-like systems.")
                print("You have two options:")
                print("1. Run with sudo:  sudo python start.py")
                print(f"2. Change the port to > 1024 in config.yaml (e.g., {8443 if use_https else 8080})")
                
                answer = input("Would you like to automatically modify config.yaml to use a non-privileged port? (y/n): ")
                if answer.lower().startswith('y'):
                    try:
                        new_port = 8443 if use_https else 8080
                        web_config['port'] = new_port
                        config['web'] = web_config
                        
                        with open('config.yaml', 'w') as f:
                            yaml.dump(config, f, default_flow_style=False)
                            
                        print(f"✅ Updated config.yaml to use port {new_port}")
                        port = new_port
                    except Exception as e:
                        print(f"❌ Failed to update config.yaml: {e}")
                        print("Please manually edit the file and change the port.")
    
    # Start HTTP to HTTPS redirect server if HTTPS is enabled
    redirect_thread = None
    if use_https:
        http_port = 80  # Standard HTTP port for redirect
        try:
            print(f"🔄 Setting up HTTP to HTTPS redirection (port {http_port} -> {port})...")
            
            try:
                # Use the proper http_redirect module
                from http_redirect import run_redirect_server
                
                # Start the redirect server
                try:
                    redirect_thread = threading.Thread(
                        target=run_redirect_server,
                        args=(http_port, port),
                        daemon=True
                    )
                    redirect_thread.start()
                    print(f"✅ HTTP to HTTPS redirection activated (port {http_port} → {port})")
                    
                except PermissionError:
                    print("⚠️ Could not start HTTP redirect server - permission denied for port 80")
                    print("   To enable HTTP to HTTPS redirection, run with sudo/administrator privileges")
                    
            except ImportError as e:
                print(f"⚠️ Could not import http_redirect module: {e}")
                
        except Exception as e:
            print(f"⚠️ Failed to set up HTTP redirection: {e}")
        
    # Start the bot
    print(f"🚀 Starting the bot on {'https' if use_https else 'http'}://localhost{f':{port}' if port != (443 if use_https else 80) else ''}")
    try:
        import main
        import asyncio
        asyncio.run(main.main())
    except ImportError as e:
        print(f"❌ Failed to start bot: {e}")
        sys.exit(1)
    except PermissionError as e:
        print(f"❌ Permission error: {e}")
        print(f"This is likely because port {port} requires administrator/root privileges.")
        print("Please either:")
        print("1. Run with sudo/administrator privileges")
        print("2. Edit config.yaml to use a port > 1024")
        sys.exit(1)
    finally:
        # No temporary files to clean up when using the proper module
        pass
        
if __name__ == "__main__":
    main()
