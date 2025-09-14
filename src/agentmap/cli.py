"""
AgentMap CLI entry point.

This module provides the main CLI interface by importing and re-exporting
the actual CLI implementation from agentmap.core.cli.
"""

from agentmap.deployment.cli.main_cli import app, main_cli

# Re-export the CLI app for poetry scripts entry point
__all__ = ["app", "main_cli"]

# Allow running as module: python -m agentmap.cli
if __name__ == "__main__":
    main_cli()
