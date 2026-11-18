import pytest

from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.services.state_adapter_service import StateAdapterService
from tests.utils.mock_service_factory import MockServiceFactory


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


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("exclusion_field", ["excluded_providers", "exclude_providers"])
async def test_workflow_agent_forwards_provider_exclusions(
    llm_service, mode, exclusion_field
):
    service, clients = llm_service
    tracking = MockServiceFactory.create_mock_execution_tracking_service()
    agent = LLMAgent(
        name="routed",
        prompt="Respond.",
        context={
            "input_fields": ["message"],
            "output_field": "response",
            "routing_enabled": True,
            "complexity_override": "low",
            "provider_preference": ["anthropic", "google"],
            exclusion_field: ["Anthropic"],
        },
        logger=service._logger,
        execution_tracking_service=tracking,
        state_adapter_service=StateAdapterService(),
    )
    agent.set_execution_tracker(tracking.create_tracker())
    agent.configure_llm_service(service)
    state = {"message": "test"}

    result = await agent.run_async(state) if mode == "async" else agent.run(state)

    assert result["response"] == "response from google"
    assert [call.args[0] for call in clients.call_args_list] == ["google"]
