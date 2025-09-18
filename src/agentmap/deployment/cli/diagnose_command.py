"""
CLI diagnose command handler for system health and dependency checking.

This command follows SPEC-DEP-001 by using only the runtime facade
and CLI presenter utilities for consistent behavior and error handling.
"""

from typing import Optional

import typer

from agentmap.deployment.cli.utils.cli_presenter import (
    map_exception_to_exit_code,
    print_err,
    print_json,
)
from agentmap.runtime_api import diagnose_system, ensure_initialized


def diagnose_cmd(
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to custom config file"
    )
):
    """
    Check and display dependency status for all components.

    This command follows the facade pattern defined in SPEC-DEP-001 for
    consistent behavior across all deployment adapters.
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized(config_file=config_file)

        typer.echo("AgentMap Dependency Diagnostics")
        typer.echo("=============================")

        # Execute diagnosis using runtime facade
        typer.echo("\nDiscovering available providers...")

        result = diagnose_system(config_file=config_file)

        # Display results using CLI presenter for consistency
        if result.get("success", False):
            outputs = result.get("outputs", {})
            metadata = result.get("metadata", {})

            typer.echo("\n✅ Discovery complete. Showing actual runtime state:\n")

            # Display LLM information
            features = outputs.get("features", {})
            llm_info = features.get("llm", {})
            storage_info = features.get("storage", {})

            typer.echo("LLM Dependencies:")
            llm_enabled = llm_info.get("enabled", False)
            available_providers = llm_info.get("available_providers", [])
            typer.echo(
                f"  Feature Status: {'✅ Enabled' if llm_enabled else '❌ Disabled'}"
            )
            typer.echo(f"  Available Providers: {available_providers or 'None'}")

            typer.echo("\n  Provider Details:")
            provider_details = llm_info.get("provider_details", {})
            for provider, details in provider_details.items():
                status = details.get("status", "unknown")
                missing_deps = details.get("missing_dependencies", [])

                if status == "available":
                    status_msg = "✅ Available and validated"
                elif status == "deps_found_validation_failed":
                    status_msg = "⚠️ Dependencies found but validation failed"
                else:
                    missing_str = (
                        ", ".join(missing_deps) if missing_deps else "Not configured"
                    )
                    status_msg = f"❌ Missing dependencies: {missing_str}"

                typer.echo(f"    {provider.capitalize()}: {status_msg}")

            # Display Storage information
            typer.echo("\nStorage Dependencies:")
            storage_enabled = storage_info.get("enabled", False)
            available_types = storage_info.get("available_types", [])
            typer.echo(
                f"  Feature Status: {'✅ Enabled' if storage_enabled else '❌ Disabled'}"
            )
            typer.echo(f"  Available Types: {available_types or 'None'}")

            typer.echo("\n  Storage Type Details:")
            storage_details = storage_info.get("storage_details", {})
            for storage_type, details in storage_details.items():
                status = details.get("status", "unknown")
                missing_deps = details.get("missing_dependencies", [])

                if status == "builtin":
                    status_msg = "✅ Built-in (always available)"
                elif status == "available":
                    status_msg = "✅ Available and validated"
                elif status == "deps_found_validation_failed":
                    status_msg = "⚠️ Dependencies found but validation failed"
                else:
                    missing_str = (
                        ", ".join(missing_deps) if missing_deps else "Not configured"
                    )
                    status_msg = f"❌ Missing dependencies: {missing_str}"

                typer.echo(f"    {storage_type}: {status_msg}")

            # Display installation suggestions
            suggestions = outputs.get("suggestions", [])
            if suggestions:
                typer.echo("\nInstallation Suggestions:")
                for suggestion in suggestions:
                    typer.echo(f"  • {suggestion}")

            # Display environment information
            env_info = outputs.get("environment", {})
            typer.echo("\nEnvironment Information:")
            typer.echo(f"  Python Version: {env_info.get('python_version', 'Unknown')}")
            typer.echo(f"  Python Path: {env_info.get('python_path', 'Unknown')}")
            typer.echo(
                f"  Current Directory: {env_info.get('current_directory', 'Unknown')}"
            )

            # Display package versions
            package_versions = env_info.get("package_versions", {})
            if package_versions:
                typer.echo("\nInstalled Package Versions:")
                for package_name, version_info in package_versions.items():
                    if version_info == "not_installed":
                        typer.echo(f"  {package_name}: ❌ Not installed")
                    elif version_info == "installed":
                        typer.echo(f"  {package_name}: ✅ Installed")
                    else:
                        typer.echo(f"  {package_name}: ✅ {version_info}")

            # Display summary
            typer.echo("\n" + "=" * 50)
            typer.echo("Summary:")

            overall_status = outputs.get("overall_status", "unknown")
            llm_ready = metadata.get("llm_ready", False)
            storage_ready = metadata.get("storage_ready", False)

            if overall_status == "fully_operational":
                typer.echo(
                    "✅ AgentMap is fully operational with LLM and storage support!"
                )
            elif overall_status == "llm_only":
                typer.echo(
                    "⚠️ AgentMap has LLM support but limited storage capabilities."
                )
            elif overall_status == "storage_only":
                typer.echo("⚠️ AgentMap has storage support but no LLM capabilities.")
            else:
                typer.echo(
                    "❌ AgentMap has limited functionality. Install dependencies above."
                )

        else:
            # This shouldn't happen with the facade pattern, but handle gracefully
            error_msg = result.get("error", "Unknown error")
            print_err(f"System diagnosis failed: {error_msg}")
            raise typer.Exit(code=1)

    except Exception as e:
        # Use CLI presenter for consistent error handling and exit codes
        print_err(str(e))
        exit_code = map_exception_to_exit_code(e)
        raise typer.Exit(code=exit_code)
