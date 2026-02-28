"""
Unit tests for display_utils.py - Presentation Layer Display Utilities.

Tests pure display functions that format and present information to users.
"""

import unittest
from unittest.mock import patch

from agentmap.deployment.cli.display_utils import (
    display_error,
    display_interaction_request,
    display_resume_result,
    display_success,
)
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType


class TestDisplayInteractionRequest(unittest.TestCase):
    """Test display_interaction_request function."""

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_approval_request(self, mock_echo):
        """Test displaying an approval interaction request."""
        request = HumanInteractionRequest(
            node_name="approve_node",
            thread_id="thread_123",
            interaction_type=InteractionType.APPROVAL,
            prompt="Please approve the operation",
            timeout_seconds=300,
            context={"operation": "delete", "target": "old_data"},
        )

        display_interaction_request(request)

        # Verify key output elements
        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        # Check header
        self.assertIn("AGENT INTERACTION REQUIRED", full_output)

        # Check basic info
        self.assertIn("Node: approve_node", full_output)
        self.assertIn("Thread: thread_123", full_output)
        self.assertIn("Type: APPROVAL", full_output)
        self.assertIn("Timeout: 300 seconds", full_output)

        # Check prompt
        self.assertIn("Please approve the operation", full_output)

        # Check context
        self.assertIn("CONTEXT", full_output)
        self.assertIn("operation", full_output)

        # Check instructions
        self.assertIn("APPROVAL REQUIRED", full_output)
        self.assertIn("approve", full_output)
        self.assertIn("reject", full_output)

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_choice_request(self, mock_echo):
        """Test displaying a choice interaction request."""
        request = HumanInteractionRequest(
            node_name="choice_node",
            thread_id="thread_456",
            interaction_type=InteractionType.CHOICE,
            prompt="Choose an option",
            options=["Option A", "Option B", "Option C"],
        )

        display_interaction_request(request)

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        # Check type and options
        self.assertIn("Type: CHOICE", full_output)
        self.assertIn("CHOOSE AN OPTION", full_output)
        self.assertIn("1. Option A", full_output)
        self.assertIn("2. Option B", full_output)
        self.assertIn("3. Option C", full_output)

        # Check example
        self.assertIn("--action choose", full_output)

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_text_input_request(self, mock_echo):
        """Test displaying a text input interaction request."""
        request = HumanInteractionRequest(
            node_name="input_node",
            thread_id="thread_789",
            interaction_type=InteractionType.TEXT_INPUT,
            prompt="Enter your feedback",
        )

        display_interaction_request(request)

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        # Check type and instructions
        self.assertIn("Type: TEXT_INPUT", full_output)
        self.assertIn("TEXT INPUT REQUIRED", full_output)
        self.assertIn("submit", full_output)
        self.assertIn("text", full_output)

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_request_without_optional_fields(self, mock_echo):
        """Test displaying request without timeout or context."""
        request = HumanInteractionRequest(
            node_name="basic_node",
            thread_id="thread_000",
            interaction_type=InteractionType.CONVERSATION,
            prompt="Let's chat",
            # No timeout, no context, no options
        )

        display_interaction_request(request)

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        # Should not show timeout if not set
        self.assertNotIn("Timeout:", full_output)

        # Should still show basic info
        self.assertIn("Node: basic_node", full_output)
        self.assertIn("CONVERSATION", full_output)
        self.assertIn("reply", full_output)


class TestDisplayResumeResult(unittest.TestCase):
    """Test display_resume_result function."""

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_success_result(self, mock_echo):
        """Test displaying a successful resume result."""
        result = {
            "success": True,
            "outputs": {
                "completed": True,
                "result": "All done",
            },
            "execution_summary": {
                "nodes_executed": 5,
                "status": "completed",
            },
            "metadata": {
                "thread_id": "thread_123",
                "response_action": "approve",
                "graph_name": "test_graph",
                "duration": 10.5,
            },
        }

        display_resume_result(result)

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        # Check success header
        self.assertIn("WORKFLOW RESUMED SUCCESSFULLY", full_output)

        # Check metadata
        self.assertIn("Thread: thread_123", full_output)
        self.assertIn("Action: approve", full_output)
        self.assertIn("Graph: test_graph", full_output)
        self.assertIn("Duration: 10.50s", full_output)

        # Check execution summary
        self.assertIn("EXECUTION SUMMARY", full_output)
        self.assertIn("nodes_executed: 5", full_output)

        # Check outputs
        self.assertIn("FINAL OUTPUTS", full_output)
        self.assertIn("completed", full_output)

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_failure_result(self, mock_echo):
        """Test displaying a failed resume result."""
        result = {
            "success": False,
            "error": "Thread not found in storage",
            "metadata": {
                "resume_token": "invalid_token_123",
            },
        }

        display_resume_result(result)

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        # Check failure header
        self.assertIn("WORKFLOW RESUME FAILED", full_output)

        # Check error
        self.assertIn("Error: Thread not found", full_output)

        # Check metadata
        self.assertIn("Token: invalid_token_123", full_output)

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_minimal_result(self, mock_echo):
        """Test displaying a minimal result with few fields."""
        result = {
            "success": True,
            "outputs": {},
            "metadata": {"thread_id": "thread_999"},
        }

        display_resume_result(result)

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        # Should still show success
        self.assertIn("WORKFLOW RESUMED SUCCESSFULLY", full_output)
        self.assertIn("Thread: thread_999", full_output)


class TestDisplayMessages(unittest.TestCase):
    """Test display_error and display_success functions."""

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_error_default(self, mock_echo):
        """Test displaying an error with default type."""
        display_error("Something went wrong")

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        self.assertIn("ERROR", full_output)
        self.assertIn("Something went wrong", full_output)

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_error_custom_type(self, mock_echo):
        """Test displaying an error with custom type."""
        display_error("File not found", error_type="Warning")

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        self.assertIn("WARNING", full_output)
        self.assertIn("File not found", full_output)

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_success_default(self, mock_echo):
        """Test displaying a success message with default title."""
        display_success("Operation completed")

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        self.assertIn("SUCCESS", full_output)
        self.assertIn("Operation completed", full_output)

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_success_custom_title(self, mock_echo):
        """Test displaying a success message with custom title."""
        display_success("All tests passed", title="Tests Complete")

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        self.assertIn("TESTS COMPLETE", full_output)
        self.assertIn("All tests passed", full_output)


class TestDisplayContext(unittest.TestCase):
    """Test context display functionality."""

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_display_complex_context(self, mock_echo):
        """Test displaying complex context with nested structures."""
        request = HumanInteractionRequest(
            node_name="node",
            thread_id="thread",
            interaction_type=InteractionType.APPROVAL,
            prompt="Test",
            context={
                "simple_field": "value",
                "number": 42,
                "nested": {
                    "field1": "value1",
                    "field2": "value2",
                },
                "list": [1, 2, 3],
            },
        )

        display_interaction_request(request)

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        # Check context is displayed
        self.assertIn("CONTEXT", full_output)
        self.assertIn("simple_field: value", full_output)
        self.assertIn("number: 42", full_output)

        # Nested structures should be JSON formatted
        self.assertIn("field1", full_output)
        self.assertIn("field2", full_output)


class TestInteractionInstructions(unittest.TestCase):
    """Test interaction type specific instructions."""

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_edit_interaction_instructions(self, mock_echo):
        """Test EDIT interaction type instructions."""
        request = HumanInteractionRequest(
            node_name="edit_node",
            thread_id="thread",
            interaction_type=InteractionType.EDIT,
            prompt="Edit the document",
        )

        display_interaction_request(request)

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        self.assertIn("EDITING REQUIRED", full_output)
        self.assertIn("save", full_output)
        self.assertIn("cancel", full_output)
        self.assertIn("content", full_output)

    @patch("agentmap.deployment.cli.display_utils.typer.echo")
    def test_unknown_interaction_type_fallback(self, mock_echo):
        """Test fallback for unknown interaction types."""
        # Create a request with a type that doesn't have specific handling
        request = HumanInteractionRequest(
            node_name="unknown_node",
            thread_id="thread",
            interaction_type=InteractionType.APPROVAL,  # Will modify to test
            prompt="Do something",
        )

        # Simulate an unknown type by patching
        with patch.object(request, "interaction_type", None):
            display_interaction_request(request)

        calls_text = [str(call) for call in mock_echo.call_args_list]
        full_output = "\n".join(calls_text)

        # Should show generic fallback
        self.assertIn("INTERACTION REQUIRED", full_output)
        self.assertIn("continue", full_output)
        self.assertIn("cancel", full_output)


if __name__ == "__main__":
    unittest.main()
