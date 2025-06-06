"""
CLI diagnostic and information command handlers.

This module provides diagnostic commands for system health, dependency checking,
and information display using the new service architecture.
"""

from typing import Optional

import typer

from agentmap.di import initialize_di


def diagnose_cmd(
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to custom config file")
):
    """Check and display dependency status for all components."""
    container = initialize_di(config_file)
    features_service = container.features_registry_service()
    dependency_checker = container.dependency_checker_service()
    logging_service = container.logging_service()

    logger = logging_service.get_logger("agentmap.cli.diagnostic")

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
            status = "⚠️ INCONSISTENT: Provider marked available but dependencies missing"
        
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
            status = "⚠️ INCONSISTENT: Provider marked available but dependencies missing"
        
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
        typer.echo("  For OpenAI support: pip install agentmap[openai] or pip install openai>=1.0.0")
    
    has_anthropic, _ = dependency_checker.check_llm_dependencies("anthropic")
    if not has_anthropic:
        typer.echo("  For Anthropic support: pip install agentmap[anthropic] or pip install anthropic")
    
    has_google, _ = dependency_checker.check_llm_dependencies("google")
    if not has_google:
        typer.echo("  For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai")
    
    has_vector, _ = dependency_checker.check_storage_dependencies("vector")
    if not has_vector:
        typer.echo("  For vector storage: pip install chromadb")
    
    # Show path and Python info
    typer.echo("\nEnvironment Information:")
    import sys
    import os
    typer.echo(f"  Python Version: {sys.version}")
    typer.echo(f"  Python Path: {sys.executable}")
    typer.echo(f"  Current Directory: {os.getcwd()}")
    
    # List installed versions of LLM packages
    typer.echo("\nRelevant Package Versions:")
    packages = ["openai", "anthropic", "google.generativeai", "langchain", "langchain_google_genai", "chromadb"]
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
    config_file: Optional[str] = typer.Option(None, "--path", "-p", help="Path to config file to display")
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
    cleanup: bool = typer.Option(False, "--cleanup", help="Remove expired cache entries"),
    stats: bool = typer.Option(False, "--stats", help="Show cache statistics"),
    file_path: Optional[str] = typer.Option(None, "--file", help="Clear cache for specific file only")
):
    """Manage validation result cache."""
    container = initialize_di()
    validation_cache_service = container.validation_cache_service()

    if clear:
        if file_path:
            removed = validation_cache_service.clear_validation_cache(file_path)
            typer.secho(f"✅ Cleared {removed} cache entries for {file_path}", fg=typer.colors.GREEN)
        else:
            removed = validation_cache_service.clear_validation_cache()
            typer.secho(f"✅ Cleared {removed} cache entries", fg=typer.colors.GREEN)
    
    elif cleanup:
        removed = validation_cache_service.cleanup_validation_cache()
        typer.secho(f"✅ Removed {removed} expired cache entries", fg=typer.colors.GREEN)
    
    elif stats or not (clear or cleanup):
        # Show stats by default if no other action specified
        cache_stats = validation_cache_service.get_validation_cache_stats()
        
        typer.echo("Validation Cache Statistics:")
        typer.echo("=" * 30)
        typer.echo(f"Total files: {cache_stats['total_files']}")
        typer.echo(f"Valid files: {cache_stats['valid_files']}")
        typer.echo(f"Expired files: {cache_stats['expired_files']}")
        typer.echo(f"Corrupted files: {cache_stats['corrupted_files']}")
        
        if cache_stats['expired_files'] > 0:
            typer.echo(f"\n💡 Run 'agentmap validate-cache --cleanup' to remove expired entries")
        
        if cache_stats['corrupted_files'] > 0:
            typer.echo(f"⚠️  Found {cache_stats['corrupted_files']} corrupted cache files")


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
            "missing_dependencies": missing
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
            "missing_dependencies": missing
        }
    
    # Build environment information
    import sys
    import os
    environment = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "current_directory": os.getcwd(),
        "platform": sys.platform
    }
    
    # Get package versions
    packages = ["openai", "anthropic", "google.generativeai", "langchain", "langchain_google_genai", "chromadb"]
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
        installation_suggestions.append("To enable LLM agents: pip install agentmap[llm]")
    
    # Check if storage feature is enabled
    if not features_service.is_feature_enabled("storage"):
        installation_suggestions.append("To enable storage agents: pip install agentmap[storage]")
    
    # Provider-specific suggestions
    if not dependency_checker.check_llm_dependencies("openai")[0]:
        installation_suggestions.append("For OpenAI support: pip install agentmap[openai] or pip install openai>=1.0.0")
    
    if not dependency_checker.check_llm_dependencies("anthropic")[0]:
        installation_suggestions.append("For Anthropic support: pip install agentmap[anthropic] or pip install anthropic")
    
    if not dependency_checker.check_llm_dependencies("google")[0]:
        installation_suggestions.append("For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai")
    
    if not dependency_checker.check_storage_dependencies("vector")[0]:
        installation_suggestions.append("For vector storage: pip install chromadb")
    
    return {
        "llm": llm_info,
        "storage": storage_info,
        "environment": environment,
        "package_versions": package_versions,
        "installation_suggestions": installation_suggestions
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
    if cache_stats['expired_files'] > 0:
        suggestions.append("Run 'agentmap validate-cache --cleanup' to remove expired entries")
    if cache_stats['corrupted_files'] > 0:
        suggestions.append(f"Found {cache_stats['corrupted_files']} corrupted cache files")
    
    return {
        "cache_statistics": cache_stats,
        "suggestions": suggestions
    }


def clear_cache_command(file_path: Optional[str] = None, cleanup_expired: bool = False) -> dict:
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
        "file_path": file_path
    }
