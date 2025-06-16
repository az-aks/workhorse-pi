#!/usr/bin/env python3
"""
Simple redirect server for HTTP to HTTPS redirection
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import argparse
import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class RedirectHandler(BaseHTTPRequestHandler):
    """Handler to redirect HTTP requests to HTTPS"""
    
    def do_GET(self):
        """Redirect GET requests to HTTPS"""
        self.redirect_to_https()
    
    def do_POST(self):
        """Redirect POST requests to HTTPS"""
        self.redirect_to_https()
    
    def redirect_to_https(self):
        """Perform the redirection"""
        host = self.headers.get('Host', '').split(':')[0]
        if not host:
            host = 'localhost'
            
        https_port = self.server.https_port
        target_url = f"https://{host}"
        
        # Only include port in the URL if it's not the standard HTTPS port (443)
        if https_port != 443:
            target_url += f":{https_port}"
            
        target_url += self.path
        
        self.send_response(301)
        self.send_header('Location', target_url)
        self.send_header('Content-Length', '0')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")

def run_redirect_server(http_port, https_port):
    """Run the HTTP to HTTPS redirect server"""
    try:
        server = HTTPServer(('0.0.0.0', http_port), RedirectHandler)
        server.https_port = https_port
        logger.info(f"Starting HTTP->HTTPS redirect server on port {http_port}, redirecting to HTTPS port {https_port}")
        server.serve_forever()
    except PermissionError:
        logger.error(f"Permission error: Cannot bind to port {http_port}. Try running with sudo or as administrator.")
        logger.info("You can also modify config.yaml to use ports above 1024 for both HTTP and HTTPS.")
        sys.exit(1)
    except OSError as e:
        logger.error(f"Error starting redirect server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTTP to HTTPS redirect server")
    parser.add_argument("--http-port", type=int, default=80, help="HTTP port to listen on")
    parser.add_argument("--https-port", type=int, default=443, help="HTTPS port to redirect to")
    args = parser.parse_args()
    
    run_redirect_server(args.http_port, args.https_port)
