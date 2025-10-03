"""System-level operations: cache, config, diagnostics."""

from typing import Any, Dict, Optional


def refresh_cache(
    *,
    force: bool = False,
    llm_only: bool = False,
    storage_only: bool = False,
    config_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Refresh availability cache by discovering and validating all providers.

    Args:
        force: Force refresh even if cache exists.
        llm_only: Only refresh LLM providers.
        storage_only: Only refresh storage providers.
        config_file: Optional configuration file path.

    Returns:
        Dict containing refresh results and provider availability.

    Raises:
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    from .init_ops import ensure_initialized
    from .runtime_manager import RuntimeManager

    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()
        dependency_checker = container.dependency_checker_service()

        # Invalidate the cache
        dependency_checker.invalidate_environment_cache()

        llm_results = {}
        storage_results = {}

        # Discover and validate LLM providers
        if not storage_only:
            llm_results = dependency_checker.discover_and_validate_providers(
                "llm", True
            )

        # Discover and validate storage providers
        if not llm_only:
            storage_results = dependency_checker.discover_and_validate_providers(
                "storage", True
            )

        # Get summary
        status_summary = dependency_checker.get_dependency_status_summary()

        return {
            "success": True,
            "outputs": {
                "cache_invalidated": True,
                "llm_results": llm_results,
                "storage_results": storage_results,
                "status_summary": status_summary,
            },
            "metadata": {
                "force": force,
                "llm_only": llm_only,
                "storage_only": storage_only,
            },
        }

    except Exception as e:
        raise RuntimeError(f"Failed to refresh cache: {e}")


def validate_cache(
    *,
    clear: bool = False,
    cleanup: bool = False,
    stats: bool = False,
    file_path: Optional[str] = None,
    config_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Manage validation result cache.

    Args:
        clear: Clear all validation cache.
        cleanup: Remove expired cache entries.
        stats: Show cache statistics.
        file_path: Clear cache for specific file only.
        config_file: Optional configuration file path.

    Returns:
        Dict containing cache management results.

    Raises:
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    from .init_ops import ensure_initialized
    from .runtime_manager import RuntimeManager

    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()
        validation_cache_service = container.validation_cache_service()

        results = {}

        if clear:
            if file_path:
                removed = validation_cache_service.clear_validation_cache(file_path)
                results["action"] = "clear_file"
                results["removed_entries"] = removed
                results["file_path"] = file_path
            else:
                removed = validation_cache_service.clear_validation_cache()
                results["action"] = "clear_all"
                results["removed_entries"] = removed

        elif cleanup:
            removed = validation_cache_service.cleanup_validation_cache()
            results["action"] = "cleanup"
            results["removed_entries"] = removed

        else:
            # Show stats by default
            cache_stats = validation_cache_service.get_validation_cache_stats()
            results["action"] = "stats"
            results["cache_stats"] = cache_stats

        return {
            "success": True,
            "outputs": results,
            "metadata": {
                "clear": clear,
                "cleanup": cleanup,
                "stats": stats,
                "file_path": file_path,
            },
        }

    except Exception as e:
        raise RuntimeError(f"Failed to manage validation cache: {e}")


def get_config(*, config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get current configuration values.

    Args:
        config_file: Optional configuration file path.

    Returns:
        Dict containing current configuration values.

    Raises:
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    from .init_ops import ensure_initialized
    from .runtime_manager import RuntimeManager

    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()
        app_config_service = container.app_config_service()

        config_data = app_config_service.get_all()

        return {
            "success": True,
            "outputs": config_data,
            "metadata": {
                "config_file": config_file,
            },
        }

    except Exception as e:
        raise RuntimeError(f"Failed to get configuration: {e}")


def diagnose_system(*, config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Diagnose system health and dependency status.

    Args:
        config_file: Optional configuration file path.

    Returns:
        Dict containing diagnostic information including:
            - Feature status (LLM, storage)
            - Provider availability
            - Dependency status
            - Installation suggestions
            - Environment information

    Raises:
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    from .init_ops import ensure_initialized
    from .runtime_manager import RuntimeManager

    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()
        features_service = container.features_registry_service()
        dependency_checker = container.dependency_checker_service()

        # Run discovery first to match runtime behavior
        # This will auto-enable features if dependencies are found
        llm_providers = dependency_checker.discover_and_validate_providers(
            "llm", force=True
        )
        storage_providers = dependency_checker.discover_and_validate_providers(
            "storage", force=True
        )

        # Get feature states after discovery
        llm_enabled = features_service.is_feature_enabled("llm")
        storage_enabled = features_service.is_feature_enabled("storage")

        # Build LLM provider details
        llm_details = {}
        for provider in ["openai", "anthropic", "google"]:
            is_available = llm_providers.get(provider, False)
            has_deps, missing = dependency_checker.check_llm_dependencies(provider)

            if is_available:
                status = "available"
            elif has_deps:
                status = "deps_found_validation_failed"
            else:
                status = "missing_dependencies"

            llm_details[provider] = {
                "status": status,
                "available": is_available,
                "has_dependencies": has_deps,
                "missing_dependencies": missing,
            }

        # Build storage provider details
        storage_details = {}
        for storage_type in ["csv", "json", "file", "vector", "firebase", "blob"]:
            is_available = storage_providers.get(storage_type, False)

            # Built-in types don't require external deps
            if storage_type in ["json", "file"]:
                status = "builtin"
                has_deps = True
                missing = []
            else:
                has_deps, missing = dependency_checker.check_storage_dependencies(
                    storage_type
                )
                if is_available:
                    status = "available"
                elif has_deps:
                    status = "deps_found_validation_failed"
                else:
                    status = "missing_dependencies"

            storage_details[storage_type] = {
                "status": status,
                "available": is_available,
                "has_dependencies": has_deps,
                "missing_dependencies": missing,
            }

        # Generate installation suggestions
        suggestions = []
        if not llm_enabled or not any(llm_providers.values()):
            suggestions.append("To enable LLM agents: pip install agentmap[llm]")

        for provider in ["openai", "anthropic", "google"]:
            if not llm_providers.get(provider, False):
                if provider == "openai":
                    suggestions.append(
                        "For OpenAI: pip install openai>=1.0.0 langchain-openai"
                    )
                elif provider == "anthropic":
                    suggestions.append(
                        "For Anthropic: pip install anthropic langchain-anthropic"
                    )
                elif provider == "google":
                    suggestions.append(
                        "For Google: pip install google-generativeai langchain-google-genai"
                    )

        if not storage_enabled:
            suggestions.append(
                "To enable storage agents: pip install agentmap[storage]"
            )

        if not storage_providers.get("vector", False):
            suggestions.append("For vector storage: pip install chromadb")

        # Get environment information
        import os
        import sys

        # Check package versions
        package_versions = {}
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
                    package_versions[display_name] = "installed"
                else:
                    module = __import__(package)
                    version = getattr(module, "__version__", "unknown")
                    package_versions[display_name] = f"v{version}"
            except ImportError:
                package_versions[display_name] = "not_installed"

        # Calculate overall readiness
        llm_ready = llm_enabled and any(llm_providers.values())
        storage_ready = storage_enabled and any(storage_providers.values())

        if llm_ready and storage_ready:
            overall_status = "fully_operational"
        elif llm_ready:
            overall_status = "llm_only"
        elif storage_ready:
            overall_status = "storage_only"
        else:
            overall_status = "limited_functionality"

        return {
            "success": True,
            "outputs": {
                "overall_status": overall_status,
                "features": {
                    "llm": {
                        "enabled": llm_enabled,
                        "available_providers": [
                            p for p, avail in llm_providers.items() if avail
                        ],
                        "provider_details": llm_details,
                    },
                    "storage": {
                        "enabled": storage_enabled,
                        "available_types": [
                            t for t, avail in storage_providers.items() if avail
                        ],
                        "storage_details": storage_details,
                    },
                },
                "suggestions": suggestions,
                "environment": {
                    "python_version": sys.version,
                    "python_path": sys.executable,
                    "current_directory": os.getcwd(),
                    "package_versions": package_versions,
                },
            },
            "metadata": {
                "llm_ready": llm_ready,
                "storage_ready": storage_ready,
            },
        }

    except Exception as e:
        raise RuntimeError(f"System diagnosis failed: {e}")


def get_version(*, config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get AgentMap version information.

    Args:
        config_file: Optional configuration file path.

    Returns:
        Dict containing version information.

    Raises:
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    from .init_ops import ensure_initialized

    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        from agentmap._version import __version__

        return {
            "success": True,
            "outputs": {"agentmap_version": __version__, "api_version": "2.0"},
            "metadata": {"config_file": config_file},
        }
    except ImportError:
        return {
            "success": True,
            "outputs": {"agentmap_version": "unknown", "api_version": "2.0"},
            "metadata": {"config_file": config_file},
        }


def get_health(*, config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get basic health status of the AgentMap runtime.

    Args:
        config_file: Optional configuration file path.

    Returns:
        Dict containing health status.

    Note: This always returns success=True if it can execute,
    with status indicating the actual health state.
    """
    from .init_ops import ensure_initialized
    from .runtime_manager import RuntimeManager

    try:
        # Try to ensure initialized
        ensure_initialized(config_file=config_file)

        # Try to get container to verify it's working
        container = RuntimeManager.get_container()

        # Check a basic service
        try:
            app_config_service = container.app_config_service()
            _ = app_config_service.get_all()
            status = "healthy"
        except Exception:
            status = "degraded"

        return {
            "success": True,
            "outputs": {"status": status, "initialized": True},
            "metadata": {"config_file": config_file},
        }
    except Exception as e:
        # Runtime not initialized or other error
        return {
            "success": True,
            "outputs": {
                "status": "not_initialized",
                "initialized": False,
                "error": str(e),
            },
            "metadata": {"config_file": config_file},
        }


def get_system_paths(*, config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get system directory paths used by AgentMap.

    Args:
        config_file: Optional configuration file path.

    Returns:
        Dict containing system paths.

    Raises:
        AgentMapNotInitialized: if runtime has not been initialized.
    """
    from .init_ops import ensure_initialized
    from .runtime_manager import RuntimeManager

    # Ensure runtime is initialized
    ensure_initialized(config_file=config_file)

    try:
        # Get container and services through RuntimeManager delegation
        container = RuntimeManager.get_container()
        app_config_service = container.app_config_service()

        # Get paths from configuration
        csv_path = app_config_service.get_csv_repository_path()
        custom_agents_path = app_config_service.get_custom_agents_path()
        functions_path = app_config_service.get_functions_path()

        return {
            "success": True,
            "outputs": {
                "csv_repository": str(csv_path),
                "custom_agents": str(custom_agents_path),
                "functions": str(functions_path),
            },
            "metadata": {"config_file": config_file},
        }
    except Exception as e:
        raise RuntimeError(f"Failed to get system paths: {e}")
