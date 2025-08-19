"""
TDD Tests for GraphBundleService.create_bundle_from_csv Method.

Tests the CSV parsing and bundle creation functionality that will be moved 
from GraphRunnerService to GraphBundleService for better separation of concerns.

Updated to use the real CSVGraphParserService interface with parse_csv_to_graph_spec().
"""

import unittest
from pathlib import Path
from unittest.mock import Mock
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime

# Test utilities
from tests.utils.mock_service_factory import MockServiceFactory

# Import real models that the CSV parser uses
from agentmap.models.graph_spec import GraphSpec, NodeSpec
from agentmap.models.node import Node


class CSVParseError(Exception):
    """Exception raised when CSV parsing fails."""
    pass


class TestGraphBundleService(unittest.TestCase):
    """TDD tests for GraphBundleService.create_bundle_from_csv method."""
    
    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        
        # Create mock dependencies
        self.storage_service = self.mock_factory.create_mock_storage_service_manager()
        self.logging_service = self.mock_factory.create_mock_logging_service()
        self.csv_parser = Mock()  # Mock CSVGraphParserService
        
        # Create additional required mock dependencies for enhanced functionality
        self.protocol_requirements_analyzer = Mock()
        self.agent_factory_service = Mock()
        
        # Configure protocol requirements analyzer mock to be dynamic
        def mock_analyze_requirements(nodes):
            # Extract agent types from the actual nodes passed to the analyzer
            required_agents = set()
            for node in nodes.values():
                if hasattr(node, 'agent_type') and node.agent_type:
                    required_agents.add(node.agent_type)
            
            return {
                "required_agents": required_agents,
                "required_services": {"logging_service", "storage_service"}
            }
        
        self.protocol_requirements_analyzer.analyze_graph_requirements.side_effect = mock_analyze_requirements
        
        # Configure agent factory service mock to be dynamic
        def mock_get_agent_mappings(agent_types):
            # Create mappings for any agent types requested
            mappings = {}
            for agent_type in agent_types:
                mappings[agent_type] = f"agentmap.agents.{agent_type.lower()}.{agent_type}Agent"
            return mappings
        
        self.agent_factory_service.get_agent_class_mappings.side_effect = mock_get_agent_mappings
        
        # Import the actual service to test
        from agentmap.services.graph.graph_bundle_service import GraphBundleService
        
        # Create service instance with all required dependencies
        self.bundle_service = GraphBundleService(
            logging_service=self.logging_service,
            json_storage_service=self.storage_service.get_json_service(),
            csv_parser=self.csv_parser,
            protocol_requirements_analyzer=self.protocol_requirements_analyzer,
            agent_factory_service=self.agent_factory_service
        )
    
    def _create_mock_graph_spec(self, graph_name: str, node_specs: List[NodeSpec]) -> Mock:
        """Helper to create a mock GraphSpec with proper interface."""
        mock_spec = Mock(spec=GraphSpec)
        mock_spec.get_graph_names.return_value = [graph_name]
        mock_spec.get_nodes_for_graph.return_value = node_specs
        return mock_spec
    
    def _create_mock_node_dict(self, node_specs: List[NodeSpec]) -> Dict[str, Node]:
        """Helper to create mock nodes dictionary from node specs."""
        nodes = {}
        for spec in node_specs:
            node = Node(
                name=spec.name,
                agent_type=spec.agent_type or "Default",
                context={"context": spec.context} if spec.context else {},
                inputs=spec.input_fields or [],
                output=spec.output_field,
                prompt=spec.prompt,
                description=spec.description
            )
            # Add edges from spec
            if spec.edge:
                node.add_edge("default", spec.edge)
            if spec.success_next:
                node.add_edge("success", spec.success_next)
            if spec.failure_next:
                node.add_edge("failure", spec.failure_next)
            
            nodes[spec.name] = node
        return nodes
    
    def test_create_bundle_from_csv_success(self):
        """Test successful bundle creation from CSV with all metadata preserved."""
        # Arrange
        node_specs = [
            NodeSpec(
                name="agent1",
                graph_name="test-graph",
                agent_type="type1",
                prompt="Test prompt 1",
                success_next="agent2"
            ),
            NodeSpec(
                name="agent2",
                graph_name="test-graph", 
                agent_type="type2",
                prompt="Test prompt 2"
            )
        ]
        
        mock_graph_spec = self._create_mock_graph_spec("test-graph", node_specs)
        mock_nodes = self._create_mock_node_dict(node_specs)
        
        # Configure mock CSV parser
        self.csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self.csv_parser._convert_node_specs_to_nodes.return_value = mock_nodes
        
        # Act
        bundle = self.bundle_service.create_bundle_from_csv("test.csv")
        
        # Assert bundle properties
        self.assertEqual(bundle.graph_name, "test-graph")
        self.assertEqual(len(bundle.required_agents), 2)
        self.assertEqual(len(bundle.nodes), 2)
        self.assertIsNotNone(bundle.created_at)
        
        # Assert agents preserved correctly (required_agents is a set of agent types)
        self.assertIn("type1", bundle.required_agents)
        self.assertIn("type2", bundle.required_agents)
        
        # Assert nodes preserved correctly (nodes dict contains Node objects)
        self.assertIn("agent1", bundle.nodes)
        self.assertIn("agent2", bundle.nodes)
        
        # Assert CSV parser was called correctly
        self.csv_parser.parse_csv_to_graph_spec.assert_called_once_with(Path("test.csv"))
        self.csv_parser._convert_node_specs_to_nodes.assert_called_once_with(node_specs)
    
    def test_create_bundle_from_csv_handles_missing_file(self):
        """Test that missing CSV file raises appropriate error."""
        # Arrange
        self.csv_parser.parse_csv_to_graph_spec.side_effect = FileNotFoundError("test.csv not found")
        
        # Act & Assert
        with self.assertRaises(FileNotFoundError) as context:
            self.bundle_service.create_bundle_from_csv("test.csv")
        
        self.assertIn("test.csv", str(context.exception))
        
        # Verify CSV parser was called
        self.csv_parser.parse_csv_to_graph_spec.assert_called_once_with(Path("test.csv"))
    
    def test_create_bundle_from_csv_handles_invalid_format(self):
        """Test that invalid CSV format raises ValueError (from real parser)."""
        # Arrange - real parser raises ValueError for invalid CSV
        self.csv_parser.parse_csv_to_graph_spec.side_effect = ValueError("Invalid CSV format: missing required columns")
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.bundle_service.create_bundle_from_csv("invalid.csv")
        
        self.assertIn("Invalid CSV", str(context.exception))
        
        # Verify CSV parser was called
        self.csv_parser.parse_csv_to_graph_spec.assert_called_once_with(Path("invalid.csv"))
    
    def test_create_bundle_from_csv_generates_graph_id_if_missing(self):
        """Test that graph_id is generated when graph name is empty."""
        # Arrange - empty graph name should trigger ID generation
        node_specs = [
            NodeSpec(
                name="agent1",
                graph_name="",  # Empty graph name
                agent_type="default"
            )
        ]
        
        mock_graph_spec = self._create_mock_graph_spec("", node_specs)
        mock_nodes = self._create_mock_node_dict(node_specs)
        
        self.csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self.csv_parser._convert_node_specs_to_nodes.return_value = mock_nodes
        
        # Act
        bundle = self.bundle_service.create_bundle_from_csv("test.csv")
        
        # Assert
        self.assertIsNotNone(bundle.graph_name)
        self.assertTrue(bundle.graph_name.startswith("graph-"))  # Generated ID format
        
        # Verify CSV parser was called
        self.csv_parser.parse_csv_to_graph_spec.assert_called_once_with(Path("test.csv"))
    
    def test_create_bundle_from_csv_handles_empty_agents_list(self):
        """Test that empty agents list is handled gracefully."""
        # Arrange - no node specs means empty agents
        node_specs = []  # Empty list
        
        mock_graph_spec = self._create_mock_graph_spec("empty-graph", node_specs)
        mock_nodes = self._create_mock_node_dict(node_specs)
        
        self.csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self.csv_parser._convert_node_specs_to_nodes.return_value = mock_nodes
        
        # Act
        bundle = self.bundle_service.create_bundle_from_csv("empty.csv")
        
        # Assert
        self.assertEqual(bundle.graph_name, "empty-graph")
        self.assertEqual(len(bundle.required_agents), 0)
        self.assertEqual(len(bundle.nodes), 0)
        
        # Verify CSV parser was called
        self.csv_parser.parse_csv_to_graph_spec.assert_called_once_with(Path("empty.csv"))
    
    def test_create_bundle_from_csv_preserves_agent_details(self):
        """Test that all agent configuration details are preserved."""
        # Arrange
        node_specs = [
            NodeSpec(
                name="detailed_agent",
                graph_name="detailed-graph",
                agent_type="llm",
                prompt="You are a helpful assistant",
                description="Agent for processing user queries"
            )
        ]
        
        mock_graph_spec = self._create_mock_graph_spec("detailed-graph", node_specs)
        mock_nodes = self._create_mock_node_dict(node_specs)
        
        self.csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self.csv_parser._convert_node_specs_to_nodes.return_value = mock_nodes
        
        # Act
        bundle = self.bundle_service.create_bundle_from_csv("detailed.csv")
        
        # Assert - required_agents contains agent types
        self.assertEqual(len(bundle.required_agents), 1)
        self.assertIn("llm", bundle.required_agents)
        
        # Assert - nodes contain the actual Node objects
        self.assertIn("detailed_agent", bundle.nodes)
        detailed_node = bundle.nodes["detailed_agent"]
        self.assertEqual(detailed_node.name, "detailed_agent")
        self.assertEqual(detailed_node.agent_type, "llm")
    
    def test_create_bundle_from_csv_preserves_edge_types(self):
        """Test that edge type information is preserved correctly."""
        # Arrange
        node_specs = [
            NodeSpec(name="start", graph_name="edge-types-graph", agent_type="input", edge="process"),
            NodeSpec(name="process", graph_name="edge-types-graph", agent_type="llm", 
                    success_next="success_end", failure_next="failure_end"),
            NodeSpec(name="success_end", graph_name="edge-types-graph", agent_type="output"),
            NodeSpec(name="failure_end", graph_name="edge-types-graph", agent_type="error")
        ]
        
        mock_graph_spec = self._create_mock_graph_spec("edge-types-graph", node_specs)
        mock_nodes = self._create_mock_node_dict(node_specs)
        
        self.csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self.csv_parser._convert_node_specs_to_nodes.return_value = mock_nodes
        
        # Act
        bundle = self.bundle_service.create_bundle_from_csv("edge_types.csv")
        
        # Assert - bundle.nodes contains Node objects with edges
        self.assertEqual(len(bundle.nodes), 4)  # Four nodes
        
        # Check that nodes with edges have them preserved
        self.assertIn("start", bundle.nodes)
        self.assertIn("process", bundle.nodes)
        
        # Verify specific edge mappings in the process node
        process_node = bundle.nodes["process"]
        self.assertIn("success", process_node.edges)
        self.assertIn("failure", process_node.edges)
        self.assertEqual(process_node.edges["success"], "success_end")
        self.assertEqual(process_node.edges["failure"], "failure_end")
    
    def test_create_bundle_from_csv_sets_creation_timestamp(self):
        """Test that creation timestamp is set when bundle is created."""
        # Arrange
        node_specs = [
            NodeSpec(name="agent1", graph_name="timestamp-test", agent_type="default")
        ]
        
        mock_graph_spec = self._create_mock_graph_spec("timestamp-test", node_specs)
        mock_nodes = self._create_mock_node_dict(node_specs)
        
        self.csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self.csv_parser._convert_node_specs_to_nodes.return_value = mock_nodes
        
        # Record time before call
        before_time = datetime.utcnow()
        
        # Act
        bundle = self.bundle_service.create_bundle_from_csv("timestamp.csv")
        
        # Record time after call
        after_time = datetime.utcnow()
        
        # Assert
        self.assertIsNotNone(bundle.created_at)
        # Verify timestamp is within reasonable range (bundle.created_at is ISO string)
        created_at_dt = datetime.fromisoformat(bundle.created_at)
        self.assertGreaterEqual(created_at_dt, before_time)
        self.assertLessEqual(created_at_dt, after_time)
    
    def test_create_bundle_from_csv_logs_operation(self):
        """Test that the operation is properly logged."""
        # Arrange
        node_specs = [
            NodeSpec(name="agent1", graph_name="logging-test", agent_type="default")
        ]
        
        mock_graph_spec = self._create_mock_graph_spec("logging-test", node_specs)
        mock_nodes = self._create_mock_node_dict(node_specs)
        
        self.csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self.csv_parser._convert_node_specs_to_nodes.return_value = mock_nodes
        
        # Act
        bundle = self.bundle_service.create_bundle_from_csv("logging.csv")
        
        # Assert - verify logging service was called to get a logger
        # This ensures the service is properly using the logging infrastructure
        self.logging_service.get_class_logger.assert_called()
        
        # The operation completed successfully, which means logging was set up correctly
        # (detailed logging behavior is implementation detail, not core functionality)


if __name__ == '__main__':
    unittest.main(verbosity=2)
