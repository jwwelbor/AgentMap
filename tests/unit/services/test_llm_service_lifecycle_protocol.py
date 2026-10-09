"""Keep agent calls separate from runtime-owned service lifecycle operations."""

from unittest.mock import Mock

from agentmap.services.llm_service import LLMService
from agentmap.services.protocols import (
    LLMServiceLifecycleProtocol,
    LLMServiceProtocol,
)


def test_llm_agent_protocol_does_not_require_runtime_lifecycle_methods():
    assert not hasattr(LLMServiceProtocol, "retire")
    assert not hasattr(LLMServiceProtocol, "prepare_shutdown")
    assert not hasattr(LLMServiceProtocol, "shutdown")


def test_concrete_llm_service_satisfies_both_call_and_lifecycle_protocols():
    configuration = Mock()
    configuration.get_llm_pricing_config.return_value = {}
    configuration.get_llm_resilience_config.return_value = {}
    service = LLMService(configuration, Mock(), Mock(), Mock())

    assert isinstance(service, LLMServiceProtocol)
    assert isinstance(service, LLMServiceLifecycleProtocol)
