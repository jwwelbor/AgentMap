"""
Unit tests for workflow_ops.py resume_workflow() - Runtime API Layer.

Tests the public runtime API resume_workflow() function and _parse_resume_token helper.
"""

import json
import unittest
from unittest.mock import MagicMock, Mock, patch

from agentmap.exceptions.runtime_exceptions import InvalidInputs
from agentmap.models.execution.result import ExecutionResult
from agentmap.runtime.workflow_ops import _parse_resume_token, resume_workflow


class TestResumeWorkflowRuntimeAPI(unittest.TestCase):
    """Test resume_workflow() public runtime API function."""

    def setUp(self):
        """Set up test fixtures."""
        self.thread_id = "test_thread_123"
        self.response_action = "approve"
        self.response_data = {"reason": "looks good"}

    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch(
        "agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService"
    )
    def test_resume_workflow_success_with_json_token(
        self, mock_orchestration_service, mock_ensure_init
    ):
        """Test successful resume with JSON format resume token."""
        # Setup mock result from orchestration service
        mock_result = ExecutionResult(
            graph_name="test_graph",
            final_state={"completed": True, "result": "done"},
            execution_summary="Workflow resumed and completed",
            success=True,
            total_duration=10.5,
        )
        mock_orchestration_service.resume_workflow.return_value = mock_result

        # Create JSON resume token
        resume_token = json.dumps(
            {
                "thread_id": self.thread_id,
                "response_action": self.response_action,
                "response_data": self.response_data,
            }
        )

        # Execute
        result = resume_workflow(resume_token, profile="dev")

        # Verify initialization
        mock_ensure_init.assert_called_once_with(config_file=None)

        # Verify orchestration service was called correctly
        mock_orchestration_service.resume_workflow.assert_called_once_with(
            thread_id=self.thread_id,
            response_action=self.response_action,
            response_data=self.response_data,
            config_file=None,
        )

        # Verify result format
        self.assertTrue(result["success"])
        self.assertEqual(result["outputs"], {"completed": True, "result": "done"})
        self.assertEqual(result["execution_summary"], "Workflow resumed and completed")
        self.assertEqual(result["metadata"]["thread_id"], self.thread_id)
        self.assertEqual(result["metadata"]["response_action"], self.response_action)
        self.assertEqual(result["metadata"]["profile"], "dev")
        self.assertEqual(result["metadata"]["graph_name"], "test_graph")
        self.assertEqual(result["metadata"]["duration"], 10.5)

    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch(
        "agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService"
    )
    def test_resume_workflow_success_with_plain_thread_id(
        self, mock_orchestration_service, mock_ensure_init
    ):
        """Test successful resume with plain thread_id string as token."""
        # Setup mock result
        mock_result = ExecutionResult(
            graph_name="test_graph",
            final_state={"status": "completed"},
            execution_summary="Resumed",
            success=True,
            total_duration=5.0,
        )
        mock_orchestration_service.resume_workflow.return_value = mock_result

        # Use plain thread_id as token
        resume_token = self.thread_id

        # Execute
        result = resume_workflow(resume_token)

        # Verify orchestration service was called with defaults
        mock_orchestration_service.resume_workflow.assert_called_once_with(
            thread_id=self.thread_id,
            response_action="continue",  # Default action
            response_data=None,  # No data
            config_file=None,
        )

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["outputs"], {"status": "completed"})

    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch(
        "agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService"
    )
    def test_resume_workflow_with_config_file(
        self, mock_orchestration_service, mock_ensure_init
    ):
        """Test resume workflow with custom config file."""
        # Setup mock result
        mock_result = ExecutionResult(
            graph_name="test_graph",
            final_state={},
            execution_summary="Done",
            success=True,
            total_duration=1.0,
        )
        mock_orchestration_service.resume_workflow.return_value = mock_result

        resume_token = json.dumps({"thread_id": self.thread_id})
        config_file = "custom_config.yaml"

        # Execute
        result = resume_workflow(resume_token, config_file=config_file)

        # Verify initialization with config
        mock_ensure_init.assert_called_once_with(config_file=config_file)

        # Verify orchestration service received config
        mock_orchestration_service.resume_workflow.assert_called_once_with(
            thread_id=self.thread_id,
            response_action="continue",
            response_data=None,
            config_file=config_file,
        )

    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch(
        "agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService"
    )
    def test_resume_workflow_error_handling(
        self, mock_orchestration_service, mock_ensure_init
    ):
        """Test error handling in resume workflow."""
        # Orchestration service raises exception
        mock_orchestration_service.resume_workflow.side_effect = RuntimeError(
            "Failed to load thread data"
        )

        resume_token = json.dumps({"thread_id": self.thread_id})

        # Execute
        result = resume_workflow(resume_token)

        # Verify error response format
        self.assertFalse(result["success"])
        self.assertIn("Failed to load thread data", result["error"])
        self.assertEqual(result["metadata"]["resume_token"], resume_token)
        self.assertIsNone(result["metadata"]["profile"])

    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    def test_resume_workflow_invalid_token_format(self, mock_ensure_init):
        """Test resume workflow with invalid token format."""
        # Invalid JSON
        resume_token = "{invalid json"

        # Execute
        result = resume_workflow(resume_token)

        # Should treat as plain thread_id and succeed/fail based on that
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch(
        "agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService"
    )
    def test_resume_workflow_backward_compatibility(
        self, mock_orchestration_service, mock_ensure_init
    ):
        """Test backward compatibility with existing token formats."""
        # Setup mock result
        mock_result = ExecutionResult(
            graph_name="test_graph",
            final_state={"done": True},
            execution_summary="Complete",
            success=True,
            total_duration=1.0,
        )
        mock_orchestration_service.resume_workflow.return_value = mock_result

        # Old format: just thread_id with action in separate field
        resume_token = json.dumps(
            {
                "thread_id": self.thread_id,
                "action": "approve",  # Old field name
                "data": {"old": "format"},
            }
        )

        # Execute - should still work
        result = resume_workflow(resume_token)

        # Verify it processed correctly
        self.assertTrue(result["success"])

        # Check what was passed to orchestration service
        call_args = mock_orchestration_service.resume_workflow.call_args
        # Should use default "continue" since response_action not found
        self.assertEqual(call_args.kwargs["response_action"], "continue")


class TestParseResumeToken(unittest.TestCase):
    """Test _parse_resume_token helper function."""

    def test_parse_json_token_complete(self):
        """Test parsing complete JSON token with all fields."""
        token = json.dumps(
            {
                "thread_id": "thread_123",
                "response_action": "approve",
                "response_data": {"reason": "ok"},
            }
        )

        thread_id, action, data = _parse_resume_token(token)

        self.assertEqual(thread_id, "thread_123")
        self.assertEqual(action, "approve")
        self.assertEqual(data, {"reason": "ok"})

    def test_parse_json_token_minimal(self):
        """Test parsing JSON token with only thread_id."""
        token = json.dumps({"thread_id": "thread_456"})

        thread_id, action, data = _parse_resume_token(token)

        self.assertEqual(thread_id, "thread_456")
        self.assertEqual(action, "continue")  # Default action
        self.assertIsNone(data)

    def test_parse_plain_string_token(self):
        """Test parsing plain string as thread_id."""
        token = "simple_thread_id"

        thread_id, action, data = _parse_resume_token(token)

        self.assertEqual(thread_id, "simple_thread_id")
        self.assertEqual(action, "continue")
        self.assertIsNone(data)

    def test_parse_invalid_json_treated_as_string(self):
        """Test invalid JSON is treated as plain thread_id string."""
        token = "{not valid json"

        thread_id, action, data = _parse_resume_token(token)

        self.assertEqual(thread_id, "{not valid json")
        self.assertEqual(action, "continue")
        self.assertIsNone(data)

    def test_parse_empty_thread_id_raises_error(self):
        """Test empty thread_id raises InvalidInputs."""
        token = json.dumps({"response_action": "approve"})

        with self.assertRaises(InvalidInputs) as context:
            _parse_resume_token(token)

        self.assertIn("valid thread_id", str(context.exception))

    def test_parse_non_string_token_raises_error(self):
        """Test non-string token raises InvalidInputs."""
        token = {"dict": "not_string"}

        with self.assertRaises(InvalidInputs) as context:
            _parse_resume_token(token)

        self.assertIn("must be a string", str(context.exception))

    def test_parse_token_with_null_thread_id(self):
        """Test token with null thread_id raises error."""
        token = json.dumps({"thread_id": None})

        with self.assertRaises(InvalidInputs) as context:
            _parse_resume_token(token)

        self.assertIn("valid thread_id", str(context.exception))

    def test_parse_token_preserves_complex_data(self):
        """Test parsing preserves complex response data structures."""
        complex_data = {
            "nested": {
                "field": "value",
                "list": [1, 2, 3],
            },
            "flag": True,
            "count": 42,
        }

        token = json.dumps(
            {
                "thread_id": "complex_thread",
                "response_action": "submit",
                "response_data": complex_data,
            }
        )

        thread_id, action, data = _parse_resume_token(token)

        self.assertEqual(thread_id, "complex_thread")
        self.assertEqual(action, "submit")
        self.assertEqual(data, complex_data)

    def test_parse_token_with_defaults(self):
        """Test default values are applied correctly."""
        # Token with thread_id but missing action
        token = json.dumps(
            {
                "thread_id": "test",
                "response_data": {"some": "data"},
            }
        )

        thread_id, action, data = _parse_resume_token(token)

        self.assertEqual(thread_id, "test")
        self.assertEqual(action, "continue")  # Default
        self.assertEqual(data, {"some": "data"})  # Preserved


class TestResumeWorkflowIntegrationPoints(unittest.TestCase):
    """Test integration points of resume_workflow with other systems."""

    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch(
        "agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService"
    )
    def test_resume_with_different_response_actions(
        self, mock_orchestration_service, mock_ensure_init
    ):
        """Test resume workflow handles different response action types."""
        # Setup mock
        mock_result = ExecutionResult(
            graph_name="test",
            final_state={},
            execution_summary="Done",
            success=True,
            total_duration=1.0,
        )
        mock_orchestration_service.resume_workflow.return_value = mock_result

        # Test different action types
        actions = ["approve", "reject", "choose", "text_input", "continue", "cancel"]

        for action in actions:
            with self.subTest(action=action):
                token = json.dumps(
                    {
                        "thread_id": "thread_test",
                        "response_action": action,
                    }
                )

                result = resume_workflow(token)

                self.assertTrue(result["success"])

                # Verify correct action was passed
                call_args = mock_orchestration_service.resume_workflow.call_args
                self.assertEqual(call_args.kwargs["response_action"], action)

    @patch("agentmap.runtime.workflow_ops.ensure_initialized")
    @patch(
        "agentmap.services.workflow_orchestration_service.WorkflowOrchestrationService"
    )
    def test_resume_metadata_preservation(
        self, mock_orchestration_service, mock_ensure_init
    ):
        """Test that ExecutionResult metadata is preserved in response."""
        # Create result with full metadata
        mock_result = ExecutionResult(
            graph_name="metadata_test",
            final_state={"key": "value", "execution_id": "exec_123"},
            execution_summary="Test summary with details",
            success=True,
            total_duration=15.75,
        )
        mock_orchestration_service.resume_workflow.return_value = mock_result

        token = json.dumps({"thread_id": "meta_thread"})

        result = resume_workflow(token, profile="staging")

        # Verify all metadata is preserved
        self.assertEqual(result["execution_summary"], "Test summary with details")
        self.assertEqual(result["metadata"]["graph_name"], "metadata_test")
        self.assertEqual(result["metadata"]["duration"], 15.75)
        self.assertEqual(result["metadata"]["profile"], "staging")

        # ExecutionResult fields are preserved
        self.assertIn("execution_id", result["outputs"])


if __name__ == "__main__":
    unittest.main()
