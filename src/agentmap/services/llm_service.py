"""
LLM Service for centralized LLM calling in AgentMap.

Provides a unified interface for calling different LLM providers while
handling configuration, error handling, provider abstraction, tiered fallback,
and resilience (retry with backoff + circuit breaker).
"""

import asyncio
import base64
import inspect
import mimetypes
import random
import re
import time
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)
from uuid import uuid4

from agentmap.exceptions import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMProviderError,
    LLMResolvedCallError,
    LLMServiceError,
)
from agentmap.models.llm_execution import (
    LLMBatchHandle,
    LLMBatchResult,
    LLMBatchStatus,
    LLMBatchSubmitRequest,
    LLMExecutionError,
    LLMFanoutResult,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMUsage,
)
from agentmap.services.config import AppConfigService
from agentmap.services.config.llm_models_config_service import LLMModelsConfigService
from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.llm_batch_errors import (
    LLMBatchCancelNotSupportedError,
    LLMBatchExpiredError,
    LLMBatchNotReadyError,
    LLMBatchUnsupportedProviderError,
)
from agentmap.services.llm_client_factory import LLMClientFactory
from agentmap.services.llm_error_utils import (
    _sanitize_error_message,
    classify_llm_error,
    is_retryable,
)
from agentmap.services.llm_fallback_handler import LLMFallbackHandler
from agentmap.services.llm_message_service import LLMMessageService
from agentmap.services.llm_provider_utils import LLMProviderUtils
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.circuit_breaker import CircuitBreaker
from agentmap.services.routing.routing_service import LLMRoutingService
from agentmap.services.routing.types import RoutingContext
from agentmap.services.telemetry.constants import (
    GEN_AI_PROMPT_CONTENT,
    GEN_AI_PROVIDER_REQUEST_ID,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_CONTENT,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_SYSTEM_FINGERPRINT,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    LLM_CALL_SPAN,
    METRIC_DIM_BATCH_STATUS,
    METRIC_DIM_ERROR_TYPE,
    METRIC_DIM_MODEL,
    METRIC_DIM_PROVIDER,
    METRIC_DIM_TIER,
    METRIC_LLM_BATCH_CANCEL_COUNT,
    METRIC_LLM_BATCH_POLL_COUNT,
    METRIC_LLM_BATCH_RESULTS_FETCHED_COUNT,
    METRIC_LLM_BATCH_SUBMITTED_COUNT,
    METRIC_LLM_CIRCUIT_BREAKER,
    METRIC_LLM_DURATION,
    METRIC_LLM_ERRORS,
    METRIC_LLM_FALLBACK,
    METRIC_LLM_ROUTING_CACHE_HIT,
    METRIC_LLM_TOKENS_INPUT,
    METRIC_LLM_TOKENS_OUTPUT,
    METRIC_LLM_TTFT,
    ROUTING_CACHE_HIT,
    ROUTING_CIRCUIT_BREAKER_STATE,
    ROUTING_COMPLEXITY,
    ROUTING_CONFIDENCE,
    ROUTING_FALLBACK_TIER,
    ROUTING_MODEL,
    ROUTING_PROVIDER,
)

# Keys that ``call_llm_async`` accepts as explicit parameters.  If any of these
# appear in ``LLMRequest.request_options`` they would collide with the explicit
# keyword arguments in ``_execute_fan_out_item``, causing a TypeError at runtime.
_RESERVED_KEYS: frozenset = frozenset(
    {
        "messages",
        "provider",
        "model",
        "temperature",
        "routing_context",
        "cache_system_prompt",
    }
)


class LLMService:
    """
    Centralized service for making LLM calls across different providers.

    Handles provider abstraction, configuration loading, error handling,
    and tiered fallback strategies while maintaining a simple interface for callers.
    """

    def __init__(
        self,
        configuration: AppConfigService,
        logging_service: LoggingService,
        routing_service: LLMRoutingService,
        llm_models_config_service: LLMModelsConfigService,
        features_registry_service: Optional[FeaturesRegistryService] = None,
        routing_config_service: Optional[LLMRoutingConfigService] = None,
        telemetry_service: Optional[Any] = None,
        batch_adapter: Optional[Any] = None,
        batch_adapters: Optional[Dict[str, Any]] = None,
        batch_repo: Optional[Any] = None,
    ):
        """
        Initialize the LLM service.

        Args:
            configuration: Application configuration service
            logging_service: Logging service
            routing_service: LLM routing service
            llm_models_config_service: LLM models configuration service
            features_registry_service: Optional features registry service
            routing_config_service: Optional routing configuration service
            telemetry_service: Optional telemetry service for span management.
                When None, all telemetry helpers silently no-op.
        """
        self.configuration = configuration
        self._logger = logging_service.get_class_logger("agentmap.llm")
        self.routing_service = routing_service
        self.llm_models_config = llm_models_config_service
        self.features_registry = features_registry_service
        self.routing_config = routing_config_service
        self._telemetry_service = telemetry_service

        # Initialize helper components
        self._client_factory = LLMClientFactory(logging_service)
        self._provider_utils = LLMProviderUtils(
            configuration, llm_models_config_service, logging_service
        )
        # Use lambda so the fallback handler always dispatches through the
        # current binding of _invoke_with_resilience_async (important for
        # tests that patch the method after construction).
        self._fallback_handler = LLMFallbackHandler(
            logging_service,
            routing_config_service,
            features_registry_service,
            invoke_fn=self._invoke_with_resilience,
            invoke_async_fn=lambda client, msgs, provider, model: self._invoke_with_resilience_async(
                client, msgs, provider, model
            ),
        )
        self._message_utils = LLMMessageService()

        # Resilience: retry + circuit breaker
        self._resilience_config = configuration.get_llm_resilience_config()
        cb_cfg = self._resilience_config.get("circuit_breaker", {})
        self._circuit_breaker = CircuitBreaker(
            failures_threshold=cb_cfg.get("failure_threshold", 5),
            reset_seconds=cb_cfg.get("reset_timeout", 60),
        )

        # Track whether routing is enabled
        self._routing_enabled = routing_service is not None

        # Metrics instruments (created once, reused per call) -- ADR-E02F07-003
        self._metric_duration = None
        self._metric_tokens_input = None
        self._metric_tokens_output = None
        self._metric_errors = None
        self._metric_cache_hit = None
        self._metric_circuit_breaker = None
        self._metric_fallback = None
        self._metric_batch_submitted = None
        self._metric_batch_poll = None
        self._metric_batch_results_fetched = None
        self._metric_batch_cancel = None
        self._metric_ttft = None  # E06-F03: streaming time-to-first-token histogram
        if telemetry_service is not None:
            try:
                self._metric_duration = telemetry_service.create_histogram(
                    METRIC_LLM_DURATION,
                    unit="s",
                    description="LLM call duration",
                )
                self._metric_ttft = telemetry_service.create_histogram(
                    METRIC_LLM_TTFT,
                    unit="s",
                    description="LLM streaming time-to-first-token",
                )
                self._metric_tokens_input = telemetry_service.create_counter(
                    METRIC_LLM_TOKENS_INPUT,
                    unit="token",
                    description="LLM input tokens",
                )
                self._metric_tokens_output = telemetry_service.create_counter(
                    METRIC_LLM_TOKENS_OUTPUT,
                    unit="token",
                    description="LLM output tokens",
                )
                self._metric_errors = telemetry_service.create_counter(
                    METRIC_LLM_ERRORS,
                    unit="1",
                    description="LLM call errors",
                )
                self._metric_cache_hit = telemetry_service.create_counter(
                    METRIC_LLM_ROUTING_CACHE_HIT,
                    unit="1",
                    description="Routing cache hits",
                )
                self._metric_circuit_breaker = telemetry_service.create_up_down_counter(
                    METRIC_LLM_CIRCUIT_BREAKER,
                    unit="1",
                    description="Open circuit breakers",
                )
                self._metric_fallback = telemetry_service.create_counter(
                    METRIC_LLM_FALLBACK,
                    unit="1",
                    description="Fallback activations",
                )
                self._metric_batch_submitted = telemetry_service.create_counter(
                    METRIC_LLM_BATCH_SUBMITTED_COUNT,
                    unit="1",
                    description="Batch submissions",
                )
                self._metric_batch_poll = telemetry_service.create_counter(
                    METRIC_LLM_BATCH_POLL_COUNT,
                    unit="1",
                    description="Batch polls",
                )
                self._metric_batch_results_fetched = telemetry_service.create_counter(
                    METRIC_LLM_BATCH_RESULTS_FETCHED_COUNT,
                    unit="1",
                    description="Batch result fetches",
                )
                self._metric_batch_cancel = telemetry_service.create_counter(
                    METRIC_LLM_BATCH_CANCEL_COUNT,
                    unit="1",
                    description="Batch cancellation requests",
                )
            except Exception:
                pass  # Instrument creation failure silently ignored

        # Batch execution dependencies (E05-F04) — provider→adapter registry.
        # batch_adapters takes precedence; batch_adapter (single) kept for
        # backwards-compat with F03 DI wiring (wraps it as {"anthropic": adapter}).
        if batch_adapters is not None:
            self._batch_adapters: Dict[str, Any] = dict(batch_adapters)
        elif batch_adapter is not None:
            self._batch_adapters = {"anthropic": batch_adapter}
        else:
            self._batch_adapters = {}
        self._batch_repo = batch_repo

    @property
    def _clients(self):
        """Backwards compatibility accessor for client cache."""
        return self._client_factory._clients

    def _normalize_provider(self, provider: str) -> str:
        """Backwards compatibility wrapper for normalize_provider."""
        return self._provider_utils.normalize_provider(provider)

    def _get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Backwards compatibility wrapper for get_provider_config."""
        return self._provider_utils.get_provider_config(provider)

    def _get_available_providers(self) -> List[str]:
        """Backwards compatibility wrapper for get_available_providers."""
        return self._provider_utils.get_available_providers()

    def _create_langchain_client(self, provider: str, config: Dict[str, Any]) -> Any:
        """Backwards compatibility wrapper for create_langchain_client."""
        return self._client_factory._create_langchain_client(provider, config)

    def _get_or_create_client(self, provider: str, config: Dict[str, Any]) -> Any:
        """Backwards compatibility wrapper for get_or_create_client."""
        return self._client_factory.get_or_create_client(provider, config)

    def _convert_messages_to_langchain(self, messages: List[LLMMessage]) -> List[Any]:
        """Backwards compatibility wrapper for convert_messages_to_langchain."""
        return self._message_utils.convert_messages_to_langchain(messages)

    def _extract_prompt_from_messages(self, messages: List[LLMMessage]) -> str:
        """Backwards compatibility wrapper for extract_prompt_from_messages."""
        return self._message_utils.extract_prompt_from_messages(messages)

    def _is_prompt_caching_requested(
        self,
        messages: List[Dict[str, Any]],
        routing_context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Return True when caller input requests prompt caching."""
        if routing_context and routing_context.get("requires_prompt_caching", False):
            return True
        return LLMMessageService.has_prompt_caching(messages)

    # Providers where cache_system_prompt=True is a documented silent no-op.
    # inject_cache_metadata returns messages unchanged for these providers;
    # the capability check is skipped so callers do not receive a spurious error.
    # E05-F05 spec: "OpenAI auto-caches at >1024 tokens — no injection needed."
    _CACHE_SYSTEM_PROMPT_NOOP_PROVIDERS: frozenset = frozenset({"openai"})

    def _validate_prompt_caching_support(
        self,
        provider: Optional[str],
        messages: List[Dict[str, Any]],
        routing_context: Optional[Dict[str, Any]] = None,
        *,
        execution_path: str,
        cache_system_prompt: bool = False,
    ) -> None:
        """Fail fast when prompt caching is requested on an unsupported path.

        Caching is considered requested when any of these signals are present:
        - ``cache_system_prompt=True`` kwarg (E05-F05 agnostic interface)
        - ``routing_context["requires_prompt_caching"]`` is True (routing path)
        - Any message content block carries a ``cache_control`` key (E05-F01 passthrough)

        For providers in ``_CACHE_SYSTEM_PROMPT_NOOP_PROVIDERS`` (e.g. ``openai``),
        ``cache_system_prompt=True`` is a documented no-op: ``inject_cache_metadata``
        returns messages unchanged and no error is raised.  The capability flag
        ``prompt_caching`` in config controls the E05-F01 passthrough path
        (Anthropic-specific ``cache_control`` syntax) and is not consulted when the
        only caching signal is the agnostic ``cache_system_prompt`` kwarg for a
        known no-op provider.
        """
        if not cache_system_prompt and not self._is_prompt_caching_requested(
            messages, routing_context
        ):
            return

        if execution_path == "ask_vision":
            raise LLMServiceError(
                "Prompt caching is not supported on execution path 'ask_vision'."
            )

        normalized_provider = (
            self._provider_utils.normalize_provider(provider) if provider else None
        )

        # When cache_system_prompt=True is the only caching signal and the provider
        # is a known no-op (e.g. openai), injection is skipped by inject_cache_metadata
        # and no error should be raised.  The capability check is only needed for
        # the E05-F01 passthrough path (embedded cache_control blocks) or routing
        # context signals, both of which require Anthropic-specific syntax.
        if (
            cache_system_prompt
            and normalized_provider in self._CACHE_SYSTEM_PROMPT_NOOP_PROVIDERS
            and not self._is_prompt_caching_requested(messages, routing_context)
        ):
            return

        if (
            normalized_provider is None
            or self.routing_config is None
            or not self.routing_config.supports_prompt_caching(normalized_provider)
        ):
            provider_name = normalized_provider or "unknown"
            raise LLMServiceError(
                "Prompt caching is not supported for provider "
                f"'{provider_name}' on execution path '{execution_path}'."
            )

    def call_llm(
        self,
        messages: List[LLMMessage],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        cache_system_prompt: bool = False,
        **kwargs,
    ) -> str:
        """
        Make an LLM call with standardized interface.

        When routing_context is provided, routing owns all provider and model selection.
        The provider and model parameters are ignored in that case -- use
        routing_context['provider_preference'] / routing_context['fallback_provider'] and
        routing_context['model_override'] instead. Warnings are logged if provider or model
        are passed alongside routing_context.

        Args:
            provider: Provider name ("openai", "anthropic", "google", etc.).
                      Ignored when routing_context is provided.
            messages: List of message dictionaries
            model: Optional model override. Ignored when routing_context is provided.
            temperature: Optional temperature override
            routing_context: Optional routing context for intelligent model selection.
                             When present, routing owns all provider/model decisions.
            cache_system_prompt: When True, inject provider-specific prompt-caching
                                 metadata into system messages (Anthropic only; no-op
                                 for other providers).
            **kwargs: Additional provider-specific parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: On various error conditions
        """
        kwargs["cache_system_prompt"] = cache_system_prompt
        if self._telemetry_service is not None:
            return self._call_llm_with_telemetry(
                messages, provider, model, temperature, routing_context, **kwargs
            )
        return self._call_llm_core(
            messages, provider, model, temperature, routing_context, **kwargs
        )

    async def call_llm_async(
        self,
        messages: List[LLMMessage],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        cache_system_prompt: bool = False,
        **kwargs,
    ) -> LLMResponse:
        """
        Make an async LLM call and return a rich ``LLMResponse``.

        ``LLMResponse.text`` carries the response text; ``.resolved_provider``
        and ``.resolved_model`` reflect the provider and model that **actually
        handled** the request (after routing or fallback); ``.usage`` carries
        normalized token counts when the provider returned usage metadata.

        When routing_context is provided, routing owns all provider and model
        selection. Explicit provider and model inputs are ignored with the same
        warnings used by the sync path.

        Args:
            cache_system_prompt: When True, inject provider-specific prompt-caching
                                 metadata into system messages (Anthropic only; no-op
                                 for other providers).
        """
        kwargs["cache_system_prompt"] = cache_system_prompt
        if self._telemetry_service is not None:
            return await self._call_llm_async_with_telemetry(
                messages, provider, model, temperature, routing_context, **kwargs
            )
        return await self._call_llm_async_core(
            messages, provider, model, temperature, routing_context, **kwargs
        )

    async def _call_llm_async_with_telemetry(
        self,
        messages: List[LLMMessage],
        provider: Optional[str],
        model: Optional[str],
        temperature: Optional[float],
        routing_context: Optional[Dict[str, Any]],
        **kwargs,
    ) -> LLMResponse:
        """Async telemetry wrapper mirroring the sync LLM span behavior."""
        assert self._telemetry_service is not None
        initial_attributes: Dict[str, Any] = {}
        if provider:
            initial_attributes[GEN_AI_SYSTEM] = self._provider_utils.normalize_provider(
                provider
            )
        if model:
            initial_attributes[GEN_AI_REQUEST_MODEL] = model

        try:
            with self._telemetry_service.start_span(
                LLM_CALL_SPAN,
                attributes=initial_attributes,
            ) as span:
                try:
                    result = await self._call_llm_async_core(
                        messages,
                        provider,
                        model,
                        temperature,
                        routing_context,
                        **kwargs,
                    )
                    self._capture_llm_content(span, messages, result.text)
                    self._set_span_status_ok(span)
                    return result
                except Exception as e:
                    self._record_span_exception_safe(span, e)
                    raise
        except Exception as outer_error:
            if isinstance(
                outer_error,
                (
                    LLMServiceError,
                    LLMProviderError,
                    LLMConfigurationError,
                    LLMDependencyError,
                ),
            ):
                raise
            self._logger.warning(
                f"Telemetry error, executing without instrumentation: {outer_error}"
            )
            return await self._call_llm_async_core(
                messages, provider, model, temperature, routing_context, **kwargs
            )

    def _call_llm_with_telemetry(
        self,
        messages: List[LLMMessage],
        provider: Optional[str],
        model: Optional[str],
        temperature: Optional[float],
        routing_context: Optional[Dict[str, Any]],
        **kwargs,
    ) -> str:
        """Execute call_llm wrapped in a gen_ai.chat telemetry span.

        Falls back to ``_call_llm_core`` if span creation fails (Layer 1
        isolation).  LLM errors are re-raised directly -- only telemetry
        infrastructure failures trigger the fallback.
        """
        assert self._telemetry_service is not None
        # Build initial attributes from known values
        initial_attributes: Dict[str, Any] = {}
        if provider:
            initial_attributes[GEN_AI_SYSTEM] = self._provider_utils.normalize_provider(
                provider
            )
        if model:
            initial_attributes[GEN_AI_REQUEST_MODEL] = model

        try:
            with self._telemetry_service.start_span(
                LLM_CALL_SPAN,
                attributes=initial_attributes,
            ) as span:
                try:
                    result = self._call_llm_core(
                        messages,
                        provider,
                        model,
                        temperature,
                        routing_context,
                        **kwargs,
                    )

                    # Capture optional content on the span
                    self._capture_llm_content(span, messages, result)

                    # Set span status to OK on success
                    self._set_span_status_ok(span)

                    return result

                except Exception as e:
                    # Record exception and set ERROR status on span
                    self._record_span_exception_safe(span, e)
                    raise

        except Exception as outer_error:
            # Distinguish LLM errors (re-raise) from telemetry errors (fallback)
            if isinstance(
                outer_error,
                (
                    LLMServiceError,
                    LLMProviderError,
                    LLMConfigurationError,
                    LLMDependencyError,
                ),
            ):
                raise
            # Telemetry setup failure -- fall back to uninstrumented path
            self._logger.warning(
                f"Telemetry error, executing without instrumentation: " f"{outer_error}"
            )
            return self._call_llm_core(
                messages, provider, model, temperature, routing_context, **kwargs
            )

    def _call_llm_core(
        self,
        messages: List[LLMMessage],
        provider: Optional[str],
        model: Optional[str],
        temperature: Optional[float],
        routing_context: Optional[Dict[str, Any]],
        **kwargs,
    ) -> str:
        """Execute the actual LLM call logic (routing or direct).

        This is the original ``call_llm()`` body, extracted so that the
        guard-and-dispatch pattern can wrap it with telemetry.
        """
        if routing_context is not None and self.routing_service:
            if model is not None:
                self._logger.warning(
                    "[LLMService] 'model' parameter is ignored when routing_context "
                    "is provided. Use routing_context['model_override'] to force a "
                    "specific model."
                )
            if provider is not None:
                self._logger.warning(
                    "[LLMService] 'provider' parameter is ignored when routing_context "
                    "is provided. Use routing_context['provider_preference'] to "
                    "influence provider selection or "
                    "routing_context['fallback_provider'] to set the fallback."
                )
            return self._call_llm_with_routing(
                messages,
                routing_context,
                temperature=temperature,
                model=model,
                **kwargs,
            )
        if not provider:
            raise LLMServiceError(
                "provider is required when routing_context is not provided."
            )
        return self._call_llm_direct(
            provider,
            messages,
            model,
            temperature,
            **kwargs,
        )

    async def _call_llm_async_core(
        self,
        messages: List[LLMMessage],
        provider: Optional[str],
        model: Optional[str],
        temperature: Optional[float],
        routing_context: Optional[Dict[str, Any]],
        **kwargs,
    ) -> LLMResponse:
        """Single async seam shared by ``call_llm_async`` and the fan-out path.

        Returns a rich ``LLMResponse`` carrying the resolved provider identity
        and usage.  Both public entrypoints delegate here; there is exactly one
        async resilience stack.
        """
        if routing_context is not None and self.routing_service:
            if model is not None:
                self._logger.warning(
                    "[LLMService] 'model' parameter is ignored when routing_context "
                    "is provided. Use routing_context['model_override'] to force a "
                    "specific model."
                )
            if provider is not None:
                self._logger.warning(
                    "[LLMService] 'provider' parameter is ignored when routing_context "
                    "is provided. Use routing_context['provider_preference'] to "
                    "influence provider selection or "
                    "routing_context['fallback_provider'] to set the fallback."
                )
            return await self._call_llm_async_with_routing(
                messages,
                routing_context,
                temperature=temperature,
                model=model,
                **kwargs,
            )
        if not provider:
            raise LLMServiceError(
                "provider is required when routing_context is not provided."
            )
        return await self._call_llm_async_direct(
            provider,
            messages,
            model,
            temperature,
            **kwargs,
        )

    def _call_llm_with_routing(
        self,
        messages: List[LLMMessage],
        routing_context: Dict[str, Any],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Make an LLM call using intelligent routing to select provider/model.

        Args:
            messages: List of message dictionaries
            routing_context: Dictionary containing routing parameters
            temperature: Optional temperature override from caller
            model: Optional model hint (used as fallback if routing fails)
            **kwargs: Additional LLM parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: If routing fails or no providers are available
        """
        if not self.routing_service:
            raise LLMServiceError("Routing requested but no routing service available")

        # Narrow try to routing decision only — _call_llm_direct errors must propagate
        # as-is; the broad except was re-labeling downstream errors as routing failures.
        try:
            # Convert routing context dict to RoutingContext object
            context = self._create_routing_context(routing_context, messages)

            # Get available providers from configuration
            available_providers = self._provider_utils.get_available_providers()

            if not available_providers:
                raise LLMServiceError("No providers configured")

            # Extract prompt for routing analysis
            prompt = self._message_utils.extract_prompt_from_messages(messages)

            # Get routing decision
            decision = self.routing_service.route_request(
                prompt=prompt,
                task_type=context.task_type,
                available_providers=available_providers,
                routing_context=context,
            )

            self._logger.info(
                f"Routing decision: {decision.provider}:{decision.model} "
                f"(complexity: {decision.complexity}, "
                f"confidence: {decision.confidence:.2f})"
            )

            # Record routing attributes on the current span (E02-F03)
            self._record_routing_attributes(decision)

            # Resolve max_tokens priority: node context > activity config > provider default
            node_max_tokens = routing_context.get("max_tokens")
            if node_max_tokens is None:
                node_max_tokens = kwargs.pop("max_tokens", None)

            resolved_max_tokens = (
                node_max_tokens if node_max_tokens is not None else decision.max_tokens
            )
            # 0 means "no limit" — actively suppress any provider default
            if resolved_max_tokens == 0:
                self._logger.debug(
                    "max_tokens=0 resolved to no limit (provider default)"
                )
                kwargs["max_tokens"] = 0  # sentinel: _call_llm_direct strips it
                resolved_max_tokens = None
            elif resolved_max_tokens is not None:
                source = (
                    "node context" if node_max_tokens is not None else "activity config"
                )
                self._logger.debug(
                    f"max_tokens={resolved_max_tokens} (source: {source})"
                )
                kwargs["max_tokens"] = resolved_max_tokens

            # Record resolved max_tokens on telemetry span (post-priority)
            if resolved_max_tokens is not None:
                self._set_current_span_attributes(
                    {GEN_AI_REQUEST_MAX_TOKENS: resolved_max_tokens}
                )

            # Make the actual LLM call with the selected provider/model
            return self._call_llm_direct(
                provider=decision.provider,
                messages=messages,
                model=decision.model,
                temperature=temperature,
                routing_context=routing_context,
                **kwargs,
            )

        except LLMServiceError:
            raise
        except Exception as e:
            self._logger.error(f"Routing failed: {e}")
            # Fall back to direct call if routing (pre-selection) fails
            fallback_provider = routing_context.get("fallback_provider", "anthropic")
            self._logger.warning(
                f"Falling back to {fallback_provider} due to routing failure"
            )
            # Record fallback metric
            self._record_fallback_metric("routing_fallback")
            # Preserve node-level max_tokens in fallback path
            fallback_max_tokens = routing_context.get("max_tokens")
            if fallback_max_tokens is not None and "max_tokens" not in kwargs:
                kwargs["max_tokens"] = fallback_max_tokens
            return self._call_llm_direct(
                provider=fallback_provider,
                messages=messages,
                model=model,
                temperature=temperature,
                routing_context=routing_context,
                **kwargs,
            )

    def _call_llm_direct(
        self,
        provider: str,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Make a direct LLM call to a specific provider without routing.

        Uses ``_invoke_with_resilience`` for retry + circuit breaker, then
        falls back through tiered providers if routing config is available.

        Args:
            provider: Provider name ("openai", "anthropic", "google", etc.)
            messages: List of message dictionaries
            model: Optional model override
            temperature: Optional temperature override
            routing_context: Optional routing context forwarded from the routing
                             path so that ``requires_prompt_caching`` flags
                             carried there are honoured even when messages contain
                             no embedded ``cache_control`` blocks.
            **kwargs: Additional provider-specific parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: On various error conditions
        """
        config: Dict[str, Any] = {}
        original_messages = messages
        try:
            # Extract cache_system_prompt before forwarding kwargs to the provider.
            # This must happen before validation so the flag triggers the support check.
            cache_system_prompt: bool = kwargs.pop("cache_system_prompt", False)

            # Normalize provider name
            provider = self._provider_utils.normalize_provider(provider)
            self._validate_prompt_caching_support(
                provider,
                messages,
                routing_context,
                execution_path="call_llm",
                cache_system_prompt=cache_system_prompt,
            )

            # Get provider configuration
            config = self._provider_utils.get_provider_config(provider)

            # Override model, temperature, and max_tokens if provided
            max_tokens = kwargs.pop("max_tokens", None)
            if model or temperature is not None or max_tokens is not None:
                config = config.copy()
                if model:
                    config["model"] = model
                if temperature is not None:
                    config["temperature"] = temperature
                if max_tokens == 0:
                    # 0 means "no limit" — suppress any provider-level default
                    config.pop("max_tokens", None)
                elif max_tokens is not None:
                    config["max_tokens"] = max_tokens

            # Get or create LangChain client
            client = self._client_factory.get_or_create_client(provider, config)

            # Inject provider-specific cache metadata (E05-F05).
            # Placed after provider resolution and before LangChain conversion
            # so the correct resolved provider drives injection (Decision 2).
            messages = self._message_utils.inject_cache_metadata(
                messages, provider, cache_system_prompt
            )

            # Convert messages to LangChain format
            langchain_messages = self._message_utils.convert_messages_to_langchain(
                messages
            )

            # Make the call with resilience (retry + circuit breaker)
            current_model = config.get("model", "unknown")
            return self._invoke_with_resilience(
                client, langchain_messages, provider, current_model
            )

        except Exception as e:
            # Classify the error
            typed_error = classify_llm_error(e, provider)

            # Dependency and config errors should NOT trigger fallback
            if isinstance(typed_error, (LLMDependencyError, LLMConfigurationError)):
                raise typed_error

            # For provider errors, try fallback if services available
            if self.features_registry and self.routing_config:
                try:
                    current_model = model or config.get("model", "unknown")
                    return self._fallback_handler.try_with_fallback(
                        provider,
                        current_model,
                        original_messages,
                        typed_error,
                        self._provider_utils.get_provider_config,
                        self._client_factory.get_or_create_client,
                        self._message_utils.convert_messages_to_langchain,
                        **kwargs,
                    )
                except LLMServiceError:
                    # Fallback exhausted, raise original typed error
                    pass

            raise typed_error

    async def _call_llm_async_with_routing(
        self,
        messages: List[LLMMessage],
        routing_context: Dict[str, Any],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """Async sibling of ``_call_llm_with_routing`` preserving routing rules.

        Delegates to ``_call_llm_async_direct`` which returns ``LLMResponse``
        carrying the resolved provider, model, and usage from the raw response.
        """
        if not self.routing_service:
            raise LLMServiceError("Routing requested but no routing service available")

        # Narrow try to routing decision only — _call_llm_async_direct errors must
        # propagate as-is; the broad except was re-labeling downstream errors as
        # routing failures and silently swapping to fallback_provider.
        try:
            context = self._create_routing_context(routing_context, messages)
            available_providers = self._provider_utils.get_available_providers()

            if not available_providers:
                raise LLMServiceError("No providers configured")

            prompt = self._message_utils.extract_prompt_from_messages(messages)
            decision = self.routing_service.route_request(
                prompt=prompt,
                task_type=context.task_type,
                available_providers=available_providers,
                routing_context=context,
            )

            self._logger.info(
                f"Routing decision: {decision.provider}:{decision.model} "
                f"(complexity: {decision.complexity}, "
                f"confidence: {decision.confidence:.2f})"
            )

            self._record_routing_attributes(decision)

            node_max_tokens = routing_context.get("max_tokens")
            if node_max_tokens is None:
                node_max_tokens = kwargs.pop("max_tokens", None)

            resolved_max_tokens = (
                node_max_tokens if node_max_tokens is not None else decision.max_tokens
            )
            if resolved_max_tokens == 0:
                self._logger.debug(
                    "max_tokens=0 resolved to no limit (provider default)"
                )
                kwargs["max_tokens"] = 0
                resolved_max_tokens = None
            elif resolved_max_tokens is not None:
                source = (
                    "node context" if node_max_tokens is not None else "activity config"
                )
                self._logger.debug(
                    f"max_tokens={resolved_max_tokens} (source: {source})"
                )
                kwargs["max_tokens"] = resolved_max_tokens

            if resolved_max_tokens is not None:
                self._set_current_span_attributes(
                    {GEN_AI_REQUEST_MAX_TOKENS: resolved_max_tokens}
                )

            return await self._call_llm_async_direct(
                provider=decision.provider,
                messages=messages,
                model=decision.model,
                temperature=temperature,
                routing_context=routing_context,
                **kwargs,
            )

        except LLMResolvedCallError:
            # Post-selection provider failure — routing already resolved a concrete
            # (provider, model) before the call failed. Preserve that identity
            # intact; do NOT trigger the routing-fallback retry path, which would
            # silently rewrite the resolved identity with the fallback provider.
            # Mirrors the identical guard in _call_llm_async_direct:842.
            raise
        except LLMServiceError:
            raise
        except Exception as e:
            self._logger.error(f"Routing failed: {e}")
            fallback_provider = routing_context.get("fallback_provider", "anthropic")
            self._logger.warning(
                f"Falling back to {fallback_provider} due to pre-selection routing failure"
            )
            self._record_fallback_metric("routing_fallback")
            fallback_max_tokens = routing_context.get("max_tokens")
            if fallback_max_tokens is not None and "max_tokens" not in kwargs:
                kwargs["max_tokens"] = fallback_max_tokens
            return await self._call_llm_async_direct(
                provider=fallback_provider,
                messages=messages,
                model=model,
                temperature=temperature,
                routing_context=routing_context,
                **kwargs,
            )

    async def _call_llm_async_direct(
        self,
        provider: str,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Async direct provider invocation with resilience and fallback parity.

        Args:
            routing_context: Optional routing context forwarded from the routing
                             path so that ``requires_prompt_caching`` flags
                             carried there are honoured even when messages contain
                             no embedded ``cache_control`` blocks.

        Returns ``LLMResponse`` carrying the resolved provider, model, and usage
        extracted from the raw provider response.
        """
        current_model: str = "unknown"
        original_messages = messages
        try:
            # Extract cache_system_prompt before forwarding kwargs to the provider.
            # Mirrors the sync path (_call_llm_direct) for NFR-F-002 parity.
            cache_system_prompt: bool = kwargs.pop("cache_system_prompt", False)

            provider = self._provider_utils.normalize_provider(provider)
            self._validate_prompt_caching_support(
                provider,
                messages,
                routing_context,
                execution_path="call_llm_async",
                cache_system_prompt=cache_system_prompt,
            )
            config = self._provider_utils.get_provider_config(provider)

            max_tokens = kwargs.pop("max_tokens", None)
            if model or temperature is not None or max_tokens is not None:
                config = config.copy()
                if model:
                    config["model"] = model
                if temperature is not None:
                    config["temperature"] = temperature
                if max_tokens == 0:
                    config.pop("max_tokens", None)
                elif max_tokens is not None:
                    config["max_tokens"] = max_tokens

            current_model = config.get("model", "unknown")
            client = self._client_factory.get_or_create_client(provider, config)

            # Inject provider-specific cache metadata (E05-F05).
            # Placed after provider resolution and before LangChain conversion
            # so the correct resolved provider drives injection (Decision 2).
            messages = self._message_utils.inject_cache_metadata(
                messages, provider, cache_system_prompt
            )

            langchain_messages = self._message_utils.convert_messages_to_langchain(
                messages
            )
            return await self._invoke_with_resilience_async(
                client, langchain_messages, provider, current_model
            )
        except LLMResolvedCallError:
            # Already wrapped by the fallback handler — preserve its tier identity.
            raise
        except Exception as e:
            typed_error = classify_llm_error(e, provider)

            if isinstance(typed_error, (LLMDependencyError, LLMConfigurationError)):
                raise LLMResolvedCallError(
                    provider, current_model, typed_error
                ) from typed_error

            if self.features_registry and self.routing_config:
                try:
                    return await self._fallback_handler.try_with_fallback_async(
                        provider,
                        current_model,
                        original_messages,
                        typed_error,
                        self._provider_utils.get_provider_config,
                        self._client_factory.get_or_create_client,
                        self._message_utils.convert_messages_to_langchain,
                        **kwargs,
                    )
                except LLMResolvedCallError:
                    # Fallback handler already wrapped the error with tier identity.
                    raise
                except LLMServiceError as fallback_err:
                    # Tier exhaustion without LLMResolvedCallError — wrap with
                    # the original provider/model (the last known resolved identity).
                    raise LLMResolvedCallError(
                        provider, current_model, fallback_err
                    ) from fallback_err

            raise LLMResolvedCallError(
                provider, current_model, typed_error
            ) from typed_error

    def _invoke_with_resilience(
        self,
        client: Any,
        langchain_messages: List[Any],
        provider: str,
        model: str,
    ) -> str:
        """
        Invoke an LLM client with retry + circuit breaker protection.

        Args:
            client: LangChain chat model client.
            langchain_messages: Pre-converted LangChain message list.
            provider: Provider name (for circuit breaker keying).
            model: Model name (for circuit breaker keying).

        Returns:
            Response text string.

        Raises:
            LLMProviderError (or subclass): After retries exhausted or
                circuit open or non-retryable error.
        """
        # Record circuit breaker state on current span (E02-F03)
        self._record_circuit_breaker_state(provider, model)

        # Circuit breaker check
        if self._circuit_breaker.is_open(provider, model):
            raise LLMProviderError(
                f"Circuit breaker open for {provider}:{model} -- "
                f"skipping call (resets after "
                f"{self._circuit_breaker.reset}s)"
            )

        retry_cfg = self._resilience_config.get("retry", {})
        max_attempts = retry_cfg.get("max_attempts", 3)
        backoff_base = retry_cfg.get("backoff_base", 2.0)
        backoff_max = retry_cfg.get("backoff_max", 30.0)
        jitter = retry_cfg.get("jitter", True)

        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                self._logger.debug(
                    f"LLM call to {provider}:{model} "
                    f"(attempt {attempt}/{max_attempts})"
                )
                start_time = time.monotonic()
                response = client.invoke(langchain_messages)
                duration = time.monotonic() - start_time

                # Extract content
                result = (
                    response.content if hasattr(response, "content") else str(response)
                )

                # Track circuit breaker close transition (was open -> now success)
                was_open = self._circuit_breaker.is_open(provider, model)
                self._circuit_breaker.record_success(provider, model)
                self._record_circuit_breaker_metric_on_close(was_open, provider, model)

                # Record duration metric
                self._record_duration_metric(duration, provider, model)

                # Record token counts, response model on span, and token metrics
                self._record_llm_response_attributes(response, provider, model)

                # Log request ID for debugging
                resp_meta = getattr(response, "response_metadata", None)
                req_id = (
                    self._extract_provider_request_id(resp_meta, provider)
                    if isinstance(resp_meta, dict)
                    else None
                )
                self._logger.debug(
                    f"LLM call successful, response length: {len(result)}"
                    + (f", request_id: {req_id}" if req_id else "")
                )
                return result

            except Exception as e:
                typed_error = classify_llm_error(e, provider)
                last_error = typed_error

                # Non-retryable -> fail immediately
                if not is_retryable(typed_error):
                    self._circuit_breaker.record_failure(provider, model)
                    self._record_error_metric(typed_error, provider, model)
                    self._record_circuit_breaker_metric_on_open(provider, model)
                    raise typed_error

                # Last attempt -> no more retries
                if attempt == max_attempts:
                    break

                # Exponential backoff with optional jitter
                delay = min(backoff_base ** (attempt - 1), backoff_max)
                if jitter:
                    delay = delay * (0.5 + random.random())

                self._logger.warning(
                    f"Retryable error on {provider}:{model} "
                    f"(attempt {attempt}/{max_attempts}): {typed_error}. "
                    f"Retrying in {delay:.1f}s"
                )
                time.sleep(delay)

        # All retries exhausted
        self._circuit_breaker.record_failure(provider, model)
        self._record_error_metric(last_error, provider, model)
        self._record_circuit_breaker_metric_on_open(provider, model)
        raise last_error  # type: ignore[misc]

    async def _invoke_with_resilience_async(
        self,
        client: Any,
        langchain_messages: List[Any],
        provider: str,
        model: str,
    ) -> LLMResponse:
        """Single async resilience seam: retry + circuit breaker + response wrapping.

        Returns ``LLMResponse`` carrying the resolved ``provider``, ``model``,
        response text, and normalized ``LLMUsage`` extracted from the raw response.
        This is the **only** async resilience stack — the fan-out path and the
        public ``call_llm_async`` both funnel through here.
        """
        self._record_circuit_breaker_state(provider, model)

        if self._circuit_breaker.is_open(provider, model):
            raise LLMProviderError(
                f"Circuit breaker open for {provider}:{model} -- "
                f"skipping call (resets after "
                f"{self._circuit_breaker.reset}s)"
            )

        retry_cfg = self._resilience_config.get("retry", {})
        max_attempts = retry_cfg.get("max_attempts", 3)
        backoff_base = retry_cfg.get("backoff_base", 2.0)
        backoff_max = retry_cfg.get("backoff_max", 30.0)
        jitter = retry_cfg.get("jitter", True)

        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                self._logger.debug(
                    f"LLM call to {provider}:{model} "
                    f"(attempt {attempt}/{max_attempts})"
                )
                start_time = time.monotonic()
                response = await self._invoke_provider_async(client, langchain_messages)
                duration = time.monotonic() - start_time

                text = (
                    response.content if hasattr(response, "content") else str(response)
                )

                was_open = self._circuit_breaker.is_open(provider, model)
                self._circuit_breaker.record_success(provider, model)
                self._record_circuit_breaker_metric_on_close(was_open, provider, model)
                self._record_duration_metric(duration, provider, model)
                self._record_llm_response_attributes(response, provider, model)

                resp_meta = getattr(response, "response_metadata", None)
                req_id = (
                    self._extract_provider_request_id(resp_meta, provider)
                    if isinstance(resp_meta, dict)
                    else None
                )
                self._logger.debug(
                    f"LLM call successful, response length: {len(text)}"
                    + (f", request_id: {req_id}" if req_id else "")
                )
                return LLMResponse(
                    text=text,
                    resolved_provider=provider,
                    resolved_model=model,
                    usage=self._extract_llm_usage(response),
                    finish_reason=self._extract_finish_reason(response),
                )
            except Exception as e:
                typed_error = classify_llm_error(e, provider)
                last_error = typed_error

                if not is_retryable(typed_error):
                    self._circuit_breaker.record_failure(provider, model)
                    self._record_error_metric(typed_error, provider, model)
                    self._record_circuit_breaker_metric_on_open(provider, model)
                    raise typed_error

                if attempt == max_attempts:
                    break

                delay = min(backoff_base ** (attempt - 1), backoff_max)
                if jitter:
                    delay = delay * (0.5 + random.random())

                self._logger.warning(
                    f"Retryable error on {provider}:{model} "
                    f"(attempt {attempt}/{max_attempts}): {typed_error}. "
                    f"Retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)

        self._circuit_breaker.record_failure(provider, model)
        self._record_error_metric(last_error, provider, model)
        self._record_circuit_breaker_metric_on_open(provider, model)
        raise last_error  # type: ignore[misc]

    async def _invoke_provider_async(
        self, client: Any, langchain_messages: List[Any]
    ) -> Any:
        """Invoke the provider client with native async or worker-thread fallback."""
        async_invoke = getattr(client, "ainvoke", None)
        if callable(async_invoke):
            response = async_invoke(langchain_messages)
            if inspect.isawaitable(response):
                return await response
            return response
        return await asyncio.to_thread(client.invoke, langchain_messages)

    # ------------------------------------------------------------------
    # Routing telemetry helpers (error-isolated, silent no-op when disabled)
    # ------------------------------------------------------------------

    def _record_routing_attributes(self, decision: Any) -> None:
        """Record routing decision attributes on the current LLM span."""
        if self._telemetry_service is None:
            return
        try:
            attributes: Dict[str, Any] = {
                ROUTING_COMPLEXITY: str(decision.complexity),
                ROUTING_CONFIDENCE: decision.confidence,
                ROUTING_PROVIDER: decision.provider,
                ROUTING_MODEL: decision.model,
                ROUTING_CACHE_HIT: decision.cache_hit,
                GEN_AI_SYSTEM: decision.provider,
                GEN_AI_REQUEST_MODEL: decision.model,
            }
            if decision.fallback_used:
                attributes[ROUTING_FALLBACK_TIER] = "fallback"
            self._set_current_span_attributes(attributes)

            if decision.cache_hit and self._metric_cache_hit is not None:
                try:
                    self._metric_cache_hit.add(1)
                except Exception:
                    pass
        except Exception:
            pass

    def _record_circuit_breaker_state(self, provider: str, model: str) -> None:
        """Record circuit breaker state on the current span."""
        if self._telemetry_service is None:
            return
        try:
            state = (
                "open" if self._circuit_breaker.is_open(provider, model) else "closed"
            )
            self._set_current_span_attributes({ROUTING_CIRCUIT_BREAKER_STATE: state})
        except Exception:
            pass

    def _create_routing_context(
        self, routing_context: Dict[str, Any], messages: List[LLMMessage]
    ) -> RoutingContext:
        """
        Convert routing context dictionary to RoutingContext object.

        Args:
            routing_context: Dictionary containing routing parameters
            messages: List of messages for context analysis

        Returns:
            RoutingContext object
        """
        # Extract prompt for complexity analysis
        prompt = self._message_utils.extract_prompt_from_messages(messages)

        return RoutingContext(
            task_type=routing_context.get("task_type", "general"),
            routing_enabled=routing_context.get("routing_enabled", True),
            activity=routing_context.get("activity"),
            complexity_override=routing_context.get("complexity_override"),
            auto_detect_complexity=routing_context.get("auto_detect_complexity", True),
            provider_preference=routing_context.get("provider_preference", []),
            excluded_providers=routing_context.get("excluded_providers", []),
            model_override=routing_context.get("model_override"),
            max_cost_tier=routing_context.get("max_cost_tier"),
            prompt=prompt,
            input_context=routing_context.get("input_context", {}),
            memory_size=len(messages) - 1 if messages else 0,
            input_field_count=routing_context.get("input_field_count", 1),
            cost_optimization=routing_context.get("cost_optimization", True),
            prefer_speed=routing_context.get("prefer_speed", False),
            prefer_quality=routing_context.get("prefer_quality", False),
            fallback_provider=routing_context.get("fallback_provider"),
            fallback_model=routing_context.get("fallback_model"),
            retry_with_lower_complexity=routing_context.get(
                "retry_with_lower_complexity", True
            ),
            max_tokens=routing_context.get("max_tokens"),
            requires_prompt_caching=(
                routing_context.get("requires_prompt_caching", False)
                or LLMMessageService.has_prompt_caching(messages)
            ),
            requires_vision=routing_context.get("requires_vision", False),
        )

    def clear_cache(self) -> None:
        """Clear the client cache."""
        self._client_factory.clear_cache()
        self._logger.debug("[LLMService] Client cache cleared")

    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing service statistics if available.

        Returns:
            Dictionary containing routing statistics, circuit breaker state,
            or empty dict if no routing service.
        """
        stats: Dict[str, Any] = {}
        if self.routing_service:
            stats.update(self.routing_service.get_routing_stats())

        # Append circuit breaker state
        cb = self._circuit_breaker
        stats["circuit_breaker"] = {
            "open_circuits": list(cb.opened_at.keys()),
            "failure_counts": dict(cb.failures),
        }
        return stats

    def is_routing_enabled(self) -> bool:
        """
        Check if routing is enabled for this service.

        Returns:
            True if routing service is available
        """
        return self._routing_enabled

    # ------------------------------------------------------------------
    # Vision / multimodal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_image(
        image: Union[str, bytes], image_type: str = "image/png"
    ) -> Tuple[bytes, str]:
        """Resolve an image input to (bytes, mime_type).

        Args:
            image: File path (str) or raw image bytes.
            image_type: MIME type to use when *image* is bytes.

        Returns:
            Tuple of (image_bytes, mime_type).

        Raises:
            LLMServiceError: If the file path does not exist or cannot be read.

        Note:
            In distributed or containerized environments the service may not
            share the caller's filesystem.  Prefer passing *image* as ``bytes``
            and let the caller handle file I/O.
        """
        if isinstance(image, bytes):
            return image, image_type

        # Treat as a file path — open directly (EAFP) instead of pre-checking
        mime, _ = mimetypes.guess_type(image)
        if mime is None:
            mime = image_type  # fall back to caller-provided default

        try:
            with open(image, "rb") as fh:
                return fh.read(), mime
        except FileNotFoundError:
            raise LLMServiceError(f"Image file not found: {image}")
        except OSError as exc:
            raise LLMServiceError(f"Cannot read image file: {image}") from exc

    def ask_vision(
        self,
        prompt: str,
        image: Union[str, bytes],
        image_type: str = "image/png",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """Ask the LLM a question about an image.

        Convenience wrapper around ``call_llm()`` that constructs the
        multimodal messages list expected by LangChain chat models.

        This method is **synchronous**, consistent with the rest of
        ``LLMService`` (``ask()``, ``call_llm()``, etc.).  Converting to
        async would require migrating the entire call chain; see the
        WormwoodGM spec PR (#143) for discussion.

        Args:
            prompt: Text prompt describing what to analyze.
            image: Image as a file path (str) or raw bytes.  In distributed
                or containerized environments, prefer passing ``bytes`` — the
                service may not share the caller's filesystem.
            image_type: MIME type when *image* is bytes (default ``image/png``).
            provider: Optional provider name (defaults to ``'anthropic'``).
            model: Optional model override.
            temperature: Optional temperature override.
            routing_context: Optional routing context for intelligent routing.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLM response as string.  Per-call token usage (input/output
            counts) is recorded on the active OpenTelemetry span as
            ``gen_ai.usage.input_tokens`` and ``gen_ai.usage.output_tokens``
            and emitted as OTel counter metrics — use your telemetry backend
            for cost tracking rather than the return value.
        """
        # Extract cache_system_prompt early so the validation fires before any
        # image decoding or client creation (TC-015 contract: error before image
        # resolution). This must be popped from kwargs before forwarding.
        cache_system_prompt: bool = kwargs.pop("cache_system_prompt", False)

        # Validate BEFORE image resolution so the error fires as early as possible.
        self._validate_prompt_caching_support(
            provider,
            [],
            routing_context,
            execution_path="ask_vision",
            cache_system_prompt=cache_system_prompt,
        )

        image_bytes, mime = self._resolve_image(image, image_type)
        b64 = base64.b64encode(image_bytes).decode("ascii")

        messages: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        if routing_context is not None:
            routing_context = dict(routing_context)  # copy to avoid mutation
            routing_context["requires_vision"] = True

        # Default provider when routing is not active (mirrors ask() behavior)
        if provider is None and routing_context is None:
            provider = "anthropic"

        return self.call_llm(
            messages=messages,
            provider=provider,
            model=model,
            temperature=temperature,
            routing_context=routing_context,
            **kwargs,
        )

    async def ask_vision_async(
        self,
        prompt: str,
        image: Union[str, bytes],
        image_type: str = "image/png",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        cache_prompt: bool = False,
        **kwargs,
    ) -> LLMResponse:
        """Async vision call returning a rich ``LLMResponse``.

        Async counterpart of :meth:`ask_vision`. Constructs the multimodal
        messages list and routes through :meth:`call_llm_async`, so it inherits
        intelligent routing, tiered provider fallback, resilience (retry +
        circuit breaker), and prompt caching — and returns the full
        ``LLMResponse`` (``.text``, ``.resolved_provider``, ``.resolved_model``,
        ``.usage``, ``.finish_reason``) rather than a bare string. Callers that
        need per-call token usage or truncation detection should use this method
        instead of the string-returning :meth:`ask_vision`.

        Prompt caching: vision messages are a single user turn (image + text),
        so the agnostic ``cache_system_prompt`` (which only marks *system*
        messages) does not apply. Instead, ``cache_prompt=True`` attaches an
        Anthropic ``cache_control`` block to the prompt text block (manual
        passthrough) and sets ``routing_context["requires_prompt_caching"]`` so
        routing selects a cache-capable provider (and excludes providers whose
        ``routing.provider_capabilities.<p>.prompt_caching`` is false). For long,
        static extraction/OCR prompts this caches the prompt's input tokens
        across calls — a substantial cost saving. The capability gate is enforced
        downstream against the *resolved* provider, so no pre-validation here.

        Args:
            prompt: Text prompt describing what to analyze.
            image: Image as a file path (str) or raw bytes. Prefer ``bytes`` in
                distributed/containerized environments.
            image_type: MIME type when *image* is bytes (default ``image/png``).
            provider: Optional provider name (defaults to ``'anthropic'`` only
                when routing is not active).
            model: Optional model override (ignored when routing_context is set).
            temperature: Optional temperature override.
            routing_context: Optional routing context for intelligent routing.
                ``requires_vision=True`` is injected automatically; when
                ``cache_prompt`` is set, ``requires_prompt_caching=True`` is too.
            cache_prompt: When True, mark the prompt text block with
                ``cache_control`` and request cache-aware routing.
            **kwargs: Additional provider-specific parameters (e.g. ``max_tokens``).

        Returns:
            ``LLMResponse`` from the provider that actually handled the request.
        """
        image_bytes, mime = self._resolve_image(image, image_type)
        b64 = base64.b64encode(image_bytes).decode("ascii")

        text_block: Dict[str, Any] = {"type": "text", "text": prompt}
        if cache_prompt:
            text_block["cache_control"] = {"type": "ephemeral"}

        messages: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    text_block,
                ],
            }
        ]

        # Inject vision/caching routing signals on a copy (never mutate caller's).
        if routing_context is not None or cache_prompt:
            routing_context = dict(routing_context or {})
            routing_context["requires_vision"] = True
            if cache_prompt:
                routing_context["requires_prompt_caching"] = True

        # Default provider only when routing is not active (mirrors ask_vision).
        if provider is None and routing_context is None:
            provider = "anthropic"

        return await self.call_llm_async(
            messages=messages,
            provider=provider,
            model=model,
            temperature=temperature,
            routing_context=routing_context,
            **kwargs,
        )

    def ask(self, prompt: str, provider: Optional[str] = None, **kwargs) -> str:
        """
        Ask the LLM a single plain-string question.

        Convenience wrapper around call_llm() for simple single-turn prompts
        that don't require constructing a messages list.

        Args:
            prompt: The prompt text to send
            provider: Optional provider name (defaults to 'anthropic')
            **kwargs: Additional LLM parameters (e.g. temperature, model)

        Returns:
            Response text string
        """
        provider = provider or "anthropic"
        messages = [{"role": "user", "content": prompt}]
        return self.call_llm(provider=provider, messages=messages, **kwargs)

    async def ask_async(
        self, prompt: str, provider: Optional[str] = None, **kwargs
    ) -> str:
        """Async convenience wrapper mirroring ``ask()`` behavior."""
        provider = provider or "anthropic"
        messages = [{"role": "user", "content": prompt}]
        response = await self.call_llm_async(
            provider=provider, messages=messages, **kwargs
        )
        return response.text

    async def call_llm_many_async(
        self,
        requests: List[LLMRequest],
        max_concurrency: int,
    ) -> List[LLMFanoutResult]:
        """
        Submit many LLM call specs and receive one terminal result per spec.

        Validates the submission before any provider execution:
        - ``requests`` must not be empty.
        - ``request_id`` values must be unique within one submission.
        - ``max_concurrency`` must be an integer >= 1.

        Once execution starts, item failures are captured as ``LLMFanoutResult``
        records with ``status="failed"`` rather than aborting the submission.
        The returned list preserves the same positional order as ``requests``.
        """
        self._validate_fan_out_submission(requests, max_concurrency)

        semaphore = asyncio.Semaphore(max_concurrency)
        tasks = [
            asyncio.ensure_future(self._execute_fan_out_item(spec, semaphore))
            for spec in requests
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)

    def _validate_fan_out_submission(
        self,
        requests: List[LLMRequest],
        max_concurrency: int,
    ) -> None:
        """Validate a fan-out submission before any provider execution begins."""
        if not requests:
            raise LLMServiceError(
                "requests must not be empty — at least one LLMRequest is required."
            )
        # Reject bool explicitly: isinstance(True, int) is True in Python.
        if (
            isinstance(max_concurrency, bool)
            or not isinstance(max_concurrency, int)
            or max_concurrency < 1
        ):
            raise LLMServiceError(
                f"max_concurrency must be an integer >= 1, got {max_concurrency!r}."
            )
        seen_ids: set = set()
        for spec in requests:
            if not isinstance(spec.request_id, str) or not spec.request_id:
                raise LLMServiceError(
                    f"request_id must be a non-empty string, got {spec.request_id!r}."
                )
            if spec.request_id in seen_ids:
                raise LLMServiceError(
                    f"Duplicate request_id detected: {spec.request_id!r}. "
                    "Each request_id must be unique within one submission."
                )
            seen_ids.add(spec.request_id)
            if spec.request_options:
                collision = _RESERVED_KEYS & spec.request_options.keys()
                if collision:
                    raise LLMServiceError(
                        f"request_id={spec.request_id!r}: request_options contains reserved "
                        f"keys that collide with call_llm_async parameters: {collision}"
                    )

    async def _execute_fan_out_item(
        self,
        spec: LLMRequest,
        semaphore: asyncio.Semaphore,
    ) -> LLMFanoutResult:
        """Execute one fan-out item through the public ``call_llm_async`` path.

        Calls ``call_llm_async`` directly so that routing, retry, jitter,
        circuit-breaker, fallback, telemetry, and cache-aware behavior are all
        inherited from the single async resilience stack (spec Decision 3).
        Builds ``LLMFanoutResult`` from the returned ``LLMResponse`` so that
        ``provider``, ``model``, and ``usage`` reflect the resolved values, not
        the requested spec values.
        """
        async with semaphore:
            kwargs = dict(spec.request_options)
            try:
                llm_response = await self.call_llm_async(
                    messages=spec.messages,
                    provider=spec.provider,
                    model=spec.model,
                    temperature=spec.temperature,
                    routing_context=spec.routing_context,
                    cache_system_prompt=spec.cache_system_prompt,
                    **kwargs,
                )
                return LLMFanoutResult(
                    request_id=spec.request_id,
                    status="succeeded",
                    resolved_provider=llm_response.resolved_provider,
                    resolved_model=llm_response.resolved_model,
                    text=llm_response.text,
                    usage=llm_response.usage,
                )
            except LLMResolvedCallError as exc:
                # Failure occurred after routing/fallback resolved a concrete
                # provider/model — preserve that identity in the result record.
                return LLMFanoutResult(
                    request_id=spec.request_id,
                    status="failed",
                    resolved_provider=exc.resolved_provider,
                    resolved_model=exc.resolved_model,
                    text=None,
                    usage=None,
                    error=LLMExecutionError(
                        error_type=type(exc.cause).__name__,
                        message=_sanitize_error_message(exc.cause),
                        retryable=is_retryable(exc.cause),
                    ),
                )
            except Exception as exc:
                # Failure occurred before any provider/model was resolved
                # (e.g., validation error, routing service unavailable).
                # Echo spec values — may be None. Do not fabricate.
                return LLMFanoutResult(
                    request_id=spec.request_id,
                    status="failed",
                    resolved_provider=spec.provider,
                    resolved_model=spec.model,
                    text=None,
                    usage=None,
                    error=LLMExecutionError(
                        error_type=type(exc).__name__,
                        message=_sanitize_error_message(exc),
                        retryable=is_retryable(exc),
                    ),
                )

    # ------------------------------------------------------------------
    # Batch lifecycle methods (E05-F04 registry-based dispatch)
    # ------------------------------------------------------------------

    # Terminal statuses where cancel is not permitted.
    _TERMINAL_STATUSES = {
        LLMBatchStatus.ENDED,
        LLMBatchStatus.EXPIRED,
        LLMBatchStatus.FAILED,
        LLMBatchStatus.CANCELED,
        LLMBatchStatus.CANCELING,
    }

    def _get_adapter(self, provider: str) -> Any:
        """Return the registered adapter for ``provider`` or raise.

        Provider aliases (e.g. "gemini" → "google", "claude" → "anthropic",
        "gpt" → "openai") are normalized via the same
        ``_provider_utils.normalize_provider`` function used by every other
        LLMService path (N5 / AC-2 / AC-3 contract parity).

        Raises:
            LLMBatchUnsupportedProviderError: When no adapter is registered for
                the requested provider.  The error message names the registered
                providers so callers can discover what is available.
        """
        provider = self._provider_utils.normalize_provider(provider)
        adapter = self._batch_adapters.get(provider)
        if adapter is None:
            registered = list(self._batch_adapters.keys())
            self._logger.error(
                "llm_batch.unsupported_provider provider=%s registered=%s",
                provider,
                registered,
            )
            raise LLMBatchUnsupportedProviderError(
                f"Provider {provider!r} is not registered for batch execution. "
                f"Registered providers: {registered}."
            )
        return adapter

    # Pattern that a valid agentmap_batch_id must satisfy (no path separators).
    _AGENTMAP_BATCH_ID_RE = re.compile(r"^amatch_[a-f0-9]{32}$")

    def _validate_batch_submit_request(
        self, request: LLMBatchSubmitRequest
    ) -> List[Dict[str, Any]]:
        """
        Validate a batch submit request and build the per-spec resolved param
        dicts.  Returns the resolved params list (index-aligned with
        ``request.requests``) so ``submit_batch`` can pass it straight to the
        adapter without re-computing.

        Validation order:
        1. Non-empty requests
        2. Per-spec provider not set (batch-level only — REQ-F-008)
        3. Unique request_ids
        4. Centralized parameter resolution (D-8) — covers all conflict/
           incompatible/max_tokens==0 checks via ``resolve_request_params``
        5. Batch-level max_tokens != 0 (envelope guard)
        6. Registered provider check (raises LLMBatchUnsupportedProviderError)

        Raises:
            LLMServiceError: For validation failures (empty specs, duplicate
                ids, per-spec provider, batch-incompatible params, max_tokens==0,
                conflicting parameter values).
            LLMBatchParamConflictError: When the same logical parameter is set
                on two surfaces with different values (AC-8 / D-8).
            LLMBatchUnsupportedProviderError: For unregistered providers.
        """
        from agentmap.services.llm._param_resolution import build_resolved_params_list

        if not request.requests:
            raise LLMServiceError(
                "requests must not be empty — at least one LLMRequest is required "
                "for batch submission."
            )

        if not isinstance(request.model, str) or not request.model:
            raise LLMServiceError(
                f"model must be a non-empty string, got {request.model!r}."
            )

        # REQ-F-008: provider is batch-level only; reject per-spec provider settings.
        for spec in request.requests:
            if spec.provider is not None and spec.provider != "":
                raise LLMServiceError(
                    f"request_id={spec.request_id!r}: LLMRequest.provider must not be set "
                    "when LLMBatchSubmitRequest.provider is specified. Provider is a "
                    "batch-level concern only (one batch = one adapter)."
                )

        seen_ids: set = set()
        for spec in request.requests:
            if not isinstance(spec.request_id, str) or not spec.request_id:
                raise LLMServiceError(
                    f"request_id must be a non-empty string, got {spec.request_id!r}."
                )
            if spec.request_id in seen_ids:
                raise LLMServiceError(
                    f"Duplicate request_id detected: {spec.request_id!r}. "
                    "Each request_id must be unique within one batch submission."
                )
            seen_ids.add(spec.request_id)

        # D-8: centralized parameter resolution — raises LLMBatchParamConflictError
        # or LLMServiceError for any conflict, incompatible param, or max_tokens==0.
        resolved = build_resolved_params_list(request)

        # Envelope-level max_tokens guard (catches request.max_tokens == 0 before
        # resolution would see it as S3; belt-and-suspenders).
        if request.max_tokens == 0:
            raise LLMServiceError(
                "max_tokens=0 is not supported in batch submissions. "
                "Cache pre-warm (max_tokens=0) is incompatible with batch mode."
            )

        # REQ-F-002: registry-based provider check (raises LLMBatchUnsupportedProviderError).
        self._get_adapter(request.provider)

        return resolved

    def submit_batch(self, request: LLMBatchSubmitRequest) -> LLMBatchHandle:
        """
        Submit a provider-native batch and return a serializable handle.

        Validation order: non-empty specs → unique request_ids → batch-incompatible
        params → registered provider check → max_tokens != 0 → adapter call →
        build handle → persist → return.

        Raises:
            LLMServiceError: For validation failures.
            LLMBatchUnsupportedProviderError: For unsupported providers.
        """
        # _validate_batch_submit_request returns the per-spec resolved param dicts
        # (D-8: centralized resolver, no adapter merging).
        resolved_params = self._validate_batch_submit_request(request)

        # N5: normalize provider alias to canonical key (same function used by
        # sync/async direct paths) so the handle stores the canonical provider name
        # and downstream lookups (poll/fetch/cancel) succeed without re-normalizing.
        canonical_provider = self._provider_utils.normalize_provider(request.provider)
        adapter = self._get_adapter(canonical_provider)
        self._logger.info(
            "llm_batch.submit provider=%s specs=%d",
            canonical_provider,
            len(request.requests),
        )
        provider_batch_id, request_id_map, expires_at = adapter.submit(
            specs=request.requests,
            resolved_params=resolved_params,
        )

        agentmap_batch_id = "amatch_" + uuid4().hex
        handle = LLMBatchHandle(
            agentmap_batch_id=agentmap_batch_id,
            provider_batch_id=provider_batch_id,
            status=LLMBatchStatus.SUBMITTED,
            provider=canonical_provider,
            model=request.model,
            request_id_map=request_id_map,
            expires_at=expires_at,
        )

        if self._batch_repo is not None:
            self._batch_repo.save(handle)
            self._logger.info(
                "llm_batch.handle_saved agentmap_batch_id=%s path=%s",
                agentmap_batch_id,
                getattr(self._batch_repo, "_batch_dir", "<unknown>"),
            )

        self._record_batch_submit_metric(
            provider=canonical_provider,
            status=handle.status.value,
        )
        self._logger.info(
            "llm_batch.submitted agentmap_batch_id=%s provider_batch_id=%s spec_count=%d",
            agentmap_batch_id,
            provider_batch_id,
            len(request.requests),
        )
        return handle

    def restore_batch(self, handle_data: dict) -> LLMBatchHandle:
        """
        Restore a batch handle from a serialized dict.

        Validates that the dict contains the required ``provider_batch_id``
        field before constructing the handle.

        Raises:
            LLMServiceError: If ``provider_batch_id`` is absent.
        """
        if (
            "provider_batch_id" not in handle_data
            or not handle_data["provider_batch_id"]
        ):
            raise LLMServiceError(
                "Cannot restore batch handle: 'provider_batch_id' is missing or "
                "empty in the provided handle dict."
            )

        # Validate agentmap_batch_id format (F-HIGH-2): prevent path traversal.
        # The id must match ^amatch_[a-f0-9]{32}$ — no slashes, dots, or other
        # path components that could escape the batch directory.
        agentmap_batch_id = handle_data.get("agentmap_batch_id", "")
        if not self._AGENTMAP_BATCH_ID_RE.match(agentmap_batch_id):
            raise LLMServiceError(
                f"Cannot restore batch handle: agentmap_batch_id "
                f"{agentmap_batch_id!r} is invalid. Expected format: "
                "amatch_<32 hex chars> (e.g. amatch_0a1b...c2d3)."
            )

        try:
            return LLMBatchHandle.from_dict(handle_data)
        except (KeyError, ValueError) as exc:
            raise LLMServiceError(f"Cannot restore batch handle: {exc}") from exc

    def poll_batch(self, handle: LLMBatchHandle) -> LLMBatchHandle:
        """
        Poll the provider for current batch status and return an updated handle.

        Dispatches through the provider→adapter registry.  Adapters return an
        already-normalized ``LLMBatchStatus``; the service performs zero enum
        mapping (REQ-F-003).

        Raises:
            LLMBatchExpiredError: If the handle is already in EXPIRED status.
            LLMBatchUnsupportedProviderError: If handle.provider is not registered.
        """
        if handle.status == LLMBatchStatus.EXPIRED:
            self._logger.warning(
                "llm_batch.expired_operation handle_id=%s", handle.agentmap_batch_id
            )
            raise LLMBatchExpiredError(
                f"Batch {handle.agentmap_batch_id!r} has expired. "
                "Results are no longer available."
            )

        adapter = self._get_adapter(handle.provider)
        self._logger.info(
            "llm_batch.poll provider=%s status=%s",
            handle.provider,
            handle.status.value,
        )
        poll_result = adapter.poll(handle.provider_batch_id)

        updated = LLMBatchHandle(
            agentmap_batch_id=handle.agentmap_batch_id,
            provider_batch_id=handle.provider_batch_id,
            status=poll_result.status,
            provider=handle.provider,
            model=handle.model,
            request_id_map=handle.request_id_map,
            results_url=poll_result.results_url or handle.results_url,
            result_ref=poll_result.result_ref or handle.result_ref,
            expires_at=poll_result.expires_at or handle.expires_at,
            ended_at=poll_result.ended_at,
            request_counts=poll_result.request_counts,
        )

        if self._batch_repo is not None:
            self._batch_repo.save(updated)

        self._record_batch_poll_metric(
            provider=handle.provider,
            status=updated.status.value,
        )
        self._logger.info(
            "llm_batch.polled agentmap_batch_id=%s status=%s processing=%s succeeded=%s",
            handle.agentmap_batch_id,
            updated.status.value,
            updated.request_counts.processing if updated.request_counts else None,
            updated.request_counts.succeeded if updated.request_counts else None,
        )
        return updated

    def cancel_batch(self, handle: LLMBatchHandle) -> LLMBatchHandle:
        """
        Request cancellation of an active batch.

        Raises:
            LLMBatchCancelNotSupportedError: If the provider does not support
                cancel (REQ-F-009e — distinct message from terminal-state case).
            LLMBatchCancelNotSupportedError: If the handle is already in a
                terminal status (distinct message from provider-not-supported).
        """
        adapter = self._get_adapter(handle.provider)

        # F5 / REQ-F-009e: check terminal state FIRST so a terminal batch on any
        # provider (including one where supports_cancel=False) gets the more
        # accurate "terminal state" message rather than "provider does not support
        # cancel".  The two conditions are distinct and the batch state is the
        # more specific diagnosis when both would apply.
        if handle.status in self._TERMINAL_STATUSES:
            self._logger.warning(
                "llm_batch.cancel_rejected agentmap_batch_id=%s status=%s",
                handle.agentmap_batch_id,
                handle.status.value,
            )
            raise LLMBatchCancelNotSupportedError(
                f"Cannot cancel batch {handle.agentmap_batch_id!r}: "
                f"current status is {handle.status.value!r} (terminal state)."
            )

        # REQ-F-009e: provider capability check (after terminal check so terminal
        # state is always the more specific diagnosis).
        if not getattr(adapter, "supports_cancel", True):
            self._logger.warning(
                "llm_batch.cancel_not_supported provider=%s handle_id=%s",
                handle.provider,
                handle.agentmap_batch_id,
            )
            raise LLMBatchCancelNotSupportedError(
                f"Provider {handle.provider!r} does not support cancel. "
                f"Cannot cancel batch {handle.agentmap_batch_id!r}."
            )

        self._logger.info(
            "llm_batch.cancel_requested agentmap_batch_id=%s",
            handle.agentmap_batch_id,
        )
        self._record_batch_cancel_metric(
            provider=handle.provider,
            status=handle.status.value,
        )
        adapter.cancel(handle.provider_batch_id)
        return self.poll_batch(handle)

    def fetch_batch_results(self, handle: LLMBatchHandle) -> List[LLMBatchResult]:
        """
        Retrieve completed batch results keyed by caller ``request_id``.

        Delegates to the adapter which yields ``LLMBatchResult`` items
        with ``request_id`` already restored from the request_id_map.

        Raises:
            LLMBatchExpiredError: If the handle is in EXPIRED status.
            LLMBatchNotReadyError: If the handle status is not ``"ended"``.
        """
        if handle.status == LLMBatchStatus.EXPIRED:
            self._logger.warning(
                "llm_batch.expired_operation handle_id=%s", handle.agentmap_batch_id
            )
            raise LLMBatchExpiredError(
                f"Batch {handle.agentmap_batch_id!r} has expired. "
                "Results are no longer available."
            )

        if handle.status != LLMBatchStatus.ENDED:
            raise LLMBatchNotReadyError(
                f"Batch {handle.agentmap_batch_id!r} is not yet ready for result "
                f"retrieval (current status: {handle.status.value!r}). "
                "Poll until status == 'ended' before fetching results."
            )

        # Adapter-aware fetch readiness (spec §1.3 / D-7).
        # The universal results_url guard is intentionally removed here:
        #   - Anthropic: fetches by provider_batch_id (results_url is advisory)
        #   - OpenAI: requires result_ref (output_file_id), not results_url
        #   - Gemini inline: requires neither — re-retrieves the job object
        # Each adapter is authoritative over its own readiness check.
        adapter = self._get_adapter(handle.provider)
        records = list(
            adapter.fetch_results(
                handle.provider_batch_id,
                handle.request_id_map,
                result_ref=handle.result_ref,
            )
        )

        self._logger.info(
            "llm_batch.results_fetched agentmap_batch_id=%s item_count=%d",
            handle.agentmap_batch_id,
            len(records),
        )
        self._record_batch_results_fetched_metric(
            provider=handle.provider,
            status=handle.status.value,
        )
        return records

    # ------------------------------------------------------------------
    # Async surfaces (REQ-F-006) — wrap sync methods via asyncio.to_thread
    # ------------------------------------------------------------------

    async def asubmit_batch(self, request: "LLMBatchSubmitRequest") -> "LLMBatchHandle":
        """Async wrapper for :meth:`submit_batch` (runs off event-loop thread)."""
        return await asyncio.to_thread(self.submit_batch, request)

    async def apoll_batch(self, handle: "LLMBatchHandle") -> "LLMBatchHandle":
        """Async wrapper for :meth:`poll_batch` (runs off event-loop thread)."""
        return await asyncio.to_thread(self.poll_batch, handle)

    async def acancel_batch(self, handle: "LLMBatchHandle") -> "LLMBatchHandle":
        """Async wrapper for :meth:`cancel_batch` (runs off event-loop thread)."""
        return await asyncio.to_thread(self.cancel_batch, handle)

    async def afetch_batch_results(
        self, handle: "LLMBatchHandle"
    ) -> "List[LLMBatchResult]":
        """Async wrapper for :meth:`fetch_batch_results` (runs off event-loop thread)."""
        return await asyncio.to_thread(self.fetch_batch_results, handle)

    async def wait_for_batch(
        self,
        handle: "LLMBatchHandle",
        *,
        poll_interval: float = 5.0,
        timeout: "Optional[float]" = None,
    ) -> "LLMBatchHandle":
        """Poll until the batch reaches a terminal status or timeout expires.

        Uses capped exponential backoff between polls.  Raises
        ``LLMBatchExpiredError`` immediately when the handle is already EXPIRED
        (no polling needed).  Raises ``TimeoutError`` when ``timeout`` seconds
        elapse without reaching a terminal status.

        Args:
            handle: The batch handle to watch.
            poll_interval: Initial poll interval in seconds (default 5).
            timeout: Maximum total wait in seconds.  ``None`` (default) means
                wait indefinitely — the call returns only when a terminal status
                is reached or an exception is raised by the adapter.

        Raises:
            LLMBatchExpiredError: If the handle status is EXPIRED before polling.
            TimeoutError: If timeout is set and elapses without reaching a
                terminal status.
        """
        if handle.status == LLMBatchStatus.EXPIRED:
            self._logger.warning(
                "llm_batch.expired_operation handle_id=%s", handle.agentmap_batch_id
            )
            raise LLMBatchExpiredError(
                f"Batch {handle.agentmap_batch_id!r} has already expired."
            )

        import time

        _TERMINAL = {
            LLMBatchStatus.ENDED,
            LLMBatchStatus.FAILED,
            LLMBatchStatus.EXPIRED,
            LLMBatchStatus.CANCELED,
        }
        # F6: timeout=None means "no deadline" — wait indefinitely.
        deadline = None if timeout is None else time.monotonic() + timeout
        interval = poll_interval

        current = handle
        while current.status not in _TERMINAL:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._logger.warning(
                        "llm_batch.wait_timeout handle_id=%s timeout_s=%s",
                        handle.agentmap_batch_id,
                        timeout,
                    )
                    raise TimeoutError(
                        f"wait_for_batch timed out after {timeout}s for batch "
                        f"{handle.agentmap_batch_id!r} "
                        f"(last status: {current.status.value!r})."
                    )
                await asyncio.sleep(min(interval, remaining))
            else:
                await asyncio.sleep(interval)
            current = await self.apoll_batch(current)
            # Capped exponential backoff (max 60 s).
            interval = min(interval * 2, 60.0)

        return current

    def submit_and_wait(
        self,
        request: "LLMBatchSubmitRequest",
        *,
        poll_interval: float = 5.0,
        timeout: "Optional[float]" = None,
    ) -> "LLMBatchHandle":
        """Submit a batch and synchronously wait until it reaches a terminal status.

        Convenience wrapper combining :meth:`submit_batch` and
        :meth:`wait_for_batch`. Sync-context only.

        Raises:
            TimeoutError: If timeout elapses before the batch terminates.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise LLMServiceError(
                "submit_and_wait cannot run inside an active event loop; "
                "use asubmit_batch() + await wait_for_batch() from async contexts."
            )
        handle = self.submit_batch(request)
        return asyncio.run(
            self.wait_for_batch(handle, poll_interval=poll_interval, timeout=timeout)
        )

    def batch_capabilities(self, provider: str) -> Dict[str, Any]:
        """Return capability information for a registered provider.

        Reads the adapter's ``provider_name`` and ``supports_cancel`` attributes
        plus static per-provider metadata.

        Returns a dict whose keys match the ``LLMServiceProtocol`` contract:
        ``supports_cancel`` (bool), ``provider_name`` (str), ``supported`` (bool),
        ``completion_window`` (str), ``partial_fetch`` (bool).

        Raises:
            LLMBatchUnsupportedProviderError: If the provider is not registered.
        """
        adapter = self._get_adapter(provider)
        return {
            "supported": True,
            "supports_cancel": bool(getattr(adapter, "supports_cancel", False)),
            "provider_name": getattr(adapter, "provider_name", provider),
            "completion_window": "24h",
            "partial_fetch": False,
        }

    @staticmethod
    def results_by_request_id(
        records: "List[LLMBatchResult]",
    ) -> "Dict[str, LLMBatchResult]":
        """Index a list of result records by their ``request_id``.

        Args:
            records: Records returned by :meth:`fetch_batch_results`.

        Returns:
            Dict mapping ``request_id`` → ``LLMBatchResult``.
        """
        return {
            record.request_id: record
            for record in records
            if record.request_id is not None and record.request_id != ""
        }

    @staticmethod
    def reconcile_batch_results(
        submitted_request_ids: "List[str]",
        records: "List[LLMBatchResult]",
    ) -> "Dict[str, Optional[LLMBatchResult]]":
        """Report reconciliation between submitted request_ids and returned records.

        Identifies request_ids that have no returned record (missing from results).
        This satisfies REQ-F-009c: a caller can detect silent data loss where a
        spec was submitted but the provider returned no result for it.

        Args:
            submitted_request_ids: The list of request_ids submitted in the batch.
            records: Records returned by :meth:`fetch_batch_results`.

        Returns:
            Dict mapping every submitted ``request_id`` to its
            ``LLMBatchResult`` if one was returned, or ``None`` if the
            request_id has no corresponding record in ``records``.  A ``None``
            value signals a missing result that the caller should investigate.
        """
        by_id = {record.request_id: record for record in records}
        return {
            request_id: by_id.get(request_id) for request_id in submitted_request_ids
        }

    @staticmethod
    def _extract_llm_usage(response: Any) -> Optional[LLMUsage]:
        """Extract a normalized ``LLMUsage`` from an LLM provider response.

        Returns ``None`` when no usage metadata is available or when
        ``usage_metadata`` is present but all fields fail coercion.  Per-field
        coercion failures return ``None`` for that field (not for the whole
        ``LLMUsage``) so that a malformed token count never converts a successful
        provider response into a failed ``LLMFanoutResult``.

        Two-path extraction for ``cache_read_input_tokens`` (REQ-F-004):
          1. Flat key: ``usage_metadata.cache_read_input_tokens`` (Anthropic-style).
          2. Nested fallback: ``usage_metadata.input_token_details.cache_read``
             (OpenAI-style, where the LangChain adapter exposes cached token
             counts under the ``input_token_details`` object).

        Precedence rule: the flat ``cache_read_input_tokens`` value is used when
        it is non-None; the nested ``input_token_details.cache_read`` value is
        used only when the flat key is absent or None. This matches the
        Anthropic-first convention already established for other cache fields.
        """
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata is None:
            return None

        def _to_int(val: Any) -> Optional[int]:
            if val is None:
                return None
            try:
                return int(val)
            except (TypeError, ValueError):
                return None

        def _get(key: str) -> Optional[int]:
            if isinstance(usage_metadata, dict):
                return _to_int(usage_metadata.get(key))
            return _to_int(getattr(usage_metadata, key, None))

        # Flat key first (Anthropic-style); fall back to OpenAI nested path.
        flat_cache_read = _get("cache_read_input_tokens")
        if flat_cache_read is None:
            # OpenAI: usage_metadata["input_token_details"]["cache_read"]
            # LangChain normalizes AIMessage.usage_metadata as a dict (UsageMetadata
            # TypedDict); the nested sub-dict uses key "cache_read" (InputTokenDetails
            # TypedDict), not an object attribute "cached_tokens".
            if isinstance(usage_metadata, dict):
                details = usage_metadata.get("input_token_details")
            else:
                details = getattr(usage_metadata, "input_token_details", None)

            if isinstance(details, dict):
                nested_cached = details.get("cache_read")
            else:
                nested_cached = getattr(details, "cache_read", None)
            cache_read_input_tokens = _to_int(nested_cached)
        else:
            cache_read_input_tokens = flat_cache_read

        return LLMUsage(
            input_tokens=_get("input_tokens"),
            output_tokens=_get("output_tokens"),
            cache_creation_input_tokens=_get("cache_creation_input_tokens"),
            cache_read_input_tokens=cache_read_input_tokens,
        )

    @staticmethod
    def _extract_finish_reason(response: Any) -> Optional[str]:
        """Extract the provider's normalized stop/finish reason, if any.

        Reads ``response.response_metadata`` and returns the first of
        ``stop_reason`` (Anthropic) or ``finish_reason`` (OpenAI / Google)
        that is present. Returns ``None`` when metadata is absent or carries
        no recognized key. Used by callers for truncation detection.
        """
        resp_meta = getattr(response, "response_metadata", None)
        if not isinstance(resp_meta, dict):
            return None
        value = resp_meta.get("stop_reason")
        if value is None:
            value = resp_meta.get("finish_reason")
        return str(value) if value is not None else None

    def get_available_providers(self) -> List[str]:
        """
        Public method to get available providers.

        Returns:
            List of available provider names
        """
        return self._provider_utils.get_available_providers()

    # ------------------------------------------------------------------
    # Telemetry helpers (error-isolated, silent no-op when disabled)
    # ------------------------------------------------------------------

    def _set_span_status_ok(self, span: Any) -> None:
        """Set span status to OK using a function-level OTEL import.

        Guards: short-circuits if span is None.
        Error isolation: catches all exceptions (including ImportError).
        """
        if span is None:
            return
        try:
            from opentelemetry.trace import StatusCode

            span.set_status(StatusCode.OK)
        except Exception:
            pass

    def _set_current_span_attributes(self, attributes: Dict[str, Any]) -> None:
        """Set attributes on the current recording span (silent no-op on failure).

        Encapsulates the function-level OTEL import + span access pattern
        (ADR-E02F03-002). Guards: short-circuits if _telemetry_service is None.
        """
        if self._telemetry_service is None:
            return
        try:
            import opentelemetry.trace as trace_api

            current_span = trace_api.get_current_span()
            if current_span and current_span.is_recording():
                self._telemetry_service.set_span_attributes(current_span, attributes)
        except Exception:
            pass

    def _record_span_exception_safe(self, span: Any, exception: Exception) -> None:
        """Record exception on span safely. No-op on failure."""
        if span is None or self._telemetry_service is None:
            return
        try:
            self._telemetry_service.record_exception(span, exception)
        except Exception:
            pass

    @staticmethod
    def _extract_token_counts(response: Any) -> Tuple[Optional[int], Optional[int]]:
        """Extract (input_tokens, output_tokens) from an LLM response.

        Returns (None, None) when token data is unavailable.
        """
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata is None:
            return None, None
        if isinstance(usage_metadata, dict):
            return (
                usage_metadata.get("input_tokens"),
                usage_metadata.get("output_tokens"),
            )
        return (
            getattr(usage_metadata, "input_tokens", None),
            getattr(usage_metadata, "output_tokens", None),
        )

    @staticmethod
    def _extract_provider_request_id(
        response_metadata: Dict[str, Any], provider: str
    ) -> Optional[str]:
        """Extract the provider-specific request ID from response metadata.

        Each LLM provider returns request IDs in different locations:
        - Anthropic: response_metadata["id"] (e.g. "msg_01XFDUDYJgAACzvnptvVoYEL")
        - OpenAI: response_metadata["headers"]["x-request-id"]
        - Google: response_metadata["request_id"] (when available)

        Returns None when the ID is not found.
        """
        if not response_metadata:
            return None

        if provider == "anthropic":
            # Anthropic puts message ID directly in metadata
            return response_metadata.get("id")

        if provider == "openai":
            # OpenAI puts request ID in response headers
            headers = response_metadata.get("headers", {})
            if isinstance(headers, dict):
                return headers.get("x-request-id")

        if provider == "google":
            return response_metadata.get("request_id")

        # Generic fallback: try common keys
        for key in ("id", "request_id", "x-request-id"):
            val = response_metadata.get(key)
            if val and isinstance(val, str):
                return val

        return None

    def _record_llm_response_attributes(
        self, response: Any, provider: str, model: str = "unknown"
    ) -> None:
        """Extract and record token counts and response model from LLM response.

        Also records token count metrics when instruments are available.
        Guards: short-circuits if telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if self._telemetry_service is None:
            return
        try:
            input_tokens, output_tokens = self._extract_token_counts(response)

            attributes: Dict[str, Any] = {}
            if input_tokens is not None:
                attributes[GEN_AI_USAGE_INPUT_TOKENS] = int(input_tokens)
            if output_tokens is not None:
                attributes[GEN_AI_USAGE_OUTPUT_TOKENS] = int(output_tokens)

            response_metadata = getattr(response, "response_metadata", None)
            if response_metadata and isinstance(response_metadata, dict):
                response_model = response_metadata.get(
                    "model_name"
                ) or response_metadata.get("model")
                if response_model:
                    attributes[GEN_AI_RESPONSE_MODEL] = response_model

                request_id = self._extract_provider_request_id(
                    response_metadata, provider
                )
                if request_id:
                    attributes[GEN_AI_PROVIDER_REQUEST_ID] = request_id

                fingerprint = response_metadata.get("system_fingerprint")
                if fingerprint:
                    attributes[GEN_AI_SYSTEM_FINGERPRINT] = fingerprint

            if attributes:
                self._set_current_span_attributes(attributes)

            self._record_token_metrics(input_tokens, output_tokens, provider, model)
        except Exception:
            pass

    def _capture_llm_content(
        self,
        span: Any,
        messages: List[LLMMessage],
        result: str,
    ) -> None:
        """Optionally capture prompt/response content on the span.

        Flags ``_capture_llm_prompts`` and ``_capture_llm_responses``
        default to False (privacy-safe).  Content is truncated to 4096
        characters.

        Guards: short-circuits if telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if self._telemetry_service is None:
            return
        try:
            if getattr(self, "_capture_llm_prompts", False) and messages:
                prompt_text = self._message_utils.extract_prompt_from_messages(messages)
                value = prompt_text[:4096]
                self._telemetry_service.set_span_attributes(
                    span, {GEN_AI_PROMPT_CONTENT: value}
                )
            if getattr(self, "_capture_llm_responses", False) and result:
                value = str(result)[:4096]
                self._telemetry_service.set_span_attributes(
                    span, {GEN_AI_RESPONSE_CONTENT: value}
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Metrics recording helpers (error-isolated, silent no-op when disabled)
    # ------------------------------------------------------------------

    def _record_duration_metric(
        self, duration: float, provider: str, model: str
    ) -> None:
        """Record LLM call duration on the histogram instrument.

        Guards: short-circuits if telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if self._telemetry_service is None or self._metric_duration is None:
            return
        try:
            self._metric_duration.record(
                duration,
                {METRIC_DIM_PROVIDER: provider, METRIC_DIM_MODEL: model},
            )
        except Exception:
            pass

    def _record_token_metrics(
        self,
        input_tokens: Any,
        output_tokens: Any,
        provider: str,
        model: str,
    ) -> None:
        """Record token count metrics when available.

        Guards: short-circuits if telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if self._telemetry_service is None:
            return
        try:
            dims = {METRIC_DIM_PROVIDER: provider, METRIC_DIM_MODEL: model}
            if input_tokens is not None and self._metric_tokens_input is not None:
                self._metric_tokens_input.add(int(input_tokens), dims)
            if output_tokens is not None and self._metric_tokens_output is not None:
                self._metric_tokens_output.add(int(output_tokens), dims)
        except Exception:
            pass

    def _record_error_metric(self, error: Any, provider: str, model: str) -> None:
        """Record LLM error on the error counter.

        The error_type dimension is derived from the classified exception
        class name.

        Guards: short-circuits if telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if self._telemetry_service is None or self._metric_errors is None:
            return
        try:
            error_type = type(error).__name__
            self._metric_errors.add(
                1,
                {
                    METRIC_DIM_PROVIDER: provider,
                    METRIC_DIM_MODEL: model,
                    METRIC_DIM_ERROR_TYPE: error_type,
                },
            )
        except Exception:
            pass

    def _record_batch_metric(self, metric: Any, provider: str, status: str) -> None:
        """Record a batch lifecycle counter with provider/status dimensions."""
        if self._telemetry_service is None or metric is None:
            return
        try:
            metric.add(
                1,
                {
                    METRIC_DIM_PROVIDER: provider,
                    METRIC_DIM_BATCH_STATUS: status,
                },
            )
        except Exception:
            pass

    def _record_batch_submit_metric(self, provider: str, status: str) -> None:
        """Record one batch submit event."""
        self._record_batch_metric(self._metric_batch_submitted, provider, status)

    def _record_batch_poll_metric(self, provider: str, status: str) -> None:
        """Record one batch poll event."""
        self._record_batch_metric(self._metric_batch_poll, provider, status)

    def _record_batch_results_fetched_metric(self, provider: str, status: str) -> None:
        """Record one batch result-fetch event."""
        self._record_batch_metric(self._metric_batch_results_fetched, provider, status)

    def _record_batch_cancel_metric(self, provider: str, status: str) -> None:
        """Record one batch cancel request event."""
        self._record_batch_metric(self._metric_batch_cancel, provider, status)

    def _record_fallback_metric(self, tier: str) -> None:
        """Record a fallback activation on the fallback counter.

        Guards: short-circuits if telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if self._telemetry_service is None or self._metric_fallback is None:
            return
        try:
            self._metric_fallback.add(1, {METRIC_DIM_TIER: tier})
        except Exception:
            pass

    def _record_circuit_breaker_metric_on_open(self, provider: str, model: str) -> None:
        """Increment circuit breaker gauge when a circuit opens.

        Checks whether the circuit is now open after a failure was recorded.
        Guards: short-circuits if telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if self._telemetry_service is None or self._metric_circuit_breaker is None:
            return
        try:
            if self._circuit_breaker.is_open(provider, model):
                self._metric_circuit_breaker.add(1)
        except Exception:
            pass

    def _record_circuit_breaker_metric_on_close(
        self, was_open: bool, provider: str, model: str
    ) -> None:
        """Decrement circuit breaker gauge when a circuit closes.

        Called after record_success(); checks the transition from open
        to closed state.

        Guards: short-circuits if telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if self._telemetry_service is None or self._metric_circuit_breaker is None:
            return
        try:
            if was_open and not self._circuit_breaker.is_open(provider, model):
                self._metric_circuit_breaker.add(-1)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # E06-F03: Streaming entry point skeleton
    # Five sibling methods mirroring the non-streaming async chain.
    # Non-streaming methods are byte-untouched (REQ-NF-001, SC-2c).
    # ------------------------------------------------------------------

    async def call_llm_stream_async(
        self,
        messages: List[LLMMessage],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        cache_system_prompt: bool = False,
        **kwargs: Any,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Return an async iterator of ``LLMStreamChunk`` for token-streaming.

        Mirrors ``call_llm_async`` (:425) with the same parameter list. Dispatches
        to the telemetry wrapper when ``_telemetry_service`` is set; otherwise
        iterates ``_call_llm_stream_async_core`` directly (REQ-F-001).

        The caller iterates the result with ``async for chunk in ...``. Non-final
        chunks carry ``text_delta`` and ``chunk_index``; exactly one terminal chunk
        (``is_final=True``) closes the stream with accumulated usage/finish_reason
        and reconstructed provider/model identity (REQ-F-011, SC-1).
        """
        kwargs["cache_system_prompt"] = cache_system_prompt
        if self._telemetry_service is not None:
            async for chunk in self._call_llm_stream_async_with_telemetry(
                messages, provider, model, temperature, routing_context, **kwargs
            ):
                yield chunk
        else:
            async for chunk in self._call_llm_stream_async_core(
                messages, provider, model, temperature, routing_context, **kwargs
            ):
                yield chunk

    async def _call_llm_stream_async_with_telemetry(
        self,
        messages: List[LLMMessage],
        provider: Optional[str],
        model: Optional[str],
        temperature: Optional[float],
        routing_context: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Streaming telemetry wrapper — explicit span management (REQ-F-010).

        Opens the span via ``__enter__``/``try-finally __exit__`` (NOT a ``with``
        block) so the span survives across all ``yield`` suspension points and is
        guaranteed to close on completion, error, or ``GeneratorExit`` (caller
        abandonment / asyncio cancellation).

        Records TTFT once on the first delivered chunk, total duration on clean
        completion (REQ-F-009). Captures content once at completion (REQ-NF-002, C9).

        This is the sibling of ``_call_llm_async_with_telemetry`` (:461).
        """
        assert self._telemetry_service is not None

        initial_attributes: Dict[str, Any] = {}
        if provider:
            initial_attributes[GEN_AI_SYSTEM] = self._provider_utils.normalize_provider(
                provider
            )
        if model:
            initial_attributes[GEN_AI_REQUEST_MODEL] = model

        # Explicit span open — must NOT use `with` so the span survives yields.
        span_cm = self._telemetry_service.start_span(
            LLM_CALL_SPAN, attributes=initial_attributes
        )
        span = span_cm.__enter__()

        t0 = time.monotonic()
        ttft_recorded = False
        accumulated_text: List[str] = []

        try:
            async for chunk in self._call_llm_stream_async_core(
                messages, provider, model, temperature, routing_context, **kwargs
            ):
                if not ttft_recorded:
                    self._record_ttft_metric(
                        time.monotonic() - t0, provider or "", model or ""
                    )
                    ttft_recorded = True
                if chunk.text_delta:
                    accumulated_text.append(chunk.text_delta)
                yield chunk

            # Clean completion — capture content once, record total duration.
            self._capture_llm_content(span, messages, "".join(accumulated_text))
            self._set_span_status_ok(span)
            self._record_duration_metric(
                time.monotonic() - t0, provider or "", model or ""
            )
        except Exception as e:
            self._record_span_exception_safe(span, e)
            raise
        finally:
            span_cm.__exit__(None, None, None)

    async def _call_llm_stream_async_core(
        self,
        messages: List[LLMMessage],
        provider: Optional[str],
        model: Optional[str],
        temperature: Optional[float],
        routing_context: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Routing dispatch for the streaming path (REQ-F-002).

        Mirrors ``_call_llm_async_core`` (:638): routes through the streaming
        routing variant when a routing_context and routing service are present;
        raises ``LLMServiceError`` when no provider and no routing_context.
        """
        if routing_context is not None and self.routing_service:
            if model is not None:
                self._logger.warning(
                    "[LLMService] 'model' parameter is ignored when routing_context "
                    "is provided. Use routing_context['model_override'] to force a "
                    "specific model."
                )
            if provider is not None:
                self._logger.warning(
                    "[LLMService] 'provider' parameter is ignored when routing_context "
                    "is provided. Use routing_context['provider_preference'] to "
                    "influence provider selection or "
                    "routing_context['fallback_provider'] to set the fallback."
                )
            async for chunk in self._call_llm_stream_async_with_routing(
                messages,
                routing_context,
                temperature=temperature,
                model=model,
                **kwargs,
            ):
                yield chunk
            return
        if not provider:
            raise LLMServiceError(
                "provider is required when routing_context is not provided."
            )
        async for chunk in self._call_llm_stream_async_direct(
            provider,
            messages,
            model,
            temperature,
            **kwargs,
        ):
            yield chunk

    async def _call_llm_stream_async_with_routing(
        self,
        messages: List[LLMMessage],
        routing_context: Dict[str, Any],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Streaming routing variant — sibling of ``_call_llm_async_with_routing`` (:924).

        Resolves the routing decision then delegates to the streaming direct method.
        Skeleton: routing resolution logic will be filled by later tasks; currently
        raises ``LLMServiceError`` to indicate routing is not yet wired for streaming.
        """
        if not self.routing_service:
            raise LLMServiceError("Routing requested but no routing service available")
        # Routing resolution body is filled by later tasks (T-E06-F03-002+).
        raise LLMServiceError(
            "Streaming with routing_context is not yet implemented (E06-F03 T-002)."
        )
        # Unreachable yield — required to make this an async generator.
        yield  # type: ignore[misc]

    async def _call_llm_stream_async_direct(
        self,
        provider: str,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Direct streaming provider invocation with resilience and fallback.

        Skeleton: provider resolution, validation gate, resilience body, and
        fallback materialization will be filled by later tasks. Raises
        ``LLMServiceError`` to indicate the body is not yet implemented.
        """
        # Skeleton body — implementation added in later tasks (T-E06-F03-002+).
        raise LLMServiceError(
            "Streaming direct invocation is not yet implemented (E06-F03 T-002+)."
        )
        # Unreachable yield — required to make this an async generator.
        yield  # type: ignore[misc]

    def _record_ttft_metric(self, ttft: float, provider: str, model: str) -> None:
        """Record LLM streaming time-to-first-token on the TTFT histogram.

        Mirrors ``_record_duration_metric`` (:2705). No-op when ``_metric_ttft``
        or ``_telemetry_service`` is None. Error-isolated (never raises).

        REQ-F-008, REQ-F-009.
        """
        if self._telemetry_service is None or self._metric_ttft is None:
            return
        try:
            self._metric_ttft.record(
                ttft,
                {METRIC_DIM_PROVIDER: provider, METRIC_DIM_MODEL: model},
            )
        except Exception:
            pass
