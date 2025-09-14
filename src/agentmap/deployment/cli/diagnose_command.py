"""
CLI diagnose command handler - FIXED VERSION.

This module provides the diagnose command for system health and dependency checking
using the new service architecture. Now properly discovers and validates providers
to match runtime behavior.
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

    logger = logging_service.get_logger("agentmap.cli.diagnostic")

    typer.echo("AgentMap Dependency Diagnostics")
    typer.echo("=============================")

    # IMPORTANT: Run discovery first to match runtime behavior
    # This will auto-enable features if dependencies are found
    typer.echo("\nDiscovering available providers...")

    # Force discovery to bypass cache and get fresh results
    llm_providers = dependency_checker.discover_and_validate_providers(
        "llm", force=True
    )
    storage_providers = dependency_checker.discover_and_validate_providers(
        "storage", force=True
    )

    # Now the feature states will be accurate
    typer.echo("\n✅ Discovery complete. Showing actual runtime state:\n")

    # Check LLM dependencies
    typer.echo("LLM Dependencies:")
    llm_enabled = features_service.is_feature_enabled("llm")
    typer.echo(f"  Feature Status: {'✅ Enabled' if llm_enabled else '❌ Disabled'}")
    typer.echo(
        f"  Available Providers: {[p for p, avail in llm_providers.items() if avail] or 'None'}"
    )

    typer.echo("\n  Provider Details:")
    for provider in ["openai", "anthropic", "google"]:
        # Get validation status from discovery results
        is_available = llm_providers.get(provider, False)

        # Check what's missing if not available
        has_deps, missing = dependency_checker.check_llm_dependencies(provider)

        if is_available:
            status = "✅ Available and validated"
        elif has_deps:
            status = "⚠️ Dependencies found but validation failed"
        else:
            status = f"❌ Missing dependencies: {', '.join(missing)}"

        typer.echo(f"    {provider.capitalize()}: {status}")

    # Check storage dependencies
    typer.echo("\nStorage Dependencies:")
    storage_enabled = features_service.is_feature_enabled("storage")
    typer.echo(
        f"  Feature Status: {'✅ Enabled' if storage_enabled else '❌ Disabled'}"
    )
    typer.echo(
        f"  Available Types: {[t for t, avail in storage_providers.items() if avail] or 'None'}"
    )

    typer.echo("\n  Storage Type Details:")
    for storage_type in ["csv", "json", "file", "vector", "firebase", "blob"]:
        # Get validation status from discovery results
        is_available = storage_providers.get(storage_type, False)

        # For built-in types that don't require external deps
        if storage_type in ["json", "file"]:
            status = "✅ Built-in (always available)"
        else:
            # Check what's missing if not available
            has_deps, missing = dependency_checker.check_storage_dependencies(
                storage_type
            )

            if is_available:
                status = "✅ Available and validated"
            elif has_deps:
                status = "⚠️ Dependencies found but validation failed"
            else:
                status = f"❌ Missing dependencies: {', '.join(missing) if missing else 'Not configured'}"

        typer.echo(f"    {storage_type}: {status}")

    # Installation suggestions based on actual missing dependencies
    missing_suggestions = []

    if not llm_enabled or not any(llm_providers.values()):
        missing_suggestions.append("To enable LLM agents: pip install agentmap[llm]")

    for provider in ["openai", "anthropic", "google"]:
        if not llm_providers.get(provider, False):
            if provider == "openai":
                missing_suggestions.append(
                    "For OpenAI: pip install openai>=1.0.0 langchain-openai"
                )
            elif provider == "anthropic":
                missing_suggestions.append(
                    "For Anthropic: pip install anthropic langchain-anthropic"
                )
            elif provider == "google":
                missing_suggestions.append(
                    "For Google: pip install google-generativeai langchain-google-genai"
                )

    if not storage_enabled:
        missing_suggestions.append(
            "To enable storage agents: pip install agentmap[storage]"
        )

    if not storage_providers.get("vector", False):
        missing_suggestions.append("For vector storage: pip install chromadb")

    if missing_suggestions:
        typer.echo("\nInstallation Suggestions:")
        for suggestion in missing_suggestions:
            typer.echo(f"  • {suggestion}")

    # Show environment info
    typer.echo("\nEnvironment Information:")
    import os
    import sys

    typer.echo(f"  Python Version: {sys.version}")
    typer.echo(f"  Python Path: {sys.executable}")
    typer.echo(f"  Current Directory: {os.getcwd()}")

    # List installed versions of key packages
    typer.echo("\nInstalled Package Versions:")
    packages = [
        ("openai", "OpenAI SDK"),
        ("anthropic", "Anthropic SDK"),
        ("google.generativeai", "Google AI SDK"),
        ("langchain", "LangChain Core"),
        ("langchain_openai", "LangChain OpenAI"),
        ("langchain_anthropic", "LangChain Anthropic"),
        ("langchain_google_genai", "LangChain Google"),
        ("chromadb", "ChromaDB"),
        ("pandas", "Pandas (CSV support)"),
    ]

    for package, display_name in packages:
        try:
            if "." in package:
                base_pkg = package.split(".")[0]
                module = __import__(base_pkg)
                typer.echo(f"  {display_name}: ✅ Installed")
            else:
                module = __import__(package)
                version = getattr(module, "__version__", "unknown")
                typer.echo(f"  {display_name}: ✅ v{version}")
        except ImportError:
            typer.echo(f"  {display_name}: ❌ Not installed")

    # Summary
    typer.echo("\n" + "=" * 50)
    typer.echo("Summary:")

    llm_ready = llm_enabled and any(llm_providers.values())
    storage_ready = storage_enabled and any(storage_providers.values())

    if llm_ready and storage_ready:
        typer.echo("✅ AgentMap is fully operational with LLM and storage support!")
    elif llm_ready:
        typer.echo("⚠️ AgentMap has LLM support but limited storage capabilities.")
    elif storage_ready:
        typer.echo("⚠️ AgentMap has storage support but no LLM capabilities.")
    else:
        typer.echo("❌ AgentMap has limited functionality. Install dependencies above.")
