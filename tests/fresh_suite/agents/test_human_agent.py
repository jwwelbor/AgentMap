"""
Unit tests for HumanAgent following AgentMap's testing patterns.

Tests verify interruption mechanism, checkpoint saving, interaction request creation,
and proper exception raising for human-in-the-loop functionality.
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.agents.builtins.human_agent import HumanAgent
from agentmap.models.human_interaction import InteractionType
from tests.utils.mock_service_factory import MockServiceFactory


class TestHumanAgent(unittest.TestCase):
    """Unit tests for HumanAgent using pure Mock objects."""

    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )
        self.mock_state_adapter_service.get_inputs = Mock()
        self.mock_state_adapter_service.get_inputs.return_value = {"user_data": None}

        # Get the mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(HumanAgent)

        # Create HumanAgent instance with basic configuration
        self.agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="test_human_agent",
            prompt="Please provide your input: {user_data}",
            context={
                "input_fields": ["user_data"],
                "output_field": "human_response",
                "interaction_type": "text_input",
                "timeout_seconds": 300,
                "default_option": "continue",
            },
            logger=self.mock_logger,
        )

        # Create mock execution tracker
        self.mock_execution_tracker = Mock()
        self.mock_execution_tracker.thread_id = "test-thread-123"
        self.agent.set_execution_tracker(self.mock_execution_tracker)

    @patch("agentmap.agents.builtins.human_agent.interrupt")
    def test_resume_sets_output_field_on_state(self, mock_interrupt):
        """HumanAgent run() should put resume value into configured output field."""

        resume_payload = {"action": "submit", "data": {"text": "approved"}}
        mock_interrupt.return_value = resume_payload

        initial_state = {"user_data": "need approval"}
        self.mock_state_adapter_service.get_inputs.return_value = {
            "user_data": "need approval"
        }

        result_state = self.agent.run(initial_state)

        # NEW BEHAVIOR: Returns partial state update (only output field)
        # set_value is not called - just returns {output_field: value}
        self.assertIn("human_response", result_state)
        self.assertEqual(result_state["human_response"], "approved")
        self.assertEqual(len(result_state), 1)  # Only output field

    @patch("agentmap.agents.builtins.human_agent.interrupt")
    def test_human_agent_interrupts_execution(self, mock_interrupt):
        """Test that HumanAgent calls interrupt() with correct metadata."""
        from langgraph.errors import GraphInterrupt

        inputs = {"user_data": "test input"}

        # Configure interrupt to raise GraphInterrupt (simulating first call)
        mock_interrupt.side_effect = GraphInterrupt(
            [{"type": "human_interaction", "thread_id": "test-thread-123"}]
        )

        # Test that process() raises GraphInterrupt
        with self.assertRaises(GraphInterrupt):
            self.agent.process(inputs)

        # Verify interrupt was called with correct metadata
        mock_interrupt.assert_called_once()
        call_args = mock_interrupt.call_args[0][0]

        self.assertEqual(call_args["type"], "human_interaction")
        self.assertEqual(call_args["thread_id"], "test-thread-123")
        self.assertEqual(call_args["node_name"], "test_human_agent")
        self.assertEqual(call_args["interaction_type"], "text_input")
        self.assertEqual(call_args["prompt"], "Please provide your input: test input")
        self.assertEqual(call_args["inputs"], inputs)
        self.assertEqual(call_args["timeout_seconds"], 300)

    @patch("agentmap.agents.builtins.human_agent.interrupt")
    def test_interrupt_metadata_structure(self, mock_interrupt):
        """Test that interrupt is called with complete metadata structure."""
        from langgraph.errors import GraphInterrupt

        inputs = {"user_data": "test input"}

        # Configure interrupt to raise GraphInterrupt
        mock_interrupt.side_effect = GraphInterrupt([{}])

        # Execute and expect interruption
        with self.assertRaises(GraphInterrupt):
            self.agent.process(inputs)

        # Verify interrupt was called
        mock_interrupt.assert_called_once()

        # Verify metadata structure
        call_args = mock_interrupt.call_args[0][0]

        self.assertEqual(call_args["type"], "human_interaction")
        self.assertEqual(call_args["thread_id"], "test-thread-123")
        self.assertEqual(call_args["node_name"], "test_human_agent")
        self.assertEqual(call_args["interaction_type"], "text_input")
        self.assertEqual(call_args["prompt"], "Please provide your input: test input")
        self.assertEqual(call_args["inputs"], inputs)
        self.assertEqual(call_args["options"], [])
        self.assertEqual(call_args["default_option"], "continue")
        self.assertEqual(call_args["timeout_seconds"], 300)

    @patch("agentmap.agents.builtins.human_agent.interrupt")
    def test_interaction_request_creation(self, mock_interrupt):
        """Test that interrupt metadata has all required fields."""
        from langgraph.errors import GraphInterrupt

        inputs = {"user_data": "test input", "session_id": "sess_123"}

        # Configure interrupt to raise GraphInterrupt
        mock_interrupt.side_effect = GraphInterrupt([{}])

        with self.assertRaises(GraphInterrupt):
            self.agent.process(inputs)

        call_args = mock_interrupt.call_args[0][0]

        # Verify all required fields are present
        self.assertEqual(call_args["type"], "human_interaction")
        self.assertEqual(call_args["thread_id"], "test-thread-123")
        self.assertEqual(call_args["node_name"], "test_human_agent")
        self.assertEqual(call_args["interaction_type"], "text_input")
        self.assertEqual(call_args["prompt"], "Please provide your input: test input")
        self.assertEqual(call_args["inputs"], inputs)
        self.assertEqual(call_args["options"], [])
        self.assertEqual(call_args["timeout_seconds"], 300)
        self.assertIn("context", call_args)

    @patch("agentmap.agents.builtins.human_agent.interrupt")
    def test_thread_id_generation(self, mock_interrupt):
        """Test that unique thread IDs are created when not available from tracker."""
        from langgraph.errors import GraphInterrupt

        inputs = {"user_data": "test input"}

        # Test without execution tracker (should generate new UUID)
        self.agent.set_execution_tracker(None)

        # Configure interrupt to raise GraphInterrupt
        mock_interrupt.side_effect = GraphInterrupt([{}])

        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="generated-uuid-456")

            with self.assertRaises(GraphInterrupt):
                self.agent.process(inputs)

            # Verify UUID was generated
            mock_uuid.assert_called_once()
            call_args = mock_interrupt.call_args[0][0]
            self.assertEqual(call_args["thread_id"], "generated-uuid-456")

        # Reset mocks
        mock_interrupt.reset_mock()
        mock_interrupt.side_effect = GraphInterrupt([{}])

        # Test with execution tracker without thread_id attribute
        mock_tracker_no_id = Mock(spec=[])  # No thread_id attribute
        self.agent.set_execution_tracker(mock_tracker_no_id)

        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="generated-uuid-789")

            with self.assertRaises(GraphInterrupt):
                self.agent.process(inputs)

            mock_uuid.assert_called_once()
            call_args = mock_interrupt.call_args[0][0]
            self.assertEqual(call_args["thread_id"], "generated-uuid-789")

    @patch("agentmap.agents.builtins.human_agent.interrupt")
    def test_configuration_options(self, mock_interrupt):
        """Test different interaction types and configurations."""
        from langgraph.errors import GraphInterrupt

        # Test approval interaction type
        approval_agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="approval_agent",
            prompt="Do you approve this action?",
            context={"interaction_type": "approval", "options": ["yes", "no"]},
            logger=self.mock_logger,
        )
        approval_agent.set_execution_tracker(self.mock_execution_tracker)

        # Configure interrupt to raise GraphInterrupt
        mock_interrupt.side_effect = GraphInterrupt([{}])

        with self.assertRaises(GraphInterrupt):
            approval_agent.process({"request": "delete user data"})

        call_args = mock_interrupt.call_args[0][0]
        self.assertEqual(call_args["interaction_type"], "approval")
        self.assertEqual(call_args["options"], ["yes", "no"])

        # Reset mock for next test
        mock_interrupt.reset_mock()

        # Test choice interaction type
        choice_agent = HumanAgent(
            name="choice_agent",
            prompt="Select an option:",
            context={
                "interaction_type": "choice",
                "options": ["option1", "option2", "option3"],
            },
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        choice_agent.set_execution_tracker(self.mock_execution_tracker)

        with self.assertRaises(GraphInterrupt):
            choice_agent.process({"data": "test"})

        call_args = mock_interrupt.call_args[0][0]
        self.assertEqual(call_args["interaction_type"], "choice")
        self.assertEqual(call_args["options"], ["option1", "option2", "option3"])

        # Test invalid interaction type (should default to text_input)
        invalid_agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="invalid_agent",
            prompt="Test prompt",
            context={"interaction_type": "invalid_type"},
            logger=self.mock_logger,
        )

        # Should log warning and default to text_input
        self.assertEqual(invalid_agent.interaction_type, InteractionType.TEXT_INPUT)

        # Verify warning was logged
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(
            any("Invalid interaction type" in call[1] for call in warning_calls)
        )

    @patch("agentmap.agents.builtins.human_agent.interrupt")
    def test_prompt_formatting_with_inputs(self, mock_interrupt):
        """Test that prompts are formatted correctly with input values."""
        from langgraph.errors import GraphInterrupt

        inputs = {"user_name": "Alice", "task": "review document"}

        # Create agent with formatted prompt
        formatted_agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="formatted_agent",
            prompt="Hello {user_name}, please {task}",
            context={"interaction_type": "text_input"},
            logger=self.mock_logger,
        )
        formatted_agent.set_execution_tracker(self.mock_execution_tracker)

        # Configure interrupt to raise GraphInterrupt
        mock_interrupt.side_effect = GraphInterrupt([{}])

        with self.assertRaises(GraphInterrupt):
            formatted_agent.process(inputs)

        call_args = mock_interrupt.call_args[0][0]
        self.assertEqual(call_args["prompt"], "Hello Alice, please review document")

    @patch("agentmap.agents.builtins.human_agent.interrupt")
    def test_prompt_formatting_fallback(self, mock_interrupt):
        """Test that prompt formatting falls back gracefully on error."""
        from langgraph.errors import GraphInterrupt

        inputs = {"incomplete": "data"}

        # Create agent with prompt that can't be formatted with given inputs
        fallback_agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="fallback_agent",
            prompt="Hello {missing_key}, please {another_missing}",
            context={"interaction_type": "text_input"},
            logger=self.mock_logger,
        )
        fallback_agent.set_execution_tracker(self.mock_execution_tracker)

        # Configure interrupt to raise GraphInterrupt
        mock_interrupt.side_effect = GraphInterrupt([{}])

        with self.assertRaises(GraphInterrupt):
            fallback_agent.process(inputs)

        call_args = mock_interrupt.call_args[0][0]
        # Should fallback to original prompt
        self.assertEqual(
            call_args["prompt"], "Hello {missing_key}, please {another_missing}"
        )

    # Checkpoint tests removed - HumanAgent now uses LangGraph's interrupt() directly
    # Checkpoint management is handled by LangGraph framework, not by the agent

    def test_agent_initialization(self):
        """Test that agent initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.agent.name, "test_human_agent")
        self.assertEqual(self.agent.prompt, "Please provide your input: {user_data}")
        self.assertEqual(self.agent.interaction_type, InteractionType.TEXT_INPUT)
        self.assertEqual(self.agent.timeout_seconds, 300)
        self.assertEqual(self.agent.default_option, "continue")
        self.assertEqual(self.agent.options, [])

        # Verify services are configured
        self.assertEqual(self.agent.logger, self.mock_logger)
        self.assertEqual(
            self.agent.execution_tracking_service, self.mock_execution_tracking_service
        )
        self.assertEqual(
            self.agent.state_adapter_service, self.mock_state_adapter_service
        )


if __name__ == "__main__":
    unittest.main()
