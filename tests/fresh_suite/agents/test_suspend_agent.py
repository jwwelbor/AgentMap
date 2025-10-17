"""Unit tests for SuspendAgent resume output mapping."""

import unittest
from unittest.mock import Mock, patch

from agentmap.agents.builtins.suspend_agent import SuspendAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestSuspendAgent(unittest.TestCase):
    """Verify suspend agent integrates resume value into state."""

    def setUp(self):
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )
        self.mock_state_adapter_service.get_inputs = Mock()
        self.mock_state_adapter_service.get_inputs.return_value = {
            "raw_input": None
        }

        logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_logger = logging_service.get_class_logger(SuspendAgent)

        self.agent = SuspendAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="wait_external",
            prompt="Wait for external result",
            context={
                "input_fields": ["raw_input"],
                "output_field": "external_result",
            },
            logger=self.mock_logger,
        )

        self.mock_execution_tracker = Mock()
        self.mock_execution_tracker.thread_id = "thread-001"
        self.agent.set_execution_tracker(self.mock_execution_tracker)

    @patch("agentmap.agents.builtins.suspend_agent.interrupt")
    def test_resume_sets_output_field_with_resume_bundle(self, mock_interrupt):
        """SuspendAgent run should store resume payload using configured output field."""

        resume_payload = {"result": "processed"}
        mock_interrupt.return_value = resume_payload

        initial_state = {"raw_input": {"payload": "pending"}}
        self.mock_state_adapter_service.get_inputs.return_value = {
            "raw_input": {"payload": "pending"}
        }

        result_state = self.agent.run(initial_state)

        # Current implementation returns simplified output without suspended/resumed flags
        expected_output = {
            "resume_value": resume_payload,
            "node_name": "wait_external",
        }
        self.mock_state_adapter_service.set_value.assert_called_with(
            initial_state,
            "external_result",
            expected_output,
        )
        self.assertIn("external_result", result_state)
        self.assertEqual(result_state["external_result"], expected_output)


if __name__ == "__main__":
    unittest.main()
