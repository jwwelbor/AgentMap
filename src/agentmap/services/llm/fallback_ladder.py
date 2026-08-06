"""
Async fallback-ladder machinery for :class:`LLMFallbackHandler` (E05-F06).

``LLMFallbackAsyncLadderMixin`` supplies the async half of the tiered
fallback strategy -- ``try_with_fallback_async`` and its two private
helpers (``_try_fallback_tier``, ``_run_fallback_ladder_async``,
``_raise_fallback_exhausted``) -- as a mixin that
``agentmap.services.llm_fallback_handler.LLMFallbackHandler`` inherits
from.

Extracted out of ``llm_fallback_handler.py`` once round-1's own two
prescriptions (re-raising ``BudgetGuardRefusal`` ahead of the per-tier
``except Exception``; extracting methods to satisfy the 50-line ceiling)
pushed that file past the NFR-F-006 350-line file ceiling (round-2 code
review). A mixin -- rather than free functions taking a bag of
positional state -- keeps every method using ``self._logger``,
``self.routing_config``, ``self.features_registry``,
``self._build_tier_plan``, and ``self._invoke_client_async`` exactly as
before; only the file the bytes live in changed, not the class shape,
call signatures, or behavior.

Placed in ``services/llm/`` alongside ``cost_calculator.py`` /
``tool_call_extraction.py`` (same NFR-F-006 precedent). This module only
imports from ``services/llm/_budget_guard_refusal.py``,
``exceptions/service_exceptions.py``, ``models/llm_execution.py``, and
``services/llm_message_service.py`` -- none of which import
``llm_service.py`` or ``llm_fallback_handler.py`` back, so there is no
import cycle to dodge (verified with a direct import smoke test; see
T-E05-F06-008 rework notes).
"""

from typing import Any, List, NoReturn, Optional, Tuple

from agentmap.exceptions.service_exceptions import LLMResolvedCallError
from agentmap.models.llm_execution import LLMMessage, LLMResponse
from agentmap.services.llm._budget_guard_refusal import BudgetGuardRefusal
from agentmap.services.llm_message_service import LLMMessageService


class LLMFallbackAsyncLadderMixin:
    """Async tiered-fallback ladder: walk the shared tier plan, materialize
    the first success, or raise once every tier is exhausted.

    Expects the consuming class to provide ``self._logger``,
    ``self.routing_config``, ``self.features_registry``,
    ``self._build_tier_plan(...)``, and ``self._invoke_client_async(...)``
    -- all defined on ``LLMFallbackHandler`` itself.
    """

    async def _try_fallback_tier(
        self,
        fallback_provider: str,
        fallback_model: str,
        langchain_msgs: List[Any],
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
    ) -> Tuple[Optional[LLMResponse], Optional[Exception], bool]:
        """Resolve one fallback tier's client and invoke it, translating the
        outcome into a plain result tuple instead of an exception.

        Returns ``(response, tier_error, client_resolved)``: exactly one of
        ``response``/``tier_error`` is set. ``client_resolved`` is True once
        ``get_or_create_client_fn`` succeeded -- preserves the MEDIUM-2 fix's
        "identity reflects only an attempted network call" semantics without
        a callback. ``BudgetGuardRefusal`` is deliberately **not** caught --
        it propagates so the ladder stops instead of treating a fail-closed
        refusal as an ordinary tier failure (E05-F06 REQ-F-003 / NFR-F-003).
        Extracted from ``try_with_fallback_async`` (NFR-F-006).
        """
        client_resolved = False
        try:
            self._logger.warning(
                f"Fallback tier: trying '{fallback_provider}:{fallback_model}'"
            )
            config = get_provider_config_fn(fallback_provider)
            config = dict(config)  # defensive copy — avoid mutating shared config
            config["model"] = fallback_model
            client = get_or_create_client_fn(fallback_provider, config)
            client_resolved = True
            result = await self._invoke_client_async(
                client, langchain_msgs, fallback_provider, fallback_model
            )
            self._logger.info(
                f"Fallback tier '{fallback_provider}:{fallback_model}' successful"
            )
            return result, None, client_resolved
        except BudgetGuardRefusal:
            raise
        except Exception as tier_error:
            self._logger.warning(
                f"Fallback tier '{fallback_provider}:{fallback_model}' failed: {tier_error}"
            )
            return None, tier_error, client_resolved

    async def try_with_fallback_async(
        self,
        original_provider: str,
        original_model: str,
        messages: List[LLMMessage],
        error: Exception,
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
        convert_messages_fn: Any,
        **kwargs,
    ) -> LLMResponse:
        """Async variant of tiered fallback preserving the sync fallback order.

        Returns ``LLMResponse`` carrying the resolved provider, model, and usage
        from the winning fallback tier. On exhaustion, raises
        ``LLMResolvedCallError`` carrying the last-attempted tier's identity
        (policy: last tier wins). A ``BudgetGuardRefusal`` from any tier's own
        pre-dispatch budget check propagates unchanged instead of being
        absorbed as a tier failure -- see ``_run_fallback_ladder_async``
        (E05-F06 REQ-F-003 / NFR-F-003).
        """
        self._logger.error(
            f"Model '{original_model}' failed for provider '{original_provider}': {error}"
        )
        # Strip Anthropic-only cache_control before failover — non-Anthropic
        # fallback providers can reject it at their API boundary, and prompt-cache
        # savings are moot on a recovery call.
        langchain_msgs = convert_messages_fn(
            LLMMessageService.strip_cache_control(messages)
        )
        return await self._run_fallback_ladder_async(
            original_provider,
            original_model,
            langchain_msgs,
            error,
            get_provider_config_fn,
            get_or_create_client_fn,
        )

    async def _run_fallback_ladder_async(
        self,
        original_provider: str,
        original_model: str,
        langchain_msgs: List[Any],
        error: Exception,
        get_provider_config_fn: Any,
        get_or_create_client_fn: Any,
    ) -> LLMResponse:
        """Walk the shared tier plan; return the first success or raise via
        ``_raise_fallback_exhausted``.

        Extracted from ``try_with_fallback_async`` (NFR-F-006) once
        ``BudgetGuardRefusal`` handling pushed it past 50 lines.
        """
        attempted_fallbacks: List[str] = []
        last_attempted_provider = original_provider
        last_attempted_model = original_model
        last_error: Exception = error

        for fallback_provider, fallback_model in self._build_tier_plan(
            original_provider, original_model
        ):
            attempted_fallbacks.append(f"{fallback_provider}:{fallback_model}")
            response, tier_error, client_resolved = await self._try_fallback_tier(
                fallback_provider,
                fallback_model,
                langchain_msgs,
                get_provider_config_fn,
                get_or_create_client_fn,
            )
            if response is not None:
                return response
            last_error = tier_error
            if client_resolved:
                last_attempted_provider = fallback_provider
                last_attempted_model = fallback_model

        self._raise_fallback_exhausted(
            original_provider,
            original_model,
            attempted_fallbacks,
            error,
            last_attempted_provider,
            last_attempted_model,
            last_error,
        )

    def _raise_fallback_exhausted(
        self,
        original_provider: str,
        original_model: str,
        attempted_fallbacks: List[str],
        original_error: Exception,
        last_attempted_provider: str,
        last_attempted_model: str,
        last_error: Exception,
    ) -> NoReturn:
        """Log and raise once every fallback tier has failed.

        Extracted from ``_run_fallback_ladder_async`` (NFR-F-006). Raises
        with the last-attempted tier identity and the last tier's typed
        error as cause -- using ``last_error`` (the actual typed exception
        from the last invocation) rather than a synthetic ``LLMServiceError``
        wrapper preserves the error discriminator (``LLMTimeoutError``,
        ``LLMRateLimitError``, etc.) for callers that filter on
        ``LLMExecutionError.error_type`` (MEDIUM-1 fix).
        """
        error_msg = (
            f"All fallback strategies exhausted for original request "
            f"(provider: {original_provider}, model: {original_model}). "
            f"Attempted fallbacks: {', '.join(attempted_fallbacks) if attempted_fallbacks else 'none'}. "
            f"Original error: {original_error}"
        )
        self._logger.error(error_msg)
        raise LLMResolvedCallError(
            resolved_provider=last_attempted_provider,
            resolved_model=last_attempted_model,
            cause=last_error,
        )
