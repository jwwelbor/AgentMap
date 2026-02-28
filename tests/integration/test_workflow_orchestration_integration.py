"""
Integration tests for WorkflowOrchestrationService using temporary files and real services.

This follows AgentMap testing patterns:
- Use temporary files instead of heavy mocking
- Test real service coordination
- Use real DI container for integration testing
- Focus on actual workflow orchestration behavior
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.execution.result import ExecutionResult
from agentmap.services.workflow_orchestration_service import (
    WorkflowOrchestrationService,
)


class TestWorkflowOrchestrationIntegration(unittest.TestCase):
    """Integration tests for WorkflowOrchestrationService using temporary files."""

    def setUp(self):
        """Set up test fixtures with temporary files."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create test CSV file with simple graph
        self.csv_file = self.temp_path / "test_workflow.csv"
        self.create_test_csv()

        # Create temporary config pointing to our temp directories
        self.config_file = self.temp_path / "test_config.yaml"
        self.create_test_config()

        # Create test data directories
        (self.temp_path / "compiled").mkdir()
        (self.temp_path / "data").mkdir()
        (self.temp_path / "data" / "json").mkdir()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_csv(self):
        """Create a simple test CSV file for workflow testing."""
        csv_content = """graph_name,node_name,agent_type,prompt,description,context,input_fields,output_field,edge,success_next,failure_next
test_graph,start_node,echo,Echo user input,Start node,{},user_input,result,end_node,,
test_graph,end_node,echo,Echo the result,End node,{},result,final_output,,,
"""
        self.csv_file.write_text(csv_content, encoding="utf-8")

    def create_test_config(self):
        """Create test configuration file pointing to temporary directories."""
        import yaml

        # Create storage config file
        storage_config_file = self.temp_path / "storage_config.yaml"
        storage_config_data = {
            "base_directory": str(self.temp_path / "data"),
            "json": {
                "default_directory": "json",
                "collections": {
                    "interactions_threads": {"filename": "threads.json"},
                    "interactions_responses": {"filename": "responses.json"},
                },
            },
        }

        with open(storage_config_file, "w") as f:
            yaml.dump(storage_config_data, f, default_flow_style=False, indent=2)

        config_data = {
            "app": {
                "csv_path": str(self.csv_file),
                "compiled_graphs_path": str(self.temp_path / "compiled"),
            },
            "storage_config_path": str(storage_config_file),
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "console": {"class": "logging.StreamHandler", "level": "ERROR"}
                },
                "root": {"level": "ERROR", "handlers": ["console"]},
            },
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-sonnet-4-6",
                }
            },
        }

        with open(self.config_file, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)

    def test_execute_workflow_basic_success(self):
        """Test basic workflow execution with real services and temp files."""
        # Prepare initial state
        initial_state = {"user_input": "Hello, world!"}

        # Execute workflow using our temporary files
        result = WorkflowOrchestrationService.execute_workflow(
            workflow=str(self.csv_file),
            graph_name="test_graph",
            initial_state=initial_state,
            config_file=str(self.config_file),
        )

        # Verify execution result
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "test_graph")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.final_state)
        self.assertIsNotNone(result.execution_summary)

        # Verify nodes were executed
        node_executions = result.execution_summary.node_executions
        self.assertGreater(len(node_executions), 0)

        executed_nodes = [node_exec.node_name for node_exec in node_executions]
        self.assertIn("start_node", executed_nodes)
        self.assertIn("end_node", executed_nodes)

    def test_execute_workflow_with_json_initial_state(self):
        """Test workflow execution with JSON string initial state."""
        # Use JSON string instead of dict
        initial_state_json = '{"user_input": "JSON test input"}'

        result = WorkflowOrchestrationService.execute_workflow(
            workflow=str(self.csv_file),
            graph_name="test_graph",
            initial_state=initial_state_json,
            config_file=str(self.config_file),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.graph_name, "test_graph")

    def test_execute_workflow_invalid_json_state(self):
        """Test workflow execution handles invalid JSON gracefully."""
        invalid_json = '{"invalid": json malformed}'

        with self.assertRaises(ValueError) as context:
            WorkflowOrchestrationService.execute_workflow(
                workflow=str(self.csv_file),
                graph_name="test_graph",
                initial_state=invalid_json,
                config_file=str(self.config_file),
            )

        self.assertIn("Invalid JSON", str(context.exception))

    def test_execute_workflow_missing_graph(self):
        """Test workflow execution with non-existent graph name."""
        with self.assertRaises(
            Exception
        ):  # Should raise some error about missing graph
            WorkflowOrchestrationService.execute_workflow(
                workflow=str(self.csv_file),
                graph_name="nonexistent_graph",
                initial_state={"test": "data"},
                config_file=str(self.config_file),
            )


class TestWorkflowResumeIntegration(unittest.TestCase):
    """Integration tests for workflow resume functionality with real storage."""

    def setUp(self):
        """Set up test fixtures for resume testing."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create test files and config (same as above)
        self.csv_file = self.temp_path / "test_workflow.csv"
        self.config_file = self.temp_path / "test_config.yaml"
        self.create_test_files()

        # Set up test data
        self.thread_id = "test_thread_123"
        self.request_id = str(uuid4())
        self.bundle_path = self.temp_path / "compiled" / "test_graph.pkl"

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_files(self):
        """Create test CSV and config files."""
        import yaml

        # Same CSV content as above test
        csv_content = """graph_name,node_name,agent_type,prompt,description,context,input_fields,output_field,edge,success_next,failure_next
test_graph,start_node,echo,Echo user input,Start node,{},user_input,result,end_node,,
test_graph,end_node,echo,Echo the result,End node,{},result,final_output,,,
"""
        self.csv_file.write_text(csv_content, encoding="utf-8")

        # Create storage config file
        storage_config_file = self.temp_path / "storage_config.yaml"
        storage_config_data = {
            "base_directory": str(self.temp_path / "data"),
            "json": {
                "default_directory": "json",
                "collections": {
                    "interactions_threads": {"filename": "threads.json"},
                    "interactions_responses": {"filename": "responses.json"},
                },
            },
        }

        with open(storage_config_file, "w") as f:
            yaml.dump(storage_config_data, f, default_flow_style=False, indent=2)

        # Config pointing to temp directories
        config_data = {
            "app": {
                "csv_path": str(self.csv_file),
                "compiled_graphs_path": str(self.temp_path / "compiled"),
            },
            "storage_config_path": str(storage_config_file),
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "console": {"class": "logging.StreamHandler", "level": "ERROR"}
                },
                "root": {"level": "ERROR", "handlers": ["console"]},
            },
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-sonnet-4-6",
                }
            },
        }

        with open(self.config_file, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)

        # Create directories
        (self.temp_path / "compiled").mkdir()
        (self.temp_path / "data").mkdir()
        (self.temp_path / "data" / "json").mkdir()

    def test_resume_workflow_thread_not_found(self):
        """Test resume when thread doesn't exist in storage."""
        with self.assertRaises(RuntimeError) as context:
            WorkflowOrchestrationService.resume_workflow(
                thread_id="nonexistent_thread",
                response_action="approve",
                config_file=str(self.config_file),
            )

        self.assertIn("Thread 'nonexistent_thread' not found", str(context.exception))

    def test_resume_workflow_no_pending_interaction(self):
        """Suspend-only threads resume using stored checkpoint metadata."""
        from agentmap.di import initialize_di

        container = initialize_di(str(self.config_file))
        interaction_handler = container.interaction_handler_service()
        graph_bundle_service = container.graph_bundle_service()

        bundle, _ = graph_bundle_service.get_or_create_bundle(
            csv_path=self.csv_file,
            graph_name="test_graph",
            config_path=str(self.config_file),
        )

        checkpoint_data = {
            "node_name": "start_node",
            "inputs": {},
            "agent_context": {},
            "execution_tracker": None,
        }

        exception = ExecutionInterruptedException(
            thread_id=self.thread_id,
            interaction_request=None,
            checkpoint_data=checkpoint_data,
        )

        interaction_handler.handle_execution_interruption(exception, bundle=bundle)

        mock_graph_runner = Mock()
        expected_result = ExecutionResult(
            success=True,
            graph_name="test_graph",
            final_state={"status": "resumed"},
            execution_summary="Resume completed",
            total_duration=1.0,
        )
        mock_graph_runner.resume_from_checkpoint.return_value = expected_result

        with (
            patch(
                "agentmap.services.workflow_orchestration_service.initialize_di",
                return_value=container,
            ),
            patch.object(
                container,
                "interaction_handler_service",
                return_value=interaction_handler,
            ),
            patch.object(
                container, "graph_bundle_service", return_value=graph_bundle_service
            ),
            patch.object(
                container, "graph_runner_service", return_value=mock_graph_runner
            ),
        ):
            result = WorkflowOrchestrationService.resume_workflow(
                thread_id=self.thread_id,
                response_action="",
                config_file=str(self.config_file),
            )

        self.assertEqual(result, expected_result)
        mock_graph_runner.resume_from_checkpoint.assert_called_once()

        updated_metadata = interaction_handler.get_thread_metadata(self.thread_id)
        self.assertIsNotNone(updated_metadata)
        self.assertEqual(updated_metadata["status"], "resuming")


class TestBundleRehydrationIntegration(unittest.TestCase):
    """Integration tests for bundle rehydration with real GraphBundleService."""

    def setUp(self):
        """Set up test fixtures for bundle rehydration testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Create test CSV and config
        self.csv_file = self.temp_path / "test_workflow.csv"
        self.config_file = self.temp_path / "test_config.yaml"
        self.bundle_path = self.temp_path / "compiled" / "test_graph.pkl"
        self.create_test_files()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_files(self):
        """Create test files for bundle testing."""
        import yaml

        csv_content = """graph_name,node_name,agent_type,prompt,description,context,input_fields,output_field,edge,success_next,failure_next
test_graph,start_node,echo,Echo test,Test node,{},input,output,,,
"""
        self.csv_file.write_text(csv_content, encoding="utf-8")

        config_data = {
            "app": {
                "csv_path": str(self.csv_file),
                "compiled_graphs_path": str(self.temp_path / "compiled"),
            },
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "console": {"class": "logging.StreamHandler", "level": "ERROR"}
                },
                "root": {"level": "ERROR", "handlers": ["console"]},
            },
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-sonnet-4-6",
                }
            },
        }

        with open(self.config_file, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)

        (self.temp_path / "compiled").mkdir()

    def test_rehydrate_from_csv_path(self):
        """Test bundle rehydration by recreating from CSV path."""
        from agentmap.di import initialize_di
        from agentmap.services.workflow_orchestration_service import (
            _rehydrate_bundle_from_metadata,
        )

        container = initialize_di(str(self.config_file))
        graph_bundle_service = container.graph_bundle_service()

        # Bundle info with only CSV path (no existing bundle)
        bundle_info = {
            "csv_path": str(self.csv_file),
            "bundle_path": None,  # No existing bundle
            "csv_hash": None,  # No hash
        }

        # Try to rehydrate - should recreate from CSV
        bundle = _rehydrate_bundle_from_metadata(
            bundle_info, "test_graph", graph_bundle_service
        )

        # Should successfully create bundle
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle.graph_name, "test_graph")

    def test_rehydrate_empty_bundle_info(self):
        """Test bundle rehydration with empty bundle info."""
        from agentmap.di import initialize_di
        from agentmap.services.workflow_orchestration_service import (
            _rehydrate_bundle_from_metadata,
        )

        container = initialize_di(str(self.config_file))
        graph_bundle_service = container.graph_bundle_service()

        # Empty bundle info
        bundle_info = {}

        bundle = _rehydrate_bundle_from_metadata(
            bundle_info, "test_graph", graph_bundle_service
        )

        # Should return None for empty info
        self.assertIsNone(bundle)


if __name__ == "__main__":
    unittest.main()
