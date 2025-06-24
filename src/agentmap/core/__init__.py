"""
Core layer initialization.

This module exports core functionality for CLI, API, and serverless handlers
using the new service architecture.
"""

from agentmap.core.adapters import ServiceAdapter, create_service_adapter

__all__ = ["ServiceAdapter", "create_service_adapter"]
