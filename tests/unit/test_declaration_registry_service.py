"""
Unit tests for DeclarationRegistryService.

Tests loading declarations from Python sources and YAML sources,
requirement resolution without loading implementations, and backwards compatibility.
"""

import unittest
from unittest.mock import Mock

from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from agentmap.services.declaration_registry_service import DeclarationRegistryService
from tests.utils.mock_service_factory import MockServiceFactory


class TestDeclarationRegistryService(unittest.TestCase):
    """Test DeclarationRegistryService functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()

        # Create mock services
        self.mock_app_config = self.mock_factory.create_mock_app_config_service()
        self.mock_logging = self.mock_factory.create_mock_logging_service()

        # Configure mock app config to return empty paths by default
        self.mock_app_config.get_declaration_paths.return_value = []
        self.mock_app_config.get_host_declaration_paths.return_value = []
        self.mock_app_config.is_host_declarations_enabled.return_value = False
        self.mock_app_config.get_declaration_validation_settings.return_value = {
            "strict": False,
            "warn_on_missing": True,
            "require_versions": False,
        }

        # Create service under test
        self.registry_service = DeclarationRegistryService(
            self.mock_app_config, self.mock_logging
        )

    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.registry_service)
        self.assertEqual(len(self.registry_service._sources), 0)
        self.assertEqual(len(self.registry_service._agents), 0)
        self.assertEqual(len(self.registry_service._services), 0)

    def test_get_agent_declaration_empty_registry(self):
        """Test getting agent declaration from empty registry."""
        result = self.registry_service.get_agent_declaration("test_agent")
        self.assertIsNone(result)

    def test_get_service_declaration_empty_registry(self):
        """Test getting service declaration from empty registry."""
        result = self.registry_service.get_service_declaration("test_service")
        self.assertIsNone(result)

    def test_resolve_agent_requirements_empty_registry(self):
        """Test resolving requirements from empty registry."""
        result = self.registry_service.resolve_agent_requirements({"test_agent"})

        self.assertIn("services", result)
        self.assertIn("protocols", result)
        self.assertIn("missing", result)
        self.assertEqual(len(result["services"]), 0)
        self.assertEqual(len(result["protocols"]), 0)
        self.assertEqual(result["missing"], {"test_agent"})

    def test_add_source_and_load(self):
        """Test adding a source and loading declarations."""
        # Create mock source
        mock_source = Mock()

        # Create test agent declaration
        test_agent = AgentDeclaration(
            agent_type="test_agent", class_path="test.TestAgent", source="test_source"
        )

        # Create test service declaration
        test_service = ServiceDeclaration(
            service_name="test_service",
            class_path="test.TestService",
            source="test_source",
        )

        # Configure mock source to return test declarations
        mock_source.load_agents.return_value = {"test_agent": test_agent}
        mock_source.load_services.return_value = {"test_service": test_service}

        # Add source and load declarations
        self.registry_service.add_source(mock_source)
        self.registry_service.load_all()

        # Verify declarations were loaded
        loaded_agent = self.registry_service.get_agent_declaration("test_agent")
        self.assertIsNotNone(loaded_agent)
        self.assertEqual(loaded_agent.agent_type, "test_agent")

        loaded_service = self.registry_service.get_service_declaration("test_service")
        self.assertIsNotNone(loaded_service)
        self.assertEqual(loaded_service.service_name, "test_service")

    def test_resolve_agent_requirements_with_declarations(self):
        """Test resolving agent requirements with loaded declarations."""
        # Manually add test declarations to registry
        test_agent = AgentDeclaration(
            agent_type="test_agent", class_path="test.TestAgent", source="test"
        )

        test_service = ServiceDeclaration(
            service_name="logging_service",
            class_path="test.LoggingService",
            source="test",
        )

        # Add declarations directly to registry
        self.registry_service._agents["test_agent"] = test_agent
        self.registry_service._services["logging_service"] = test_service

        # Resolve requirements
        result = self.registry_service.resolve_agent_requirements({"test_agent"})

        self.assertIn("services", result)
        self.assertIn("protocols", result)
        self.assertIn("missing", result)
        self.assertEqual(len(result["missing"]), 0)

    def test_resolve_agent_requirements_with_missing_agents(self):
        """Test resolving requirements when agents are missing."""
        # Add one valid agent
        test_agent = AgentDeclaration(
            agent_type="valid_agent", class_path="test.ValidAgent", source="test"
        )
        self.registry_service._agents["valid_agent"] = test_agent

        # Request both valid and invalid agents
        result = self.registry_service.resolve_agent_requirements(
            {"valid_agent", "missing_agent"}
        )

        self.assertIn("missing", result)
        self.assertIn("missing_agent", result["missing"])
        self.assertNotIn("valid_agent", result["missing"])

    def test_cycle_detection_in_service_dependencies(self):
        """Test detection of circular dependencies in service declarations."""
        # Create services with circular dependencies
        service_a = ServiceDeclaration(
            service_name="service_a",
            class_path="test.ServiceA",
            required_dependencies=["service_b"],
            source="test",
        )

        service_b = ServiceDeclaration(
            service_name="service_b",
            class_path="test.ServiceB",
            required_dependencies=["service_a"],
            source="test",
        )

        # Add to registry
        self.registry_service._services["service_a"] = service_a
        self.registry_service._services["service_b"] = service_b

        # This should not cause infinite recursion
        result = self.registry_service.resolve_agent_requirements(set())

        # Verify that cycle detection worked (no infinite loop)
        self.assertIsInstance(result, dict)
        self.assertIn("services", result)

    def test_source_precedence_later_overrides_earlier(self):
        """Test that later sources override earlier sources."""
        # Create two sources with different declarations for same agent
        source1 = Mock()
        source2 = Mock()

        agent1 = AgentDeclaration(
            agent_type="test_agent", class_path="first.TestAgent", source="source1"
        )

        agent2 = AgentDeclaration(
            agent_type="test_agent", class_path="second.TestAgent", source="source2"
        )

        source1.load_agents.return_value = {"test_agent": agent1}
        source1.load_services.return_value = {}

        source2.load_agents.return_value = {"test_agent": agent2}
        source2.load_services.return_value = {}

        # Add sources in order
        self.registry_service.add_source(source1)
        self.registry_service.add_source(source2)
        self.registry_service.load_all()

        # Verify that second source overrode first
        loaded_agent = self.registry_service.get_agent_declaration("test_agent")
        self.assertEqual(loaded_agent.class_path, "second.TestAgent")
        self.assertEqual(loaded_agent.source, "source2")

    def test_namespace_handling(self):
        """Test that namespace is properly handled in declarations."""
        # Create mock source with namespace
        source = Mock()

        agent = AgentDeclaration(
            agent_type="test_agent",
            class_path="test.TestAgent",
            source="namespace.source",
        )

        source.load_agents.return_value = {"test_agent": agent}
        source.load_services.return_value = {}

        self.registry_service.add_source(source)
        self.registry_service.load_all()

        # Verify namespace is preserved in source tracking
        loaded_agent = self.registry_service.get_agent_declaration("test_agent")
        self.assertEqual(loaded_agent.source, "namespace.source")

    def test_error_handling_in_source_loading(self):
        """Test error handling when source loading fails."""
        # Create source that raises exception
        bad_source = Mock()
        bad_source.load_agents.side_effect = Exception("Loading failed")
        bad_source.load_services.side_effect = Exception("Loading failed")

        # This should not crash the service
        self.registry_service.add_source(bad_source)
        self.registry_service.load_all()

        # Registry should remain empty
        self.assertEqual(len(self.registry_service._agents), 0)
        self.assertEqual(len(self.registry_service._services), 0)

    def test_get_all_agent_types(self):
        """Test getting all available agent types."""
        # Add test agent
        test_agent = AgentDeclaration(
            agent_type="test_agent", class_path="test.TestAgent", source="test"
        )
        self.registry_service._agents["test_agent"] = test_agent

        available_agents = self.registry_service.get_all_agent_types()
        self.assertIn("test_agent", available_agents)
        self.assertEqual(len(available_agents), 1)

    def test_get_all_service_names(self):
        """Test getting all available service names."""
        # Add test service
        test_service = ServiceDeclaration(
            service_name="test_service", class_path="test.TestService", source="test"
        )
        self.registry_service._services["test_service"] = test_service

        available_services = self.registry_service.get_all_service_names()
        self.assertIn("test_service", available_services)
        self.assertEqual(len(available_services), 1)

    def test_load_all_clears_declarations(self):
        """Test that load_all clears existing declarations."""
        # Add test declarations
        test_agent = AgentDeclaration(
            agent_type="test_agent", class_path="test.TestAgent", source="test"
        )
        self.registry_service._agents["test_agent"] = test_agent

        # Call load_all which should clear declarations
        self.registry_service.load_all()

        # Verify registry is empty (no sources added)
        self.assertEqual(len(self.registry_service._agents), 0)
        self.assertEqual(len(self.registry_service._services), 0)

        # Verify get methods return None
        self.assertIsNone(self.registry_service.get_agent_declaration("test_agent"))


if __name__ == "__main__":
    unittest.main()
