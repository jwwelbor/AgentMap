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
    from agentmap.features_registry import features
    from agentmap.agents.dependency_checker import check_llm_dependencies, check_storage_dependencies
    
    typer.echo("AgentMap Dependency Diagnostics")
    typer.echo("=============================")
    
    # Check LLM dependencies
    typer.echo("\nLLM Dependencies:")
    llm_enabled = features.is_feature_enabled("llm")
    typer.echo(f"LLM feature enabled: {llm_enabled}")
    
    for provider in ["openai", "anthropic", "google"]:
        # Always get fresh dependency info
        has_deps, missing = check_llm_dependencies(provider)
        
        # Check registry status for comparison
        registered = features.is_provider_registered("llm", provider)
        validated = features.is_provider_validated("llm", provider)
        available = features.is_provider_available("llm", provider)
        
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
    storage_enabled = features.is_feature_enabled("storage")
    typer.echo(f"Storage feature enabled: {storage_enabled}")
    
    for storage_type in ["csv", "vector", "firebase", "azure_blob", "aws_s3", "gcp_storage"]:
        available = features.is_provider_available("storage", storage_type)
        has_deps, missing = check_storage_dependencies(storage_type)
        
        status = "✅ Available" if available else "❌ Not available"
        if not has_deps and missing:
            status += f" (Missing: {', '.join(missing)})"
        
        typer.echo(f"  {storage_type}: {status}")
    
    # Installation suggestions
    typer.echo("\nInstallation Suggestions:")
    
    # Always check dependencies directly for accurate reporting
    has_llm, missing_llm = check_llm_dependencies()
    has_openai, missing_openai = check_llm_dependencies("openai")
    has_anthropic, missing_anthropic = check_llm_dependencies("anthropic")
    has_google, missing_google = check_llm_dependencies("google")
    
    if not has_llm or not llm_enabled:
        typer.echo("  To enable LLM agents: pip install agentmap[llm]")
    if not storage_enabled:
        typer.echo("  To enable storage agents: pip install agentmap[storage]")
    
    # Provider-specific suggestions
    if not has_openai:
        typer.echo("  For OpenAI support: pip install agentmap[openai] or pip install openai>=1.0.0")
    if not has_anthropic:
        typer.echo("  For Anthropic support: pip install agentmap[anthropic] or pip install anthropic")
    if not has_google:
        typer.echo("  For Google support: pip install agentmap[google] or pip install google-generativeai langchain-google-genai")
    
    # Show path and Python info
    typer.echo("\nEnvironment Information:")
    import sys
    import os
    typer.echo(f"  Python Version: {sys.version}")
    typer.echo(f"  Python Path: {sys.executable}")
    typer.echo(f"  Current Directory: {os.getcwd()}")
    
    # List installed versions of LLM packages
    typer.echo("\nRelevant Package Versions:")
    packages = ["openai", "anthropic", "google.generativeai", "langchain", "langchain_google_genai"]
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
    
    if clear:
        from agentmap.validation import clear_validation_cache
        if file_path:
            removed = clear_validation_cache(file_path)
            typer.secho(f"✅ Cleared {removed} cache entries for {file_path}", fg=typer.colors.GREEN)
        else:
            removed = clear_validation_cache()
            typer.secho(f"✅ Cleared {removed} cache entries", fg=typer.colors.GREEN)
    
    elif cleanup:
        from agentmap.validation import cleanup_validation_cache
        removed = cleanup_validation_cache()
        typer.secho(f"✅ Removed {removed} expired cache entries", fg=typer.colors.GREEN)
    
    elif stats or not (clear or cleanup):
        # Show stats by default if no other action specified
        from agentmap.validation import get_validation_cache_stats
        cache_stats = get_validation_cache_stats()
        
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
