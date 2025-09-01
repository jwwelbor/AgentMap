"""
CLI diagnose command handler.

This module provides the diagnose command for system health and dependency checking
using the new service architecture.
"""

from typing import Optional

import typer

from agentmap.di import initialize_di


def diagnose_cmd(
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    )
):
    """Check and display dependency status for all components."""
    container = initialize_di(config_file)
    features_service = container.features_registry_service()
    dependency_checker = container.dependency_checker_service()
    logging_service = container.logging_service()

    logging_service.get_logger("agentmap.cli.diagnostic")

    typer.echo("AgentMap Dependency Diagnostics")
    typer.echo("=============================")

    # Check LLM dependencies
    typer.echo("\nLLM Dependencies:")
    llm_enabled = features_service.is_feature_enabled("llm")
    typer.echo(f"LLM feature enabled: {llm_enabled}")

    for provider in ["openai", "anthropic", "google"]:
        # Get fresh dependency check
        has_deps, missing = dependency_checker.check_llm_dependencies(provider)

        # Check registry status for comparison
        registered = features_service.is_provider_registered("llm", provider)
        validated = features_service.is_provider_validated("llm", provider)
        available = features_service.is_provider_available("llm", provider)

        status = "✅ Available" if has_deps and available else "❌ Not available"

        # Detect inconsistencies
        if has_deps and not available:
            status = "⚠️ Dependencies OK but provider not available (Registration issue)"
        elif not has_deps and available:
            status = (
                "⚠️ INCONSISTENT: Provider marked available but dependencies missing"
            )

        if missing:
            status += f" (Missing: {', '.join(missing)})"

        # Add registry status
        status += f" [Registry: reg={registered}, val={validated}, avail={available}]"

        typer.echo(f"  {provider.capitalize()}: {status}")

    # Check storage dependencies
    typer.echo("\nStorage Dependencies:")
    storage_enabled = features_service.is_feature_enabled("storage")
    typer.echo(f"Storage feature enabled: {storage_enabled}")

    for storage_type in ["csv", "json", "file", "vector", "firebase", "blob"]:
        # Get fresh dependency check
        has_deps, missing = dependency_checker.check_storage_dependencies(storage_type)

        # Check registry status
        registered = features_service.is_provider_registered("storage", storage_type)
        validated = features_service.is_provider_validated("storage", storage_type)
        available = features_service.is_provider_available("storage", storage_type)

        status = "✅ Available" if has_deps and available else "❌ Not available"

        # Detect inconsistencies
        if has_deps and not available:
            status = "⚠️ Dependencies OK but provider not available (Registration issue)"
        elif not has_deps and available:
            status = (
                "⚠️ INCONSISTENT: Provider marked available but dependencies missing"
            )

        if missing:
            status += f" (Missing: {', '.join(missing)})"

        # Add registry status
        status += f" [Registry: reg={registered}, val={validated}, avail={available}]"

        typer.echo(f"  {storage_type}: {status}")

    # Installation suggestions
    typer.echo("\nInstallation Suggestions:")

    # Check overall LLM and storage availability
    has_any_llm = any(
        dependency_checker.check_llm_dependencies(provider)[0]
        for provider in ["openai", "anthropic", "google"]
    )

    if not has_any_llm or not llm_enabled:
        typer.echo("  To enable LLM agents: pip install agentmap[llm]")
    if not storage_enabled:
        typer.echo("  To enable storage agents: pip install agentmap[storage]")

    # Provider-specific suggestions
    has_openai, _ = dependency_checker.check_llm_dependencies("openai")
    if not has_openai:
        typer.echo(
            "  For OpenAI support: pip install agentmap[openai] or pip install openai>=1.0.0"
        )

    has_anthropic, _ = dependency_checker.check_llm_dependencies("anthropic")
    if not has_anthropic:
        typer.echo(
            "  For Anthropic support: pip install agentmap[anthropic] or pip install anthropic"
        )

    has_google, _ = dependency_checker.check_llm_dependencies("google")
    if not has_google:
        typer.echo(
            "  For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai"
        )

    has_vector, _ = dependency_checker.check_storage_dependencies("vector")
    if not has_vector:
        typer.echo("  For vector storage: pip install chromadb")

    # Show path and Python info
    typer.echo("\nEnvironment Information:")
    import os
    import sys

    typer.echo(f"  Python Version: {sys.version}")
    typer.echo(f"  Python Path: {sys.executable}")
    typer.echo(f"  Current Directory: {os.getcwd()}")

    # List installed versions of LLM packages
    typer.echo("\nRelevant Package Versions:")
    packages = [
        "openai",
        "anthropic",
        "google.generativeai",
        "langchain",
        "langchain_google_genai",
        "chromadb",
    ]
    for package in packages:
        try:
            if "." in package:
                base_pkg = package.split(".")[0]
                module = __import__(base_pkg)
                typer.echo(f"  {package}: Installed (base package {base_pkg})")
            else:
                module = __import__(package)
                version = getattr(module, "__version__", "unknown")
                typer.echo(f"  {package}: v{version}")
        except ImportError:
            typer.echo(f"  {package}: Not installed")
