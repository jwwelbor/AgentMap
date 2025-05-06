
# test_imports.py
import pytest


def test_agent_imports():
    """Test that important agent classes can be imported."""
    from agentmap.agents import (AGENT_MAP, BaseAgent, DefaultAgent, EchoAgent,
                                 get_agent_class)
    
    assert BaseAgent is not None
    assert DefaultAgent is not None
    assert EchoAgent is not None
    assert isinstance(AGENT_MAP, dict)
    assert callable(get_agent_class)
    
    # Test that we can get built-in agent classes
    echo_class = get_agent_class("echo")
    assert echo_class == EchoAgent
    
    default_class = get_agent_class("default")
    assert default_class == DefaultAgent

def test_routing_imports():
    """Test that routing functions can be imported."""
    from agentmap.graph.routing import (choose_next, dynamic_branch,
                                        parallel_branch)
    
    assert callable(choose_next)
    assert callable(dynamic_branch)
    assert callable(parallel_branch)