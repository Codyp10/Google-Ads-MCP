"""
Entry point for the Google Ads MCP Server.

Supports two transport modes:
  - streamable-http (default): For remote deployment and Claude.ai connectors
  - stdio: For local testing with MCP clients

Usage:
  python main.py                  # HTTP mode on 0.0.0.0:8000
  python main.py --stdio          # Stdio mode for local testing
  PORT=9000 python main.py        # Custom port
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.server import mcp


def main():
    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        host = os.environ.get("HOST", "0.0.0.0")
        port = os.environ.get("PORT", "8000")
        print(f"Starting Google Ads MCP Server on {host}:{port}")
        print(f"MCP endpoint: http://{host}:{port}/mcp")
        print(f"Health check: http://{host}:{port}/health")
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
