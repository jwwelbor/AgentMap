"""
Simple unit test for ExecutionInterruptedException without external imports.

This test verifies the basic exception functionality works.
"""

import unittest
from typing import Dict, Any
from uuid import uuid4

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException, AgentError
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType


class TestExecutionInterruptedExceptionSimple(unittest.TestCase):
    """Test ExecutionInterruptedException basic functionality."""

    def test_exception_initialization(self):
        """Test exception initialization with all parameters."""
        # Arrange
        thread_id = "test_thread_123"
        interaction_request = HumanInteractionRequest(
            id=uuid4(),
            thread_id=thread_id,
            node_name="test_node",
            interaction_type=InteractionType.TEXT_INPUT,
            prompt="Please provide input"
        )
        checkpoint_data = {
            "inputs": {"input_key": "input_value"},
            "agent_context": {"context_key": "context_value"},
            "execution_tracker": "tracker_data",
            "node_name": "test_node"
        }
        
        # Act
        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data
        )
        
        # Assert
        self.assertEqual(exception.thread_id, thread_id)
        self.assertEqual(exception.interaction_request, interaction_request)
        self.assertEqual(exception.checkpoint_data, checkpoint_data)
        
        # Check message format
        expected_message = f"Execution interrupted for human interaction in thread: {thread_id}"
        self.assertEqual(str(exception), expected_message)

    def test_exception_inheritance(self):
        """Test exception inheritance hierarchy."""
        # Arrange
        thread_id = "test_thread"
        interaction_request = HumanInteractionRequest(
            thread_id=thread_id,
            node_name="test_node",
            interaction_type=InteractionType.TEXT_INPUT,
            prompt="Test prompt"
        )
        checkpoint_data = {"test": "data"}
        
        # Act
        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data
        )
        
        # Assert
        self.assertIsInstance(exception, ExecutionInterruptedException)
        self.assertIsInstance(exception, AgentError)
        self.assertIsInstance(exception, Exception)


if __name__ == "__main__":
    unittest.main()
