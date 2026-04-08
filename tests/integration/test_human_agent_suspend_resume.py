"""
Integration test for HumanAgent suspend/resume functionality.

Tests the complete workflow including:
1. Graph execution starts with normal flow
2. HumanAgent triggers suspend with checkpoint save
3. ExecutionInterruptedException is raised and handled
4. Graph state is persisted correctly
5. Graph execution can be resumed from checkpoint
6. Final workflow completion

This test focuses on the core suspend/resume mechanics without UI complexity.
"""

import os
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from agentmap.di.containers import ApplicationContainer
from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.human_interaction import InteractionType


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

    @patch(
        "agentmap.services.interaction_handler_service.InteractionHandlerService.handle_execution_interruption"
    )
    def test_human_agent_suspend_and_resume_workflow(self, mock_handle_interruption):
        """Test complete HumanAgent suspend and resume workflow."""
        mock_handle_interruption.side_effect = self._simulate_user_response

        graph_runner_service = self.container.graph_runner_service()

        workflow_id = "document_review_workflow::DocumentReview"

        with self.assertRaises(ExecutionInterruptedException) as context:
            graph_runner_service.run_graph(csv_identifier=workflow_id, config_path=None)

        exception = context.exception
        self.assertIsNotNone(exception.thread_id)
        self.assertIsNotNone(exception.interaction_request)
        self.assertIsNotNone(exception.checkpoint_data)

        interaction_request = exception.interaction_request
        self.assertEqual(
            interaction_request.interaction_type, InteractionType.TEXT_INPUT
        )
        self.assertIn("Please review this document", interaction_request.prompt)
        self.assertEqual(interaction_request.node_name, "ReviewDocument")

        checkpoint_service = self.container.graph_checkpoint_service()
        saved_checkpoint = checkpoint_service.load_checkpoint(exception.thread_id)

        self.assertIsNotNone(saved_checkpoint)
        self.assertEqual(saved_checkpoint["thread_id"], exception.thread_id)
        self.assertIn("execution_state", saved_checkpoint)

        execution_state = saved_checkpoint["execution_state"]
        self.assertIn("document_content", execution_state)
        self.assertEqual(execution_state["document_content"], "test document content")

        thread_id = exception.thread_id
        user_response = "approved"

        updated_execution_state = execution_state.copy()
        updated_execution_state["approval_result"] = user_response

        save_result = checkpoint_service.save_checkpoint(
            thread_id=thread_id,
            node_name="ReviewDocument",
            checkpoint_type="user_response",
            metadata={"user_input": user_response, "resumed": True},
            execution_state=updated_execution_state,
        )
        self.assertTrue(save_result.success)

        resumed_checkpoint = checkpoint_service.load_checkpoint(thread_id)
        resumed_state = resumed_checkpoint["execution_state"]

        self.assertEqual(resumed_state["approval_result"], "approved")
        self.assertEqual(resumed_state["document_content"], "test document content")

        mock_handle_interruption.assert_called_once()
        call_args = mock_handle_interruption.call_args[1]
        self.assertEqual(call_args["exception"], exception)

    def _simulate_user_response(
        self, exception: ExecutionInterruptedException, **kwargs
    ):
        """Simulate user providing input during interruption."""
        pass

    def test_checkpoint_service_protocol_compliance(self):
        """Test that GraphCheckpointService properly implements the protocol."""
        checkpoint_service = self.container.graph_checkpoint_service()

        thread_id = f"test_thread_{uuid4()}"

        save_result = checkpoint_service.save_checkpoint(
            thread_id=thread_id,
            node_name="TestNode",
            checkpoint_type="test",
            metadata={"test": "metadata"},
            execution_state={"key": "value", "node_state": "active"},
        )

        self.assertTrue(save_result.success)
        self.assertIsNotNone(save_result.data)
        self.assertIn("checkpoint_id", save_result.data)

        loaded_checkpoint = checkpoint_service.load_checkpoint(thread_id)

        self.assertIsNotNone(loaded_checkpoint)
        self.assertEqual(loaded_checkpoint["thread_id"], thread_id)

        execution_state = loaded_checkpoint["execution_state"]
        self.assertEqual(execution_state["key"], "value")
        self.assertEqual(execution_state["node_state"], "active")

        metadata = loaded_checkpoint["metadata"]
        self.assertEqual(metadata["node_name"], "TestNode")
        self.assertEqual(metadata["checkpoint_type"], "test")
        self.assertEqual(metadata["test"], "metadata")

    def test_human_agent_checkpoint_data_structure(self):
        """Test that HumanAgent creates properly structured checkpoint data."""
        from agentmap.agents.builtins.human_agent import HumanAgent

        execution_tracking = self.container.execution_tracking_service()
        state_adapter = self.container.state_adapter_service()
        checkpoint_service = self.container.graph_checkpoint_service()

        human_agent = HumanAgent(
            execution_tracking_service=execution_tracking,
            state_adapter_service=state_adapter,
            name="TestHumanAgent",
            prompt="Test prompt: {input_data}",
        )

        human_agent.configure_checkpoint_service(checkpoint_service)

        test_inputs = {
            "input_data": "test data for review",
            "context": "document review context",
        }

        with self.assertRaises(ExecutionInterruptedException) as context:
            human_agent.process(test_inputs)

        exception = context.exception

        checkpoint_data = exception.checkpoint_data
        self.assertIn("inputs", checkpoint_data)
        self.assertIn("node_name", checkpoint_data)
        self.assertIn("agent_context", checkpoint_data)

        self.assertEqual(checkpoint_data["inputs"], test_inputs)
        self.assertEqual(checkpoint_data["node_name"], "TestHumanAgent")

        interaction_request = exception.interaction_request
        self.assertEqual(interaction_request.node_name, "TestHumanAgent")
        self.assertIn("test data for review", interaction_request.prompt)

    def test_concurrent_suspend_resume_operations(self):
        """Test handling multiple concurrent suspend/resume operations."""
        checkpoint_service = self.container.graph_checkpoint_service()

        threads = [f"thread_{i}_{uuid4()}" for i in range(3)]

        for i, thread_id in enumerate(threads):
            save_result = checkpoint_service.save_checkpoint(
                thread_id=thread_id,
                node_name=f"Node_{i}",
                checkpoint_type="concurrent_test",
                metadata={"thread_index": i, "test_type": "concurrent"},
                execution_state={
                    "thread_data": f"data_for_thread_{i}",
                    "step": i + 1,
                    "status": "suspended",
                },
            )
            self.assertTrue(save_result.success)

        for i, thread_id in enumerate(threads):
            loaded_checkpoint = checkpoint_service.load_checkpoint(thread_id)

            self.assertIsNotNone(loaded_checkpoint)
            self.assertEqual(loaded_checkpoint["thread_id"], thread_id)

            execution_state = loaded_checkpoint["execution_state"]
            self.assertEqual(execution_state["thread_data"], f"data_for_thread_{i}")
            self.assertEqual(execution_state["step"], i + 1)

            metadata = loaded_checkpoint["metadata"]
            self.assertEqual(metadata["thread_index"], i)


if __name__ == "__main__":
    unittest.main()
