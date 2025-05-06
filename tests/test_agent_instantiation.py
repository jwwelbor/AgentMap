from agentmap.agents.builtins.default_agent import DefaultAgent


def test_agent_instantiation():
    agent = DefaultAgent(name="TestAgent", prompt="Say hi", context={})
    assert agent.name == "TestAgent"
    assert agent.prompt == "Say hi"
    assert callable(getattr(agent, "run"))
    assert callable(getattr(agent, "process"))