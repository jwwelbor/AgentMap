"""
Unit tests for Node domain model.

Tests focus on data storage, retrieval, and simple intrinsic behavior.
No business logic testing - that belongs in service tests.
"""
import pytest
from agentmap.models.node import Node


class TestNodeModel:
    """Unit tests for Node domain model - simple data container tests."""
    
    def test_node_creation_minimal(self):
        """Test creating node with minimal parameters."""
        node = Node("test_node")
        
        assert node.name == "test_node"
        assert node.context is None
        assert node.agent_type is None
        assert node.inputs == []
        assert node.output is None
        assert node.prompt is None
        assert node.description is None
        assert node.edges == {}
    
    def test_node_creation_full_parameters(self):
        """Test creating node with all parameters."""
        context = {"key": "value", "config": {"setting": True}}
        inputs = ["input1", "input2"]
        
        node = Node(
            name="full_node",
            context=context,
            agent_type="llm_agent",
            inputs=inputs,
            output="result",
            prompt="Test prompt",
            description="Test description"
        )
        
        assert node.name == "full_node"
        assert node.context == context
        assert node.agent_type == "llm_agent"
        assert node.inputs == inputs
        assert node.output == "result"
        assert node.prompt == "Test prompt"
        assert node.description == "Test description"
        assert node.edges == {}
    
    def test_inputs_default_to_empty_list(self):
        """Test that inputs parameter defaults to empty list."""
        node = Node("test_node")
        assert node.inputs == []
        assert isinstance(node.inputs, list)
    
    def test_inputs_parameter_not_mutated(self):
        """Test that provided inputs list is stored correctly."""
        original_inputs = ["input1", "input2"]
        node = Node("test_node", inputs=original_inputs)
        
        assert node.inputs == original_inputs
        assert node.inputs is original_inputs  # Should be the same object
    
    def test_add_edge_storage(self):
        """Test that add_edge stores relationships correctly."""
        node = Node("test_node")
        
        # Add single edge
        node.add_edge("success", "next_node")
        assert node.edges["success"] == "next_node"
        assert len(node.edges) == 1
        
        # Add another edge
        node.add_edge("failure", "error_node")
        assert node.edges["failure"] == "error_node"
        assert len(node.edges) == 2
        
        # Test overwrite existing edge
        node.add_edge("success", "different_node")
        assert node.edges["success"] == "different_node"
        assert len(node.edges) == 2  # Still only 2 edges
    
    def test_add_edge_different_conditions(self):
        """Test adding edges with various condition types."""
        node = Node("test_node")
        
        node.add_edge("default", "default_next")
        node.add_edge("success", "success_next")
        node.add_edge("failure", "failure_next")
        node.add_edge("custom", "custom_next")
        
        assert node.edges["default"] == "default_next"
        assert node.edges["success"] == "success_next"
        assert node.edges["failure"] == "failure_next"
        assert node.edges["custom"] == "custom_next"
        assert len(node.edges) == 4
    
    def test_has_conditional_routing_with_success(self):
        """Test conditional routing detection with success edge."""
        node = Node("test_node")
        
        # No conditional routing initially
        assert node.has_conditional_routing() is False
        
        # Add success edge
        node.add_edge("success", "next_node")
        assert node.has_conditional_routing() is True
    
    def test_has_conditional_routing_with_failure(self):
        """Test conditional routing detection with failure edge."""
        node = Node("test_node")
        
        # Add failure edge
        node.add_edge("failure", "error_node")
        assert node.has_conditional_routing() is True
    
    def test_has_conditional_routing_with_both(self):
        """Test conditional routing with both success and failure edges."""
        node = Node("test_node")
        
        node.add_edge("success", "success_node")
        node.add_edge("failure", "failure_node")
        assert node.has_conditional_routing() is True
    
    def test_has_conditional_routing_without_success_failure(self):
        """Test conditional routing detection without success/failure edges."""
        node = Node("test_node")
        
        # Add non-conditional edges
        node.add_edge("default", "next_node")
        node.add_edge("custom", "custom_node")
        assert node.has_conditional_routing() is False
    
    def test_has_conditional_routing_empty_edges(self):
        """Test conditional routing detection with no edges."""
        node = Node("test_node")
        assert node.has_conditional_routing() is False
    
    def test_node_representation_minimal(self):
        """Test string representation with minimal node."""
        node = Node("test_node")
        repr_str = repr(node)
        
        assert "test_node" in repr_str
        assert "Node" in repr_str
        assert "[None]" in repr_str  # agent_type is None
    
    def test_node_representation_with_agent_type(self):
        """Test string representation with agent type."""
        node = Node("test_node", agent_type="llm_agent")
        repr_str = repr(node)
        
        assert "test_node" in repr_str
        assert "llm_agent" in repr_str
        assert "[llm_agent]" in repr_str
    
    def test_node_representation_with_edges(self):
        """Test string representation with edges."""
        node = Node("test_node", agent_type="llm_agent")
        node.add_edge("success", "next_node")
        node.add_edge("failure", "error_node")
        
        repr_str = repr(node)
        assert "test_node" in repr_str
        assert "llm_agent" in repr_str
        assert "success->next_node" in repr_str
        assert "failure->error_node" in repr_str
    
    def test_node_representation_no_edges(self):
        """Test string representation with no edges."""
        node = Node("test_node", agent_type="llm_agent")
        repr_str = repr(node)
        
        assert "test_node" in repr_str
        assert "llm_agent" in repr_str
        # Should not crash with empty edges
        assert "→" in repr_str
    
    def test_context_object_storage(self):
        """Test that context objects are stored correctly."""
        complex_context = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "boolean": True,
            "number": 42
        }
        
        node = Node("test_node", context=complex_context)
        assert node.context == complex_context
        assert node.context is complex_context  # Should be same object
    
    def test_edge_condition_types(self):
        """Test that various edge condition types are stored correctly."""
        node = Node("test_node")
        
        # Test string conditions
        node.add_edge("success", "target1")
        node.add_edge("failure", "target2")
        node.add_edge("timeout", "target3")
        node.add_edge("retry", "target4")
        
        assert node.edges["success"] == "target1"
        assert node.edges["failure"] == "target2"
        assert node.edges["timeout"] == "target3"
        assert node.edges["retry"] == "target4"
