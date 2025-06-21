#!/usr/bin/env python3
"""
CPU Optimization Helper for Workhorse
Easily toggle performance settings to reduce CPU usage
"""

import yaml
import sys
from pathlib import Path

def load_config():
    """Load the current configuration."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("❌ Error: config.yaml not found")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def save_config(config):
    """Save the configuration back to file."""
    config_path = Path("config.yaml")
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)

def show_current_settings(config):
    """Display current performance settings."""
    perf = config.get('performance', {})
    print("\n📊 Current Performance Settings:")
    print(f"  Background Tasks: {'✅ Enabled' if perf.get('enable_background_tasks', True) else '❌ Disabled'}")
    print(f"  Balance Update Interval: {perf.get('balance_update_interval', 300)} seconds")
    print(f"  Status Update Interval: {perf.get('status_update_interval', 60)} seconds")
    print(f"  Price Logging: {'❌ Disabled' if perf.get('disable_price_logging', False) else '✅ Enabled'}")
    print(f"  Minimal Updates: {'✅ Enabled' if perf.get('minimal_updates', False) else '❌ Disabled'}")
    print(f"  Max Workers: {perf.get('max_workers', 2)}")
    print(f"  Price Change Threshold: {perf.get('price_change_threshold', 0.01)*100}%")
    
    logging = config.get('logging', {})
    print(f"  Log Level: {logging.get('level', 'INFO')}")

def apply_high_performance_mode(config):
    """Apply settings for high performance (normal CPU usage)."""
    print("🚀 Applying HIGH PERFORMANCE mode...")
    
    perf = config.setdefault('performance', {})
    perf['enable_background_tasks'] = True
    perf['balance_update_interval'] = 300  # 5 minutes
    perf['status_update_interval'] = 60    # 1 minute
    perf['price_log_interval'] = 60        # 1 minute
    perf['health_check_interval'] = 300    # 5 minutes
    perf['disable_price_logging'] = False
    perf['minimal_updates'] = False
    perf['max_workers'] = 2
    perf['price_change_threshold'] = 0.005  # 0.5%
    
    logging = config.setdefault('logging', {})
    logging['level'] = 'INFO'
    
    print("✅ High performance mode applied")

def apply_balanced_mode(config):
    """Apply settings for balanced performance (moderate CPU usage)."""
    print("⚖️ Applying BALANCED mode...")
    
    perf = config.setdefault('performance', {})
    perf['enable_background_tasks'] = True
    perf['balance_update_interval'] = 600  # 10 minutes
    perf['status_update_interval'] = 120   # 2 minutes
    perf['price_log_interval'] = 300       # 5 minutes
    perf['health_check_interval'] = 600    # 10 minutes
    perf['disable_price_logging'] = False
    perf['minimal_updates'] = False
    perf['max_workers'] = 1
    perf['price_change_threshold'] = 0.01  # 1%
    
    logging = config.setdefault('logging', {})
    logging['level'] = 'WARNING'
    
    print("✅ Balanced mode applied")

def apply_low_cpu_mode(config):
    """Apply settings for minimal CPU usage."""
    print("🔋 Applying LOW CPU mode...")
    
    perf = config.setdefault('performance', {})
    perf['enable_background_tasks'] = False  # Disable background tasks
    perf['balance_update_interval'] = 1800   # 30 minutes
    perf['status_update_interval'] = 300     # 5 minutes
    perf['price_log_interval'] = 600         # 10 minutes
    perf['health_check_interval'] = 1200     # 20 minutes
    perf['disable_price_logging'] = True     # Disable price logging
    perf['minimal_updates'] = True           # Enable minimal updates
    perf['max_workers'] = 1
    perf['price_change_threshold'] = 0.02    # 2% - only process significant changes
    
    logging = config.setdefault('logging', {})
    logging['level'] = 'ERROR'  # Only log errors
    
    print("✅ Low CPU mode applied")
    print("⚠️  Note: Background balance updates and real-time features are disabled")

def main():
    """Main menu for CPU optimization."""
    config = load_config()
    
    while True:
        print("\n🐎 Workhorse CPU Optimization Tool")
        print("=" * 40)
        
        show_current_settings(config)
        
        print("\n🔧 Available Modes:")
        print("  1. High Performance (Normal CPU usage, all features)")
        print("  2. Balanced (Moderate CPU usage, most features)")
        print("  3. Low CPU (Minimal CPU usage, reduced features)")
        print("  4. Custom Settings")
        print("  5. Exit")
        
        choice = input("\nSelect mode (1-5): ").strip()
        
        if choice == '1':
            apply_high_performance_mode(config)
            save_config(config)
        elif choice == '2':
            apply_balanced_mode(config)
            save_config(config)
        elif choice == '3':
            apply_low_cpu_mode(config)
            save_config(config)
        elif choice == '4':
            custom_settings_menu(config)
        elif choice == '5':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice, please try again")

def custom_settings_menu(config):
    """Custom settings menu for fine-tuning."""
    perf = config.setdefault('performance', {})
    
    print("\n🔧 Custom Settings")
    print("=" * 20)
    
    # Background tasks
    current = perf.get('enable_background_tasks', True)
    response = input(f"Enable background tasks? (current: {current}) [y/n/skip]: ").strip().lower()
    if response in ['y', 'yes']:
        perf['enable_background_tasks'] = True
    elif response in ['n', 'no']:
        perf['enable_background_tasks'] = False
    
    # Balance update interval
    if perf.get('enable_background_tasks', True):
        current = perf.get('balance_update_interval', 600)
        response = input(f"Balance update interval in seconds (current: {current}): ").strip()
        if response.isdigit():
            perf['balance_update_interval'] = int(response)
    
    # Disable price logging
    current = perf.get('disable_price_logging', False)
    response = input(f"Disable price logging? (current: {current}) [y/n/skip]: ").strip().lower()
    if response in ['y', 'yes']:
        perf['disable_price_logging'] = True
    elif response in ['n', 'no']:
        perf['disable_price_logging'] = False
    
    # Minimal updates
    current = perf.get('minimal_updates', False)
    response = input(f"Enable minimal updates mode? (current: {current}) [y/n/skip]: ").strip().lower()
    if response in ['y', 'yes']:
        perf['minimal_updates'] = True
    elif response in ['n', 'no']:
        perf['minimal_updates'] = False
    
    # Logging level
    logging_config = config.setdefault('logging', {})
    current = logging_config.get('level', 'INFO')
    print(f"Log levels: ERROR (lowest CPU), WARNING, INFO, DEBUG (highest CPU)")
    response = input(f"Log level (current: {current}): ").strip().upper()
    if response in ['ERROR', 'WARNING', 'INFO', 'DEBUG']:
        logging_config['level'] = response
    
    save_config(config)
    print("✅ Custom settings saved!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
