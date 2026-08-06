"""
Unit tests for ``agentmap.services.llm._budget_guard_refusal`` (T-E05-F06-008
round-4 UAT rework, Finding 2: telemetry/log leakage).

Codex red-team finding: ``BudgetGuardRefusal(str(original))`` and the
span-exception recording it feeds echo a host budget guard's raw exception
message (which may carry tenant ids, remaining budget, spend caps) into
telemetry/log channels never designed to carry it.

These tests verify the fix at its root:
  1. ``BudgetGuardRefusal``'s own message no longer contains the original
     exception's text (only its class name).
  2. ``telemetry_safe_marker`` produces an object that -- when fed to the
     *exact* formatting function OpenTelemetry's SDK uses internally
     (``traceback.format_exception(type(exc), exc, exc.__traceback__)``,
     verified against ``opentelemetry.sdk.trace.Span.record_exception``
     source) -- carries no trace of the original message anywhere,
     including via the ``__cause__`` chain that a naively-generic message
     alone would NOT close (the actual root cause the round-4 UAT flagged).
  3. The *pre-fix* shape (recording the real ``BudgetGuardRefusal`` object
     directly, which still carries ``__cause__``) is proven to leak with the
     same formatting call -- so these tests discriminate a real fix from a
     cosmetic one instead of trivially passing either way.
  4. The ``mark_as_budget_guard_refusal`` / ``is_budget_guard_refusal``
     round-trip used by ``LLMService._execute_fan_out_item`` (Finding 1).
"""

import traceback
import unittest

from agentmap.services.llm._budget_guard_refusal import (
    BudgetGuardRefusal,
    is_budget_guard_refusal,
    mark_as_budget_guard_refusal,
    telemetry_safe_marker,
)

_SENTINEL = "tenant=acme-42 remaining_budget=$3.10 spend_cap=$100.00"


def _otel_sdk_stacktrace(exc: BaseException) -> str:
    """Reproduce ``opentelemetry.sdk.trace.Span.record_exception``'s own
    stacktrace formatting verbatim (source verified during this rework):

        stacktrace = "".join(traceback.format_exception(
            type(exception), value=exception, tb=exception.__traceback__
        ))

    Used directly (rather than through the real OTEL SDK, which is not an
    installed dependency in this project's test environment -- only
    ``opentelemetry-api`` is) so the test still exercises the real leak
    mechanism instead of a mocked stand-in.
    """
    return "".join(
        traceback.format_exception(type(exc), value=exc, tb=exc.__traceback__)
    )


class TestBudgetGuardRefusalMessage(unittest.TestCase):
    """BudgetGuardRefusal's own message must not echo the original text."""

    def test_message_does_not_contain_original_text(self):
        original = RuntimeError(_SENTINEL)
        refusal = BudgetGuardRefusal(original)

        self.assertNotIn(_SENTINEL, str(refusal))
        self.assertIn("RuntimeError", str(refusal))

    def test_original_is_preserved_unchanged(self):
        """NFR-F-003: the guard's own exception -- what a caller of
        call_llm_async ultimately observes -- must be byte-for-byte
        unchanged; only this wrapper's own message is sanitized."""
        original = RuntimeError(_SENTINEL)
        refusal = BudgetGuardRefusal(original)

        self.assertIs(refusal.original, original)
        self.assertEqual(str(refusal.original), _SENTINEL)


class TestTelemetrySafeMarker(unittest.TestCase):
    """telemetry_safe_marker must close both the message leak AND the
    __cause__-chain leak a generic message alone would not."""

    def _make_raised_refusal(self):
        """Raise a BudgetGuardRefusal the same way
        LLMService._check_budget_before_dispatch does (`raise
        BudgetGuardRefusal(e) from e`), so __cause__ and __traceback__ are
        populated exactly as they are on the real dispatch path."""
        original = RuntimeError(_SENTINEL)
        try:
            raise BudgetGuardRefusal(original) from original
        except BudgetGuardRefusal as refusal:
            return refusal

    def test_marker_has_no_cause_or_context(self):
        refusal = self._make_raised_refusal()
        self.assertIsNotNone(refusal.__cause__)  # sanity: the chain exists

        marker = telemetry_safe_marker(refusal)

        self.assertIsNone(marker.__cause__)
        self.assertIsNone(marker.__context__)
        self.assertIsNone(marker.__traceback__)

    def test_marker_stacktrace_formatting_contains_no_sentinel(self):
        """The exact OTEL-SDK-equivalent formatting of the marker must not
        contain the original guard exception's message anywhere."""
        refusal = self._make_raised_refusal()
        marker = telemetry_safe_marker(refusal)

        formatted = _otel_sdk_stacktrace(marker)
        self.assertNotIn(_SENTINEL, formatted)
        self.assertNotIn(_SENTINEL, str(marker))

    def test_recording_the_real_refusal_directly_would_have_leaked(self):
        """Negative control: proves this test suite is discriminating.

        Recording the *real*, raised ``BudgetGuardRefusal`` (the pre-fix
        behavior at llm_service.py's telemetry wrapper) leaks the sentinel
        via the __cause__ chain even though the wrapper's own top-level
        message was already sanitized -- exactly the gap the round-4 UAT
        flagged and a naive "just change the message" fix would have missed.
        """
        refusal = self._make_raised_refusal()

        leaky = _otel_sdk_stacktrace(refusal)
        self.assertIn(
            _SENTINEL,
            leaky,
            "test fixture invariant broken: expected the raw wrapper (with "
            "__cause__ set) to leak via chained traceback formatting -- if "
            "this fails, the negative control itself is no longer valid",
        )


class TestBudgetGuardRefusalMarkerAttribute(unittest.TestCase):
    """mark_as_budget_guard_refusal / is_budget_guard_refusal round-trip,
    used by LLMService._execute_fan_out_item (Finding 1) to recognize a
    budget refusal after it has already been unwrapped back to .original."""

    def test_unmarked_exception_is_not_recognized(self):
        self.assertFalse(is_budget_guard_refusal(RuntimeError("boom")))

    def test_marked_exception_is_recognized(self):
        exc = RuntimeError(_SENTINEL)
        mark_as_budget_guard_refusal(exc)
        self.assertTrue(is_budget_guard_refusal(exc))

    def test_marking_does_not_change_type_or_message(self):
        exc = RuntimeError(_SENTINEL)
        mark_as_budget_guard_refusal(exc)
        self.assertIsInstance(exc, RuntimeError)
        self.assertEqual(str(exc), _SENTINEL)

    def test_marking_survives_the_dispatch_unwrap_pattern(self):
        """Mirrors _check_budget_before_dispatch -> _dispatch_call_llm_async:
        mark, wrap, raise-and-catch, unwrap back to .original -- the marker
        must still be readable off the unwrapped object, since that is
        exactly what _execute_fan_out_item receives."""
        original = RuntimeError(_SENTINEL)
        mark_as_budget_guard_refusal(original)
        try:
            raise BudgetGuardRefusal(original) from original
        except BudgetGuardRefusal as refusal:
            unwrapped = refusal.original

        self.assertIs(unwrapped, original)
        self.assertTrue(is_budget_guard_refusal(unwrapped))


if __name__ == "__main__":
    unittest.main()
