"""
Unit tests for AgentMap Domain Models as Pure Data Containers.

These tests validate that domain models are pure data containers following
the established architecture principle that models contain no business logic,
only data storage and access functionality.

IMPORTANT: These tests focus ONLY on data container functionality.
NO business logic testing - that belongs in service tests.
"""
import unittest
from datetime import datetime, timedelta
from typing import Dict, Any

from agentmap.models.graph import Graph
from agentmap.models.node import Node
from agentmap.models.execution.tracker import ExecutionTracker, NodeExecution as TrackerNodeExecution
from agentmap.models.execution.summary import ExecutionSummary, NodeExecution as SummaryNodeExecution
from agentmap.models.execution.result import ExecutionResult


class TestGraphDataContainer(unittest.TestCase):
    """Test Graph model as pure data container."""
    
    def test_graph_initialization_with_required_fields(self):
        """Test Graph initialization with required fields only."""
        # Act
        graph = Graph(name="test_graph")
        
        # Assert
        self.assertEqual(graph.name, "test_graph")
        self.assertIsNone(graph.entry_point)
        self.assertEqual(graph.nodes, {})
        self.assertIsInstance(graph.nodes, dict)
    
    def test_graph_initialization_with_all_fields(self):
        """Test Graph initialization with all fields provided."""
        # Arrange
        test_nodes = {"node1": Node("node1"), "node2": Node("node2")}
        
        # Act
        graph = Graph(
            name="full_graph",
            entry_point="start_node",
            nodes=test_nodes
        )
        
        # Assert
        self.assertEqual(graph.name, "full_graph")
        self.assertEqual(graph.entry_point, "start_node")
        self.assertEqual(graph.nodes, test_nodes)
        self.assertEqual(len(graph.nodes), 2)
    
    def test_graph_nodes_default_factory(self):
        """Test that nodes dict uses default factory correctly."""
        # Act
        graph1 = Graph(name="graph1")
        graph2 = Graph(name="graph2")
        
        # Assert - Each instance should have its own nodes dict
        self.assertIsNot(graph1.nodes, graph2.nodes)
        
        # Modify one and verify the other is unchanged
        graph1.nodes["test"] = Node("test")
        self.assertNotIn("test", graph2.nodes)
    
    def test_graph_data_storage_and_retrieval(self):
        """Test basic data storage and retrieval in Graph model."""
        # Arrange
        graph = Graph(name="storage_test")
        node = Node("test_node")
        
        # Act - Store data
        graph.entry_point = "new_entry"
        graph.nodes["test_node"] = node
        
        # Assert - Retrieve data
        self.assertEqual(graph.entry_point, "new_entry")
        self.assertIn("test_node", graph.nodes)
        self.assertIs(graph.nodes["test_node"], node)
    
    def test_graph_name_modification(self):
        """Test that graph name can be modified (data container behavior)."""
        # Arrange
        graph = Graph(name="original")
        
        # Act
        graph.name = "modified"
        
        # Assert
        self.assertEqual(graph.name, "modified")


class TestNodeDataContainer(unittest.TestCase):
    """Test Node model as pure data container."""
    
    def test_node_initialization_minimal(self):
        """Test Node initialization with minimal required data."""
        # Act
        node = Node(name="test_node")
        
        # Assert
        self.assertEqual(node.name, "test_node")
        self.assertIsNone(node.context)
        self.assertIsNone(node.agent_type)
        self.assertEqual(node.inputs, [])
        self.assertIsNone(node.output)
        self.assertIsNone(node.prompt)
        self.assertIsNone(node.description)
        self.assertEqual(node.edges, {})
        self.assertIsInstance(node.edges, dict)
    
    def test_node_initialization_with_all_properties(self):
        """Test Node initialization with all properties provided."""
        # Arrange
        context = {"key": "value", "config": {"nested": True}}
        inputs = ["input1", "input2"]
        
        # Act
        node = Node(
            name="full_node",
            context=context,
            agent_type="llm_agent",
            inputs=inputs,
            output="result",
            prompt="Test prompt",
            description="A test node"
        )
        
        # Assert
        self.assertEqual(node.name, "full_node")
        self.assertEqual(node.context, context)
        self.assertEqual(node.agent_type, "llm_agent")
        self.assertEqual(node.inputs, inputs)
        self.assertEqual(node.output, "result")
        self.assertEqual(node.prompt, "Test prompt")
        self.assertEqual(node.description, "A test node")
        self.assertEqual(node.edges, {})
    
    def test_node_inputs_default_list(self):
        """Test that inputs defaults to empty list, not None."""
        # Act
        node = Node("test")
        
        # Assert
        self.assertEqual(node.inputs, [])
        self.assertIsInstance(node.inputs, list)
        
        # Test that different instances get different lists
        node2 = Node("test2")
        self.assertIsNot(node.inputs, node2.inputs)
    
    def test_node_add_edge_simple_data_storage(self):
        """Test add_edge() as simple data storage method."""
        # Arrange
        node = Node("test_node")
        
        # Act - Store edge data
        node.add_edge("success", "next_node")
        node.add_edge("failure", "error_node")
        
        # Assert - Verify data storage
        self.assertEqual(node.edges["success"], "next_node")
        self.assertEqual(node.edges["failure"], "error_node")
        self.assertEqual(len(node.edges), 2)
    
    def test_node_add_edge_overwrites_existing(self):
        """Test that add_edge() overwrites existing condition (data storage behavior)."""
        # Arrange
        node = Node("test_node")
        node.add_edge("success", "first_target")
        
        # Act
        node.add_edge("success", "second_target")
        
        # Assert
        self.assertEqual(node.edges["success"], "second_target")
        self.assertEqual(len(node.edges), 1)
    
    def test_node_has_conditional_routing_simple_query(self):
        """Test has_conditional_routing() as simple data query method."""
        # Arrange
        node_no_routing = Node("no_routing")
        node_with_success = Node("with_success")
        node_with_failure = Node("with_failure")
        node_with_both = Node("with_both")
        node_with_other = Node("with_other")
        
        # Act - Set up different edge scenarios
        node_with_success.add_edge("success", "target")
        node_with_failure.add_edge("failure", "target")
        node_with_both.add_edge("success", "target1")
        node_with_both.add_edge("failure", "target2")
        node_with_other.add_edge("custom", "target")
        
        # Assert - Query routing data
        self.assertFalse(node_no_routing.has_conditional_routing())
        self.assertTrue(node_with_success.has_conditional_routing())
        self.assertTrue(node_with_failure.has_conditional_routing())
        self.assertTrue(node_with_both.has_conditional_routing())
        self.assertFalse(node_with_other.has_conditional_routing())  # Only custom, not success/failure
    
    def test_node_property_modification(self):
        """Test that node properties can be modified (data container behavior)."""
        # Arrange
        node = Node("test")
        
        # Act - Modify properties
        node.context = {"new": "context"}
        node.agent_type = "new_type"
        node.inputs.append("new_input")
        node.output = "new_output"
        node.prompt = "new_prompt"
        node.description = "new_description"
        
        # Assert - Verify modifications
        self.assertEqual(node.context["new"], "context")
        self.assertEqual(node.agent_type, "new_type")
        self.assertIn("new_input", node.inputs)
        self.assertEqual(node.output, "new_output")
        self.assertEqual(node.prompt, "new_prompt")
        self.assertEqual(node.description, "new_description")
    
    def test_node_string_representation(self):
        """Test node string representation (__repr__)."""
        # Arrange
        node = Node("test_node", agent_type="test_agent")
        node.add_edge("success", "next")
        node.add_edge("failure", "error")
        
        # Act
        repr_str = repr(node)
        
        # Assert
        self.assertIn("test_node", repr_str)
        self.assertIn("test_agent", repr_str)
        self.assertIn("success->next", repr_str)
        self.assertIn("failure->error", repr_str)


class TestExecutionTrackerDataContainer(unittest.TestCase):
    """Test ExecutionTracker model as pure data container."""
    
    def test_execution_tracker_default_initialization(self):
        """Test ExecutionTracker initialization with defaults."""
        # Act
        tracker = ExecutionTracker()
        
        # Assert
        self.assertEqual(tracker.node_executions, [])
        self.assertEqual(tracker.node_execution_counts, {})
        self.assertIsInstance(tracker.start_time, datetime)
        self.assertIsNone(tracker.end_time)
        self.assertTrue(tracker.overall_success)
        self.assertFalse(tracker.track_inputs)
        self.assertFalse(tracker.track_outputs)
        self.assertFalse(tracker.minimal_mode)
    
    def test_execution_tracker_with_custom_values(self):
        """Test ExecutionTracker initialization with custom values."""
        # Arrange
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        end_time = datetime(2024, 1, 1, 12, 5, 0)
        executions = [TrackerNodeExecution("node1")]
        counts = {"node1": 2, "node2": 1}
        
        # Act
        tracker = ExecutionTracker(
            node_executions=executions,
            node_execution_counts=counts,
            start_time=start_time,
            end_time=end_time,
            overall_success=False,
            track_inputs=True,
            track_outputs=True,
            minimal_mode=True
        )
        
        # Assert
        self.assertEqual(tracker.node_executions, executions)
        self.assertEqual(tracker.node_execution_counts, counts)
        self.assertEqual(tracker.start_time, start_time)
        self.assertEqual(tracker.end_time, end_time)
        self.assertFalse(tracker.overall_success)
        self.assertTrue(tracker.track_inputs)
        self.assertTrue(tracker.track_outputs)
        self.assertTrue(tracker.minimal_mode)
    
    def test_execution_tracker_default_factories(self):
        """Test that default factories create independent instances."""
        # Act
        tracker1 = ExecutionTracker()
        tracker2 = ExecutionTracker()
        
        # Assert - Different instances should have different lists/dicts
        self.assertIsNot(tracker1.node_executions, tracker2.node_executions)
        self.assertIsNot(tracker1.node_execution_counts, tracker2.node_execution_counts)
        
        # Modify one and verify the other is unchanged
        tracker1.node_executions.append(TrackerNodeExecution("test"))
        tracker1.node_execution_counts["test"] = 1
        
        self.assertEqual(len(tracker2.node_executions), 0)
        self.assertEqual(len(tracker2.node_execution_counts), 0)
    
    def test_execution_tracker_data_modification(self):
        """Test that ExecutionTracker data can be modified."""
        # Arrange
        tracker = ExecutionTracker()
        node_exec = TrackerNodeExecution("test_node")
        
        # Act - Modify data
        tracker.node_executions.append(node_exec)
        tracker.node_execution_counts["test_node"] = 5
        tracker.end_time = datetime.utcnow()
        tracker.overall_success = False
        tracker.track_inputs = True
        
        # Assert - Verify modifications
        self.assertEqual(len(tracker.node_executions), 1)
        self.assertEqual(tracker.node_execution_counts["test_node"], 5)
        self.assertIsNotNone(tracker.end_time)
        self.assertFalse(tracker.overall_success)
        self.assertTrue(tracker.track_inputs)


class TestTrackerNodeExecutionDataContainer(unittest.TestCase):
    """Test NodeExecution (from execution_tracker) model as pure data container."""
    
    def test_tracker_node_execution_minimal_initialization(self):
        """Test TrackerNodeExecution initialization with minimal data."""
        # Act
        execution = TrackerNodeExecution(node_name="test_node")
        
        # Assert
        self.assertEqual(execution.node_name, "test_node")
        self.assertIsNone(execution.success)
        self.assertIsNone(execution.start_time)
        self.assertIsNone(execution.end_time)
        self.assertIsNone(execution.duration)
        self.assertIsNone(execution.output)
        self.assertIsNone(execution.error)
        self.assertIsNone(execution.subgraph_execution_tracker)
        self.assertIsNone(execution.inputs)
    
    def test_tracker_node_execution_full_initialization(self):
        """Test TrackerNodeExecution initialization with all data."""
        # Arrange
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        end_time = datetime(2024, 1, 1, 12, 0, 30)
        duration = 30.5
        output = {"result": "success"}
        inputs = {"input1": "value1"}
        sub_tracker = ExecutionTracker()
        
        # Act
        execution = TrackerNodeExecution(
            node_name="full_node",
            success=True,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            output=output,
            error=None,
            subgraph_execution_tracker=sub_tracker,
            inputs=inputs
        )
        
        # Assert
        self.assertEqual(execution.node_name, "full_node")
        self.assertTrue(execution.success)
        self.assertEqual(execution.start_time, start_time)
        self.assertEqual(execution.end_time, end_time)
        self.assertEqual(execution.duration, duration)
        self.assertEqual(execution.output, output)
        self.assertIsNone(execution.error)
        self.assertIs(execution.subgraph_execution_tracker, sub_tracker)
        self.assertEqual(execution.inputs, inputs)
    
    def test_tracker_node_execution_error_case(self):
        """Test TrackerNodeExecution with error data."""
        # Act
        execution = TrackerNodeExecution(
            node_name="error_node",
            success=False,
            error="Something went wrong"
        )
        
        # Assert
        self.assertEqual(execution.node_name, "error_node")
        self.assertFalse(execution.success)
        self.assertEqual(execution.error, "Something went wrong")
    
    def test_tracker_node_execution_data_modification(self):
        """Test TrackerNodeExecution data modification."""
        # Arrange
        execution = TrackerNodeExecution("test")
        
        # Act - Modify data
        execution.success = True
        execution.start_time = datetime.utcnow()
        execution.duration = 45.2
        execution.output = {"new": "output"}
        
        # Assert - Verify modifications
        self.assertTrue(execution.success)
        self.assertIsNotNone(execution.start_time)
        self.assertEqual(execution.duration, 45.2)
        self.assertEqual(execution.output["new"], "output")


class TestExecutionSummaryDataContainer(unittest.TestCase):
    """Test ExecutionSummary model as pure data container."""
    
    def test_execution_summary_minimal_initialization(self):
        """Test ExecutionSummary initialization with minimal data."""
        # Act
        summary = ExecutionSummary(graph_name="test_graph")
        
        # Assert
        self.assertEqual(summary.graph_name, "test_graph")
        self.assertIsNone(summary.start_time)
        self.assertIsNone(summary.end_time)
        self.assertEqual(summary.node_executions, [])
        self.assertIsNone(summary.final_output)
        self.assertIsNone(summary.graph_success)
        self.assertEqual(summary.status, "pending")
    
    def test_execution_summary_full_initialization(self):
        """Test ExecutionSummary initialization with all data."""
        # Arrange
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        end_time = datetime(2024, 1, 1, 12, 5, 0)
        node_exec = SummaryNodeExecution(
            node_name="test_node",
            success=True,
            start_time=start_time,
            end_time=end_time,
            duration=30.0
        )
        executions = [node_exec]
        final_output = {"result": "completed"}
        
        # Act
        summary = ExecutionSummary(
            graph_name="full_graph",
            start_time=start_time,
            end_time=end_time,
            node_executions=executions,
            final_output=final_output,
            graph_success=True,
            status="completed"
        )
        
        # Assert
        self.assertEqual(summary.graph_name, "full_graph")
        self.assertEqual(summary.start_time, start_time)
        self.assertEqual(summary.end_time, end_time)
        self.assertEqual(summary.node_executions, executions)
        self.assertEqual(summary.final_output, final_output)
        self.assertTrue(summary.graph_success)
        self.assertEqual(summary.status, "completed")
    
    def test_execution_summary_default_factory(self):
        """Test ExecutionSummary default factory for node_executions."""
        # Act
        summary1 = ExecutionSummary("graph1")
        summary2 = ExecutionSummary("graph2")
        
        # Assert - Different instances should have different lists
        self.assertIsNot(summary1.node_executions, summary2.node_executions)
        
        # Modify one and verify the other is unchanged
        summary1.node_executions.append(SummaryNodeExecution("test", True, datetime.utcnow(), datetime.utcnow(), 1.0))
        self.assertEqual(len(summary2.node_executions), 0)
    
    def test_execution_summary_data_modification(self):
        """Test ExecutionSummary data modification."""
        # Arrange
        summary = ExecutionSummary("test")
        node_exec = SummaryNodeExecution("node1", True, datetime.utcnow(), datetime.utcnow(), 1.0)
        
        # Act - Modify data
        summary.start_time = datetime.utcnow()
        summary.end_time = datetime.utcnow()
        summary.node_executions.append(node_exec)
        summary.final_output = {"modified": True}
        summary.graph_success = True
        summary.status = "modified"
        
        # Assert - Verify modifications
        self.assertIsNotNone(summary.start_time)
        self.assertIsNotNone(summary.end_time)
        self.assertEqual(len(summary.node_executions), 1)
        self.assertEqual(summary.final_output["modified"], True)
        self.assertTrue(summary.graph_success)
        self.assertEqual(summary.status, "modified")


class TestSummaryNodeExecutionDataContainer(unittest.TestCase):
    """Test NodeExecution (from execution_summary) model as pure data container."""
    
    def test_summary_node_execution_initialization(self):
        """Test SummaryNodeExecution initialization with required fields."""
        # Arrange
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        end_time = datetime(2024, 1, 1, 12, 0, 30)
        duration = 30.0
        
        # Act
        execution = SummaryNodeExecution(
            node_name="summary_node",
            success=True,
            start_time=start_time,
            end_time=end_time,
            duration=duration
        )
        
        # Assert
        self.assertEqual(execution.node_name, "summary_node")
        self.assertTrue(execution.success)
        self.assertEqual(execution.start_time, start_time)
        self.assertEqual(execution.end_time, end_time)
        self.assertEqual(execution.duration, duration)
        self.assertIsNone(execution.output)
        self.assertIsNone(execution.error)
    
    def test_summary_node_execution_with_optional_fields(self):
        """Test SummaryNodeExecution with optional output and error fields."""
        # Arrange
        start_time = datetime.utcnow()
        end_time = datetime.utcnow()
        output = {"key": "value"}
        
        # Act
        execution = SummaryNodeExecution(
            node_name="optional_node",
            success=True,
            start_time=start_time,
            end_time=end_time,
            duration=15.5,
            output=output,
            error=None
        )
        
        # Assert
        self.assertEqual(execution.output, output)
        self.assertIsNone(execution.error)
    
    def test_summary_node_execution_error_case(self):
        """Test SummaryNodeExecution with error scenario."""
        # Arrange
        start_time = datetime.utcnow()
        end_time = datetime.utcnow()
        
        # Act
        execution = SummaryNodeExecution(
            node_name="error_node",
            success=False,
            start_time=start_time,
            end_time=end_time,
            duration=5.0,
            output=None,
            error="Node execution failed"
        )
        
        # Assert
        self.assertFalse(execution.success)
        self.assertEqual(execution.error, "Node execution failed")
        self.assertIsNone(execution.output)
    
    def test_summary_node_execution_data_modification(self):
        """Test SummaryNodeExecution data modification."""
        # Arrange
        execution = SummaryNodeExecution("test", True, datetime.utcnow(), datetime.utcnow(), 1.0)
        
        # Act - Modify data
        execution.success = False
        execution.duration = 25.5
        execution.output = {"modified": "output"}
        execution.error = "Modified error"
        
        # Assert - Verify modifications
        self.assertFalse(execution.success)
        self.assertEqual(execution.duration, 25.5)
        self.assertEqual(execution.output["modified"], "output")
        self.assertEqual(execution.error, "Modified error")


class TestExecutionResultDataContainer(unittest.TestCase):
    """Test ExecutionResult model as pure data container."""
    
    def test_execution_result_initialization_minimal(self):
        """Test ExecutionResult initialization with minimal required fields."""
        # Arrange
        final_state = {"output": "result"}
        execution_summary = ExecutionSummary("test_graph")
        
        # Act
        result = ExecutionResult(
            graph_name="result_graph",
            final_state=final_state,
            execution_summary=execution_summary,
            success=True,
            total_duration=45.5,
            compiled_from="memory"
        )
        
        # Assert
        self.assertEqual(result.graph_name, "result_graph")
        self.assertEqual(result.final_state, final_state)
        self.assertIs(result.execution_summary, execution_summary)
        self.assertTrue(result.success)
        self.assertEqual(result.total_duration, 45.5)
        self.assertEqual(result.compiled_from, "memory")
        self.assertIsNone(result.error)
    
    def test_execution_result_initialization_with_error(self):
        """Test ExecutionResult initialization with error scenario."""
        # Arrange
        final_state = {"error": "execution failed"}
        execution_summary = ExecutionSummary("failed_graph")
        
        # Act
        result = ExecutionResult(
            graph_name="failed_graph",
            final_state=final_state,
            execution_summary=execution_summary,
            success=False,
            total_duration=12.3,
            compiled_from="autocompiled",
            error="Graph execution encountered an error"
        )
        
        # Assert
        self.assertEqual(result.graph_name, "failed_graph")
        self.assertFalse(result.success)
        self.assertEqual(result.compiled_from, "autocompiled")
        self.assertEqual(result.error, "Graph execution encountered an error")
    
    def test_execution_result_compiled_from_options(self):
        """Test ExecutionResult with different compiled_from values."""
        # Arrange
        base_data = {
            "final_state": {},
            "execution_summary": ExecutionSummary("test"),
            "success": True,
            "total_duration": 1.0
        }
        
        # Act & Assert - Test different compiled_from values
        for compiled_from in ["precompiled", "autocompiled", "memory"]:
            result = ExecutionResult(
                graph_name=f"graph_{compiled_from}",
                compiled_from=compiled_from,
                **base_data
            )
            self.assertEqual(result.compiled_from, compiled_from)
    
    def test_execution_result_data_modification(self):
        """Test ExecutionResult data modification."""
        # Arrange
        result = ExecutionResult(
            graph_name="modifiable",
            final_state={},
            execution_summary=ExecutionSummary("test"),
            success=True,
            total_duration=1.0,
            compiled_from="memory"
        )
        
        # Act - Modify data
        result.final_state = {"new": "state"}
        result.success = False
        result.total_duration = 99.9
        result.error = "New error"
        
        # Assert - Verify modifications
        self.assertEqual(result.final_state["new"], "state")
        self.assertFalse(result.success)
        self.assertEqual(result.total_duration, 99.9)
        self.assertEqual(result.error, "New error")


class TestDataContainerInteroperability(unittest.TestCase):
    """Test how data container models work together."""
    
    def test_graph_with_multiple_nodes(self):
        """Test Graph containing multiple Node data containers."""
        # Arrange
        node1 = Node("start", agent_type="input")
        node2 = Node("process", agent_type="llm")
        node3 = Node("end", agent_type="output")
        
        # Set up edges
        node1.add_edge("success", "process")
        node2.add_edge("success", "end")
        node2.add_edge("failure", "start")
        
        # Act
        graph = Graph(
            name="multi_node_graph",
            entry_point="start",
            nodes={"start": node1, "process": node2, "end": node3}
        )
        
        # Assert - Data storage works correctly
        self.assertEqual(len(graph.nodes), 3)
        self.assertEqual(graph.entry_point, "start")
        self.assertEqual(graph.nodes["start"].edges["success"], "process")
        self.assertEqual(graph.nodes["process"].edges["failure"], "start")
    
    def test_execution_summary_with_node_executions(self):
        """Test ExecutionSummary containing NodeExecution data containers."""
        # Arrange
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        node_exec1 = SummaryNodeExecution("node1", True, start_time, start_time + timedelta(seconds=10), 10.0)
        node_exec2 = SummaryNodeExecution("node2", True, start_time + timedelta(seconds=10), start_time + timedelta(seconds=25), 15.0)
        
        # Act
        summary = ExecutionSummary(
            graph_name="interop_test",
            start_time=start_time,
            end_time=start_time + timedelta(seconds=25),
            node_executions=[node_exec1, node_exec2],
            graph_success=True,
            status="completed"
        )
        
        # Assert - Data relationships work correctly
        self.assertEqual(len(summary.node_executions), 2)
        self.assertEqual(summary.node_executions[0].node_name, "node1")
        self.assertEqual(summary.node_executions[1].duration, 15.0)
        self.assertTrue(all(exec.success for exec in summary.node_executions))
    
    def test_execution_result_with_summary(self):
        """Test ExecutionResult containing ExecutionSummary data container."""
        # Arrange
        summary = ExecutionSummary("result_test")
        summary.graph_success = True
        final_state = {"final_output": "success"}
        
        # Act
        result = ExecutionResult(
            graph_name="result_test",
            final_state=final_state,
            execution_summary=summary,
            success=True,
            total_duration=30.0,
            compiled_from="precompiled"
        )
        
        # Assert - Data container composition works
        self.assertIs(result.execution_summary, summary)
        self.assertEqual(result.execution_summary.graph_name, "result_test")
        self.assertTrue(result.execution_summary.graph_success)
        self.assertEqual(result.final_state["final_output"], "success")


if __name__ == '__main__':
    unittest.main()
