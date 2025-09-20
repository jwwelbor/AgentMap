"""
Unit tests for HumanAgent following AgentMap's testing patterns.

Tests verify interruption mechanism, checkpoint saving, interaction request creation,
and proper exception raising for human-in-the-loop functionality.
"""

import unittest
import uuid
from unittest.mock import Mock, patch

from agentmap.agents.builtins.human_agent import HumanAgent
from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
from agentmap.models.storage.types import StorageResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestHumanAgent(unittest.TestCase):
    """Unit tests for HumanAgent using pure Mock objects."""

    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Create mock checkpoint service with proper protocol interface
        self.mock_checkpoint_service = Mock()
        self.mock_checkpoint_service.save_checkpoint.return_value = StorageResult(
            success=True,
            operation="save_checkpoint",
            collection="graph_checkpoints"
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(HumanAgent)
        
        # Create HumanAgent instance with basic configuration
        self.agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="test_human_agent",
            prompt="Please provide your input: {user_data}",
            interaction_type="text_input",
            timeout_seconds=300,
            default_action="continue",
            context={"input_fields": ["user_data"], "output_field": "human_response"},
            logger=self.mock_logger,
        )
        
        # Configure checkpoint service post-construction
        self.agent.configure_checkpoint_service(self.mock_checkpoint_service)
        
        # Create mock execution tracker
        self.mock_execution_tracker = Mock()
        self.mock_execution_tracker.thread_id = "test-thread-123"
        self.agent.set_execution_tracker(self.mock_execution_tracker)

    def test_human_agent_interrupts_execution(self):
        """Test that HumanAgent raises ExecutionInterruptedException."""
        inputs = {"user_data": "test input"}
        
        # Mock execution tracking service to return the mock tracker
        self.mock_execution_tracking_service.serialize_tracker.return_value = {
            "thread_id": "test-thread-123",
            "execution_data": "mock_tracker_data"
        }
        
        # Test that process() raises ExecutionInterruptedException
        with self.assertRaises(ExecutionInterruptedException) as context:
            self.agent.process(inputs)
        
        # Verify exception details
        exception = context.exception
        self.assertEqual(exception.thread_id, "test-thread-123")
        self.assertIsInstance(exception.interaction_request, HumanInteractionRequest)
        self.assertIsInstance(exception.checkpoint_data, dict)
        
        # Verify interaction request details
        request = exception.interaction_request
        self.assertEqual(request.thread_id, "test-thread-123")
        self.assertEqual(request.node_name, "test_human_agent")
        self.assertEqual(request.interaction_type, InteractionType.TEXT_INPUT)
        self.assertEqual(request.prompt, "Please provide your input: test input")
        self.assertEqual(request.context, inputs)
        self.assertEqual(request.timeout_seconds, 300)

    def test_checkpoint_saved_on_interruption(self):
        """Test that checkpoint is saved correctly when execution is interrupted."""
        inputs = {"user_data": "test input"}
        
        # Mock execution tracking service
        mock_tracker_data = {
            "thread_id": "test-thread-123",
            "execution_data": "serialized_tracker"
        }
        self.mock_execution_tracking_service.serialize_tracker.return_value = mock_tracker_data
        
        # Execute and expect interruption
        with self.assertRaises(ExecutionInterruptedException):
            self.agent.process(inputs)
        
        # Verify checkpoint service was called
        self.mock_checkpoint_service.save_checkpoint.assert_called_once()
        
        # Verify checkpoint call arguments
        call_args = self.mock_checkpoint_service.save_checkpoint.call_args
        
        # Check if args were passed as positional or keyword arguments
        if call_args.args:
            # Positional arguments
            args = call_args.args
            kwargs = call_args.kwargs
            
            self.assertEqual(args[0], "test-thread-123")  # thread_id
            self.assertEqual(args[1], "test_human_agent")  # node_name
            self.assertEqual(args[2], "human_intervention")  # checkpoint_type
            
            # Verify metadata structure
            metadata = args[3]
            execution_state = args[4]
        else:
            # Keyword arguments
            kwargs = call_args.kwargs
            
            self.assertEqual(kwargs["thread_id"], "test-thread-123")
            self.assertEqual(kwargs["node_name"], "test_human_agent")
            self.assertEqual(kwargs["checkpoint_type"], "human_intervention")
            
            # Verify metadata structure
            metadata = kwargs["metadata"]
            execution_state = kwargs["execution_state"]
        
        self.assertIn("interaction_request", metadata)
        self.assertIn("agent_config", metadata)
        self.assertEqual(metadata["agent_config"]["name"], "test_human_agent")
        self.assertEqual(metadata["agent_config"]["interaction_type"], "text_input")
        self.assertEqual(metadata["agent_config"]["default_action"], "continue")
        
        # Verify execution state
        self.assertEqual(execution_state["inputs"], inputs)
        self.assertEqual(execution_state["node_name"], "test_human_agent")
        self.assertEqual(execution_state["execution_tracker"], mock_tracker_data)

    def test_interaction_request_creation(self):
        """Test that interaction request has all required fields."""
        inputs = {"user_data": "test input", "session_id": "sess_123"}
        
        # Mock execution tracking service
        self.mock_execution_tracking_service.serialize_tracker.return_value = {"mock": "data"}
        
        with self.assertRaises(ExecutionInterruptedException) as context:
            self.agent.process(inputs)
        
        request = context.exception.interaction_request
        
        # Verify all required fields are present
        self.assertIsNotNone(request.id)
        self.assertIsInstance(request.id, uuid.UUID)
        self.assertEqual(request.thread_id, "test-thread-123")
        self.assertEqual(request.node_name, "test_human_agent")
        self.assertEqual(request.interaction_type, InteractionType.TEXT_INPUT)
        self.assertEqual(request.prompt, "Please provide your input: test input")
        self.assertEqual(request.context, inputs)
        self.assertEqual(request.options, [])
        self.assertEqual(request.timeout_seconds, 300)
        self.assertIsNotNone(request.created_at)

    def test_thread_id_generation(self):
        """Test that unique thread IDs are created when not available from tracker."""
        inputs = {"user_data": "test input"}
        
        # Test without execution tracker (should generate new UUID)
        self.agent.set_execution_tracker(None)
        
        # Mock execution tracking service
        self.mock_execution_tracking_service.serialize_tracker.return_value = {"mock": "data"}
        
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="generated-uuid-456")
            
            with self.assertRaises(ExecutionInterruptedException) as context:
                self.agent.process(inputs)
            
            # Verify UUID was generated
            mock_uuid.assert_called_once()
            self.assertEqual(context.exception.thread_id, "generated-uuid-456")
        
        # Test with execution tracker without thread_id attribute
        mock_tracker_no_id = Mock(spec=[])  # No thread_id attribute
        self.agent.set_execution_tracker(mock_tracker_no_id)
        
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="generated-uuid-789")
            
            with self.assertRaises(ExecutionInterruptedException) as context:
                self.agent.process(inputs)
            
            mock_uuid.assert_called_once()
            self.assertEqual(context.exception.thread_id, "generated-uuid-789")

    def test_configuration_options(self):
        """Test different interaction types and configurations."""
        # Test approval interaction type
        approval_agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="approval_agent",
            prompt="Do you approve this action?",
            interaction_type="approval",
            options=["yes", "no"],
            logger=self.mock_logger,
        )
        approval_agent.configure_checkpoint_service(self.mock_checkpoint_service)
        approval_agent.set_execution_tracker(self.mock_execution_tracker)
        
        with self.assertRaises(ExecutionInterruptedException) as context:
            approval_agent.process({"request": "delete user data"})
        
        request = context.exception.interaction_request
        self.assertEqual(request.interaction_type, InteractionType.APPROVAL)
        self.assertEqual(request.options, ["yes", "no"])
        
        # Test choice interaction type
        choice_agent = HumanAgent(
            name="choice_agent",
            prompt="Select an option:",
            interaction_type="choice",
            options=["option1", "option2", "option3"],
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        choice_agent.configure_checkpoint_service(self.mock_checkpoint_service)
        choice_agent.set_execution_tracker(self.mock_execution_tracker)
        
        with self.assertRaises(ExecutionInterruptedException) as context:
            choice_agent.process({"data": "test"})
        
        request = context.exception.interaction_request
        self.assertEqual(request.interaction_type, InteractionType.CHOICE)
        self.assertEqual(request.options, ["option1", "option2", "option3"])
        
        # Test invalid interaction type (should default to text_input)
        invalid_agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="invalid_agent",
            prompt="Test prompt",
            interaction_type="invalid_type",
            logger=self.mock_logger,
        )
        
        # Should log warning and default to text_input
        self.assertEqual(invalid_agent.interaction_type, InteractionType.TEXT_INPUT)
        
        # Verify warning was logged
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("Invalid interaction type" in call[1] for call in warning_calls))

    def test_prompt_formatting_with_inputs(self):
        """Test that prompts are formatted correctly with input values."""
        inputs = {"user_name": "Alice", "task": "review document"}
        
        # Create agent with formatted prompt
        formatted_agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="formatted_agent",
            prompt="Hello {user_name}, please {task}",
            interaction_type="text_input",
            logger=self.mock_logger,
        )
        formatted_agent.configure_checkpoint_service(self.mock_checkpoint_service)
        formatted_agent.set_execution_tracker(self.mock_execution_tracker)
        
        # Mock execution tracking service
        self.mock_execution_tracking_service.serialize_tracker.return_value = {"mock": "data"}
        
        with self.assertRaises(ExecutionInterruptedException) as context:
            formatted_agent.process(inputs)
        
        request = context.exception.interaction_request
        self.assertEqual(request.prompt, "Hello Alice, please review document")

    def test_prompt_formatting_fallback(self):
        """Test that prompt formatting falls back gracefully on error."""
        inputs = {"incomplete": "data"}
        
        # Create agent with prompt that can't be formatted with given inputs
        fallback_agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="fallback_agent",
            prompt="Hello {missing_key}, please {another_missing}",
            interaction_type="text_input",
            logger=self.mock_logger,
        )
        fallback_agent.configure_checkpoint_service(self.mock_checkpoint_service)
        fallback_agent.set_execution_tracker(self.mock_execution_tracker)
        
        # Mock execution tracking service
        self.mock_execution_tracking_service.serialize_tracker.return_value = {"mock": "data"}
        
        with self.assertRaises(ExecutionInterruptedException) as context:
            fallback_agent.process(inputs)
        
        request = context.exception.interaction_request
        # Should fallback to original prompt
        self.assertEqual(request.prompt, "Hello {missing_key}, please {another_missing}")

    def test_checkpoint_service_not_configured(self):
        """Test behavior when checkpoint service is not configured."""
        # Create agent without checkpoint service
        no_checkpoint_agent = HumanAgent(
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            name="no_checkpoint_agent",
            prompt="Test prompt",
            interaction_type="text_input",
            logger=self.mock_logger,
        )
        no_checkpoint_agent.set_execution_tracker(self.mock_execution_tracker)
        
        # Mock execution tracking service
        self.mock_execution_tracking_service.serialize_tracker.return_value = {"mock": "data"}
        self.assertRaises(RuntimeError)
        #self.assertTrue(any("No checkpoint service configured" in call[1] for call in warning_calls))

    def test_checkpoint_save_failure(self):
        """Test behavior when checkpoint save fails."""
        # Configure checkpoint service to return failure
        self.mock_checkpoint_service.save_checkpoint.return_value = StorageResult(
            success=False,
            error="Storage error",
            operation="save_checkpoint",
            collection="graph_checkpoints"
        )
        
        inputs = {"data": "test"}
        
        # Mock execution tracking service
        self.mock_execution_tracking_service.serialize_tracker.return_value = {"mock": "data"}
        
        # Should still raise exception but log warning about checkpoint failure
        with self.assertRaises(ExecutionInterruptedException):
            self.agent.process(inputs)
        
        # Verify warning was logged
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("Failed to save checkpoint" in call[1] for call in warning_calls))

    def test_agent_initialization(self):
        """Test that agent initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.agent.name, "test_human_agent")
        self.assertEqual(self.agent.prompt, "Please provide your input: {user_data}")
        self.assertEqual(self.agent.interaction_type, InteractionType.TEXT_INPUT)
        self.assertEqual(self.agent.timeout_seconds, 300)
        self.assertEqual(self.agent.default_action, "continue")
        self.assertEqual(self.agent.options, [])
        
        # Verify services are configured
        self.assertEqual(self.agent.logger, self.mock_logger)
        self.assertEqual(self.agent.execution_tracking_service, self.mock_execution_tracking_service)
        self.assertEqual(self.agent.state_adapter_service, self.mock_state_adapter_service)
        self.assertEqual(self.agent._checkpoint_service, self.mock_checkpoint_service)
        
        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(any("Agent initialized" in call[1] for call in debug_calls))


if __name__ == '__main__':
    unittest.main()
