"""
Unit tests for StaticBundleAnalyzer.

Tests bundle creation using only declarations, CSV parsing without implementation loading,
performance characteristics, and error handling for missing declarations.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
from pathlib import Path
import time
from uuid import UUID

from agentmap.services.static_bundle_analyzer import StaticBundleAnalyzer
from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from tests.utils.mock_service_factory import MockServiceFactory


class TestStaticBundleAnalyzer(unittest.TestCase):
    """Test StaticBundleAnalyzer functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        
        # Create mock services
        self.mock_declaration_registry = Mock()
        self.mock_csv_parser = Mock()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        
        # Create analyzer under test
        self.analyzer = StaticBundleAnalyzer(
            self.mock_declaration_registry,
            self.mock_csv_parser,
            self.mock_logging
        )

    def test_initialization(self):
        """Test analyzer initialization."""
        self.assertIsNotNone(self.analyzer)
        self.assertEqual(self.analyzer.declaration_registry, self.mock_declaration_registry)
        self.assertEqual(self.analyzer.csv_parser, self.mock_csv_parser)

    @patch('pathlib.Path.exists')
    def test_create_static_bundle_basic(self, mock_exists):
        """Test basic static bundle creation from CSV."""
        # Mock file existence
        mock_exists.return_value = True
        
        # Setup mock CSV parser
        mock_graph_spec = Mock()
        mock_graph_spec.graph_name = "test_graph"
        mock_graph_spec.nodes = [
            self._create_mock_node_spec("node1", "echo"),
            self._create_mock_node_spec("node2", "default")
        ]
        
        self.mock_csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Setup mock declaration registry
        self._setup_mock_declarations()
        
        # Create bundle
        csv_path = Path("test.csv")
        result = self.analyzer.create_static_bundle(csv_path)
        
        # Verify result
        self.assertIsInstance(result, GraphBundle)
        self.assertEqual(result.graph_name, "test_graph")
        self.assertEqual(len(result.nodes), 2)
        self.assertIn("echo", result.declared_agent_types)
        self.assertIn("default", result.declared_agent_types)

    @patch('pathlib.Path.exists')
    def test_create_static_bundle_with_custom_graph_name(self, mock_exists):
        """Test static bundle creation with custom graph name override."""
        # Mock file existence
        mock_exists.return_value = True
        
        # Setup mock CSV parser
        mock_graph_spec = Mock()
        mock_graph_spec.graph_name = "original_name"
        mock_graph_spec.nodes = [self._create_mock_node_spec("node1", "echo")]
        
        self.mock_csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self._setup_mock_declarations()
        
        # Create bundle with custom name
        csv_path = Path("test.csv")
        result = self.analyzer.create_static_bundle(csv_path, graph_name="custom_name")
        
        # Verify custom name is used
        self.assertEqual(result.graph_name, "custom_name")

    def test_create_static_bundle_csv_not_found(self):
        """Test static bundle creation when CSV file doesn't exist."""
        csv_path = Path("nonexistent.csv")
        
        with self.assertRaises(FileNotFoundError):
            self.analyzer.create_static_bundle(csv_path)

    @patch('pathlib.Path.exists')
    def test_create_static_bundle_csv_parse_error(self, mock_exists):
        """Test static bundle creation when CSV parsing fails."""
        # Mock file existence
        mock_exists.return_value = True
        
        csv_path = Path("test.csv")
        
        # Mock CSV parser to raise exception
        self.mock_csv_parser.parse_csv_to_graph_spec.side_effect = Exception("Parse error")
        
        with self.assertRaises(ValueError) as context:
            self.analyzer.create_static_bundle(csv_path)
        
        self.assertIn("Invalid CSV structure", str(context.exception))

    @patch('pathlib.Path.exists')
    def test_create_static_bundle_no_implementation_loading(self, mock_exists):
        """Test that bundle creation doesn't load any implementations."""
        # Mock file existence
        mock_exists.return_value = True
        
        # Setup mocks
        mock_graph_spec = Mock()
        mock_graph_spec.graph_name = "test_graph"
        mock_graph_spec.nodes = [self._create_mock_node_spec("node1", "echo")]
        
        self.mock_csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self._setup_mock_declarations()
        
        # Track if any imports or class loading happens
        with patch('builtins.__import__') as mock_import:
            csv_path = Path("test.csv")
            result = self.analyzer.create_static_bundle(csv_path)
            
            # Verify no implementation imports occurred
            mock_import.assert_not_called()
        
        # Verify bundle was still created successfully
        self.assertIsInstance(result, GraphBundle)
        self.assertEqual(result.graph_name, "test_graph")

    @patch('pathlib.Path.exists')
    def test_create_static_bundle_performance(self, mock_exists):
        """Test that static bundle creation is fast."""
        # Mock file existence
        mock_exists.return_value = True
        
        # Setup mocks for medium-sized graph
        mock_graph_spec = Mock()
        mock_graph_spec.graph_name = "performance_test"
        mock_graph_spec.nodes = [
            self._create_mock_node_spec(f"node{i}", "echo") 
            for i in range(50)  # 50 nodes
        ]
        
        self.mock_csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self._setup_mock_declarations()
        
        # Measure creation time
        csv_path = Path("test.csv")
        start_time = time.time()
        result = self.analyzer.create_static_bundle(csv_path)
        end_time = time.time()
        
        # Verify it completed quickly (should be under 100ms for 50 nodes)
        duration = end_time - start_time
        self.assertLess(duration, 0.1, "Static bundle creation should be very fast")
        
        # Verify result
        self.assertIsInstance(result, GraphBundle)
        self.assertEqual(len(result.nodes), 50)

    @patch('pathlib.Path.exists')
    def test_resolve_requirements_with_dependencies(self, mock_exists):
        """Test requirement resolution with service dependencies."""
        # Mock file existence
        mock_exists.return_value = True
        
        # Setup mocks
        mock_graph_spec = Mock()
        mock_graph_spec.graph_name = "test_graph"
        mock_graph_spec.nodes = [self._create_mock_node_spec("node1", "llm")]
        
        self.mock_csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Setup declaration registry to return requirements
        requirements = {
            "services": {"logging_service", "llm_service"},
            "protocols": {"LLMServiceProtocol"},
            "missing": set()
        }
        self.mock_declaration_registry.resolve_agent_requirements.return_value = requirements
        
        # Create bundle
        csv_path = Path("test.csv")
        result = self.analyzer.create_static_bundle(csv_path)
        
        # Verify requirements were resolved
        self.assertEqual(result.declared_services, {"logging_service", "llm_service"})
        self.assertEqual(result.declared_protocols, {"LLMServiceProtocol"})
        self.assertEqual(len(result.missing_declarations), 0)

    @patch('pathlib.Path.exists')
    def test_missing_declarations_handling(self, mock_exists):
        """Test handling of missing agent declarations."""
        # Mock file existence
        mock_exists.return_value = True
        
        # Setup mocks
        mock_graph_spec = Mock()
        mock_graph_spec.graph_name = "test_graph"
        mock_graph_spec.nodes = [
            self._create_mock_node_spec("node1", "unknown_agent"),
            self._create_mock_node_spec("node2", "echo")
        ]
        
        self.mock_csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Setup declaration registry with missing declaration
        requirements = {
            "services": {"logging_service"},
            "protocols": set(),
            "missing": {"unknown_agent"}
        }
        self.mock_declaration_registry.resolve_agent_requirements.return_value = requirements
        
        # Setup validation to return missing agent
        self.mock_declaration_registry.get_agent_declaration.side_effect = (
            lambda agent_type: None if agent_type == "unknown_agent" else Mock()
        )
        
        # Create bundle
        csv_path = Path("test.csv")
        result = self.analyzer.create_static_bundle(csv_path)
        
        # Verify missing declarations are tracked
        self.assertIn("unknown_agent", result.missing_declarations)

    def test_compute_csv_hash(self):
        """Test CSV hash computation."""
        # Create temporary CSV content as bytes (since the implementation opens in 'rb' mode)
        csv_content = "GraphName,Node,AgentType\ntest,node1,echo\n"
        csv_bytes = csv_content.encode('utf-8')
        
        # Mock file reading
        with patch("builtins.open", mock_open(read_data=csv_bytes)):
            csv_path = Path("test.csv")
            hash_result = self.analyzer._compute_csv_hash(csv_path)
        
        # Verify hash is computed
        self.assertIsInstance(hash_result, str)
        self.assertEqual(len(hash_result), 64)  # SHA256 hash length

    def test_extract_agent_types(self):
        """Test extraction of agent types from nodes."""
        nodes = [
            Node("node1", agent_type="echo"),
            Node("node2", agent_type="default"),
            Node("node3", agent_type="echo"),  # Duplicate
            Node("node4", agent_type=None)     # No agent type
        ]
        
        result = self.analyzer._extract_agent_types(nodes)
        
        # Verify unique agent types extracted
        self.assertEqual(result, {"echo", "default"})

    def test_extract_agent_types_empty(self):
        """Test extraction when no nodes have agent types."""
        nodes = [
            Node("node1", agent_type=None),
            Node("node2", agent_type="")
        ]
        
        result = self.analyzer._extract_agent_types(nodes)
        
        # Should default to 'default' agent type
        self.assertEqual(result, {"default"})

    def test_validate_declarations(self):
        """Test declaration validation."""
        # Setup mock declaration registry
        self.mock_declaration_registry.get_agent_declaration.side_effect = (
            lambda agent_type: Mock() if agent_type == "echo" else None
        )
        
        agent_types = {"echo", "unknown_agent"}
        valid, missing = self.analyzer._validate_declarations(agent_types)
        
        self.assertEqual(valid, {"echo"})
        self.assertEqual(missing, {"unknown_agent"})

    def test_find_entry_point(self):
        """Test entry point detection."""
        # Create nodes with edges
        node1 = Node("node1", agent_type="echo")
        node2 = Node("node2", agent_type="default")
        node3 = Node("node3", agent_type="success")
        
        # node1 -> node2 -> node3
        node1.edges = {"default": "node2"}
        node2.edges = {"default": "node3"}
        # node3 has no edges
        
        nodes = {"node1": node1, "node2": node2, "node3": node3}
        
        entry_point = self.analyzer._find_entry_point(nodes)
        
        # node1 should be the entry point (not a target of any edge)
        self.assertEqual(entry_point, "node1")

    def test_find_entry_point_empty_graph(self):
        """Test entry point detection with empty graph."""
        result = self.analyzer._find_entry_point({})
        self.assertIsNone(result)

    @patch('pathlib.Path.exists')
    def test_bundle_id_uniqueness(self, mock_exists):
        """Test that each bundle gets a unique ID."""
        # Mock file existence
        mock_exists.return_value = True
        
        # Setup mocks
        mock_graph_spec = Mock()
        mock_graph_spec.graph_name = "test_graph"
        mock_graph_spec.nodes = [self._create_mock_node_spec("node1", "echo")]
        
        self.mock_csv_parser.parse_csv_to_graph_spec.return_value = mock_graph_spec
        self._setup_mock_declarations()
        
        # Create two bundles
        csv_path = Path("test.csv")
        bundle1 = self.analyzer.create_static_bundle(csv_path)
        bundle2 = self.analyzer.create_static_bundle(csv_path)
        
        # Verify unique IDs
        self.assertNotEqual(bundle1.bundle_id, bundle2.bundle_id)
        
        # Verify IDs are valid UUIDs
        UUID(bundle1.bundle_id)  # Should not raise exception
        UUID(bundle2.bundle_id)  # Should not raise exception

    def _create_mock_node_spec(self, name: str, agent_type: str = None):
        """Helper to create mock node spec."""
        mock_node = Mock()
        mock_node.name = name
        mock_node.agent_type = agent_type
        mock_node.inputs = []
        mock_node.output = "result"
        mock_node.prompt = f"Test prompt for {name}"
        mock_node.description = f"Test description for {name}"
        mock_node.context = {}
        mock_node.edges = {}
        return mock_node

    def _setup_mock_declarations(self):
        """Helper to setup mock declaration registry responses."""
        # Setup basic agent declarations
        echo_declaration = AgentDeclaration(
            agent_type="echo",
            class_path="agentmap.agents.EchoAgent",
            source="builtin"
        )
        
        default_declaration = AgentDeclaration(
            agent_type="default",
            class_path="agentmap.agents.DefaultAgent", 
            source="builtin"
        )
        
        self.mock_declaration_registry.get_agent_declaration.side_effect = (
            lambda agent_type: echo_declaration if agent_type == "echo" 
            else default_declaration if agent_type == "default" 
            else None
        )
        
        # Setup requirement resolution
        self.mock_declaration_registry.resolve_agent_requirements.return_value = {
            "services": {"logging_service"},
            "protocols": set(),
            "missing": set()
        }




if __name__ == "__main__":
    unittest.main()
