"""
Unit tests for BaseAgent using pure Mock objects and established testing patterns.

This test suite validates the new protocol-based dependency injection pattern
that serves as the foundation for all AgentMap agents.
"""
import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import (
    LLMCapableAgent, StorageCapableAgent, LLMServiceProtocol, StorageServiceProtocol
)
from tests.utils.mock_service_factory import MockServiceFactory


# Mixins that provide service configuration methods
class LLMCapableMixin:
    """Mixin that provides LLM service configuration for agents."""
    
    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None:
        """Configure LLM service for this agent."""
        self._llm_service = llm_service
        if hasattr(self, 'log_debug'):
            self.log_debug("LLM service configured")


class StorageCapableMixin:
    """Mixin that provides storage service configuration for agents."""
    
    def configure_storage_service(self, storage_service: StorageServiceProtocol) -> None:
        """Configure storage service for this agent."""
        self._storage_service = storage_service
        if hasattr(self, 'log_debug'):
            self.log_debug("Storage service configured")


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Simple test implementation."""
        return f"processed: {inputs}"


class LLMCapableTestAgent(BaseAgent, LLMCapableMixin, LLMCapableAgent):
    """Test agent that implements LLMCapableAgent protocol."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Test implementation that uses LLM service."""
        response = self.llm_service.call_llm("test", [])
        return f"llm_result: {response}"


class StorageCapableTestAgent(BaseAgent, StorageCapableMixin, StorageCapableAgent):
    """Test agent that implements StorageCapableAgent protocol."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Test implementation that uses storage service."""
        data = self.storage_service.read("test_collection")
        return f"storage_result: {data}"


class MultiServiceTestAgent(BaseAgent, LLMCapableMixin, StorageCapableMixin, LLMCapableAgent, StorageCapableAgent):
    """Test agent that implements both LLM and Storage protocols."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """Test implementation that uses both services."""
        llm_response = self.llm_service.call_llm("test", [])
        storage_data = self.storage_service.read("test")
        return f"multi_result: {llm_response}, {storage_data}"


class TestBaseAgent(unittest.TestCase):
    """Unit tests for BaseAgent using pure Mock objects."""
    
    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Create business service mocks
        self.mock_llm_service = Mock(spec=LLMServiceProtocol)
        self.mock_llm_service.call_llm.return_value = "mock_llm_response"
        
        self.mock_storage_service = Mock(spec=StorageServiceProtocol)
        self.mock_storage_service.read.return_value = "mock_storage_data"
        self.mock_storage_service.write.return_value = "mock_write_result"
        
        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()
        
        # Create basic context for testing
        self.test_context = {
            "input_fields": ["input1", "input2"],
            "output_field": "output",
            "description": "Test agent"
        }
        
        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(ConcreteAgent)
    
    # =============================================================================
    # 1. BaseAgent Initialization Tests
    # =============================================================================
    
    def test_base_agent_initialization_with_all_infrastructure_services(self):
        """Test BaseAgent initializes correctly with all infrastructure services."""
        agent = ConcreteAgent(
            name="test_agent",
            prompt="Test prompt",
            context=self.test_context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Verify all infrastructure dependencies are stored
        self.assertEqual(agent.name, "test_agent")
        self.assertEqual(agent.prompt, "Test prompt")
        self.assertEqual(agent.context, self.test_context)
        self.assertEqual(agent.input_fields, ["input1", "input2"])
        self.assertEqual(agent.output_field, "output")
        self.assertEqual(agent.description, "Test agent")
        
        # Verify infrastructure services are accessible
        self.assertEqual(agent.logger, self.mock_logger)
        self.assertEqual(agent.execution_tracking_service, self.mock_execution_tracking_service)
        self.assertEqual(agent.state_adapter_service, self.mock_state_adapter_service)
        
        # Verify business services are not configured by default
        with self.assertRaises(ValueError):
            _ = agent.llm_service
        with self.assertRaises(ValueError):
            _ = agent.storage_service
    
    def test_base_agent_initialization_with_minimal_parameters(self):
        """Test BaseAgent initialization with only required parameters."""
        agent = ConcreteAgent(
            name="minimal_agent",
            prompt="Minimal prompt"
        )
        
        # Verify basic configuration
        self.assertEqual(agent.name, "minimal_agent")
        self.assertEqual(agent.prompt, "Minimal prompt")
        self.assertEqual(agent.context, {})
        self.assertEqual(agent.input_fields, [])
        self.assertIsNone(agent.output_field)  # Should default to None now
        self.assertEqual(agent.description, "")
        
        # Verify services are not configured
        with self.assertRaises(ValueError):
            _ = agent.logger
        with self.assertRaises(ValueError):
            _ = agent.execution_tracking_service
    
    def test_base_agent_context_processing(self):
        """Test BaseAgent correctly processes context information."""
        context = {
            "input_fields": ["field1", "field2", "field3"],
            "output_field": "result",
            "description": "Complex test agent",
            "custom_property": "custom_value"
        }
        
        agent = ConcreteAgent(
            name="context_test",
            prompt="Context test",
            context=context
        )
        
        # Verify context extraction
        self.assertEqual(agent.input_fields, ["field1", "field2", "field3"])
        self.assertEqual(agent.output_field, "result")
        self.assertEqual(agent.description, "Complex test agent")
        
        # Verify full context is preserved
        self.assertEqual(agent.context["custom_property"], "custom_value")
    
    def test_output_field_defaults_to_none(self):
        """Test that output_field defaults to None when not specified."""
        # Agent without explicit output_field
        agent_no_output = ConcreteAgent(
            name="no_output",
            prompt="No output",
            context={"input_fields": ["input"]}  # No output_field specified
        )
        
        # Should default to None
        self.assertIsNone(agent_no_output.output_field)
        
        # Agent with explicit output_field should use that value
        agent_with_output = ConcreteAgent(
            name="with_output",
            prompt="With output",
            context={"input_fields": ["input"], "output_field": "result"}
        )
        
        # Should use explicitly set value
        self.assertEqual(agent_with_output.output_field, "result")
    
    def test_run_method_with_no_output_field(self):
        """Test that agents with output_field=None don't modify state."""
        agent = ConcreteAgent(
            name="no_output_test",
            prompt="No output test",
            context={"input_fields": ["input"]},  # No output_field = None
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Configure state adapter
        self.mock_state_adapter_service.get_inputs.return_value = {"input": "test"}
        self.mock_state_adapter_service.set_value.side_effect = lambda s, k, v: {**s, k: v}
        
        # CRITICAL: Set execution tracker on agent (required by new architecture)
        agent.set_execution_tracker(self.mock_tracker)
        
        # Test state
        test_state = {"input": "test_value", "existing": "preserved"}
        
        # Execute run method
        result_state = agent.run(test_state)
        
        # State should be unchanged (no output field set)
        self.assertEqual(result_state["input"], "test_value")
        self.assertEqual(result_state["existing"], "preserved")
        
        # set_value should NOT have been called for output (since output_field is None)
        # The state adapter's set_value might be called for other purposes, but not for output
        # We can't easily verify this without more complex mocking, but the key point is
        # that no new output field should appear in the result state
        self.assertNotIn("output", result_state)  # No default "output" field added
    
    # =============================================================================
    # 2. Service Configuration Tests (New Protocol Pattern)
    # =============================================================================
    
    def test_configure_llm_service(self):
        """Test LLM service configuration via new protocol pattern."""
        agent = LLMCapableTestAgent(
            name="test", 
            prompt="prompt",
            logger=self.mock_logger  # Provide logger for logging during service configuration
        )
        
        # Initially no LLM service
        with self.assertRaises(ValueError) as cm:
            _ = agent.llm_service
        self.assertIn("LLM service not configured", str(cm.exception))
        
        # Configure LLM service
        agent.configure_llm_service(self.mock_llm_service)
        
        # Now service should be accessible
        self.assertEqual(agent.llm_service, self.mock_llm_service)
    
    def test_configure_storage_service(self):
        """Test storage service configuration via new protocol pattern."""
        agent = StorageCapableTestAgent(
            name="test", 
            prompt="prompt",
            logger=self.mock_logger  # Provide logger for logging during service configuration
        )
        
        # Initially no storage service
        with self.assertRaises(ValueError) as cm:
            _ = agent.storage_service
        self.assertIn("Storage service not configured", str(cm.exception))
        
        # Configure storage service
        agent.configure_storage_service(self.mock_storage_service)
        
        # Now service should be accessible
        self.assertEqual(agent.storage_service, self.mock_storage_service)
    
    def test_service_configuration_with_logging(self):
        """Test service configuration generates appropriate log messages."""
        agent = MultiServiceTestAgent(
            name="logging_test",
            prompt="Test",
            logger=self.mock_logger  # Already has logger - good!
        )
        
        # Configure services
        agent.configure_llm_service(self.mock_llm_service)
        agent.configure_storage_service(self.mock_storage_service)
        
        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        
        # Should have logged service configuration
        llm_logged = any("LLM service configured" in call[1] for call in debug_calls)
        storage_logged = any("Storage service configured" in call[1] for call in debug_calls)
        
        self.assertTrue(llm_logged, f"Expected LLM service log, got: {debug_calls}")
        self.assertTrue(storage_logged, f"Expected storage service log, got: {debug_calls}")
    
    # =============================================================================
    # 3. Protocol-Based Agent Tests
    # =============================================================================
    
    def test_llm_capable_agent_protocol_implementation(self):
        """Test agent that implements LLMCapableAgent protocol."""
        agent = LLMCapableTestAgent(
            name="llm_agent",
            prompt="LLM test",
            logger=self.mock_logger  # Provide logger for service configuration
        )
        
        # Verify protocol implementation
        self.assertIsInstance(agent, LLMCapableAgent)
        self.assertFalse(isinstance(agent, StorageCapableAgent))
        
        # Configure LLM service
        agent.configure_llm_service(self.mock_llm_service)
        
        # Test service usage
        inputs = {"input": "test"}
        result = agent.process(inputs)
        
        # Verify LLM service was called
        self.mock_llm_service.call_llm.assert_called_once_with("test", [])
        self.assertEqual(result, "llm_result: mock_llm_response")
    
    def test_storage_capable_agent_protocol_implementation(self):
        """Test agent that implements StorageCapableAgent protocol."""
        agent = StorageCapableTestAgent(
            name="storage_agent",
            prompt="Storage test",
            logger=self.mock_logger  # Provide logger for service configuration
        )
        
        # Verify protocol implementation
        self.assertIsInstance(agent, StorageCapableAgent)
        self.assertFalse(isinstance(agent, LLMCapableAgent))
        
        # Configure storage service
        agent.configure_storage_service(self.mock_storage_service)
        
        # Test service usage
        inputs = {"input": "test"}
        result = agent.process(inputs)
        
        # Verify storage service was called
        self.mock_storage_service.read.assert_called_once_with("test_collection")
        self.assertEqual(result, "storage_result: mock_storage_data")
    
    def test_multi_service_agent_protocol_implementation(self):
        """Test agent that implements both LLM and Storage protocols."""
        agent = MultiServiceTestAgent(
            name="multi_agent",
            prompt="Multi test",
            logger=self.mock_logger  # Provide logger for service configuration
        )
        
        # Verify protocol implementation
        self.assertIsInstance(agent, LLMCapableAgent)
        self.assertIsInstance(agent, StorageCapableAgent)
        
        # Configure both services
        agent.configure_llm_service(self.mock_llm_service)
        agent.configure_storage_service(self.mock_storage_service)
        
        # Test service usage
        inputs = {"input": "test"}
        result = agent.process(inputs)
        
        # Verify both services were called
        self.mock_llm_service.call_llm.assert_called_once_with("test", [])
        self.mock_storage_service.read.assert_called_once_with("test")
        self.assertEqual(result, "multi_result: mock_llm_response, mock_storage_data")
    
    # =============================================================================
    # 4. Infrastructure Service Access Tests
    # =============================================================================
    
    def test_logger_property_access(self):
        """Test logger property access and error handling."""
        # Test with logger provided
        agent_with_logger = ConcreteAgent(
            name="with_logger",
            prompt="Test",
            logger=self.mock_logger
        )
        self.assertEqual(agent_with_logger.logger, self.mock_logger)
        
        # Test without logger
        agent_without_logger = ConcreteAgent("without_logger", "Test")
        with self.assertRaises(ValueError) as cm:
            _ = agent_without_logger.logger
        
        error_msg = str(cm.exception)
        self.assertIn("Logger not provided", error_msg)
        self.assertIn("without_logger", error_msg)
    
    def test_execution_tracker_property_access(self):
        """Test execution tracker property access and error handling."""
        # Test with tracker provided
        agent_with_tracker = ConcreteAgent(
            name="with_tracker",
            prompt="Test",
            execution_tracking_service=self.mock_execution_tracking_service
        )
        self.assertEqual(agent_with_tracker.execution_tracking_service, self.mock_execution_tracking_service)
        
        # Test without tracker
        agent_without_tracker = ConcreteAgent("without_tracker", "Test")
        with self.assertRaises(ValueError) as cm:
            _ = agent_without_tracker.execution_tracking_service
        
        error_msg = str(cm.exception)
        self.assertIn("ExecutionTrackingService not provided", error_msg)
        self.assertIn("without_tracker", error_msg)
    
    def test_state_adapter_property_access(self):
        """Test state adapter property access """
        # Test with adapter provided
        agent_with_adapter = ConcreteAgent(
            name="with_adapter",
            prompt="Test",
            state_adapter_service=self.mock_state_adapter_service
        )
        self.assertEqual(agent_with_adapter.state_adapter_service, self.mock_state_adapter_service)
        
        adapter = agent_with_adapter.state_adapter_service
        self.assertIsNotNone(adapter)

        self.assertTrue(hasattr(adapter, 'get_inputs'))
        self.assertTrue(hasattr(adapter, 'set_value'))
    
    # =============================================================================
    # 5. Logging Integration Tests
    # =============================================================================
    
    def test_logging_methods(self):
        """Test all logging methods work correctly."""
        agent = ConcreteAgent(
            name="logging_test",
            prompt="Test",
            logger=self.mock_logger
        )
        
        # Test all logging levels
        agent.log_debug("Debug message")
        agent.log_info("Info message")
        agent.log_warning("Warning message")
        agent.log_error("Error message")
        agent.log_trace("Trace message")
        
        # Verify all calls were made
        logger_calls = self.mock_logger.calls
        
        expected_calls = [
            ("debug", "[ConcreteAgent:logging_test] Debug message"),
            ("info", "[ConcreteAgent:logging_test] Info message"),
            ("warning", "[ConcreteAgent:logging_test] Warning message"),
            ("error", "[ConcreteAgent:logging_test] Error message"),
            ("trace", "[ConcreteAgent:logging_test] Trace message")
        ]
        
        for expected_call in expected_calls:
            self.assertTrue(
                any(call[:2] == expected_call for call in logger_calls),
                f"Expected call {expected_call} not found in {logger_calls}"
            )
    
    def test_generic_log_method(self):
        """Test generic log method with different levels."""
        agent = ConcreteAgent(
            name="generic_log_test",
            prompt="Test",
            logger=self.mock_logger
        )
        
        # Test generic log method
        agent.log("info", "Generic info message")
        agent.log("error", "Generic error message")
        agent.log("unknown_level", "Unknown level message")
        
        # Verify calls
        logger_calls = self.mock_logger.calls
        
        # Should have info and error calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        error_calls = [call for call in logger_calls if call[0] == "error"]
        
        self.assertTrue(len(info_calls) >= 1)
        self.assertTrue(len(error_calls) >= 1)
        
        # Unknown level should default to info
        self.assertTrue(any("Unknown level message" in call[1] for call in info_calls))
    
    # =============================================================================
    # 6. Run Method Integration Tests
    # =============================================================================
    
    def test_run_method_successful_execution(self):
        """Test run method with successful execution."""
        agent = ConcreteAgent(
            name="run_test",
            prompt="Test run",
            context={"input_fields": ["input"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,  # Pass the SERVICE, not the tracker
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Configure state adapter behavior
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}
        
        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state
        
        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # CRITICAL: Set execution tracker on agent (required by new architecture)
        agent.set_execution_tracker(self.mock_tracker)
        
        # Test state
        test_state = {"input": "test_value", "other": "preserved"}
        
        # Execute run method
        result_state = agent.run(test_state)
        
        # Verify state was updated
        self.assertIn("output", result_state)
        self.assertEqual(result_state["output"], "processed: {'input': 'test_value'}")
        self.assertEqual(result_state["other"], "preserved")
        
        # Verify tracking service methods were called with correct parameters
        self.mock_execution_tracking_service.record_node_start.assert_called_once()
        self.mock_execution_tracking_service.record_node_result.assert_called_once()
        
        # Verify the record_node_start call
        start_call_args = self.mock_execution_tracking_service.record_node_start.call_args
        start_args, start_kwargs = start_call_args
        # Should be: record_node_start(tracker, node_name, inputs)
        self.assertEqual(start_args[1], "run_test")  # node_name is second argument (after tracker)
        
        # Verify the record_node_result call 
        result_call_args = self.mock_execution_tracking_service.record_node_result.call_args
        result_args, result_kwargs = result_call_args
        # Should be: record_node_result(tracker, node_name, success, result=output)
        self.assertEqual(result_args[1], "run_test")  # node_name is second argument (after tracker)
        self.assertTrue(result_args[2])  # success=True is third argument
        self.assertIn('result', result_kwargs)  # result is keyword argument
    
    
    def test_run_method_with_process_error(self):
        """Test run method handles process errors gracefully."""
        class ErrorAgent(BaseAgent):
            def process(self, inputs):
                raise ValueError("Test process error")
        
        agent = ErrorAgent(
            name="error_test",
            prompt="Error test",
            context={"input_fields": ["input"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,  # Pass the SERVICE, not the tracker
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Configure state adapter
        self.mock_state_adapter_service.get_inputs.return_value = {"input": "test"}
        self.mock_state_adapter_service.set_value.side_effect = lambda s, k, v: s
        
        # Configure execution tracking service methods
        self.mock_execution_tracking_service.update_graph_success.return_value = False
        
        # CRITICAL: Set execution tracker on agent (required by new architecture)
        agent.set_execution_tracker(self.mock_tracker)
        
        # Test state
        test_state = {"input": "test_value"}
        
        # Execute run method (should not raise)
        result_state = agent.run(test_state)
        
        # Verify error was handled
        self.assertEqual(result_state, test_state)  # Original state returned
        
        # Verify error tracking service methods were called
        self.mock_execution_tracking_service.record_node_result.assert_called_once()
        call_args = self.mock_execution_tracking_service.record_node_result.call_args
        args, kwargs = call_args
        
        # Error case uses consistent pattern: record_node_result(tracker, node_name, False, error=error_msg)
        self.assertEqual(args[1], "error_test")  # node_name is second argument (after tracker)
        self.assertFalse(args[2])  # success=False is third argument
        self.assertIn('error', kwargs)  # error is keyword
        
        # Verify error logging
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(len(error_calls) > 0)
        self.assertTrue(any("Test process error" in call[1] for call in error_calls))
    
    # =============================================================================
    # 7. Service Information Tests
    # =============================================================================
    
    def test_get_service_info_basic_agent(self):
        """Test service info for basic agent without business services."""
        agent = ConcreteAgent(
            name="info_test",
            prompt="Info test",
            context=self.test_context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        service_info = agent.get_service_info()
        
        # Verify basic info
        self.assertEqual(service_info["agent_name"], "info_test")
        self.assertEqual(service_info["agent_type"], "ConcreteAgent")
        
        # Verify service availability
        services = service_info["services"]
        self.assertTrue(services["logger_available"])
        self.assertTrue(services["execution_tracker_available"])
        self.assertTrue(services["state_adapter_available"])
        self.assertFalse(services["llm_service_configured"])
        self.assertFalse(services["storage_service_configured"])
        
        # Verify protocol implementation
        protocols = service_info["protocols"]
        self.assertFalse(protocols["implements_llm_capable"])
        self.assertFalse(protocols["implements_storage_capable"])
        
        # Verify configuration
        config = service_info["configuration"]
        self.assertEqual(config["input_fields"], ["input1", "input2"])
        self.assertEqual(config["output_field"], "output")  # Explicitly set in test_context
        self.assertEqual(config["description"], "Test agent")
    
    def test_get_service_info_multi_service_agent(self):
        """Test service info for agent with multiple business services."""
        agent = MultiServiceTestAgent(
            name="multi_info_test",
            prompt="Multi info test",
            context=self.test_context,
            logger=self.mock_logger  # Provide logger for service configuration
        )
        
        # Configure services
        agent.configure_llm_service(self.mock_llm_service)
        agent.configure_storage_service(self.mock_storage_service)
        
        service_info = agent.get_service_info()
        
        # Verify business service configuration
        services = service_info["services"]
        self.assertTrue(services["llm_service_configured"])
        self.assertTrue(services["storage_service_configured"])
        
        # Verify protocol implementation
        protocols = service_info["protocols"]
        self.assertTrue(protocols["implements_llm_capable"])
        self.assertTrue(protocols["implements_storage_capable"])
    
    
    # =============================================================================
    # 8. Hook Methods Tests
    # =============================================================================
    
    def test_pre_process_hook(self):
        """Test _pre_process hook can be overridden."""
        class PreProcessAgent(BaseAgent):
            def _pre_process(self, state, inputs):
                # Modify inputs in pre-processing
                modified_inputs = inputs.copy()
                modified_inputs["preprocessed"] = True
                return state, modified_inputs
            
            def process(self, inputs):
                return inputs
        
        agent = PreProcessAgent(
            name="pre_test", 
            prompt="Test",
            context={"input_fields": ["input"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Configure mocks for run() method
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}
        
        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state
        
        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # CRITICAL: Set execution tracker on agent (required by new architecture)
        agent.set_execution_tracker(self.mock_tracker)
        
        # Test state with original input
        test_state = {"input": "value"}
        
        # Call run() method which triggers _pre_process
        result_state = agent.run(test_state)
        
        # Verify that preprocessing was applied (result should include preprocessed flag)
        self.assertIn("output", result_state)
        output = result_state["output"]
        
        # The output should be the processed inputs with the preprocessed flag
        self.assertIsInstance(output, dict)
        self.assertIn("input", output)
        self.assertIn("preprocessed", output)
        self.assertTrue(output["preprocessed"])
    
    def test_post_process_hook(self):
        """Test _post_process hook can be overridden."""
        class PostProcessAgent(BaseAgent):
            def _post_process(self, state, inputs, output):
                # Modify output in post-processing
                modified_output = f"post_processed: {output}"
                return state, modified_output
            
            def process(self, inputs):
                return "original_output"
        
        agent = PostProcessAgent(
            name="post_test", 
            prompt="Test",
            context={"input_fields": ["input"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Configure mocks for run() method
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}
        
        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state
        
        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # CRITICAL: Set execution tracker on agent (required by new architecture)
        agent.set_execution_tracker(self.mock_tracker)
        
        # Test state
        test_state = {"input": "value"}
        
        # Call run() method which triggers _post_process
        result_state = agent.run(test_state)
        
        # Verify that post-processing was applied
        self.assertIn("output", result_state)
        output = result_state["output"]
        
        # Should be post-processed
        self.assertEqual(output, "post_processed: original_output")
    
    # =============================================================================
    # 9. LangGraph Compatibility Tests
    # =============================================================================
    
    def test_invoke_method_compatibility(self):
        """Test invoke method for LangGraph compatibility."""
        agent = ConcreteAgent(
            name="invoke_test",
            prompt="Invoke test",
            context={"input_fields": ["input"], "output_field": "output"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Configure mocks
        self.mock_state_adapter_service.get_inputs.return_value = {"input": "test"}
        self.mock_state_adapter_service.set_value.side_effect = lambda s, k, v: {**s, k: v}
        
        # CRITICAL: Set execution tracker on agent (required by new architecture)
        agent.set_execution_tracker(self.mock_tracker)
        
        test_state = {"input": "test_value"}
        
        # invoke should work the same as run
        result_from_invoke = agent.invoke(test_state)
        result_from_run = agent.run(test_state)
        
        # Results should be identical
        self.assertEqual(result_from_invoke, result_from_run)


if __name__ == '__main__':
    unittest.main()
