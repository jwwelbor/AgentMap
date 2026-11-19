"""Tests for metadata extraction from declaration registry contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

from agentmap.services.graph.graph_bundle_service import GraphBundleService
from tests.utils.mock_service_factory import MockServiceFactory


def _service():
    registry = Mock()
    custom_manager = Mock()
    analyzer = Mock(custom_agent_declaration_manager=custom_manager)
    service = GraphBundleService(
        logging_service=MockServiceFactory.create_mock_logging_service(),
        protocol_requirements_analyzer=Mock(),
        agent_factory_service=Mock(),
        json_storage_service=Mock(),
        csv_parser_service=Mock(),
        static_bundle_analyzer=analyzer,
        app_config_service=Mock(),
        declaration_registry_service=registry,
        graph_registry_service=Mock(),
        file_path_service=Mock(),
        system_storage_manager=Mock(),
    )
    return service, registry, custom_manager


def test_extract_agent_mappings_uses_registered_declarations():
    service, registry, custom_manager = _service()
    registry.get_agent_declaration.side_effect = lambda name: (
        SimpleNamespace(class_path="agents.echo.EchoAgent") if name == "echo" else None
    )
    custom_manager.get_agent_declaration.return_value = {
        "class_path": "custom_agents.review.ReviewAgent"
    }

    mappings = service._extract_agent_mappings({"echo", "review"})

    assert mappings == {
        "echo": "agents.echo.EchoAgent",
        "review": "custom_agents.review.ReviewAgent",
    }


def test_classify_agents_uses_injected_declaration_registry():
    service, registry, _ = _service()
    registry.get_all_agent_types.return_value = ["echo", "llm"]

    builtin, custom = service._classify_agents({"echo", "review"})

    assert builtin == {"echo"}
    assert custom == {"review"}


def test_extract_protocol_mappings_uses_registry_service_map():
    service, registry, _ = _service()
    registry.get_protocol_service_map.return_value = {
        "StorageService": "json_storage_service"
    }

    assert service._extract_protocol_mappings() == {
        "StorageService": "json_storage_service"
    }
