"""B102 governed cache identity uses the complete credential."""

from unittest.mock import Mock, patch

from agentmap.services.llm_client_factory import LLMClientFactory


def test_same_prefix_credentials_do_not_share_client__b102():
    """Distinct complete credentials must own distinct provider clients."""
    factory = LLMClientFactory(Mock())
    configs = [
        {"api_key": "abcdefgh_LONGER1", "model": "offline"},
        {"api_key": "abcdefgh_LONGER2", "model": "offline"},
        {"api_key": "XXXXXXXX_anything", "model": "offline"},
    ]
    clients = [Mock(name=f"client-{index}") for index in range(3)]
    with patch.object(
        factory,
        "_create_langchain_client",
        side_effect=clients,
    ) as create:
        actual = [
            factory.get_or_create_client("openai", config, streaming=False)
            for config in configs
        ]
    assert actual == clients
    assert create.call_count == 3
    assert (
        factory.get_or_create_client("openai", configs[0], streaming=False)
        is clients[0]
    )
