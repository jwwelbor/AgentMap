"""
Unit tests for ProtocolBasedRequirementsAnalyzer service.

Tests the service that analyzes graph requirements from agent protocols,
determining which services are needed without instantiating agents.
"""
import unittest

from unittest.mock import Mock

from agentmap.services.protocol_requirements_analyzer import ProtocolBasedRequirementsAnalyzer

from agentmap.services.protocols import (
    LLMCapableAgent,
    StorageCapableAgent,
    PromptCapableAgent,
    CSVCapableAgent,
    JSONCapableAgent,
    FileCapableAgent,
    VectorCapableAgent,
    MemoryCapableAgent,
    BlobStorageCapableAgent,
    DatabaseCapableAgent,
    CheckpointCapableAgent,
    OrchestrationCapableAgent,
)


class TestProtocolBasedRequirementsAnalyzer(unittest.TestCase):
    """Test the ProtocolBasedRequirementsAnalyzer service."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_csv_parser = Mock()
        self.mock_agent_factory = Mock()
        self.mock_logging_service = Mock()
        self.mock_logger = Mock()
        self.mock_logging_service.get_class_logger.return_value = self.mock_logger

        # Create service instance
        self.service = ProtocolBasedRequirementsAnalyzer(
            csv_parser=self.mock_csv_parser,
            agent_factory_service=self.mock_agent_factory,
            logging_service=self.mock_logging_service,
        )

    def test_protocol_to_service_mapping_completeness(self):
        """Test that PROTOCOL_TO_SERVICE mapping includes all expected protocols."""
        expected_mappings = {
            "LLMCapableAgent": "llm_service",
            "StorageCapableAgent": "storage_service_manager",
            "PromptCapableAgent": "prompt_manager_service",
            "CSVCapableAgent": "csv_service",
            "JSONCapableAgent": "json_service",
            "FileCapableAgent": "file_service",
            "VectorCapableAgent": "vector_service",
            "MemoryCapableAgent": "memory_service",
            "BlobStorageCapableAgent": "blob_storage_service",
            "DatabaseCapableAgent": "database_service",
            "CheckpointCapableAgent": "checkpoint_service",
            "OrchestrationCapableAgent": "orchestrator_service",
        }

        for protocol_name, expected_service in expected_mappings.items():
            self.assertIn(
                protocol_name,
                self.service.PROTOCOL_TO_SERVICE,
                f"Protocol {protocol_name} missing from mapping",
            )
            self.assertEqual(
                self.service.PROTOCOL_TO_SERVICE[protocol_name],
                expected_service,
                f"Incorrect service mapping for {protocol_name}",
            )

    def test_implements_protocol_with_valid_protocol(self):
        """Test _implements_protocol with agents that implement protocols."""

        # Create mock agent classes that implement specific protocols
        class MockLLMAgent(LLMCapableAgent):
            def configure_llm_service(self, llm_service):
                pass

        class MockStorageAgent(StorageCapableAgent):
            def configure_storage_service(self, storage_service):
                pass

        class MockMultiProtocolAgent(LLMCapableAgent, StorageCapableAgent):
            def configure_llm_service(self, llm_service):
                pass

            def configure_storage_service(self, storage_service):
                pass

        # Test positive cases
        self.assertTrue(
            self.service._implements_protocol(MockLLMAgent, "LLMCapableAgent")
        )
        self.assertTrue(
            self.service._implements_protocol(MockStorageAgent, "StorageCapableAgent")
        )
        self.assertTrue(
            self.service._implements_protocol(
                MockMultiProtocolAgent, "LLMCapableAgent"
            )
        )
        self.assertTrue(
            self.service._implements_protocol(
                MockMultiProtocolAgent, "StorageCapableAgent"
            )
        )

        # Test negative cases
        self.assertFalse(
            self.service._implements_protocol(MockLLMAgent, "StorageCapableAgent")
        )
        self.assertFalse(
            self.service._implements_protocol(MockStorageAgent, "LLMCapableAgent")
        )

    def test_implements_protocol_with_invalid_protocol(self):
        """Test _implements_protocol with invalid protocol names."""

        class MockAgent:
            pass

        # Test with non-existent protocol
        self.assertFalse(
            self.service._implements_protocol(MockAgent, "NonExistentProtocol")
        )

    def test_implements_protocol_with_none_agent_class(self):
        """Test _implements_protocol gracefully handles None agent class."""
        self.assertFalse(
            self.service._implements_protocol(None, "LLMCapableAgent")
        )

    def test_analyze_graph_requirements_basic_case(self):
        """Test analyze_graph_requirements with basic agents."""
        # Create mock nodes directly (no CSV parsing in analyzer anymore)
        from agentmap.models.node import Node
        
        mock_nodes = {
            "node1": Node(name="node1", agent_type="llm_agent"),
            "node2": Node(name="node2", agent_type="storage_agent"),
        }

        # Mock agent factory
        class MockLLMAgent(LLMCapableAgent, PromptCapableAgent):
            def configure_llm_service(self, llm_service):
                pass

            def configure_prompt_service(self, prompt_service):
                pass

        class MockStorageAgent(StorageCapableAgent):
            def configure_storage_service(self, storage_service):
                pass

        # Mock agent factory to return appropriate classes based on agent_type
        def mock_get_agent_class(agent_type):
            if agent_type == "llm_agent":
                return MockLLMAgent
            elif agent_type == "storage_agent":
                return MockStorageAgent
            return None
        
        self.mock_agent_factory.get_agent_class.side_effect = mock_get_agent_class

        # Execute with nodes directly
        result = self.service.analyze_graph_requirements(mock_nodes)

        # Verify
        expected_result = {
            "required_agents": {"llm_agent", "storage_agent"},
            "required_services": {
                "llm_service",
                "prompt_manager_service",
                "storage_service_manager",
                "state_adapter_service",  # Default services always included
                "execution_tracking_service",
            }
        }
        self.assertEqual(result, expected_result)

        # Verify agent factory calls
        self.assertEqual(self.mock_agent_factory.get_agent_class.call_count, 2)

    def test_analyze_graph_requirements_with_unknown_agent_types(self):
        """Test analyze_graph_requirements gracefully handles unknown agent types."""
        # Create mock nodes directly
        from agentmap.models.node import Node
        
        mock_nodes = {
            "node1": Node(name="node1", agent_type="unknown_agent"),
            "node2": Node(name="node2", agent_type="llm_agent"),
        }

        # Mock agent factory - return None for unknown agent
        class MockLLMAgent(LLMCapableAgent):
            def configure_llm_service(self, llm_service):
                pass

        # Mock agent factory to return appropriate classes based on agent_type
        def mock_get_agent_class(agent_type):
            if agent_type == "llm_agent":
                return MockLLMAgent
            elif agent_type == "unknown_agent":
                return None  # Simulate unknown agent
            return None
        
        self.mock_agent_factory.get_agent_class.side_effect = mock_get_agent_class

        # Execute with nodes directly
        result = self.service.analyze_graph_requirements(mock_nodes)

        # Verify - should include basic services even with unknown agent
        expected_result = {
            "required_agents": {"unknown_agent", "llm_agent"},
            "required_services": {
                "llm_service",
                "state_adapter_service",  # Basic fallback services
                "execution_tracking_service",
            }
        }
        self.assertEqual(result, expected_result)

        # Verify warning was logged
        self.mock_logger.warning.assert_called()

    def test_analyze_graph_requirements_with_empty_nodes(self):
        """Test analyze_graph_requirements with empty nodes dictionary."""
        # Create empty nodes dictionary
        mock_nodes = {}

        # Execute with empty nodes
        result = self.service.analyze_graph_requirements(mock_nodes)

        # Verify - should return basic services for empty graph
        expected_result = {
            "required_agents": set(),
            "required_services": {"state_adapter_service", "execution_tracking_service"}
        }
        self.assertEqual(result, expected_result)

    def test_analyze_graph_requirements_complex_multi_protocol_agents(self):
        """Test analyze_graph_requirements with complex agents implementing multiple protocols."""
        # Create mock node directly
        from agentmap.models.node import Node
        
        mock_nodes = {
            "complex_node": Node(name="complex_node", agent_type="complex_agent"),
        }

        # Mock complex agent with multiple protocols
        class MockComplexAgent(
            LLMCapableAgent,
            StorageCapableAgent,
            PromptCapableAgent,
            CSVCapableAgent,
            VectorCapableAgent,
        ):
            def configure_llm_service(self, llm_service):
                pass

            def configure_storage_service(self, storage_service):
                pass

            def configure_prompt_service(self, prompt_service):
                pass

            def configure_csv_service(self, csv_service):
                pass

            def configure_vector_service(self, vector_service):
                pass

        # Mock agent factory to return complex agent
        def mock_get_agent_class(agent_type):
            if agent_type == "complex_agent":
                return MockComplexAgent
            return None
        
        self.mock_agent_factory.get_agent_class.side_effect = mock_get_agent_class

        # Execute with nodes directly
        result = self.service.analyze_graph_requirements(mock_nodes)

        # Verify all required services are included
        expected_result = {
            "required_agents": {"complex_agent"},
            "required_services": {
                "llm_service",
                "storage_service_manager",
                "prompt_manager_service",
                "csv_service",
                "vector_service",
                "state_adapter_service",  # Default services always included
                "execution_tracking_service",
            }
        }
        self.assertEqual(result, expected_result)

    def test_analyze_graph_requirements_empty_graph(self):
        """Test analyze_graph_requirements with empty graph."""
        # Create empty nodes dictionary
        mock_nodes = {}

        # Execute with empty nodes
        result = self.service.analyze_graph_requirements(mock_nodes)

        # Verify basic services are still returned
        expected_result = {
            "required_agents": set(),
            "required_services": {"state_adapter_service", "execution_tracking_service"}
        }
        self.assertEqual(result, expected_result)

    def test_analyze_graph_requirements_with_none_nodes(self):
        """Test analyze_graph_requirements handles None nodes gracefully."""
        # Test with None nodes parameter
        with self.assertRaises(TypeError):
            self.service.analyze_graph_requirements(None)

    def test_analyze_graph_requirements_with_invalid_node_structure(self):
        """Test analyze_graph_requirements handles nodes with missing agent_type."""
        # Create nodes with missing agent type
        from agentmap.models.node import Node
        
        mock_nodes = {
            "node1": Node(name="node1", agent_type=None),  # No agent type
            "node2": Node(name="node2", agent_type="valid_agent"),
        }

        # Mock agent factory for the valid agent
        class MockValidAgent(LLMCapableAgent):
            def configure_llm_service(self, llm_service):
                pass

        # Mock agent factory to return appropriate classes based on agent_type
        def mock_get_agent_class(agent_type):
            if agent_type == "valid_agent":
                return MockValidAgent
            elif agent_type is None:
                return None  # Handle None agent type
            return None
        
        self.mock_agent_factory.get_agent_class.side_effect = mock_get_agent_class

        # Execute - should handle missing agent type gracefully
        result = self.service.analyze_graph_requirements(mock_nodes)

        # Verify - should include services from valid agent and default services
        # Note: agent with agent_type=None should be skipped
        expected_result = {
            "required_agents": {"valid_agent"},  # Only agents with non-None types are included
            "required_services": {
                "llm_service",
                "state_adapter_service",
                "execution_tracking_service",
            }
        }
        self.assertEqual(result, expected_result)

    def test_get_default_services(self):
        """Test _get_default_services returns expected basic services."""
        default_services = self.service._get_default_services()
        expected_default = {"state_adapter_service", "execution_tracking_service"}
        self.assertEqual(default_services, expected_default)

    def test_service_initialization_logging(self):
        """Test that service logs initialization properly."""
        # Verify that logger was requested
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)


if __name__ == "__main__":
    unittest.main()
