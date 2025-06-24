"""
CLI diagnostic and information command handlers.

This module provides diagnostic commands for system health, dependency checking,
and information display using the new service architecture.
"""

from pathlib import Path
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


def config_cmd(
    config_file: Optional[str] = typer.Option(
        None, "--path", "-p", help="Path to config file to display"
    )
):
    """Print the current configuration values."""
    try:
        # Initialize the container
        container = initialize_di(config_file)

        # Get configuration from the container
        app_config_service = container.app_config_service()
        config_data = app_config_service.get_all()

        print("Configuration values:")
        print("---------------------")
        for k, v in config_data.items():
            if isinstance(v, dict):
                print(f"{k}:")
                for sub_k, sub_v in v.items():
                    if isinstance(sub_v, dict):
                        print(f"  {sub_k}:")
                        for deep_k, deep_v in sub_v.items():
                            print(f"    {deep_k}: {deep_v}")
                    else:
                        print(f"  {sub_k}: {sub_v}")
            else:
                print(f"{k}: {v}")

    except Exception as e:
        typer.secho(f"❌ Failed to load configuration: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def validate_cache_cmd(
    clear: bool = typer.Option(False, "--clear", help="Clear all validation cache"),
    cleanup: bool = typer.Option(
        False, "--cleanup", help="Remove expired cache entries"
    ),
    stats: bool = typer.Option(False, "--stats", help="Show cache statistics"),
    file_path: Optional[str] = typer.Option(
        None, "--file", help="Clear cache for specific file only"
    ),
):
    """Manage validation result cache."""
    container = initialize_di()
    validation_cache_service = container.validation_cache_service()

    if clear:
        if file_path:
            removed = validation_cache_service.clear_validation_cache(file_path)
            typer.secho(
                f"✅ Cleared {removed} cache entries for {file_path}",
                fg=typer.colors.GREEN,
            )
        else:
            removed = validation_cache_service.clear_validation_cache()
            typer.secho(f"✅ Cleared {removed} cache entries", fg=typer.colors.GREEN)

    elif cleanup:
        removed = validation_cache_service.cleanup_validation_cache()
        typer.secho(
            f"✅ Removed {removed} expired cache entries", fg=typer.colors.GREEN
        )

    elif stats or not (clear or cleanup):
        # Show stats by default if no other action specified
        cache_stats = validation_cache_service.get_validation_cache_stats()

        typer.echo("Validation Cache Statistics:")
        typer.echo("=" * 30)
        typer.echo(f"Total files: {cache_stats['total_files']}")
        typer.echo(f"Valid files: {cache_stats['valid_files']}")
        typer.echo(f"Expired files: {cache_stats['expired_files']}")
        typer.echo(f"Corrupted files: {cache_stats['corrupted_files']}")

        if cache_stats["expired_files"] > 0:
            typer.echo(
                f"\n💡 Run 'agentmap validate-cache --cleanup' to remove expired entries"
            )

        if cache_stats["corrupted_files"] > 0:
            typer.echo(
                f"⚠️  Found {cache_stats['corrupted_files']} corrupted cache files"
            )


def inspect_graph_cmd(
    graph_name: str = typer.Argument(..., help="Name of graph to inspect"),
    csv_file: Optional[str] = typer.Option(
        None, "--csv", "-c", help="Path to CSV file"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", help="Path to custom config file"
    ),
    node: Optional[str] = typer.Option(
        None, "--node", "-n", help="Inspect specific node only"
    ),
    show_services: bool = typer.Option(
        True, "--services/--no-services", help="Show service availability"
    ),
    show_protocols: bool = typer.Option(
        True, "--protocols/--no-protocols", help="Show protocol implementations"
    ),
    show_config: bool = typer.Option(
        False, "--config-details", help="Show detailed configuration"
    ),
    show_resolution: bool = typer.Option(
        False, "--resolution", help="Show agent resolution details"
    ),
):
    """Inspect agent service configuration for a graph."""

    container = initialize_di(config_file)
    graph_runner = container.graph_runner_service()

    typer.echo(f"🔍 Inspecting Graph: {graph_name}")
    typer.echo("=" * 50)

    try:
        # Load the graph definition
        csv_path = (
            Path(csv_file)
            if csv_file
            else container.app_config_service().get_csv_path()
        )
        graph_def, resolved_name = graph_runner._load_graph_definition_for_execution(
            csv_path, graph_name
        )

        # Get agent resolution status
        agent_status = graph_runner.get_agent_resolution_status(graph_def)

        typer.echo(f"\n📊 Graph Overview:")
        typer.echo(f"   Resolved Name: {resolved_name}")
        typer.echo(f"   Total Nodes: {agent_status['total_nodes']}")
        typer.echo(
            f"   Unique Agent Types: {agent_status['overall_status']['unique_agent_types']}"
        )
        typer.echo(
            f"   All Resolvable: {'✅' if agent_status['overall_status']['all_resolvable'] else '❌'}"
        )
        typer.echo(
            f"   Resolution Rate: {agent_status['overall_status']['resolution_rate']:.1%}"
        )

        # Show each node/agent
        nodes_to_inspect = [node] if node else list(graph_def.keys())

        for node_name in nodes_to_inspect:
            if node_name not in graph_def:
                typer.secho(
                    f"❌ Node '{node_name}' not found in graph", fg=typer.colors.RED
                )
                continue

            node_def = graph_def[node_name]

            typer.echo(f"\n🤖 Node: {node_name}")
            typer.echo(f"   Agent Type: {node_def.agent_type or 'Default'}")
            typer.echo(f"   Description: {node_def.description or 'No description'}")

            if show_resolution:
                # Show agent resolution details
                agent_type = node_def.agent_type or "Default"
                if agent_type in agent_status["agent_types"]:
                    type_info = agent_status["agent_types"][agent_type]["info"]
                    typer.echo(f"   🔧 Resolution:")
                    typer.echo(
                        f"      Resolvable: {'✅' if type_info['resolvable'] else '❌'}"
                    )
                    typer.echo(f"      Source: {type_info.get('source', 'Unknown')}")
                    if not type_info["resolvable"]:
                        typer.echo(
                            f"      Issue: {type_info.get('resolution_error', 'Unknown error')}"
                        )

            # Try to create the agent to get service info
            try:
                # Get node registry for this graph
                node_registry = graph_runner.node_registry.prepare_for_assembly(
                    graph_def, graph_name
                )

                # Create agent instance
                agent_instance = graph_runner._create_agent_instance(
                    node_def, graph_name, node_registry
                )

                # Get service info using our implemented method
                service_info = agent_instance.get_service_info()

                if show_services:
                    typer.echo(f"   📋 Services:")
                    for service, available in service_info["services"].items():
                        status = "✅" if available else "❌"
                        typer.echo(f"      {service}: {status}")

                if show_protocols:
                    typer.echo(f"   🔌 Protocols:")
                    for protocol, implemented in service_info["protocols"].items():
                        status = "✅" if implemented else "❌"
                        typer.echo(f"      {protocol}: {status}")

                if show_config:
                    # Show any specialized configuration
                    for key, value in service_info.items():
                        if key not in [
                            "agent_name",
                            "agent_type",
                            "services",
                            "protocols",
                            "configuration",
                        ]:
                            typer.echo(f"   ⚙️  {key.replace('_', ' ').title()}:")
                            if isinstance(value, dict):
                                for sub_key, sub_value in value.items():
                                    typer.echo(f"      {sub_key}: {sub_value}")
                            else:
                                typer.echo(f"      {value}")

                # Show basic configuration always
                typer.echo(f"   📝 Configuration:")
                config = service_info["configuration"]
                typer.echo(f"      Input Fields: {config.get('input_fields', [])}")
                typer.echo(f"      Output Field: {config.get('output_field', 'None')}")

            except Exception as e:
                typer.secho(
                    f"   ❌ Failed to create agent: {str(e)}", fg=typer.colors.RED
                )
                # Show what we can from the agent status
                agent_type = node_def.agent_type or "Default"
                if agent_type in agent_status["agent_types"]:
                    type_info = agent_status["agent_types"][agent_type]["info"]
                    if not type_info["resolvable"]:
                        typer.echo(
                            f"   💡 Resolution error: {type_info.get('resolution_error', 'Unknown')}"
                        )
                        if type_info.get("missing_dependencies"):
                            typer.echo(
                                f"   📦 Missing dependencies: {', '.join(type_info['missing_dependencies'])}"
                            )

        # Show issues summary if any
        if agent_status["issues"]:
            typer.echo(f"\n⚠️  Issues Found ({len(agent_status['issues'])}):")
            for issue in agent_status["issues"]:
                typer.echo(f"   {issue['node']}: {issue['issue']}")
                if issue.get("missing_deps"):
                    typer.echo(f"      Missing: {', '.join(issue['missing_deps'])}")
                if issue.get("resolution_error"):
                    typer.echo(f"      Error: {issue['resolution_error']}")
        else:
            typer.secho(
                f"\n✅ No issues found - all agents properly configured!",
                fg=typer.colors.GREEN,
            )

        # Helpful suggestions
        typer.echo(f"\n💡 Helpful Commands:")
        typer.echo(
            f"   agentmap diagnose                    # Check system dependencies"
        )
        typer.echo(
            f"   agentmap inspect-graph {graph_name} --config-details  # Show detailed config"
        )
        if node:
            typer.echo(
                f"   agentmap inspect-graph {graph_name}             # Inspect all nodes"
            )
        else:
            typer.echo(
                f"   agentmap inspect-graph {graph_name} --node NODE_NAME  # Inspect specific node"
            )

    except Exception as e:
        typer.secho(f"❌ Failed to inspect graph: {e}", fg=typer.colors.RED)
        typer.echo("\n💡 Troubleshooting:")
        typer.echo(f"   • Check that graph '{graph_name}' exists in the CSV file")
        typer.echo(f"   • Verify CSV file path: {csv_file or 'default from config'}")
        typer.echo(f"   • Run 'agentmap diagnose' to check system dependencies")
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
