"""Unit tests for SuspendAgent messaging functionality.

Tests verify:
- Suspension message publishing
- Resume message publishing with duration
- Graph message publishing
- Message skipping when disabled
- Error handling when messaging service not configured
- Raw return value handling (not wrapped)
"""

import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from agentmap.agents.builtins.suspend_agent import SuspendAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestSuspendAgentMessaging(unittest.TestCase):
    """Verify SuspendAgent messaging features work correctly."""

    def setUp(self):
        """Set up common test fixtures."""
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )
        self.mock_state_adapter_service.get_inputs = Mock()
        self.mock_state_adapter_service.get_inputs.return_value = {
            "test_input": "test_value"
        }

        logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_logger = logging_service.get_class_logger(SuspendAgent)

        # Create mock messaging service
        self.mock_messaging_service = Mock()
        self.mock_messaging_service.apply_template = Mock()
        self.mock_messaging_service.publish_message = AsyncMock()

        # Mock execution tracker with thread_id
        self.mock_execution_tracker = Mock()
        self.mock_execution_tracker.thread_id = "thread-001"
        self.mock_execution_tracker.workflow_name = "test_workflow"
        self.mock_execution_tracker.graph_name = "test_graph"

    def _create_agent(self, context: dict) -> SuspendAgent:
        """Helper to create SuspendAgent with given context."""
        agent = SuspendAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="test_suspend",
            prompt="Wait for external process",
            context=context,
            logger=self.mock_logger,
        )
        agent.set_execution_tracker(self.mock_execution_tracker)
        return agent

    # --- Suspension Message Tests ---

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    @patch("agentmap.agents.builtins.suspend_agent.asyncio.create_task")
    def test_suspend_message_published_when_enabled(
        self, mock_create_task, mock_interrupt
    ):
        """Verify suspension message published when send_suspend_message in context."""
        # Arrange
        context = {
            "send_suspend_message": True,
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)
        agent.configure_messaging_service(self.mock_messaging_service)

        # Configure template response
        self.mock_messaging_service.apply_template.return_value = {
            "event": "suspended",
            "thread": "thread-001",
        }

        mock_interrupt.return_value = {"status": "approved"}

        initial_state = {"test_input": "test_value"}
        self.mock_state_adapter_service.get_inputs.return_value = initial_state

        # Act
        agent.run(initial_state)

        # Assert - verify apply_template called with correct payload
        self.mock_messaging_service.apply_template.assert_called_once()
        template_name, payload = self.mock_messaging_service.apply_template.call_args[0]

        self.assertEqual(template_name, "default_suspend")
        self.assertEqual(payload["event_type"], "workflow_suspended")
        self.assertEqual(payload["thread_id"], "thread-001")
        self.assertEqual(payload["node_name"], "test_suspend")
        self.assertEqual(payload["workflow"], "test_workflow")
        self.assertEqual(payload["graph"], "test_graph")
        self.assertIn("timestamp", payload)
        # Suspend message keeps 'inputs' field (NOT renamed to 'state')
        self.assertEqual(payload["inputs"], {"test_input": "test_value"})
        self.assertIn("context", payload)  # Must include context

        # Assert - verify publish_message called via asyncio.create_task
        mock_create_task.assert_called()
        # Get the coroutine that was passed to create_task
        call_args = mock_create_task.call_args_list
        # First call should be for suspension message
        suspension_call = call_args[0]
        self.assertIsNotNone(suspension_call)

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    def test_suspend_message_skipped_when_disabled(self, mock_interrupt):
        """Verify no suspension message when send_suspend_message not in context."""
        # Arrange
        context = {
            "input_fields": ["test_input"],
            "output_field": "result",
            # Note: send_suspend_message not present
        }
        agent = self._create_agent(context)
        agent.configure_messaging_service(self.mock_messaging_service)

        mock_interrupt.return_value = {"status": "approved"}

        initial_state = {"test_input": "test_value"}
        self.mock_state_adapter_service.get_inputs.return_value = initial_state

        # Act
        agent.run(initial_state)

        # Assert - no template applied, no message published
        self.mock_messaging_service.apply_template.assert_not_called()
        self.mock_messaging_service.publish_message.assert_not_called()

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    def test_suspend_message_raises_when_service_not_configured(self, mock_interrupt):
        """Verify ValueError when messaging_service is None but message requested."""
        # Arrange
        context = {
            "send_suspend_message": True,
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)
        # Note: NOT configuring messaging service

        # Configure interrupt to prevent actual interruption
        mock_interrupt.return_value = {"status": "approved"}

        inputs = {"test_input": "test_value"}

        # Act & Assert - Call process() directly to test exception
        # (BaseAgent.run() catches all exceptions and returns state)
        with self.assertRaises(ValueError) as cm:
            agent.process(inputs)

        self.assertIn(
            "Messaging service required but not configured", str(cm.exception)
        )
        self.assertIn("test_suspend", str(cm.exception))

    # --- Resume Message Tests ---

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    @patch("agentmap.agents.builtins.suspend_agent.asyncio.create_task")
    @patch("agentmap.agents.builtins.suspend_agent.time.time")
    def test_resume_message_published_when_enabled(
        self, mock_time, mock_create_task, mock_interrupt
    ):
        """Verify resume message published when send_resume_message in context."""
        # Arrange
        context = {
            "send_resume_message": True,
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)
        agent.configure_messaging_service(self.mock_messaging_service)

        # Mock time progression - need multiple calls for BaseAgent.run() timing
        # BaseAgent.run() calls time.time() at: start (line 204), end success (line 254), end error (line 294)
        # SuspendAgent.process() calls time.time() for suspend_timestamp and resume_timestamp
        mock_time.side_effect = [
            1000.0,
            1000.0,
            1005.5,
            1005.6,
        ]  # start, suspend, resume, end

        # Configure template response
        self.mock_messaging_service.apply_template.return_value = {
            "event": "resumed",
            "thread": "thread-001",
        }

        mock_interrupt.return_value = {"status": "approved"}

        initial_state = {"test_input": "test_value"}
        self.mock_state_adapter_service.get_inputs.return_value = initial_state

        # Act
        agent.run(initial_state)

        # Assert - verify apply_template called for resume message
        # Should be called once for resume message
        resume_calls = [
            call
            for call in self.mock_messaging_service.apply_template.call_args_list
            if len(call[0]) > 1 and call[0][1].get("event_type") == "workflow_resumed"
        ]
        self.assertEqual(len(resume_calls), 1)

        template_name, payload = resume_calls[0][0]
        self.assertEqual(template_name, "default_resume")
        self.assertEqual(payload["event_type"], "workflow_resumed")
        self.assertEqual(payload["action"], "resume")  # NEW: serverless resume action
        self.assertEqual(payload["thread_id"], "thread-001")
        self.assertEqual(payload["node_name"], "test_suspend")
        self.assertEqual(payload["graph"], "test_graph")
        self.assertEqual(payload["workflow"], "test_workflow")
        self.assertEqual(payload["resume_value"], {"status": "approved"})
        # Duration should be approximately 5.5 seconds
        self.assertGreater(payload["suspension_duration_seconds"], 5.0)
        self.assertLess(payload["suspension_duration_seconds"], 6.0)
        self.assertIn("timestamp", payload)
        self.assertIn("context", payload)  # Must include context per user requirement

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    @patch("agentmap.agents.builtins.suspend_agent.time.time")
    def test_resume_message_includes_duration(self, mock_time, mock_interrupt):
        """Verify resume message duration calculated correctly."""
        # Arrange
        context = {
            "send_resume_message": True,
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)
        agent.configure_messaging_service(self.mock_messaging_service)

        # Mock time: suspend at 100s, resume at 110s = 10s duration
        # Need 4 calls: BaseAgent.run() start, suspend_timestamp, resume_timestamp, BaseAgent.run() end
        mock_time.side_effect = [100.0, 100.0, 110.0, 110.1]

        self.mock_messaging_service.apply_template.return_value = {}
        mock_interrupt.return_value = {"result": "success"}

        initial_state = {"test_input": "test_value"}
        self.mock_state_adapter_service.get_inputs.return_value = initial_state

        # Act
        agent.run(initial_state)

        # Assert - verify duration in payload
        resume_calls = [
            call
            for call in self.mock_messaging_service.apply_template.call_args_list
            if len(call[0]) > 1 and call[0][1].get("event_type") == "workflow_resumed"
        ]
        self.assertEqual(len(resume_calls), 1)

        _, payload = resume_calls[0][0]
        self.assertEqual(payload["suspension_duration_seconds"], 10.0)
        self.assertEqual(payload["action"], "resume")  # Verify resume action present
        self.assertIn("context", payload)  # Verify context present

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    @patch("agentmap.agents.builtins.suspend_agent.time.time")
    def test_resume_message_raises_when_service_not_configured(
        self, mock_time, mock_interrupt
    ):
        """Verify ValueError when messaging_service is None but resume message requested."""
        # Arrange
        context = {
            "send_resume_message": True,
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)
        # Note: NOT configuring messaging service

        # Mock time for duration calculation - need 2 calls for suspend and resume timestamps
        mock_time.side_effect = [1000.0, 1005.0]
        mock_interrupt.return_value = {"status": "approved"}

        inputs = {"test_input": "test_value"}

        # Act & Assert - Call process() directly to test exception
        # (BaseAgent.run() catches all exceptions and returns state)
        with self.assertRaises(ValueError) as cm:
            agent.process(inputs)

        self.assertIn(
            "Messaging service required but not configured", str(cm.exception)
        )

    # --- Graph Message Tests ---

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    @patch("agentmap.agents.builtins.suspend_agent.asyncio.create_task")
    def test_graph_message_published_when_enabled(
        self, mock_create_task, mock_interrupt
    ):
        """Verify graph message published when send_graph_message in context."""
        # Arrange
        context = {
            "send_graph_message": True,
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)
        agent.configure_messaging_service(self.mock_messaging_service)

        # Configure template response
        self.mock_messaging_service.apply_template.return_value = {
            "event": "graph_event",
            "thread": "thread-001",
        }

        mock_interrupt.return_value = {"status": "approved"}

        initial_state = {"test_input": "test_value"}
        self.mock_state_adapter_service.get_inputs.return_value = initial_state

        # Act
        agent.run(initial_state)

        # Assert - verify apply_template called for graph message
        graph_calls = [
            call
            for call in self.mock_messaging_service.apply_template.call_args_list
            if len(call[0]) > 1
            and call[0][1].get("event_type") == "workflow_graph_trigger"
        ]
        self.assertEqual(len(graph_calls), 1)

        template_name, payload = graph_calls[0][0]
        self.assertEqual(template_name, "default_graph")
        self.assertEqual(payload["event_type"], "workflow_graph_trigger")
        self.assertEqual(payload["thread_id"], "thread-001")
        self.assertEqual(payload["node_name"], "test_suspend")
        self.assertEqual(payload["graph"], "test_graph")
        self.assertEqual(payload["workflow"], "test_workflow")
        # Graph message has 'state' field (for serverless) instead of 'inputs'
        self.assertEqual(payload["state"], {"test_input": "test_value"})
        self.assertIn("timestamp", payload)
        self.assertIn("context", payload)

        # Verify asyncio.create_task called for graph message
        mock_create_task.assert_called()

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    def test_graph_message_skipped_when_disabled(self, mock_interrupt):
        """Verify no graph message when send_graph_message not in context."""
        # Arrange
        context = {
            "input_fields": ["test_input"],
            "output_field": "result",
            # Note: send_graph_message not present
        }
        agent = self._create_agent(context)
        agent.configure_messaging_service(self.mock_messaging_service)

        mock_interrupt.return_value = {"status": "approved"}

        initial_state = {"test_input": "test_value"}
        self.mock_state_adapter_service.get_inputs.return_value = initial_state

        # Act
        agent.run(initial_state)

        # Assert - no graph message should be published
        graph_calls = [
            call
            for call in self.mock_messaging_service.apply_template.call_args_list
            if len(call[0]) > 1
            and call[0][1].get("event_type") == "workflow_graph_trigger"
        ]
        self.assertEqual(len(graph_calls), 0)

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    def test_graph_message_raises_when_service_not_configured(self, mock_interrupt):
        """Verify ValueError when messaging_service is None but graph message requested."""
        # Arrange
        context = {
            "send_graph_message": True,
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)
        # Note: NOT configuring messaging service

        # Configure interrupt to prevent actual interruption
        mock_interrupt.return_value = {"status": "approved"}

        inputs = {"test_input": "test_value"}

        # Act & Assert - Call process() directly to test exception
        # (BaseAgent.run() catches all exceptions and returns state)
        with self.assertRaises(ValueError) as cm:
            agent.process(inputs)

        self.assertIn(
            "Messaging service required but not configured", str(cm.exception)
        )

    # --- Return Value Tests ---

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    def test_returns_raw_resume_value(self, mock_interrupt):
        """Verify SuspendAgent returns raw resume value (not wrapped)."""
        # Arrange
        context = {
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)

        # Return complex object
        resume_payload = {
            "transaction_id": "TXN-123",
            "status": "approved",
            "amount": 5000,
        }
        mock_interrupt.return_value = resume_payload

        initial_state = {"test_input": "test_value"}
        self.mock_state_adapter_service.get_inputs.return_value = initial_state

        # Act
        result_state = agent.run(initial_state)

        # NEW BEHAVIOR: Returns partial state update (only output field)
        # set_value is not called - just returns {output_field: value}
        self.assertIn("result", result_state)
        self.assertEqual(result_state["result"], resume_payload)
        self.assertEqual(len(result_state), 1)  # Only output field

        # Verify NOT wrapped structure
        self.assertNotIn("resume_value", result_state["result"])
        self.assertNotIn("node_name", result_state["result"])

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    @patch("agentmap.agents.builtins.suspend_agent.time.time")
    def test_returns_none_when_resume_value_is_none(self, mock_time, mock_interrupt):
        """Verify SuspendAgent correctly handles None resume value."""
        # Arrange
        context = {
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)

        # Mock time for BaseAgent.run() - start and end times
        # No messaging, so only need BaseAgent.run() times
        # Adding extra value in case of additional time.time() calls during execution
        mock_time.side_effect = [1000.0, 1001.0, 1001.5]
        mock_interrupt.return_value = None

        # State includes result field with None value
        initial_state = {"test_input": "test_value", "result": None}
        self.mock_state_adapter_service.get_inputs.return_value = {
            "test_input": "test_value"
        }

        # Act
        result_state = agent.run(initial_state)

        # NEW BEHAVIOR: When output is None, BaseAgent.run() returns empty dict
        # (Line 250-266 in base_agent.py: if output_field and output is not None)
        # Since output is None, it skips setting the field and returns {}
        self.assertEqual(result_state, {})
        self.assertEqual(len(result_state), 0)

    # --- Custom Topic and Template Tests ---

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    @patch("agentmap.agents.builtins.suspend_agent.asyncio.create_task")
    def test_suspend_message_uses_custom_topic_and_template(
        self, mock_create_task, mock_interrupt
    ):
        """Verify suspension message uses custom topic and template from context."""
        # Arrange
        context = {
            "send_suspend_message": True,
            "suspend_message_topic": "custom_topic",
            "suspend_message_template": "custom_suspend_template",
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)
        agent.configure_messaging_service(self.mock_messaging_service)

        self.mock_messaging_service.apply_template.return_value = {}
        mock_interrupt.return_value = {}

        initial_state = {"test_input": "test_value"}
        self.mock_state_adapter_service.get_inputs.return_value = initial_state

        # Act
        agent.run(initial_state)

        # Assert - verify custom template used
        template_calls = [
            call
            for call in self.mock_messaging_service.apply_template.call_args_list
            if len(call[0]) > 1 and call[0][1].get("event_type") == "workflow_suspended"
        ]
        self.assertEqual(len(template_calls), 1)

        template_name, _ = template_calls[0][0]
        self.assertEqual(template_name, "custom_suspend_template")

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    @patch("agentmap.agents.builtins.suspend_agent.asyncio.create_task")
    def test_resume_message_uses_custom_topic_and_template(
        self, mock_create_task, mock_interrupt
    ):
        """Verify resume message uses custom topic and template from context."""
        # Arrange
        context = {
            "send_resume_message": True,
            "resume_message_topic": "custom_resume_topic",
            "resume_message_template": "custom_resume_template",
            "input_fields": ["test_input"],
            "output_field": "result",
        }
        agent = self._create_agent(context)
        agent.configure_messaging_service(self.mock_messaging_service)

        self.mock_messaging_service.apply_template.return_value = {}
        mock_interrupt.return_value = {}

        initial_state = {"test_input": "test_value"}
        self.mock_state_adapter_service.get_inputs.return_value = initial_state

        # Act
        agent.run(initial_state)

        # Assert - verify custom template used
        resume_calls = [
            call
            for call in self.mock_messaging_service.apply_template.call_args_list
            if len(call[0]) > 1 and call[0][1].get("event_type") == "workflow_resumed"
        ]
        self.assertEqual(len(resume_calls), 1)

        template_name, _ = resume_calls[0][0]
        self.assertEqual(template_name, "custom_resume_template")


if __name__ == "__main__":
    unittest.main()
