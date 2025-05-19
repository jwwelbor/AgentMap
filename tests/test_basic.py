# test_basic.py

def test_import():
    """Test that the main package can be imported."""
    import agentmap
    assert agentmap is not None
    
    # Test importing important modules
    from agentmap import agents, config, runner
    from agentmap.graph import builder
    
    assert agents is not None
    assert config is not None
    assert builder is not None
    assert runner is not None

    from agentmap.agents.builtins.llm.llm_agent import LLMAgent
    from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
    from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent
    from agentmap.agents.builtins.llm.google_agent import GoogleAgent