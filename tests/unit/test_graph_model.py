"""
Unit tests for Graph domain model.

Tests focus on data storage and basic functionality only.
All business logic testing belongs in service tests.
"""

import unittest
from agentmap.models import Graph, Node


class TestGraphModel(unittest.TestCase):
    """Test the Graph data container."""

    def test_graph_creation_minimal(self):
        """Test creating a graph with minimal parameters."""
        graph = Graph(name="test_graph")
        
        self.assertEqual(graph.name, "test_graph")
        self.assertIsNone(graph.entry_point)
        self.assertEqual(graph.nodes, {})

    def test_graph_creation_with_entry_point(self):
        """Test creating a graph with entry point."""
        graph = Graph(name="test_graph", entry_point="start_node")
        
        self.assertEqual(graph.name, "test_graph")
        self.assertEqual(graph.entry_point, "start_node")
        self.assertEqual(graph.nodes, {})

    def test_graph_nodes_dictionary_is_mutable(self):
        """Test that the nodes dictionary can be modified."""
        graph = Graph(name="test_graph")
        node = Node(name="test_node")
        
        # Direct manipulation of nodes dict (would be done by GraphService)
        graph.nodes["test_node"] = node
        
        self.assertEqual(len(graph.nodes), 1)
        self.assertIn("test_node", graph.nodes)
        self.assertEqual(graph.nodes["test_node"], node)

    def test_graph_with_multiple_nodes(self):
        """Test graph with multiple nodes stored."""
        graph = Graph(name="multi_node_graph")
        node1 = Node(name="node1")
        node2 = Node(name="node2")
        
        graph.nodes["node1"] = node1
        graph.nodes["node2"] = node2
        
        self.assertEqual(len(graph.nodes), 2)
        self.assertIn("node1", graph.nodes)
        self.assertIn("node2", graph.nodes)

    def test_graph_dataclass_equality(self):
        """Test that graphs with same data are equal."""
        graph1 = Graph(name="test", entry_point="start")
        graph2 = Graph(name="test", entry_point="start")
        
        self.assertEqual(graph1, graph2)

    def test_graph_dataclass_repr(self):
        """Test string representation of graph."""
        graph = Graph(name="test_graph", entry_point="start")
        repr_str = repr(graph)
        
        self.assertIn("test_graph", repr_str)
        self.assertIn("start", repr_str)

    def test_graph_nodes_field_factory(self):
        """Test that each graph gets its own nodes dictionary."""
        graph1 = Graph(name="graph1")
        graph2 = Graph(name="graph2")
        
        graph1.nodes["node1"] = Node(name="node1")
        
        self.assertEqual(len(graph1.nodes), 1)
        self.assertEqual(len(graph2.nodes), 0)


if __name__ == '__main__':
    unittest.main()
