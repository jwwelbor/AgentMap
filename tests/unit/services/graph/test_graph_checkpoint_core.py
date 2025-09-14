"""
Working unit tests for GraphCheckpointService - core functionality.

Tests the checkpoint service basic operations without complex LangGraph integration.
Focuses on testing the actual business logic and data handling.
"""

import unittest
from unittest.mock import Mock

from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
from agentmap.services.storage.types import StorageResult, WriteMode


class TestGraphCheckpointServiceCore(unittest.TestCase):
    """Test GraphCheckpointService core functionality."""

    def setUp(self):
        """Set up test fixtures using basic mocks."""
        self.mock_json_storage = Mock()
        self.mock_logging = Mock()
        self.mock_logger = Mock()
        self.mock_logging.get_class_logger.return_value = self.mock_logger
        
        # Configure successful storage operations by default
        self.mock_json_storage.write.return_value = StorageResult(success=True, error=None)
        self.mock_json_storage.read.return_value = []
        self.mock_json_storage.is_healthy.return_value = True
        
        # Create service under test
        self.checkpoint_service = GraphCheckpointService(
            json_storage_service=self.mock_json_storage,
            logging_service=self.mock_logging
        )

    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.checkpoint_service)
        self.assertEqual(self.checkpoint_service.storage, self.mock_json_storage)
        self.assertEqual(self.checkpoint_service.checkpoint_collection, "langgraph_checkpoints")

    def test_get_service_info(self):
        """Test service information retrieval."""
        info = self.checkpoint_service.get_service_info()
        
        # Verify basic service info
        self.assertEqual(info["service_name"], "GraphCheckpointService")
        self.assertEqual(info["langgraph_collection"], "langgraph_checkpoints")
        self.assertTrue(info["storage_available"])
        self.assertTrue(info["capabilities"]["langgraph_put"])
        self.assertTrue(info["capabilities"]["langgraph_get_tuple"])
        self.assertTrue(info["implements_base_checkpoint_saver"])

    def test_get_service_info_unhealthy_storage(self):
        """Test service information when storage is unhealthy."""
        self.mock_json_storage.is_healthy.return_value = False
        
        info = self.checkpoint_service.get_service_info()
        self.assertFalse(info["storage_available"])

    def test_get_thread_checkpoints_empty(self):
        """Test getting checkpoints for thread with no checkpoints."""
        self.mock_json_storage.read.return_value = None
        
        checkpoints = self.checkpoint_service._get_thread_checkpoints("empty_thread")
        self.assertEqual(checkpoints, [])

    def test_get_thread_checkpoints_with_dict_result(self):
        """Test getting checkpoints when storage returns dict."""
        mock_data = {
            "checkpoint1": {"thread_id": "test", "data": "value1"},
            "checkpoint2": {"thread_id": "test", "data": "value2"}
        }
        self.mock_json_storage.read.return_value = mock_data
        
        checkpoints = self.checkpoint_service._get_thread_checkpoints("test_thread")
        
        self.assertEqual(len(checkpoints), 2)
        self.assertIn({"thread_id": "test", "data": "value1"}, checkpoints)
        self.assertIn({"thread_id": "test", "data": "value2"}, checkpoints)

    def test_get_thread_checkpoints_with_list_result(self):
        """Test getting checkpoints when storage returns list."""
        mock_data = [
            {"thread_id": "test", "data": "value1"},
            {"thread_id": "test", "data": "value2"}
        ]
        self.mock_json_storage.read.return_value = mock_data
        
        checkpoints = self.checkpoint_service._get_thread_checkpoints("test_thread")
        self.assertEqual(checkpoints, mock_data)

    def test_get_thread_checkpoints_error_handling(self):
        """Test error handling in checkpoint retrieval."""
        self.mock_json_storage.read.side_effect = Exception("Storage error")
        
        checkpoints = self.checkpoint_service._get_thread_checkpoints("error_thread")
        self.assertEqual(checkpoints, [])
        
        # Verify error was logged
        self.mock_logger.error.assert_called()
        error_call = self.mock_logger.error.call_args[0][0]
        self.assertIn("Error getting thread checkpoints", error_call)

    def test_metadata_serialization_deserialization(self):
        """Test metadata serialization and deserialization."""
        test_metadata = {"source": "test", "step": 1, "nested": {"key": "value"}}
        
        # Test serialization
        serialized = self.checkpoint_service._serialize_metadata(test_metadata)
        self.assertIsInstance(serialized, str)
        
        # Test deserialization
        deserialized = self.checkpoint_service._deserialize_metadata(serialized)
        self.assertEqual(deserialized, test_metadata)

    def test_storage_query_parameters(self):
        """Test that storage is called with correct query parameters."""
        thread_id = "test_thread_123"
        
        # Call method that queries storage
        self.checkpoint_service._get_thread_checkpoints(thread_id)
        
        # Verify storage was called with correct parameters
        self.mock_json_storage.read.assert_called_once_with(
            collection="langgraph_checkpoints",
            query={"thread_id": thread_id}
        )

    def test_inheritance_from_base_checkpoint_saver(self):
        """Test that the service inherits from BaseCheckpointSaver."""
        from langgraph.checkpoint.base import BaseCheckpointSaver
        
        self.assertIsInstance(self.checkpoint_service, BaseCheckpointSaver)

    def test_service_has_required_methods(self):
        """Test that the service implements required methods."""
        # These are the key methods that should exist
        required_methods = [
            'put', 'get_tuple', '_serialize_checkpoint', '_deserialize_checkpoint',
            '_serialize_metadata', '_deserialize_metadata', '_get_thread_checkpoints'
        ]
        
        for method_name in required_methods:
            self.assertTrue(hasattr(self.checkpoint_service, method_name))
            self.assertTrue(callable(getattr(self.checkpoint_service, method_name)))


class TestInterruptResumeWorkflowCore(unittest.TestCase):
    """Test core interrupt and resume workflow functionality."""

    def test_execution_interrupted_exception_structure(self):
        """Test that ExecutionInterruptedException has the right structure."""
        from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
        from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
        from uuid import uuid4
        
        # Create test data
        thread_id = "workflow_test_thread"
        interaction_request = HumanInteractionRequest(
            id=uuid4(),
            thread_id=thread_id,
            node_name="test_node",
            interaction_type=InteractionType.TEXT_INPUT,
            prompt="Test prompt"
        )
        checkpoint_data = {"test": "data"}
        
        # Create exception
        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data
        )
        
        # Verify structure
        self.assertEqual(exception.thread_id, thread_id)
        self.assertEqual(exception.interaction_request, interaction_request)
        self.assertEqual(exception.checkpoint_data, checkpoint_data)
        self.assertIn(thread_id, str(exception))

    def test_human_interaction_request_structure(self):
        """Test HumanInteractionRequest model structure."""
        from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
        from uuid import uuid4
        
        request_id = uuid4()
        request = HumanInteractionRequest(
            id=request_id,
            thread_id="test_thread",
            node_name="test_node",
            interaction_type=InteractionType.APPROVAL,
            prompt="Please approve",
            context={"key": "value"},
            options=["approve", "reject"],
            timeout_seconds=300
        )
        
        # Verify all fields are preserved
        self.assertEqual(request.id, request_id)
        self.assertEqual(request.thread_id, "test_thread")
        self.assertEqual(request.node_name, "test_node")
        self.assertEqual(request.interaction_type, InteractionType.APPROVAL)
        self.assertEqual(request.prompt, "Please approve")
        self.assertEqual(request.context["key"], "value")
        self.assertEqual(request.options, ["approve", "reject"])
        self.assertEqual(request.timeout_seconds, 300)

    def test_interaction_workflow_components_exist(self):
        """Test that all required workflow components exist and are importable."""
        # These should all import successfully
        try:
            from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
            from agentmap.services.interaction_handler_service import InteractionHandlerService  
            from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
            from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
            
            # If we get here, all imports succeeded
            self.assertTrue(True)
            
        except ImportError as e:
            self.fail(f"Required component could not be imported: {e}")


if __name__ == "__main__":
    unittest.main()
