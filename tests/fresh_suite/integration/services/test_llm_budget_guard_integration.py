"""
Integration test suite for E05-F06 T-E05-F06-008: DI wiring of the opt-in
``LLMBudgetGuardProtocol`` (Component Change 10).

Proves the guard is not merely unit-testable in isolation (that's
``test_llm_service_async.py::TestLLMServiceBudgetGuard``'s job, which
constructs ``LLMService`` directly) but actually reaches the real async
dispatch seam when ``LLMService`` is built the way production DI wiring
builds it -- via ``LLMContainer``'s single canonical ``budget_guard``
provider (``container.llm.budget_guard.override(...)``, Decision 4).

Seam convention matches ``test_llm_batch_integration.py``'s
``TestInt05DIContainerWiring._make_container``: a real ``LLMContainer``
instance built from ``providers.Object(...)`` dependency overrides, no
network or real provider SDK calls. The single provider-transport seam
mocked here is ``_client_factory.get_or_create_client`` -- everything
above it (container construction, guard override, ``LLMService.__init__``,
``call_llm_async`` -> ``_call_llm_async_direct`` ->
``_invoke_with_resilience_async``) runs for real.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from dependency_injector import providers

from agentmap.di.container_parts.llm import LLMContainer
from agentmap.exceptions.service_exceptions import LLMBudgetExceededError
from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory


def _make_container(budget_guard=None):
    """Build a real LLMContainer with mocked leaf dependencies.

    ``anthropic``'s configured api_key is left empty so no batch adapter
    is constructed -- this suite is about the budget-guard provider, not
    batch wiring (already covered by ``test_llm_batch_integration.py``).
    """
    mock_logging = MockServiceFactory.create_mock_logging_service()
    mock_app_config = MockServiceFactory.create_mock_app_config_service()
    mock_app_config.get_llm_config.side_effect = lambda provider: {
        "api_key": "",
        "model": f"{provider}-default-model",
    }
    mock_app_config.get_llm_resilience_config.return_value = {
        "retry": {
            "max_attempts": 1,
            "backoff_base": 2.0,
            "backoff_max": 30.0,
            "jitter": False,
        },
        "circuit_breaker": {"failure_threshold": 5, "reset_timeout": 60},
    }
    mock_app_config.get_routing_config.return_value = {
        "enabled": False,
        "routing_matrix": {},
        "task_types": {},
        "complexity_analysis": {},
        "cost_optimization": {},
        "fallback": {},
        "performance": {},
        "activities": {},
    }
    mock_models = MockServiceFactory.create_mock_llm_models_config_service()
    mock_features_registry = Mock()
    mock_availability_cache = Mock()

    container = LLMContainer(
        app_config_service=providers.Object(mock_app_config),
        logging_service=providers.Object(mock_logging),
        availability_cache_service=providers.Object(mock_availability_cache),
        features_registry_service=providers.Object(mock_features_registry),
        llm_models_config_service=providers.Object(mock_models),
        telemetry_service=providers.Object(None),
    )
    if budget_guard is not None:
        container.budget_guard.override(providers.Object(budget_guard))
    return container


class TestBudgetGuardDIWiring:
    """Component Change 10: single canonical DI registration path."""

    def test_no_guard_registered_defaults_to_none(self):
        """No override -> ``LLMService._budget_guard is None`` -- the
        pre-F06 byte-identical async dispatch path (Decision 4, NFR-F-002)."""
        container = _make_container()
        llm_service = container.llm_service()

        assert isinstance(llm_service, LLMService)
        assert llm_service._budget_guard is None

    def test_overriding_budget_guard_provider_wires_it_into_llm_service(self):
        """``container.budget_guard.override(...)`` is the single canonical
        registration path -- the resulting ``LLMService`` instance carries
        that exact guard object, not a copy or a wrapper."""
        guard = Mock()
        guard.check_before_dispatch = AsyncMock(return_value=None)
        guard.observe_receipt = AsyncMock(return_value=None)

        container = _make_container(budget_guard=guard)
        llm_service = container.llm_service()

        assert llm_service._budget_guard is guard

    @pytest.mark.asyncio
    async def test_registered_guard_refuses_real_di_built_service(self):
        """INT: a guard registered through the real DI container refuses a
        call before any provider invocation -- proving the wiring reaches
        all the way from the container override to the dispatch seam.

        Caller-Path Contract:
          - Entrypoint: ``container.llm_service().call_llm_async(...)``
            (real DI construction, not ``LLMService(...)`` directly).
          - Lowest allowed mock seam: ``_client_factory.get_or_create_client``.
          - Forbidden mocks: ``_invoke_with_resilience_async`` and the
            guard-check call site.
        """
        guard = Mock()
        guard.check_before_dispatch = AsyncMock(
            side_effect=LLMBudgetExceededError("integration: over budget")
        )
        guard.observe_receipt = AsyncMock(return_value=None)

        container = _make_container(budget_guard=guard)
        llm_service = container.llm_service()

        mock_client = Mock()
        mock_client.ainvoke = AsyncMock(return_value=Mock(content="never"))
        mock_client.invoke = Mock()
        llm_service._client_factory.get_or_create_client = Mock(
            return_value=mock_client
        )

        with pytest.raises(LLMBudgetExceededError):
            await llm_service.call_llm_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
            )

        mock_client.ainvoke.assert_not_called()
        mock_client.invoke.assert_not_called()
        guard.check_before_dispatch.assert_awaited_once()
        guard.observe_receipt.assert_not_awaited()
