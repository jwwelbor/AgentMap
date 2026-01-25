"""
Unit tests for AgentFactoryService.

These tests validate the AgentFactoryService using the updated API signatures
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from pathlib import Path
from typing import Any, Dict, Type
from unittest.mock import Mock, patch

from agentmap.services.agent.agent_class_resolver import AgentClassResolver
from agentmap.services.agent.agent_factory_service import AgentFactoryService
from tests.utils.migration_utils import MockLoggingService
from tests.utils.mock_service_factory import MockServiceFactory


class TestAgentFactoryService(unittest.TestCase):
    """Unit tests for AgentFactoryService with mocked dependencies."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Mock dependencies that match current constructor
        self.mock_features_registry_service = Mock()
        self.mock_custom_agent_loader = self._create_mock_custom_agent_loader()

        # Use migration-safe mock logging service (established pattern)
        self.mock_logging_service = MockLoggingService()

        # Configure features registry mock defaults
        self._configure_features_registry_defaults()

        # Create service instance with mocked dependencies (updated constructor)
        self.service = AgentFactoryService(
            features_registry_service=self.mock_features_registry_service,
            logging_service=self.mock_logging_service,
            custom_agent_loader=self.mock_custom_agent_loader,
        )

        # Get the mock logger for verification (established pattern)
        self.mock_logger = self.service.logger

    def _create_mock_custom_agent_loader(self):
        """Create a mock CustomAgentLoader service."""
        mock_loader = Mock()

        # Configure default behaviors
        mock_loader.load_agent_class.return_value = None  # No custom agents by default
        mock_loader.get_available_agents.return_value = {}
        mock_loader.validate_agent_class.return_value = True

        return mock_loader

    def _configure_features_registry_defaults(self):
        """Configure default behavior for features registry mock."""
        # Default to storage dependencies available, LLM dependencies not available
        self.mock_features_registry_service.is_provider_available.side_effect = (
            self._default_provider_availability
        )
        self.mock_features_registry_service.get_available_providers.side_effect = (
            self._default_get_available_providers
        )

    def _default_provider_availability(self, category: str, provider: str) -> bool:
        """Default provider availability for tests."""
        if category == "storage":
            return provider in ["csv", "json", "file"]
        elif category == "llm":
            return False  # LLM dependencies not available by default
        return False

    def _default_get_available_providers(self, category: str) -> list:
        """Default available providers for tests."""
        if category == "storage":
            return ["csv", "json", "file"]
        elif category == "llm":
            return []  # No LLM providers available by default
        return []

    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================

    def test_service_initialization_with_all_dependencies(self):
        """Test that service initializes correctly with all required dependencies."""
        self.assertIsNotNone(self.service.features)
        self.assertIsNotNone(self.service.logger)
        self.assertIsNotNone(self.service._custom_agent_loader)
        self.assertIsInstance(self.service.get_class_cache(), dict)

    # =============================================================================
    # 2. resolve_agent_class() Method Tests - Updated for Current API
    # =============================================================================

    @patch.object(AgentClassResolver, "_import_class_from_path")
    def test_resolve_agent_class_success_builtin_agent(self, mock_import):
        """Test successful resolution of builtin agent with valid dependencies."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "DefaultAgent"
        mock_import.return_value = mock_agent_class

        # Create agent mappings as expected by current API
        agent_mappings = {
            "default": "agentmap.agents.builtins.default_agent.DefaultAgent"
        }

        # Act
        result = self.service.resolve_agent_class("default", agent_mappings)

        # Assert
        self.assertEqual(result, mock_agent_class)
        mock_import.assert_called_once_with(
            "agentmap.agents.builtins.default_agent.DefaultAgent"
        )

    def test_resolve_agent_class_failure_agent_not_found(self):
        """Test agent resolution failure when agent type is not in mappings."""
        # Arrange - empty agent mappings
        agent_mappings = {}

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service.resolve_agent_class("nonexistent_agent", agent_mappings)

        error_message = str(context.exception)
        self.assertIn("Agent type 'nonexistent_agent' not found", error_message)

    @patch.object(AgentClassResolver, "_import_class_from_path")
    def test_resolve_agent_class_success_custom_agent(self, mock_import):
        """Test successful resolution of custom agent with mappings."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "CustomAgent"
        mock_import.return_value = mock_agent_class

        # Create agent mappings with custom agent
        agent_mappings = {"custom": "path.to.custom_agent.CustomAgent"}
        custom_agents = {"custom"}

        # Act
        result = self.service.resolve_agent_class(
            "custom", agent_mappings, custom_agents
        )

        # Assert
        self.assertEqual(result, mock_agent_class)
        mock_import.assert_called_once_with("path.to.custom_agent.CustomAgent")

    def test_resolve_agent_class_failure_custom_agent_without_mapping(self):
        """Test custom agent resolution failure when mapping is missing."""
        # Arrange - custom agent declared but no mapping provided
        agent_mappings = {}
        custom_agents = {"custom"}

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service.resolve_agent_class("custom", agent_mappings, custom_agents)

        error_message = str(context.exception)
        self.assertIn(
            "Custom agent 'custom' declared but no class path mapping provided",
            error_message,
        )

    @patch.object(AgentClassResolver, "_import_class_from_path")
    def test_resolve_agent_class_failure_import_error(self, mock_import):
        """Test agent resolution failure when import fails."""
        # Arrange
        mock_import.side_effect = ImportError("Module not found")

        agent_mappings = {"failing": "nonexistent.module.FailingAgent"}

        # Act & Assert
        with self.assertRaises(ImportError) as context:
            self.service.resolve_agent_class("failing", agent_mappings)

        error_message = str(context.exception)
        self.assertIn("Failed to import agent class", error_message)
        self.assertIn("nonexistent.module.FailingAgent", error_message)

    # =============================================================================
    # 3. _import_class_from_path() Method Tests - Now test AgentClassResolver
    # =============================================================================

    def test_import_class_from_path_success_agentmap_package(self):
        """Test successful import of AgentMap package class."""
        # Mock the importlib functions
        with patch("importlib.import_module") as mock_import_module:
            mock_module = Mock()
            mock_agent_class = Mock()
            mock_agent_class.__name__ = "DefaultAgent"
            mock_module.DefaultAgent = mock_agent_class
            mock_import_module.return_value = mock_module

            # Act
            result = self.service._resolver._import_class_from_path(
                "agentmap.agents.builtins.default_agent.DefaultAgent"
            )

            # Assert
            self.assertEqual(result, mock_agent_class)
            mock_import_module.assert_called_once_with(
                "agentmap.agents.builtins.default_agent"
            )

            # Verify caching
            self.assertIn(
                "agentmap.agents.builtins.default_agent.DefaultAgent",
                self.service.get_class_cache(),
            )

    def test_import_class_from_path_tries_custom_loader_for_non_package(self):
        """Test that custom agent loader is tried for non-agentmap paths."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "CustomAgent"
        self.mock_custom_agent_loader.load_agent_class.return_value = mock_agent_class

        # Act
        result = self.service._resolver._import_class_from_path(
            "custom.path.CustomAgent"
        )

        # Assert
        self.assertEqual(result, mock_agent_class)
        self.mock_custom_agent_loader.load_agent_class.assert_called_once_with(
            "custom.path.CustomAgent"
        )

        # Verify caching
        self.assertIn("custom.path.CustomAgent", self.service.get_class_cache())

    def test_import_class_from_path_fallback_to_importlib_when_custom_loader_fails(
        self,
    ):
        """Test fallback to importlib when custom loader fails."""
        # Arrange
        self.mock_custom_agent_loader.load_agent_class.side_effect = Exception(
            "Custom loader failed"
        )

        with patch("importlib.import_module") as mock_import_module:
            mock_module = Mock()
            mock_agent_class = Mock()
            mock_agent_class.__name__ = "CustomAgent"
            mock_module.CustomAgent = mock_agent_class
            mock_import_module.return_value = mock_module

            # Act
            result = self.service._resolver._import_class_from_path(
                "custom.path.CustomAgent"
            )

            # Assert
            self.assertEqual(result, mock_agent_class)
            mock_import_module.assert_called_once_with("custom.path")

    def test_import_class_from_path_failure_invalid_format(self):
        """Test import failure with invalid class path format."""
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service._resolver._import_class_from_path("invalid_format")

        self.assertIn("Invalid class path format", str(context.exception))

    def test_import_class_from_path_uses_cache(self):
        """Test that previously imported classes are returned from cache."""
        # Arrange - populate cache
        mock_agent_class = Mock()
        self.service._resolver._class_cache["cached.class.Agent"] = mock_agent_class

        # Act
        result = self.service._resolver._import_class_from_path("cached.class.Agent")

        # Assert
        self.assertEqual(result, mock_agent_class)
        # Verify no import calls were made
        self.mock_custom_agent_loader.load_agent_class.assert_not_called()

    # =============================================================================
    # 4. get_agent_resolution_context() Method Tests - Updated
    # =============================================================================

    @patch.object(AgentClassResolver, "resolve_agent_class")
    def test_get_agent_resolution_context_success(self, mock_resolve):
        """Test get_agent_resolution_context() returns complete context for valid agent."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "DefaultAgent"
        mock_resolve.return_value = mock_agent_class

        agent_mappings = {
            "default": "agentmap.agents.builtins.default_agent.DefaultAgent"
        }

        # Act
        context = self.service.get_agent_resolution_context("default", agent_mappings)

        # Assert
        expected_keys = {
            "agent_type",
            "agent_class",
            "class_name",
            "resolvable",
            "dependencies_valid",
            "missing_dependencies",
            "_factory_version",
            "_resolution_method",
        }
        self.assertEqual(set(context.keys()), expected_keys)

        self.assertEqual(context["agent_type"], "default")
        self.assertEqual(context["agent_class"], mock_agent_class)
        self.assertEqual(context["class_name"], "DefaultAgent")
        self.assertTrue(context["resolvable"])
        self.assertTrue(context["dependencies_valid"])
        self.assertEqual(context["missing_dependencies"], [])
        self.assertEqual(context["_factory_version"], "2.0")
        self.assertEqual(
            context["_resolution_method"], "AgentClassResolver.resolve_agent_class"
        )

    @patch.object(AgentClassResolver, "resolve_agent_class")
    def test_get_agent_resolution_context_failure(self, mock_resolve):
        """Test get_agent_resolution_context() returns error context for invalid agent."""
        # Arrange
        mock_resolve.side_effect = ValueError("Agent type 'nonexistent' not found")

        agent_mappings = {}

        # Act
        context = self.service.get_agent_resolution_context(
            "nonexistent", agent_mappings
        )

        # Assert
        self.assertEqual(context["agent_type"], "nonexistent")
        self.assertIsNone(context["agent_class"])
        self.assertIsNone(context["class_name"])
        self.assertFalse(context["resolvable"])
        self.assertFalse(context["dependencies_valid"])
        self.assertEqual(context["missing_dependencies"], ["resolution_failed"])
        self.assertIn("resolution_error", context)
        self.assertIn("Agent type 'nonexistent' not found", context["resolution_error"])

    # =============================================================================
    # 5. create_agent_instance() Method Tests - Updated for Current API
    # =============================================================================

    @patch.object(AgentClassResolver, "resolve_agent_class")
    def test_create_agent_instance_with_default_agent(self, mock_resolve):
        """Test create_agent_instance() creates a default agent instance."""
        # Arrange
        mock_node = Mock()
        mock_node.name = "test_node"
        mock_node.agent_type = "default"
        mock_node.prompt = "test prompt"
        mock_node.inputs = ["input1", "input2"]
        mock_node.output = "result"
        mock_node.description = "test description"
        mock_node.context = {}

        # Mock agent class
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "DefaultAgent"
        mock_agent_instance = Mock()
        mock_agent_instance.name = "test_node"
        mock_agent_instance.run = Mock()
        mock_agent_class.return_value = mock_agent_instance
        mock_resolve.return_value = mock_agent_class

        # Agent mappings
        agent_mappings = {
            "default": "agentmap.agents.builtins.default_agent.DefaultAgent"
        }

        # Mock dependencies that would be injected
        mock_execution_tracking = Mock()
        mock_state_adapter = Mock()
        mock_prompt_manager = None

        # Act
        result = self.service.create_agent_instance(
            mock_node,
            "test_graph",
            agent_mappings,
            execution_tracking_service=mock_execution_tracking,
            state_adapter_service=mock_state_adapter,
            prompt_manager_service=mock_prompt_manager,
        )

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "test_node")
        self.assertTrue(hasattr(result, "run"))
        mock_resolve.assert_called_once_with("default", agent_mappings, None)

    def test_create_agent_instance_missing_agent_type(self):
        """Test create_agent_instance() raises error for node without agent_type."""
        # Arrange
        mock_node = Mock()
        mock_node.name = "test_node"
        # Missing agent_type attribute
        del mock_node.agent_type

        agent_mappings = {}

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service.create_agent_instance(mock_node, "test_graph", agent_mappings)

        error_message = str(context.exception)
        self.assertIn(
            "Node 'test_node' is missing required 'agent_type' attribute", error_message
        )

    @patch.object(AgentClassResolver, "resolve_agent_class")
    def test_create_agent_instance_handles_orchestrator_special_case(
        self, mock_resolve
    ):
        """Test create_agent_instance() handles OrchestratorAgent node registry injection."""
        # Arrange
        mock_node = Mock()
        mock_node.name = "orchestrator_node"
        mock_node.agent_type = "orchestrator"
        mock_node.prompt = "orchestrator prompt"
        mock_node.context = {}

        # Mock OrchestratorAgent class
        mock_orchestrator_class = Mock()
        mock_orchestrator_class.__name__ = "OrchestratorAgent"
        mock_orchestrator_instance = Mock()
        mock_orchestrator_instance.name = "orchestrator_node"
        mock_orchestrator_instance.run = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator_instance
        mock_resolve.return_value = mock_orchestrator_class

        # Agent mappings
        agent_mappings = {
            "orchestrator": "agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent"
        }

        # Node registry for injection
        node_registry = {"node1": Mock(), "node2": Mock()}

        # Act
        result = self.service.create_agent_instance(
            mock_node, "test_graph", agent_mappings, node_registry=node_registry
        )

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "orchestrator_node")
        # Verify node registry was injected
        self.assertEqual(result.node_registry, node_registry)

    # =============================================================================
    # 6. validate_agent_instance() Method Tests - Updated
    # =============================================================================

    def test_validate_agent_instance_success_with_valid_agent(self):
        """Test validate_agent_instance() passes for properly configured agent."""
        # Arrange
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        mock_agent.run = Mock()  # Has required run method

        mock_node = Mock()
        mock_node.name = "test_node"

        # Act & Assert - should not raise any exception
        try:
            self.service.validate_agent_instance(mock_agent, mock_node)
        except ValueError:
            self.fail("validate_agent_instance() raised ValueError unexpectedly!")

    def test_validate_agent_instance_fails_missing_name(self):
        """Test validate_agent_instance() fails for agent missing name."""
        # Arrange
        mock_agent = Mock()
        mock_agent.run = Mock()
        # Missing name attribute
        del mock_agent.name

        mock_node = Mock()
        mock_node.name = "test_node"

        # Act & Assert - should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.service.validate_agent_instance(mock_agent, mock_node)

        self.assertIn("missing required 'name' attribute", str(context.exception))

    def test_validate_agent_instance_fails_missing_run_method(self):
        """Test validate_agent_instance() fails for agent missing run method."""
        # Arrange
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        # Missing run method
        del mock_agent.run

        mock_node = Mock()
        mock_node.name = "test_node"

        # Act & Assert - should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.service.validate_agent_instance(mock_agent, mock_node)

        self.assertIn("missing required 'run' method", str(context.exception))

    # =============================================================================
    # 7. Private Helper Method Tests - Now test AgentClassResolver
    # =============================================================================

    @patch.object(AgentClassResolver, "_get_default_agent_class")
    def test_resolve_agent_class_with_fallback_empty_agent_type(self, mock_get_default):
        """Test resolve_agent_class_with_fallback() handles empty agent type."""
        # Arrange
        mock_default_class = Mock()
        mock_default_class.__name__ = "DefaultAgent"
        mock_get_default.return_value = mock_default_class

        # Act
        result = self.service._resolver.resolve_agent_class_with_fallback("")

        # Assert
        self.assertEqual(result, mock_default_class)
        mock_get_default.assert_called_once()

    @patch.object(AgentClassResolver, "_get_default_agent_class")
    def test_resolve_agent_class_with_fallback_none_agent_type(self, mock_get_default):
        """Test resolve_agent_class_with_fallback() handles None agent type."""
        # Arrange
        mock_default_class = Mock()
        mock_default_class.__name__ = "DefaultAgent"
        mock_get_default.return_value = mock_default_class

        # Act
        result = self.service._resolver.resolve_agent_class_with_fallback(None)

        # Assert
        self.assertEqual(result, mock_default_class)
        mock_get_default.assert_called_once()

    def test_get_default_agent_class_success(self):
        """Test _get_default_agent_class() imports DefaultAgent successfully."""
        # Act
        result = self.service._resolver._get_default_agent_class()

        # Assert
        # Should return the actual DefaultAgent class (real implementation working)
        self.assertIsNotNone(result)
        self.assertEqual(result.__name__, "DefaultAgent")
        # Verify it can be instantiated with proper interface
        instance = result(name="test", prompt="test", context={})
        self.assertEqual(instance.name, "test")
        self.assertTrue(hasattr(instance, "run"))

    @patch("importlib.import_module")
    def test_get_default_agent_class_fallback_on_import_error(self, mock_import):
        """Test _get_default_agent_class() creates fallback when import fails."""
        # Arrange
        mock_import.side_effect = ImportError("Module not found")

        # Act
        result = self.service._resolver._get_default_agent_class()

        # Assert
        self.assertIsNotNone(result)
        # Should return a class that can be instantiated
        instance = result(name="test", prompt="test", context={})
        self.assertEqual(instance.name, "test")
        self.assertTrue(hasattr(instance, "run"))

    def test_build_constructor_args_basic(self):
        """Test _build_constructor_args() builds correct arguments."""
        # Arrange
        mock_node = Mock()
        mock_node.name = "test_node"
        mock_node.prompt = "test prompt"

        context = {"key": "value"}

        # Mock agent class with simple constructor
        mock_agent_class = Mock()
        mock_signature = Mock()
        mock_signature.parameters.keys.return_value = [
            "self",
            "name",
            "prompt",
            "context",
            "logger",
        ]

        with patch("inspect.signature", return_value=mock_signature):
            # Act
            result = self.service._build_constructor_args(
                mock_agent_class, mock_node, context, None, None, None
            )

        # Assert
        expected_args = {
            "name": "test_node",
            "prompt": "test prompt",
            "context": context,
            "logger": self.service.logger,
        }
        self.assertEqual(result, expected_args)

    def test_build_constructor_args_with_services(self):
        """Test _build_constructor_args() includes services when agent supports them."""
        # Arrange
        mock_node = Mock()
        mock_node.name = "test_node"
        mock_node.prompt = "test prompt"

        context = {"key": "value"}
        mock_execution_tracking = Mock()
        mock_state_adapter = Mock()
        mock_prompt_manager = Mock()

        # Mock agent class with service parameters
        mock_agent_class = Mock()
        mock_signature = Mock()
        mock_signature.parameters.keys.return_value = [
            "self",
            "name",
            "prompt",
            "context",
            "logger",
            "execution_tracking_service",
            "state_adapter_service",
            "prompt_manager_service",
        ]

        with patch("inspect.signature", return_value=mock_signature):
            # Act
            result = self.service._build_constructor_args(
                mock_agent_class,
                mock_node,
                context,
                mock_execution_tracking,
                mock_state_adapter,
                mock_prompt_manager,
            )

        # Assert
        self.assertIn("execution_tracking_service", result)
        self.assertIn("state_adapter_service", result)
        self.assertIn("prompt_manager_service", result)
        self.assertEqual(result["execution_tracking_service"], mock_execution_tracking)
        self.assertEqual(result["state_adapter_service"], mock_state_adapter)
        self.assertEqual(result["prompt_manager_service"], mock_prompt_manager)

    # =============================================================================
    # 7. Output Validation Config Tests - NEW TESTS FOR TASK T-E08-F01-015
    # =============================================================================

    @patch.object(AgentClassResolver, "resolve_agent_class")
    def test_create_agent_instance_includes_output_validation_config(
        self, mock_resolve
    ):
        """Test create_agent_instance() includes output_validation from AppConfigService."""
        # Arrange
        mock_app_config_service = Mock()
        mock_app_config_service.get_output_validation_config.return_value = {
            "multi_output_mode": "error",
            "require_all_outputs": True,
            "allow_extra_outputs": False,
        }

        # Update service with app_config_service dependency
        self.service.app_config_service = mock_app_config_service

        mock_node = Mock()
        mock_node.name = "test_node"
        mock_node.agent_type = "default"
        mock_node.prompt = "test prompt"
        mock_node.inputs = ["input1"]
        mock_node.output = "result"
        mock_node.description = "test description"
        mock_node.context = {}

        mock_agent_class = Mock()
        mock_agent_class.__name__ = "DefaultAgent"
        mock_agent_instance = Mock()
        mock_agent_instance.name = "test_node"
        mock_agent_class.return_value = mock_agent_instance
        mock_resolve.return_value = mock_agent_class

        agent_mappings = {
            "default": "agentmap.agents.builtins.default_agent.DefaultAgent"
        }

        # Act
        result = self.service.create_agent_instance(
            mock_node, "test_graph", agent_mappings
        )

        # Assert - Verify app_config_service was called
        mock_app_config_service.get_output_validation_config.assert_called_once()

        # Verify result is created
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "test_node")

    @patch.object(AgentClassResolver, "resolve_agent_class")
    def test_create_agent_instance_output_validation_default_warn(self, mock_resolve):
        """Test create_agent_instance() defaults to 'warn' mode when not configured."""
        # Arrange
        mock_app_config_service = Mock()
        # Return defaults with warn mode
        mock_app_config_service.get_output_validation_config.return_value = {
            "multi_output_mode": "warn",
            "require_all_outputs": True,
            "allow_extra_outputs": True,
        }

        self.service.app_config_service = mock_app_config_service

        mock_node = Mock()
        mock_node.name = "test_node"
        mock_node.agent_type = "default"
        mock_node.prompt = "test prompt"
        mock_node.inputs = []
        mock_node.output = "result"
        mock_node.description = ""
        mock_node.context = {}

        mock_agent_class = Mock()
        mock_agent_class.__name__ = "DefaultAgent"
        mock_agent_instance = Mock()
        mock_agent_instance.name = "test_node"
        mock_agent_class.return_value = mock_agent_instance
        mock_resolve.return_value = mock_agent_class

        agent_mappings = {
            "default": "agentmap.agents.builtins.default_agent.DefaultAgent"
        }

        # Act
        result = self.service.create_agent_instance(
            mock_node, "test_graph", agent_mappings
        )

        # Assert
        self.assertIsNotNone(result)
        mock_app_config_service.get_output_validation_config.assert_called_once()


if __name__ == "__main__":
    unittest.main()
