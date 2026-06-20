"""
Unit tests for E06-F04: Graph Progress Streaming via Runtime Facade.

Test classes in this file:
  - TestWorkflowProgressEventModel — data model field-contract assertions (T-E06-F04-002)
  - TestAstreamShapeSmoke — TC-F04-D9 (T-E06-F04-001)

TC-F04-D9: Empirically verify that LangGraph's .astream(stream_mode="updates")
on the installed langgraph version (1.0.5, per epic A2 / engineering-context §B)
yields one {node_name: state_delta_dict} mapping per completed super-step.

PURPOSE: The architect could not run Python during spec authoring. This test
documents the confirmed real output shape so that T-E06-F04-002 through T-E06-F04-005
implement against empirically verified behavior rather than assumptions.

CONFIRMED SHAPE (langgraph==1.0.5, observed in TC-F04-D9):
  - Each iteration yields one dict: {node_name: state_delta_dict}
  - node_name is a str (the name of the completed node)
  - state_delta_dict is a dict (only the keys the node returned — NOT the full graph state)
  - A 2-node linear graph produces exactly 2 updates, one per node, in execution order
  - Shape is NOT the "values" stream_mode (which yields full accumulated state each step)
  - Each update dict has exactly 1 key (one node per super-step in a linear graph)

FORBIDDEN MOCKS:
  - Do NOT mock LangGraph's .astream() — the whole point is to verify the installed
    langgraph behavior against the real engine.
  - Node implementations may be simple sync functions that return dicts.

CALLER-PATH CONTRACT (per test-plan §TC-F04-D9):
  Entrypoint: executable_graph.astream(initial_state, config=config, stream_mode="updates")
  Lowest allowed mock seam: node implementations (returning dicts)
  Forbidden mocks: LangGraph .astream() itself

COUNTER-FACTUAL:
  A langgraph version that changes stream_mode="updates" to yield full state instead
  of {node_name: delta} would fail the assertIn(node_name, update_dict) shape assertion.
  A mode that yields lists/tuples would fail the assertIsInstance(update, dict) check.

Framework: unittest.IsolatedAsyncioTestCase for async tests.
"""

import dataclasses
import unittest
from importlib.metadata import version
from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import END, StateGraph

# ---------------------------------------------------------------------------
# TestWorkflowProgressEventModel — field-contract assertions (T-E06-F04-002)
# ---------------------------------------------------------------------------


class TestWorkflowProgressEventModel(unittest.TestCase):
    """Field-contract assertions for WorkflowProgressEvent (spec.md §3.3, AC-1).

    ENTRYPOINT (internal): WorkflowProgressEvent(...) constructor, called directly.

    Internal-only entrypoint is justified here: this test class validates the
    data-model contract (field names, types, defaults, mutability) — not a
    service method or facade boundary. The dataclass itself IS the entrypoint.

    LOWEST ALLOWED MOCK SEAM: none — the dataclass is the production object; no
    mocking is appropriate for a data-only struct.

    FORBIDDEN MOCKS: none to specify; all assertions use the real constructor.

    COUNTER-FACTUAL:
      An impl missing the 'sequence' field would raise TypeError on construction.
      An impl with frozen=True would raise FrozenInstanceError on sequence mutation.
      An impl with 'node_name' as a required field (no default) would raise TypeError
      when constructing a terminal event without node_name.
      An impl that imports LLMStreamChunk or call_llm_stream_async would be caught
      by test_model_does_not_import_llm_streaming_symbols (white-box AC-9 check).
    """

    def _make_node_progress_event(self, **kwargs: Any) -> Any:
        """Construct a node_progress WorkflowProgressEvent.

        Uses the production constructor signature — event_type, sequence,
        is_terminal are positional-equivalent (required); optional fields default
        to None.  This is the PRODUCTION CALLER SHAPE: no convenience kwargs that
        production never passes.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        defaults: Dict[str, Any] = {
            "event_type": "node_progress",
            "sequence": 0,
            "is_terminal": False,
            "node_name": "some_node",
            "state_delta": {"output": "val"},
        }
        defaults.update(kwargs)
        return WorkflowProgressEvent(**defaults)

    def _make_terminal_event(self, event_type: str = "completed", **kwargs: Any) -> Any:
        """Construct a terminal WorkflowProgressEvent.

        Omits node_name, state_delta, and node_duration (must default to None).
        result is passed explicitly so the terminal contract can be asserted.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        defaults: Dict[str, Any] = {
            "event_type": event_type,
            "sequence": 1,
            "is_terminal": True,
            "result": {"success": True, "outputs": {}},
        }
        defaults.update(kwargs)
        return WorkflowProgressEvent(**defaults)

    # ------------------------------------------------------------------
    # Import surface — AC-1 (importable from agentmap.models.execution)
    # ------------------------------------------------------------------

    def test_importable_from_agentmap_models_execution(self) -> None:
        """WorkflowProgressEvent is importable from agentmap.models.execution.

        COUNTER-FACTUAL: An impl that puts the class in the wrong package or omits
        the __init__.py export would raise ImportError here.
        """
        # Arrange + Act
        from agentmap.models.execution import WorkflowProgressEvent  # noqa: F401

        # Assert: import succeeded (no ImportError)
        self.assertTrue(True)

    # ------------------------------------------------------------------
    # Required fields — AC-1 field table (§3.3)
    # ------------------------------------------------------------------

    def test_required_fields_present_on_node_progress_event(self) -> None:
        """event_type, sequence, is_terminal are present and hold correct values.

        COUNTER-FACTUAL: An impl that spells 'sequence' as 'seq' or omits
        'is_terminal' would raise AttributeError on the field access.
        """
        event = self._make_node_progress_event()

        self.assertEqual(event.event_type, "node_progress")
        self.assertEqual(event.sequence, 0)
        self.assertFalse(event.is_terminal)

    def test_node_name_field_present_on_node_progress_event(self) -> None:
        """node_name is present and carries the node name string.

        COUNTER-FACTUAL: An impl that names the field 'name' or omits it would
        raise AttributeError.
        """
        event = self._make_node_progress_event(node_name="my_node")
        self.assertEqual(event.node_name, "my_node")

    def test_state_delta_field_present_on_node_progress_event(self) -> None:
        """state_delta is present and carries the node's output dict.

        COUNTER-FACTUAL: An impl that names the field 'delta' or omits it would
        raise AttributeError.
        """
        delta: Dict[str, Any] = {"output": "result", "count": 42}
        event = self._make_node_progress_event(state_delta=delta)
        self.assertEqual(event.state_delta, delta)

    def test_node_duration_field_present_and_defaults_to_none(self) -> None:
        """node_duration field exists and defaults to None when not provided.

        COUNTER-FACTUAL: An impl that omits node_duration or makes it required
        would fail here — either AttributeError or TypeError on construction.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        event = WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
        )
        self.assertIsNone(event.node_duration)

    def test_result_field_present_and_defaults_to_none(self) -> None:
        """result field exists and defaults to None when not provided.

        COUNTER-FACTUAL: An impl that omits result or makes it required would
        fail here — AttributeError or TypeError.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        event = WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
        )
        self.assertIsNone(event.result)

    def test_error_field_present_and_defaults_to_none(self) -> None:
        """error field exists and defaults to None when not provided.

        COUNTER-FACTUAL: An impl that omits error or names it 'err' would raise
        AttributeError.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        event = WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
        )
        self.assertIsNone(event.error)

    # ------------------------------------------------------------------
    # Optional fields default to None — §3.3 "Optional fields default to None"
    # ------------------------------------------------------------------

    def test_optional_fields_all_default_to_none_when_omitted(self) -> None:
        """All five optional fields (node_name, state_delta, node_duration, result, error)
        default to None when constructed without them.

        COUNTER-FACTUAL: An impl where any optional field is required (no default)
        would raise TypeError on the bare-minimum construction call.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        # Minimal construction — only required fields
        event = WorkflowProgressEvent(
            event_type="completed",
            sequence=1,
            is_terminal=True,
        )

        self.assertIsNone(event.node_name)
        self.assertIsNone(event.state_delta)
        self.assertIsNone(event.node_duration)
        self.assertIsNone(event.result)
        self.assertIsNone(event.error)

    # ------------------------------------------------------------------
    # Terminal event field contract — §3.3 "Terminal-only fields absent on non-final"
    # ------------------------------------------------------------------

    def test_terminal_event_is_terminal_true_and_node_name_none(self) -> None:
        """Terminal event: is_terminal == True; node_name, state_delta are None.

        COUNTER-FACTUAL: An impl where is_terminal defaults to False and cannot
        be set to True would fail the is_terminal assertion.
        """
        event = self._make_terminal_event()

        self.assertTrue(event.is_terminal)
        self.assertIsNone(event.node_name)
        self.assertIsNone(event.state_delta)

    def test_terminal_event_carries_result_dict(self) -> None:
        """Terminal event: result field holds the execution result dict.

        COUNTER-FACTUAL: An impl that assigns result to a different field name
        would leave result=None and fail the assertIsNotNone.
        """
        result_payload: Dict[str, Any] = {
            "success": True,
            "outputs": {"answer": "42"},
        }
        event = self._make_terminal_event(result=result_payload)
        self.assertIsNotNone(event.result)
        self.assertEqual(event.result["success"], True)

    def test_terminal_event_types_accepted(self) -> None:
        """event_type accepts all three terminal values: completed, failed, suspended.

        COUNTER-FACTUAL: An impl that validates event_type against an enum and
        rejects 'failed'/'suspended' would raise on construction.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        for etype in ("completed", "failed", "suspended"):
            with self.subTest(event_type=etype):
                event = WorkflowProgressEvent(
                    event_type=etype,
                    sequence=2,
                    is_terminal=True,
                )
                self.assertEqual(event.event_type, etype)

    def test_failed_terminal_event_carries_error(self) -> None:
        """Failed terminal event: error field carries the error string.

        COUNTER-FACTUAL: An impl where error is not a field would raise
        AttributeError; one where it's read-only would fail on assignment.
        """
        event = self._make_terminal_event(
            event_type="failed",
            error="Graph node raised ValueError",
        )
        self.assertEqual(event.event_type, "failed")
        self.assertEqual(event.error, "Graph node raised ValueError")

    # ------------------------------------------------------------------
    # Mutability — §3.3 "Non-frozen dataclass; mutable sequence assignment works"
    # ------------------------------------------------------------------

    def test_sequence_is_mutable_after_construction(self) -> None:
        """sequence field can be assigned after construction (non-frozen dataclass).

        COUNTER-FACTUAL: An impl with frozen=True would raise
        dataclasses.FrozenInstanceError on the sequence assignment.
        """
        event = self._make_node_progress_event(sequence=0)
        event.sequence = 5  # must not raise
        self.assertEqual(event.sequence, 5)

    def test_event_type_is_mutable_after_construction(self) -> None:
        """event_type can be reassigned (non-frozen).

        Confirms the class is a plain mutable dataclass, consistent with
        LLMStreamChunk and ExecutionResult (spec §3.3 deviation note).
        """
        event = self._make_node_progress_event()
        event.event_type = "completed"  # must not raise
        self.assertEqual(event.event_type, "completed")

    # ------------------------------------------------------------------
    # Type integrity — §3.3 field table types
    # ------------------------------------------------------------------

    def test_event_is_a_dataclass(self) -> None:
        """WorkflowProgressEvent is a dataclass (not a plain class or NamedTuple).

        COUNTER-FACTUAL: An impl using a plain class without @dataclass would
        still be constructable but would fail dataclasses.is_dataclass().
        """
        from agentmap.models.execution import WorkflowProgressEvent

        event = WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
        )
        self.assertTrue(dataclasses.is_dataclass(event))

    def test_state_delta_accepts_dict_with_any_value_types(self) -> None:
        """state_delta accepts Dict[str, Any] — nested dicts and mixed types.

        COUNTER-FACTUAL: A narrowly typed impl that rejects Dict with int values
        would raise TypeError on construction.
        """
        delta: Dict[str, Any] = {
            "output": "text",
            "count": 42,
            "nested": {"key": "val"},
        }
        event = self._make_node_progress_event(state_delta=delta)
        self.assertEqual(event.state_delta["count"], 42)
        self.assertEqual(event.state_delta["nested"]["key"], "val")

    def test_node_duration_accepts_float(self) -> None:
        """node_duration accepts a float (seconds).

        COUNTER-FACTUAL: An impl typed as int-only would coerce or reject floats.
        """
        event = self._make_node_progress_event(node_duration=1.234)
        self.assertAlmostEqual(event.node_duration, 1.234)

    # ------------------------------------------------------------------
    # White-box: no LLM streaming imports — AC-9 / DRIFT-01 / TD-026
    # ------------------------------------------------------------------

    def test_model_does_not_import_llm_streaming_symbols(self) -> None:
        """progress_event.py must not import LLMStreamChunk or call_llm_stream_async.

        This is the white-box AC-9 assertion from spec.md §3.3:
          'No import of LLMStreamChunk, call_llm_stream_async, or any LLM streaming symbol'

        COUNTER-FACTUAL: An impl that accidentally re-exported or imported
        LLMStreamChunk in progress_event.py would be caught here; the import
        itself would still succeed (not raise), but the string check would fail.
        """
        import pathlib

        source_path = (
            pathlib.Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "agentmap"
            / "models"
            / "execution"
            / "progress_event.py"
        )
        self.assertTrue(
            source_path.exists(), f"progress_event.py not found at {source_path}"
        )
        source_text = source_path.read_text(encoding="utf-8")

        self.assertNotIn(
            "LLMStreamChunk",
            source_text,
            "progress_event.py must not import LLMStreamChunk (AC-9 / DRIFT-01)",
        )
        self.assertNotIn(
            "call_llm_stream_async",
            source_text,
            "progress_event.py must not import call_llm_stream_async (AC-9 / DRIFT-01)",
        )


# ---------------------------------------------------------------------------
# Minimal state schema for the smoke check
# ---------------------------------------------------------------------------


class _SmokecheckState(TypedDict):
    """Minimal TypedDict state for the D-9 smoke check graph.

    Uses Optional fields so that initial_state does not need to pre-populate
    all output slots — only 'input' is required for the first node.
    """

    input: str
    node1_out: Optional[str]
    node2_out: Optional[str]


# ---------------------------------------------------------------------------
# TC-F04-D9 — .astream(stream_mode="updates") produces {node_name: delta} per node
# ---------------------------------------------------------------------------


class TestAstreamShapeSmoke(unittest.IsolatedAsyncioTestCase):
    """TC-F04-D9 — smoke check: verify .astream(stream_mode="updates") output shape.

    Builds a real minimal 2-node LangGraph compiled graph and iterates
    .astream(stream_mode="updates") to confirm the actual output shape on the
    installed langgraph 1.0.5.  No mocking of the LangGraph engine.

    CONFIRMED SHAPE documented here for T-E06-F04-002 through T-E06-F04-005:
      Each yielded item is a dict {node_name: state_delta_dict} where:
      - node_name: str  — the name of the completed node
      - state_delta_dict: dict — only the keys that node returned, NOT full state
      Total updates for a 2-node linear graph: exactly 2 (one per completed node)
    """

    def setUp(self) -> None:
        """Build a minimal 2-node linear LangGraph compiled graph."""
        self.langgraph_version = version("langgraph")

        # Node implementations — sync functions returning dicts (real node outputs)
        def _node1(state: _SmokecheckState) -> dict:
            return {"node1_out": f"result_from_node1 (input={state['input']})"}

        def _node2(state: _SmokecheckState) -> dict:
            return {"node2_out": "result_from_node2"}

        # Build and compile the graph using real LangGraph
        builder: StateGraph = StateGraph(_SmokecheckState)
        builder.add_node("node1", _node1)
        builder.add_node("node2", _node2)
        builder.set_entry_point("node1")
        builder.add_edge("node1", "node2")
        builder.add_edge("node2", END)

        # compiled graph — .astream() is the real LangGraph method, NOT mocked
        self.compiled_graph = builder.compile()

        self.initial_state = {
            "input": "hello",
            "node1_out": None,
            "node2_out": None,
        }

    # ------------------------------------------------------------------
    # TC-F04-D9-1: each update is a dict
    # ------------------------------------------------------------------

    async def test_astream_updates_each_item_is_a_dict(self) -> None:
        """TC-F04-D9-1: every item yielded by astream(stream_mode='updates') is a dict.

        Verifies the shape is dict, NOT a list, tuple, or other type.
        Failure of this test means the 'updates' stream_mode was changed or is
        unavailable on the installed langgraph version.
        """
        updates = []
        async for update in self.compiled_graph.astream(
            self.initial_state, config=None, stream_mode="updates"
        ):
            updates.append(update)

        self.assertGreater(len(updates), 0, "Expected at least one update from astream")
        for i, update in enumerate(updates):
            with self.subTest(update_index=i):
                self.assertIsInstance(
                    update,
                    dict,
                    f"update[{i}] must be a dict, got {type(update).__name__!r}"
                    f" — SHAPE CHANGE ALERT: langgraph {self.langgraph_version}"
                    f" stream_mode='updates' no longer yields dicts",
                )

    # ------------------------------------------------------------------
    # TC-F04-D9-2: each update has string keys mapping to dict values
    # ------------------------------------------------------------------

    async def test_astream_updates_keys_are_node_names_values_are_state_dicts(
        self,
    ) -> None:
        """TC-F04-D9-2: each update dict has str keys (node names) -> dict values (state deltas).

        CONFIRMED SHAPE: {node_name: state_delta_dict} where both parts are dicts.
        Failure means the nested structure changed, e.g., the delta is now a list
        or a state snapshot object rather than a plain dict.
        """
        updates = []
        async for update in self.compiled_graph.astream(
            self.initial_state, config=None, stream_mode="updates"
        ):
            updates.append(update)

        for i, update in enumerate(updates):
            with self.subTest(update_index=i):
                for key, value in update.items():
                    self.assertIsInstance(
                        key,
                        str,
                        f"update[{i}] key must be a str (node name), got {type(key).__name__!r}",
                    )
                    self.assertIsInstance(
                        value,
                        dict,
                        f"update[{i}][{key!r}] must be a dict (state delta),"
                        f" got {type(value).__name__!r}"
                        f" — langgraph {self.langgraph_version}",
                    )

    # ------------------------------------------------------------------
    # TC-F04-D9-3: 2-node linear graph produces exactly 2 updates
    # ------------------------------------------------------------------

    async def test_astream_updates_2_node_graph_produces_exactly_2_updates(
        self,
    ) -> None:
        """TC-F04-D9-3: a 2-node linear graph produces exactly 2 updates.

        Confirms one update per completed node (NOT one update for the full graph
        nor one update per state field).  If a future langgraph version emits a
        single 'merged' update for all nodes, this test would fail with count=1.
        """
        updates = []
        async for update in self.compiled_graph.astream(
            self.initial_state, config=None, stream_mode="updates"
        ):
            updates.append(update)

        self.assertEqual(
            len(updates),
            2,
            f"Expected exactly 2 updates for a 2-node linear graph,"
            f" got {len(updates)}"
            f" — SHAPE CHANGE ALERT: langgraph {self.langgraph_version}"
            f" may have changed per-node vs per-step granularity",
        )

    # ------------------------------------------------------------------
    # TC-F04-D9-4: node names appear in execution order
    # ------------------------------------------------------------------

    async def test_astream_updates_node_names_in_execution_order(self) -> None:
        """TC-F04-D9-4: updates arrive with node1 first, node2 second.

        Confirms ordered delivery matching graph execution topology.
        update[0] must contain 'node1' as its sole key;
        update[1] must contain 'node2' as its sole key.
        """
        updates = []
        async for update in self.compiled_graph.astream(
            self.initial_state, config=None, stream_mode="updates"
        ):
            updates.append(update)

        self.assertEqual(len(updates), 2)
        self.assertIn(
            "node1",
            updates[0],
            f"Expected 'node1' in updates[0], got keys={list(updates[0].keys())}"
            f" — langgraph {self.langgraph_version}",
        )
        self.assertIn(
            "node2",
            updates[1],
            f"Expected 'node2' in updates[1], got keys={list(updates[1].keys())}"
            f" — langgraph {self.langgraph_version}",
        )

    # ------------------------------------------------------------------
    # TC-F04-D9-5: each update contains ONLY the delta keys (not full state)
    # ------------------------------------------------------------------

    async def test_astream_updates_delta_contains_only_returned_keys(self) -> None:
        """TC-F04-D9-5: each node's delta dict contains only the keys that node returned.

        node1 returns only 'node1_out'; its delta must NOT contain 'node2_out'.
        node2 returns only 'node2_out'; its delta must NOT contain 'node1_out' or 'input'.

        This distinguishes stream_mode='updates' (delta) from stream_mode='values'
        (full accumulated state).  The downstream F04 implementation relies on deltas
        being sparse — consuming the full accumulated state instead of deltas would
        violate the Constraint C1 materialized-state contract assumptions.
        """
        updates = []
        async for update in self.compiled_graph.astream(
            self.initial_state, config=None, stream_mode="updates"
        ):
            updates.append(update)

        self.assertEqual(len(updates), 2)

        # node1's delta: only 'node1_out', NOT 'input' or 'node2_out'
        delta_node1 = updates[0]["node1"]
        self.assertIn(
            "node1_out",
            delta_node1,
            "node1's delta must contain 'node1_out'",
        )
        self.assertNotIn(
            "input",
            delta_node1,
            "node1's delta must NOT contain 'input' (stream_mode='updates' yields"
            " delta, not full state) — SHAPE CHANGE: may have switched to 'values' mode",
        )
        self.assertNotIn(
            "node2_out",
            delta_node1,
            "node1's delta must NOT contain 'node2_out' (that key is node2's output)",
        )

        # node2's delta: only 'node2_out', NOT 'input' or 'node1_out'
        delta_node2 = updates[1]["node2"]
        self.assertIn(
            "node2_out",
            delta_node2,
            "node2's delta must contain 'node2_out'",
        )
        self.assertNotIn(
            "input",
            delta_node2,
            "node2's delta must NOT contain 'input'",
        )
        self.assertNotIn(
            "node1_out",
            delta_node2,
            "node2's delta must NOT contain 'node1_out'",
        )

    # ------------------------------------------------------------------
    # TC-F04-D9-6: each update has exactly one key (one node per super-step)
    # ------------------------------------------------------------------

    async def test_astream_updates_each_update_has_exactly_one_node_key(
        self,
    ) -> None:
        """TC-F04-D9-6: in a linear (non-parallel) graph, each update has exactly 1 key.

        A parallel graph might yield multiple node names in a single update (one per
        concurrent super-step).  For a linear 2-node graph the invariant is 1 key.

        This is the load-bearing shape fact for the F04 implementation:
        stream_compiled_graph_async iterates updates and unpacks {node_name: delta}
        assuming exactly one key per update in linear topologies.  The implementation
        must handle the general case (parallel), but the smoke check uses a linear
        graph as the simplest valid test.
        """
        updates = []
        async for update in self.compiled_graph.astream(
            self.initial_state, config=None, stream_mode="updates"
        ):
            updates.append(update)

        for i, update in enumerate(updates):
            with self.subTest(update_index=i):
                self.assertEqual(
                    len(update),
                    1,
                    f"update[{i}] must have exactly 1 key in a linear graph,"
                    f" got {len(update)} keys: {list(update.keys())}"
                    f" — langgraph {self.langgraph_version}",
                )

    # ------------------------------------------------------------------
    # TC-F04-D9-7: delta values contain the exact content the node returned
    # ------------------------------------------------------------------

    async def test_astream_updates_delta_values_match_node_return(self) -> None:
        """TC-F04-D9-7: delta dict values match the dict returned by the node function.

        node1 returns {'node1_out': 'result_from_node1 (input=hello)'}.
        The delta in the update must contain that exact value.
        """
        updates = []
        async for update in self.compiled_graph.astream(
            self.initial_state, config=None, stream_mode="updates"
        ):
            updates.append(update)

        self.assertEqual(len(updates), 2)
        node1_delta = updates[0]["node1"]
        self.assertEqual(
            node1_delta.get("node1_out"),
            "result_from_node1 (input=hello)",
            f"node1 delta value mismatch: {node1_delta}",
        )

        node2_delta = updates[1]["node2"]
        self.assertEqual(
            node2_delta.get("node2_out"),
            "result_from_node2",
            f"node2 delta value mismatch: {node2_delta}",
        )


if __name__ == "__main__":
    unittest.main()
