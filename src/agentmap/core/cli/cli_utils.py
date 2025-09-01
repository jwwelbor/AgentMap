"""
Common utilities for CLI commands.

This module provides shared functionality for CLI commands to reduce
code duplication while maintaining clear error handling and user feedback.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import typer

from agentmap.di import initialize_di


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
    container = initialize_di(config_file)
    features_service = container.features_registry_service()
    dependency_checker = container.dependency_checker_service()

    # Build LLM diagnostic information
    llm_info = {}
    for provider in ["openai", "anthropic", "google"]:
        has_deps, missing = dependency_checker.check_llm_dependencies(provider)
        registered = features_service.is_provider_registered("llm", provider)
        validated = features_service.is_provider_validated("llm", provider)
        available = features_service.is_provider_available("llm", provider)

        llm_info[provider] = {
            "available": available,
            "registered": registered,
            "validated": validated,
            "has_dependencies": has_deps,
            "missing_dependencies": missing,
        }

    # Build storage diagnostic information
    storage_info = {}
    for storage_type in ["csv", "json", "file", "vector", "firebase", "blob"]:
        has_deps, missing = dependency_checker.check_storage_dependencies(storage_type)
        registered = features_service.is_provider_registered("storage", storage_type)
        validated = features_service.is_provider_validated("storage", storage_type)
        available = features_service.is_provider_available("storage", storage_type)

        storage_info[storage_type] = {
            "available": available,
            "registered": registered,
            "validated": validated,
            "has_dependencies": has_deps,
            "missing_dependencies": missing,
        }

    # Build environment information
    import os
    import sys

    environment = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "current_directory": os.getcwd(),
        "platform": sys.platform,
    }

    # Get package versions
    packages = [
        "openai",
        "anthropic",
        "google.generativeai",
        "langchain",
        "langchain_google_genai",
        "chromadb",
    ]
    package_versions = {}
    for package in packages:
        try:
            if "." in package:
                base_pkg = package.split(".")[0]
                module = __import__(base_pkg)
                package_versions[package] = f"Installed (base package {base_pkg})"
            else:
                module = __import__(package)
                version = getattr(module, "__version__", "unknown")
                package_versions[package] = version
        except ImportError:
            package_versions[package] = "Not installed"

    # Build installation suggestions
    installation_suggestions = []

    # Check if LLM feature is enabled
    if not features_service.is_feature_enabled("llm"):
        installation_suggestions.append(
            "To enable LLM agents: pip install agentmap[llm]"
        )

    # Check if storage feature is enabled
    if not features_service.is_feature_enabled("storage"):
        installation_suggestions.append(
            "To enable storage agents: pip install agentmap[storage]"
        )

    # Provider-specific suggestions
    if not dependency_checker.check_llm_dependencies("openai")[0]:
        installation_suggestions.append(
            "For OpenAI support: pip install agentmap[openai] or pip install openai>=1.0.0"
        )

    if not dependency_checker.check_llm_dependencies("anthropic")[0]:
        installation_suggestions.append(
            "For Anthropic support: pip install agentmap[anthropic] or pip install anthropic"
        )

    if not dependency_checker.check_llm_dependencies("google")[0]:
        installation_suggestions.append(
            "For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai"
        )

    if not dependency_checker.check_storage_dependencies("vector")[0]:
        installation_suggestions.append("For vector storage: pip install chromadb")

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
    container = initialize_di()
    validation_cache_service = container.validation_cache_service()
    cache_stats = validation_cache_service.get_validation_cache_stats()

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
    container = initialize_di()
    validation_cache_service = container.validation_cache_service()

    if file_path:
        removed = validation_cache_service.clear_validation_cache(file_path)
        operation = f"clear_file:{file_path}"
    elif cleanup_expired:
        removed = validation_cache_service.cleanup_validation_cache()
        operation = "cleanup_expired"
    else:
        removed = validation_cache_service.clear_validation_cache()
        operation = "clear_all"

    return {
        "success": True,
        "operation": operation,
        "removed_count": removed,
        "file_path": file_path,
    }
