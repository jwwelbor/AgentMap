"""
Unit tests for the shared services/serverless/trigger_parser.TriggerParser.

TD-013: base_handler.py previously duplicated this strategy-iteration parser
locally. These tests cover the shared parser directly (strategy iteration,
first-match-wins, and the "no strategy matched" fallback), plus the
regression the consolidation could have introduced: the fallback branch
returning a dict that aliases (and can mutate) the caller's event.
"""

import unittest

from agentmap.models.serverless_models import TriggerType
from agentmap.services.serverless.trigger_parser import TriggerParser


class _AlwaysMatchStrategy:
    def __init__(self, trigger_type, payload):
        self._trigger_type = trigger_type
        self._payload = payload
        self.calls = 0

    def matches(self, event):
        self.calls += 1
        return True

    def parse(self, event):
        return self._trigger_type, self._payload


class _NeverMatchStrategy:
    def __init__(self):
        self.calls = 0

    def matches(self, event):
        self.calls += 1
        return False

    def parse(self, event):  # pragma: no cover - never reached
        raise AssertionError("parse() must not be called when matches() is False")


class TestTriggerParserStrategyIteration(unittest.TestCase):
    """TriggerParser iterates strategies in order and stops at first match."""

    def test_first_matching_strategy_wins(self):
        never = _NeverMatchStrategy()
        matches_first = _AlwaysMatchStrategy(TriggerType.STORAGE, {"a": 1})
        matches_second = _AlwaysMatchStrategy(TriggerType.DATABASE, {"b": 2})

        parser = TriggerParser([never, matches_first, matches_second])
        trigger_type, data = parser.parse({"any": "event"})

        self.assertEqual(trigger_type, TriggerType.STORAGE)
        self.assertEqual(data, {"a": 1})
        self.assertEqual(never.calls, 1)

    def test_later_strategies_not_consulted_after_match(self):
        matches_first = _AlwaysMatchStrategy(TriggerType.HTTP, {})
        never_reached = _NeverMatchStrategy()

        parser = TriggerParser([matches_first, never_reached])
        parser.parse({"any": "event"})

        self.assertEqual(never_reached.calls, 0)


class TestTriggerParserDefaultFallback(unittest.TestCase):
    """When no strategy matches, the parser falls back to treating the event
    (or its 'body') as the data payload — without mutating the caller's event."""

    def setUp(self):
        self.parser = TriggerParser([_NeverMatchStrategy()])

    def test_fallback_returns_http_trigger_type(self):
        trigger_type, _ = self.parser.parse({"graph": "my_graph", "state": {}})
        self.assertEqual(trigger_type, TriggerType.HTTP)

    def test_fallback_exposes_graph_and_state_keys_from_direct_invoke_event(self):
        """A direct-invoke event (no 'body' key) behaves like the pre-consolidation
        base_handler default: graph/state/csv keys are readable off the result."""
        event = {"graph": "my_graph", "state": {"k": "v"}, "csv": "workflow.csv"}
        _, data = self.parser.parse(event)

        self.assertEqual(data.get("graph"), "my_graph")
        self.assertEqual(data.get("state"), {"k": "v"})
        self.assertEqual(data.get("csv"), "workflow.csv")

    def test_fallback_does_not_mutate_caller_event_when_merging_path_parameters(self):
        """Regression guard: safe_json_loads() passes non-str bodies through by
        reference, so merging pathParameters into that dict must not mutate
        the original event dict in place."""
        event = {
            "graph": "my_graph",
            "state": {},
            "pathParameters": {"injected": "value"},
        }
        original_event_copy = dict(event)

        _, data = self.parser.parse(event)

        self.assertEqual(data.get("injected"), "value")
        # The source event must be unchanged (no aliasing into event itself).
        self.assertNotIn("injected", event)
        self.assertEqual(event, original_event_copy)

    def test_fallback_non_dict_json_array_body_does_not_raise(self):
        """TD-047: safe_json_loads() returns whatever json.loads() yields for
        a JSON string body, including a bare list for a JSON array body.
        Coercing that directly via dict(...) raises TypeError; the fallback
        must instead wrap it under a "raw" key.

        Counter-factual: pre-fix, dict(safe_json_loads(body)) raised
        ``TypeError: cannot convert dictionary update sequence element #0
        to a sequence`` for this exact input.
        """
        event = {"body": "[1, 2, 3]"}

        trigger_type, data = self.parser.parse(event)

        self.assertEqual(trigger_type, TriggerType.HTTP)
        self.assertEqual(data, {"raw": [1, 2, 3]})

    def test_fallback_non_dict_json_scalar_body_does_not_raise(self):
        """TD-047: a JSON scalar body (e.g. a bare number) must also be
        wrapped, not raise, at this external-input deserialization boundary."""
        event = {"body": "42"}

        _, data = self.parser.parse(event)

        self.assertEqual(data, {"raw": 42})


if __name__ == "__main__":
    unittest.main()
