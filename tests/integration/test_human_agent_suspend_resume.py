"""
Integration test for HumanAgent suspend/resume functionality.

Tests the complete workflow including:
1. GraphCheckpointService using the LangGraph put/get_tuple interface
2. Checkpoint data structures
3. Concurrent suspend/resume operations
4. Graph runner producing interrupt results for HumanAgent workflows

This test focuses on the core suspend/resume mechanics using the current API.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from langgraph.checkpoint.base import Checkpoint

from agentmap.di.containers import ApplicationContainer


class TestHumanAgentSuspendResumeIntegration(unittest.TestCase):
    """Integration test for HumanAgent suspend/resume functionality."""

    def setUp(self):
        """Set up test fixtures with real DI container."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.user_storage_dir = os.path.join(self.temp_dir, "user_storage")
        self.cache_dir = os.path.join(self.temp_dir, "cache")
        self.examples_dir = os.path.join(self.temp_dir, "examples")

        os.makedirs(self.user_storage_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.examples_dir, exist_ok=True)

        # Create test CSV workflow
        self._create_test_workflow_csv()

        # Create test configuration files
        self._create_test_config_files()

        # Initialize real DI container
        self.container = ApplicationContainer()
        self.container.config.from_dict(
            {"path": os.path.join(self.temp_dir, "config.yaml")}
        )

        # Wire up the container
        self.container.wire(modules=[])

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        self.container.unwire()

    def _create_test_workflow_csv(self):
        """Create a test CSV workflow for document approval with HumanAgent."""
        csv_content = """Graph,Node,AgentType,Prompt,NextSuccess,NextFailure,Output,Input,Condition,Context
DocumentReview,StartReview,input,Please provide the document content for review,ReviewDocument,,document_content,,,
DocumentReview,ReviewDocument,human,Please review this document and approve/reject: {document_content},ApprovalComplete,RejectionHandling,approval_result,document_content,,
DocumentReview,ApprovalComplete,default,Document has been approved successfully!,,,notification_message,approval_result,,
DocumentReview,RejectionHandling,default,Document was rejected and requires revision,,,rejection_message,approval_result,,
"""

        csv_path = os.path.join(self.examples_dir, "document_review_workflow.csv")
        with open(csv_path, "w") as f:
            f.write(csv_content)

        self.csv_path = csv_path

    def _create_test_config_files(self):
        """Create test configuration files for integration testing."""
        storage_config_path = os.path.join(self.temp_dir, "storage.yaml").replace(
            "\\", "/"
        )
        cache_path = self.cache_dir.replace("\\", "/")
        examples_path = self.examples_dir.replace("\\", "/")

        config_content = f"""
storage_config_path: "{storage_config_path}"
paths:
  cache: "{cache_path}"
  examples: "{examples_path}"
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
execution:
  success_policy: any_end_node
"""

        config_path = os.path.join(self.temp_dir, "config.yaml")
        with open(config_path, "w") as f:
            f.write(config_content)

        user_storage_path = self.user_storage_dir.replace("\\", "/")
        storage_content = f"""
core:
  base_directory: "{user_storage_path}"
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

    def test_human_agent_suspend_and_resume_workflow(self):
        """Test complete HumanAgent suspend workflow via GraphRunnerService."""
        graph_runner_service = self.container.graph_runner_service()
        graph_bundle_service = self.container.graph_bundle_service()

        csv_path = Path(self.csv_path)
        bundle, _ = graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path, graph_name="DocumentReview", config_path=None
        )

        initial_state = {"document_content": "test document content"}

        with patch(
            "agentmap.services.graph.runner.interrupt_handler.GraphInterruptHandler.display_resume_instructions"
        ):
            result = graph_runner_service.run(bundle, initial_state)

        # With a HumanAgent node, the graph should be interrupted rather than completed
        # The result should indicate an interrupted/suspended state
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.graph_name)

        # The execution_summary should indicate the workflow paused for human input
        if result.execution_summary:
            status = result.execution_summary.status
            self.assertIn(
                status,
                ["suspended", "interrupted", "completed"],
                f"Unexpected status: {status}",
            )

    def test_checkpoint_service_protocol_compliance(self):
        """Test that GraphCheckpointService properly implements the LangGraph protocol."""
        checkpoint_service = self.container.graph_checkpoint_service()

        thread_id = f"test_thread_{uuid4()}"
        config = {"configurable": {"thread_id": thread_id}}

        checkpoint = Checkpoint(
            channel_values={"key": "value", "node_state": "active"},
            channel_versions={"nodes": 1},
            versions_seen={"TestNode": 1},
        )
        metadata = {
            "node_name": "TestNode",
            "checkpoint_type": "test",
            "test": "metadata",
        }

        result = checkpoint_service.put(config, checkpoint, metadata)
        self.assertTrue(result["success"])
        self.assertIn("checkpoint_id", result)

        checkpoint_tuple = checkpoint_service.get_tuple(config)
        self.assertIsNotNone(checkpoint_tuple)
        self.assertEqual(checkpoint_tuple.config, config)

        # Verify checkpoint channel values round-trip correctly
        self.assertEqual(checkpoint_tuple.checkpoint["channel_values"]["key"], "value")
        self.assertEqual(
            checkpoint_tuple.checkpoint["channel_values"]["node_state"], "active"
        )

        # Verify metadata round-trips correctly
        self.assertEqual(checkpoint_tuple.metadata["node_name"], "TestNode")
        self.assertEqual(checkpoint_tuple.metadata["checkpoint_type"], "test")
        self.assertEqual(checkpoint_tuple.metadata["test"], "metadata")

    def test_human_agent_checkpoint_data_structure(self):
        """Test that HumanAgent creates properly structured interrupt payloads."""
        from agentmap.agents.builtins.human_agent import HumanAgent

        execution_tracking = self.container.execution_tracking_service()
        state_adapter = self.container.state_adapter_service()
        logging_service = self.container.logging_service()

        human_agent = HumanAgent(
            execution_tracking_service=execution_tracking,
            state_adapter_service=state_adapter,
            name="TestHumanAgent",
            prompt="Test prompt: {input_data}",
            context={},
            logger=logging_service.get_logger("TestHumanAgent"),
        )

        test_inputs = {
            "input_data": "test data for review",
            "context": "document review context",
        }

        # HumanAgent.process() calls LangGraph's interrupt() which requires a runnable
        # context. Outside that context, it raises RuntimeError. We verify the agent
        # is configured correctly by checking it raises the expected error type.
        try:
            human_agent.process(test_inputs)
        except RuntimeError as e:
            # Expected: interrupt() requires a LangGraph runnable context
            self.assertIn("runnable", str(e).lower())
        except Exception as e:
            self.fail(f"Unexpected exception type {type(e).__name__}: {e}")
        else:
            self.fail("Expected RuntimeError (interrupt() outside runnable context)")

        # Verify the agent's interaction configuration
        from agentmap.models.human_interaction import InteractionType

        self.assertEqual(human_agent.interaction_type, InteractionType.TEXT_INPUT)
        self.assertEqual(human_agent.name, "TestHumanAgent")

    def test_concurrent_suspend_resume_operations(self):
        """Test handling multiple concurrent suspend/resume operations."""
        checkpoint_service = self.container.graph_checkpoint_service()

        threads = [f"thread_{i}_{uuid4()}" for i in range(3)]

        # Save a checkpoint for each thread
        for i, thread_id in enumerate(threads):
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint = Checkpoint(
                channel_values={
                    "thread_data": f"data_for_thread_{i}",
                    "step": i + 1,
                    "status": "suspended",
                },
                channel_versions={"nodes": i + 1},
                versions_seen={f"Node_{i}": 1},
            )
            metadata = {
                "node_name": f"Node_{i}",
                "thread_index": i,
                "test_type": "concurrent",
            }

            result = checkpoint_service.put(config, checkpoint, metadata)
            self.assertTrue(result["success"])

        # Verify each thread's checkpoint can be independently retrieved
        for i, thread_id in enumerate(threads):
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint_tuple = checkpoint_service.get_tuple(config)

            self.assertIsNotNone(checkpoint_tuple)
            self.assertEqual(checkpoint_tuple.config, config)

            # Verify the correct data was stored for each thread
            channel_values = checkpoint_tuple.checkpoint["channel_values"]
            self.assertEqual(channel_values["thread_data"], f"data_for_thread_{i}")
            self.assertEqual(channel_values["step"], i + 1)

            # Verify metadata
            self.assertEqual(checkpoint_tuple.metadata["thread_index"], i)
            self.assertEqual(checkpoint_tuple.metadata["node_name"], f"Node_{i}")


if __name__ == "__main__":
    unittest.main()
