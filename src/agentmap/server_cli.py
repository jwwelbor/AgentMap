"""
AgentMap Server CLI entry point.

This module provides the server CLI interface by importing and re-exporting
the FastAPI server implementation from agentmap.core.api.
"""

from agentmap.core.api.fastapi_server import main, run_server, create_fastapi_app

# Re-export for poetry scripts entry point
__all__ = ["main", "run_server", "create_fastapi_app"]

# Allow running as module: python -m agentmap.server_cli
if __name__ == "__main__":
    main()
