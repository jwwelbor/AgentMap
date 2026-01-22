"""
Unit tests for AgentRegistryService.

These tests validate the AgentRegistryService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from typing import Any, Dict, Type
from unittest.mock import Mock

from agentmap.models.agent_registry import AgentRegistry
from agentmap.services.agent.agent_registry_service import AgentRegistryService
from tests.utils.migration_utils import MockLoggingService


class TestAgentRegistryService(unittest.TestCase):
    """Unit tests for AgentRegistryService with mocked dependencies."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create real AgentRegistry model (pure data container)
        self.agent_registry_model = AgentRegistry()

        # Use migration-safe mock logging service (established pattern)
        self.mock_logging_service = MockLoggingService()

        # Create service instance with real model and mocked logging
        self.service = AgentRegistryService(
            agent_registry=self.agent_registry_model,
            logging_service=self.mock_logging_service,
        )

        # Get the mock logger for verification (established pattern)
        self.mock_logger = self.service.logger

        # Create mock agent classes for testing
        self.mock_default_agent = Mock()
        self.mock_default_agent.__name__ = "DefaultAgent"

        self.mock_custom_agent = Mock()
        self.mock_custom_agent.__name__ = "CustomAgent"

        self.mock_llm_agent = Mock()
        self.mock_llm_agent.__name__ = "OpenAIAgent"

    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================

    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored (match actual implementation)
        self.assertEqual(self.service.agent_registry, self.agent_registry_model)

        # Verify logger is configured (established pattern)
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, "AgentRegistryService")

        # Verify initialization log message (established pattern)
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                call[1] == "[AgentRegistryService] Initialized"
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    # =============================================================================
    # 2. register_agent() Method Tests
    # =============================================================================

    def test_register_agent_adds_to_registry(self):
        """Test that register_agent() adds agent to the registry."""
        # Act
        self.service.register_agent("custom", self.mock_custom_agent)

        # Assert
        self.assertTrue(self.agent_registry_model.has_agent("custom"))
        retrieved_agent = self.agent_registry_model.get_agent_class("custom")
        self.assertEqual(retrieved_agent, self.mock_custom_agent)

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Registered agent 'custom': CustomAgent" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_register_agent_default_agent(self):
        """Test that registering 'default' agent sets default_agent_class."""
        # Act
        self.service.register_agent("default", self.mock_default_agent)

        # Assert
        self.assertTrue(self.agent_registry_model.has_agent("default"))
        self.assertEqual(
            self.agent_registry_model.default_agent_class, self.mock_default_agent
        )

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Registered default agent: DefaultAgent" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_register_agent_overwrites_existing(self):
        """Test that register_agent() overwrites existing agent registration."""
        # Arrange - Register initial agent
        initial_agent = Mock()
        initial_agent.__name__ = "InitialAgent"
        self.service.register_agent("test_type", initial_agent)

        # Act - Register new agent with same type
        self.service.register_agent("test_type", self.mock_custom_agent)

        # Assert - Should have new agent
        retrieved_agent = self.agent_registry_model.get_agent_class("test_type")
        self.assertEqual(retrieved_agent, self.mock_custom_agent)
        self.assertNotEqual(retrieved_agent, initial_agent)

    def test_register_agent_case_normalization(self):
        """Test that register_agent() normalizes agent type to lowercase."""
        # Act
        self.service.register_agent("CUSTOM_TYPE", self.mock_custom_agent)

        # Assert - Should be stored as lowercase
        self.assertTrue(self.agent_registry_model.has_agent("custom_type"))
        self.assertTrue(
            self.agent_registry_model.has_agent("CUSTOM_TYPE")
        )  # Should find it
        retrieved_agent = self.agent_registry_model.get_agent_class("custom_type")
        self.assertEqual(retrieved_agent, self.mock_custom_agent)

    # =============================================================================
    # 3. unregister_agent() Method Tests
    # =============================================================================

    def test_unregister_agent_removes_from_registry(self):
        """Test that unregister_agent() removes agent from registry."""
        # Arrange
        self.service.register_agent("test_agent", self.mock_custom_agent)
        self.assertTrue(self.agent_registry_model.has_agent("test_agent"))

        # Act
        self.service.unregister_agent("test_agent")

        # Assert
        self.assertFalse(self.agent_registry_model.has_agent("test_agent"))

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Unregistered agent: test_agent" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_unregister_agent_default_clears_default_class(self):
        """Test that unregistering 'default' agent clears default_agent_class."""
        # Arrange
        self.service.register_agent("default", self.mock_default_agent)
        self.assertEqual(
            self.agent_registry_model.default_agent_class, self.mock_default_agent
        )

        # Act
        self.service.unregister_agent("default")

        # Assert
        self.assertFalse(self.agent_registry_model.has_agent("default"))
        self.assertIsNone(self.agent_registry_model.default_agent_class)

    def test_unregister_agent_nonexistent_logs_warning(self):
        """Test that unregistering non-existent agent logs warning."""
        # Act
        self.service.unregister_agent("nonexistent_agent")

        # Assert - Should not crash
        self.assertFalse(self.agent_registry_model.has_agent("nonexistent_agent"))

        # Verify warning logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Attempted to unregister unknown agent: nonexistent_agent" in call[1]
                for call in logger_calls
                if call[0] == "warning"
            )
        )

    def test_unregister_agent_case_insensitive(self):
        """Test that unregister_agent() works with different cases."""
        # Arrange
        self.service.register_agent("test_agent", self.mock_custom_agent)

        # Act - Unregister with different case
        self.service.unregister_agent("TEST_AGENT")

        # Assert
        self.assertFalse(self.agent_registry_model.has_agent("test_agent"))

    # =============================================================================
    # 4. get_agent_class() Method Tests
    # =============================================================================

    def test_get_agent_class_returns_registered_agent(self):
        """Test that get_agent_class() returns registered agent."""
        # Arrange
        self.service.register_agent("test_agent", self.mock_custom_agent)

        # Act
        result = self.service.get_agent_class("test_agent")

        # Assert
        self.assertEqual(result, self.mock_custom_agent)

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Retrieved agent 'test_agent': CustomAgent" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_get_agent_class_returns_default_for_empty_type(self):
        """Test that get_agent_class() returns default agent for empty type."""
        # Arrange
        self.service.register_agent("default", self.mock_default_agent)

        # Act
        result_empty = self.service.get_agent_class("")
        result_none = self.service.get_agent_class(None)

        # Assert
        self.assertEqual(result_empty, self.mock_default_agent)
        self.assertEqual(result_none, self.mock_default_agent)

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Retrieved default agent: DefaultAgent" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_get_agent_class_returns_provided_default_when_not_found(self):
        """Test that get_agent_class() returns provided default when agent not found."""
        # Act
        result = self.service.get_agent_class(
            "nonexistent_agent", self.mock_default_agent
        )

        # Assert
        self.assertEqual(result, self.mock_default_agent)

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Agent 'nonexistent_agent' not found, using default: DefaultAgent"
                in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_get_agent_class_returns_none_when_not_found_no_default(self):
        """Test that get_agent_class() returns None when agent not found and no default."""
        # Act
        result = self.service.get_agent_class("nonexistent_agent")

        # Assert
        self.assertIsNone(result)

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Agent 'nonexistent_agent' not found, no default provided" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_get_agent_class_case_insensitive(self):
        """Test that get_agent_class() is case insensitive."""
        # Arrange
        self.service.register_agent("test_agent", self.mock_custom_agent)

        # Act
        result = self.service.get_agent_class("TEST_AGENT")

        # Assert
        self.assertEqual(result, self.mock_custom_agent)

    # =============================================================================
    # 5. has_agent() Method Tests
    # =============================================================================

    def test_has_agent_returns_true_for_registered_agent(self):
        """Test that has_agent() returns True for registered agent."""
        # Arrange
        self.service.register_agent("test_agent", self.mock_custom_agent)

        # Act
        result = self.service.has_agent("test_agent")

        # Assert
        self.assertTrue(result)

    def test_has_agent_returns_false_for_unregistered_agent(self):
        """Test that has_agent() returns False for unregistered agent."""
        # Act
        result = self.service.has_agent("nonexistent_agent")

        # Assert
        self.assertFalse(result)

    def test_has_agent_case_insensitive(self):
        """Test that has_agent() is case insensitive."""
        # Arrange
        self.service.register_agent("test_agent", self.mock_custom_agent)

        # Act & Assert
        self.assertTrue(self.service.has_agent("test_agent"))
        self.assertTrue(self.service.has_agent("TEST_AGENT"))
        self.assertTrue(self.service.has_agent("Test_Agent"))

    # =============================================================================
    # 6. list_agents() Method Tests
    # =============================================================================

    def test_list_agents_returns_all_registered_agents(self):
        """Test that list_agents() returns all registered agents."""
        # Arrange
        self.service.register_agent("agent1", self.mock_custom_agent)
        self.service.register_agent("agent2", self.mock_llm_agent)
        self.service.register_agent("default", self.mock_default_agent)

        # Act
        agent_map = self.service.list_agents()

        # Assert
        expected_agents = {
            "agent1": self.mock_custom_agent,
            "agent2": self.mock_llm_agent,
            "default": self.mock_default_agent,
        }
        self.assertEqual(agent_map, expected_agents)

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Listed 3 registered agents" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_list_agents_returns_copy_for_safety(self):
        """Test that list_agents() returns a copy to prevent external modification."""
        # Arrange
        self.service.register_agent("test_agent", self.mock_custom_agent)

        # Act
        agent_map = self.service.list_agents()
        original_count = len(self.agent_registry_model.agents)

        # Modify the returned map
        agent_map["new_agent"] = self.mock_llm_agent

        # Assert - Original registry should be unchanged
        self.assertEqual(len(self.agent_registry_model.agents), original_count)
        self.assertFalse(self.agent_registry_model.has_agent("new_agent"))

    def test_list_agents_empty_registry(self):
        """Test that list_agents() returns empty dict for empty registry."""
        # Act
        agent_map = self.service.list_agents()

        # Assert
        self.assertEqual(agent_map, {})

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Listed 0 registered agents" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    # =============================================================================
    # 7. get_default_agent_class() Method Tests
    # =============================================================================

    def test_get_default_agent_class_returns_default_when_set(self):
        """Test that get_default_agent_class() returns default agent when set."""
        # Arrange
        self.service.register_agent("default", self.mock_default_agent)

        # Act
        result = self.service.get_default_agent_class()

        # Assert
        self.assertEqual(result, self.mock_default_agent)

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Retrieved default agent class: DefaultAgent" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_get_default_agent_class_returns_none_when_not_set(self):
        """Test that get_default_agent_class() returns None when no default is set."""
        # Act
        result = self.service.get_default_agent_class()

        # Assert
        self.assertIsNone(result)

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "No default agent class is set" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    # =============================================================================
    # 8. set_default_agent_class() Method Tests
    # =============================================================================

    def test_set_default_agent_class_registers_as_default(self):
        """Test that set_default_agent_class() registers agent as 'default'."""
        # Act
        self.service.set_default_agent_class(self.mock_default_agent)

        # Assert
        self.assertTrue(self.agent_registry_model.has_agent("default"))
        self.assertEqual(
            self.agent_registry_model.default_agent_class, self.mock_default_agent
        )
        self.assertEqual(
            self.service.get_default_agent_class(), self.mock_default_agent
        )

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Set default agent class: DefaultAgent" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_set_default_agent_class_overwrites_existing_default(self):
        """Test that set_default_agent_class() overwrites existing default."""
        # Arrange
        old_default = Mock()
        old_default.__name__ = "OldDefaultAgent"
        self.service.set_default_agent_class(old_default)

        # Act
        self.service.set_default_agent_class(self.mock_default_agent)

        # Assert
        self.assertEqual(
            self.agent_registry_model.default_agent_class, self.mock_default_agent
        )
        self.assertNotEqual(self.agent_registry_model.default_agent_class, old_default)

    # =============================================================================
    # 9. get_registered_agent_types() Method Tests
    # =============================================================================

    def test_get_registered_agent_types_returns_all_type_names(self):
        """Test that get_registered_agent_types() returns all registered type names."""
        # Arrange
        self.service.register_agent("agent1", self.mock_custom_agent)
        self.service.register_agent("agent2", self.mock_llm_agent)
        self.service.register_agent("default", self.mock_default_agent)

        # Act
        agent_types = self.service.get_registered_agent_types()

        # Assert
        expected_types = ["agent1", "agent2", "default"]
        self.assertEqual(set(agent_types), set(expected_types))

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Found 3 registered agent types:" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    def test_get_registered_agent_types_empty_registry(self):
        """Test that get_registered_agent_types() returns empty list for empty registry."""
        # Act
        agent_types = self.service.get_registered_agent_types()

        # Assert
        self.assertEqual(agent_types, [])

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Found 0 registered agent types:" in call[1]
                for call in logger_calls
                if call[0] == "debug"
            )
        )

    # =============================================================================
    # 10. clear_all_agents() Method Tests
    # =============================================================================

    def test_clear_all_agents_removes_all_registrations(self):
        """Test that clear_all_agents() removes all agent registrations."""
        # Arrange
        self.service.register_agent("agent1", self.mock_custom_agent)
        self.service.register_agent("agent2", self.mock_llm_agent)
        self.service.register_agent("default", self.mock_default_agent)

        self.assertEqual(len(self.agent_registry_model.agents), 3)
        self.assertIsNotNone(self.agent_registry_model.default_agent_class)

        # Act
        self.service.clear_all_agents()

        # Assert
        self.assertEqual(len(self.agent_registry_model.agents), 0)
        self.assertIsNone(self.agent_registry_model.default_agent_class)

        # Verify warning logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Cleared all 3 registered agents" in call[1]
                for call in logger_calls
                if call[0] == "warning"
            )
        )

    def test_clear_all_agents_empty_registry(self):
        """Test that clear_all_agents() works on empty registry."""
        # Act
        self.service.clear_all_agents()

        # Assert - Should not crash
        self.assertEqual(len(self.agent_registry_model.agents), 0)
        self.assertIsNone(self.agent_registry_model.default_agent_class)

        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(
            any(
                "Cleared all 0 registered agents" in call[1]
                for call in logger_calls
                if call[0] == "warning"
            )
        )

    # =============================================================================
    # 11. Integration Tests with AgentRegistry Model
    # =============================================================================

    def test_service_integrates_with_agent_registry_model(self):
        """Test that service properly integrates with AgentRegistry model."""
        # This test ensures the service correctly delegates to the model

        # Test registration affects model
        self.service.register_agent("integration_test", self.mock_custom_agent)
        self.assertTrue(self.agent_registry_model.has_agent("integration_test"))

        # Test retrieval from model
        direct_result = self.agent_registry_model.get_agent_class("integration_test")
        service_result = self.service.get_agent_class("integration_test")
        self.assertEqual(direct_result, service_result)

        # Test unregistration affects model
        self.service.unregister_agent("integration_test")
        self.assertFalse(self.agent_registry_model.has_agent("integration_test"))

    def test_model_case_normalization_consistency(self):
        """Test that service case normalization is consistent with model."""
        # Register through service
        self.service.register_agent("CamelCase", self.mock_custom_agent)

        # Verify model is case-insensitive for queries (correct behavior)
        self.assertTrue(self.agent_registry_model.has_agent("camelcase"))
        self.assertTrue(
            self.agent_registry_model.has_agent("CamelCase")
        )  # Model normalizes input
        self.assertTrue(self.agent_registry_model.has_agent("CAMELCASE"))

        # Verify service can find with different cases
        self.assertTrue(self.service.has_agent("camelcase"))
        self.assertTrue(self.service.has_agent("CamelCase"))
        self.assertTrue(self.service.has_agent("CAMELCASE"))

    # =============================================================================
    # 12. Error Handling and Edge Cases
    # =============================================================================

    def test_service_handles_none_agent_class(self):
        """Test that service handles None agent class gracefully."""
        # This might raise TypeError, which is acceptable
        with self.assertRaises((TypeError, AttributeError)):
            self.service.register_agent("test", None)

    def test_service_handles_empty_agent_type(self):
        """Test that service handles empty agent type gracefully."""
        # Register with empty string (gets stored but not retrievable as empty)
        self.service.register_agent("", self.mock_custom_agent)

        # Empty string queries should return default agent (correct model behavior)
        result = self.service.get_agent_class("")
        self.assertIsNone(result)  # No default set, so returns None

        # Set a default agent
        self.service.set_default_agent_class(self.mock_default_agent)

        # Now empty string should return the default
        result = self.service.get_agent_class("")
        self.assertEqual(result, self.mock_default_agent)

    def test_service_handles_special_characters_in_agent_type(self):
        """Test that service handles special characters in agent type."""
        # Test with special characters
        special_types = [
            "agent-with-dashes",
            "agent_with_underscores",
            "agent.with.dots",
        ]

        for agent_type in special_types:
            with self.subTest(agent_type=agent_type):
                self.service.register_agent(agent_type, self.mock_custom_agent)
                self.assertTrue(self.service.has_agent(agent_type))
                result = self.service.get_agent_class(agent_type)
                self.assertEqual(result, self.mock_custom_agent)

    def test_service_consistency_across_operations(self):
        """Test that service maintains consistency across multiple operations."""
        # Perform a series of operations and verify consistency

        # Register multiple agents
        agents = {
            "agent1": self.mock_custom_agent,
            "agent2": self.mock_llm_agent,
            "default": self.mock_default_agent,
        }

        for agent_type, agent_class in agents.items():
            self.service.register_agent(agent_type, agent_class)

        # Verify all are registered
        for agent_type in agents.keys():
            self.assertTrue(self.service.has_agent(agent_type))

        # Verify list_agents returns all
        agent_map = self.service.list_agents()
        self.assertEqual(len(agent_map), 3)

        # Verify get_registered_agent_types returns all
        agent_types = self.service.get_registered_agent_types()
        self.assertEqual(set(agent_types), set(agents.keys()))

        # Unregister one agent
        self.service.unregister_agent("agent1")

        # Verify consistency after unregistration
        self.assertFalse(self.service.has_agent("agent1"))
        agent_map = self.service.list_agents()
        self.assertEqual(len(agent_map), 2)
        self.assertNotIn("agent1", agent_map)


if __name__ == "__main__":
    unittest.main()
