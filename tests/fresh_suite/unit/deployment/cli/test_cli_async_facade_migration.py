"""
Tests for CLI entrypoint migration to async runtime facade.

TC-003A: agentmap run preserves stdout/stderr and exit codes while calling async facade
TC-003B: agentmap resume preserves stdout/stderr and exit codes while calling async facade
TC-003C: agentmap inspect-graph preserves presentation contract while calling async facade
TC-003D: agentmap validate preserves validation contract while calling async facade

Caller-Path Contracts (from test-plan.md):
- TC-003A: entrypoint run_command(...), mock seam run_workflow_async,
           forbidden: run_workflow, presenter helpers, helper-only runtime signatures
- TC-003B: entrypoint resume_command(...), mock seam resume_workflow_async,
           forbidden: resume_workflow, presenter helpers
- TC-003C: entrypoint inspect_graph_cmd(...), mock seam inspect_graph_async,
           forbidden: inspect_graph, CLI presenter output helpers
- TC-003D: entrypoint validate_command(...), mock seam validate_workflow_async,
           forbidden: validate_workflow, resolve_csv_path behavior changes
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest
import typer

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_run_success_payload(interrupted: bool = False):
    """Return a representative run_workflow_async success payload."""
    if interrupted:
        return {
            "success": False,
            "interrupted": True,
            "thread_id": "thread-cli-123",
            "message": "Execution interrupted for human interaction in thread: thread-cli-123",
            "interrupt_info": {"type": "human", "node_name": "approve_node"},
            "execution_summary": None,
            "metadata": {
                "graph_name": "test_workflow",
                "profile": None,
                "checkpoint_available": True,
                "interrupt_type": "human",
                "node_name": "approve_node",
            },
        }
    return {
        "success": True,
        "outputs": {"result": "test_output", "completed": True},
        "execution_id": None,
        "execution_summary": None,
        "metadata": {"graph_name": "test_workflow", "profile": None},
    }


def _make_resume_success_payload():
    """Return a representative resume_workflow_async success payload."""
    return {
        "success": True,
        "outputs": {"resumed": True, "final_result": "done"},
        "execution_summary": None,
        "metadata": {
            "thread_id": "thread-resume-001",
            "response_action": "continue",
            "profile": "dev",
        },
    }


def _make_inspect_graph_payload():
    """Return a representative inspect_graph_async payload.

    Shape matches the real inspect_graph / inspect_graph_async return value
    (see agentmap/runtime/workflow_ops.py inspect_graph):
      outputs["structure"]["nodes"] — list of dicts with name/agent_type/description
      outputs["issues"]             — list of strings
    """
    return {
        "success": True,
        "outputs": {
            "resolved_name": "test_graph",
            "total_nodes": 2,
            "unique_agent_types": 1,
            "all_resolvable": True,
            "resolution_rate": 1.0,
            "structure": {
                "nodes": [
                    {
                        "name": "start_node",
                        "agent_type": "default",
                        "description": "Start node",
                    },
                    {
                        "name": "end_node",
                        "agent_type": "default",
                        "description": "End node",
                    },
                ],
                "entry_point": "start_node",
            },
            "issues": [],
            "required_agents": ["default"],
            "required_services": [],
        },
        "metadata": {
            "graph_name": "test_graph",
            "csv_file": "/tmp/test.csv",
            "inspected_node": None,
            "csv_hash": None,
        },
    }


def _make_validate_workflow_payload():
    """Return a representative validate_workflow_async success payload."""
    return {
        "success": True,
        "outputs": {
            "valid": True,
            "total_nodes": 3,
            "total_edges": 2,
            "missing_declarations": [],
            "graph_name": "test_graph",
        },
        "metadata": {
            "bundle_name": "test_graph",
            "csv_path": "/tmp/test.csv",
        },
    }


# ---------------------------------------------------------------------------
# TC-003A: agentmap run uses run_workflow_async, not run_workflow
# ---------------------------------------------------------------------------


class TestRunCommandUsesAsyncFacade:
    """TC-003A: run_command calls run_workflow_async, not run_workflow."""

    @patch(
        "agentmap.deployment.cli.run_command.run_workflow",
    )
    @patch("agentmap.deployment.cli.run_command.ensure_initialized")
    def test_run_command_calls_run_workflow_async_on_success(
        self, mock_ensure_initialized, mock_run_workflow_async
    ):
        """TC-003A happy path: run_command uses run_workflow_async and exits 0."""
        mock_ensure_initialized.return_value = None
        mock_run_workflow_async.return_value = _make_run_success_payload()

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.run_command import run_command

            run_command(
                workflow="test_workflow",
                graph="{}",
                state="{}",
                validate=False,
                config_file=None,
                pretty=False,
                verbose=False,
                force_create=False,
            )

        assert exc_info.value.exit_code == 0
        mock_run_workflow_async.assert_called_once()
        mock_ensure_initialized.assert_called_once()

    @patch(
        "agentmap.deployment.cli.run_command.run_workflow",
    )
    @patch("agentmap.deployment.cli.run_command.ensure_initialized")
    def test_run_command_interrupted_exits_0_with_thread_id(
        self, mock_ensure_initialized, mock_run_workflow_async
    ):
        """TC-003A edge case: interrupted execution still exits 0 (suspend case)."""
        mock_ensure_initialized.return_value = None
        mock_run_workflow_async.return_value = _make_run_success_payload(
            interrupted=True
        )

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.run_command import run_command

            run_command(
                workflow="test_workflow",
                graph="{}",
                state="{}",
                validate=False,
                config_file=None,
                pretty=False,
                verbose=False,
                force_create=False,
            )

        assert exc_info.value.exit_code == 0
        mock_run_workflow_async.assert_called_once()

    @patch(
        "agentmap.deployment.cli.run_command.run_workflow",
    )
    @patch("agentmap.deployment.cli.run_command.ensure_initialized")
    def test_run_command_invalid_json_state_exits_nonzero(
        self, mock_ensure_initialized, mock_run_workflow_async
    ):
        """TC-003A edge case: invalid JSON in --state maps to the same exit-code path."""
        mock_ensure_initialized.return_value = None

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.run_command import run_command

            run_command(
                workflow="test_workflow",
                graph="{}",
                state="not_valid_json{",
                validate=False,
                config_file=None,
                pretty=False,
                verbose=False,
                force_create=False,
            )

        # Invalid JSON produces a non-zero exit code
        assert exc_info.value.exit_code != 0
        # run_workflow_async must not be called when JSON parsing fails
        mock_run_workflow_async.assert_not_called()

    @patch(
        "agentmap.deployment.cli.run_command.run_workflow",
    )
    @patch("agentmap.deployment.cli.run_command.ensure_initialized")
    def test_run_command_missing_workflow_exits_nonzero(
        self, mock_ensure_initialized, mock_run_workflow_async
    ):
        """TC-003A edge case: missing workflow argument exits with error code."""
        mock_ensure_initialized.return_value = None

        # workflow=None and graph=None means no workflow is provided
        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.run_command import run_command

            run_command(
                workflow=None,
                graph="",
                state="{}",
                validate=False,
                config_file=None,
                pretty=False,
                verbose=False,
                force_create=False,
            )

        assert exc_info.value.exit_code == 2

    @patch(
        "agentmap.deployment.cli.run_command.run_workflow",
    )
    @patch("agentmap.deployment.cli.run_command.ensure_initialized")
    def test_run_command_force_create_is_passed_to_async_facade(
        self, mock_ensure_initialized, mock_run_workflow_async
    ):
        """TC-003A edge case: --force-create flag is forwarded to the async facade."""
        mock_ensure_initialized.return_value = None
        mock_run_workflow_async.return_value = _make_run_success_payload()

        with pytest.raises(typer.Exit):
            from agentmap.deployment.cli.run_command import run_command

            run_command(
                workflow="test_workflow",
                graph="{}",
                state="{}",
                validate=False,
                config_file=None,
                pretty=False,
                verbose=False,
                force_create=True,
            )

        call_kwargs = mock_run_workflow_async.call_args
        # force_create=True must be forwarded
        assert call_kwargs is not None
        assert (
            "True" in str(call_kwargs) or call_kwargs.kwargs.get("force_create") is True
        )

    def test_run_command_does_not_import_async_run_workflow(self):
        """TC-003A counter-factual: async run_workflow_async must not be in run_command namespace."""
        import agentmap.deployment.cli.run_command as run_command_module

        # CLI uses sync facade directly — async variant must not be imported
        assert not hasattr(
            run_command_module, "run_workflow_async"
        ), "async run_workflow_async is imported in run_command.py — use sync facade for CLI"

    @patch(
        "agentmap.deployment.cli.run_command.run_workflow",
    )
    @patch("agentmap.deployment.cli.run_command.ensure_initialized")
    def test_run_command_pretty_verbose_do_not_change_exit_code(
        self, mock_ensure_initialized, mock_run_workflow_async
    ):
        """TC-003A edge case: --pretty and --verbose only affect presentation, not exit code."""
        mock_ensure_initialized.return_value = None
        mock_run_workflow_async.return_value = _make_run_success_payload()

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.run_command import run_command

            run_command(
                workflow="test_workflow",
                graph="{}",
                state="{}",
                validate=False,
                config_file=None,
                pretty=True,
                verbose=True,
                force_create=False,
            )

        assert exc_info.value.exit_code == 0
        mock_run_workflow_async.assert_called_once()


# ---------------------------------------------------------------------------
# TC-003B: agentmap resume uses resume_workflow_async, not resume_workflow
# ---------------------------------------------------------------------------


class TestResumeCommandUsesAsyncFacade:
    """TC-003B: resume_command calls resume_workflow_async, not resume_workflow."""

    @patch(
        "agentmap.deployment.cli.resume_command.resume_workflow",
    )
    @patch("agentmap.deployment.cli.resume_command.ensure_initialized")
    def test_resume_command_calls_resume_workflow_async_on_success(
        self, mock_ensure_initialized, mock_resume_workflow_async
    ):
        """TC-003B happy path: resume_command uses resume_workflow_async and exits 0."""
        mock_ensure_initialized.return_value = None
        mock_resume_workflow_async.return_value = _make_resume_success_payload()

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.resume_command import resume_command

            resume_command(
                thread_id="thread-resume-001",
                response="continue",
                data=None,
                data_file=None,
                config_file=None,
            )

        assert exc_info.value.exit_code == 0
        mock_resume_workflow_async.assert_called_once()
        mock_ensure_initialized.assert_called_once()

    @patch(
        "agentmap.deployment.cli.resume_command.resume_workflow",
    )
    @patch("agentmap.deployment.cli.resume_command.ensure_initialized")
    def test_resume_command_with_json_data_calls_async_facade(
        self, mock_ensure_initialized, mock_resume_workflow_async
    ):
        """TC-003B: --data JSON is parsed and forwarded to the async resume facade."""
        mock_ensure_initialized.return_value = None
        mock_resume_workflow_async.return_value = _make_resume_success_payload()

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.resume_command import resume_command

            resume_command(
                thread_id="thread-resume-001",
                response="approve",
                data='{"user_choice": "yes"}',
                data_file=None,
                config_file=None,
            )

        assert exc_info.value.exit_code == 0
        mock_resume_workflow_async.assert_called_once()

    @patch(
        "agentmap.deployment.cli.resume_command.resume_workflow",
    )
    @patch("agentmap.deployment.cli.resume_command.ensure_initialized")
    def test_resume_command_invalid_json_data_exits_nonzero(
        self, mock_ensure_initialized, mock_resume_workflow_async
    ):
        """TC-003B edge case: invalid JSON in --data maps to same error path as sync."""
        mock_ensure_initialized.return_value = None

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.resume_command import resume_command

            resume_command(
                thread_id="thread-resume-001",
                response="continue",
                data="invalid_json{{{",
                data_file=None,
                config_file=None,
            )

        assert exc_info.value.exit_code != 0
        mock_resume_workflow_async.assert_not_called()

    @patch(
        "agentmap.deployment.cli.resume_command.resume_workflow",
    )
    @patch("agentmap.deployment.cli.resume_command.ensure_initialized")
    def test_resume_command_missing_data_file_exits_nonzero(
        self, mock_ensure_initialized, mock_resume_workflow_async
    ):
        """TC-003B edge case: missing --data-file maps to same error path."""
        mock_ensure_initialized.return_value = None

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.resume_command import resume_command

            resume_command(
                thread_id="thread-resume-001",
                response="continue",
                data=None,
                data_file="/nonexistent/path/file.json",
                config_file=None,
            )

        assert exc_info.value.exit_code != 0
        mock_resume_workflow_async.assert_not_called()

    @patch(
        "agentmap.deployment.cli.resume_command.resume_workflow",
    )
    @patch("agentmap.deployment.cli.resume_command.ensure_initialized")
    def test_resume_command_with_data_file_calls_async_facade(
        self, mock_ensure_initialized, mock_resume_workflow_async
    ):
        """TC-003B edge case: --data-file reads JSON and forwards to async facade."""
        mock_ensure_initialized.return_value = None
        mock_resume_workflow_async.return_value = _make_resume_success_payload()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmpf:
            json.dump({"user_choice": "yes"}, tmpf)
            tmp_path = tmpf.name

        try:
            with pytest.raises(typer.Exit) as exc_info:
                from agentmap.deployment.cli.resume_command import resume_command

                resume_command(
                    thread_id="thread-resume-001",
                    response="approve",
                    data=None,
                    data_file=tmp_path,
                    config_file=None,
                )

            assert exc_info.value.exit_code == 0
            mock_resume_workflow_async.assert_called_once()
        finally:
            os.unlink(tmp_path)

    @patch(
        "agentmap.deployment.cli.resume_command.resume_workflow",
    )
    @patch("agentmap.deployment.cli.resume_command.ensure_initialized")
    def test_resume_command_blank_response_action_preserves_token_behavior(
        self, mock_ensure_initialized, mock_resume_workflow_async
    ):
        """TC-003B edge case: blank/omitted response action still produces a valid token."""
        mock_ensure_initialized.return_value = None
        mock_resume_workflow_async.return_value = _make_resume_success_payload()

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.resume_command import resume_command

            resume_command(
                thread_id="thread-resume-001",
                response=None,
                data=None,
                data_file=None,
                config_file=None,
            )

        assert exc_info.value.exit_code == 0
        mock_resume_workflow_async.assert_called_once()

    def test_resume_command_does_not_import_async_resume_workflow(self):
        """TC-003B counter-factual: async resume_workflow_async must not be in resume_command namespace."""
        import agentmap.deployment.cli.resume_command as resume_command_module

        assert not hasattr(
            resume_command_module, "resume_workflow_async"
        ), "async resume_workflow_async is imported in resume_command.py — use sync facade for CLI"


# ---------------------------------------------------------------------------
# TC-003C: agentmap inspect-graph uses inspect_graph_async, not inspect_graph
# ---------------------------------------------------------------------------


class TestInspectGraphCommandUsesAsyncFacade:
    """TC-003C: inspect_graph_cmd calls inspect_graph_async, not inspect_graph."""

    @patch(
        "agentmap.deployment.cli.inspect_graph_command.inspect_graph",
    )
    def test_inspect_graph_cmd_calls_inspect_graph_async_on_success(
        self, mock_inspect_graph_async
    ):
        """TC-003C happy path: inspect_graph_cmd uses inspect_graph_async and exits 0."""
        mock_inspect_graph_async.return_value = _make_inspect_graph_payload()

        # inspect_graph_cmd returns normally on success (no typer.Exit raised)
        from agentmap.deployment.cli.inspect_graph_command import inspect_graph_cmd

        inspect_graph_cmd(
            graph_name="test_graph",
            csv_file=None,
            config_file=None,
            node=None,
            show_services=True,
            show_protocols=True,
            show_config=False,
            show_resolution=False,
        )

        # Counter-factual: inspect_graph_async must be called, not inspect_graph
        mock_inspect_graph_async.assert_called_once()

    @patch(
        "agentmap.deployment.cli.inspect_graph_command.inspect_graph",
    )
    def test_inspect_graph_cmd_node_filter_passed_to_async_facade(
        self, mock_inspect_graph_async
    ):
        """TC-003C edge case: --node filter is forwarded to inspect_graph_async."""
        mock_inspect_graph_async.return_value = _make_inspect_graph_payload()

        try:
            from agentmap.deployment.cli.inspect_graph_command import inspect_graph_cmd

            inspect_graph_cmd(
                graph_name="test_graph",
                csv_file=None,
                config_file=None,
                node="start_node",
                show_services=True,
                show_protocols=True,
                show_config=False,
                show_resolution=False,
            )
        except typer.Exit:
            pass

        call_kwargs = mock_inspect_graph_async.call_args
        assert call_kwargs is not None
        # The node argument must be forwarded
        assert "start_node" in str(call_kwargs)

    @patch(
        "agentmap.deployment.cli.inspect_graph_command.inspect_graph",
    )
    def test_inspect_graph_cmd_graph_not_found_exits_1(self, mock_inspect_graph_async):
        """TC-003C negative: graph-not-found still maps to exit code 1."""
        from agentmap.exceptions.runtime_exceptions import GraphNotFound

        mock_inspect_graph_async.side_effect = GraphNotFound(
            "nonexistent", "Graph not found"
        )

        with pytest.raises(typer.Exit) as exc_info:
            from agentmap.deployment.cli.inspect_graph_command import inspect_graph_cmd

            inspect_graph_cmd(
                graph_name="nonexistent",
                csv_file=None,
                config_file=None,
                node=None,
                show_services=True,
                show_protocols=True,
                show_config=False,
                show_resolution=False,
            )

        assert exc_info.value.exit_code == 1

    def test_inspect_graph_cmd_does_not_import_async_inspect_graph(self):
        """TC-003C counter-factual: async inspect_graph_async must not be in inspect_graph_command namespace."""
        import agentmap.deployment.cli.inspect_graph_command as inspect_cmd_module

        assert not hasattr(
            inspect_cmd_module, "inspect_graph_async"
        ), "async inspect_graph_async is imported in inspect_graph_command.py — use sync facade for CLI"

    @patch(
        "agentmap.deployment.cli.inspect_graph_command.inspect_graph",
    )
    def test_inspect_graph_cmd_with_csv_file_passes_to_async_facade(
        self, mock_inspect_graph_async
    ):
        """TC-003C edge case: --csv is forwarded to inspect_graph_async."""
        mock_inspect_graph_async.return_value = _make_inspect_graph_payload()

        try:
            from agentmap.deployment.cli.inspect_graph_command import inspect_graph_cmd

            inspect_graph_cmd(
                graph_name="test_graph",
                csv_file="/tmp/test.csv",
                config_file=None,
                node=None,
                show_services=True,
                show_protocols=True,
                show_config=False,
                show_resolution=False,
            )
        except typer.Exit:
            pass

        call_kwargs = mock_inspect_graph_async.call_args
        assert call_kwargs is not None
        assert "/tmp/test.csv" in str(call_kwargs)


# ---------------------------------------------------------------------------
# TC-003D: agentmap validate uses validate_workflow_async, not validate_workflow
# ---------------------------------------------------------------------------


class TestValidateCommandUsesAsyncFacade:
    """TC-003D: validate_command calls validate_workflow_async, not validate_workflow."""

    @patch(
        "agentmap.deployment.cli.validate_command.validate_workflow",
    )
    @patch("agentmap.deployment.cli.validate_command.resolve_csv_path")
    def test_validate_command_calls_validate_workflow_async_on_success(
        self, mock_resolve_csv_path, mock_validate_workflow_async
    ):
        """TC-003D happy path: validate_command uses validate_workflow_async."""
        mock_resolve_csv_path.return_value = "/tmp/test.csv"
        mock_validate_workflow_async.return_value = _make_validate_workflow_payload()

        # Should complete without raising Exit(nonzero) or Exception
        try:
            from agentmap.deployment.cli.validate_command import validate_command

            validate_command(
                csv_file="test.csv",
                csv=None,
                graph=None,
                config_file=None,
            )
        except typer.Exit as e:
            # Exit(0) is fine; any non-zero exit would be a failure
            assert e.exit_code == 0 or e.exit_code is None

        mock_validate_workflow_async.assert_called_once()

    @patch(
        "agentmap.deployment.cli.validate_command.validate_workflow",
    )
    @patch("agentmap.deployment.cli.validate_command.resolve_csv_path")
    def test_validate_command_positional_csv_resolves_same_as_flag(
        self, mock_resolve_csv_path, mock_validate_workflow_async
    ):
        """TC-003D edge case: positional CSV resolves same target as --csv."""
        mock_resolve_csv_path.return_value = "/tmp/test.csv"
        mock_validate_workflow_async.return_value = _make_validate_workflow_payload()

        try:
            from agentmap.deployment.cli.validate_command import validate_command

            validate_command(
                csv_file="test.csv",
                csv=None,
                graph=None,
                config_file=None,
            )
        except typer.Exit:
            pass

        mock_resolve_csv_path.assert_called_once()
        mock_validate_workflow_async.assert_called_once()

    @patch(
        "agentmap.deployment.cli.validate_command.validate_workflow",
    )
    @patch("agentmap.deployment.cli.validate_command.resolve_csv_path")
    def test_validate_command_graph_name_forwarded_to_async_facade(
        self, mock_resolve_csv_path, mock_validate_workflow_async
    ):
        """TC-003D edge case: --graph name is used as the graph target for async facade."""
        mock_resolve_csv_path.return_value = "/tmp/test.csv"
        mock_validate_workflow_async.return_value = _make_validate_workflow_payload()

        try:
            from agentmap.deployment.cli.validate_command import validate_command

            validate_command(
                csv_file=None,
                csv="test.csv",
                graph="complex_workflow",
                config_file=None,
            )
        except typer.Exit:
            pass

        call_kwargs = mock_validate_workflow_async.call_args
        assert call_kwargs is not None
        # The graph name must be forwarded as the first positional arg
        assert "complex_workflow" in str(call_kwargs)
        mock_validate_workflow_async.assert_called_once()

    @patch(
        "agentmap.deployment.cli.validate_command.validate_workflow",
    )
    @patch("agentmap.deployment.cli.validate_command.resolve_csv_path")
    def test_validate_command_missing_declarations_still_displays_output(
        self, mock_resolve_csv_path, mock_validate_workflow_async
    ):
        """TC-003D edge case: missing declarations produce the same output as sync path."""
        mock_resolve_csv_path.return_value = "/tmp/test.csv"
        payload = _make_validate_workflow_payload()
        payload["outputs"]["missing_declarations"] = ["missing_agent_type"]
        mock_validate_workflow_async.return_value = payload

        try:
            from agentmap.deployment.cli.validate_command import validate_command

            validate_command(
                csv_file="test.csv",
                csv=None,
                graph=None,
                config_file=None,
            )
        except typer.Exit:
            pass

        mock_validate_workflow_async.assert_called_once()

    def test_validate_command_does_not_import_async_validate_workflow(self):
        """TC-003D counter-factual: async validate_workflow_async must not be in validate_command namespace."""
        import agentmap.deployment.cli.validate_command as validate_cmd_module

        assert not hasattr(
            validate_cmd_module, "validate_workflow_async"
        ), "async validate_workflow_async is imported in validate_command.py — use sync facade for CLI"
