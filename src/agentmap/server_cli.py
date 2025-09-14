"""
AgentMap Server CLI entry point.

This module provides the server CLI interface by importing and re-exporting
the FastAPI server implementation from agentmap.infrastructure.api.fastapi.
"""

from agentmap.deployment.http.api.server import (
    create_fastapi_app,
    main,
    run_server,
)

# Re-export for poetry scripts entry point
__all__ = ["main", "run_server", "create_fastapi_app"]

# Allow running as module: python -m agentmap.server_cli
if __name__ == "__main__":
    main()
