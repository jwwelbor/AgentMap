"""
Common utilities for CLI commands.

This module provides shared functionality for CLI commands to reduce
code duplication while maintaining clear error handling and user feedback.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import typer

from agentmap.runtime_api import diagnose_system, validate_cache


def resolve_csv_path(
    csv_file: Optional[str] = None, csv_option: Optional[str] = None
) -> Path:
    """
    Resolve CSV path from either positional argument or option.

    Args:
        csv_file: Positional CSV file argument
        csv_option: --csv option value

    Returns:
        Path object for the CSV file

    Raises:
        typer.Exit: If CSV is not provided or doesn't exist
    """
    # Handle shorthand CSV file argument
    csv = csv_file if csv_file is not None else csv_option

    if not csv:
        typer.secho("❌ CSV file required", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    csv_path = Path(csv)
    if not csv_path.exists():
        typer.secho(f"❌ CSV file not found: {csv_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    return csv_path


def parse_json_state(state_str: str) -> Dict[str, Any]:
    """
    Parse JSON state string with error handling.

    Args:
        state_str: JSON string to parse

    Returns:
        Parsed dictionary

    Raises:
        typer.Exit: If JSON is invalid
    """
    if state_str == "{}":
        return {}

    try:
        return json.loads(state_str)
    except json.JSONDecodeError as e:
        typer.secho(f"❌ Invalid JSON in --state: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def handle_command_error(e: Exception, verbose: bool = False) -> None:
    """
    Standard error handling for CLI commands.

    Args:
        e: Exception that occurred
        verbose: Whether to show detailed traceback
    """
    typer.secho(f"❌ Error: {str(e)}", fg=typer.colors.RED)

    if verbose:
        import traceback

        typer.secho("\nDetailed error trace:", fg=typer.colors.YELLOW)
        typer.echo(traceback.format_exc())

    raise typer.Exit(code=1)


# Helper functions for backward compatibility and easier testing
def diagnose_command(config_file: Optional[str] = None) -> dict:
    """
    Programmatic version of diagnose_cmd that returns structured data.
    Used by API endpoints and testing.
    """
    # Use facade function and extract outputs
    result = diagnose_system(config_file=config_file)
    outputs = result["outputs"]

    # Transform facade format to legacy format for backward compatibility
    llm_info = {}
    storage_info = {}

    if "features" in outputs:
        features = outputs["features"]

        # Transform LLM info
        if "llm" in features and "provider_details" in features["llm"]:
            for provider, details in features["llm"]["provider_details"].items():
                llm_info[provider] = {
                    "available": details["available"],
                    "has_dependencies": details["has_dependencies"],
                    "missing_dependencies": details["missing_dependencies"],
                    # Legacy fields - use available as proxy for registered/validated
                    "registered": details["available"],
                    "validated": details["available"],
                }

        # Transform storage info
        if "storage" in features and "storage_details" in features["storage"]:
            for storage_type, details in features["storage"]["storage_details"].items():
                storage_info[storage_type] = {
                    "available": details["available"],
                    "has_dependencies": details["has_dependencies"],
                    "missing_dependencies": details["missing_dependencies"],
                    # Legacy fields - use available as proxy for registered/validated
                    "registered": details["available"],
                    "validated": details["available"],
                }

    # Extract environment and suggestions
    environment = outputs.get("environment", {})
    package_versions = environment.get("package_versions", {})
    installation_suggestions = outputs.get("suggestions", [])

    return {
        "llm": llm_info,
        "storage": storage_info,
        "environment": environment,
        "package_versions": package_versions,
        "installation_suggestions": installation_suggestions,
    }


def cache_info_command() -> dict:
    """
    Programmatic version of cache info that returns structured data.
    Used by API endpoints and testing.
    """
    # Use facade function for stats
    result = validate_cache(stats=True)
    outputs = result["outputs"]

    cache_stats = outputs["cache_stats"]

    suggestions = []
    if cache_stats["expired_files"] > 0:
        suggestions.append(
            "Run 'agentmap validate-cache --cleanup' to remove expired entries"
        )
    if cache_stats["corrupted_files"] > 0:
        suggestions.append(
            f"Found {cache_stats['corrupted_files']} corrupted cache files"
        )

    return {"cache_statistics": cache_stats, "suggestions": suggestions}


def clear_cache_command(
    file_path: Optional[str] = None, cleanup_expired: bool = False
) -> dict:
    """
    Programmatic version of cache clearing that returns structured data.
    Used by API endpoints and testing.
    """
    # Use facade function for cache operations
    if file_path:
        result = validate_cache(clear=True, file_path=file_path)
        operation = f"clear_file:{file_path}"
    elif cleanup_expired:
        result = validate_cache(cleanup=True)
        operation = "cleanup_expired"
    else:
        result = validate_cache(clear=True)
        operation = "clear_all"

    outputs = result["outputs"]
    removed = outputs["removed_entries"]

    return {
        "success": True,
        "operation": operation,
        "removed_count": removed,
        "file_path": file_path,
    }
