"""
Internal marker exception carrying a budget-guard refusal through the
several blanket ``except Exception`` nets on the async LLM dispatch and
fallback path.

E05-F06 REQ-F-003 / NFR-F-003: *any* exception raised by
``LLMBudgetGuardProtocol.check_before_dispatch`` -- typed or not -- must
propagate to the original caller of ``call_llm_async`` unchanged, on
**every** tier (primary and each fallback tier), must never be
reclassified as a transient provider failure, and must never trigger a
further fallback attempt or a silent re-dispatch.

Lives in its own module (not ``llm_service.py``) specifically so that
``llm_fallback_handler.py`` can import and re-raise it ahead of its own
per-tier ``except Exception`` -- ``llm_service.py`` imports
``LLMFallbackHandler``, so defining this in ``llm_service.py`` would make
that import circular.
"""


class BudgetGuardRefusal(Exception):
    """Marker wrapping a budget guard's raw exception so every
    exception-handling seam on the async dispatch/fallback path can
    recognize "this came from the guard, not the provider or telemetry
    infrastructure" without changing the original exception's type or
    message.

    Raised for **every** attempt kind (``"primary"`` and ``"fallback"``) by
    ``LLMService._check_budget_before_dispatch``. Unwrapped back to
    ``.original`` at ``LLMService._dispatch_call_llm_async`` -- the single
    outermost boundary that every dispatch path (direct, routing,
    telemetry-wrapped, and every fallback tier re-entering the resilience
    seam) funnels through -- and never surfaces to a caller of
    ``call_llm_async``.
    """

    def __init__(self, original: BaseException) -> None:
        super().__init__(str(original))
        self.original = original
