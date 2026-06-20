"""
Unit tests for E06-F04: Graph Progress Streaming via Runtime Facade.

This file currently contains only the D-9 smoke check class:
  - TestAstreamShapeSmoke — TC-F04-D9

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

import unittest
from importlib.metadata import version
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

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
