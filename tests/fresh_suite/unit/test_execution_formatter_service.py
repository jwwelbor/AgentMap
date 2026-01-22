"""Test ExecutionFormatterService functionality."""

import unittest
from datetime import datetime, timedelta

from agentmap.services.execution_formatter_service import ExecutionFormatterService


class MockNodeExecution:
    """Mock node execution for testing."""

    def __init__(self, name, output, duration, success=True):
        self.node_name = name
        self.output = output
        self.duration = duration
        self.success = success
        self.error = None
        self.start_time = datetime.now() - timedelta(seconds=duration)
        self.end_time = datetime.now()


class MockExecutionSummary:
    """Mock execution summary for testing."""

    def __init__(self):
        self.graph_name = "test_graph"
        self.status = "completed"
        self.graph_success = True
        self.start_time = datetime.now() - timedelta(minutes=5)
        self.end_time = datetime.now()
        self.node_executions = [
            MockNodeExecution("UserInput", "test input", 2.5),
            MockNodeExecution("ProcessNode", {"result": "processed"}, 0.1),
            MockNodeExecution("EndNode", "completed", 0.01),
        ]


class TestExecutionFormatterService(unittest.TestCase):
    """Test ExecutionFormatterService."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter_service = ExecutionFormatterService()
        self.test_result = {
            "input": "test",
            "__next_node": "EndNode",
            "__policy_success": True,
            "__execution_summary": MockExecutionSummary(),
        }

    def test_basic_formatting(self):
        """Test basic formatting without verbose."""
        output = self.formatter_service.format_execution_result(
            self.test_result, verbose=False
        )

        # Check for key sections
        self.assertIn("GRAPH EXECUTION SUMMARY", output)
        self.assertIn("NODE EXECUTION ORDER", output)
        self.assertIn("FINAL STATE", output)

        # Check for graph info
        self.assertIn("Graph Name: test_graph", output)
        self.assertIn("Status: COMPLETED", output)
        self.assertIn("Success: ✅ Yes", output)

        # Check for node list
        self.assertIn("1. UserInput", output)
        self.assertIn("2. ProcessNode", output)
        self.assertIn("3. EndNode", output)

        # Check for timing info
        self.assertIn("2.5s ✅", output)  # UserInput duration

        # Check for hint
        self.assertIn("Use --pretty --verbose", output)

    def test_verbose_formatting(self):
        """Test verbose formatting."""
        output = self.formatter_service.format_execution_result(
            self.test_result, verbose=True
        )

        # Check for detailed node info
        self.assertIn("├─ Status:", output)
        self.assertIn("├─ Duration:", output)
        self.assertIn("├─ Time:", output)
        self.assertIn("└─ Output:", output)

        # Should not have the hint in verbose mode
        self.assertNotIn("Use --pretty --verbose", output)

    def test_simple_summary(self):
        """Test simple summary format."""
        summary = self.formatter_service.format_simple_summary(self.test_result)

        # Check for key elements
        self.assertIn("✅", summary)
        self.assertIn("test_graph", summary)
        self.assertIn("3 nodes", summary)
        self.assertIn("completed", summary)

    def test_missing_execution_summary(self):
        """Test handling of missing execution summary."""
        result_no_summary = {"input": "test", "__policy_success": True}
        output = self.formatter_service.format_execution_result(result_no_summary)

        # Should still have basic structure
        self.assertIn("GRAPH EXECUTION SUMMARY", output)
        self.assertIn("FINAL STATE", output)

        # Simple summary should handle missing data
        summary = self.formatter_service.format_simple_summary(result_no_summary)
        self.assertIn("no summary available", summary)

    def test_special_output_formatting(self):
        """Test special formatting for agent outputs."""
        # Create a test with special agent output
        special_result = self.test_result.copy()
        special_result["__execution_summary"] = MockExecutionSummary()
        special_result["__execution_summary"].node_executions = [
            MockNodeExecution(
                "AgentNode",
                {"processed": True, "agent_type": "test_agent", "node": "NextNode"},
                1.0,
            ),
        ]

        output = self.formatter_service.format_execution_result(
            special_result, verbose=True
        )

        # Check for special agent output formatting
        self.assertIn("[test_agent] → NextNode", output)


if __name__ == "__main__":
    unittest.main()
