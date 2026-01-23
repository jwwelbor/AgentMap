"""
Unit tests for ExecutionInterruptedException.

Tests the exception structure and data preservation for graph execution interruptions.
"""

import unittest
from typing import Any, Dict
from uuid import uuid4

from agentmap.exceptions.agent_exceptions import (
    AgentError,
    ExecutionInterruptedException,
)
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType


class TestExecutionInterruptedException(unittest.TestCase):
    """Test ExecutionInterruptedException functionality."""

    def _create_test_interaction_request(
        self, thread_id: str = "test_thread", node_name: str = "test_node"
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
            timeout_seconds=300,
        )

    def _create_test_checkpoint_data(self) -> Dict[str, Any]:
        """Create test checkpoint data."""
        return {
            "inputs": {"input_key": "input_value"},
            "agent_context": {"context_key": "context_value"},
            "execution_tracker": "tracker_data",
            "node_name": "test_node",
            "state": {"current": "processing"},
        }

    def test_exception_initialization(self):
        """Test exception initialization with all parameters."""
        # Arrange
        thread_id = "test_thread_123"
        interaction_request = self._create_test_interaction_request(thread_id)
        checkpoint_data = self._create_test_checkpoint_data()

        # Act
        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

        # Assert
        self.assertEqual(exception.thread_id, thread_id)
        self.assertEqual(exception.interaction_request, interaction_request)
        self.assertEqual(exception.checkpoint_data, checkpoint_data)

        # Check message format
        expected_message = (
            f"Execution interrupted for human interaction in thread: {thread_id}"
        )
        self.assertEqual(str(exception), expected_message)

    def test_exception_inheritance(self):
        """Test exception inheritance hierarchy."""
        # Arrange
        thread_id = "test_thread"
        interaction_request = self._create_test_interaction_request()
        checkpoint_data = self._create_test_checkpoint_data()

        # Act
        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

        # Assert
        self.assertIsInstance(exception, ExecutionInterruptedException)
        self.assertIsInstance(exception, AgentError)
        self.assertIsInstance(exception, Exception)

    def test_exception_data_preservation(self):
        """Test that exception preserves all data correctly."""
        # Arrange
        thread_id = "complex_thread_456"
        interaction_request = self._create_test_interaction_request(
            thread_id, "complex_node"
        )

        complex_checkpoint_data = {
            "inputs": {
                "user_input": "complex input data",
                "parameters": {"param1": "value1", "param2": 42},
            },
            "agent_context": {
                "execution_id": "exec_789",
                "previous_nodes": ["node1", "node2"],
                "metadata": {"created_at": "2023-01-01T10:00:00"},
            },
            "execution_tracker": {
                "node_count": 5,
                "current_node": "complex_node",
                "execution_path": ["start", "process", "complex_node"],
            },
            "node_name": "complex_node",
            "state": {
                "current_processing": True,
                "data_buffer": ["item1", "item2", "item3"],
                "settings": {"timeout": 300, "retry_count": 3},
            },
        }

        # Act
        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=complex_checkpoint_data,
        )

        # Assert - Check thread ID
        self.assertEqual(exception.thread_id, thread_id)

        # Assert - Check interaction request preservation
        self.assertEqual(exception.interaction_request.thread_id, thread_id)
        self.assertEqual(exception.interaction_request.node_name, "complex_node")
        self.assertEqual(exception.interaction_request.prompt, "Please provide input")

        # Assert - Check checkpoint data preservation (deep nested structure)
        checkpoint = exception.checkpoint_data
        self.assertEqual(checkpoint["inputs"]["user_input"], "complex input data")
        self.assertEqual(checkpoint["inputs"]["parameters"]["param1"], "value1")
        self.assertEqual(checkpoint["inputs"]["parameters"]["param2"], 42)

        self.assertEqual(checkpoint["agent_context"]["execution_id"], "exec_789")
        self.assertEqual(
            checkpoint["agent_context"]["previous_nodes"], ["node1", "node2"]
        )

        self.assertEqual(checkpoint["execution_tracker"]["node_count"], 5)
        self.assertEqual(
            checkpoint["execution_tracker"]["execution_path"],
            ["start", "process", "complex_node"],
        )

        self.assertEqual(
            checkpoint["state"]["data_buffer"], ["item1", "item2", "item3"]
        )
        self.assertEqual(checkpoint["state"]["settings"]["timeout"], 300)

    def test_exception_with_minimal_data(self):
        """Test exception with minimal required data."""
        # Arrange
        thread_id = "minimal_thread"
        interaction_request = HumanInteractionRequest(
            thread_id=thread_id,
            node_name="minimal_node",
            interaction_type=InteractionType.APPROVAL,
            prompt="Approve action",
        )
        checkpoint_data = {}  # Empty checkpoint data

        # Act
        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

        # Assert
        self.assertEqual(exception.thread_id, thread_id)
        self.assertEqual(exception.interaction_request.node_name, "minimal_node")
        self.assertEqual(
            exception.interaction_request.interaction_type, InteractionType.APPROVAL
        )
        self.assertEqual(exception.checkpoint_data, {})

    def test_exception_message_format(self):
        """Test exception message formatting with different thread IDs."""
        test_cases = [
            (
                "simple_thread",
                "Execution interrupted for human interaction in thread: simple_thread",
            ),
            (
                "thread_with_numbers_123",
                "Execution interrupted for human interaction in thread: thread_with_numbers_123",
            ),
            (
                "thread-with-dashes",
                "Execution interrupted for human interaction in thread: thread-with-dashes",
            ),
            (
                "thread_with_underscores_and_numbers_456",
                "Execution interrupted for human interaction in thread: thread_with_underscores_and_numbers_456",
            ),
        ]

        for thread_id, expected_message in test_cases:
            with self.subTest(thread_id=thread_id):
                # Arrange
                interaction_request = self._create_test_interaction_request(thread_id)
                checkpoint_data = self._create_test_checkpoint_data()

                # Act
                exception = ExecutionInterruptedException(
                    thread_id=thread_id,
                    interaction_request=interaction_request,
                    checkpoint_data=checkpoint_data,
                )

                # Assert
                self.assertEqual(str(exception), expected_message)

    def test_exception_attribute_access(self):
        """Test direct attribute access on exception."""
        # Arrange
        thread_id = "access_test_thread"
        interaction_request = self._create_test_interaction_request(thread_id)
        checkpoint_data = {"test_key": "test_value", "nested": {"inner": "data"}}

        # Act
        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

        # Assert - Direct attribute access should work
        self.assertEqual(exception.thread_id, thread_id)

        # Assert - Should be able to access nested interaction request data
        self.assertEqual(exception.interaction_request.thread_id, thread_id)
        self.assertEqual(
            exception.interaction_request.interaction_type, InteractionType.TEXT_INPUT
        )

        # Assert - Should be able to access nested checkpoint data
        self.assertEqual(exception.checkpoint_data["test_key"], "test_value")
        self.assertEqual(exception.checkpoint_data["nested"]["inner"], "data")

    def test_exception_serialization_compatibility(self):
        """Test that exception data is serialization-friendly."""
        # Arrange
        thread_id = "serialization_test"
        interaction_request = self._create_test_interaction_request(thread_id)

        # Create checkpoint data with various Python types
        checkpoint_data = {
            "string_value": "test_string",
            "int_value": 42,
            "float_value": 3.14,
            "bool_value": True,
            "none_value": None,
            "list_value": [1, 2, 3],
            "dict_value": {"nested": "data"},
        }

        # Act
        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

        # Assert - All data should be accessible and of correct types
        self.assertIsInstance(exception.thread_id, str)
        self.assertIsInstance(exception.checkpoint_data["string_value"], str)
        self.assertIsInstance(exception.checkpoint_data["int_value"], int)
        self.assertIsInstance(exception.checkpoint_data["float_value"], float)
        self.assertIsInstance(exception.checkpoint_data["bool_value"], bool)
        self.assertIsNone(exception.checkpoint_data["none_value"])
        self.assertIsInstance(exception.checkpoint_data["list_value"], list)
        self.assertIsInstance(exception.checkpoint_data["dict_value"], dict)

    def test_exception_raising_and_catching(self):
        """Test that exception can be raised and caught properly."""
        # Arrange
        thread_id = "raise_test_thread"
        interaction_request = self._create_test_interaction_request(thread_id)
        checkpoint_data = {"test": "data"}

        def raise_exception():
            raise ExecutionInterruptedException(
                thread_id=thread_id,
                interaction_request=interaction_request,
                checkpoint_data=checkpoint_data,
            )

        # Act & Assert - Should be catchable as specific exception type
        with self.assertRaises(ExecutionInterruptedException) as context:
            raise_exception()

        caught_exception = context.exception
        self.assertEqual(caught_exception.thread_id, thread_id)
        self.assertEqual(caught_exception.interaction_request, interaction_request)
        self.assertEqual(caught_exception.checkpoint_data, checkpoint_data)

        # Act & Assert - Should also be catchable as base exception type
        with self.assertRaises(AgentError):
            raise_exception()

        with self.assertRaises(Exception):
            raise_exception()

    def test_multiple_exception_instances(self):
        """Test creating multiple exception instances doesn't interfere."""
        # Arrange & Act
        exception1 = ExecutionInterruptedException(
            thread_id="thread_1",
            interaction_request=self._create_test_interaction_request("thread_1"),
            checkpoint_data={"data": "first"},
        )

        exception2 = ExecutionInterruptedException(
            thread_id="thread_2",
            interaction_request=self._create_test_interaction_request("thread_2"),
            checkpoint_data={"data": "second"},
        )

        # Assert - Instances should be independent
        self.assertEqual(exception1.thread_id, "thread_1")
        self.assertEqual(exception2.thread_id, "thread_2")
        self.assertEqual(exception1.checkpoint_data["data"], "first")
        self.assertEqual(exception2.checkpoint_data["data"], "second")

        # Modifying one should not affect the other
        exception1.checkpoint_data["modified"] = True
        self.assertNotIn("modified", exception2.checkpoint_data)


if __name__ == "__main__":
    unittest.main()
