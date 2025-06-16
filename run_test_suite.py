#!/usr/bin/env python3
"""
Comprehensive test suite runner for DEX arbitrage bot
Runs all test scripts to verify proper handling of various failure scenarios
"""

import os
import sys
import logging
import asyncio
import time
import subprocess
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_suite_results.log')
    ]
)

logger = logging.getLogger(__name__)

# List of test scripts to run
TEST_SCRIPTS = [
    "test_trade_failures.py",              # Original trade failure tests
    "test_additional_trade_failures.py",   # Additional trade failure scenarios
    "test_price_volatility.py",            # Price volatility and discrepancy tests
    "test_token_edge_cases.py",            # Token-specific edge cases
    "test_trading_limits.py",              # Trading limits enforcement tests
    "test_balances.py",                    # Wallet balance tests
    "test_network_failures.py",            # Network-related failure tests
    "test_slippage_failures.py"            # DEX slippage and liquidity tests
]

async def run_test_script(script_name):
    """Run a single test script and return the result"""
    start_time = time.time()
    logger.info(f"{'=' * 80}")
    logger.info(f"Starting test script: {script_name}")
    
    try:
        # Run the script as a subprocess
        process = await asyncio.create_subprocess_exec(
            sys.executable, script_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Log the output
        if stdout:
            logger.info(f"[{script_name}] Standard output:")
            for line in stdout.decode().splitlines():
                logger.info(f"  {line}")
                
        if stderr:
            logger.warning(f"[{script_name}] Standard error:")
            for line in stderr.decode().splitlines():
                logger.warning(f"  {line}")
        
        # Check return code
        if process.returncode == 0:
            result = "SUCCESS"
        else:
            result = f"FAILED (return code {process.returncode})"
            
        elapsed_time = time.time() - start_time
        logger.info(f"Finished {script_name}: {result} in {elapsed_time:.1f} seconds")
        return {
            "script": script_name,
            "result": result,
            "return_code": process.returncode,
            "elapsed_time": elapsed_time
        }
        
    except Exception as e:
        logger.error(f"Error running {script_name}: {str(e)}", exc_info=True)
        elapsed_time = time.time() - start_time
        return {
            "script": script_name,
            "result": f"ERROR: {str(e)}",
            "return_code": -1,
            "elapsed_time": elapsed_time
        }

async def run_all_tests():
    """Run all test scripts and report results"""
    logger.info(f"Starting comprehensive test suite at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Running {len(TEST_SCRIPTS)} test scripts")
    
    start_time = time.time()
    results = []
    
    # Run all test scripts
    for script in TEST_SCRIPTS:
        result = await run_test_script(script)
        results.append(result)
    
    # Summarize results
    total_time = time.time() - start_time
    success_count = sum(1 for r in results if r["return_code"] == 0)
    failure_count = len(results) - success_count
    
    logger.info(f"\n{'=' * 80}")
    logger.info(f"TEST SUITE SUMMARY")
    logger.info(f"{'-' * 80}")
    logger.info(f"Total scripts:   {len(results)}")
    logger.info(f"Successful:      {success_count}")
    logger.info(f"Failed:          {failure_count}")
    logger.info(f"Total time:      {total_time:.1f} seconds")
    logger.info(f"{'-' * 80}")
    
    # Show individual results
    logger.info("Individual test results:")
    for result in results:
        status_indicator = "✅" if result["return_code"] == 0 else "❌"
        logger.info(f"{status_indicator} {result['script']:<30} {result['result']:<20} {result['elapsed_time']:.1f}s")
    
    logger.info(f"{'=' * 80}")
    logger.info(f"Test suite completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Return success if all tests pass
    return success_count == len(results)

if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest suite interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
