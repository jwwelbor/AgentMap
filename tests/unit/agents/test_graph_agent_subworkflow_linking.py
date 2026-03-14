"""
Tests for GraphAgent sub-workflow span linking (T-E02-F06-003).

Verifies that GraphAgent.process() correctly sources parent_graph_name from
agent context (self.context["graph_name"]) and passes it to
GraphRunnerService.run(), enabling OTEL context propagation for sub-workflow
span hierarchy.

Test cases TC-640 through TC-643.
"""

import logging
from unittest.mock import MagicMock

import pytest

from agentmap.agents.builtins.graph_agent import GraphAgent
from agentmap.models.execution.result import ExecutionResult


def _make_graph_agent(context=None, name="sub_workflow_node"):
    """Create a GraphAgent with sensible defaults and mock services."""
    agent = GraphAgent(
        name=name,
        prompt="child_graph",
        context=context,
        logger=logging.getLogger("test"),
    )
    # Mock graph_runner_service
    mock_runner = MagicMock()
    mock_runner.run.return_value = ExecutionResult(
        graph_name="child_graph",
        final_state={"result": "ok"},
        execution_summary=None,
        success=True,
        total_duration=0.1,
    )
    agent._graph_runner_service = mock_runner

    # Mock graph_bundle_service
    agent._graph_bundle_service = MagicMock()

    return agent, mock_runner


def _make_bundle(graph_name="child_graph"):
    """Create a mock bundle."""
    bundle = MagicMock()
    bundle.graph_name = graph_name
    bundle.nodes = [MagicMock()]
    return bundle


class TestTC640_ParentGraphNameFromContext:
    """TC-640: GraphAgent sources parent_graph_name from context['graph_name']."""

    def test_parent_graph_name_passed_from_context(self):
        """When context has graph_name, it is passed as parent_graph_name to run()."""
        agent, mock_runner = _make_graph_agent(
            context={
                "graph_name": "parent_workflow",
                "input_fields": [],
                "output_field": "result",
            }
        )
        bundle = _make_bundle()
        inputs = {"subgraph_bundles": {"sub_workflow_node": bundle}}

        agent.process(inputs)

        mock_runner.run.assert_called_once()
        call_kwargs = mock_runner.run.call_args
        assert (
            call_kwargs.kwargs.get("parent_graph_name") == "parent_workflow"
            or call_kwargs[1].get("parent_graph_name") == "parent_workflow"
        ), f"Expected parent_graph_name='parent_workflow', got call: {call_kwargs}"

    def test_parent_graph_name_is_none_when_context_missing_graph_name(self):
        """When context has no graph_name key, parent_graph_name is None."""
        agent, mock_runner = _make_graph_agent(
            context={
                "input_fields": [],
                "output_field": "result",
            }
        )
        bundle = _make_bundle()
        inputs = {"subgraph_bundles": {"sub_workflow_node": bundle}}

        agent.process(inputs)

        mock_runner.run.assert_called_once()
        call_kwargs = mock_runner.run.call_args
        # parent_graph_name should be None when graph_name not in context
        pgn = call_kwargs.kwargs.get("parent_graph_name", "NOT_FOUND")
        if pgn == "NOT_FOUND":
            pgn = call_kwargs[1].get("parent_graph_name", "NOT_FOUND")
        assert pgn is None, f"Expected parent_graph_name=None, got {pgn}"

    def test_parent_graph_name_is_none_when_context_is_none(self):
        """When context is None (defaults to empty dict), parent_graph_name is None."""
        agent, mock_runner = _make_graph_agent(context=None)
        bundle = _make_bundle()
        inputs = {"subgraph_bundles": {"sub_workflow_node": bundle}}

        agent.process(inputs)

        mock_runner.run.assert_called_once()
        call_kwargs = mock_runner.run.call_args
        pgn = call_kwargs.kwargs.get("parent_graph_name", "NOT_FOUND")
        if pgn == "NOT_FOUND":
            pgn = call_kwargs[1].get("parent_graph_name", "NOT_FOUND")
        assert pgn is None, f"Expected parent_graph_name=None, got {pgn}"


class TestTC641_ParentGraphNamePropagation:
    """TC-641: parent_graph_name value is correctly propagated to run()."""

    def test_various_graph_names_propagated(self):
        """Different graph_name values in context are all correctly passed."""
        graph_names = [
            "simple_workflow",
            "complex-workflow-123",
            "Workflow With Spaces",
            "a",  # single char
        ]
        for graph_name in graph_names:
            agent, mock_runner = _make_graph_agent(
                context={
                    "graph_name": graph_name,
                    "input_fields": [],
                    "output_field": "result",
                }
            )
            bundle = _make_bundle()
            inputs = {"subgraph_bundles": {"sub_workflow_node": bundle}}

            agent.process(inputs)

            call_kwargs = mock_runner.run.call_args
            pgn = call_kwargs.kwargs.get("parent_graph_name", "NOT_FOUND")
            if pgn == "NOT_FOUND":
                pgn = call_kwargs[1].get("parent_graph_name", "NOT_FOUND")
            assert (
                pgn == graph_name
            ), f"Expected parent_graph_name='{graph_name}', got '{pgn}'"


class TestTC642_SubWorkflowSpanAttributes:
    """TC-642: Verify is_subgraph=True is also passed alongside parent_graph_name."""

    def test_is_subgraph_true_passed(self):
        """GraphAgent always passes is_subgraph=True to run()."""
        agent, mock_runner = _make_graph_agent(
            context={
                "graph_name": "parent_workflow",
                "input_fields": [],
                "output_field": "result",
            }
        )
        bundle = _make_bundle()
        inputs = {"subgraph_bundles": {"sub_workflow_node": bundle}}

        agent.process(inputs)

        call_kwargs = mock_runner.run.call_args
        is_subgraph = call_kwargs.kwargs.get("is_subgraph", "NOT_FOUND")
        if is_subgraph == "NOT_FOUND":
            is_subgraph = call_kwargs[1].get("is_subgraph", "NOT_FOUND")
        assert is_subgraph is True, f"Expected is_subgraph=True, got {is_subgraph}"

    def test_bundle_passed_correctly(self):
        """The correct bundle is passed to run()."""
        agent, mock_runner = _make_graph_agent(
            context={
                "graph_name": "parent_workflow",
                "input_fields": [],
                "output_field": "result",
            }
        )
        bundle = _make_bundle("child_graph")
        inputs = {"subgraph_bundles": {"sub_workflow_node": bundle}}

        agent.process(inputs)

        call_kwargs = mock_runner.run.call_args
        passed_bundle = call_kwargs.kwargs.get("bundle", "NOT_FOUND")
        if passed_bundle == "NOT_FOUND":
            passed_bundle = call_kwargs[1].get(
                "bundle", call_kwargs[0][0] if call_kwargs[0] else "NOT_FOUND"
            )
        assert passed_bundle is bundle


class TestTC643_EmptyContextEdgeCases:
    """TC-643: Edge cases for context-based parent_graph_name sourcing."""

    def test_empty_dict_context(self):
        """Empty dict context yields None parent_graph_name."""
        agent, mock_runner = _make_graph_agent(context={})
        bundle = _make_bundle()
        inputs = {"subgraph_bundles": {"sub_workflow_node": bundle}}

        agent.process(inputs)

        call_kwargs = mock_runner.run.call_args
        pgn = call_kwargs.kwargs.get("parent_graph_name", "NOT_FOUND")
        if pgn == "NOT_FOUND":
            pgn = call_kwargs[1].get("parent_graph_name", "NOT_FOUND")
        assert pgn is None

    def test_graph_name_empty_string(self):
        """Empty string graph_name is passed as-is (not converted to None)."""
        agent, mock_runner = _make_graph_agent(
            context={
                "graph_name": "",
                "input_fields": [],
                "output_field": "result",
            }
        )
        bundle = _make_bundle()
        inputs = {"subgraph_bundles": {"sub_workflow_node": bundle}}

        agent.process(inputs)

        call_kwargs = mock_runner.run.call_args
        pgn = call_kwargs.kwargs.get("parent_graph_name", "NOT_FOUND")
        if pgn == "NOT_FOUND":
            pgn = call_kwargs[1].get("parent_graph_name", "NOT_FOUND")
        # Empty string is still passed -- the downstream service decides how to handle it
        assert pgn == ""

    def test_context_with_other_keys_but_no_graph_name(self):
        """Context with unrelated keys but no graph_name yields None."""
        agent, mock_runner = _make_graph_agent(
            context={
                "input_fields": ["x", "y"],
                "output_field": "z",
                "description": "some agent",
            }
        )
        bundle = _make_bundle()
        inputs = {"subgraph_bundles": {"sub_workflow_node": bundle}}

        agent.process(inputs)

        call_kwargs = mock_runner.run.call_args
        pgn = call_kwargs.kwargs.get("parent_graph_name", "NOT_FOUND")
        if pgn == "NOT_FOUND":
            pgn = call_kwargs[1].get("parent_graph_name", "NOT_FOUND")
        assert pgn is None

    def test_no_bundle_raises_runtime_error(self):
        """When no bundle found for node, RuntimeError is raised."""
        agent, mock_runner = _make_graph_agent(
            context={"graph_name": "parent", "input_fields": [], "output_field": "r"}
        )
        inputs = {"subgraph_bundles": {}}  # no bundle for this node

        with pytest.raises(RuntimeError, match="No pre-resolved subgraph bundle"):
            agent.process(inputs)
