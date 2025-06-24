"""
API endpoints for AgentMap using the new service architecture.
"""

from agentmap.core.api.fastapi_server import create_fastapi_app, run_server

__all__ = ["create_fastapi_app", "run_server"]
