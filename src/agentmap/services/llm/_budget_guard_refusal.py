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

Lives in its own module (not ``llm_service.py``) specifically so that the
async fallback ladder (``LLMFallbackAsyncLadderMixin._try_fallback_tier``,
``services/llm/fallback_ladder.py``, composed into
``LLMFallbackHandler``) can import and re-raise it ahead of its own
per-tier ``except Exception`` -- ``llm_service.py`` imports
``LLMFallbackHandler``, so defining this in ``llm_service.py`` would make
that import circular.

T-E05-F06-008 round-4 UAT rework: two defect classes fixed here --

1. **Telemetry/log leakage** (this module's own contribution): a host
   guard's exception message may carry business/budget data (tenant ids,
   remaining budget, spend caps) that must never be exported through a
   channel not designed to carry it. ``BudgetGuardRefusal`` itself never
   reaches a caller of ``call_llm_async``/``call_llm_stream_async`` (both
   entrypoints unwrap back to ``.original`` before returning control), so
   its own ``str()`` is observed **only** by the telemetry span-exception
   recording sites in ``llm_service.py`` (``_call_llm_async_with_telemetry``,
   ``_call_llm_stream_async_with_telemetry``) which run *before* that
   unwrap. Its message is therefore a generic, class-name-only marker, not
   ``str(original)`` -- see ``telemetry_safe_marker`` below for why the
   ``raise ... from e`` cause chain needs a second, independent fix at
   those call sites.
2. **Fan-out distinguishability**: ``LLMService._execute_fan_out_item``
   only ever sees the *unwrapped* ``.original`` (never this wrapper), so it
   cannot recognize a budget refusal via ``isinstance``. ``mark_as_budget_
   guard_refusal`` / ``is_budget_guard_refusal`` stamp and read a best-effort,
   message-preserving marker attribute directly on ``.original`` for that
   purpose.

TD-042 update: defect class 2's setattr/getattr marker is best-effort and
fails silently for a host guard exception whose ``__setattr__`` rejects the
marker attribute (e.g. one that raises to protect its own fields), leaving
``LLMFanoutResult.error.is_budget_refusal`` incorrectly ``None``/``False``
for that exception even though the guard did refuse. ``call_llm_async``
must keep unwrapping ``BudgetGuardRefusal`` back to ``.original`` before
returning to ANY caller (REQ-F-003 -- including ``_execute_fan_out_item``,
which deliberately stays on the public ``call_llm_async`` seam so it keeps
inheriting routing/retry/fallback/telemetry behavior, and so existing tests
that patch ``call_llm_async`` directly keep working), so
``_execute_fan_out_item`` can never ``except BudgetGuardRefusal`` itself --
by the time it sees the exception, it is already unwrapped.

Fix: ``mark_budget_guard_refusal_context`` / ``consume_budget_guard_refusal_
context`` record and read the exact (by identity) guard exception via a
task-scoped ``contextvars.ContextVar`` instead of an attribute on the
exception object -- no mutation of ``exc`` at all, so no ``__setattr__``
failure mode is possible. ``asyncio`` copies the context at
``asyncio.ensure_future``/``Task`` creation, and ``call_llm_many_async``
creates one task per fan-out item, so concurrent siblings never observe
each other's marks. ``mark_as_budget_guard_refusal`` / ``is_budget_guard_
refusal`` (the original setattr/getattr marker) are kept for backward
compatibility and as a defense-in-depth fallback for any other call path
that still relies on the marker side-channel (D-2,
``docs/plan/tech-debt/TD-042.research-report.md``).
"""

import contextvars
from typing import Optional


class BudgetGuardRefusal(Exception):
    """Marker wrapping a budget guard's raw exception so every
    exception-handling seam on the async dispatch/fallback path can
    recognize "this came from the guard, not the provider or telemetry
    infrastructure" without changing the original exception's type or
    message.

    Raised for **every** attempt kind (``"primary"`` and ``"fallback"``) by
    ``LLMService._check_budget_before_dispatch``. Unwrapped back to
    ``.original`` at the single outermost boundary each entrypoint owns --
    ``LLMService._dispatch_call_llm_async`` for every non-streaming dispatch
    path (direct, routing, telemetry-wrapped, and every fallback tier
    re-entering the resilience seam), and ``LLMService.call_llm_stream_async``
    for its streaming sibling (a fallback-tier refusal can reach it via
    ``_call_llm_stream_async_direct``'s pre-first-chunk fallback
    materialization) -- and never surfaces to a caller of ``call_llm_async``
    or ``call_llm_stream_async``, including ``LLMService._execute_fan_out_item``
    (TD-042: recognized instead via ``consume_budget_guard_refusal_context``,
    an identity check against the un-unwrapped exception recorded in a
    ContextVar at the moment ``_check_budget_before_dispatch`` raised it).

    ``.original``'s type and message are preserved byte-for-byte (that is
    what every caller of ``call_llm_async``/``call_llm_stream_async``
    ultimately observes). This wrapper's **own** message is deliberately
    *not* ``str(original)`` -- see module docstring, defect class 1: the
    only consumer of this exception's own ``str()`` is telemetry span
    recording, which must never carry the host guard's raw text.
    """

    def __init__(self, original: BaseException) -> None:
        super().__init__(f"budget guard refused ({type(original).__name__})")
        self.original = original


_MARKER_ATTR = "_agentmap_budget_guard_refusal"


def mark_as_budget_guard_refusal(exc: BaseException) -> None:
    """Best-effort marker stamped onto *exc* -- the guard's own, still-
    unwrapped exception -- so a caller that only ever sees the unwrapped
    original (``LLMService._execute_fan_out_item``'s blanket ``except
    Exception``, which runs *after* ``_dispatch_call_llm_async`` has already
    unwrapped ``BudgetGuardRefusal`` back to ``.original``) can still
    recognize that a fan-out item's failure came from the budget guard, not
    from the provider, and classify it deterministically (e.g. force
    ``retryable=False``) instead of leaving that to chance based on the
    host's chosen exception type (T-E05-F06-008 round-4 UAT finding).

    Deliberately does not change ``exc``'s type or message (NFR-F-003: the
    guard's exception must propagate to the caller of ``call_llm_async``
    unchanged) -- only adds an out-of-band attribute. Best-effort: a few
    exception types restrict instance attributes (e.g. a custom
    ``__setattr__`` that raises); a failed stamp silently degrades to "not
    recognized as a guard refusal" rather than breaking the refusal itself.

    .. deprecated:: TD-042
        ``LLMService._execute_fan_out_item`` no longer depends solely on
        this marker -- it primarily uses
        ``consume_budget_guard_refusal_context``, a task-scoped ContextVar
        identity check immune to this marker's silent-failure mode (see
        module docstring). This function is still called (kept for backward
        compatibility and as a defense-in-depth fallback for any other call
        path, D-2, ``docs/plan/tech-debt/TD-042.research-report.md``); new
        code should prefer ``mark_budget_guard_refusal_context``.
    """
    try:
        setattr(exc, _MARKER_ATTR, True)
    except Exception:
        pass


def is_budget_guard_refusal(exc: BaseException) -> bool:
    """True if *exc* was stamped by ``mark_as_budget_guard_refusal``.

    Best-effort, mirroring the stamp side: ``exc`` is an arbitrary
    host-authored exception (the guard protocol permits "any exception" to
    refuse), and this is called from inside
    ``LLMService._execute_fan_out_item``'s own blanket ``except Exception``
    handler. A host exception with a pathological ``__getattr__`` that
    raises something other than ``AttributeError`` must not be allowed to
    escape from there -- that would abort every sibling item in the same
    ``asyncio.gather`` call, breaking fan-out's per-item isolation contract
    for a reason that has nothing to do with any of those siblings.

    .. deprecated:: TD-042
        Superseded, for ``_execute_fan_out_item``, by
        ``consume_budget_guard_refusal_context``'s ContextVar identity
        check, which runs first and does not depend on ``exc`` accepting an
        out-of-band attribute. Kept as a defense-in-depth fallback for other
        call paths (D-2); see ``mark_as_budget_guard_refusal``'s
        deprecation note.
    """
    try:
        return getattr(exc, _MARKER_ATTR, False) is True
    except Exception:
        return False


# TD-042: task-scoped companion to the setattr/getattr marker above, keyed
# by object identity rather than a mutated attribute. ``contextvars.Context``
# is copied whenever ``asyncio`` starts a new ``Task``
# (``asyncio.ensure_future``/``asyncio.create_task``) -- ``LLMService.
# call_llm_many_async`` creates exactly one such task per fan-out item, so a
# ``set()`` made while handling one item's refusal is never visible to a
# concurrently-running sibling item's task, without any global registry, id()
# re-use risk, or weak-referenceability requirement.
_budget_guard_refusal_context: "contextvars.ContextVar[Optional[BaseException]]" = (
    contextvars.ContextVar("agentmap_budget_guard_refusal_context", default=None)
)


def mark_budget_guard_refusal_context(original: BaseException) -> None:
    """Record *original* -- the guard's own, still-unwrapped exception -- in
    the current task's ``ContextVar`` right before it is wrapped and raised
    as ``BudgetGuardRefusal`` (``LLMService._check_budget_before_dispatch``).

    Companion to ``mark_as_budget_guard_refusal``: unlike that function,
    this never touches ``original`` itself, so it cannot fail for any
    exception shape, including one with a pathological ``__setattr__``
    (TD-042). Read back via ``consume_budget_guard_refusal_context``.
    """
    _budget_guard_refusal_context.set(original)


def consume_budget_guard_refusal_context(exc: BaseException) -> bool:
    """True if *exc* is -- by identity, not equality -- the exact exception
    most recently recorded in THIS task's context by
    ``mark_budget_guard_refusal_context``.

    Always clears the ContextVar after reading (read-once semantics) so a
    stale mark can never be attributed to a later, unrelated exception
    handled in the same task. Safe to call for any exception, including one
    the guard never touched -- ``exc`` is never mutated or inspected beyond
    an identity comparison, so no host exception shape (pathological
    ``__setattr__``/``__eq__``/``__hash__``) can make this raise.
    """
    recorded = _budget_guard_refusal_context.get()
    _budget_guard_refusal_context.set(None)
    return recorded is not None and recorded is exc


def telemetry_safe_marker(exc: "BudgetGuardRefusal") -> Exception:
    """Return a stand-in for *exc* that is safe to hand to a telemetry
    span's exception recorder.

    ``BudgetGuardRefusal.__init__`` already keeps this wrapper's own
    message generic (defect class 1 above), but that alone is not
    sufficient: ``LLMService._check_budget_before_dispatch`` raises via
    ``raise BudgetGuardRefusal(e) from e``, which sets ``__cause__`` to the
    host's *original* exception. OpenTelemetry's ``span.record_exception``
    formats the full chained traceback (``traceback.format_exception``
    includes "the above exception was the direct cause of..." followed by
    the cause's own ``str()``), so recording ``exc`` directly would still
    leak the original message through ``exception.stacktrace`` even though
    ``exception.message`` is clean.

    The returned exception is never raised -- callers only pass it to
    ``TelemetryService.record_exception`` for its class name and
    constructed message -- so it is constructed fresh, with no
    ``__cause__``/``__context__``/``__traceback__`` (those are only
    populated by the interpreter at ``raise`` time, never by plain
    instantiation).

    Deliberate residual scope: ``str(exc)`` is
    ``BudgetGuardRefusal``'s own generic message, ``"budget guard refused
    (<ClassName>)"`` -- it names the host guard's exception *class*, never
    its instance data. A host that names tenant/budget identity in the
    exception *class name itself* (e.g. a dynamically-generated
    ``TenantBudgetExceeded_acme42`` type, as opposed to putting it in the
    instance message, which this fix already strips) would still surface
    that name here. This matches the UAT finding's own suggested
    remediation verbatim ("record only a generic marker ... without the
    original text") and the ordinary Python convention that exception
    *type names* are code, not data; going further (e.g. hashing or
    omitting the class name entirely) was judged unnecessary and would
    remove genuinely useful, non-sensitive diagnostic signal for the
    overwhelming majority of hosts that follow that convention.
    """
    marker = Exception(str(exc))
    return marker
