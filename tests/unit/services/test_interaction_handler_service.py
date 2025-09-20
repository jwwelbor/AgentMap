"""
Unit tests for InteractionHandlerService.

Tests the interaction handling middleware including exception processing,
thread metadata storage, bundle context preservation, and CLI coordination.
"""

import time
import unittest
import unittest.mock
from datetime import datetime
from typing import Dict, Any, Optional
from unittest.mock import Mock, MagicMock
from uuid import uuid4

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
from agentmap.services.interaction_handler_service import InteractionHandlerService
from agentmap.services.storage.types import StorageResult, WriteMode
from tests.utils.mock_service_factory import MockServiceFactory
from tests.utils.mock_service_factory_patch import create_fixed_mock_logging_service


class TestInteractionHandlerService(unittest.TestCase):
    """Test InteractionHandlerService functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory."""
        self.mock_factory = MockServiceFactory()
        
        # Create mock services
        self.mock_storage_service = Mock()
        self.mock_logging = create_fixed_mock_logging_service()
        
        # Configure successful storage operations by default
        self.mock_storage_service.write.return_value = StorageResult(success=True, error=None)
        self.mock_storage_service.read.return_value = None
        
        # Create service under test
        self.interaction_service = InteractionHandlerService(
            storage_service=self.mock_storage_service,
            logging_service=self.mock_logging
        )

    def _create_test_interaction_request(
        self,
        thread_id: str = "test_thread",
        node_name: str = "test_node"
    ) -> HumanInteractionRequest:
        """Create a test interaction request."""
        return HumanInteractionRequest(
            id=uuid4(),
            thread_id=thread_id,
            node_name=node_name,
            interaction_type=InteractionType.TEXT_INPUT,
            prompt="Please provide input",
            context={"test": "context"},
            options=["option1", "option2"],
            timeout_seconds=300
        )

    def _create_test_exception(
        self,
        thread_id: str = "test_thread",
        interaction_request: Optional[HumanInteractionRequest] = None,
        checkpoint_data: Optional[Dict[str, Any]] = None
    ) -> ExecutionInterruptedException:
        """Create a test ExecutionInterruptedException."""
        if interaction_request is None:
            interaction_request = self._create_test_interaction_request(thread_id)
        
        if checkpoint_data is None:
            checkpoint_data = {
                "inputs": {"input_key": "input_value"},
                "agent_context": {"context_key": "context_value"},
                "execution_tracker": "tracker_data",
                "node_name": "test_node"
            }
        
        return ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data
        )

    def _create_test_bundle(self) -> Mock:
        """Create a test GraphBundle mock."""
        mock_bundle = Mock()
        mock_bundle.csv_hash = "test_hash_123"
        mock_bundle.bundle_path = "/test/path/bundle.json"
        mock_bundle.csv_path = "/test/path/workflow.csv"
        return mock_bundle

    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.interaction_service)
        self.assertEqual(
            self.interaction_service.storage_service,
            self.mock_storage_service
        )
        
        # Check collection names
        self.assertEqual(
            self.interaction_service.interactions_collection,
            "interactions"
        )
        self.assertEqual(
            self.interaction_service.threads_collection,
            "interactions_threads"
        )
        self.assertEqual(
            self.interaction_service.responses_collection,
            "interactions_responses"
        )

    def test_handle_execution_interruption_success(self):
        """Test successful execution interruption handling."""
        # Arrange
        exception = self._create_test_exception()
        bundle = self._create_test_bundle()
        bundle_context = {"additional": "context"}
        
        # Act
        self.interaction_service.handle_execution_interruption(
            exception=exception,
            bundle=bundle,
            bundle_context=bundle_context
        )
        
        # Assert - Verify interaction request was stored
        interaction_calls = [
            call for call in self.mock_storage_service.write.call_args_list
            if call.kwargs.get("collection") == "interactions"
        ]
        self.assertEqual(len(interaction_calls), 1)
        
        interaction_call = interaction_calls[0]
        self.assertEqual(interaction_call.kwargs["mode"], WriteMode.WRITE)
        
        interaction_data = interaction_call.kwargs["data"]
        self.assertEqual(interaction_data["thread_id"], "test_thread")
        self.assertEqual(interaction_data["node_name"], "test_node")
        self.assertEqual(interaction_data["interaction_type"], "text_input")
        self.assertEqual(interaction_data["prompt"], "Please provide input")
        self.assertEqual(interaction_data["status"], "pending")
        
        # Assert - Verify thread metadata was stored
        thread_calls = [
            call for call in self.mock_storage_service.write.call_args_list
            if call.kwargs.get("collection") == "interactions_threads"
        ]
        self.assertEqual(len(thread_calls), 1)
        
        thread_call = thread_calls[0]
        thread_data = thread_call.kwargs["data"]
        self.assertEqual(thread_data["thread_id"], "test_thread")
        self.assertEqual(thread_data["status"], "paused")
        
        # Check bundle context preservation
        bundle_info = thread_data["bundle_info"]
        self.assertEqual(bundle_info["additional"], "context")  # From bundle_context
        
        # Note: The service uses a direct import of display_interaction_request
        # In a more comprehensive test, we would mock that import

    def test_handle_execution_interruption_with_bundle_extraction(self):
        """Test interruption handling with bundle context extraction."""
        # Arrange
        exception = self._create_test_exception()
        bundle = self._create_test_bundle()
        # No bundle_context provided - should extract from bundle
        
        # Act
        self.interaction_service.handle_execution_interruption(
            exception=exception,
            bundle=bundle
        )
        
        # Assert - Verify bundle info was extracted
        thread_calls = [
            call for call in self.mock_storage_service.write.call_args_list
            if call.kwargs.get("collection") == "interactions_threads"
        ]
        
        thread_data = thread_calls[0].kwargs["data"]
        bundle_info = thread_data["bundle_info"]
        
        self.assertEqual(bundle_info["csv_hash"], "test_hash_123")
        self.assertEqual(bundle_info["bundle_path"], "/test/path/bundle.json")
        self.assertEqual(bundle_info["csv_path"], "/test/path/workflow.csv")

    def test_handle_execution_interruption_no_bundle(self):
        """Test interruption handling without bundle context."""
        # Arrange
        exception = self._create_test_exception()
        
        # Act
        self.interaction_service.handle_execution_interruption(exception=exception)
        
        # Assert - Verify empty bundle info
        thread_calls = [
            call for call in self.mock_storage_service.write.call_args_list
            if call.kwargs.get("collection") == "interactions_threads"
        ]
        
        thread_data = thread_calls[0].kwargs["data"]
        bundle_info = thread_data["bundle_info"]
        
        self.assertEqual(bundle_info, {})

    def test_store_interaction_request(self):
        """Test interaction request storage."""
        # Arrange
        request = self._create_test_interaction_request()
        
        # Act
        self.interaction_service._store_interaction_request(request)
        
        # Assert
        self.mock_storage_service.write.assert_called_once()
        call_args = self.mock_storage_service.write.call_args
        
        self.assertEqual(call_args.kwargs["collection"], "interactions")
        self.assertEqual(call_args.kwargs["document_id"], str(request.id))
        self.assertEqual(call_args.kwargs["mode"], WriteMode.WRITE)
        
        data = call_args.kwargs["data"]
        self.assertEqual(data["id"], str(request.id))
        self.assertEqual(data["thread_id"], request.thread_id)
        self.assertEqual(data["node_name"], request.node_name)
        self.assertEqual(data["interaction_type"], request.interaction_type.value)
        self.assertEqual(data["prompt"], request.prompt)
        self.assertEqual(data["context"], request.context)
        self.assertEqual(data["options"], request.options)
        self.assertEqual(data["timeout_seconds"], request.timeout_seconds)
        self.assertEqual(data["status"], "pending")

    def test_store_interaction_request_failure(self):
        """Test interaction request storage failure."""
        # Arrange
        request = self._create_test_interaction_request()
        self.mock_storage_service.write.return_value = StorageResult(
            success=False,
            error="Storage failed"
        )
        
        # Act & Assert
        with self.assertRaises(RuntimeError) as context:
            self.interaction_service._store_interaction_request(request)
        
        self.assertIn("Failed to store interaction request", str(context.exception))

    def test_store_thread_metadata(self):
        """Test thread metadata storage."""
        # Arrange
        thread_id = "test_thread"
        interaction_request = self._create_test_interaction_request()
        checkpoint_data = {
            "inputs": {"key": "value"},
            "agent_context": {"context": "data"},
            "execution_tracker": "tracker",
            "node_name": "test_node"
        }
        bundle = self._create_test_bundle()
        bundle_context = {"extra": "data"}
        
        # Act
        self.interaction_service._store_thread_metadata(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
            bundle=bundle,
            bundle_context=bundle_context
        )
        
        # Assert
        self.mock_storage_service.write.assert_called_once()
        call_args = self.mock_storage_service.write.call_args
        
        self.assertEqual(call_args.kwargs["collection"], "interactions_threads")
        self.assertEqual(call_args.kwargs["document_id"], thread_id)
        self.assertEqual(call_args.kwargs["mode"], WriteMode.WRITE)
        
        data = call_args.kwargs["data"]
        self.assertEqual(data["thread_id"], thread_id)
        self.assertEqual(data["node_name"], interaction_request.node_name)
        self.assertEqual(data["pending_interaction_id"], str(interaction_request.id))
        self.assertEqual(data["status"], "paused")
        
        # Check bundle context (should prefer bundle_context over bundle)
        self.assertEqual(data["bundle_info"]["extra"], "data")
        
        # Check checkpoint data preservation
        checkpoint = data["checkpoint_data"]
        self.assertEqual(checkpoint["inputs"], {"key": "value"})
        self.assertEqual(checkpoint["agent_context"], {"context": "data"})
        self.assertEqual(checkpoint["execution_tracker"], "tracker")

    def test_store_thread_metadata_failure(self):
        """Test thread metadata storage failure."""
        # Arrange
        self.mock_storage_service.write.return_value = StorageResult(
            success=False,
            error="Thread storage failed"
        )
        
        thread_id = "test_thread"
        interaction_request = self._create_test_interaction_request()
        checkpoint_data = {"test": "data"}
        
        # Act & Assert
        with self.assertRaises(RuntimeError) as context:
            self.interaction_service._store_thread_metadata(
                thread_id=thread_id,
                interaction_request=interaction_request,
                checkpoint_data=checkpoint_data
            )
        
        self.assertIn("Failed to store thread metadata", str(context.exception))

    def test_get_thread_metadata_found(self):
        """Test retrieving existing thread metadata."""
        # Arrange
        thread_id = "test_thread"
        expected_metadata = {
            "thread_id": thread_id,
            "status": "paused",
            "bundle_info": {"csv_hash": "test123"},
            "node_name": "test_node"
        }
        
        self.mock_storage_service.read.return_value = expected_metadata
        
        # Act
        metadata = self.interaction_service.get_thread_metadata(thread_id)
        
        # Assert
        self.assertEqual(metadata, expected_metadata)
        self.mock_storage_service.read.assert_called_once_with(
            collection="interactions_threads",
            document_id=thread_id
        )

    def test_get_thread_metadata_not_found(self):
        """Test retrieving non-existent thread metadata."""
        # Arrange
        thread_id = "nonexistent_thread"
        self.mock_storage_service.read.return_value = None
        
        # Act
        metadata = self.interaction_service.get_thread_metadata(thread_id)
        
        # Assert
        self.assertIsNone(metadata)

    def test_get_thread_metadata_error(self):
        """Test error handling in thread metadata retrieval."""
        # Arrange
        thread_id = "error_thread"
        self.mock_storage_service.read.side_effect = Exception("Storage error")
        
        # Act
        metadata = self.interaction_service.get_thread_metadata(thread_id)
        
        # Assert
        self.assertIsNone(metadata)
        
        # Verify error was logged
        # The service calls get_class_logger(self) where self is the InteractionHandlerService instance
        logger = self.mock_logging.get_class_logger(self.interaction_service)
        error_calls = logger.error.call_args_list
        self.assertTrue(
            any("Failed to retrieve thread metadata" in str(call) for call in error_calls),
            f"Expected error message not found in calls: {error_calls}"
        )

    def test_mark_thread_resuming_success(self):
        """Test successfully marking thread as resuming."""
        # Arrange
        thread_id = "test_thread"
        
        # Act
        result = self.interaction_service.mark_thread_resuming(thread_id)
        
        # Assert
        self.assertTrue(result)
        self.mock_storage_service.write.assert_called_once()
        
        call_args = self.mock_storage_service.write.call_args
        self.assertEqual(call_args.kwargs["collection"], "interactions_threads")
        self.assertEqual(call_args.kwargs["document_id"], thread_id)
        self.assertEqual(call_args.kwargs["mode"], WriteMode.UPDATE)
        
        data = call_args.kwargs["data"]
        self.assertEqual(data["status"], "resuming")
        self.assertIn("resumed_at", data)

    def test_mark_thread_resuming_failure(self):
        """Test failure in marking thread as resuming."""
        # Arrange
        thread_id = "test_thread"
        self.mock_storage_service.write.return_value = StorageResult(
            success=False,
            error="Update failed"
        )
        
        # Act
        result = self.interaction_service.mark_thread_resuming(thread_id)
        
        # Assert
        self.assertFalse(result)

    def test_mark_thread_resuming_exception(self):
        """Test exception handling in mark_thread_resuming."""
        # Arrange
        thread_id = "test_thread"
        self.mock_storage_service.write.side_effect = Exception("Storage exception")
        
        # Act
        result = self.interaction_service.mark_thread_resuming(thread_id)
        
        # Assert
        self.assertFalse(result)

    def test_mark_thread_completed_success(self):
        """Test successfully marking thread as completed."""
        # Arrange
        thread_id = "test_thread"
        
        # Act
        result = self.interaction_service.mark_thread_completed(thread_id)
        
        # Assert
        self.assertTrue(result)
        self.mock_storage_service.write.assert_called_once()
        
        call_args = self.mock_storage_service.write.call_args
        data = call_args.kwargs["data"]
        self.assertEqual(data["status"], "completed")
        self.assertIsNone(data["pending_interaction_id"])
        self.assertIn("completed_at", data)

    def test_mark_thread_completed_failure(self):
        """Test failure in marking thread as completed."""
        # Arrange
        thread_id = "test_thread"
        self.mock_storage_service.write.return_value = StorageResult(
            success=False,
            error="Completion update failed"
        )
        
        # Act
        result = self.interaction_service.mark_thread_completed(thread_id)
        
        # Assert
        self.assertFalse(result)

    def test_cleanup_expired_threads(self):
        """Test expired thread cleanup."""
        # Act
        cleaned = self.interaction_service.cleanup_expired_threads(24)
        
        # Assert
        # Current implementation is simplified and returns 0
        self.assertEqual(cleaned, 0)

    def test_get_service_info(self):
        """Test service information retrieval."""
        # Act
        info = self.interaction_service.get_service_info()
        
        # Assert
        self.assertEqual(info["service"], "InteractionHandlerService")
        self.assertTrue(info["storage_service_available"])
        
        collections = info["collections"]
        self.assertEqual(collections["interactions"], "interactions")
        self.assertEqual(collections["threads"], "interactions_threads")
        self.assertEqual(collections["responses"], "interactions_responses")
        
        capabilities = info["capabilities"]
        self.assertTrue(capabilities["exception_handling"])
        self.assertTrue(capabilities["thread_metadata_storage"])
        self.assertTrue(capabilities["bundle_context_preservation"])
        self.assertTrue(capabilities["cli_interaction_display"])
        self.assertTrue(capabilities["lifecycle_management"])
        self.assertTrue(capabilities["cleanup_support"])

    def test_get_service_info_missing_services(self):
        """Test service info with missing services."""
        # Arrange - Create service with None services
        service = InteractionHandlerService(
            storage_service=None,
            logging_service=self.mock_logging
        )
        
        # Act
        info = service.get_service_info()
        
        # Assert
        self.assertFalse(info["storage_service_available"])

    def test_handle_execution_interruption_storage_failure(self):
        """Test execution interruption handling with storage failure."""
        # Arrange
        exception = self._create_test_exception()
        self.mock_storage_service.write.return_value = StorageResult(
            success=False,
            error="Storage failure"
        )
        
        # Act & Assert
        with self.assertRaises(RuntimeError) as context:
            self.interaction_service.handle_execution_interruption(exception)
        
        self.assertIn("Interaction handling failed", str(context.exception))

    def test_handle_execution_interruption_cli_failure(self):
        """Test execution interruption handling with CLI display failure."""
        # Arrange
        exception = self._create_test_exception()
        
        # Mock the display_interaction_request import to raise an exception
        with unittest.mock.patch(
            'agentmap.deployment.cli.display_utils.display_interaction_request',
            side_effect=Exception("CLI error")
        ):
            # Act & Assert
            with self.assertRaises(RuntimeError) as context:
                self.interaction_service.handle_execution_interruption(exception)
            
            self.assertIn("Interaction handling failed", str(context.exception))

    def test_thread_metadata_with_checkpoint_data_extraction(self):
        """Test thread metadata storage with checkpoint data processing."""
        # Arrange
        thread_id = "test_thread"
        interaction_request = self._create_test_interaction_request()
        checkpoint_data = {
            "inputs": {"user_input": "test_value"},
            "agent_context": {"execution_id": "exec_123"},
            "execution_tracker": {"node_count": 3},
            "node_name": "current_node"
        }
        
        # Act
        self.interaction_service._store_thread_metadata(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data
        )
        
        # Assert
        call_args = self.mock_storage_service.write.call_args
        data = call_args.kwargs["data"]
        
        # Verify graph_name fallback logic
        expected_graph_name = checkpoint_data.get("node_name") or interaction_request.node_name
        self.assertEqual(data["graph_name"], expected_graph_name)
        
        # Verify checkpoint data structure
        stored_checkpoint = data["checkpoint_data"]
        self.assertEqual(stored_checkpoint["inputs"], checkpoint_data["inputs"])
        self.assertEqual(stored_checkpoint["agent_context"], checkpoint_data["agent_context"])
        self.assertEqual(stored_checkpoint["execution_tracker"], checkpoint_data["execution_tracker"])

    def test_bundle_extraction_edge_cases(self):
        """Test bundle context extraction edge cases."""
        # Test with bundle that has no attributes
        minimal_bundle = Mock()
        del minimal_bundle.csv_hash  # Remove attributes
        del minimal_bundle.bundle_path
        del minimal_bundle.csv_path
        
        exception = self._create_test_exception()
        
        # Should not raise exception
        self.interaction_service.handle_execution_interruption(
            exception=exception,
            bundle=minimal_bundle
        )
        
        # Verify it handled missing attributes gracefully
        thread_calls = [
            call for call in self.mock_storage_service.write.call_args_list
            if call.kwargs.get("collection") == "interactions_threads"
        ]
        
        thread_data = thread_calls[0].kwargs["data"]
        bundle_info = thread_data["bundle_info"]
        
        # Should have None values for missing attributes
        self.assertIsNone(bundle_info.get("csv_hash"))
        self.assertIsNone(bundle_info.get("bundle_path"))
        self.assertIsNone(bundle_info.get("csv_path"))


if __name__ == "__main__":
    unittest.main()
