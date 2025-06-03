"""
Unit tests for ExecutionSummary and NodeExecution domain models.

Tests focus on data storage and basic functionality only.
All business logic testing belongs in service tests.
"""

import unittest
from datetime import datetime
from agentmap.models import ExecutionSummary, NodeExecution


class TestNodeExecutionModel(unittest.TestCase):
    """Test the NodeExecution data container."""

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = datetime(2025, 6, 1, 10, 0, 0)
        self.end_time = datetime(2025, 6, 1, 10, 0, 5)

    def test_node_execution_creation_success(self):
        """Test creating a successful node execution record."""
        execution = NodeExecution(
            node_name="test_node",
            success=True,
            start_time=self.start_time,
            end_time=self.end_time,
            duration=5.0,
            output={"result": "completed"}
        )
        
        self.assertEqual(execution.node_name, "test_node")
        self.assertTrue(execution.success)
        self.assertEqual(execution.start_time, self.start_time)
        self.assertEqual(execution.end_time, self.end_time)
        self.assertEqual(execution.duration, 5.0)
        self.assertEqual(execution.output, {"result": "completed"})
        self.assertIsNone(execution.error)

    def test_node_execution_creation_failure(self):
        """Test creating a failed node execution record."""
        execution = NodeExecution(
            node_name="failing_node",
            success=False,
            start_time=self.start_time,
            end_time=self.end_time,
            duration=2.5,
            error="Node processing failed"
        )
        
        self.assertEqual(execution.node_name, "failing_node")
        self.assertFalse(execution.success)
        self.assertEqual(execution.duration, 2.5)
        self.assertEqual(execution.error, "Node processing failed")
        self.assertIsNone(execution.output)

    def test_node_execution_dataclass_equality(self):
        """Test that node executions with same data are equal."""
        execution1 = NodeExecution(
            node_name="test",
            success=True,
            start_time=self.start_time,
            end_time=self.end_time,
            duration=1.0
        )
        execution2 = NodeExecution(
            node_name="test",
            success=True,
            start_time=self.start_time,
            end_time=self.end_time,
            duration=1.0
        )
        
        self.assertEqual(execution1, execution2)


class TestExecutionSummaryModel(unittest.TestCase):
    """Test the ExecutionSummary data container."""

    def setUp(self):
        """Set up test fixtures."""
        self.start_time = datetime(2025, 6, 1, 10, 0, 0)
        self.end_time = datetime(2025, 6, 1, 10, 0, 10)

    def test_execution_summary_creation_minimal(self):
        """Test creating execution summary with minimal parameters."""
        summary = ExecutionSummary(graph_name="test_graph")
        
        self.assertEqual(summary.graph_name, "test_graph")
        self.assertIsNone(summary.start_time)
        self.assertIsNone(summary.end_time)
        self.assertEqual(summary.node_executions, [])
        self.assertIsNone(summary.final_output)
        self.assertEqual(summary.status, "pending")

    def test_execution_summary_creation_full(self):
        """Test creating execution summary with all parameters."""
        node_execution = NodeExecution(
            node_name="test_node",
            success=True,
            start_time=self.start_time,
            end_time=self.end_time,
            duration=5.0
        )
        
        summary = ExecutionSummary(
            graph_name="test_graph",
            start_time=self.start_time,
            end_time=self.end_time,
            node_executions=[node_execution],
            final_output={"completed": True},
            status="completed"
        )
        
        self.assertEqual(summary.graph_name, "test_graph")
        self.assertEqual(summary.start_time, self.start_time)
        self.assertEqual(summary.end_time, self.end_time)
        self.assertEqual(len(summary.node_executions), 1)
        self.assertEqual(summary.node_executions[0], node_execution)
        self.assertEqual(summary.final_output, {"completed": True})
        self.assertEqual(summary.status, "completed")

    def test_execution_summary_node_executions_list_is_mutable(self):
        """Test that node executions list can be modified."""
        summary = ExecutionSummary(graph_name="test_graph")
        node_execution = NodeExecution(
            node_name="test_node",
            success=True,
            start_time=self.start_time,
            end_time=self.end_time,
            duration=1.0
        )
        
        # Direct manipulation (would be done by ExecutionService)
        summary.node_executions.append(node_execution)
        
        self.assertEqual(len(summary.node_executions), 1)
        self.assertEqual(summary.node_executions[0], node_execution)

    def test_execution_summary_status_modification(self):
        """Test that status can be modified."""
        summary = ExecutionSummary(graph_name="test_graph")
        
        self.assertEqual(summary.status, "pending")
        
        summary.status = "running"
        self.assertEqual(summary.status, "running")
        
        summary.status = "completed"
        self.assertEqual(summary.status, "completed")

    def test_execution_summary_dataclass_equality(self):
        """Test that summaries with same data are equal."""
        summary1 = ExecutionSummary(
            graph_name="test",
            status="completed"
        )
        summary2 = ExecutionSummary(
            graph_name="test",
            status="completed"
        )
        
        self.assertEqual(summary1, summary2)

    def test_execution_summary_field_factory(self):
        """Test that each summary gets its own node executions list."""
        summary1 = ExecutionSummary(graph_name="graph1")
        summary2 = ExecutionSummary(graph_name="graph2")
        
        node_execution = NodeExecution(
            node_name="test",
            success=True,
            start_time=self.start_time,
            end_time=self.end_time,
            duration=1.0
        )
        
        summary1.node_executions.append(node_execution)
        
        self.assertEqual(len(summary1.node_executions), 1)
        self.assertEqual(len(summary2.node_executions), 0)


if __name__ == '__main__':
    unittest.main()
