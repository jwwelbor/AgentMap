"""CLI Presenter utilities for consistent stdout/stderr and exit codes.

Usage in a command:
    from agentmap.runtime_api import run_workflow
    from deployment.cli.utils.cli_presenter import print_json, print_err, map_exception_to_exit_code

    def main(args) -> int:
        try:
            result = run_workflow(args.graph, inputs=args.inputs, profile=args.profile, config_file=args.config)
            print_json(result)
            return 0
        except Exception as exc:
            print_err(str(exc))
            return map_exception_to_exit_code(exc)
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from typing import Any

try:
    # Prefer importing canonical exceptions if available.
    from agentmap.exceptions.runtime_exceptions import (
        AgentMapNotInitialized,
        GraphNotFound,
        InvalidInputs,
    )
except Exception:  # pragma: no cover
    # Fallback placeholders to avoid hard failures in stub usage.
    class AgentMapNotInitialized(Exception): ...

    class GraphNotFound(Exception): ...

    class InvalidInputs(Exception): ...


class AgentMapJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for AgentMap objects."""

    def default(self, obj: Any) -> Any:
        """Convert non-serializable objects to serializable formats."""
        # Handle datetime objects
        if isinstance(obj, datetime):
            return obj.isoformat()

        # Handle StorageResult objects
        if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
            return obj.to_dict()

        # Handle dataclass objects (ExecutionSummary, NodeExecution)
        if hasattr(obj, "__dataclass_fields__"):
            result = asdict(obj)
            # Recursively process nested datetime objects
            return self._process_nested_datetimes(result)

        # Let the base class handle other objects
        return super().default(obj)

    def _process_nested_datetimes(self, obj: Any) -> Any:
        """Recursively process nested structures to convert datetime objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._process_nested_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._process_nested_datetimes(item) for item in obj]
        else:
            return obj


def print_json(payload: dict) -> None:
    """Pretty-print JSON to stdout."""
    sys.stdout.write(
        json.dumps(payload, indent=2, ensure_ascii=False, cls=AgentMapJSONEncoder)
        + "\n"
    )
    sys.stdout.flush()


def print_err(message: str) -> None:
    """Print an error message to stderr."""
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def map_exception_to_exit_code(exc: Exception) -> int:
    """Map runtime facade exceptions to process exit codes.

    Returns:
        int: Exit code (0 success not represented here).
    """
    if isinstance(exc, InvalidInputs):
        return 2
    if isinstance(exc, GraphNotFound):
        return 3
    if isinstance(exc, AgentMapNotInitialized):
        return 4
    # Unknown/unexpected
    return 1
