"""
Entry point for the Google Ads MCP Server.

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
        import uvicorn
        import anyio

        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", 8000))

        # Override the settings so streamable_http_app picks them up
        mcp.settings.host = host
        mcp.settings.port = port

        print(f"Starting Google Ads MCP Server on {host}:{port}")
        print(f"MCP endpoint: http://{host}:{port}/mcp")
        print(f"Health check: http://{host}:{port}/health")

        async def serve():
            app = mcp.streamable_http_app()
            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level="info",
            )
            server = uvicorn.Server(config)
            await server.serve()

        anyio.run(serve)


if __name__ == "__main__":
    main()
