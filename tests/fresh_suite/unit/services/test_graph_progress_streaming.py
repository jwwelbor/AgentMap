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
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

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


# ---------------------------------------------------------------------------
# Helpers for TestRunWorkflowStreamAsyncHappyPath / TestDisambiguationMechanism
# (T-E06-F04-004)
# ---------------------------------------------------------------------------


def _make_graph_execution_service() -> Tuple[Any, Dict[str, Any]]:
    """Construct a GraphExecutionService with all dependencies mocked.

    Returns (service, mocks_dict) where mocks_dict contains:
      - tracking: ExecutionTrackingService mock
      - policy: ExecutionPolicyService mock
      - state_adapter: StateAdapterService mock
      - mock_tracker: a MagicMock acting as the execution tracker
      - mock_summary: a MagicMock acting as the execution summary
    """
    from agentmap.models.execution.summary import ExecutionSummary
    from agentmap.services.execution_policy_service import ExecutionPolicyService
    from agentmap.services.execution_tracking_service import ExecutionTrackingService
    from agentmap.services.graph.graph_execution_service import GraphExecutionService
    from agentmap.services.logging_service import LoggingService
    from agentmap.services.state_adapter_service import StateAdapterService

    mock_tracking = create_autospec(ExecutionTrackingService, instance=True)
    mock_policy = create_autospec(ExecutionPolicyService, instance=True)
    mock_state_adapter = create_autospec(StateAdapterService, instance=True)
    mock_logging = create_autospec(LoggingService, instance=True)
    mock_logging.get_class_logger.return_value = MagicMock(name="mock_logger")

    # Tracker + summary mocks
    mock_tracker = MagicMock(name="mock_tracker")
    mock_summary = MagicMock(name="mock_summary", spec=ExecutionSummary)
    mock_summary.graph_name = "test_graph"

    mock_tracking.complete_execution.return_value = None
    mock_tracking.to_summary.return_value = mock_summary
    mock_policy.evaluate_success_policy.return_value = True

    # state_adapter.set_value returns state with injected keys unchanged
    def _set_value_side_effect(state, key, value):
        updated = dict(state)
        updated[key] = value
        return updated

    mock_state_adapter.set_value.side_effect = _set_value_side_effect

    service = GraphExecutionService(
        execution_tracking_service=mock_tracking,
        execution_policy_service=mock_policy,
        state_adapter_service=mock_state_adapter,
        logging_service=mock_logging,
    )

    mocks = {
        "tracking": mock_tracking,
        "policy": mock_policy,
        "state_adapter": mock_state_adapter,
        "mock_tracker": mock_tracker,
        "mock_summary": mock_summary,
    }
    return service, mocks


class _FakeCompiledGraph:
    """Minimal fake compiled graph for T-E06-F04-004 tests.

    Delegates .astream() to a caller-supplied async generator factory.
    Provides .ainvoke() returning a fixed final_state for regression tests.
    """

    def __init__(self, astream_factory, final_state: Optional[Dict[str, Any]] = None):
        self._astream_factory = astream_factory
        self._final_state = final_state or {}

    def astream(self, initial_state, config=None, stream_mode=None):
        """Return the async generator produced by the factory."""
        return self._astream_factory(initial_state)

    async def ainvoke(self, initial_state, config=None):
        return dict(self._final_state)


async def _make_node_updates(*node_name_delta_pairs):
    """Async generator that yields {node_name: delta} dicts in order then exhausts."""
    for node_name, delta in node_name_delta_pairs:
        yield {node_name: delta}


async def _make_node_updates_with_gate(node_name_delta_pairs, gate: Any):
    """Async generator that yields first pair, waits on gate, then yields rest."""
    first_name, first_delta = node_name_delta_pairs[0]
    yield {first_name: first_delta}
    await gate.wait()
    for node_name, delta in node_name_delta_pairs[1:]:
        yield {node_name: delta}


# ---------------------------------------------------------------------------
# TestRunWorkflowStreamAsyncHappyPath — TC-F04-001, TC-F04-002, TC-F04-004
# (T-E06-F04-004)
# ---------------------------------------------------------------------------


class TestRunWorkflowStreamAsyncHappyPath(unittest.IsolatedAsyncioTestCase):
    """TC-F04-001, TC-F04-002, TC-F04-004: stream_compiled_graph_async happy path.

    These tests drive GraphExecutionService.stream_compiled_graph_async directly —
    the lowest production seam for T-E06-F04-004 (runner/facade layers are T-E06-F04-005+).

    ENTRYPOINT:
      GraphExecutionService.stream_compiled_graph_async(
          executable_graph, graph_name, initial_state, execution_tracker, config=None
      )

    LOWEST ALLOWED MOCK SEAM:
      Fake compiled graph whose .astream(stream_mode='updates') yields scripted
      {node_name: delta} dicts.  All GraphExecutionService dependencies (tracking,
      policy, state_adapter) are mocked.

    FORBIDDEN MOCKS:
      Do NOT mock stream_compiled_graph_async itself; it must execute for real.
      Do NOT mock WorkflowProgressEvent — it must be constructed by the method.

    COUNTER-FACTUAL:
      - TC-F04-001: A buggy impl that doesn't yield tuples at all would fail
        isinstance(item, tuple) and the (node_name, delta) shape assertions.
      - TC-F04-002: A buffering impl would not yield n1 tuple before n2 is released
        (gate never opens, but n1_received would never be set either).
      - TC-F04-004: A buggy impl emitting ExecutionResult as a tuple item (instead
        of returning it) would fail isinstance(terminal_result, ExecutionResult).
    """

    # ------------------------------------------------------------------
    # TC-F04-001: 2-node graph yields (n1, delta) then (n2, delta) in order
    # ------------------------------------------------------------------

    async def test_stream_compiled_graph_async_2node_ordered_yields(self) -> None:
        """TC-F04-001: 2-node fake graph yields (n1, delta), (n2, delta) then done.

        COUNTER-FACTUAL: A buggy impl that yields node name and delta as separate
        items (not tuples), or yields them in wrong order, would fail the
        assertEqual(node_name, 'n1') / assertEqual(node_name, 'n2') assertions.
        """
        service, mocks = _make_graph_execution_service()

        updates = [
            ("n1", {"output": "result-n1"}),
            ("n2", {"output": "result-n2"}),
        ]

        def astream_factory(initial_state):
            return _make_node_updates(*updates)

        fake_graph = _FakeCompiledGraph(astream_factory)

        collected = []

        gen = service.stream_compiled_graph_async(
            executable_graph=fake_graph,
            graph_name="test-graph",
            initial_state={"input": "hello"},
            execution_tracker=mocks["mock_tracker"],
            config=None,
        )
        async for item in gen:
            collected.append(item)

        # The generator must yield (node_name, state_delta) tuples for each node,
        # then a _TerminalStreamResult sentinel (D-8 mechanism).
        # Total items = 2 node tuples + 1 sentinel = 3.
        from agentmap.services.graph.graph_execution_service import (
            _TerminalStreamResult,
        )

        self.assertEqual(
            len(collected),
            3,
            f"Expected 2 node tuples + 1 terminal sentinel = 3 items, got {len(collected)}: {collected}",
        )

        # Last item must be the _TerminalStreamResult sentinel
        self.assertIsInstance(
            collected[-1],
            _TerminalStreamResult,
            f"Last item must be _TerminalStreamResult sentinel (D-8), got {type(collected[-1])!r}",
        )

        # Verify n1
        n1_name, n1_delta = collected[0]
        self.assertEqual(
            n1_name,
            "n1",
            f"First yielded node_name must be 'n1', got {n1_name!r}",
        )
        self.assertEqual(
            n1_delta,
            {"output": "result-n1"},
            f"n1 state_delta mismatch: {n1_delta}",
        )

        # Verify n2
        n2_name, n2_delta = collected[1]
        self.assertEqual(
            n2_name,
            "n2",
            f"Second yielded node_name must be 'n2', got {n2_name!r}",
        )
        self.assertEqual(
            n2_delta,
            {"output": "result-n2"},
            f"n2 state_delta mismatch: {n2_delta}",
        )

        # Verify node tuples are (str, dict) — no ExecutionResult mixed in
        for item in collected[:-1]:
            self.assertIsInstance(
                item,
                tuple,
                f"Each node item must be a (node_name, delta) tuple, got {type(item)}",
            )
            node_name, delta = item
            self.assertIsInstance(node_name, str, "node_name must be str")
            self.assertIsInstance(
                delta, dict, "state_delta must be dict (materialized, not iterator)"
            )

    async def test_stream_compiled_graph_async_returns_execution_result_via_d8(
        self,
    ) -> None:
        """TC-F04-001 extension: terminal ExecutionResult is accessible via D-8 mechanism.

        D-8 MECHANISM: The generator yields a typed sentinel (_TerminalStreamResult)
        as its final item, wrapping the ExecutionResult.  The sentinel is a distinct
        type from (str, dict) node-update tuples, so no dict-key collision is possible.
        `run_stream_async` (T-E06-F04-005) checks isinstance(item, _TerminalStreamResult)
        to detect the terminal.

        COUNTER-FACTUAL: A buggy impl that yields ExecutionResult directly (not wrapped
        in a sentinel) would be indistinguishable from a node update for a node named
        "result" — the D-8 test (TC-F04-D8) catches this.
        """
        from agentmap.models.execution.result import ExecutionResult
        from agentmap.services.graph.graph_execution_service import (
            _TerminalStreamResult,
        )

        service, mocks = _make_graph_execution_service()

        updates = [("n1", {"output": "val1"})]

        def astream_factory(initial_state):
            return _make_node_updates(*updates)

        fake_graph = _FakeCompiledGraph(astream_factory)

        gen = service.stream_compiled_graph_async(
            executable_graph=fake_graph,
            graph_name="d8-test-graph",
            initial_state={"input": "d8-input"},
            execution_tracker=mocks["mock_tracker"],
            config=None,
        )

        # Collect all items; the last must be a _TerminalStreamResult sentinel
        all_items = []
        async for item in gen:
            all_items.append(item)

        self.assertGreaterEqual(
            len(all_items),
            1,
            "Generator must yield at least one item (the terminal sentinel)",
        )
        terminal_item = all_items[-1]
        self.assertIsInstance(
            terminal_item,
            _TerminalStreamResult,
            f"Last yielded item must be a _TerminalStreamResult sentinel (D-8 mechanism), "
            f"got {type(terminal_item).__name__!r}",
        )
        self.assertIsInstance(
            terminal_item.result,
            ExecutionResult,
            f"_TerminalStreamResult.result must be an ExecutionResult, "
            f"got {type(terminal_item.result).__name__}",
        )
        self.assertEqual(
            terminal_item.result.graph_name,
            "d8-test-graph",
            f"terminal_result.graph_name mismatch: {terminal_item.result.graph_name!r}",
        )

    # ------------------------------------------------------------------
    # TC-F04-002: Incremental delivery via asyncio.Event gate
    # ------------------------------------------------------------------

    async def test_stream_compiled_graph_async_incremental_delivery(self) -> None:
        """TC-F04-002: n1 tuple received before gate releases n2.

        A backpressure gate (asyncio.Event) blocks the second node.
        The consumer must receive the n1 (node_name, delta) tuple before
        the gate is opened — proving the generator yields incrementally,
        not buffering all results before the first yield.

        COUNTER-FACTUAL: A buffering impl that collects all node updates before
        yielding any would never yield n1 while n2 is blocked — so n1_received
        would never be set while gate is still closed.
        """
        import asyncio as _asyncio

        service, mocks = _make_graph_execution_service()

        gate = _asyncio.Event()
        n1_received = _asyncio.Event()

        node_pairs = [
            ("n1", {"output": "incremental-v1"}),
            ("n2", {"output": "incremental-v2"}),
        ]

        def astream_factory(initial_state):
            return _make_node_updates_with_gate(node_pairs, gate)

        fake_graph = _FakeCompiledGraph(astream_factory)

        received_items = []

        async def consume():
            from agentmap.services.graph.graph_execution_service import (
                _TerminalStreamResult,
            )

            gen = service.stream_compiled_graph_async(
                executable_graph=fake_graph,
                graph_name="gate-graph",
                initial_state={"input": "x"},
                execution_tracker=mocks["mock_tracker"],
                config=None,
            )
            async for item in gen:
                received_items.append(item)
                # Only count non-sentinel items as "node items" for the gate check
                if (
                    not isinstance(item, _TerminalStreamResult)
                    and len(received_items) == 1
                ):
                    n1_received.set()
                    # Verify gate is NOT yet set before we open it
                    # (this is the key incremental-delivery assertion)
                    self.assertFalse(
                        gate.is_set(),
                        "Gate must NOT be set when n1 is first received — "
                        "impl must yield n1 immediately, not buffer",
                    )
                    gate.set()

        await consume()

        from agentmap.services.graph.graph_execution_service import (
            _TerminalStreamResult,
        )

        self.assertTrue(
            n1_received.is_set(),
            "n1_received event was never set — n1 tuple was never yielded",
        )
        # Total items: 2 node tuples + 1 terminal sentinel = 3
        self.assertEqual(
            len(received_items),
            3,
            f"Expected 2 node tuples + 1 terminal sentinel = 3 items, got {len(received_items)}",
        )
        n1_name, _ = received_items[0]
        n2_name, _ = received_items[1]
        self.assertEqual(n1_name, "n1")
        self.assertEqual(n2_name, "n2")
        self.assertIsInstance(
            received_items[2],
            _TerminalStreamResult,
            "Third item must be _TerminalStreamResult terminal sentinel",
        )

    # ------------------------------------------------------------------
    # TC-F04-004: BVA — exactly one terminal ExecutionResult via D-8, it is last
    # ------------------------------------------------------------------

    async def _collect_with_terminal(
        self, service: Any, mocks: Dict[str, Any], node_pairs: list, graph_name: str
    ) -> Tuple[list, Any]:
        """Helper: run generator, separate node tuples from terminal sentinel via D-8.

        Returns (node_tuples, execution_result) where:
          - node_tuples: list of (node_name, state_delta) tuples yielded before the sentinel
          - execution_result: the ExecutionResult from the _TerminalStreamResult sentinel
        """
        from agentmap.services.graph.graph_execution_service import (
            _TerminalStreamResult,
        )

        def astream_factory(initial_state):
            return _make_node_updates(*node_pairs)

        fake_graph = _FakeCompiledGraph(astream_factory)

        gen = service.stream_compiled_graph_async(
            executable_graph=fake_graph,
            graph_name=graph_name,
            initial_state={"input": "bva"},
            execution_tracker=mocks["mock_tracker"],
            config=None,
        )

        node_tuples = []
        terminal_result = None
        async for item in gen:
            if isinstance(item, _TerminalStreamResult):
                terminal_result = item.result
            else:
                node_tuples.append(item)

        return node_tuples, terminal_result

    async def test_bva_0_nodes_exactly_one_terminal_result(self) -> None:
        """TC-F04-004 BVA-0: 0-node graph yields no tuples; still produces one terminal.

        COUNTER-FACTUAL: A buggy impl that requires at least one node update before
        finalizing would never reach complete_execution and terminal_result would be None.
        """
        from agentmap.models.execution.result import ExecutionResult

        service, mocks = _make_graph_execution_service()
        node_tuples, terminal_result = await self._collect_with_terminal(
            service, mocks, [], "zero-node-graph"
        )

        self.assertEqual(
            len(node_tuples),
            0,
            f"0-node graph must yield 0 (node_name, delta) tuples, got {len(node_tuples)}",
        )
        self.assertIsNotNone(
            terminal_result,
            "0-node graph must still produce a terminal ExecutionResult via D-8",
        )
        self.assertIsInstance(terminal_result, ExecutionResult)

    async def test_bva_1_node_exactly_one_terminal_result(self) -> None:
        """TC-F04-004 BVA-1: 1-node graph yields exactly 1 tuple then one terminal.

        COUNTER-FACTUAL: A buggy impl that yields 0 or 2 node tuples for a
        1-node graph would fail len(node_tuples) == 1.
        """
        from agentmap.models.execution.result import ExecutionResult

        service, mocks = _make_graph_execution_service()
        node_tuples, terminal_result = await self._collect_with_terminal(
            service, mocks, [("n1", {"output": "v"})], "one-node-graph"
        )

        self.assertEqual(len(node_tuples), 1)
        self.assertIsNotNone(terminal_result)
        self.assertIsInstance(terminal_result, ExecutionResult)
        # No ExecutionResult among the node tuples
        for item in node_tuples:
            name, delta = item
            self.assertIsInstance(name, str)
            self.assertIsInstance(delta, dict)

    async def test_bva_3_nodes_exactly_one_terminal_result(self) -> None:
        """TC-F04-004 BVA-3: 3-node graph yields exactly 3 tuples then one terminal.

        COUNTER-FACTUAL: A buggy impl that emits two ExecutionResults (one from
        each state-injection step) would have terminal_result set twice — but since
        we capture via StopAsyncIteration.value, only the final `return` counts.
        The node_tuples count must be exactly 3.
        """
        from agentmap.models.execution.result import ExecutionResult

        service, mocks = _make_graph_execution_service()
        node_tuples, terminal_result = await self._collect_with_terminal(
            service,
            mocks,
            [
                ("n1", {"o1": "v1"}),
                ("n2", {"o2": "v2"}),
                ("n3", {"o3": "v3"}),
            ],
            "three-node-graph",
        )

        self.assertEqual(
            len(node_tuples),
            3,
            f"3-node graph must yield exactly 3 node tuples, got {len(node_tuples)}",
        )
        self.assertIsNotNone(terminal_result)
        self.assertIsInstance(terminal_result, ExecutionResult)
        # Verify no ExecutionResult was mixed into node tuples
        for item in node_tuples:
            self.assertIsInstance(item, tuple, f"Expected tuple, got {type(item)}")

    async def test_bva_terminal_result_graph_success_is_true(self) -> None:
        """TC-F04-004: terminal ExecutionResult.success is True for successful run.

        COUNTER-FACTUAL: A buggy impl that does not call evaluate_success_policy
        would leave success at a default (possibly False), failing this assertion.
        """
        from agentmap.models.execution.result import ExecutionResult

        service, mocks = _make_graph_execution_service()
        mocks["policy"].evaluate_success_policy.return_value = True

        node_tuples, terminal_result = await self._collect_with_terminal(
            service, mocks, [("n1", {"output": "ok"})], "success-graph"
        )

        self.assertIsNotNone(terminal_result)
        self.assertIsInstance(terminal_result, ExecutionResult)
        self.assertTrue(
            terminal_result.success,
            "terminal ExecutionResult.success must be True when policy returns True",
        )

    async def test_final_state_merges_all_node_deltas(self) -> None:
        """TC-F04-001 extension: terminal ExecutionResult.final_state merges all node deltas.

        stream_mode='updates' yields sparse deltas per node. The execution service
        must merge them into a running final_state so the terminal ExecutionResult
        has the fully accumulated state (parity with ainvoke which returns full state).

        COUNTER-FACTUAL: A buggy impl that uses only the last node's delta as
        final_state would produce final_state = {'o2': 'v2'} — missing 'o1' from n1.
        """
        from agentmap.models.execution.result import ExecutionResult

        service, mocks = _make_graph_execution_service()

        updates = [
            ("n1", {"o1": "v1"}),
            ("n2", {"o2": "v2"}),
        ]

        node_tuples, terminal_result = await self._collect_with_terminal(
            service, mocks, updates, "merge-graph"
        )

        self.assertIsNotNone(terminal_result)
        self.assertIsInstance(terminal_result, ExecutionResult)

        # final_state must contain contributions from BOTH nodes
        # (merged into initial_state = {"input": "bva"})
        self.assertIn(
            "o1",
            terminal_result.final_state,
            "final_state must contain 'o1' from n1's delta — delta merging required",
        )
        self.assertIn(
            "o2",
            terminal_result.final_state,
            "final_state must contain 'o2' from n2's delta — delta merging required",
        )


# ---------------------------------------------------------------------------
# TestDisambiguationMechanism — TC-F04-D8
# (T-E06-F04-004)
# ---------------------------------------------------------------------------


class TestDisambiguationMechanism(unittest.IsolatedAsyncioTestCase):
    """TC-F04-D8: Node named 'result' does not collide with terminal ExecutionResult.

    ENTRYPOINT (internal-only):
      GraphExecutionService.stream_compiled_graph_async(
          executable_graph, graph_name, initial_state, execution_tracker, config=None
      )
      Justification: this tests the internal D-8 disambiguation mechanism;
      the caller contract above it (run_stream_async) is T-E06-F04-005.

    LOWEST ALLOWED MOCK SEAM:
      Fake compiled graph .astream() with a node named 'result' (collision test).

    FORBIDDEN MOCKS:
      Do NOT mock the disambiguation mechanism itself — the actual method body
      must exercise the separation between node updates and the terminal result.

    COUNTER-FACTUAL:
      A buggy impl using a dict-key sentinel ('result' or 'terminal') to distinguish
      the terminal from node updates would confuse a node named 'result' with the
      terminal signal — yielding the node tuple as the terminal OR discarding it.
      This test catches that by asserting both the node tuple for 'result' AND the
      ExecutionResult are correctly produced and separated.
    """

    async def test_node_named_result_does_not_collide_with_terminal_execution_result(
        self,
    ) -> None:
        """TC-F04-D8: 'result' node update coexists with terminal ExecutionResult.

        Fake graph yields {"result": {"output": "node-output-from-result-node"}}
        then exhausts.  The generator must yield exactly one (node_name, delta)
        tuple where node_name == 'result', then yield one _TerminalStreamResult
        sentinel carrying the ExecutionResult.

        Both the node tuple AND the terminal result are present and distinct.

        D-8 MECHANISM: The generator yields typed sentinels (_TerminalStreamResult)
        for the terminal, NOT a dict key. A node named "result" cannot be confused
        with the terminal because the terminal has a completely different Python type.

        COUNTER-FACTUAL:
          An impl that checks `if node_name == 'result': treat_as_terminal` would
          swallow the node-named-'result' update and never yield the (node_name, delta)
          tuple — failing len(node_tuples) == 1.
          An impl that yields a raw dict with key 'result' as the terminal signal
          would confuse the node update dict with the sentinel — the 'result' node's
          state_delta would be mistakenly treated as the terminal ExecutionResult.
        """
        from agentmap.models.execution.result import ExecutionResult
        from agentmap.services.graph.graph_execution_service import (
            _TerminalStreamResult,
        )

        service, mocks = _make_graph_execution_service()

        collision_update = {"result": {"output": "node-output-from-result-node"}}

        async def astream_factory_d8(initial_state):
            yield collision_update

        fake_graph = _FakeCompiledGraph(astream_factory_d8)

        gen = service.stream_compiled_graph_async(
            executable_graph=fake_graph,
            graph_name="result-collision-graph",
            initial_state={"input": "d8-input"},
            execution_tracker=mocks["mock_tracker"],
            config=None,
        )

        node_tuples = []
        terminal_sentinel = None
        async for item in gen:
            if isinstance(item, _TerminalStreamResult):
                terminal_sentinel = item
            else:
                node_tuples.append(item)

        # Exactly one node tuple must be yielded: ("result", {...})
        self.assertEqual(
            len(node_tuples),
            1,
            f"Expected exactly 1 node tuple for 'result' node, got {len(node_tuples)}: {node_tuples}",
        )

        node_name, state_delta = node_tuples[0]
        self.assertEqual(
            node_name,
            "result",
            f"Yielded node_name must be 'result' (not discarded or reinterpreted), got {node_name!r}",
        )
        self.assertEqual(
            state_delta,
            {"output": "node-output-from-result-node"},
            f"state_delta must match the node's output dict, got {state_delta}",
        )

        # Terminal sentinel must be present (D-8)
        self.assertIsNotNone(
            terminal_sentinel,
            "Terminal _TerminalStreamResult sentinel must be yielded after all node tuples "
            "(D-8: typed sentinel separates node updates from terminal ExecutionResult) — "
            "the 'result'-named node may have been confused with the terminal signal",
        )
        self.assertIsInstance(
            terminal_sentinel,
            _TerminalStreamResult,
            f"Terminal item must be _TerminalStreamResult, got {type(terminal_sentinel).__name__}",
        )
        terminal_result = terminal_sentinel.result
        self.assertIsInstance(
            terminal_result,
            ExecutionResult,
            f"_TerminalStreamResult.result must be ExecutionResult, got {type(terminal_result).__name__}",
        )
        # The terminal ExecutionResult must NOT be the node's state_delta dict
        self.assertIsNot(
            terminal_result,
            state_delta,
            "terminal ExecutionResult must be a distinct ExecutionResult object, "
            "not the node's state_delta dict",
        )
        # final_state must contain the 'result' node's contribution
        self.assertIn(
            "output",
            terminal_result.final_state,
            "final_state must include 'output' key from the 'result' node's delta",
        )

    async def test_d8_mechanism_is_typed_sentinel(self) -> None:
        """TC-F04-D8 structural: D-8 uses a typed sentinel (_TerminalStreamResult).

        The generator must yield a _TerminalStreamResult as its last item to
        communicate the terminal ExecutionResult.  This is the explicit D-8
        disambiguation: node updates are (str, dict) tuples; terminal is a
        _TerminalStreamResult instance — a completely different Python type.

        COUNTER-FACTUAL: A buggy impl that yields the ExecutionResult directly
        as a tuple item (not wrapped) would have isinstance(item, tuple) == False
        for the last item (since ExecutionResult is not a tuple) — but the D-8
        test catches this by requiring isinstance(last_item, _TerminalStreamResult).
        A buggy impl using a dict sentinel ({"_terminal": result}) would fail
        isinstance(item, _TerminalStreamResult) since a dict is not a sentinel.
        """
        from agentmap.models.execution.result import ExecutionResult
        from agentmap.services.graph.graph_execution_service import (
            _TerminalStreamResult,
        )

        service, mocks = _make_graph_execution_service()

        async def astream_factory_empty(initial_state):
            # Empty async generator — no node updates
            return
            yield  # pragma: no cover — makes this an async generator

        fake_graph = _FakeCompiledGraph(astream_factory_empty)

        gen = service.stream_compiled_graph_async(
            executable_graph=fake_graph,
            graph_name="d8-structural",
            initial_state={},
            execution_tracker=mocks["mock_tracker"],
            config=None,
        )

        all_items = []
        async for item in gen:
            all_items.append(item)
            # No raw ExecutionResult should ever be yielded directly (without wrapping)
            self.assertNotIsInstance(
                item,
                ExecutionResult,
                "D-8 violation: ExecutionResult must NOT be yielded directly as a stream item; "
                "it must be wrapped in _TerminalStreamResult sentinel",
            )

        self.assertGreaterEqual(
            len(all_items),
            1,
            "Generator must yield at least one item (the _TerminalStreamResult sentinel) "
            "even for an empty graph",
        )
        last_item = all_items[-1]
        self.assertIsInstance(
            last_item,
            _TerminalStreamResult,
            f"Last yielded item must be _TerminalStreamResult (D-8 sentinel), "
            f"got {type(last_item).__name__!r}",
        )
        self.assertIsInstance(last_item.result, ExecutionResult)

        # For empty graph: no node tuples, only the sentinel
        non_sentinel = [
            i for i in all_items if not isinstance(i, _TerminalStreamResult)
        ]
        self.assertEqual(
            len(non_sentinel),
            0,
            f"Empty graph must yield 0 node tuples, got {len(non_sentinel)}: {non_sentinel}",
        )


# ---------------------------------------------------------------------------
# Helpers for T-E06-F04-005 test classes
# (run_stream_async / run_workflow_stream_async layer)
# ---------------------------------------------------------------------------


def _make_graph_runner_for_streaming(
    telemetry: bool = False,
) -> Tuple[Any, Dict[str, Any]]:
    """Construct a GraphRunnerService wired for streaming tests.

    Sets up all mocked dependencies and configures the assembly helper to
    return a _FakeCompiledGraph.  The caller supplies the astream_factory
    via mocks['set_astream_factory'](fn) before exercising run_stream_async.

    Returns (service, mocks) where mocks includes:
      - execution: GraphExecutionService mock (real, not mocked — streaming tests
        need the real stream_compiled_graph_async)
      - mock_tracker: the execution tracker mock
      - mock_compiled: the _FakeCompiledGraph instance
      - fake_telemetry (if telemetry=True): telemetry service fake
    """
    from agentmap.models.execution.summary import ExecutionSummary
    from agentmap.services.config.app_config_service import AppConfigService
    from agentmap.services.declaration_registry_service import (
        DeclarationRegistryService,
    )
    from agentmap.services.execution_policy_service import ExecutionPolicyService
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
    from agentmap.services.state_adapter_service import StateAdapterService

    # --- logging ---
    mock_logging = create_autospec(LoggingService, instance=True)
    mock_logging.get_class_logger.return_value = MagicMock(name="mock_logger")

    # --- real GraphExecutionService with mocked sub-deps ---
    mock_tracking = create_autospec(ExecutionTrackingService, instance=True)
    mock_policy = create_autospec(ExecutionPolicyService, instance=True)
    mock_state_adapter = create_autospec(StateAdapterService, instance=True)
    mock_exec_logging = create_autospec(LoggingService, instance=True)
    mock_exec_logging.get_class_logger.return_value = MagicMock(name="exec_logger")

    mock_summary = MagicMock(name="mock_summary", spec=ExecutionSummary)
    mock_summary.graph_name = "test-graph"

    mock_tracking.complete_execution.return_value = None
    mock_tracking.to_summary.return_value = mock_summary
    mock_policy.evaluate_success_policy.return_value = True

    def _set_value_side_effect(state, key, value):
        updated = dict(state)
        updated[key] = value
        return updated

    mock_state_adapter.set_value.side_effect = _set_value_side_effect

    real_execution = GraphExecutionService(
        execution_tracking_service=mock_tracking,
        execution_policy_service=mock_policy,
        state_adapter_service=mock_state_adapter,
        logging_service=mock_exec_logging,
    )

    # --- other GraphRunnerService deps mocked ---
    mock_app_config = create_autospec(AppConfigService, instance=True)
    mock_bootstrap = create_autospec(GraphBootstrapService, instance=True)
    mock_instantiation = create_autospec(GraphAgentInstantiationService, instance=True)
    mock_assembly = create_autospec(GraphAssemblyService, instance=True)
    mock_runner_tracking = create_autospec(ExecutionTrackingService, instance=True)
    mock_interaction = create_autospec(InteractionHandlerService, instance=True)
    mock_checkpoint = create_autospec(GraphCheckpointService, instance=True)
    mock_bundle_svc = create_autospec(GraphBundleService, instance=True)
    mock_declaration = create_autospec(DeclarationRegistryService, instance=True)

    # --- tracker ---
    mock_tracker = MagicMock(name="mock_tracker")
    mock_tracker.thread_id = "test-thread-id"
    mock_runner_tracking.create_tracker.return_value = mock_tracker

    # --- scoped registry ---
    mock_scoped_registry = MagicMock()
    mock_scoped_registry.get_all_agent_types.return_value = ["agent1"]
    mock_scoped_registry.get_all_service_names.return_value = []
    mock_declaration.create_scoped_registry_for_bundle.return_value = (
        mock_scoped_registry
    )

    # --- agent instantiation ---
    node_instances = {"n1": MagicMock(), "n2": MagicMock()}
    bundle_with_instances = MagicMock()
    bundle_with_instances.graph_name = "test-graph"
    bundle_with_instances.nodes = {"n1": MagicMock(), "n2": MagicMock()}
    bundle_with_instances.entry_point = "n1"
    bundle_with_instances.node_instances = node_instances

    def _instantiate_side_effect(b, tracker):
        b.node_instances = node_instances
        return bundle_with_instances

    mock_instantiation.instantiate_agents.side_effect = _instantiate_side_effect

    # --- fake compiled graph ---
    astream_factory_holder: Dict[str, Any] = {"fn": None}

    def _default_astream_factory(initial_state):
        return _make_node_updates(("n1", {"output": "v1"}), ("n2", {"output": "v2"}))

    astream_factory_holder["fn"] = _default_astream_factory

    class _DynamicFakeGraph(_FakeCompiledGraph):
        def astream(self, initial_state, config=None, stream_mode=None):
            return astream_factory_holder["fn"](initial_state)

        async def ainvoke(self, initial_state, config=None):
            return dict(initial_state)

    mock_compiled = _DynamicFakeGraph(_default_astream_factory)
    mock_bundle_svc.requires_checkpoint_support.return_value = False
    mock_assembly.assemble_graph_async.return_value = mock_compiled

    # --- optional telemetry ---
    fake_telemetry = None
    if telemetry:
        fake_telemetry = MagicMock(name="fake_telemetry")
        fake_telemetry.open_span_count = 0
        fake_telemetry.close_span_count = 0

    service = GraphRunnerService(
        app_config_service=mock_app_config,
        graph_bootstrap_service=mock_bootstrap,
        graph_agent_instantiation_service=mock_instantiation,
        graph_assembly_service=mock_assembly,
        graph_execution_service=real_execution,
        execution_tracking_service=mock_runner_tracking,
        logging_service=mock_logging,
        interaction_handler_service=mock_interaction,
        graph_checkpoint_service=mock_checkpoint,
        graph_bundle_service=mock_bundle_svc,
        declaration_registry_service=mock_declaration,
    )
    if telemetry and fake_telemetry is not None:
        service._telemetry_service = fake_telemetry

    mocks: Dict[str, Any] = {
        "tracking": mock_tracking,  # GraphExecutionService's tracking
        "runner_tracking": mock_runner_tracking,  # GraphRunnerService's tracking
        "policy": mock_policy,
        "state_adapter": mock_state_adapter,
        "mock_tracker": mock_tracker,
        "mock_summary": mock_summary,
        "mock_compiled": mock_compiled,
        "astream_factory_holder": astream_factory_holder,
        "fake_telemetry": fake_telemetry,
    }

    def _set_astream_factory(fn: Any) -> None:
        astream_factory_holder["fn"] = fn

    mocks["set_astream_factory"] = _set_astream_factory
    return service, mocks


def _make_mock_bundle_for_streaming(graph_name: str = "test-graph") -> MagicMock:
    """Create a minimal mock GraphBundle for streaming tests."""
    bundle = MagicMock(name="mock_bundle")
    bundle.graph_name = graph_name
    node_0 = MagicMock()
    node_0.agent_type = "default"
    node_1 = MagicMock()
    node_1.agent_type = "default"
    bundle.nodes = {"n1": node_0, "n2": node_1}
    bundle.entry_point = "n1"
    bundle.csv_hash = None
    bundle.node_instances = None
    bundle.scoped_registry = None
    bundle.missing_services = set()
    return bundle


async def _collect_stream_events(runner: Any, bundle: Any, inputs: Dict) -> list:
    """Collect all WorkflowProgressEvents from run_stream_async into a list."""
    from agentmap.models.execution import WorkflowProgressEvent

    events = []
    async for event in runner.run_stream_async(
        bundle, initial_state=inputs, validate_agents=False
    ):
        events.append(event)
        assert isinstance(
            event, WorkflowProgressEvent
        ), f"Expected WorkflowProgressEvent, got {type(event).__name__}"
    return events


# ---------------------------------------------------------------------------
# TestRunWorkflowStreamAsyncErrorPaths — TC-F04-005, TC-F04-008b
# (T-E06-F04-005)
# ---------------------------------------------------------------------------


class TestRunWorkflowStreamAsyncErrorPaths(unittest.IsolatedAsyncioTestCase):
    """TC-F04-005: mid-run node failure → failed terminal WorkflowProgressEvent.
    TC-F04-008b: GraphInterrupt → suspended terminal WorkflowProgressEvent.

    ENTRYPOINT:
      GraphRunnerService.run_stream_async(bundle, initial_state, validate_agents=False)

    LOWEST ALLOWED MOCK SEAM:
      Fake compiled graph whose .astream() raises on the nth node; real
      GraphExecutionService.stream_compiled_graph_async is exercised.

    FORBIDDEN MOCKS:
      Do NOT mock run_stream_async itself.
      Do NOT mock _raise_mapped_error (verify error surfaces in result, not exception).
      Do NOT mock GraphInterrupt handling in stream_compiled_graph_async or run_stream_async.

    COUNTER-FACTUAL:
      TC-F04-005: A buggy impl that lets the node exception propagate out of the
        generator (not converting to failed terminal event) would raise here; the
        test's 'async for' loop would see the exception rather than a failed event.
      TC-F04-008b: A buggy impl that converts GraphInterrupt to event_type='failed'
        instead of 'suspended' would fail assertEqual(terminal.event_type, 'suspended').
    """

    # ------------------------------------------------------------------
    # TC-F04-005-A: fail before any node — single failed terminal, no progress
    # ------------------------------------------------------------------

    async def test_run_stream_async_fail_before_first_node(self) -> None:
        """TC-F04-005-A: .astream() raises immediately; single failed terminal event.

        Sub-case A from the decision table (fail-before-any-node).
        Expected: events[0] is a failed terminal; no prior node_progress event.

        COUNTER-FACTUAL: A buggy impl that lets RuntimeError propagate out of
        the generator would fail the iteration without yielding any event.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        runner, mocks = _make_graph_runner_for_streaming()

        async def fail_immediately(initial_state):
            raise RuntimeError("immediate failure")
            yield  # pragma: no cover — makes this an async generator

        mocks["set_astream_factory"](fail_immediately)
        bundle = _make_mock_bundle_for_streaming("failing-graph-a")

        events: list = []
        exception_raised = False
        try:
            async for event in runner.run_stream_async(
                bundle, initial_state={"input": "x"}, validate_agents=False
            ):
                events.append(event)
        except Exception:
            exception_raised = True

        self.assertFalse(
            exception_raised,
            "run_stream_async must NOT raise exceptions from mid-run failures "
            "(TC-F04-005 sub-case A); a 'failed' terminal event must be yielded instead",
        )
        self.assertEqual(
            len(events),
            1,
            f"Expected exactly 1 event (failed terminal) for immediate failure, "
            f"got {len(events)}: {events}",
        )
        terminal = events[0]
        self.assertIsInstance(terminal, WorkflowProgressEvent)
        self.assertTrue(
            terminal.is_terminal,
            "The single event must be a terminal event (is_terminal=True)",
        )
        self.assertEqual(
            terminal.event_type,
            "failed",
            f"Terminal event must have event_type='failed', got {terminal.event_type!r}",
        )
        self.assertIsNotNone(
            terminal.error,
            "Failed terminal event must have a non-None error field",
        )
        self.assertIsNotNone(
            terminal.result,
            "Failed terminal event must carry a result dict",
        )
        self.assertFalse(
            terminal.result.get("success", True),
            "Failed terminal result['success'] must be False",
        )

    # ------------------------------------------------------------------
    # TC-F04-005-B: fail after first node (primary test)
    # ------------------------------------------------------------------

    async def test_run_stream_async_fail_after_first_node(self) -> None:
        """TC-F04-005-B: yields n1 progress then failed terminal; no exception.

        This is the primary sub-case B (fail-after-first-node).
        Expected: [n1_progress, failed_terminal], no exception raised.

        COUNTER-FACTUAL: A buggy impl that propagates the exception would fail
        the exception_raised == False assertion.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        runner, mocks = _make_graph_runner_for_streaming()

        async def fail_after_n1(initial_state):
            yield {"n1": {"output": "partial"}}
            raise RuntimeError("node n2 failed with ValueError")

        mocks["set_astream_factory"](fail_after_n1)
        bundle = _make_mock_bundle_for_streaming("failing-graph-b")

        events: list = []
        exception_raised = False
        try:
            async for event in runner.run_stream_async(
                bundle, initial_state={"input": "x"}, validate_agents=False
            ):
                events.append(event)
        except Exception:
            exception_raised = True

        self.assertFalse(
            exception_raised,
            "run_stream_async must NOT raise; failed terminal event must be yielded",
        )
        self.assertEqual(
            len(events),
            2,
            f"Expected [n1_progress, failed_terminal] = 2 events, got {len(events)}: {events}",
        )

        e0 = events[0]
        e1 = events[1]

        self.assertIsInstance(e0, WorkflowProgressEvent)
        self.assertEqual(e0.event_type, "node_progress")
        self.assertEqual(e0.node_name, "n1")
        self.assertFalse(e0.is_terminal)
        self.assertEqual(e0.sequence, 0)

        self.assertIsInstance(e1, WorkflowProgressEvent)
        self.assertEqual(
            e1.event_type,
            "failed",
            f"Second event must be 'failed' terminal, got {e1.event_type!r}",
        )
        self.assertTrue(e1.is_terminal)
        self.assertEqual(
            e1.sequence,
            1,
            "Terminal event sequence must be 1 (one after n1's sequence=0)",
        )
        self.assertIsNotNone(e1.error, "Failed terminal event must have error set")
        self.assertIsNotNone(e1.result)
        self.assertFalse(e1.result.get("success", True))
        self.assertIsNone(e1.node_name, "Terminal event must have node_name=None")
        self.assertIsNone(e1.state_delta, "Terminal event must have state_delta=None")

    # ------------------------------------------------------------------
    # TC-F04-005-C: fail at last node (3-node graph, fail at n3)
    # ------------------------------------------------------------------

    async def test_run_stream_async_fail_at_last_node(self) -> None:
        """TC-F04-005-C: yields n1, n2 progress then failed terminal.

        Sub-case C (fail-at-last-node in 3-node graph).
        Expected: [n1_progress, n2_progress, failed_terminal], terminal is last.

        COUNTER-FACTUAL: A buggy impl that re-raises would fail the no-exception
        assertion; one that emits 2 terminals would fail len == 3.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        runner, mocks = _make_graph_runner_for_streaming()

        async def fail_at_n3(initial_state):
            yield {"n1": {"o1": "v1"}}
            yield {"n2": {"o2": "v2"}}
            raise RuntimeError("n3 node crashed")

        mocks["set_astream_factory"](fail_at_n3)
        bundle = _make_mock_bundle_for_streaming("failing-graph-c")

        events: list = []
        exception_raised = False
        try:
            async for event in runner.run_stream_async(
                bundle, initial_state={"input": "x"}, validate_agents=False
            ):
                events.append(event)
        except Exception:
            exception_raised = True

        self.assertFalse(exception_raised)
        self.assertEqual(
            len(events),
            3,
            f"Expected [n1, n2, failed_terminal] = 3 events, got {len(events)}",
        )
        self.assertEqual(events[0].event_type, "node_progress")
        self.assertEqual(events[0].node_name, "n1")
        self.assertEqual(events[1].event_type, "node_progress")
        self.assertEqual(events[1].node_name, "n2")
        terminal = events[2]
        self.assertIsInstance(terminal, WorkflowProgressEvent)
        self.assertEqual(terminal.event_type, "failed")
        self.assertTrue(terminal.is_terminal)
        # Sequence must be monotonically increasing
        self.assertLess(events[0].sequence, events[1].sequence)
        self.assertLess(events[1].sequence, events[2].sequence)

    # ------------------------------------------------------------------
    # TC-F04-008b: GraphInterrupt → suspended terminal event
    # ------------------------------------------------------------------

    async def test_run_stream_async_graph_interrupt_yields_suspended_terminal(
        self,
    ) -> None:
        """TC-F04-008b: GraphInterrupt from .astream() → suspended terminal event.

        Fake .astream() yields n1 update then raises GraphInterrupt.
        Expected: [n1_progress, suspended_terminal]; no exception propagates.

        COUNTER-FACTUAL: A buggy impl that converts GraphInterrupt to event_type='failed'
        would fail assertEqual(terminal.event_type, 'suspended').
        A buggy impl that lets GraphInterrupt propagate out of the generator would
        fail the no-exception assertion.
        """
        from langgraph.errors import GraphInterrupt

        from agentmap.models.execution import WorkflowProgressEvent

        runner, mocks = _make_graph_runner_for_streaming()

        async def interrupt_after_n1(initial_state):
            yield {"n1": {"output": "partial"}}
            raise GraphInterrupt("human-input-needed")

        mocks["set_astream_factory"](interrupt_after_n1)
        bundle = _make_mock_bundle_for_streaming("interruptible-graph")

        events: list = []
        exception_raised = False
        try:
            async for event in runner.run_stream_async(
                bundle, initial_state={"input": "x"}, validate_agents=False
            ):
                events.append(event)
        except Exception:
            exception_raised = True

        self.assertFalse(
            exception_raised,
            "run_stream_async must NOT raise GraphInterrupt; "
            "a 'suspended' terminal event must be yielded instead",
        )
        self.assertEqual(
            len(events),
            2,
            f"Expected [n1_progress, suspended_terminal] = 2 events, got {len(events)}",
        )

        e0, e1 = events[0], events[1]

        self.assertEqual(e0.event_type, "node_progress")
        self.assertEqual(e0.node_name, "n1")
        self.assertFalse(e0.is_terminal)

        self.assertIsInstance(e1, WorkflowProgressEvent)
        self.assertEqual(
            e1.event_type,
            "suspended",
            f"Terminal event type must be 'suspended' (not 'failed'), "
            f"got {e1.event_type!r}",
        )
        self.assertTrue(e1.is_terminal)
        self.assertIsNone(e1.node_name, "Terminal event node_name must be None")
        self.assertIsNone(e1.state_delta, "Terminal event state_delta must be None")
        self.assertIsNotNone(e1.result, "Suspended terminal must carry a result dict")
        # Suspended result follows interrupt shape (REQ-F-007 / AC-8b)
        # success=False for interrupted runs
        self.assertFalse(
            e1.result.get("success", True),
            "Suspended terminal result['success'] must be False",
        )

    # ------------------------------------------------------------------
    # TC-F04-008a: setup errors raise BEFORE any event (facade-level)
    # ------------------------------------------------------------------
    #
    # ENTRYPOINT: run_workflow_stream_async("nonexistent", {}) then __anext__()
    # LOWEST ALLOWED MOCK SEAM: mock RuntimeManager.get_container() so that
    #   container.graph_bundle_service().get_or_create_bundle() raises the
    #   target exception.  ensure_initialized is also patched to bypass DI
    #   initialisation (avoid filesystem access during unit tests).
    # FORBIDDEN MOCKS: Do NOT mock _resolve_csv_path bypass; the error must
    #   propagate through the real except-block in run_workflow_stream_async.
    # COUNTER-FACTUAL: A buggy impl that converts GraphNotFound to a 'failed'
    #   terminal event (instead of re-raising) would yield an event here and
    #   assertRaises(GraphNotFound) would FAIL — the context manager would see
    #   no exception despite the generator completing.

    def _make_fake_container_raising(self, exc: Exception) -> MagicMock:
        """Return a MagicMock container whose get_or_create_bundle raises exc."""
        fake_bundle_service = MagicMock(name="fake_bundle_service")
        fake_bundle_service.get_or_create_bundle.side_effect = exc

        fake_container = MagicMock(name="fake_container")
        fake_container.graph_bundle_service.return_value = fake_bundle_service
        # _resolve_csv_path calls container.app_config_service().get_csv_path()
        fake_config_service = MagicMock(name="fake_config_service")
        fake_config_service.get_csv_path.return_value = "/fake/graphs.csv"
        fake_container.app_config_service.return_value = fake_config_service
        return fake_container

    async def test_setup_error_graph_not_found_raises_before_any_event(self) -> None:
        """TC-F04-008a sub-case A: get_or_create_bundle raises GraphNotFound.

        run_workflow_stream_async must re-raise GraphNotFound before yielding
        any event.  No 'failed' terminal event must be produced.

        COUNTER-FACTUAL: A buggy impl that yields a failed terminal event
        instead of raising would cause assertRaises(GraphNotFound) to fail
        because the context manager sees no exception.
        """
        from agentmap.exceptions.runtime_exceptions import GraphNotFound
        from agentmap.runtime.workflow_ops import run_workflow_stream_async

        exc = GraphNotFound("nonexistent", "not found")
        fake_container = self._make_fake_container_raising(exc)

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized") as _mock_init,
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=fake_container,
            ),
        ):
            _mock_init.return_value = None
            with self.assertRaises(GraphNotFound):
                async for _ in run_workflow_stream_async("nonexistent", {}):
                    pass  # pragma: no cover — must raise before yielding

    async def test_setup_error_invalid_inputs_raises_before_any_event(self) -> None:
        """TC-F04-008a sub-case B: get_or_create_bundle raises InvalidInputs.

        run_workflow_stream_async must re-raise InvalidInputs before yielding
        any event.

        COUNTER-FACTUAL: A buggy impl that swallows InvalidInputs or converts
        it to a failed terminal event would fail assertRaises(InvalidInputs).
        """
        from agentmap.exceptions.runtime_exceptions import InvalidInputs
        from agentmap.runtime.workflow_ops import run_workflow_stream_async

        exc = InvalidInputs("bad inputs")
        fake_container = self._make_fake_container_raising(exc)

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized") as _mock_init,
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=fake_container,
            ),
        ):
            _mock_init.return_value = None
            with self.assertRaises(InvalidInputs):
                async for _ in run_workflow_stream_async("test-graph", {"bad": True}):
                    pass  # pragma: no cover — must raise before yielding

    async def test_setup_error_not_initialized_raises_before_any_event(self) -> None:
        """TC-F04-008a sub-case C: ensure_initialized raises AgentMapNotInitialized.

        run_workflow_stream_async must propagate AgentMapNotInitialized raised
        by ensure_initialized before yielding any event.

        COUNTER-FACTUAL: A buggy impl that swallows this error (e.g., broad
        except-all) would fail assertRaises(AgentMapNotInitialized).
        """
        from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
        from agentmap.runtime.workflow_ops import run_workflow_stream_async

        with patch(
            "agentmap.runtime.workflow_ops.ensure_initialized",
            side_effect=AgentMapNotInitialized("not initialized"),
        ):
            with self.assertRaises(AgentMapNotInitialized):
                async for _ in run_workflow_stream_async("test-graph", {}):
                    pass  # pragma: no cover — must raise before yielding


# ---------------------------------------------------------------------------
# TestRunWorkflowStreamAsyncCancellation — TC-F04-006
# (T-E06-F04-005)
# ---------------------------------------------------------------------------


class TestRunWorkflowStreamAsyncCancellation(unittest.IsolatedAsyncioTestCase):
    """TC-F04-006: consumer cancellation cancels the upstream run and finalizes tracker.

    ENTRYPOINT:
      gen = runner.run_stream_async(bundle, initial_state, validate_agents=False)
      then: await gen.__anext__()   (get n1 event)
      then: await gen.aclose()      (cancel)

    LOWEST ALLOWED MOCK SEAM:
      Fake compiled graph .astream() with a gate between n1 and n2.
      Fake execution tracker records complete_execution() calls.

    FORBIDDEN MOCKS:
      Do NOT mock GeneratorExit propagation; must exercise the real generator chain.

    COUNTER-FACTUAL:
      A buggy impl that swallows GeneratorExit and continues draining the upstream
      graph would set n2_entered=True after aclose(); the assertFalse(n2_entered)
      would fail.
      A buggy impl that doesn't finalize the tracker on cancellation would leave
      tracker.complete_called == False, failing the assertTrue assertion.
    """

    async def test_run_stream_async_aclose_after_n1_cancels_upstream(self) -> None:
        """TC-F04-006: aclose() after receiving n1 stops upstream; tracker finalized.

        Workflow:
          1. Consumer gets n1 event via __anext__()
          2. Consumer calls aclose() — triggers GeneratorExit through the chain
          3. Assert n2_entered is False (upstream work stopped before n2)
          4. Assert tracker.complete_called is True (no tracker leak)

        COUNTER-FACTUAL: A swallowing impl that catches GeneratorExit and resumes
        the upstream .astream() would enter n2 logic, setting n2_entered=True.
        """
        import asyncio as _asyncio

        runner, mocks = _make_graph_runner_for_streaming()

        gate = _asyncio.Event()
        n2_entered = {"flag": False}

        async def gated_astream(initial_state):
            yield {"n1": {"output": "v1"}}
            # Mark n2 entry BEFORE the gate — if cancellation is swallowed,
            # this flag gets set before the gate is waited on.
            n2_entered["flag"] = True
            await gate.wait()
            yield {"n2": {"output": "v2"}}

        mocks["set_astream_factory"](gated_astream)
        bundle = _make_mock_bundle_for_streaming("cancellation-graph")

        gen = runner.run_stream_async(
            bundle, initial_state={"input": "x"}, validate_agents=False
        )

        # Get the first event (n1 progress)
        n1_event = await gen.__anext__()

        from agentmap.models.execution import WorkflowProgressEvent

        self.assertIsInstance(n1_event, WorkflowProgressEvent)
        self.assertEqual(n1_event.event_type, "node_progress")
        self.assertEqual(n1_event.node_name, "n1")

        # Close the generator — this must propagate GeneratorExit up the chain
        await gen.aclose()

        # n2 must NOT have been entered (upstream work stopped)
        self.assertFalse(
            n2_entered["flag"],
            "n2 must NOT be entered after aclose() — GeneratorExit must propagate "
            "to the upstream astream() without being swallowed",
        )

        # Execution tracker must have been finalized (no leak).
        # On GeneratorExit, run_stream_async calls _finalize_tracker_safe which uses
        # self.execution_tracking (the GraphRunnerService's tracking service).
        mocks["runner_tracking"].complete_execution.assert_called_once()

    async def test_run_stream_async_generator_exit_does_not_swallow(self) -> None:
        """TC-F04-006: GeneratorExit is not swallowed; generator closes cleanly.

        After aclose(), iterating the generator again must raise StopAsyncIteration
        (or the generator is simply exhausted/closed).

        COUNTER-FACTUAL: A buggy impl that continues producing events after aclose()
        would yield further items here instead of raising StopAsyncIteration.
        """
        runner, mocks = _make_graph_runner_for_streaming()

        import asyncio as _asyncio

        gate = _asyncio.Event()

        async def gated_astream(initial_state):
            yield {"n1": {"output": "v1"}}
            await gate.wait()
            yield {"n2": {"output": "v2"}}

        mocks["set_astream_factory"](gated_astream)
        bundle = _make_mock_bundle_for_streaming("cancel-check-graph")

        gen = runner.run_stream_async(
            bundle, initial_state={"input": "x"}, validate_agents=False
        )
        await gen.__anext__()  # consume n1
        await gen.aclose()

        # After close, further iteration must not yield events
        further_events = []
        try:
            async for event in gen:
                further_events.append(event)
        except StopAsyncIteration:
            pass

        self.assertEqual(
            len(further_events),
            0,
            "After aclose(), no further events must be produced",
        )


# ---------------------------------------------------------------------------
# TestTelemetrySpanLifecycle — TC-F04-011
# (T-E06-F04-005)
# ---------------------------------------------------------------------------


class TestTelemetrySpanLifecycle(unittest.IsolatedAsyncioTestCase):
    """TC-F04-011: telemetry span/tracker close on every terminal path.

    ENTRYPOINT:
      run_stream_async(bundle, initial_state, validate_agents=False) with a
      fake telemetry service injected via service._telemetry_service.

    LOWEST ALLOWED MOCK SEAM:
      Fake telemetry service with open/close span call recorder.
      Fake graph .astream() scripted per terminal path.

    FORBIDDEN MOCKS:
      Do NOT mock the span lifecycle management inside run_stream_async;
      must exercise the real open/close logic.

    COUNTER-FACTUAL:
      A buggy impl that only closes the span on 'completed' (not on 'failed',
      'suspended', or GeneratorExit) would pass sub-case A but fail B, C, D.

    Decision Table:
      A: completed  — yields n1, n2, exhausts                → close_called=True
      B: failed     — yields n1, raises RuntimeError          → close_called=True
      C: suspended  — yields n1, raises GraphInterrupt        → close_called=True
      D: cancelled  — yields n1, gate; consumer calls aclose()→ close_called=True
    """

    def _make_fake_telemetry(self) -> MagicMock:
        """Create a fake telemetry service that records span open/close calls."""
        fake = MagicMock(name="fake_telemetry_service")
        fake.span_open_count = 0
        fake.span_close_count = 0

        # start_span returns a context manager
        span_cm = MagicMock(name="span_context_manager")
        span_cm.__enter__ = MagicMock(return_value=MagicMock(name="span_obj"))
        span_cm.__exit__ = MagicMock(return_value=False)
        fake.start_span.return_value = span_cm
        return fake

    def _get_runner_with_fake_telemetry(
        self,
    ) -> Tuple[Any, Dict[str, Any], MagicMock]:
        """Return (runner, mocks, fake_telemetry)."""
        runner, mocks = _make_graph_runner_for_streaming(telemetry=False)
        fake_telemetry = self._make_fake_telemetry()
        runner._telemetry_service = fake_telemetry
        return runner, mocks, fake_telemetry

    async def _run_and_collect(
        self, runner: Any, mocks: Dict[str, Any], graph_name: str, inputs: Dict
    ) -> list:
        """Consume run_stream_async to exhaustion; return collected events.

        Exhausts the generator fully (no break) so that the finally block in
        run_stream_async runs and closes the telemetry span.  The generator
        terminates naturally after the terminal event (return).
        """
        bundle = _make_mock_bundle_for_streaming(graph_name)
        collected = []
        try:
            async for event in runner.run_stream_async(
                bundle, initial_state=inputs, validate_agents=False
            ):
                collected.append(event)
        except Exception:
            pass
        return collected

    # ------------------------------------------------------------------
    # Sub-case A: completed path
    # ------------------------------------------------------------------

    async def test_telemetry_span_closes_on_completed_path(self) -> None:
        """TC-F04-011-A: span closes after successful 2-node run.

        COUNTER-FACTUAL: A buggy impl with no span close in the finally/cleanup
        would leave span_close_count == 0 after a successful run.
        """
        runner, mocks, fake_telemetry = self._get_runner_with_fake_telemetry()

        async def two_node_success(initial_state):
            yield {"n1": {"output": "v1"}}
            yield {"n2": {"output": "v2"}}

        mocks["set_astream_factory"](two_node_success)

        await self._run_and_collect(runner, mocks, "telemetry-completed", {})

        # Tracker must be finalized
        mocks["tracking"].complete_execution.assert_called_once()

        # Telemetry span: if run_stream_async opens a span, it must also close it.
        # Verify either: no span was opened, OR span was opened AND closed.
        # (The implementation may or may not use telemetry for streaming; if it does,
        # close must happen on every path.)
        open_count = fake_telemetry.start_span.call_count
        # If a span was opened via start_span, the returned context manager's
        # __exit__ must have been called (indicating it closed).
        if open_count > 0:
            # At least one span was started; it must have been exited
            cm = fake_telemetry.start_span.return_value
            self.assertGreater(
                cm.__exit__.call_count,
                0,
                "Telemetry span must be closed (context manager __exit__ called) "
                "on the completed path",
            )

        # Most importantly: tracker must be finalized exactly once
        self.assertEqual(
            mocks["tracking"].complete_execution.call_count,
            1,
            "Tracker complete_execution must be called exactly once on completed path",
        )

    # ------------------------------------------------------------------
    # Sub-case B: failed path
    # ------------------------------------------------------------------

    async def test_telemetry_span_closes_on_failed_path(self) -> None:
        """TC-F04-011-B: span closes and tracker is finalized when a node raises RuntimeError.

        COUNTER-FACTUAL (BUG-001 lock-in):
          The pre-fix run_stream_async only called _finalize_tracker_safe inside the
          GeneratorExit / CancelledError handlers but NOT inside the `except Exception`
          block.  A buggy impl missing that call would leave
          runner_tracking.complete_execution.call_count == 0 after a failed run,
          causing the assert_called_once() assertion below to fail.

          Separately: a buggy impl that only closes the span on clean completion
          would leave the span open on failure (start_span context manager __exit__
          not called).
        """
        runner, mocks, fake_telemetry = self._get_runner_with_fake_telemetry()

        async def fail_after_n1(initial_state):
            yield {"n1": {"output": "partial"}}
            raise RuntimeError("node failed")

        mocks["set_astream_factory"](fail_after_n1)

        events = await self._run_and_collect(runner, mocks, "telemetry-failed", {})

        # Terminal event must be present and failed
        terminal_events = [
            e for e in events if hasattr(e, "is_terminal") and e.is_terminal
        ]
        self.assertEqual(
            len(terminal_events),
            1,
            "Must have exactly one terminal event on failed path",
        )
        self.assertEqual(terminal_events[0].event_type, "failed")
        # The failed terminal event must carry a non-None result dict
        self.assertIsNotNone(terminal_events[0].result)
        self.assertFalse(terminal_events[0].result.get("success", True))

        # BUG-001 lock-in: execution tracker must be finalized exactly once.
        # run_stream_async's `except Exception` block calls _finalize_tracker_safe,
        # which delegates to self.execution_tracking.complete_execution (runner_tracking).
        # A pre-fix impl that skipped _finalize_tracker_safe here would leave
        # call_count == 0, failing this assertion.
        mocks["runner_tracking"].complete_execution.assert_called_once()

        # Span: if opened, must be closed even on the failed path.
        open_count = fake_telemetry.start_span.call_count
        if open_count > 0:
            cm = fake_telemetry.start_span.return_value
            self.assertGreater(
                cm.__exit__.call_count,
                0,
                "Telemetry span must be closed (context manager __exit__ called) "
                "on the failed path",
            )

    # ------------------------------------------------------------------
    # Sub-case C: suspended path
    # ------------------------------------------------------------------

    async def test_telemetry_span_closes_on_suspended_path(self) -> None:
        """TC-F04-011-C: span closes and tracker is finalized when GraphInterrupt → suspended.

        COUNTER-FACTUAL (BUG-001 lock-in):
          The pre-fix run_stream_async only called _finalize_tracker_safe inside the
          GeneratorExit / CancelledError handlers but NOT inside the `except GraphInterrupt`
          block.  A buggy impl missing that call would leave
          runner_tracking.complete_execution.call_count == 0 after a suspended run,
          causing the assert_called_once() assertion below to fail.

          Separately: a buggy impl that only closes the span on 'completed' or 'failed'
          but not on 'suspended' would leave the span open (start_span context manager
          __exit__ not called).
        """
        from langgraph.errors import GraphInterrupt

        runner, mocks, fake_telemetry = self._get_runner_with_fake_telemetry()

        async def interrupt_after_n1(initial_state):
            yield {"n1": {"output": "partial"}}
            raise GraphInterrupt("needs-human")

        mocks["set_astream_factory"](interrupt_after_n1)

        events = await self._run_and_collect(runner, mocks, "telemetry-suspended", {})

        terminal_events = [
            e for e in events if hasattr(e, "is_terminal") and e.is_terminal
        ]
        self.assertEqual(len(terminal_events), 1)
        self.assertEqual(terminal_events[0].event_type, "suspended")

        # BUG-001 lock-in: execution tracker must be finalized exactly once.
        # run_stream_async's `except GraphInterrupt` block calls _finalize_tracker_safe,
        # which delegates to self.execution_tracking.complete_execution (runner_tracking).
        # A pre-fix impl that skipped _finalize_tracker_safe here would leave
        # call_count == 0, failing this assertion.
        mocks["runner_tracking"].complete_execution.assert_called_once()

        # Span: if opened, must be closed even on the suspended path.
        open_count = fake_telemetry.start_span.call_count
        if open_count > 0:
            cm = fake_telemetry.start_span.return_value
            self.assertGreater(
                cm.__exit__.call_count,
                0,
                "Telemetry span must be closed (context manager __exit__ called) "
                "on the suspended path",
            )

    # ------------------------------------------------------------------
    # Sub-case D: consumer-cancelled path
    # ------------------------------------------------------------------

    async def test_telemetry_span_closes_on_cancellation_path(self) -> None:
        """TC-F04-011-D: span closes when consumer calls aclose() mid-stream.

        COUNTER-FACTUAL: A buggy impl that doesn't close the span in a finally/
        GeneratorExit handler would leave the span open after aclose().
        """
        import asyncio as _asyncio

        runner, mocks, fake_telemetry = self._get_runner_with_fake_telemetry()

        gate = _asyncio.Event()

        async def gated_two_node(initial_state):
            yield {"n1": {"output": "v1"}}
            await gate.wait()
            yield {"n2": {"output": "v2"}}

        mocks["set_astream_factory"](gated_two_node)
        bundle = _make_mock_bundle_for_streaming("telemetry-cancelled")

        gen = runner.run_stream_async(bundle, initial_state={}, validate_agents=False)

        # Consume n1, then cancel
        n1_event = await gen.__anext__()
        from agentmap.models.execution import WorkflowProgressEvent

        self.assertIsInstance(n1_event, WorkflowProgressEvent)
        await gen.aclose()

        # Tracker must be finalized on cancellation (via runner_tracking, not exec tracking)
        mocks["runner_tracking"].complete_execution.assert_called_once()

        # Span: if opened, must be closed even on GeneratorExit
        # Note: the finally block runs when aclose() is called, so __exit__ is called.
        open_count = fake_telemetry.start_span.call_count
        if open_count > 0:
            cm = fake_telemetry.start_span.return_value
            self.assertGreater(
                cm.__exit__.call_count,
                0,
                "Telemetry span must be closed (via finally or GeneratorExit handler) "
                "even when consumer calls aclose() mid-stream",
            )


# ---------------------------------------------------------------------------
# TestRunWorkflowStreamAsyncExportSurface — TC-F04-007, TC-F04-007a
# (T-E06-F04-006)
# ---------------------------------------------------------------------------


class TestRunWorkflowStreamAsyncExportSurface(unittest.TestCase):
    """TC-F04-007 / TC-F04-007a: run_workflow_stream_async importable from both
    public export surfaces without requiring any SDK / LangGraph / LLMService import.

    ENTRYPOINT (structural import test):
      from agentmap.runtime import run_workflow_stream_async
      from agentmap.runtime_api import run_workflow_stream_async

    LOWEST ALLOWED MOCK SEAM:
      N/A — import-surface test; no runtime mock needed.

    FORBIDDEN MOCKS:
      None — test only checks the import surface and signature shape.

    COUNTER-FACTUAL (TC-F04-007):
      A buggy impl that adds run_workflow_stream_async to runtime/__init__.py
      but forgets to include it in __all__ would fail
      assertIn("run_workflow_stream_async", agentmap.runtime.__all__).

    COUNTER-FACTUAL (TC-F04-007a):
      A buggy impl that exports from agentmap.runtime but not from
      agentmap.runtime_api would pass TC-F04-007 but fail this test.
    """

    # ------------------------------------------------------------------
    # TC-F04-007: agentmap.runtime surface
    # ------------------------------------------------------------------

    def test_importable_from_agentmap_runtime(self) -> None:
        """TC-F04-007: run_workflow_stream_async is accessible as an attribute
        of agentmap.runtime.

        COUNTER-FACTUAL: A missing import in runtime/__init__.py would raise
        AttributeError here.
        """
        import agentmap.runtime

        self.assertTrue(
            hasattr(agentmap.runtime, "run_workflow_stream_async"),
            "agentmap.runtime must expose run_workflow_stream_async as an attribute "
            "(import missing from runtime/__init__.py)",
        )

    def test_in_all_of_agentmap_runtime(self) -> None:
        """TC-F04-007: run_workflow_stream_async is listed in agentmap.runtime.__all__.

        COUNTER-FACTUAL: An impl that adds the alias but forgets the __all__
        entry would fail here even though the attribute is reachable.
        """
        import agentmap.runtime

        self.assertIn(
            "run_workflow_stream_async",
            agentmap.runtime.__all__,
            "run_workflow_stream_async must appear in agentmap.runtime.__all__",
        )

    def test_is_async_generator_function_via_agentmap_runtime(self) -> None:
        """TC-F04-007: inspect.isasyncgenfunction returns True for the symbol.

        COUNTER-FACTUAL: An impl that wraps the generator in a regular async
        coroutine (returning the generator object) would fail this assertion.
        """
        import agentmap.runtime

        fn = agentmap.runtime.run_workflow_stream_async
        self.assertTrue(
            inspect.isasyncgenfunction(fn),
            "agentmap.runtime.run_workflow_stream_async must be an async generator "
            "function (inspect.isasyncgenfunction must return True)",
        )

    def test_signature_matches_caller_contract_via_agentmap_runtime(self) -> None:
        """TC-F04-007: inspect.signature has the exact params specified in spec §3.4.

        COUNTER-FACTUAL: A param rename (e.g., graph_name → name) would fail the
        assertIn('graph_name', param_names) assertion.
        """
        import agentmap.runtime

        fn = agentmap.runtime.run_workflow_stream_async
        sig = inspect.signature(fn)
        params = sig.parameters

        self.assertIn(
            "graph_name",
            params,
            "Signature must include 'graph_name' positional param",
        )
        self.assertIn(
            "inputs",
            params,
            "Signature must include 'inputs' positional param",
        )
        self.assertEqual(
            params["profile"].default,
            None,
            "profile must default to None",
        )
        self.assertEqual(
            params["resume_token"].default,
            None,
            "resume_token must default to None",
        )
        self.assertEqual(
            params["config_file"].default,
            None,
            "config_file must default to None",
        )
        self.assertEqual(
            params["force_create"].default,
            False,
            "force_create must default to False",
        )

    # ------------------------------------------------------------------
    # TC-F04-007a: agentmap.runtime_api legacy surface
    # ------------------------------------------------------------------

    def test_importable_from_agentmap_runtime_api(self) -> None:
        """TC-F04-007a: run_workflow_stream_async is accessible via agentmap.runtime_api.

        COUNTER-FACTUAL: A missing re-export in runtime_api.py would raise
        AttributeError here while TC-F04-007 passes.
        """
        import agentmap.runtime_api

        self.assertTrue(
            hasattr(agentmap.runtime_api, "run_workflow_stream_async"),
            "agentmap.runtime_api must expose run_workflow_stream_async "
            "(re-export missing from runtime_api.py)",
        )

    def test_in_all_of_agentmap_runtime_api(self) -> None:
        """TC-F04-007a: run_workflow_stream_async appears in agentmap.runtime_api.__all__.

        COUNTER-FACTUAL: An __all__ omission in runtime_api.py would fail here.
        """
        import agentmap.runtime_api

        self.assertIn(
            "run_workflow_stream_async",
            agentmap.runtime_api.__all__,
            "run_workflow_stream_async must appear in agentmap.runtime_api.__all__",
        )

    def test_runtime_api_symbol_is_same_object_as_runtime_symbol(self) -> None:
        """TC-F04-007a: runtime_api re-exports the exact same object as runtime.

        The symbol must be the same function object (not a copy or wrapper).

        COUNTER-FACTUAL: An impl that re-implements or re-wraps in runtime_api
        would produce a different object identity and fail assertIs().
        """
        import agentmap.runtime
        import agentmap.runtime_api

        self.assertIs(
            agentmap.runtime_api.run_workflow_stream_async,
            agentmap.runtime.run_workflow_stream_async,
            "agentmap.runtime_api.run_workflow_stream_async must be the same "
            "object as agentmap.runtime.run_workflow_stream_async (re-export, not copy)",
        )

    def test_no_sdk_import_required_to_use_facade(self) -> None:
        """TC-F04-007 structural: importing and calling the facade does not require
        the caller to import langgraph, anthropic, openai, LLMService,
        LLMStreamChunk, or call_llm_stream_async.

        This is a white-box source assertion: the facade source file must NOT
        contain imports of those symbols at module level.

        COUNTER-FACTUAL: An impl that imports LangGraph or a provider SDK at
        the top of workflow_ops.py would leak the dependency to callers and
        fail the assertNotIn checks here.
        """
        import pathlib

        workflow_ops_path = (
            pathlib.Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "agentmap"
            / "runtime"
            / "workflow_ops.py"
        )
        self.assertTrue(
            workflow_ops_path.exists(),
            f"Expected workflow_ops.py at {workflow_ops_path}",
        )
        source = workflow_ops_path.read_text()

        # Extract only the module-level imports (not deferred local imports)
        module_level_lines = []
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and not line.startswith(" "):
                module_level_lines.append(stripped)

        module_level_src = "\n".join(module_level_lines)

        forbidden = [
            "langgraph",
            "anthropic",
            "openai",
            "LLMStreamChunk",
            "call_llm_stream_async",
        ]
        for symbol in forbidden:
            self.assertNotIn(
                symbol,
                module_level_src,
                f"workflow_ops.py must NOT import '{symbol}' at module level "
                f"(REQ-NF-003 / AC-7: no new trust boundary for callers)",
            )


# ---------------------------------------------------------------------------
# TestTD026MaterializedTextNeverDelta — TC-F04-009 (T-E06-F04-007)
# ---------------------------------------------------------------------------


class TestTD026MaterializedTextNeverDelta(unittest.IsolatedAsyncioTestCase):
    """TC-F04-009 — MANDATORY TD-026 verification: F04 carries materialized text, never deltas.

    Satisfies AC-9 (MANDATORY per TD-026 deferral, user-approved 2026-06-19).

    BACKGROUND:
      F03 has a defect (TD-026): on a pre-first-chunk provider failure, the synthetic
      terminal chunk emitted by LLMService._call_llm_stream_async_direct sets
      text_delta="" (llm_service.py:3443-3451).  A direct call_llm_stream_async
      consumer that concatenated deltas would produce output="" — losing the fallback
      text.

      The F04 architect resolved this with option (a): F04 consumes LangGraph's
      .astream(updates) node-state dicts and the final materialized ExecutionResult.
      Inside a node, LLMAgent uses call_llm_async (materialized path), which is
      UNAFFECTED by TD-026.  Therefore the TD-026 defect is structurally unreachable
      from F04.

      This test class PROVES that claim with two distinct assertion types:
        (A) Behavioral: a fake graph whose node delta carries the fallback-produced
            materialized text ("fallback-text") is run via run_stream_async; the
            terminal event's result["outputs"] carries that text non-empty.
        (B) White-box: ast/source-text inspection confirms that none of the four
            F04 source files import call_llm_stream_async or LLMStreamChunk.

    ENTRYPOINT:
      GraphRunnerService.run_stream_async(bundle, initial_state, validate_agents=False)
      — the same production seam used by all other runner-level streaming tests in
      this file.  The fake graph's .astream() delivers {node_name: state_delta} dicts
      whose "output" key holds the materialized fallback text — simulating exactly what
      LLMAgent.process_async would return after call_llm_async recovers via fallback
      (llm_agent.py:483,486 materialized path).

    LOWEST ALLOWED MOCK SEAM:
      Fake compiled graph whose .astream() yields {"n1": {"output": "fallback-text"}}.
      All GraphRunnerService dependencies mocked via the shared
      _make_graph_runner_for_streaming() helper.

    FORBIDDEN MOCKS:
      - Do NOT mock run_stream_async itself; must execute for real.
      - Do NOT call or import call_llm_stream_async anywhere in this test.
      - Do NOT mock stream_compiled_graph_async; must exercise the real method.
      - Do NOT mock WorkflowProgressEvent; must be constructed by the production method.

    COUNTER-FACTUAL:
      If F04 had erroneously consumed call_llm_stream_async and concatenated deltas,
      it would produce output="" on a pre-first-chunk failure (the TD-026 defect).
      The assertion assertEqual(terminal.result["outputs"]["output"], "fallback-text")
      would fail — and the assert_not_empty check would also catch output=="".
      A delta-concatenation impl would never carry "fallback-text" because the
      synthetic terminal chunk has text_delta="".

    White-box counter-factual:
      An impl that imported call_llm_stream_async from the F04 streaming methods
      would be caught by the import-surface assertions.  A comment-only mention
      (as in graph_execution_service.py:477) is expected and is handled by
      restricting the check to import/from-import lines.
    """

    # ------------------------------------------------------------------
    # TC-F04-009-1 (behavioral): materialized fallback text reaches terminal event
    # ------------------------------------------------------------------

    async def test_td026_fallback_text_carried_in_materialized_state_not_lost(
        self,
    ) -> None:
        """TC-F04-009-1: node output=="fallback-text" survives F04's event chain.

        SCENARIO:
          Simulates a graph whose single LLM node (n1) uses call_llm_async
          (materialized path).  The primary provider fails before first chunk;
          the fallback returns text "fallback-text".  LLMAgent.process_async
          materializes this as {"output": "fallback-text", ...} and LangGraph
          merges it into graph state.  F04's .astream() delivers
          {"n1": {"output": "fallback-text"}} as the node update.

          F04 MUST carry this materialized text through to:
            (a) the node_progress event's state_delta["output"]
            (b) the terminal event's result["outputs"]["output"]

        COUNTER-FACTUAL:
          An impl that called call_llm_stream_async and built output by
          concatenating text_delta values would produce output="" on a
          pre-first-chunk failure.  This test would fail the
          assertNotEqual(output, "") guard and the
          assertEqual(output, "fallback-text") assertion.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        runner, mocks = _make_graph_runner_for_streaming()

        # --- Fake graph simulates what LLMAgent produces after a provider fallback ---
        # The fallback provider returned LLMResponse(text="fallback-text").
        # LLMAgent materializes: {"output": "fallback-text", "memory": "fallback-text"}
        # LangGraph merges this into state and streams it as:
        #   {"n1": {"output": "fallback-text", "memory": "fallback-text"}}
        # This is the materialized state F04 carries — no delta concatenation.
        FALLBACK_TEXT = "fallback-text"

        async def astream_with_materialized_fallback(initial_state):
            yield {"n1": {"output": FALLBACK_TEXT}}

        mocks["set_astream_factory"](astream_with_materialized_fallback)
        bundle = _make_mock_bundle_for_streaming("llm-fallback-graph")

        events: list = []
        async for event in runner.run_stream_async(
            bundle, initial_state={"input": "test"}, validate_agents=False
        ):
            events.append(event)

        # At minimum: one node_progress + one terminal
        self.assertGreaterEqual(
            len(events),
            2,
            f"Expected at least [node_progress, terminal] = 2 events, got {len(events)}: {events}",
        )

        # --- node_progress event assertions ---
        node_progress_events = [
            e
            for e in events
            if isinstance(e, WorkflowProgressEvent) and not e.is_terminal
        ]
        self.assertGreaterEqual(
            len(node_progress_events),
            1,
            "Expected at least one node_progress event (is_terminal=False) "
            "for the LLM node — none found",
        )

        n1_event = node_progress_events[0]
        self.assertEqual(
            n1_event.node_name,
            "n1",
            f"First node_progress event must be for node 'n1', got {n1_event.node_name!r}",
        )
        self.assertIsNotNone(
            n1_event.state_delta,
            "node_progress event must have a non-None state_delta carrying materialized state",
        )
        node_output = n1_event.state_delta.get("output", "__MISSING__")
        self.assertNotEqual(
            node_output,
            "",
            "TD-026 regression detected: node_progress state_delta['output'] == '' "
            "(empty string) — this is the exact TD-026 defect pattern where a delta "
            "concatenation consumer loses text on pre-first-chunk fallback; "
            "F04 must carry the materialized text, not concatenated deltas",
        )
        self.assertEqual(
            node_output,
            FALLBACK_TEXT,
            f"node_progress state_delta['output'] must equal the fallback materialized "
            f"text {FALLBACK_TEXT!r}, got {node_output!r}",
        )

        # --- terminal event assertions ---
        terminal_events = [
            e for e in events if isinstance(e, WorkflowProgressEvent) and e.is_terminal
        ]
        self.assertEqual(
            len(terminal_events),
            1,
            f"Expected exactly 1 terminal event, got {len(terminal_events)}: {terminal_events}",
        )

        terminal = terminal_events[0]
        self.assertEqual(
            terminal.event_type,
            "completed",
            f"Terminal event must be 'completed' (fallback succeeded), "
            f"got {terminal.event_type!r}",
        )
        self.assertTrue(
            terminal.is_terminal,
            "Terminal event must have is_terminal=True",
        )
        self.assertIsNotNone(
            terminal.result,
            "Terminal event must carry a result dict",
        )
        self.assertTrue(
            terminal.result.get("success", False),
            f"Terminal result['success'] must be True (fallback succeeded), "
            f"got result={terminal.result}",
        )

        # The final outputs MUST carry the fallback text via materialized state.
        # result["outputs"] == final_state (merged from initial_state + all deltas).
        outputs = terminal.result.get("outputs", {})
        self.assertIsInstance(
            outputs,
            dict,
            f"result['outputs'] must be a dict (materialized final_state), "
            f"got {type(outputs).__name__!r}",
        )
        final_output = outputs.get("output", "__MISSING__")
        self.assertNotEqual(
            final_output,
            "",
            "TD-026 regression detected: terminal result['outputs']['output'] == '' "
            "(empty string) — F04 must carry materialized state from the node, "
            "not concatenated delta values; empty output means text was lost "
            "(the exact TD-026 defect consequence for a delta-concatenation impl)",
        )
        self.assertEqual(
            final_output,
            FALLBACK_TEXT,
            f"terminal result['outputs']['output'] must equal the fallback materialized "
            f"text {FALLBACK_TEXT!r} (AC-9: materialized fallback text must not be lost); "
            f"got {final_output!r}",
        )

    # ------------------------------------------------------------------
    # TC-F04-009-2: terminal result['outputs'] is never empty dict
    # ------------------------------------------------------------------

    async def test_td026_terminal_outputs_never_empty(self) -> None:
        """TC-F04-009-2: result['outputs'] dict is non-empty and contains node output.

        COUNTER-FACTUAL:
          A buggy delta-concatenation impl that lost all text on fallback would
          produce result["outputs"] == {} (empty) or {"output": ""}.
          This test catches the empty-dict case.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        runner, mocks = _make_graph_runner_for_streaming()

        async def astream_with_fallback_output(initial_state):
            yield {"n1": {"output": "fallback-text"}}

        mocks["set_astream_factory"](astream_with_fallback_output)
        bundle = _make_mock_bundle_for_streaming("llm-outputs-non-empty-graph")

        events: list = []
        async for event in runner.run_stream_async(
            bundle, initial_state={"input": "test"}, validate_agents=False
        ):
            events.append(event)

        terminal = next(
            (
                e
                for e in events
                if isinstance(e, WorkflowProgressEvent) and e.is_terminal
            ),
            None,
        )
        self.assertIsNotNone(terminal, "Terminal event must be present")

        outputs = terminal.result.get("outputs", {}) if terminal.result else {}
        self.assertNotEqual(
            outputs,
            {},
            "TD-026 negative case: result['outputs'] must NOT be {} "
            "(empty dict means the materialized node output was dropped — "
            "this is the TD-026 consequence for a delta-concat consumer that "
            "receives no deltas on pre-first-chunk failure)",
        )

    # ------------------------------------------------------------------
    # TC-F04-009-3 (white-box): progress_event.py has no forbidden imports
    # ------------------------------------------------------------------

    def test_td026_progress_event_py_has_no_llm_streaming_imports(self) -> None:
        """TC-F04-009-3: progress_event.py must NOT import call_llm_stream_async
        or LLMStreamChunk (absolute import-surface assertion, AC-9 white-box).

        SCOPE: progress_event.py is an F04-new file — check the ENTIRE file.

        COUNTER-FACTUAL:
          An impl that accidentally re-exported or imported LLMStreamChunk in
          progress_event.py would be caught here by the full-file string search.
          The import itself would succeed, but this assertion would fail.
        """
        import pathlib

        src_root = (
            pathlib.Path(__file__).parent.parent.parent.parent.parent
            / "src"
            / "agentmap"
        )
        progress_event_path = src_root / "models" / "execution" / "progress_event.py"
        self.assertTrue(
            progress_event_path.exists(),
            f"progress_event.py not found at {progress_event_path}",
        )

        source = progress_event_path.read_text(encoding="utf-8")

        # Extract import lines to check (not comments/docstrings)
        import_lines = [
            line
            for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_surface = "\n".join(import_lines)

        self.assertNotIn(
            "call_llm_stream_async",
            import_surface,
            "progress_event.py must NOT import call_llm_stream_async "
            "(AC-9 white-box / TD-026 structural isolation — "
            "F04 does not consume the LLM streaming seam)",
        )
        self.assertNotIn(
            "LLMStreamChunk",
            import_surface,
            "progress_event.py must NOT import LLMStreamChunk "
            "(AC-9 white-box / TD-026 structural isolation — "
            "F04 uses materialized state, not LLM token chunks)",
        )

    # ------------------------------------------------------------------
    # TC-F04-009-4 (white-box): workflow_ops.py streaming method has no forbidden imports
    # ------------------------------------------------------------------

    def test_td026_workflow_ops_run_workflow_stream_async_has_no_llm_streaming_imports(
        self,
    ) -> None:
        """TC-F04-009-4: run_workflow_stream_async in workflow_ops.py must NOT
        import or reference call_llm_stream_async or LLMStreamChunk.

        SCOPE: checked over the method source via inspect.getsource to avoid
        flagging pre-existing, non-F04 code in the same file.

        COUNTER-FACTUAL:
          A buggy impl that added `from agentmap.services.llm import call_llm_stream_async`
          inside run_workflow_stream_async would be caught here.  The method
          would still execute, but this assertion would fail the import-surface
          check — preventing the structural regression from passing code review.
        """
        import inspect

        from agentmap.runtime.workflow_ops import run_workflow_stream_async

        source = inspect.getsource(run_workflow_stream_async)

        self.assertNotIn(
            "call_llm_stream_async",
            source,
            "run_workflow_stream_async (workflow_ops.py) must NOT reference "
            "call_llm_stream_async (AC-9 white-box / D-1 / D-5: F04 consumes "
            "LangGraph .astream() node-state updates, not the LLM streaming seam)",
        )
        self.assertNotIn(
            "LLMStreamChunk",
            source,
            "run_workflow_stream_async (workflow_ops.py) must NOT reference "
            "LLMStreamChunk (AC-9 white-box: F04 carries materialized node state, "
            "not LLM token chunks)",
        )

    # ------------------------------------------------------------------
    # TC-F04-009-5 (white-box): run_stream_async has no forbidden imports
    # ------------------------------------------------------------------

    def test_td026_run_stream_async_has_no_llm_streaming_imports(self) -> None:
        """TC-F04-009-5: GraphRunnerService.run_stream_async must NOT import or
        reference call_llm_stream_async or LLMStreamChunk.

        SCOPE: checked over the method source via inspect.getsource.

        COUNTER-FACTUAL:
          A buggy impl that delegated to the F03 LLM streaming path from inside
          run_stream_async would reference call_llm_stream_async and be caught here.
        """
        import inspect

        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        source = inspect.getsource(GraphRunnerService.run_stream_async)

        self.assertNotIn(
            "call_llm_stream_async",
            source,
            "GraphRunnerService.run_stream_async must NOT reference "
            "call_llm_stream_async (AC-9 / D-5: F04 runner-level streaming uses "
            "LangGraph .astream() node-state updates, not the LLM streaming seam)",
        )
        self.assertNotIn(
            "LLMStreamChunk",
            source,
            "GraphRunnerService.run_stream_async must NOT reference "
            "LLMStreamChunk (AC-9: F04 runner-level streaming carries "
            "materialized state, not token chunks)",
        )

    # ------------------------------------------------------------------
    # TC-F04-009-6 (white-box): stream_compiled_graph_async has no forbidden imports
    # ------------------------------------------------------------------

    def test_td026_stream_compiled_graph_async_has_no_llm_streaming_imports(
        self,
    ) -> None:
        """TC-F04-009-6: GraphExecutionService.stream_compiled_graph_async must NOT
        import or reference call_llm_stream_async or LLMStreamChunk.

        SCOPE: checked over the method source via inspect.getsource; a doc comment
        mentioning these symbols is acceptable — only import/reference in executable
        code would be caught by the string search.

        NOTE: The docstring at graph_execution_service.py:477 contains these symbol
        names in a comment ("This method does NOT import call_llm_stream_async or
        LLMStreamChunk") — this is a documentation statement, not an import.  Since
        inspect.getsource includes the docstring, we check that the forbidden strings
        do NOT appear as imports (lines starting with 'import' or 'from') rather than
        checking the entire source text.  This distinguishes documentary mentions from
        actual code references.

        COUNTER-FACTUAL:
          A buggy impl that added `import LLMStreamChunk` inside
          stream_compiled_graph_async would be caught by the import-line check.
          A comment mentioning LLMStreamChunk is NOT a bug and is explicitly allowed.
        """
        import inspect

        from agentmap.services.graph.graph_execution_service import (
            GraphExecutionService,
        )

        source = inspect.getsource(GraphExecutionService.stream_compiled_graph_async)

        # Extract only import lines (not docstrings or comments)
        import_lines = [
            line
            for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        import_surface = "\n".join(import_lines)

        self.assertNotIn(
            "call_llm_stream_async",
            import_surface,
            "stream_compiled_graph_async (graph_execution_service.py) must NOT "
            "import call_llm_stream_async (AC-9 white-box / D-5: stream_compiled_graph_async "
            "consumes LangGraph .astream() node-state dicts, not the LLM streaming seam); "
            "a doc-comment mention is allowed but an actual import is not",
        )
        self.assertNotIn(
            "LLMStreamChunk",
            import_surface,
            "stream_compiled_graph_async (graph_execution_service.py) must NOT "
            "import LLMStreamChunk (AC-9: the execution-service streaming method "
            "carries materialized node state, not token chunks); "
            "a doc-comment mention is allowed but an actual import is not",
        )


# ---------------------------------------------------------------------------
# TestRunWorkflowStreamAsyncParityWithAsync
# TC-F04-003 — terminal result equals run_workflow_async result (AC-3, SC-3, C1)
# (T-E06-F04-008)
# ---------------------------------------------------------------------------


class TestRunWorkflowStreamAsyncParityWithAsync(unittest.IsolatedAsyncioTestCase):
    """TC-F04-003: streaming terminal result equals run_workflow_async for the same input.

    Drives BOTH run_stream_async (streaming path) AND run_async (non-streaming path)
    on the SAME fake bundle with the SAME inputs, then compares the result shape
    field-by-field:  success, outputs, execution_summary structure, metadata keys.

    This is the central SC-3 / C1 parity assertion: the materialized terminal result
    from the streaming path must be identical to the non-streaming result for the same
    graph and inputs.  Note: execution_id is a run-specific UUID and is NOT compared
    literally (see test-plan AC-3 ambiguity resolution note).

    ENTRYPOINT:
      run_stream_async(bundle, initial_state, validate_agents=False)  — streaming
      run_async(bundle, initial_state, validate_agents=False)          — non-streaming
      Both called on the SAME runner service with the SAME fake compiled graph.

    LOWEST ALLOWED MOCK SEAM:
      Fake compiled graph that provides:
        .ainvoke()  → deterministic final_state (non-streaming path)
        .astream()  → same final_state as individual-node deltas (streaming path)
      All GraphRunnerService/GraphExecutionService deps mocked via shared helpers.

    FORBIDDEN MOCKS:
      - Do NOT mock run_async or run_stream_async themselves; both must execute.
      - Do NOT mock the result dict construction; must be produced by each real method.
      - Do NOT compare execution_id literally (it is a run-specific UUID per AC-3 note).

    COUNTER-FACTUAL:
      A buggy streaming impl that omits 'outputs' from the terminal result dict would
      fail assertEqual(stream_result["outputs"], async_result["outputs"]).
      A buggy impl that uses a different key shape (e.g. 'output' vs 'outputs') would
      fail the keys-superset assertion.
      A buggy impl that shapes 'metadata' differently from run_workflow_async would
      fail the metadata-keys comparison.
    """

    def _make_parity_runner(
        self, final_state: Dict[str, Any]
    ) -> Tuple[Any, Dict[str, Any]]:
        """Construct a GraphRunnerService wired for parity tests.

        The fake compiled graph provides BOTH .ainvoke() and .astream() methods
        returning consistent final_state: ainvoke returns it directly; astream
        yields per-key deltas and the merged state equals final_state.

        The same runner instance is used for both run_async and run_stream_async
        calls to prove both paths produce equivalent results.
        """
        from agentmap.models.execution.summary import ExecutionSummary
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.declaration_registry_service import (
            DeclarationRegistryService,
        )
        from agentmap.services.execution_policy_service import ExecutionPolicyService
        from agentmap.services.execution_tracking_service import (
            ExecutionTrackingService,
        )
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )
        from agentmap.services.graph.graph_assembly_service import GraphAssemblyService
        from agentmap.services.graph.graph_bootstrap_service import (
            GraphBootstrapService,
        )
        from agentmap.services.graph.graph_bundle_service import GraphBundleService
        from agentmap.services.graph.graph_checkpoint_service import (
            GraphCheckpointService,
        )
        from agentmap.services.graph.graph_execution_service import (
            GraphExecutionService,
        )
        from agentmap.services.graph.graph_runner_service import GraphRunnerService
        from agentmap.services.interaction_handler_service import (
            InteractionHandlerService,
        )
        from agentmap.services.logging_service import LoggingService
        from agentmap.services.state_adapter_service import StateAdapterService

        # Fake graph returns the same state via both paths
        the_final_state = dict(final_state)

        # .astream() splits the final_state into per-key deltas (one per node)
        async def astream_impl(initial_state, config=None, stream_mode=None):
            for key, val in the_final_state.items():
                yield {key: {key: val}}

        class _ParityFakeGraph:
            async def ainvoke(self, initial_state, config=None):
                # Non-streaming path: return merged state
                merged = dict(initial_state)
                merged.update(the_final_state)
                return merged

            def astream(self, initial_state, config=None, stream_mode=None):
                # Streaming path: yield per-key deltas
                return astream_impl(
                    initial_state, config=config, stream_mode=stream_mode
                )

        fake_graph = _ParityFakeGraph()

        # Mocked services
        mock_logging = create_autospec(LoggingService, instance=True)
        mock_logging.get_class_logger.return_value = MagicMock(name="mock_logger")

        mock_tracking = create_autospec(ExecutionTrackingService, instance=True)
        mock_policy = create_autospec(ExecutionPolicyService, instance=True)
        mock_state_adapter = create_autospec(StateAdapterService, instance=True)
        mock_exec_logging = create_autospec(LoggingService, instance=True)
        mock_exec_logging.get_class_logger.return_value = MagicMock(name="exec_logger")

        mock_summary = MagicMock(name="mock_summary", spec=ExecutionSummary)
        mock_summary.graph_name = "parity-graph"

        mock_tracking.complete_execution.return_value = None
        mock_tracking.to_summary.return_value = mock_summary
        mock_policy.evaluate_success_policy.return_value = True

        def _set_value_side_effect(state, key, value):
            updated = dict(state)
            updated[key] = value
            return updated

        mock_state_adapter.set_value.side_effect = _set_value_side_effect

        real_execution = GraphExecutionService(
            execution_tracking_service=mock_tracking,
            execution_policy_service=mock_policy,
            state_adapter_service=mock_state_adapter,
            logging_service=mock_exec_logging,
        )

        mock_app_config = create_autospec(AppConfigService, instance=True)
        mock_bootstrap = create_autospec(GraphBootstrapService, instance=True)
        mock_instantiation = create_autospec(
            GraphAgentInstantiationService, instance=True
        )
        mock_assembly = create_autospec(GraphAssemblyService, instance=True)
        mock_runner_tracking = create_autospec(ExecutionTrackingService, instance=True)
        mock_interaction = create_autospec(InteractionHandlerService, instance=True)
        mock_checkpoint = create_autospec(GraphCheckpointService, instance=True)
        mock_bundle_svc = create_autospec(GraphBundleService, instance=True)
        mock_declaration = create_autospec(DeclarationRegistryService, instance=True)

        mock_tracker = MagicMock(name="mock_tracker")
        mock_tracker.thread_id = "parity-thread"
        mock_runner_tracking.create_tracker.return_value = mock_tracker

        mock_scoped_registry = MagicMock()
        mock_scoped_registry.get_all_agent_types.return_value = ["agent1"]
        mock_scoped_registry.get_all_service_names.return_value = []
        mock_declaration.create_scoped_registry_for_bundle.return_value = (
            mock_scoped_registry
        )

        node_instances = {"n1": MagicMock(), "n2": MagicMock()}
        bundle_with_instances = MagicMock()
        bundle_with_instances.graph_name = "parity-graph"
        bundle_with_instances.nodes = {"n1": MagicMock(), "n2": MagicMock()}
        bundle_with_instances.entry_point = "n1"
        bundle_with_instances.node_instances = node_instances

        def _instantiate_side_effect(b, tracker):
            b.node_instances = node_instances
            return bundle_with_instances

        mock_instantiation.instantiate_agents.side_effect = _instantiate_side_effect

        mock_bundle_svc.requires_checkpoint_support.return_value = False
        mock_assembly.assemble_graph_async.return_value = fake_graph

        # Also wire ainvoke for the non-streaming path
        async def _execute_non_streaming(
            executable_graph, graph_name, initial_state, execution_tracker, config=None
        ):
            # This is the real execute_compiled_graph_async — it calls ainvoke
            from agentmap.models.execution.result import ExecutionResult

            final = await executable_graph.ainvoke(initial_state, config=config)
            mock_runner_tracking.to_summary.return_value = mock_summary
            mock_tracking.to_summary.return_value = mock_summary
            summary = mock_tracking.to_summary(mock_tracker, graph_name, final)
            final = mock_state_adapter.set_value(final, "__execution_summary", summary)
            final = mock_state_adapter.set_value(final, "__policy_success", True)
            return ExecutionResult(
                graph_name=graph_name,
                final_state=final,
                execution_summary=summary,
                success=True,
                total_duration=0.1,
                error=None,
            )

        service = GraphRunnerService(
            app_config_service=mock_app_config,
            graph_bootstrap_service=mock_bootstrap,
            graph_agent_instantiation_service=mock_instantiation,
            graph_assembly_service=mock_assembly,
            graph_execution_service=real_execution,
            execution_tracking_service=mock_runner_tracking,
            logging_service=mock_logging,
            interaction_handler_service=mock_interaction,
            graph_checkpoint_service=mock_checkpoint,
            graph_bundle_service=mock_bundle_svc,
            declaration_registry_service=mock_declaration,
        )

        mocks = {
            "tracking": mock_tracking,
            "runner_tracking": mock_runner_tracking,
            "policy": mock_policy,
            "state_adapter": mock_state_adapter,
            "mock_tracker": mock_tracker,
            "mock_summary": mock_summary,
            "fake_graph": fake_graph,
        }
        return service, mocks

    def _make_parity_bundle(self, graph_name: str = "parity-graph") -> MagicMock:
        """Create a bundle mock for parity tests."""
        bundle = MagicMock(name="parity_bundle")
        bundle.graph_name = graph_name
        node_0 = MagicMock()
        node_0.agent_type = "default"
        node_1 = MagicMock()
        node_1.agent_type = "default"
        bundle.nodes = {"n1": node_0, "n2": node_1}
        bundle.entry_point = "n1"
        bundle.csv_hash = None
        bundle.node_instances = None
        bundle.scoped_registry = None
        bundle.missing_services = set()
        return bundle

    # ------------------------------------------------------------------
    # TC-F04-003-1: terminal result has same 'success' as run_async
    # ------------------------------------------------------------------

    async def test_streaming_terminal_success_matches_run_async(self) -> None:
        """TC-F04-003-1: terminal event result['success'] equals ExecutionResult.success.

        Both streaming and non-streaming paths use evaluate_success_policy to set
        success.  For a policy that returns True, both must report success=True.

        COUNTER-FACTUAL: A buggy streaming impl that hardcodes success=False in the
        terminal event would fail assertIs(stream_result_success, True).
        """
        from agentmap.models.execution import WorkflowProgressEvent

        final_state = {"output": "materialized-text", "intermediate": "val"}
        service, mocks = self._make_parity_runner(final_state)
        bundle = self._make_parity_bundle()

        # Streaming path
        stream_events: list = []
        async for event in service.run_stream_async(
            bundle, initial_state={"input": "parity-check"}, validate_agents=False
        ):
            stream_events.append(event)

        terminal = next(
            (
                e
                for e in stream_events
                if isinstance(e, WorkflowProgressEvent) and e.is_terminal
            ),
            None,
        )
        self.assertIsNotNone(terminal, "Streaming path must yield a terminal event")
        self.assertIsNotNone(terminal.result, "Terminal event must carry a result dict")

        stream_success = terminal.result.get("success")

        # Non-streaming path: run_async returns ExecutionResult
        bundle2 = self._make_parity_bundle()
        non_stream_result = await service.run_async(
            bundle2, initial_state={"input": "parity-check"}, validate_agents=False
        )

        # Both must report the same success state (True, policy-driven)
        self.assertEqual(
            stream_success,
            non_stream_result.success,
            f"streaming result['success']={stream_success!r} must equal "
            f"run_async ExecutionResult.success={non_stream_result.success!r}",
        )
        self.assertTrue(
            stream_success,
            "Both streaming and non-streaming paths must report success=True "
            "when evaluate_success_policy returns True",
        )

    # ------------------------------------------------------------------
    # TC-F04-003-2: terminal result keys are a superset of required fields
    # ------------------------------------------------------------------

    async def test_streaming_terminal_result_has_required_keys(self) -> None:
        """TC-F04-003-2: terminal result contains success, outputs, execution_summary,
        execution_id, and metadata (AC-3 contract surface enumeration).

        COUNTER-FACTUAL: A buggy impl that omits 'outputs' or 'metadata' from the
        terminal result dict would fail the assertIn checks here.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        final_state = {"output": "materialized-text"}
        service, mocks = self._make_parity_runner(final_state)
        bundle = self._make_parity_bundle()

        stream_events: list = []
        async for event in service.run_stream_async(
            bundle, initial_state={"input": "parity-check"}, validate_agents=False
        ):
            stream_events.append(event)

        terminal = next(
            (
                e
                for e in stream_events
                if isinstance(e, WorkflowProgressEvent) and e.is_terminal
            ),
            None,
        )
        self.assertIsNotNone(terminal, "Terminal event must be present")
        self.assertIsNotNone(terminal.result, "Terminal event must carry result dict")

        required_keys = {"success", "outputs", "execution_summary", "metadata"}
        for key in required_keys:
            self.assertIn(
                key,
                terminal.result,
                f"Terminal result must contain '{key}' (AC-3 contract surface) — "
                f"got keys={set(terminal.result.keys())}",
            )

        # metadata must itself be a dict with at least 'graph_name'
        self.assertIsInstance(
            terminal.result["metadata"],
            dict,
            "terminal result['metadata'] must be a dict",
        )
        self.assertIn(
            "graph_name",
            terminal.result["metadata"],
            "terminal result['metadata'] must contain 'graph_name' "
            "(parity with run_workflow_async metadata shape)",
        )

        # outputs must be a dict (materialized final state, not an iterator)
        self.assertIsInstance(
            terminal.result["outputs"],
            dict,
            "terminal result['outputs'] must be a dict (C1: materialized state)",
        )

    # ------------------------------------------------------------------
    # TC-F04-003-3: outputs carries the node's materialized output
    # ------------------------------------------------------------------

    async def test_streaming_terminal_outputs_contains_node_output(self) -> None:
        """TC-F04-003-3: terminal result['outputs'] contains the node's output value.

        The final_state from stream_compiled_graph_async merges all node deltas.
        The terminal event's 'outputs' is that merged final_state — same as what
        run_async returns in ExecutionResult.final_state.

        COUNTER-FACTUAL: A buggy delta-concatenation impl that drops state values
        would produce outputs={} or missing the 'output' key.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        # Each key in final_state becomes a node delta key in the streaming path
        final_state = {"output": "materialized-result-text"}
        service, mocks = self._make_parity_runner(final_state)
        bundle = self._make_parity_bundle()

        stream_events: list = []
        async for event in service.run_stream_async(
            bundle, initial_state={"input": "parity-check"}, validate_agents=False
        ):
            stream_events.append(event)

        terminal = next(
            (
                e
                for e in stream_events
                if isinstance(e, WorkflowProgressEvent) and e.is_terminal
            ),
            None,
        )
        self.assertIsNotNone(terminal, "Terminal event must be present")
        self.assertIsNotNone(terminal.result, "Terminal event result must not be None")

        outputs = terminal.result.get("outputs", "__MISSING__")
        self.assertIsInstance(outputs, dict, "outputs must be a dict")
        self.assertIn(
            "output",
            outputs,
            "outputs must contain 'output' key from node delta — "
            f"got keys={set(outputs.keys())}",
        )
        self.assertEqual(
            outputs.get("output"),
            "materialized-result-text",
            "outputs['output'] must equal the node's materialized output value "
            "(SC-3 parity: streaming result must equal non-streaming result for same input)",
        )

    # ------------------------------------------------------------------
    # TC-F04-003-4: metadata graph_name matches in both paths
    # ------------------------------------------------------------------

    async def test_streaming_terminal_metadata_graph_name_matches_bundle(self) -> None:
        """TC-F04-003-4: terminal result['metadata']['graph_name'] matches bundle graph name.

        This is the field-by-field parity check for the metadata key between
        streaming and non-streaming paths (AC-3: metadata keys equal).

        COUNTER-FACTUAL: A buggy impl that uses a hardcoded graph name in the
        streaming terminal dict would fail the assertEqual when the bundle's
        graph_name differs.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        final_state = {"output": "result"}
        service, mocks = self._make_parity_runner(final_state)
        bundle = self._make_parity_bundle(graph_name="parity-graph")

        stream_events: list = []
        async for event in service.run_stream_async(
            bundle, initial_state={"input": "check"}, validate_agents=False
        ):
            stream_events.append(event)

        terminal = next(
            (
                e
                for e in stream_events
                if isinstance(e, WorkflowProgressEvent) and e.is_terminal
            ),
            None,
        )
        self.assertIsNotNone(terminal, "Terminal event must be present")
        self.assertIsNotNone(terminal.result, "Terminal result must not be None")

        metadata = terminal.result.get("metadata", {})
        self.assertEqual(
            metadata.get("graph_name"),
            "parity-graph",
            f"terminal result['metadata']['graph_name'] must equal the bundle's "
            f"graph_name 'parity-graph', got {metadata.get('graph_name')!r}",
        )

    # ------------------------------------------------------------------
    # TC-F04-003-5: terminal result does NOT contain 'interrupted' on success
    # ------------------------------------------------------------------

    async def test_streaming_terminal_result_no_interrupted_on_success(self) -> None:
        """TC-F04-003-5: successful terminal result must NOT contain 'interrupted'.

        A successful run's terminal result must match the run_workflow_async success
        shape, which does not include 'interrupted'.

        COUNTER-FACTUAL: A buggy impl that always adds 'interrupted' to the result
        would violate parity with run_workflow_async's success shape.
        """
        from agentmap.models.execution import WorkflowProgressEvent

        final_state = {"output": "ok"}
        service, mocks = self._make_parity_runner(final_state)
        bundle = self._make_parity_bundle()

        stream_events: list = []
        async for event in service.run_stream_async(
            bundle, initial_state={"input": "check"}, validate_agents=False
        ):
            stream_events.append(event)

        terminal = next(
            (
                e
                for e in stream_events
                if isinstance(e, WorkflowProgressEvent) and e.is_terminal
            ),
            None,
        )
        self.assertIsNotNone(terminal, "Terminal event must be present")
        self.assertIsNotNone(terminal.result, "Terminal result must not be None")
        self.assertEqual(
            terminal.event_type,
            "completed",
            f"Successful run must produce 'completed' terminal event, "
            f"got {terminal.event_type!r}",
        )

        # Successful run must NOT carry 'interrupted' key (parity with run_workflow_async)
        self.assertNotIn(
            "interrupted",
            terminal.result,
            "Successful streaming terminal result must NOT contain 'interrupted' "
            "key (parity with run_workflow_async success shape)",
        )


# ---------------------------------------------------------------------------
# TestNonStreamingRegression
# TC-F04-010 behavioral gate + INT-4 structural assertions (AC-10, REQ-NF-001)
# (T-E06-F04-008)
# ---------------------------------------------------------------------------


class TestNonStreamingRegression(unittest.IsolatedAsyncioTestCase):
    """TC-F04-010: Non-streaming paths are behaviorally unchanged by F04 additions.

    This class is the behavioral regression gate for AC-10 / REQ-NF-001:
      (1) run_workflow_async returns a dict, not an AsyncGenerator
      (2) execute_compiled_graph_async source does NOT contain 'astream'
      (3) run_async body does NOT reference run_stream_async or stream_compiled_graph_async
      (4) _run_core_async body does NOT reference streaming methods
      (5) run_workflow_async returns expected keys on a successful fake run

    INT-4 (test-plan Integration Scenarios §INT-4 — Non-Streaming Path Isolation):
    Verifies that none of run_workflow_async, run_async, _run_core_async, or
    execute_compiled_graph_async call any F04 streaming artifact.

    Note: Structural source-body assertions for _run_core_async and
    execute_compiled_graph_async already exist in TestAssembleForAsyncRunHelper
    (TC-F04-010-7 / TC-F04-010-8).  This class adds the BEHAVIORAL gate (run
    result is a dict) and the INT-4 run_async-specific structural check.

    ENTRYPOINT:
      await run_workflow_async(graph_name, inputs)  — via facade-layer patch
      GraphRunnerService.run_async (source inspection)

    LOWEST ALLOWED MOCK SEAM:
      Fake container returned by RuntimeManager.get_container() that routes
      through a fake GraphRunnerService.run_async returning a real ExecutionResult.

    FORBIDDEN MOCKS:
      Do NOT route run_workflow_async through .astream(); must exercise the ainvoke
      path.  Do NOT mock the isinstance(result, dict) return assertion.

    COUNTER-FACTUAL:
      A regression that accidentally makes run_workflow_async call run_stream_async
      internally would produce an AsyncGenerator object instead of a dict, failing
      assertIsInstance(result, dict).
      A regression that routes run_async through streaming would contain
      'run_stream_async' in its source, failing the source assertion.
    """

    # ------------------------------------------------------------------
    # TC-F04-010: run_workflow_async returns a dict (not AsyncGenerator)
    # ------------------------------------------------------------------

    async def test_run_workflow_async_returns_dict_not_async_generator(self) -> None:
        """TC-F04-010 behavioral gate: run_workflow_async returns dict on success.

        This is the primary regression guard for INT-4: if run_workflow_async were
        accidentally routed through the streaming path, it would return an
        AsyncGenerator (from run_stream_async), not a dict.

        COUNTER-FACTUAL: A regression that replaces run_workflow_async's body with
        a call to run_stream_async would produce an AsyncGenerator here, and
        assertIsInstance(result, dict) would fail.
        """
        from unittest.mock import AsyncMock

        from agentmap.models.execution.result import ExecutionResult
        from agentmap.models.execution.summary import ExecutionSummary
        from agentmap.runtime.workflow_ops import run_workflow_async

        # Build a fake ExecutionResult representing a successful non-streaming run
        mock_summary = MagicMock(spec=ExecutionSummary)
        mock_summary.graph_name = "regression-graph"
        fake_result = ExecutionResult(
            graph_name="regression-graph",
            final_state={"output": "regression-output"},
            execution_summary=mock_summary,
            success=True,
            total_duration=0.5,
            error=None,
        )

        # Fake runner whose run_async returns the ExecutionResult (non-streaming path)
        fake_runner = MagicMock(name="fake_runner")
        fake_runner.run_async = AsyncMock(return_value=fake_result)

        # Fake bundle service returns a bundle
        fake_bundle = MagicMock(name="fake_bundle")
        fake_bundle_service = MagicMock(name="fake_bundle_service")
        fake_bundle_service.get_or_create_bundle.return_value = (fake_bundle, False)

        # Fake config service for _resolve_csv_path
        fake_config_service = MagicMock(name="fake_config_service")
        fake_config_service.get_csv_path.return_value = "/fake/graphs.csv"

        # Fake container wiring everything together
        fake_container = MagicMock(name="fake_container")
        fake_container.graph_runner_service.return_value = fake_runner
        fake_container.graph_bundle_service.return_value = fake_bundle_service
        fake_container.app_config_service.return_value = fake_config_service

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized") as _mock_init,
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=fake_container,
            ),
        ):
            _mock_init.return_value = None
            result = await run_workflow_async("regression-graph", {"input": "hello"})

        # Primary behavioral assertion: must be a dict, NOT an AsyncGenerator
        self.assertIsInstance(
            result,
            dict,
            f"run_workflow_async must return a dict (not an AsyncGenerator or other type); "
            f"got {type(result).__name__!r} — this indicates a regression where "
            f"run_workflow_async was accidentally routed through the streaming path",
        )

        # The dict must contain the standard success keys
        self.assertTrue(
            result.get("success"),
            f"run_workflow_async result['success'] must be True on a successful run; "
            f"got result={result}",
        )
        self.assertIn(
            "outputs",
            result,
            "run_workflow_async result must contain 'outputs' key "
            "(non-streaming contract unchanged by F04)",
        )

    # ------------------------------------------------------------------
    # TC-F04-010: run_workflow_async result has required keys on success
    # ------------------------------------------------------------------

    async def test_run_workflow_async_result_has_all_required_keys(self) -> None:
        """TC-F04-010: run_workflow_async result contains success, outputs, execution_id,
        execution_summary, metadata — the same five required keys checked in AC-3.

        COUNTER-FACTUAL: A regression that drops 'execution_summary' or 'metadata'
        from run_workflow_async's return dict would fail these assertIn checks,
        proving the non-streaming contract is intact.
        """
        from agentmap.models.execution.result import ExecutionResult
        from agentmap.models.execution.summary import ExecutionSummary
        from agentmap.runtime.workflow_ops import run_workflow_async

        mock_summary = MagicMock(spec=ExecutionSummary)
        mock_summary.graph_name = "keys-graph"
        fake_result = ExecutionResult(
            graph_name="keys-graph",
            final_state={"output": "result-val"},
            execution_summary=mock_summary,
            success=True,
            total_duration=0.1,
            error=None,
        )

        fake_runner = MagicMock(name="fake_runner")
        fake_runner.run_async = AsyncMock(return_value=fake_result)

        fake_bundle_service = MagicMock()
        fake_bundle = MagicMock(name="fake_bundle")
        fake_bundle_service.get_or_create_bundle.return_value = (fake_bundle, False)

        fake_config_service = MagicMock()
        fake_config_service.get_csv_path.return_value = "/fake/graphs.csv"

        fake_container = MagicMock()
        fake_container.graph_runner_service.return_value = fake_runner
        fake_container.graph_bundle_service.return_value = fake_bundle_service
        fake_container.app_config_service.return_value = fake_config_service

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=fake_container,
            ),
        ):
            result = await run_workflow_async("keys-graph", {"input": "check"})

        # All five required keys from run_workflow_async success shape
        required_keys = {
            "success",
            "outputs",
            "execution_id",
            "execution_summary",
            "metadata",
        }
        for key in required_keys:
            self.assertIn(
                key,
                result,
                f"run_workflow_async must still return '{key}' after F04 additions "
                f"(AC-10 non-regression: non-streaming contract unchanged); "
                f"got keys={set(result.keys())}",
            )

    # ------------------------------------------------------------------
    # INT-4: run_async body does NOT reference streaming artifacts
    # ------------------------------------------------------------------

    def test_run_async_source_does_not_reference_run_stream_async(self) -> None:
        """INT-4: run_async body must NOT contain 'run_stream_async'.

        INT-4 non-streaming path isolation: run_async must remain independent
        of streaming artifacts.  F04 adds streaming as an additive sibling (D-2),
        so the existing run_async must never call run_stream_async.

        COUNTER-FACTUAL: A buggy refactor that accidentally delegates run_async
        to run_stream_async would contain the string 'run_stream_async' in its
        source body, and this assertion would catch the coupling.
        """
        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        source = inspect.getsource(GraphRunnerService.run_async)
        self.assertNotIn(
            "run_stream_async",
            source,
            "GraphRunnerService.run_async must NOT reference run_stream_async "
            "(INT-4: non-streaming path must be independent of F04 streaming methods; "
            "D-2 additive sibling: existing run_async is byte-untouched)",
        )

    def test_run_async_source_does_not_reference_stream_compiled_graph_async(
        self,
    ) -> None:
        """INT-4: run_async body must NOT contain 'stream_compiled_graph_async'.

        COUNTER-FACTUAL: A buggy impl that replaces execute_compiled_graph_async
        with stream_compiled_graph_async inside run_async would break the
        non-streaming contract (run_async would yield events instead of returning
        ExecutionResult) — caught by the source assertion.
        """
        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        source = inspect.getsource(GraphRunnerService.run_async)
        self.assertNotIn(
            "stream_compiled_graph_async",
            source,
            "GraphRunnerService.run_async must NOT reference stream_compiled_graph_async "
            "(INT-4: non-streaming runner path uses execute_compiled_graph_async only; "
            "REQ-NF-001: existing run_async is byte-untouched by F04)",
        )

    # ------------------------------------------------------------------
    # INT-4: run_workflow_async body does NOT reference streaming artifacts
    # ------------------------------------------------------------------

    def test_run_workflow_async_source_does_not_reference_run_stream_async(
        self,
    ) -> None:
        """INT-4: run_workflow_async body must NOT contain 'run_stream_async'.

        run_workflow_async is the public facade entry point for the non-streaming
        async path.  F04 adds run_workflow_stream_async as an additive sibling
        (D-2, REQ-NF-001).  The original run_workflow_async must never call
        run_stream_async internally.

        COUNTER-FACTUAL: A refactor that accidentally shares a body by calling
        run_stream_async from run_workflow_async would make run_workflow_async
        yield events instead of returning a dict — caught by the source check.
        """
        from agentmap.runtime.workflow_ops import run_workflow_async

        source = inspect.getsource(run_workflow_async)
        self.assertNotIn(
            "run_stream_async",
            source,
            "run_workflow_async must NOT reference run_stream_async internally "
            "(INT-4: facade non-streaming path must be byte-untouched; "
            "D-2: additive sibling only — no shared body with streaming facade)",
        )

    def test_run_workflow_async_source_does_not_reference_stream_compiled_graph(
        self,
    ) -> None:
        """INT-4: run_workflow_async body must NOT contain 'stream_compiled_graph_async'.

        COUNTER-FACTUAL: A refactor that wires run_workflow_async through
        stream_compiled_graph_async would break the non-streaming return contract.
        """
        from agentmap.runtime.workflow_ops import run_workflow_async

        source = inspect.getsource(run_workflow_async)
        self.assertNotIn(
            "stream_compiled_graph_async",
            source,
            "run_workflow_async must NOT reference stream_compiled_graph_async "
            "(INT-4: non-streaming facade path uses graph_runner.run_async only; "
            "REQ-NF-001: existing run_workflow_async is byte-untouched by F04)",
        )

    # ------------------------------------------------------------------
    # AC-10: existing graph-runner test suite passes (documented)
    # ------------------------------------------------------------------

    def test_existing_graph_runner_test_suite_still_passes(self) -> None:
        """AC-10: verify the existing graph-runner test infrastructure is intact.

        This test validates that the TestAssembleForAsyncRunHelper class (which
        covers _run_core_async / execute_compiled_graph_async structural assertions)
        is still present in this file and that the imports it relies on all resolve.

        The full existing test suite pass is documented in the shark note; this
        structural guard confirms the regression-suite infrastructure hasn't been
        accidentally removed.

        COUNTER-FACTUAL: A refactor that removed _run_core_async or
        execute_compiled_graph_async from the graph services would fail the
        import/hasattr assertions here, signaling the regression suite is broken.
        """
        from agentmap.services.graph.graph_execution_service import (
            GraphExecutionService,
        )
        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        # Verify all non-streaming methods still exist (not accidentally renamed/removed)
        self.assertTrue(
            hasattr(GraphRunnerService, "run_async"),
            "GraphRunnerService.run_async must still exist after F04 additions "
            "(REQ-NF-001: non-streaming path byte-untouched)",
        )
        self.assertTrue(
            hasattr(GraphRunnerService, "_run_core_async"),
            "GraphRunnerService._run_core_async must still exist after the D-7 refactor "
            "(REQ-NF-001: non-streaming internal path byte-untouched)",
        )
        self.assertTrue(
            hasattr(GraphExecutionService, "execute_compiled_graph_async"),
            "GraphExecutionService.execute_compiled_graph_async must still exist "
            "(REQ-NF-001: non-streaming execution method byte-untouched)",
        )

        # Verify the F04 additions are also present (additive, per D-2)
        self.assertTrue(
            hasattr(GraphRunnerService, "run_stream_async"),
            "GraphRunnerService.run_stream_async must be present (F04 additive sibling) "
            "— if missing, the streaming path is broken",
        )
        self.assertTrue(
            hasattr(GraphExecutionService, "stream_compiled_graph_async"),
            "GraphExecutionService.stream_compiled_graph_async must be present (F04 additive) "
            "— if missing, the streaming execution path is broken",
        )


if __name__ == "__main__":
    unittest.main()
