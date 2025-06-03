"""
Unit tests for ExecutionResult domain model.

Tests focus on data storage and basic functionality only.
All business logic testing belongs in service tests.
"""

import unittest
from datetime import datetime
from agentmap.models import ExecutionResult, ExecutionSummary, NodeExecution


class TestExecutionResultModel(unittest.TestCase):
    """Test the ExecutionResult data container."""

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = datetime(2025, 6, 1, 10, 0, 0)
        self.end_time = datetime(2025, 6, 1, 10, 0, 10)
        self.node_execution = NodeExecution(
            node_name="test_node",
            success=True,
            start_time=self.start_time,
            end_time=datetime(2025, 6, 1, 10, 0, 5),
            duration=5.0,
            output={"result": "completed"}
        )
        self.execution_summary = ExecutionSummary(
            graph_name="test_graph",
            start_time=self.start_time,
            end_time=self.end_time,
            node_executions=[self.node_execution],
            final_output={"completed": True},
            status="completed"
        )

    def test_execution_result_creation_success(self):
        """Test creating a successful execution result."""
        result = ExecutionResult(
            graph_name="test_graph",
            final_state={"output": "success", "status": "completed"},
            execution_summary=self.execution_summary,
            success=True,
            total_duration=10.5,
            compiled_from="precompiled"
        )
        
        self.assertEqual(result.graph_name, "test_graph")
        self.assertEqual(result.final_state, {"output": "success", "status": "completed"})
        self.assertEqual(result.execution_summary, self.execution_summary)
        self.assertTrue(result.success)
        self.assertEqual(result.total_duration, 10.5)
        self.assertEqual(result.compiled_from, "precompiled")
        self.assertIsNone(result.error)

    def test_execution_result_creation_failure(self):
        """Test creating a failed execution result."""
        failed_summary = ExecutionSummary(
            graph_name="failing_graph",
            start_time=self.start_time,
            end_time=self.end_time,
            status="failed"
        )
        
        result = ExecutionResult(
            graph_name="failing_graph",
            final_state={},
            execution_summary=failed_summary,
            success=False,
            total_duration=5.2,
            compiled_from="memory",
            error="Graph execution failed: Node timeout"
        )
        
        self.assertEqual(result.graph_name, "failing_graph")
        self.assertEqual(result.final_state, {})
        self.assertEqual(result.execution_summary, failed_summary)
        self.assertFalse(result.success)
        self.assertEqual(result.total_duration, 5.2)
        self.assertEqual(result.compiled_from, "memory")
        self.assertEqual(result.error, "Graph execution failed: Node timeout")

    def test_execution_result_compiled_from_values(self):
        """Test different compiled_from values."""
        test_cases = ["precompiled", "autocompiled", "memory"]
        
        for compiled_from in test_cases:
            with self.subTest(compiled_from=compiled_from):
                result = ExecutionResult(
                    graph_name="test_graph",
                    final_state={},
                    execution_summary=self.execution_summary,
                    success=True,
                    total_duration=1.0,
                    compiled_from=compiled_from
                )
                
                self.assertEqual(result.compiled_from, compiled_from)

    def test_execution_result_execution_summary_integration(self):
        """Test integration with ExecutionSummary model."""
        result = ExecutionResult(
            graph_name="test_graph",
            final_state={"output": "completed"},
            execution_summary=self.execution_summary,
            success=True,
            total_duration=10.0,
            compiled_from="autocompiled"
        )
        
        # Verify ExecutionSummary is properly integrated
        self.assertIsInstance(result.execution_summary, ExecutionSummary)
        self.assertEqual(result.execution_summary.graph_name, "test_graph")
        self.assertEqual(result.execution_summary.status, "completed")
        self.assertEqual(len(result.execution_summary.node_executions), 1)
        self.assertEqual(result.execution_summary.node_executions[0], self.node_execution)

    def test_execution_result_dataclass_equality(self):
        """Test that execution results with same data are equal."""
        result1 = ExecutionResult(
            graph_name="test",
            final_state={"data": "value"},
            execution_summary=self.execution_summary,
            success=True,
            total_duration=5.0,
            compiled_from="precompiled"
        )
        result2 = ExecutionResult(
            graph_name="test",
            final_state={"data": "value"},
            execution_summary=self.execution_summary,
            success=True,
            total_duration=5.0,
            compiled_from="precompiled"
        )
        
        self.assertEqual(result1, result2)

    def test_execution_result_dataclass_inequality(self):
        """Test that execution results with different data are not equal."""
        result1 = ExecutionResult(
            graph_name="test1",
            final_state={},
            execution_summary=self.execution_summary,
            success=True,
            total_duration=5.0,
            compiled_from="precompiled"
        )
        result2 = ExecutionResult(
            graph_name="test2",
            final_state={},
            execution_summary=self.execution_summary,
            success=True,
            total_duration=5.0,
            compiled_from="precompiled"
        )
        
        self.assertNotEqual(result1, result2)

    def test_execution_result_final_state_types(self):
        """Test that final_state can hold various data types."""
        test_states = [
            {},
            {"simple": "value"},
            {"nested": {"data": {"value": 123}}},
            {"list": [1, 2, 3]},
            {"mixed": {"str": "value", "num": 42, "bool": True}}
        ]
        
        for final_state in test_states:
            with self.subTest(final_state=final_state):
                result = ExecutionResult(
                    graph_name="test_graph",
                    final_state=final_state,
                    execution_summary=self.execution_summary,
                    success=True,
                    total_duration=1.0,
                    compiled_from="memory"
                )
                
                self.assertEqual(result.final_state, final_state)

    def test_execution_result_duration_precision(self):
        """Test that duration values are preserved with precision."""
        durations = [0.0, 0.001, 1.5, 10.123456, 3600.999]
        
        for duration in durations:
            with self.subTest(duration=duration):
                result = ExecutionResult(
                    graph_name="test_graph",
                    final_state={},
                    execution_summary=self.execution_summary,
                    success=True,
                    total_duration=duration,
                    compiled_from="precompiled"
                )
                
                self.assertEqual(result.total_duration, duration)

    def test_execution_result_optional_error_field(self):
        """Test that error field is optional and defaults to None."""
        result = ExecutionResult(
            graph_name="test_graph",
            final_state={},
            execution_summary=self.execution_summary,
            success=True,
            total_duration=1.0,
            compiled_from="precompiled"
        )
        
        self.assertIsNone(result.error)

    def test_execution_result_error_field_when_provided(self):
        """Test that error field holds error message when provided."""
        error_message = "Detailed error information here"
        result = ExecutionResult(
            graph_name="test_graph",
            final_state={},
            execution_summary=self.execution_summary,
            success=False,
            total_duration=1.0,
            compiled_from="memory",
            error=error_message
        )
        
        self.assertEqual(result.error, error_message)

    def test_execution_result_success_failure_consistency(self):
        """Test that success/failure states are consistent with error field."""
        # Success case - no error
        success_result = ExecutionResult(
            graph_name="success_graph",
            final_state={"result": "completed"},
            execution_summary=self.execution_summary,
            success=True,
            total_duration=5.0,
            compiled_from="precompiled"
        )
        
        self.assertTrue(success_result.success)
        self.assertIsNone(success_result.error)
        
        # Failure case - with error
        failure_result = ExecutionResult(
            graph_name="failure_graph",
            final_state={},
            execution_summary=self.execution_summary,
            success=False,
            total_duration=2.0,
            compiled_from="memory",
            error="Something went wrong"
        )
        
        self.assertFalse(failure_result.success)
        self.assertEqual(failure_result.error, "Something went wrong")


if __name__ == '__main__':
    unittest.main()
