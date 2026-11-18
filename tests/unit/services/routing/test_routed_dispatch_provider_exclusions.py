"""B006 regression coverage for routed LLM dispatch exclusions."""

from unittest.mock import Mock

import pytest

from agentmap.exceptions.service_exceptions import (
    LLMConfigurationError,
    LLMServiceError,
)


async def call_routed(service, mode, *, provider=None, model=None, **routing_context):
    messages = [{"role": "user", "content": "test"}]
    arguments = {"routing_context": routing_context}
    if provider is not None:
        arguments["provider"] = provider
    if model is not None:
        arguments["model"] = model

    if mode == "sync":
        return service.call_llm(messages, **arguments)
    if mode == "async":
        response = await service.call_llm_async(messages, **arguments)
        return response.text
    return "".join(
        [
            chunk.text_delta
            async for chunk in service.call_llm_stream_async(messages, **arguments)
        ]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
class TestRoutedDispatchProviderExclusions:
    @pytest.mark.parametrize(
        "exclusions", [["Anthropic", "OpenAI", "Google"], ["claude", "GpT", "gemini"]]
    )
    async def test_all_excluded_refuses_before_client_acquisition(
        self, llm_service, mode, exclusions
    ):
        service, clients = llm_service

        with pytest.raises(LLMConfigurationError, match="No eligible providers"):
            await call_routed(service, mode, excluded_providers=exclusions)

        clients.assert_not_called()

    @pytest.mark.parametrize(
        ("fallback_provider", "excluded"),
        [("gpt", "GpT"), ("missing", "OPENAI"), ("claude", "GOOGLE")],
    )
    async def test_router_failure_dispatches_eligible_provider(
        self, llm_service, mode, monkeypatch, fallback_provider, excluded
    ):
        service, clients = llm_service
        monkeypatch.setattr(
            service.routing_service,
            "route_request",
            Mock(side_effect=RuntimeError("router failed")),
        )

        text = await call_routed(
            service,
            mode,
            excluded_providers=[excluded],
            fallback_provider=fallback_provider,
        )

        assert text == "response from anthropic"
        assert [
            (call.args[0], call.args[1]["model"]) for call in clients.call_args_list
        ] == [("anthropic", "claude-low")]

    @pytest.mark.parametrize("configured_fallback", ["claude", "gpt"])
    async def test_provider_failure_retries_only_eligible_providers(
        self, llm_service, mode, configured_fallback
    ):
        service, clients = llm_service
        service.routing_config.fallback["default_provider"] = configured_fallback

        text = await call_routed(
            service,
            mode,
            complexity_override="low",
            provider_preference=["openai"],
            excluded_providers=["Claude"],
        )

        assert [call.args[0] for call in clients.call_args_list] == ["openai", "google"]
        assert text == "response from google"

    @pytest.mark.parametrize("trigger", ["matrix-exhausted", "router-error"])
    @pytest.mark.parametrize(
        ("global_provider", "fallback_provider", "fallback_model", "expected_model"),
        [
            ("openai", "openai", "gpt-request-fallback", "claude-provider-default"),
            ("openai", "claude", None, "claude-provider-default"),
            ("openai", "claude", "claude-request-fallback", "claude-request-fallback"),
            ("anthropic", None, None, "anthropic-system-fallback"),
        ],
    )
    async def test_partial_matrix_recovery_uses_model_owned_by_selected_provider(
        self,
        llm_service,
        provider_configs,
        mode,
        monkeypatch,
        trigger,
        global_provider,
        fallback_provider,
        fallback_model,
        expected_model,
    ):
        service, clients = llm_service
        service.routing_config.routing_matrix.pop("anthropic")
        service.routing_config.fallback.update(
            default_provider=global_provider,
            default_model=f"{global_provider}-system-fallback",
        )
        provider_configs["anthropic"]["model"] = "claude-provider-default"
        if trigger == "router-error":
            monkeypatch.setattr(
                service.routing_service,
                "route_request",
                Mock(side_effect=RuntimeError("router failed")),
            )

        text = await call_routed(
            service,
            mode,
            provider="openai",
            model="gpt-request-model",
            excluded_providers=["OpenAI", "Google"],
            fallback_provider=fallback_provider,
            fallback_model=fallback_model,
        )

        assert text == "response from anthropic"
        assert [
            (call.args[0], call.args[1]["model"]) for call in clients.call_args_list
        ] == [("anthropic", expected_model)]

    async def test_eligible_aliased_retry_provider_retains_configured_priority(
        self, llm_service, mode
    ):
        service, clients = llm_service
        service.routing_config.fallback["default_provider"] = "GeMiNi"

        text = await call_routed(service, mode, complexity_override="low")

        assert text == "response from google"
        assert [call.args[0] for call in clients.call_args_list] == ["openai", "google"]

    @pytest.mark.parametrize("configured_fallback", ["google", "openai"])
    async def test_retry_ignores_registry_providers_without_credentials(
        self, llm_service, mode, monkeypatch, configured_fallback
    ):
        service, clients = llm_service
        service.routing_config.fallback["default_provider"] = configured_fallback
        read_config = service.configuration.get_llm_config.side_effect
        service.configuration.get_llm_config.side_effect = lambda provider: read_config(
            provider
        ) | ({"api_key": ""} if provider == "google" else {})
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        resolve_config = Mock(wraps=service._provider_utils.get_provider_config)
        monkeypatch.setattr(
            service._provider_utils, "get_provider_config", resolve_config
        )

        with pytest.raises(LLMServiceError, match="primary"):
            await call_routed(
                service,
                mode,
                complexity_override="low",
                excluded_providers=["Anthropic"],
            )

        resolve_config.assert_called_once_with("openai")
        assert [call.args[0] for call in clients.call_args_list] == ["openai"]
