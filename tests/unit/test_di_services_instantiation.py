import pytest

from agentmap.di.containers import ApplicationContainer

# List of provider attribute names to attempt instantiation for.
# Optional services may naturally return None (that's okay).
SERVICE_NAMES = [
    # core_di
    "config_service",
    "app_config_service",
    "logging_service",
    "availability_cache_service",
    "file_path_service",
    "prompt_manager_service",
    "auth_service",
    # storage_di
    "storage_config_service",
    "blob_storage_service",
    "json_storage_service",
    "storage_service_manager",
    "system_storage_manager",
    # bootstrap_di
    "features_registry_model",
    "agent_registry_model",
    "validation_cache_service",
    "csv_graph_parser_service",
    "function_resolution_service",
    "declaration_parser",
    "declaration_registry_service",
    "features_registry_service",
    "agent_registry_service",
    "config_validation_service",
    "csv_validation_service",
    "validation_service",
    "indented_template_composer",
    "custom_agent_declaration_manager",
    "custom_agent_loader",
    "static_bundle_analyzer",
    "dependency_checker_service",
    # llm_di
    "llm_routing_config_service",
    "prompt_complexity_analyzer",
    "routing_cache",
    "llm_routing_service",
    "llm_service",
    # host_registry
    "host_service_registry",
    "host_protocol_configuration_service",
    # graph_agent_di
    "orchestrator_service",
    "agent_factory_service",
    "agent_service_injection_service",
    "graph_agent_instantiation_service",
    # graph_core_di
    "execution_formatter_service",
    "state_adapter_service",
    "execution_tracking_service",
    "execution_policy_service",
    "graph_factory_service",
    "graph_assembly_service",
    "protocol_requirements_analyzer",
    "graph_registry_service",
    "graph_bundle_service",
    "bundle_update_service",
    "graph_scaffold_service",
    "graph_execution_service",
    "graph_checkpoint_service",
    "interaction_handler_service",
    "graph_bootstrap_service",
    "graph_runner_service",
]


@pytest.fixture(scope="module")
def container():
    c = ApplicationContainer()
    # Use default config; if your project needs a path, set it here:
    # c.config.path.from_value("/path/to/agentmap_config.yaml")
    return c


@pytest.mark.parametrize("service_name", SERVICE_NAMES)
def test_service_provider_instantiates(container, service_name):
    # Ensure provider exists
    assert hasattr(
        container, service_name
    ), f"Provider '{service_name}' is missing on the container"

    provider = getattr(container, service_name)
    # Provider itself should be callable (providers.Singleton/Factory/etc.)
    assert callable(
        provider
    ), f"Provider '{service_name}' is not callable (got: {type(provider)})"

    # Attempt to build the instance. Some optional services may return None by design.
    try:
        _instance = provider()
    except ImportError as e:
        # If your environment lacks certain optional integrations, you can xfail instead of failing hard.
        pytest.xfail(f"ImportError while instantiating '{service_name}': {e}")
    except Exception as e:
        pytest.fail(f"Failed to instantiate provider '{service_name}': {e}")
