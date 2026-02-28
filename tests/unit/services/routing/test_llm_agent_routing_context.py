from agentmap.agents.builtins.llm.llm_agent import LLMAgent


def test_llm_agent_includes_activity_and_profile(monkeypatch):
    agent = LLMAgent(
        name="n1",
        prompt="p",
        context={
            "routing_enabled": True,
            "activity": "narrative",
            "router_profile": "quality_first",
        },
    )
    agent.input_fields = ["message"]
    agent.memory_key = "chat_memory"
    inputs = {"message": "hello", "chat_memory": []}

    rc = agent._prepare_routing_context(inputs)
    assert rc["routing_enabled"] is True
    assert rc["activity"] == "narrative"
    assert rc["router_profile"] == "quality_first"
    assert "input_context" in rc and "user_input" in rc["input_context"]
