"""
Unit tests for WorkflowOrchestrationService resume logic.

Validates suspend and human-interaction resume flows against the interaction
handler surface that now backs WorkflowOrchestrationService.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from agentmap.models.execution.result import ExecutionResult
from agentmap.services.workflow_orchestration_service import (
    WorkflowOrchestrationService,
    _rehydrate_bundle_from_metadata,
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestWorkflowOrchestrationServiceResume(unittest.TestCase):
    """Test WorkflowOrchestrationService.resume_workflow() method."""

    def setUp(self):
        self.mock_factory = MockServiceFactory()
        self.thread_id = "test_thread_123"
        self.request_id = str(uuid4())
        self.response_action = "approve"
        self.response_data = {"reason": "looks good"}

    def _create_container_with_mocks(
        self,
        *,
        thread_data,
        save_success=True,
        update_success=True,
        pending_interaction=True,
    ):
        """Create a DI container mock wired with the current interaction handler API."""
        mock_container = MagicMock()

        mock_interaction_handler = Mock()
        mock_interaction_handler.get_thread_metadata.return_value = thread_data
        mock_interaction_handler.save_interaction_response.return_value = save_success
        mock_interaction_handler.mark_thread_resuming.return_value = update_success

        mock_graph_bundle_service = self.mock_factory.create_mock_graph_bundle_service()
        mock_graph_runner = Mock()

        mock_container.interaction_handler_service.return_value = (
            mock_interaction_handler
        )
        mock_container.graph_bundle_service.return_value = mock_graph_bundle_service
        mock_container.graph_runner_service.return_value = mock_graph_runner

        return mock_container, mock_interaction_handler, mock_graph_bundle_service, mock_graph_runner

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_success(self, mock_initialize_di):
        """Thread with pending interaction saves response and resumes execution."""
        thread_data = {
            "thread_id": self.thread_id,
            "status": "paused",
            "pending_interaction_id": self.request_id,
            "graph_name": "test_graph",
            "node_name": "human_node",
            "bundle_info": {
                "bundle_path": "/path/to/bundle",
                "csv_hash": "abc123",
                "csv_path": "/path/to/test.csv",
            },
            "checkpoint_data": {
                "messages": ["Hello", "World"],
                "state": "waiting",
            },
        }

        (
            mock_container,
            mock_interaction_handler,
            mock_graph_bundle_service,
            mock_graph_runner,
        ) = self._create_container_with_mocks(thread_data=thread_data)

        mock_bundle = MagicMock()
        mock_bundle.graph_name = "test_graph"
        mock_graph_bundle_service.load_bundle.return_value = mock_bundle
        mock_graph_bundle_service.lookup_bundle.return_value = mock_bundle
        mock_graph_bundle_service.get_or_create_bundle.return_value = (mock_bundle, False)

        expected_result = ExecutionResult(
            success=True,
            graph_name="test_graph",
            final_state={"result": "completed"},
            execution_summary="Resumed successfully",
            total_duration=5.0,
        )
        mock_graph_runner.resume_from_checkpoint.return_value = expected_result

        mock_initialize_di.return_value = mock_container

        result = WorkflowOrchestrationService.resume_workflow(
            thread_id=self.thread_id,
            response_action=self.response_action,
            response_data=self.response_data,
            config_file=None,
        )

        self.assertEqual(result, expected_result)

        mock_interaction_handler.get_thread_metadata.assert_called_once_with(
            self.thread_id
        )
        mock_interaction_handler.save_interaction_response.assert_called_once_with(
            response_id=self.request_id,
            thread_id=self.thread_id,
            action=self.response_action,
            data=self.response_data,
        )
        mock_interaction_handler.mark_thread_resuming.assert_called_once_with(
            thread_id=self.thread_id, last_response_id=self.request_id
        )

        mock_graph_bundle_service.load_bundle.assert_called_once_with(
            Path("/path/to/bundle")
        )
        mock_graph_runner.resume_from_checkpoint.assert_called_once()
        call_kwargs = mock_graph_runner.resume_from_checkpoint.call_args.kwargs
        checkpoint_state = call_kwargs["checkpoint_state"]
        self.assertEqual(checkpoint_state["__human_response"]["action"], self.response_action)
        self.assertEqual(checkpoint_state["__human_response"]["data"], self.response_data)
        self.assertEqual(
            checkpoint_state["__human_response"]["request_id"], self.request_id
        )

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_thread_not_found(self, mock_initialize_di):
        """Missing thread metadata raises a wrapped RuntimeError."""
        (
            mock_container,
            mock_interaction_handler,
            _,
            _,
        ) = self._create_container_with_mocks(thread_data=None)

        mock_initialize_di.return_value = mock_container
        mock_interaction_handler.get_thread_metadata.return_value = None

        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action=self.response_action,
                response_data=self.response_data,
            )

        self.assertIn(
            f"Thread '{self.thread_id}' not found", str(context.exception)
        )

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_no_pending_interaction(self, mock_initialize_di):
        """Suspend-only threads resume without storing a human response."""
        thread_data = {
            "thread_id": self.thread_id,
            "status": "suspended",
            "pending_interaction_id": None,
            "graph_name": "test_graph",
            "node_name": "resume_node",
            "bundle_info": {"bundle_path": "/path/to/bundle"},
            "checkpoint_data": {"state": "paused"},
        }

        (
            mock_container,
            mock_interaction_handler,
            mock_graph_bundle_service,
            mock_graph_runner,
        ) = self._create_container_with_mocks(thread_data=thread_data)

        mock_bundle = MagicMock()
        mock_bundle.graph_name = "test_graph"
        mock_graph_bundle_service.load_bundle.return_value = mock_bundle

        expected_result = ExecutionResult(
            success=True,
            graph_name="test_graph",
            final_state={},
            execution_summary="Resume complete",
            total_duration=1.0,
        )
        mock_graph_runner.resume_from_checkpoint.return_value = expected_result

        mock_initialize_di.return_value = mock_container

        result = WorkflowOrchestrationService.resume_workflow(
            thread_id=self.thread_id,
            response_action="",
            config_file=None,
        )

        self.assertEqual(result, expected_result)
        mock_interaction_handler.save_interaction_response.assert_not_called()
        mock_interaction_handler.mark_thread_resuming.assert_called_once_with(
            thread_id=self.thread_id
        )

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    @patch("agentmap.services.workflow_orchestration_service._rehydrate_bundle_from_metadata")
    def test_resume_workflow_bundle_rehydration_failure(
        self, mock_rehydrate, mock_initialize_di
    ):
        """Rehydration failure produces a wrapped RuntimeError."""
        thread_data = {
            "thread_id": self.thread_id,
            "pending_interaction_id": self.request_id,
            "bundle_info": {"csv_hash": "missing"},
            "graph_name": "test_graph",
        }

        (
            mock_container,
            mock_interaction_handler,
            _,
            _,
        ) = self._create_container_with_mocks(thread_data=thread_data)

        mock_rehydrate.return_value = None
        mock_initialize_di.return_value = mock_container

        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action=self.response_action,
            )

        self.assertIn(
            "Failed to rehydrate GraphBundle", str(context.exception)
        )

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_response_save_failure(self, mock_initialize_di):
        """Failed interaction response persistence surfaces as RuntimeError."""
        thread_data = {
            "thread_id": self.thread_id,
            "pending_interaction_id": self.request_id,
            "bundle_info": {"bundle_path": "/path/to/bundle"},
            "graph_name": "test_graph",
        }

        (
            mock_container,
            mock_interaction_handler,
            mock_graph_bundle_service,
            _,
        ) = self._create_container_with_mocks(
            thread_data=thread_data, save_success=False
        )

        mock_bundle = MagicMock()
        mock_bundle.graph_name = "test_graph"
        mock_graph_bundle_service.load_bundle.return_value = mock_bundle

        mock_initialize_di.return_value = mock_container

        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action=self.response_action,
            )

        self.assertIn("Failed to save interaction response", str(context.exception))

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_thread_update_failure(self, mock_initialize_di):
        """Thread update failure surfaces as RuntimeError."""
        thread_data = {
            "thread_id": self.thread_id,
            "pending_interaction_id": self.request_id,
            "bundle_info": {"bundle_path": "/path/to/bundle"},
            "graph_name": "test_graph",
        }

        (
            mock_container,
            mock_interaction_handler,
            mock_graph_bundle_service,
            _,
        ) = self._create_container_with_mocks(
            thread_data=thread_data, update_success=False
        )

        mock_bundle = MagicMock()
        mock_bundle.graph_name = "test_graph"
        mock_graph_bundle_service.load_bundle.return_value = mock_bundle

        mock_initialize_di.return_value = mock_container

        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action=self.response_action,
            )

        self.assertIn(
            "Failed to update thread status to resuming", str(context.exception)
        )


class TestRehydrateBundleHelper(unittest.TestCase):
    """Unit tests for _rehydrate_bundle_from_metadata helper."""

    def setUp(self):
        self.mock_service = Mock()

    def test_rehydrate_bundle_from_path(self):
        mock_bundle = Mock()
        self.mock_service.load_bundle.return_value = mock_bundle

        result = _rehydrate_bundle_from_metadata(
            {"bundle_path": "/tmp/bundle.pkl"},
            "test_graph",
            self.mock_service,
        )

        self.assertEqual(result, mock_bundle)
        self.mock_service.load_bundle.assert_called_once_with(Path("/tmp/bundle.pkl"))

    def test_rehydrate_bundle_lookup(self):
        mock_bundle = Mock()
        self.mock_service.lookup_bundle.return_value = mock_bundle

        result = _rehydrate_bundle_from_metadata(
            {"csv_hash": "123"},
            "test_graph",
            self.mock_service,
        )

        self.assertEqual(result, mock_bundle)
        self.mock_service.lookup_bundle.assert_called_once_with("123", "test_graph")

    def test_rehydrate_bundle_recreate(self):
        mock_bundle = Mock()
        self.mock_service.get_or_create_bundle.return_value = (mock_bundle, False)

        result = _rehydrate_bundle_from_metadata(
            {"csv_path": "/tmp/workflow.csv"},
            "test_graph",
            self.mock_service,
        )

        self.assertEqual(result, mock_bundle)
        self.mock_service.get_or_create_bundle.assert_called_once_with(
            csv_path=Path("/tmp/workflow.csv"), graph_name="test_graph"
        )

    def test_rehydrate_bundle_failure(self):
        self.mock_service.load_bundle.side_effect = RuntimeError("boom")

        result = _rehydrate_bundle_from_metadata(
            {"bundle_path": "/tmp/bundle.pkl"},
            "test_graph",
            self.mock_service,
        )

        self.assertIsNone(result)
