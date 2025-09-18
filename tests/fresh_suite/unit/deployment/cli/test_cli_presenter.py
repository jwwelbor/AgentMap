"""
Test suite for CLI presenter utilities - JSON serialization and output formatting.

This module tests the AgentMapJSONEncoder that handles serialization of
StorageResult, ExecutionSummary, and other custom objects to JSON.
"""

import unittest
import json
import io
import sys
from datetime import datetime
from unittest.mock import patch

from agentmap.deployment.cli.utils.cli_presenter import AgentMapJSONEncoder, print_json, print_err
from agentmap.models.storage.types import StorageResult
from agentmap.models.execution.summary import ExecutionSummary, NodeExecution


class TestAgentMapJSONEncoder(unittest.TestCase):
    """Test suite for AgentMapJSONEncoder - Custom JSON encoder for AgentMap objects."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.encoder = AgentMapJSONEncoder()
    
    def test_datetime_serialization(self):
        """Test datetime objects are converted to ISO format strings."""
        test_datetime = datetime(2025, 9, 17, 20, 52, 18, 293705)
        expected = "2025-09-17T20:52:18.293705"
        
        result = self.encoder.default(test_datetime)
        self.assertEqual(result, expected)
    
    def test_storage_result_serialization(self):
        """Test StorageResult objects are converted using their to_dict method."""
        storage_result = StorageResult(
            success=True,
            operation='append',
            collection='personal_goals.csv',
            file_path='agentmap_data/data\\personal_goals.csv',
            rows_written=1
        )
        
        result = self.encoder.default(storage_result)
        
        # Should be a dictionary without None values
        self.assertIsInstance(result, dict)
        self.assertEqual(result['success'], True)
        self.assertEqual(result['operation'], 'append')
        self.assertEqual(result['collection'], 'personal_goals.csv')
        self.assertEqual(result['rows_written'], 1)
        
        # None values should be filtered out
        self.assertNotIn('document_id', result)
        self.assertNotIn('mode', result)
    
    def test_node_execution_serialization(self):
        """Test NodeExecution dataclass objects are converted with datetime handling."""
        start_time = datetime(2025, 9, 17, 20, 52, 18, 357635)
        end_time = datetime(2025, 9, 17, 20, 52, 31, 683981)
        
        node_execution = NodeExecution(
            node_name='GetGoal',
            success=True,
            start_time=start_time,
            end_time=end_time,
            duration=13.326346,
            output=None,
            error=None
        )
        
        result = self.encoder.default(node_execution)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['node_name'], 'GetGoal')
        self.assertEqual(result['success'], True)
        self.assertEqual(result['start_time'], "2025-09-17T20:52:18.357635")
        self.assertEqual(result['end_time'], "2025-09-17T20:52:31.683981")
        self.assertEqual(result['duration'], 13.326346)
    
    def test_execution_summary_serialization(self):
        """Test ExecutionSummary dataclass objects are converted with nested datetime handling."""
        start_time = datetime(2025, 9, 17, 20, 52, 18, 293705)
        end_time = datetime(2025, 9, 17, 20, 52, 38, 335310)
        
        node_exec = NodeExecution(
            node_name='GetGoal',
            success=True,
            start_time=start_time,
            end_time=end_time,
            duration=13.326346
        )
        
        execution_summary = ExecutionSummary(
            graph_name='PersonalGoals',
            start_time=start_time,
            end_time=end_time,
            node_executions=[node_exec],
            final_output={'goal': 'write a killer new song.'},
            graph_success=True,
            status='completed'
        )
        
        result = self.encoder.default(execution_summary)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['graph_name'], 'PersonalGoals')
        self.assertEqual(result['start_time'], "2025-09-17T20:52:18.293705")
        self.assertEqual(result['end_time'], "2025-09-17T20:52:38.335310")
        self.assertEqual(result['graph_success'], True)
        self.assertEqual(result['status'], 'completed')
        
        # Check nested node executions are also processed
        self.assertEqual(len(result['node_executions']), 1)
        node_result = result['node_executions'][0]
        self.assertEqual(node_result['node_name'], 'GetGoal')
        self.assertEqual(node_result['start_time'], "2025-09-17T20:52:18.293705")
    
    def test_nested_datetime_processing(self):
        """Test recursive processing of nested structures with datetime objects."""
        test_data = {
            'timestamp': datetime(2025, 9, 17, 20, 52, 18),
            'nested': {
                'inner_timestamp': datetime(2025, 9, 17, 21, 0, 0),
                'list_with_dates': [
                    datetime(2025, 9, 17, 22, 0, 0),
                    {'deep_timestamp': datetime(2025, 9, 17, 23, 0, 0)}
                ]
            }
        }
        
        result = self.encoder._process_nested_datetimes(test_data)
        
        self.assertEqual(result['timestamp'], "2025-09-17T20:52:18")
        self.assertEqual(result['nested']['inner_timestamp'], "2025-09-17T21:00:00")
        self.assertEqual(result['nested']['list_with_dates'][0], "2025-09-17T22:00:00")
        self.assertEqual(result['nested']['list_with_dates'][1]['deep_timestamp'], "2025-09-17T23:00:00")
    
    def test_unknown_object_fallback(self):
        """Test unknown objects fall back to standard JSON encoder behavior."""
        class UnknownObject:
            def __init__(self):
                self.value = "test"
        
        unknown_obj = UnknownObject()
        
        with self.assertRaises(TypeError):
            self.encoder.default(unknown_obj)
    
    def test_complex_payload_serialization(self):
        """Test serialization of complex payload similar to the original error."""
        # Create a complex payload similar to the one that caused the error
        storage_result = StorageResult(
            success=True,
            operation='append',
            collection='personal_goals.csv',
            rows_written=1
        )
        
        execution_summary = ExecutionSummary(
            graph_name='PersonalGoals',
            start_time=datetime(2025, 9, 17, 20, 52, 18, 293705),
            end_time=datetime(2025, 9, 17, 20, 52, 38, 335310),
            graph_success=True,
            status='completed'
        )
        
        complex_payload = {
            'success': True,
            'outputs': {
                'goal': 'write a killer new song.',
                'save_result': storage_result,
                'final_message': storage_result,
                'completion': storage_result
            },
            'execution_summary': execution_summary
        }
        
        # This should not raise an exception
        json_string = json.dumps(complex_payload, cls=AgentMapJSONEncoder, indent=2)
        
        # Verify it's valid JSON
        parsed_back = json.loads(json_string)
        self.assertIsInstance(parsed_back, dict)
        self.assertEqual(parsed_back['success'], True)
        self.assertEqual(parsed_back['outputs']['goal'], 'write a killer new song.')


class TestCLIPresenterFunctions(unittest.TestCase):
    """Test suite for CLI presenter utility functions."""
    
    def test_print_json_with_storage_result(self):
        """Test print_json handles StorageResult objects without errors."""
        storage_result = StorageResult(
            success=True,
            operation='test',
            collection='test_collection'
        )
        
        payload = {
            'result': storage_result,
            'timestamp': datetime(2025, 9, 17, 20, 52, 18)
        }
        
        # Capture stdout
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            print_json(payload)
        
        output = captured_output.getvalue()
        
        # Should be valid JSON
        parsed = json.loads(output.strip())
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed['result']['success'], True)
        self.assertEqual(parsed['result']['operation'], 'test')
        self.assertEqual(parsed['timestamp'], "2025-09-17T20:52:18")
    
    def test_print_json_with_execution_summary(self):
        """Test print_json handles ExecutionSummary objects without errors."""
        execution_summary = ExecutionSummary(
            graph_name='TestGraph',
            start_time=datetime(2025, 9, 17, 20, 52, 18),
            status='completed'
        )
        
        payload = {
            'execution': execution_summary
        }
        
        # Capture stdout
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            print_json(payload)
        
        output = captured_output.getvalue()
        
        # Should be valid JSON
        parsed = json.loads(output.strip())
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed['execution']['graph_name'], 'TestGraph')
        self.assertEqual(parsed['execution']['start_time'], "2025-09-17T20:52:18")
    
    def test_print_err_functionality(self):
        """Test print_err writes to stderr correctly."""
        test_message = "Test error message"
        
        # Capture stderr
        captured_error = io.StringIO()
        with patch('sys.stderr', captured_error):
            print_err(test_message)
        
        output = captured_error.getvalue()
        self.assertEqual(output, f"{test_message}\n")


if __name__ == '__main__':
    unittest.main()
