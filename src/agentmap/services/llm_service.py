"""
LLM Service for centralized LLM calling in AgentMap.

Provides a unified interface for calling different LLM providers while
handling configuration, error handling, provider abstraction, tiered fallback,
and resilience (retry with backoff + circuit breaker).
"""

import random
import time
from typing import Any, Dict, List, Optional, Tuple

from agentmap.exceptions import (
    LLMConfigurationError,
    LLMDependencyError,
    LLMProviderError,
    LLMServiceError,
)
from agentmap.services.config import AppConfigService
from agentmap.services.config.llm_models_config_service import LLMModelsConfigService
from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.llm_client_factory import LLMClientFactory
from agentmap.services.llm_error_utils import classify_llm_error, is_retryable
from agentmap.services.llm_fallback_handler import LLMFallbackHandler
from agentmap.services.llm_message_utils import LLMMessageUtils
from agentmap.services.llm_provider_utils import LLMProviderUtils
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.circuit_breaker import CircuitBreaker
from agentmap.services.routing.routing_service import LLMRoutingService
from agentmap.services.routing.types import RoutingContext
from agentmap.services.telemetry.constants import (
    GEN_AI_PROMPT_CONTENT,
    GEN_AI_PROVIDER_REQUEST_ID,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_CONTENT,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_SYSTEM_FINGERPRINT,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    LLM_CALL_SPAN,
    METRIC_DIM_ERROR_TYPE,
    METRIC_DIM_MODEL,
    METRIC_DIM_PROVIDER,
    METRIC_DIM_TIER,
    METRIC_LLM_CIRCUIT_BREAKER,
    METRIC_LLM_DURATION,
    METRIC_LLM_ERRORS,
    METRIC_LLM_FALLBACK,
    METRIC_LLM_ROUTING_CACHE_HIT,
    METRIC_LLM_TOKENS_INPUT,
    METRIC_LLM_TOKENS_OUTPUT,
    ROUTING_CACHE_HIT,
    ROUTING_CIRCUIT_BREAKER_STATE,
    ROUTING_COMPLEXITY,
    ROUTING_CONFIDENCE,
    ROUTING_FALLBACK_TIER,
    ROUTING_MODEL,
    ROUTING_PROVIDER,
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
        self._fallback_handler = LLMFallbackHandler(
            logging_service,
            routing_config_service,
            features_registry_service,
            invoke_fn=self._invoke_with_resilience,
        )
        self._message_utils = LLMMessageUtils()

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
        if telemetry_service is not None:
            try:
                self._metric_duration = telemetry_service.create_histogram(
                    METRIC_LLM_DURATION,
                    unit="s",
                    description="LLM call duration",
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
            except Exception:
                pass  # Instrument creation failure silently ignored

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

    def _convert_messages_to_langchain(
        self, messages: List[Dict[str, str]]
    ) -> List[Any]:
        """Backwards compatibility wrapper for convert_messages_to_langchain."""
        return self._message_utils.convert_messages_to_langchain(messages)

    def _extract_prompt_from_messages(self, messages: List[Dict[str, str]]) -> str:
        """Backwards compatibility wrapper for extract_prompt_from_messages."""
        return self._message_utils.extract_prompt_from_messages(messages)

    def call_llm(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
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
            **kwargs: Additional provider-specific parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: On various error conditions
        """
        if self._telemetry_service is not None:
            return self._call_llm_with_telemetry(
                messages, provider, model, temperature, routing_context, **kwargs
            )
        return self._call_llm_core(
            messages, provider, model, temperature, routing_context, **kwargs
        )

    def _call_llm_with_telemetry(
        self,
        messages: List[Dict[str, str]],
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
        messages: List[Dict[str, str]],
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
            return self._call_llm_with_routing(messages, routing_context, **kwargs)
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

    def _call_llm_with_routing(
        self, messages: List[Dict[str, str]], routing_context: Dict[str, Any], **kwargs
    ) -> str:
        """
        Make an LLM call using intelligent routing to select provider/model.

        Args:
            messages: List of message dictionaries
            routing_context: Dictionary containing routing parameters
            **kwargs: Additional LLM parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: If routing fails or no providers are available
        """
        if not self.routing_service:
            raise LLMServiceError("Routing requested but no routing service available")

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

            # Make the actual LLM call with the selected provider/model
            return self._call_llm_direct(
                provider=decision.provider,
                messages=messages,
                model=decision.model,
                temperature=kwargs.get("temperature"),
                **kwargs,
            )

        except Exception as e:
            self._logger.error(f"Routing failed: {e}")
            # Fall back to direct call if routing fails
            fallback_provider = routing_context.get("fallback_provider", "anthropic")
            self._logger.warning(
                f"Falling back to {fallback_provider} due to routing failure"
            )
            # Record fallback metric
            self._record_fallback_metric("routing_fallback")
            return self._call_llm_direct(
                provider=fallback_provider,
                messages=messages,
                model=kwargs.get("model"),
                temperature=kwargs.get("temperature"),
                **kwargs,
            )

    def _call_llm_direct(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
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
            **kwargs: Additional provider-specific parameters

        Returns:
            Response text string

        Raises:
            LLMServiceError: On various error conditions
        """
        try:
            # Normalize provider name
            provider = self._provider_utils.normalize_provider(provider)

            # Get provider configuration
            config = self._provider_utils.get_provider_config(provider)

            # Override model, temperature, and max_tokens if provided
            max_tokens = kwargs.pop("max_tokens", None)
            if model:
                config = config.copy()
                config["model"] = model
            if temperature is not None:
                config = config.copy()
                config["temperature"] = temperature
            if max_tokens is not None:
                config = config.copy()
                config["max_tokens"] = max_tokens

            # Get or create LangChain client
            client = self._client_factory.get_or_create_client(provider, config)

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
                        messages,
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

    # ------------------------------------------------------------------
    # Routing telemetry helpers (error-isolated, silent no-op when disabled)
    # ------------------------------------------------------------------

    def _record_routing_attributes(self, decision: Any) -> None:
        """Record routing decision attributes on the current LLM span.

        Uses ``opentelemetry.trace.get_current_span()`` (function-level import)
        to access the span without parameter threading (ADR-E02F03-002).

        Guards: short-circuits if ``_telemetry_service`` is None.
        Error isolation: catches all exceptions silently (3-layer isolation).
        """
        if self._telemetry_service is None:
            return
        try:
            import opentelemetry.trace as trace_api

            current_span = trace_api.get_current_span()
            if current_span and current_span.is_recording():
                attributes: Dict[str, Any] = {
                    ROUTING_COMPLEXITY: str(decision.complexity),
                    ROUTING_CONFIDENCE: decision.confidence,
                    ROUTING_PROVIDER: decision.provider,
                    ROUTING_MODEL: decision.model,
                    ROUTING_CACHE_HIT: decision.cache_hit,
                    # Update GenAI attributes with routed values
                    GEN_AI_SYSTEM: decision.provider,
                    GEN_AI_REQUEST_MODEL: decision.model,
                }

                if decision.fallback_used:
                    attributes[ROUTING_FALLBACK_TIER] = "fallback"

                self._telemetry_service.set_span_attributes(current_span, attributes)

            # Record cache hit metric
            if decision.cache_hit and self._metric_cache_hit is not None:
                try:
                    self._metric_cache_hit.add(1)
                except Exception:
                    pass  # Metric failure silently ignored
        except Exception:
            pass  # Telemetry failures silently ignored

    def _record_circuit_breaker_state(self, provider: str, model: str) -> None:
        """Record circuit breaker state on the current span.

        Uses ``opentelemetry.trace.get_current_span()`` (function-level import)
        to access the span without parameter threading (ADR-E02F03-002).

        Guards: short-circuits if ``_telemetry_service`` is None.
        Error isolation: catches all exceptions silently (3-layer isolation).
        """
        if self._telemetry_service is None:
            return
        try:
            import opentelemetry.trace as trace_api

            current_span = trace_api.get_current_span()
            if current_span and current_span.is_recording():
                state = "closed"  # Default healthy state
                if self._circuit_breaker.is_open(provider, model):
                    state = "open"
                self._telemetry_service.set_span_attributes(
                    current_span,
                    {ROUTING_CIRCUIT_BREAKER_STATE: state},
                )
        except Exception:
            pass  # Telemetry failures silently ignored

    def _create_routing_context(
        self, routing_context: Dict[str, Any], messages: List[Dict[str, str]]
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
        if not usage_metadata:
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

        Uses function-level OTEL import to access the current span.
        Also records token count metrics when instruments are available.
        Guards: short-circuits if telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if self._telemetry_service is None:
            return
        try:
            input_tokens, output_tokens = self._extract_token_counts(response)

            # Record span attributes only when a span is active
            import opentelemetry.trace as trace_api

            current_span = trace_api.get_current_span()
            if current_span and current_span.is_recording():
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

                    # Extract provider request ID for debugging/support
                    request_id = self._extract_provider_request_id(
                        response_metadata, provider
                    )
                    if request_id:
                        attributes[GEN_AI_PROVIDER_REQUEST_ID] = request_id

                    # Extract system fingerprint (OpenAI)
                    fingerprint = response_metadata.get("system_fingerprint")
                    if fingerprint:
                        attributes[GEN_AI_SYSTEM_FINGERPRINT] = fingerprint

                if attributes:
                    self._telemetry_service.set_span_attributes(
                        current_span, attributes
                    )

            # Record token metrics regardless of span context
            self._record_token_metrics(input_tokens, output_tokens, provider, model)
        except Exception:
            pass

    def _capture_llm_content(
        self,
        span: Any,
        messages: List[Dict[str, str]],
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
