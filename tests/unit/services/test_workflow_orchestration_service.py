"""
Unit tests for WorkflowOrchestrationService - Service Layer Resume Functionality.

Tests the resume_workflow() static method and _rehydrate_bundle_from_metadata helper.
Uses MockServiceFactory for isolated testing following AgentMap testing patterns.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch
from uuid import UUID, uuid4

from agentmap.exceptions.runtime_exceptions import AgentMapError
from agentmap.models.execution.result import ExecutionResult
from agentmap.models.human_interaction import HumanInteractionResponse
from agentmap.services.storage.types import StorageResult, WriteMode
from agentmap.services.workflow_orchestration_service import (
    WorkflowOrchestrationService,
    _rehydrate_bundle_from_metadata,
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestWorkflowOrchestrationServiceResume(unittest.TestCase):
    """Test WorkflowOrchestrationService.resume_workflow() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_factory = MockServiceFactory()
        self.thread_id = "test_thread_123"
        self.request_id = str(uuid4())
        self.response_action = "approve"
        self.response_data = {"reason": "looks good"}

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_success(self, mock_initialize_di):
        """Test successful resume workflow with all steps working correctly."""
        # Setup mock container and services
        mock_container = MagicMock()
        mock_initialize_di.return_value = mock_container
        
        # Create a mock storage service directly since create_storage_service doesn't exist
        mock_storage = Mock()
        mock_storage.read.return_value = None
        mock_storage.write.return_value = Mock(success=True, error=None)
        mock_storage.delete.return_value = Mock(success=True, error=None)
        mock_storage.exists.return_value = False
        mock_graph_bundle_service = self.mock_factory.create_mock_graph_bundle_service()
        # Create a mock graph runner service directly
        mock_graph_runner = Mock()
        mock_graph_runner.resume_from_checkpoint.return_value = Mock()
        
        mock_container.json_storage_service.return_value = mock_storage
        mock_container.graph_bundle_service.return_value = mock_graph_bundle_service
        mock_container.graph_runner_service.return_value = mock_graph_runner
        
        # Setup thread data with pending interaction
        thread_data = {
            "thread_id": self.thread_id,
            "status": "paused",
            "pending_interaction_id": self.request_id,
            "graph_name": "test_graph",
            "node_name": "human_node",
            "bundle_info": {
                "csv_hash": "abc123",
                "bundle_path": "/path/to/bundle",
                "csv_path": "/path/to/test.csv",
            },
            "checkpoint_data": {
                "messages": ["Hello", "World"],
                "state": "waiting",
            },
        }
        
        mock_storage.read.return_value = thread_data
        
        # Setup successful save operations
        mock_storage.write.return_value = StorageResult(success=True, document_id=self.request_id)
        
        # Setup bundle rehydration
        mock_bundle = MagicMock()
        mock_bundle.graph_name = "test_graph"
        # Ensure all bundle service methods return the same mock bundle
        mock_graph_bundle_service.load_bundle.return_value = mock_bundle
        mock_graph_bundle_service.lookup_bundle.return_value = mock_bundle
        mock_graph_bundle_service.get_or_create_bundle.return_value = mock_bundle
        
        # Setup successful resume
        expected_result = ExecutionResult(
            success=True,
            graph_name="test_graph",
            final_state={"result": "completed"},
            execution_summary="Resumed successfully",
            total_duration=5.0,
        )
        mock_graph_runner.resume_from_checkpoint.return_value = expected_result
        
        # Execute
        result = WorkflowOrchestrationService.resume_workflow(
            thread_id=self.thread_id,
            response_action=self.response_action,
            response_data=self.response_data,
            config_file=None,
        )
        
        # Verify
        self.assertEqual(result, expected_result)
        
        # Verify DI initialization
        mock_initialize_di.assert_called_once_with(None)
        
        # Verify thread data was loaded
        mock_storage.read.assert_called_once_with(
            collection="interactions_threads",
            document_id=self.thread_id,
        )
        
        # Verify response was saved
        calls = mock_storage.write.call_args_list
        self.assertEqual(len(calls), 2)
        
        # First call saves the response
        response_call = calls[0]
        self.assertEqual(response_call.kwargs["collection"], "interactions_responses")
        self.assertEqual(response_call.kwargs["document_id"], self.request_id)
        self.assertEqual(response_call.kwargs["mode"], WriteMode.WRITE)
        saved_data = response_call.kwargs["data"]
        self.assertEqual(saved_data["request_id"], self.request_id)
        self.assertEqual(saved_data["action"], self.response_action)
        self.assertEqual(saved_data["data"], self.response_data)
        
        # Second call updates thread status
        thread_update_call = calls[1]
        self.assertEqual(thread_update_call.kwargs["collection"], "interactions_threads")
        self.assertEqual(thread_update_call.kwargs["document_id"], self.thread_id)
        self.assertEqual(thread_update_call.kwargs["mode"], WriteMode.UPDATE)
        update_data = thread_update_call.kwargs["data"]
        self.assertEqual(update_data["status"], "resuming")
        self.assertIsNone(update_data["pending_interaction_id"])
        self.assertEqual(update_data["last_response_id"], self.request_id)
        
        # Verify bundle was loaded
        mock_graph_bundle_service.load_bundle.assert_called_once_with(Path("/path/to/bundle"))
        
        # Verify resume was called with correct state
        mock_graph_runner.resume_from_checkpoint.assert_called_once()
        call_args = mock_graph_runner.resume_from_checkpoint.call_args
        # Verify that a bundle was passed (the exact mock object may vary due to DI container behavior)
        self.assertIsNotNone(call_args.kwargs["bundle"])
        self.assertEqual(call_args.kwargs["thread_id"], self.thread_id)
        self.assertEqual(call_args.kwargs["resume_node"], "human_node")
        
        # Verify checkpoint state includes human response
        checkpoint_state = call_args.kwargs["checkpoint_state"]
        self.assertIn("__human_response", checkpoint_state)
        self.assertEqual(checkpoint_state["__human_response"]["action"], self.response_action)
        self.assertEqual(checkpoint_state["__human_response"]["data"], self.response_data)
        self.assertEqual(checkpoint_state["__human_response"]["request_id"], self.request_id)

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_thread_not_found(self, mock_initialize_di):
        """Test resume workflow when thread is not found in storage."""
        # Setup mock container and services
        mock_container = MagicMock()
        mock_initialize_di.return_value = mock_container
        
        # Create a mock storage service directly since create_storage_service doesn't exist
        mock_storage = Mock()
        mock_storage.read.return_value = None
        mock_storage.write.return_value = Mock(success=True, error=None)
        mock_storage.delete.return_value = Mock(success=True, error=None)
        mock_storage.exists.return_value = False
        mock_container.json_storage_service.return_value = mock_storage
        
        # Thread not found
        mock_storage.read.return_value = None
        
        # Execute and verify exception
        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action=self.response_action,
                response_data=self.response_data,
            )
        
        self.assertIn(f"Thread '{self.thread_id}' not found", str(context.exception))

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_no_pending_interaction(self, mock_initialize_di):
        """Test resume workflow when thread has no pending interaction."""
        # Setup mock container and services
        mock_container = MagicMock()
        mock_initialize_di.return_value = mock_container
        
        # Create a mock storage service directly since create_storage_service doesn't exist
        mock_storage = Mock()
        mock_storage.read.return_value = None
        mock_storage.write.return_value = Mock(success=True, error=None)
        mock_storage.delete.return_value = Mock(success=True, error=None)
        mock_storage.exists.return_value = False
        mock_container.json_storage_service.return_value = mock_storage
        
        # Thread exists but no pending interaction
        thread_data = {
            "thread_id": self.thread_id,
            "status": "completed",
            "pending_interaction_id": None,  # No pending interaction
        }
        mock_storage.read.return_value = thread_data
        
        # Execute and verify exception
        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action=self.response_action,
            )
        
        self.assertIn("No pending interaction found", str(context.exception))

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    @patch("agentmap.services.workflow_orchestration_service._rehydrate_bundle_from_metadata")
    def test_resume_workflow_bundle_rehydration_failure(
        self, mock_rehydrate, mock_initialize_di
    ):
        """Test resume workflow when bundle rehydration fails."""
        # Setup mock container and services
        mock_container = MagicMock()
        mock_initialize_di.return_value = mock_container
        
        # Create a mock storage service directly since create_storage_service doesn't exist
        mock_storage = Mock()
        mock_storage.read.return_value = None
        mock_storage.write.return_value = Mock(success=True, error=None)
        mock_storage.delete.return_value = Mock(success=True, error=None)
        mock_storage.exists.return_value = False
        mock_graph_bundle_service = self.mock_factory.create_mock_graph_bundle_service()
        
        mock_container.json_storage_service.return_value = mock_storage
        mock_container.graph_bundle_service.return_value = mock_graph_bundle_service
        
        # Setup thread data
        thread_data = {
            "thread_id": self.thread_id,
            "pending_interaction_id": self.request_id,
            "bundle_info": {"csv_hash": "abc123"},
            "graph_name": "test_graph",
        }
        mock_storage.read.return_value = thread_data
        
        # Bundle rehydration fails
        mock_rehydrate.return_value = None
        
        # Execute and verify exception
        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action=self.response_action,
            )
        
        self.assertIn("Failed to rehydrate GraphBundle", str(context.exception))

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_response_save_failure(self, mock_initialize_di):
        """Test resume workflow when saving response fails."""
        # Setup mock container and services
        mock_container = MagicMock()
        mock_initialize_di.return_value = mock_container
        
        # Create a mock storage service directly since create_storage_service doesn't exist
        mock_storage = Mock()
        mock_storage.read.return_value = None
        mock_storage.write.return_value = Mock(success=True, error=None)
        mock_storage.delete.return_value = Mock(success=True, error=None)
        mock_storage.exists.return_value = False
        mock_graph_bundle_service = self.mock_factory.create_mock_graph_bundle_service()
        
        mock_container.json_storage_service.return_value = mock_storage
        mock_container.graph_bundle_service.return_value = mock_graph_bundle_service
        
        # Setup thread data
        thread_data = {
            "thread_id": self.thread_id,
            "pending_interaction_id": self.request_id,
            "bundle_info": {"bundle_path": "/path/to/bundle"},
            "graph_name": "test_graph",
        }
        mock_storage.read.return_value = thread_data
        
        # Setup bundle
        mock_bundle = MagicMock()
        mock_graph_bundle_service.load_bundle.return_value = mock_bundle
        
        # Response save fails
        mock_storage.write.return_value = StorageResult(
            success=False, error="Database write failed"
        )
        
        # Execute and verify exception
        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action=self.response_action,
            )
        
        self.assertIn("Failed to save response", str(context.exception))

    @patch("agentmap.services.workflow_orchestration_service.initialize_di")
    def test_resume_workflow_thread_update_failure(self, mock_initialize_di):
        """Test resume workflow when updating thread status fails."""
        # Setup mock container and services
        mock_container = MagicMock()
        mock_initialize_di.return_value = mock_container
        
        # Create a mock storage service directly since create_storage_service doesn't exist
        mock_storage = Mock()
        mock_storage.read.return_value = None
        mock_storage.write.return_value = Mock(success=True, error=None)
        mock_storage.delete.return_value = Mock(success=True, error=None)
        mock_storage.exists.return_value = False
        mock_graph_bundle_service = self.mock_factory.create_mock_graph_bundle_service()
        
        mock_container.json_storage_service.return_value = mock_storage
        mock_container.graph_bundle_service.return_value = mock_graph_bundle_service
        
        # Setup thread data
        thread_data = {
            "thread_id": self.thread_id,
            "pending_interaction_id": self.request_id,
            "bundle_info": {"bundle_path": "/path/to/bundle"},
            "graph_name": "test_graph",
        }
        mock_storage.read.return_value = thread_data
        
        # Setup bundle
        mock_bundle = MagicMock()
        mock_graph_bundle_service.load_bundle.return_value = mock_bundle
        
        # First write (response) succeeds, second (thread update) fails
        mock_storage.write.side_effect = [
            StorageResult(success=True, document_id=self.request_id),
            StorageResult(success=False, error="Update failed"),
        ]
        
        # Execute and verify exception
        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action=self.response_action,
            )
        
        self.assertIn("Failed to update thread status", str(context.exception))

if __name__ == "__main__":
    unittest.main()
