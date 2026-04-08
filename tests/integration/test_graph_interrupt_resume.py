"""
Integration tests for graph interrupt and resume functionality.

Tests the complete workflow including checkpoint persistence, interaction handling,
and bundle rehydration with real service dependencies.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock
from uuid import uuid4

from agentmap.di.containers import ApplicationContainer
from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
from agentmap.services.interaction_handler_service import InteractionHandlerService


class TestGraphInterruptResumeIntegration(unittest.TestCase):
    """Integration tests for graph interrupt and resume functionality."""

    def setUp(self):
        """Set up test fixtures with real DI container."""
        self.temp_dir = tempfile.mkdtemp()
        self.user_storage_dir = os.path.join(self.temp_dir, "user_storage")
        self.cache_dir = os.path.join(self.temp_dir, "cache")

        os.makedirs(self.user_storage_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        self._create_test_config_files()

        self.container = ApplicationContainer()
        self.container.config.from_dict(
            {"path": os.path.join(self.temp_dir, "config.yaml")}
        )

        self.container.wire(modules=[])

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        self.container.unwire()

    def _create_test_config_files(self):
        """Create test configuration files for integration testing."""
        storage_config_path = os.path.join(self.temp_dir, "storage.yaml").replace(
            "\\", "/"
        )
        cache_path = self.cache_dir.replace("\\", "/")
        config_content = f"""
storage_config_path: "{storage_config_path}"
cache_path: "{cache_path}"
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
"""

        config_path = os.path.join(self.temp_dir, "config.yaml")
        with open(config_path, "w") as f:
            f.write(config_content)

        user_storage_path = self.user_storage_dir.replace("\\", "/")
        storage_content = f"""
base_directory: "{user_storage_path}"
providers:
  json:
    enabled: true
    settings:
      indent: 2
  csv:
    enabled: true
"""

        storage_path = os.path.join(self.temp_dir, "storage.yaml")
        with open(storage_path, "w") as f:
            f.write(storage_content)

    def _create_test_interaction_request(
        self, thread_id: str = "test_thread"
    ) -> HumanInteractionRequest:
        """Create a test interaction request."""
        return HumanInteractionRequest(
            id=uuid4(),
            thread_id=thread_id,
            node_name="test_node",
            interaction_type=InteractionType.TEXT_INPUT,
            prompt="Please provide input",
            context={"test": "context"},
            options=["option1", "option2"],
            timeout_seconds=300,
        )

    def _create_test_bundle(self) -> Mock:
        """Create a test GraphBundle."""
        mock_bundle = Mock()
        mock_bundle.csv_hash = "test_hash_456"
        mock_bundle.bundle_path = "/test/bundle/path.json"
        mock_bundle.csv_path = "/test/csv/workflow.csv"
        return mock_bundle

    def test_checkpoint_service_with_real_storage(self):
        """Test GraphCheckpointService with real storage backend."""
        logging_service = self.container.logging_service()
        system_storage = self.container.system_storage_manager()

        json_service = system_storage.get_json_storage("langgraph_checkpoints")

        checkpoint_service = GraphCheckpointService(
            json_storage_service=json_service, logging_service=logging_service
        )

        thread_id = "integration_test_thread"
        config = {"configurable": {"thread_id": thread_id}}

        from langgraph.checkpoint.base import Checkpoint

        checkpoint = Checkpoint(
            channel_values={"nodes": {"test_node": "test_value"}},
            channel_versions={"nodes": 1},
            versions_seen={"test_node": 1},
        )
        metadata = {"source": "integration_test", "step": 1}

        result = checkpoint_service.put(config, checkpoint, metadata)
        self.assertTrue(result["success"])
        self.assertIn("checkpoint_id", result)

        retrieved_tuple = checkpoint_service.get_tuple(config)
        self.assertIsNotNone(retrieved_tuple)
        self.assertEqual(retrieved_tuple.config, config)
        self.assertEqual(
            retrieved_tuple.checkpoint.channel_values, checkpoint.channel_values
        )
        self.assertEqual(retrieved_tuple.metadata, metadata)

        info = checkpoint_service.get_service_info()
        self.assertTrue(info["storage_available"])
        self.assertTrue(info["implements_base_checkpoint_saver"])

    def test_interaction_service_with_real_storage(self):
        """Test InteractionHandlerService with real storage backend."""
        logging_service = self.container.logging_service()
        self.container.app_config_service()
        storage_config = self.container.storage_config_service()
        file_path_service = self.container.file_path_service()

        if storage_config is None:
            self.skipTest("storage_config_service not available")

        from agentmap.services.storage.manager import StorageServiceManager

        storage_manager = StorageServiceManager(
            storage_config, logging_service, file_path_service
        )

        json_service = storage_manager.get_service("json")

        mock_cli_handler = Mock()

        interaction_service = InteractionHandlerService(
            storage_service=json_service,
            cli_handler=mock_cli_handler,
            logging_service=logging_service,
        )

        thread_id = "interaction_integration_test"
        interaction_request = self._create_test_interaction_request(thread_id)
        bundle = self._create_test_bundle()

        checkpoint_data = {
            "inputs": {"user_input": "test_data"},
            "agent_context": {"execution_id": "exec_123"},
            "execution_tracker": {"nodes": ["node1"]},
            "node_name": "test_node",
        }

        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

        interaction_service.handle_execution_interruption(
            exception=exception, bundle=bundle
        )

        mock_cli_handler.display_interaction_request.assert_called_once_with(
            interaction_request
        )

        metadata = interaction_service.get_thread_metadata(thread_id)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["thread_id"], thread_id)
        self.assertEqual(metadata["status"], "paused")

        success = interaction_service.mark_thread_resuming(thread_id)
        self.assertTrue(success)

        success = interaction_service.mark_thread_completed(thread_id)
        self.assertTrue(success)

        info = interaction_service.get_service_info()
        self.assertTrue(info["storage_service_available"])
        self.assertTrue(info["cli_handler_available"])

    def test_complete_interrupt_resume_workflow(self):
        """Test the complete interrupt and resume workflow."""
        logging_service = self.container.logging_service()
        system_storage = self.container.system_storage_manager()

        checkpoint_json_service = system_storage.get_json_storage(
            "langgraph_checkpoints"
        )
        checkpoint_service = GraphCheckpointService(
            json_storage_service=checkpoint_json_service,
            logging_service=logging_service,
        )

        interaction_json_service = system_storage.get_json_storage("interactions")
        mock_cli_handler = Mock()

        interaction_service = InteractionHandlerService(
            storage_service=interaction_json_service,
            cli_handler=mock_cli_handler,
            logging_service=logging_service,
        )

        thread_id = "complete_workflow_test"

        from langgraph.checkpoint.base import Checkpoint

        initial_checkpoint = Checkpoint(
            channel_values={"nodes": {"start": "initialized"}},
            channel_versions={"nodes": 1},
            versions_seen={"start": 1},
        )

        config = {"configurable": {"thread_id": thread_id}}
        checkpoint_result = checkpoint_service.put(
            config, initial_checkpoint, {"source": "workflow_test", "step": 1}
        )
        self.assertTrue(checkpoint_result["success"])

        interaction_request = self._create_test_interaction_request(thread_id)
        bundle = self._create_test_bundle()

        checkpoint_data = {
            "inputs": {"current_state": "paused"},
            "agent_context": {"checkpoint_id": checkpoint_result["checkpoint_id"]},
            "execution_tracker": {"completed_nodes": ["start"]},
            "node_name": "test_node",
        }

        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

        interaction_service.handle_execution_interruption(
            exception=exception, bundle=bundle
        )

        mock_cli_handler.display_interaction_request.assert_called_once()

        thread_metadata = interaction_service.get_thread_metadata(thread_id)
        self.assertIsNotNone(thread_metadata)
        self.assertEqual(thread_metadata["status"], "paused")

        resume_success = interaction_service.mark_thread_resuming(thread_id)
        self.assertTrue(resume_success)

        resumed_checkpoint = Checkpoint(
            channel_values={
                "nodes": {"test_node": "processed", "start": "initialized"}
            },
            channel_versions={"nodes": 2},
            versions_seen={"start": 1, "test_node": 1},
        )

        resume_result = checkpoint_service.put(
            config,
            resumed_checkpoint,
            {"source": "workflow_test", "step": 2, "resumed": True},
        )
        self.assertTrue(resume_result["success"])

        completion_success = interaction_service.mark_thread_completed(thread_id)
        self.assertTrue(completion_success)

        final_tuple = checkpoint_service.get_tuple(config)
        self.assertIsNotNone(final_tuple)
        self.assertEqual(
            final_tuple.checkpoint.channel_values["nodes"]["test_node"], "processed"
        )

    def test_bundle_context_preservation(self):
        """Test that bundle context is preserved during interrupt/resume cycle."""
        logging_service = self.container.logging_service()
        system_storage = self.container.system_storage_manager()

        json_service = system_storage.get_json_storage("bundle_context_test")
        mock_cli_handler = Mock()

        interaction_service = InteractionHandlerService(
            storage_service=json_service,
            cli_handler=mock_cli_handler,
            logging_service=logging_service,
        )

        thread_id = "bundle_context_test"
        interaction_request = self._create_test_interaction_request(thread_id)

        bundle = Mock()
        bundle.csv_hash = "complex_hash_789"
        bundle.bundle_path = "/complex/bundle/path.json"
        bundle.csv_path = "/complex/csv/workflow.csv"

        bundle_context = {
            "csv_hash": "override_hash_999",
            "execution_mode": "debug",
            "user_preferences": {"theme": "dark", "verbosity": "high"},
            "workflow_version": "2.1.0",
            "additional_data": {"key1": "value1", "nested": {"key2": "value2"}},
        }

        checkpoint_data = {
            "inputs": {"complex_input": "detailed_data"},
            "agent_context": {"session": "bundle_test"},
            "execution_tracker": {"phase": "context_preservation"},
            "node_name": "context_test_node",
        }

        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

        interaction_service.handle_execution_interruption(
            exception=exception, bundle=bundle, bundle_context=bundle_context
        )

        metadata = interaction_service.get_thread_metadata(thread_id)
        self.assertIsNotNone(metadata)

        preserved_bundle_info = metadata["bundle_info"]

        self.assertEqual(preserved_bundle_info["csv_hash"], "override_hash_999")
        self.assertEqual(preserved_bundle_info["execution_mode"], "debug")
        self.assertEqual(preserved_bundle_info["workflow_version"], "2.1.0")

        self.assertEqual(preserved_bundle_info["user_preferences"]["theme"], "dark")
        self.assertEqual(
            preserved_bundle_info["additional_data"]["nested"]["key2"], "value2"
        )

        checkpoint = metadata["checkpoint_data"]
        self.assertEqual(checkpoint["inputs"]["complex_input"], "detailed_data")
        self.assertEqual(checkpoint["agent_context"]["session"], "bundle_test")

    def test_error_recovery_scenarios(self):
        """Test error handling and recovery in interrupt/resume workflow."""
        logging_service = self.container.logging_service()
        system_storage = self.container.system_storage_manager()

        json_service = system_storage.get_json_storage("error_recovery_test")
        mock_cli_handler = Mock()

        interaction_service = InteractionHandlerService(
            storage_service=json_service,
            cli_handler=mock_cli_handler,
            logging_service=logging_service,
        )

        missing_thread_metadata = interaction_service.get_thread_metadata(
            "nonexistent_thread"
        )
        self.assertIsNone(missing_thread_metadata)

        thread_id = "cli_failure_test"
        interaction_request = self._create_test_interaction_request(thread_id)

        mock_cli_handler.display_interaction_request.side_effect = Exception(
            "CLI failure"
        )

        exception = ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data={"test": "data"},
        )

        with self.assertRaises(RuntimeError):
            interaction_service.handle_execution_interruption(exception)

        checkpoint_json_service = system_storage.get_json_storage("error_checkpoints")
        checkpoint_service = GraphCheckpointService(
            json_storage_service=checkpoint_json_service,
            logging_service=logging_service,
        )

        config = {"configurable": {"thread_id": "nonexistent_checkpoint_thread"}}
        result = checkpoint_service.get_tuple(config)
        self.assertIsNone(result)

        info = checkpoint_service.get_service_info()
        self.assertIn("service_name", info)
        self.assertIn("capabilities", info)

    def test_concurrent_thread_handling(self):
        """Test handling multiple concurrent threads with checkpoints."""
        logging_service = self.container.logging_service()
        system_storage = self.container.system_storage_manager()

        checkpoint_service = GraphCheckpointService(
            json_storage_service=system_storage.get_json_storage(
                "concurrent_checkpoints"
            ),
            logging_service=logging_service,
        )

        interaction_service = InteractionHandlerService(
            storage_service=system_storage.get_json_storage("concurrent_interactions"),
            cli_handler=Mock(),
            logging_service=logging_service,
        )

        threads = ["thread_1", "thread_2", "thread_3"]

        from langgraph.checkpoint.base import Checkpoint

        for i, thread_id in enumerate(threads):
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint = Checkpoint(
                channel_values={"nodes": {f"node_{i}": f"value_{i}"}},
                channel_versions={"nodes": i + 1},
                versions_seen={f"node_{i}": 1},
            )

            result = checkpoint_service.put(
                config,
                checkpoint,
                {"source": "concurrent_test", "thread": thread_id},
            )
            self.assertTrue(result["success"])

        for thread_id in threads:
            interaction_request = self._create_test_interaction_request(thread_id)
            exception = ExecutionInterruptedException(
                thread_id=thread_id,
                interaction_request=interaction_request,
                checkpoint_data={"thread": thread_id, "status": "concurrent"},
            )

            interaction_service.handle_execution_interruption(exception)

        for thread_id in threads:
            config = {"configurable": {"thread_id": thread_id}}
            tuple_result = checkpoint_service.get_tuple(config)
            self.assertIsNotNone(tuple_result)

            metadata = interaction_service.get_thread_metadata(thread_id)
            self.assertIsNotNone(metadata)
            self.assertEqual(metadata["thread_id"], thread_id)
            self.assertEqual(metadata["status"], "paused")

        for thread_id in threads:
            success = interaction_service.mark_thread_resuming(thread_id)
            self.assertTrue(success)

            success = interaction_service.mark_thread_completed(thread_id)
            self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
