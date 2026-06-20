"""
Unit tests for E06-F04: Graph Progress Streaming via Runtime Facade.

Test classes in this file:
  - TestWorkflowProgressEventModel — data model field-contract assertions (T-E06-F04-002)
  - TestAstreamShapeSmoke — TC-F04-D9 (T-E06-F04-001)
  - TestAssembleForAsyncRunHelper — TC-F04-010 regression gate (T-E06-F04-003)

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
import inspect
import unittest
from importlib.metadata import version
from typing import Any, Dict, Optional, Tuple, TypedDict
from unittest.mock import AsyncMock, MagicMock, create_autospec

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


# ---------------------------------------------------------------------------
# Shared helpers for TestAssembleForAsyncRunHelper
# ---------------------------------------------------------------------------


def _make_mock_bundle_for_assembly(
    graph_name: str = "test_graph",
    node_count: int = 2,
    checkpoint: bool = False,
) -> MagicMock:
    """Create a minimal mock GraphBundle for assembly helper tests."""
    bundle = MagicMock(name="mock_bundle")
    bundle.graph_name = graph_name
    nodes: Dict[str, MagicMock] = {}
    for i in range(node_count):
        node = MagicMock()
        node.agent_type = "default"
        nodes[f"node_{i}"] = node
    bundle.nodes = nodes
    bundle.entry_point = "node_0"
    bundle.csv_hash = None
    bundle.node_instances = None
    bundle.scoped_registry = None
    bundle.missing_services = set()
    return bundle


def _make_graph_runner_for_assembly(
    checkpoint: bool = False,
) -> Tuple[Any, Dict[str, Any]]:
    """Create a GraphRunnerService with all dependencies mocked.

    Returns:
        (service, mocks_dict)
    """
    from agentmap.services.config.app_config_service import AppConfigService
    from agentmap.services.declaration_registry_service import (
        DeclarationRegistryService,
    )
    from agentmap.services.execution_tracking_service import ExecutionTrackingService
    from agentmap.services.graph.graph_agent_instantiation_service import (
        GraphAgentInstantiationService,
    )
    from agentmap.services.graph.graph_assembly_service import GraphAssemblyService
    from agentmap.services.graph.graph_bootstrap_service import GraphBootstrapService
    from agentmap.services.graph.graph_bundle_service import GraphBundleService
    from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
    from agentmap.services.graph.graph_execution_service import GraphExecutionService
    from agentmap.services.graph.graph_runner_service import GraphRunnerService
    from agentmap.services.interaction_handler_service import InteractionHandlerService
    from agentmap.services.logging_service import LoggingService

    mock_app_config = create_autospec(AppConfigService, instance=True)
    mock_bootstrap = create_autospec(GraphBootstrapService, instance=True)
    mock_instantiation = create_autospec(GraphAgentInstantiationService, instance=True)
    mock_assembly = create_autospec(GraphAssemblyService, instance=True)
    mock_execution = create_autospec(GraphExecutionService, instance=True)
    mock_tracking = create_autospec(ExecutionTrackingService, instance=True)
    mock_logging = create_autospec(LoggingService, instance=True)
    mock_logging.get_class_logger.return_value = MagicMock(name="mock_logger")
    mock_interaction = create_autospec(InteractionHandlerService, instance=True)
    mock_checkpoint = create_autospec(GraphCheckpointService, instance=True)
    mock_bundle_svc = create_autospec(GraphBundleService, instance=True)
    mock_declaration = create_autospec(DeclarationRegistryService, instance=True)

    service = GraphRunnerService(
        app_config_service=mock_app_config,
        graph_bootstrap_service=mock_bootstrap,
        graph_agent_instantiation_service=mock_instantiation,
        graph_assembly_service=mock_assembly,
        graph_execution_service=mock_execution,
        execution_tracking_service=mock_tracking,
        logging_service=mock_logging,
        interaction_handler_service=mock_interaction,
        graph_checkpoint_service=mock_checkpoint,
        graph_bundle_service=mock_bundle_svc,
        declaration_registry_service=mock_declaration,
    )

    mocks = {
        "app_config": mock_app_config,
        "instantiation": mock_instantiation,
        "assembly": mock_assembly,
        "execution": mock_execution,
        "tracking": mock_tracking,
        "logging": mock_logging,
        "bundle_svc": mock_bundle_svc,
        "declaration": mock_declaration,
        "interaction": mock_interaction,
        "checkpoint": mock_checkpoint,
    }

    # Common setup: scoped registry, tracker, agent instantiation
    mock_scoped_registry = MagicMock()
    mock_scoped_registry.get_all_agent_types.return_value = ["agent1"]
    mock_scoped_registry.get_all_service_names.return_value = []
    mock_declaration.create_scoped_registry_for_bundle.return_value = (
        mock_scoped_registry
    )

    mock_tracker = MagicMock()
    mock_tracker.thread_id = "test-thread-id"
    mock_tracking.create_tracker.return_value = mock_tracker

    node_instances = {"node_0": MagicMock(), "node_1": MagicMock()}
    bundle_with_instances = MagicMock()
    bundle_with_instances.graph_name = "test_graph"
    bundle_with_instances.nodes = {"node_0": MagicMock(), "node_1": MagicMock()}
    bundle_with_instances.entry_point = "node_0"
    bundle_with_instances.node_instances = node_instances

    def _instantiate_side_effect(b, tracker):
        b.node_instances = node_instances
        return bundle_with_instances

    mock_instantiation.instantiate_agents.side_effect = _instantiate_side_effect

    mock_compiled = MagicMock()
    mock_bundle_svc.requires_checkpoint_support.return_value = checkpoint
    mocks["bundle_svc"].requires_checkpoint_support.return_value = checkpoint

    if checkpoint:
        mock_assembly.assemble_with_checkpoint_async.return_value = mock_compiled
    else:
        mock_assembly.assemble_graph_async.return_value = mock_compiled

    mocks["mock_compiled"] = mock_compiled
    mocks["mock_tracker"] = mock_tracker
    mocks["bundle_with_instances"] = bundle_with_instances

    return service, mocks


# ---------------------------------------------------------------------------
# TC-F04-010 — TestAssembleForAsyncRunHelper (T-E06-F04-003)
# ---------------------------------------------------------------------------


class TestAssembleForAsyncRunHelper(unittest.IsolatedAsyncioTestCase):
    """TC-F04-010: Regression gate — _assemble_for_async_run extracted from _run_core_async.

    ENTRYPOINT:
      Direct call to GraphRunnerService._assemble_for_async_run(bundle, initial_state,
      validate_agents) — internal-only unit test justified because this is explicitly
      the unit being extracted (T-E06-F04-003 goal: verify helper returns same
      assembly as _run_core_async phases 2-5).

    LOWEST ALLOWED MOCK SEAM:
      GraphAssemblyService, GraphAgentInstantiationService, ExecutionTrackingService,
      DeclarationRegistryService, GraphBundleService — all mocked via create_autospec.

    FORBIDDEN MOCKS:
      Do NOT mock _assemble_for_async_run itself; must call it for real.
      Do NOT route through _run_core_async for phase extraction verification.

    COUNTER-FACTUAL:
      An impl that does not extract the helper would raise AttributeError on
      service._assemble_for_async_run(...) — the method simply would not exist.
      An impl that extracts the helper but _run_core_async still duplicates phases 2-5
      would fail the structural-body assertion checking for _assemble_for_async_run
      in _run_core_async source.
      An impl that accidentally makes _run_core_async reference run_stream_async or
      stream_compiled_graph_async would fail the non-reference body assertion.
    """

    # ------------------------------------------------------------------
    # TC-F04-010-1: _assemble_for_async_run exists on GraphRunnerService
    # ------------------------------------------------------------------

    def test_assemble_for_async_run_method_exists(self) -> None:
        """_assemble_for_async_run is a method on GraphRunnerService.

        COUNTER-FACTUAL: A pre-refactor impl without extraction would raise
        AttributeError or return False from hasattr.
        """
        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        self.assertTrue(
            hasattr(GraphRunnerService, "_assemble_for_async_run"),
            "GraphRunnerService must have a _assemble_for_async_run method "
            "(D-7 extract — T-E06-F04-003); it was not found",
        )

    # ------------------------------------------------------------------
    # TC-F04-010-2: helper accepts (bundle, initial_state, validate_agents) args
    # ------------------------------------------------------------------

    def test_assemble_for_async_run_signature(self) -> None:
        """_assemble_for_async_run accepts (self, bundle, initial_state, validate_agents).

        COUNTER-FACTUAL: An impl with wrong parameter names/order would fail
        the signature.parameters assertion.
        """
        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        sig = inspect.signature(GraphRunnerService._assemble_for_async_run)
        params = list(sig.parameters.keys())
        # Must have 'bundle', 'initial_state', 'validate_agents' (and 'self')
        self.assertIn(
            "bundle",
            params,
            f"_assemble_for_async_run must have 'bundle' parameter; got {params}",
        )
        self.assertIn(
            "initial_state",
            params,
            f"_assemble_for_async_run must have 'initial_state' parameter; got {params}",
        )
        self.assertIn(
            "validate_agents",
            params,
            f"_assemble_for_async_run must have 'validate_agents' parameter; got {params}",
        )

    # ------------------------------------------------------------------
    # TC-F04-010-3: helper returns a 4-tuple
    # ------------------------------------------------------------------

    async def test_assemble_for_async_run_returns_4_tuple(self) -> None:
        """_assemble_for_async_run returns (executable_graph, execution_tracker,
        execution_config, requires_checkpoint) as a 4-element tuple.

        COUNTER-FACTUAL: An impl that returns 3 or 5 elements, or a dict,
        would fail the len(result) == 4 assertion.
        """
        service, mocks = _make_graph_runner_for_assembly(checkpoint=False)
        bundle = _make_mock_bundle_for_assembly()

        result = await service._assemble_for_async_run(
            bundle=bundle,
            initial_state={"input": "hello"},
            validate_agents=False,
        )

        self.assertIsInstance(
            result,
            tuple,
            f"_assemble_for_async_run must return a tuple, got {type(result).__name__!r}",
        )
        self.assertEqual(
            len(result),
            4,
            f"_assemble_for_async_run must return a 4-tuple "
            f"(executable_graph, execution_tracker, execution_config, requires_checkpoint), "
            f"got {len(result)} elements",
        )

    # ------------------------------------------------------------------
    # TC-F04-010-4: non-checkpoint path returns correct tuple elements
    # ------------------------------------------------------------------

    async def test_assemble_for_async_run_non_checkpoint_path(self) -> None:
        """Non-checkpoint path: returns (compiled_graph, tracker, None, False).

        executable_graph is the return value of assemble_graph_async.
        execution_config is None (no thread_id config needed).
        requires_checkpoint is False.

        COUNTER-FACTUAL: An impl that always uses the checkpoint path would
        call assemble_with_checkpoint_async and set requires_checkpoint=True,
        failing the assertFalse(requires_checkpoint).
        """
        service, mocks = _make_graph_runner_for_assembly(checkpoint=False)
        bundle = _make_mock_bundle_for_assembly()

        executable_graph, execution_tracker, execution_config, requires_checkpoint = (
            await service._assemble_for_async_run(
                bundle=bundle,
                initial_state={"input": "hello"},
                validate_agents=False,
            )
        )

        # executable_graph must be what assemble_graph_async returned
        self.assertIs(
            executable_graph,
            mocks["mock_compiled"],
            "executable_graph must be the return value of assemble_graph_async",
        )
        # execution_tracker must be what create_tracker returned
        self.assertIs(
            execution_tracker,
            mocks["mock_tracker"],
            "execution_tracker must be the return value of create_tracker()",
        )
        # execution_config is None for non-checkpoint runs
        self.assertIsNone(
            execution_config,
            "execution_config must be None for non-checkpoint runs",
        )
        # requires_checkpoint must be False
        self.assertFalse(
            requires_checkpoint,
            "requires_checkpoint must be False for non-checkpoint runs",
        )

    # ------------------------------------------------------------------
    # TC-F04-010-5: checkpoint path returns (compiled_graph, tracker, config, True)
    # ------------------------------------------------------------------

    async def test_assemble_for_async_run_checkpoint_path(self) -> None:
        """Checkpoint path: returns (compiled_graph, tracker, config, True).

        execution_config must contain configurable.thread_id.
        requires_checkpoint is True.

        COUNTER-FACTUAL: An impl that ignores the checkpoint flag would always
        return execution_config=None, failing the assertIsNotNone assertion.
        """
        service, mocks = _make_graph_runner_for_assembly(checkpoint=True)
        bundle = _make_mock_bundle_for_assembly()

        executable_graph, execution_tracker, execution_config, requires_checkpoint = (
            await service._assemble_for_async_run(
                bundle=bundle,
                initial_state={"input": "hello"},
                validate_agents=False,
            )
        )

        self.assertIs(
            executable_graph,
            mocks["mock_compiled"],
            "executable_graph must be the return value of assemble_with_checkpoint_async",
        )
        self.assertIs(
            execution_tracker,
            mocks["mock_tracker"],
            "execution_tracker must be the return value of create_tracker()",
        )
        self.assertIsNotNone(
            execution_config,
            "execution_config must not be None for checkpoint runs",
        )
        self.assertIn(
            "configurable",
            execution_config,
            "execution_config must have 'configurable' key for checkpoint runs",
        )
        self.assertIn(
            "thread_id",
            execution_config["configurable"],
            "execution_config['configurable'] must have 'thread_id'",
        )
        self.assertTrue(
            requires_checkpoint,
            "requires_checkpoint must be True for checkpoint runs",
        )

    # ------------------------------------------------------------------
    # TC-F04-010-6: _run_core_async calls _assemble_for_async_run (structural)
    # ------------------------------------------------------------------

    def test_run_core_async_source_calls_assemble_for_async_run(self) -> None:
        """_run_core_async source body contains a call to _assemble_for_async_run.

        This is the structural AC-10 assertion that the refactor actually
        introduced the shared helper call in the existing non-streaming path.

        COUNTER-FACTUAL: A pre-refactor impl where _run_core_async still
        contains its own inline phases 2-5 (without calling the helper)
        would fail this string-search assertion.
        """
        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        source = inspect.getsource(GraphRunnerService._run_core_async)
        self.assertIn(
            "_assemble_for_async_run",
            source,
            "_run_core_async must call _assemble_for_async_run (D-7 refactor); "
            "call not found in method source — the shared assembly helper was not wired in",
        )

    # ------------------------------------------------------------------
    # TC-F04-010-7: _run_core_async body does NOT reference streaming methods
    # ------------------------------------------------------------------

    def test_run_core_async_does_not_reference_run_stream_async(self) -> None:
        """_run_core_async body must NOT contain 'run_stream_async'.

        Non-streaming run path must remain independent of streaming methods.

        COUNTER-FACTUAL: An impl that accidentally routes _run_core_async
        through the streaming path would contain 'run_stream_async' in its
        source, and this test would catch the coupling.
        """
        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        source = inspect.getsource(GraphRunnerService._run_core_async)
        self.assertNotIn(
            "run_stream_async",
            source,
            "_run_core_async must NOT reference run_stream_async "
            "(non-streaming path must remain independent)",
        )

    def test_run_core_async_does_not_reference_stream_compiled_graph_async(
        self,
    ) -> None:
        """_run_core_async body must NOT contain 'stream_compiled_graph_async'.

        COUNTER-FACTUAL: A buggy refactor that replaces the ainvoke call with
        stream_compiled_graph_async in _run_core_async would break non-streaming
        behavior — this structural assertion catches it.
        """
        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        source = inspect.getsource(GraphRunnerService._run_core_async)
        self.assertNotIn(
            "stream_compiled_graph_async",
            source,
            "_run_core_async must NOT reference stream_compiled_graph_async "
            "(non-streaming path must use execute_compiled_graph_async only)",
        )

    # ------------------------------------------------------------------
    # TC-F04-010-8: execute_compiled_graph_async source does NOT contain astream
    # ------------------------------------------------------------------

    def test_execute_compiled_graph_async_source_does_not_contain_astream(
        self,
    ) -> None:
        """execute_compiled_graph_async must NOT contain 'astream' in its source.

        This confirms the existing ainvoke-based method was not modified by the
        T-E06-F04-003 refactor.

        COUNTER-FACTUAL: A regression that accidentally routes
        execute_compiled_graph_async through .astream() would produce an
        AsyncGenerator instead of an ExecutionResult, breaking the non-streaming
        contract; this source assertion catches the modification.
        """
        from agentmap.services.graph.graph_execution_service import (
            GraphExecutionService,
        )

        source = inspect.getsource(GraphExecutionService.execute_compiled_graph_async)
        self.assertNotIn(
            "astream",
            source,
            "execute_compiled_graph_async must NOT contain 'astream' "
            "(non-streaming path must use ainvoke only; "
            "stream_compiled_graph_async is the separate streaming method)",
        )

    # ------------------------------------------------------------------
    # TC-F04-010-9: _run_core_async behavior is byte-equivalent after refactor
    # ------------------------------------------------------------------

    async def test_run_core_async_completes_successfully_after_refactor(self) -> None:
        """_run_core_async still returns ExecutionResult after the D-7 refactor.

        COUNTER-FACTUAL: An impl where the helper extraction broke the call
        chain (e.g., wrong return unpacking) would raise AttributeError/TypeError
        inside _run_core_async before execution.execute_compiled_graph_async is called.
        """
        from agentmap.models.execution.result import ExecutionResult

        service, mocks = _make_graph_runner_for_assembly(checkpoint=False)
        bundle = _make_mock_bundle_for_assembly()

        # Set up the execution result
        mock_result = MagicMock(spec=ExecutionResult)
        mock_result.success = True
        mock_result.total_duration = 1.5
        mock_result.error = None

        mocks["execution"].execute_compiled_graph_async = AsyncMock(
            return_value=mock_result
        )

        result = await service._run_core_async(
            bundle=bundle,
            initial_state={"input": "hello"},
            parent_graph_name=None,
            parent_tracker=None,
            is_subgraph=False,
            validate_agents=False,
        )

        self.assertIs(
            result,
            mock_result,
            "_run_core_async must return the ExecutionResult from "
            "execute_compiled_graph_async after the D-7 refactor",
        )
        mocks["execution"].execute_compiled_graph_async.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
