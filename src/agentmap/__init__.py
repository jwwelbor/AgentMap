# src/agentmap/__init__.py
"""
AgentMap: Build and deploy LangGraph workflows from CSV files.

This package provides clean architecture with separated concerns:
- Models: Domain entities and validation
- Services: Business logic and orchestration
- Agents: Execution units for business logic processing
- Core: Application entry points (CLI, API, handlers)
- Infrastructure: External integrations and persistence
- DI: Dependency injection and service wiring
"""

from agentmap.deployment.cli import main_cli
from agentmap.deployment.serverless.aws_lambda import lambda_handler
from agentmap.deployment.serverless.azure_functions import azure_http_handler
from agentmap.deployment.serverless.gcp_functions import gcp_http_handler

# Core exports for new architecture
from agentmap.deployment.service_adapter import ServiceAdapter, create_service_adapter

__author__ = "John Welborn"
__license__ = "MIT"
__copyright__ = "Copyright 2025 John Welborn"
__description__ = "A Python package for creating LangGraph maps from CSV files for agentic ai workflows."

__all__ = [
    "ServiceAdapter",
    "create_service_adapter",
    "main_cli",
    "lambda_handler",
    "gcp_http_handler",
    "azure_http_handler",
]
