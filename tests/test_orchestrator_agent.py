# tests/test_orchestrator_agent.py
"""Tests for OrchestratorAgent functionality."""

import pytest
from unittest.mock import patch, MagicMock

from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
from tests.conftest import create_test_agent


@pytest.fixture
def sample_nodes():
    """Sample node data for testing."""
    return {
        "WeatherNode": {
            "description": "Gets weather information",
            "prompt": "Get weather for {location}",
            "type": "weather"
        },
        "NewsNode": {
            "description": "Fetches news articles",
            "prompt": "Get news about {topic}",
            "type": "news"
        },
        "HelpNode": {
            "description": "Provides help information",
            "prompt": "Provide help about {topic}",
            "type": "assistant"
        }
    }


def test_orchestrator_agent_initialization_defaults(test_logger, test_execution_tracker):
    """Test OrchestratorAgent initialization with default parameters."""
    agent = create_test_agent(
        OrchestratorAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt"
    )
    
    # Check default values
    assert agent.llm_type == "openai"
    assert agent.temperature == 0.2
    assert agent.default_target is None
    assert agent.matching_strategy == "tiered"
    assert agent.confidence_threshold == 0.8
    assert agent.node_filter == "all"


def test_orchestrator_agent_initialization_custom_params(test_logger, test_execution_tracker):
    """Test OrchestratorAgent initialization with custom parameters."""
    context = {
        "llm_type": "anthropic",
        "temperature": 0.5,
        "default_target": "DefaultNode",
        "matching_strategy": "algorithm",
        "confidence_threshold": 0.6,
        "nodes": "NodeA|NodeB"
    }
    
    agent = create_test_agent(
        OrchestratorAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context=context
    )
    
    # Check custom values
    assert agent.llm_type == "anthropic"
    assert agent.temperature == 0.5
    assert agent.default_target == "DefaultNode"
    assert agent.matching_strategy == "algorithm"
    assert agent.confidence_threshold == 0.6
    assert agent.node_filter == "NodeA|NodeB"


def test_orchestrator_agent_with_node_type_filter(test_logger, test_execution_tracker):
    """Test OrchestratorAgent with node_type parameter sets correct filter."""
    context = {"node_type": "weather"}
    
    agent = create_test_agent(
        OrchestratorAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context=context
    )
    
    assert agent.node_filter == "nodeType:weather"


def test_orchestrator_agent_node_filtering_specific_nodes(test_logger, test_execution_tracker, sample_nodes):
    """Test that OrchestratorAgent correctly filters to specific nodes."""
    agent = create_test_agent(
        OrchestratorAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={"nodes": "WeatherNode|HelpNode"}
    )
    
    filtered = agent._apply_node_filter(sample_nodes)
    
    assert len(filtered) == 2
    assert "WeatherNode" in filtered
    assert "HelpNode" in filtered
    assert "NewsNode" not in filtered


def test_orchestrator_agent_node_filtering_by_type(test_logger, test_execution_tracker, sample_nodes):
    """Test that OrchestratorAgent correctly filters nodes by type."""
    agent = create_test_agent(
        OrchestratorAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={"node_type": "weather"}
    )
    
    filtered = agent._apply_node_filter(sample_nodes)
    
    assert len(filtered) == 1
    assert "WeatherNode" in filtered
    assert "NewsNode" not in filtered
    assert "HelpNode" not in filtered


def test_orchestrator_agent_no_filtering_all_nodes(test_logger, test_execution_tracker, sample_nodes):
    """Test that OrchestratorAgent includes all nodes when filter is 'all'."""
    agent = create_test_agent(
        OrchestratorAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={"nodes": "all"}
    )
    
    filtered = agent._apply_node_filter(sample_nodes)
    
    assert len(filtered) == 3
    assert "WeatherNode" in filtered
    assert "NewsNode" in filtered
    assert "HelpNode" in filtered


def test_orchestrator_agent_exact_node_name_matching(sample_nodes):
    """Test that OrchestratorAgent correctly matches exact node names in input."""
    input_text = "I need the WeatherNode to check Paris weather"
    
    node, confidence = OrchestratorAgent._simple_match(input_text, sample_nodes)
    
    assert node == "WeatherNode"
    assert confidence == 1.0


def test_orchestrator_agent_keyword_matching(sample_nodes):
    """Test that OrchestratorAgent correctly matches keywords to nodes."""
    input_text = "I want to know about weather in Paris"
    
    node, confidence = OrchestratorAgent._simple_match(input_text, sample_nodes)
    
    assert node == "WeatherNode"
    assert confidence > 0.0
    assert confidence < 1.0


def test_orchestrator_agent_no_match_returns_first_node(sample_nodes):
    """Test that OrchestratorAgent returns first node when no good match found."""
    input_text = "Something completely unrelated"
    
    node, confidence = OrchestratorAgent._simple_match(input_text, sample_nodes)
    
    # Should return first node with low confidence
    assert node == "WeatherNode"  # First node in the dict
    assert confidence == 0.0


@patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._get_nodes')
def test_orchestrator_agent_with_no_available_nodes(mock_get_nodes, test_logger, test_execution_tracker):
    """Test OrchestratorAgent behavior when no nodes are available."""
    # Mock empty nodes
    mock_get_nodes.return_value = {}
    
    agent = create_test_agent(
        OrchestratorAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={"default_target": "DefaultNode"}
    )
    
    result = agent.process({"user_input": "Some request"})
    
    # Should return default target when no nodes available
    assert result == "DefaultNode"


@patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._get_nodes')
def test_orchestrator_agent_routing_functionality(mock_get_nodes, test_logger, test_execution_tracker, sample_nodes):
    """Test that OrchestratorAgent correctly routes based on input analysis."""
    # Mock nodes available to agent
    mock_get_nodes.return_value = sample_nodes
    
    agent = create_test_agent(
        OrchestratorAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Route user requests to appropriate handlers",
        context={
            "input_fields": ["user_input"],
            "output_field": "selected_node",
            "matching_strategy": "algorithm"  # Use simple matching for predictable results
        }
    )
    
    # Test weather-related input
    result = agent.run({"user_input": "What's the weather like today?"})
    
    assert "selected_node" in result
    assert result["selected_node"] == "WeatherNode"
    assert result["last_action_success"] is True


def test_orchestrator_agent_dependencies_injection(test_logger, test_execution_tracker):
    """Test that OrchestratorAgent properly receives and uses injected dependencies."""
    agent = create_test_agent(
        OrchestratorAgent,
        name="test_agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt"
    )
    
    # Verify dependencies are properly injected
    assert agent._logger is not None
    assert agent._execution_tracker is not None
    assert agent.name == "test_agent"
    assert agent.prompt == "Test prompt"
