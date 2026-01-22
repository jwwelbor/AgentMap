"""
Unit tests for refactored OrchestratorAgent as pure data container with service delegation.

Following Domain Model Principles, the agent now contains only data and configuration,
delegating all business logic to OrchestratorService. Tests focus on data handling,
configuration validation, and proper service delegation.
"""

import unittest
from typing import Any, Dict, List
from unittest.mock import Mock, patch

from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
from agentmap.services.orchestrator_service import OrchestratorService
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory


class TestOrchestratorAgent(unittest.TestCase):
    """Unit tests for refactored OrchestratorAgent as data container with service delegation."""

    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )

        # Create LLM service mock
        self.mock_llm_service = Mock(spec=LLMServiceProtocol)

        # Create orchestrator service mock
        self.mock_orchestrator_service = Mock(spec=OrchestratorService)
        self.mock_orchestrator_service.select_best_node.return_value = "selected_node"

        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        # Sample node list for testing
        self.test_nodes = {
            "node_1": {"name": "node_1", "description": "Handle user authentication"},
            "node_2": {"name": "node_2", "description": "Process payment transactions"},
            "node_3": {"name": "node_3", "description": "Send notification emails"},
        }

        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(OrchestratorAgent)

    def create_orchestrator_agent(
        self, matching_strategy="algorithm", **context_overrides
    ):
        """Helper to create orchestrator agent with common configuration."""
        context = {
            "input_fields": ["request", "available_nodes"],
            "output_field": "selected_node",
            "description": "Test orchestrator agent",
            "matching_strategy": matching_strategy,
            "selection_criteria": ["capability", "load", "availability"],
            **context_overrides,
        }

        agent = OrchestratorAgent(
            name="test_orchestrator",
            prompt="Select the best node for the given request",
            context=context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        # Configure the orchestrator service using the proper method
        agent.configure_orchestrator_service(self.mock_orchestrator_service)

        # Set the execution tracker instance on the agent
        agent.set_execution_tracker(self.mock_tracker)

        return agent

    # =============================================================================
    # 1. Agent Initialization and Configuration Tests
    # =============================================================================

    def test_agent_initialization_with_algorithm_strategy(self):
        """Test orchestrator initialization with algorithm matching strategy."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")

        # Verify basic configuration
        self.assertEqual(agent.name, "test_orchestrator")
        self.assertEqual(agent.prompt, "Select the best node for the given request")
        self.assertEqual(agent.matching_strategy, "algorithm")
        self.assertEqual(
            agent.selection_criteria, ["capability", "load", "availability"]
        )

        # Algorithm strategy doesn't require LLM service
        self.assertFalse(agent.requires_llm)

        # Verify infrastructure services are available
        self.assertIsNotNone(agent.logger)
        self.assertIsNotNone(agent.execution_tracking_service)
        self.assertIsNotNone(agent.state_adapter_service)

        # Verify orchestrator service is configured
        self.assertEqual(agent.orchestrator_service, self.mock_orchestrator_service)

    def test_agent_initialization_with_llm_strategy(self):
        """Test orchestrator initialization with LLM matching strategy."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")

        # Verify LLM-specific configuration
        self.assertEqual(agent.matching_strategy, "llm")
        self.assertTrue(agent.requires_llm)

        # Verify protocol implementation
        self.assertTrue(isinstance(agent, LLMCapableAgent))

        # LLM service should not be configured by default
        with self.assertRaises(ValueError):
            _ = agent.llm_service

    def test_agent_initialization_with_invalid_strategy(self):
        """Test orchestrator handles invalid matching strategy gracefully."""
        agent = self.create_orchestrator_agent(matching_strategy="invalid_strategy")

        # Should default to tiered strategy
        self.assertEqual(agent.matching_strategy, "tiered")
        self.assertTrue(agent.requires_llm)

    def test_agent_initialization_with_minimal_context(self):
        """Test orchestrator with minimal configuration."""
        minimal_agent = OrchestratorAgent(
            name="minimal_orchestrator", prompt="Simple orchestration"
        )

        # Configure the orchestrator service
        minimal_agent.configure_orchestrator_service(self.mock_orchestrator_service)

        # Verify defaults
        self.assertEqual(minimal_agent.name, "minimal_orchestrator")
        self.assertEqual(minimal_agent.matching_strategy, "tiered")  # Default
        self.assertEqual(minimal_agent.selection_criteria, [])  # Default empty
        self.assertTrue(minimal_agent.requires_llm)  # Tiered strategy requires LLM
        self.assertEqual(
            minimal_agent.orchestrator_service, self.mock_orchestrator_service
        )

    def test_agent_initialization_configuration_parsing(self):
        """Test agent correctly parses various configuration formats."""
        # Test node filter parsing
        agent1 = self.create_orchestrator_agent(nodes="node1|node2")
        self.assertEqual(agent1.node_filter, "node1|node2")

        agent2 = self.create_orchestrator_agent(node_type="agent")
        self.assertEqual(agent2.node_filter, "nodeType:agent")

        agent3 = self.create_orchestrator_agent(nodeType="service")
        self.assertEqual(agent3.node_filter, "nodeType:service")

        # Test other configuration values
        agent4 = self.create_orchestrator_agent(
            confidence_threshold=0.9,
            llm_type="claude",
            temperature=0.5,
            default_target="fallback_node",
        )
        self.assertEqual(agent4.confidence_threshold, 0.9)
        self.assertEqual(agent4.llm_type, "claude")
        self.assertEqual(agent4.temperature, 0.5)
        self.assertEqual(agent4.default_target, "fallback_node")

    # =============================================================================
    # 2. Service Configuration Tests
    # =============================================================================

    def test_llm_service_configuration_for_llm_strategy(self):
        """Test LLM service configuration for LLM-based orchestration."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")

        # Initially no LLM service
        with self.assertRaises(ValueError) as cm:
            _ = agent.llm_service
        self.assertIn("LLM service not configured", str(cm.exception))

        # Configure LLM service
        agent.configure_llm_service(self.mock_llm_service)

        # Now service should be accessible
        self.assertEqual(agent.llm_service, self.mock_llm_service)

        # Should also configure the orchestrator service
        self.assertEqual(agent.orchestrator_service.llm_service, self.mock_llm_service)

        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        llm_configured = any(
            "LLM service configured" in call[1] for call in debug_calls
        )
        self.assertTrue(llm_configured, f"Expected LLM service log, got: {debug_calls}")

    def test_llm_service_not_required_for_algorithm_strategy(self):
        """Test that algorithm strategy doesn't require LLM service."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")

        # Should be able to process without LLM service
        inputs = {"request": "process payment", "available_nodes": self.test_nodes}

        # Should not raise error about missing LLM service
        result = agent.process(inputs)
        self.assertEqual(result, "selected_node")  # From mock service

    def test_orchestrator_service_delegation(self):
        """Test that agent properly delegates to orchestrator service."""
        agent = self.create_orchestrator_agent(matching_strategy="tiered")

        inputs = {"request": "process payment", "available_nodes": self.test_nodes}

        result = agent.process(inputs)

        # Verify service delegation occurred
        self.mock_orchestrator_service.select_best_node.assert_called_once()
        call_args = self.mock_orchestrator_service.select_best_node.call_args

        # Verify delegation parameters
        kwargs = call_args.kwargs
        self.assertEqual(kwargs["input_text"], "process payment")
        self.assertEqual(kwargs["available_nodes"], self.test_nodes)
        self.assertEqual(kwargs["strategy"], "tiered")
        self.assertEqual(kwargs["confidence_threshold"], 0.8)  # Default
        self.assertEqual(kwargs["node_filter"], "all")  # Default

        # Verify LLM config
        llm_config = kwargs["llm_config"]
        self.assertEqual(llm_config["provider"], "openai")  # Default
        self.assertEqual(llm_config["temperature"], 0.2)  # Default

        # Verify result
        self.assertEqual(result, "selected_node")

    # =============================================================================
    # 3. Data Extraction Tests (Agent Responsibility)
    # =============================================================================

    def test_get_input_text_from_configured_fields(self):
        """Test input text extraction from configured input fields."""
        agent = self.create_orchestrator_agent()

        inputs = {
            "request": "user authentication needed",
            "available_nodes": self.test_nodes,
            "other_field": "should be ignored",
        }

        result = agent._get_input_text(inputs)
        self.assertEqual(result, "user authentication needed")

    def test_get_input_text_fallback_to_common_fields(self):
        """Test input text extraction falls back to common field names."""
        agent = self.create_orchestrator_agent()

        inputs = {"query": "find payment processor", "available_nodes": self.test_nodes}

        result = agent._get_input_text(inputs)
        self.assertEqual(result, "find payment processor")

    def test_get_input_text_last_resort_string_field(self):
        """Test input text extraction uses any string field as last resort."""
        agent = self.create_orchestrator_agent()

        inputs = {
            "available_nodes": self.test_nodes,
            "numeric_field": 123,
            "some_text": "last resort text",
        }

        result = agent._get_input_text(inputs)
        self.assertEqual(result, "last resort text")

    def test_get_input_text_handles_missing_input(self):
        """Test input text extraction handles missing input gracefully."""
        agent = self.create_orchestrator_agent()

        inputs = {"available_nodes": self.test_nodes, "numeric_field": 123}

        result = agent._get_input_text(inputs)
        self.assertEqual(result, "")

    def test_get_nodes_from_inputs_standard_fields(self):
        """Test node extraction from standard input fields."""
        agent = self.create_orchestrator_agent()

        # Test available_nodes field
        inputs1 = {"available_nodes": self.test_nodes, "request": "test"}
        result1 = agent._get_nodes_from_inputs(inputs1)
        self.assertEqual(result1, self.test_nodes)

        # Test nodes field
        inputs2 = {"nodes": self.test_nodes, "request": "test"}
        result2 = agent._get_nodes_from_inputs(inputs2)
        self.assertEqual(result2, self.test_nodes)

        # Test __node_registry field
        inputs3 = {"__node_registry": self.test_nodes, "request": "test"}
        result3 = agent._get_nodes_from_inputs(inputs3)
        self.assertEqual(result3, self.test_nodes)

    def test_get_nodes_from_inputs_configured_fields(self):
        """Test node extraction from configured input fields."""
        agent = self.create_orchestrator_agent()
        agent.input_fields = ["request", "node_data"]

        inputs = {"request": "test request", "node_data": self.test_nodes}

        result = agent._get_nodes_from_inputs(inputs)
        self.assertEqual(result, self.test_nodes)

    def test_get_nodes_from_inputs_handles_missing_nodes(self):
        """Test node extraction handles missing nodes gracefully."""
        agent = self.create_orchestrator_agent()

        inputs = {"request": "test request"}

        result = agent._get_nodes_from_inputs(inputs)
        self.assertEqual(result, {})

    # =============================================================================
    # 4. Process Method Integration Tests
    # =============================================================================

    def test_process_with_csv_provided_nodes(self):
        """Test process method uses CSV-provided nodes."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")

        inputs = {"request": "authenticate user", "available_nodes": self.test_nodes}

        result = agent.process(inputs)

        # Verify service was called with CSV nodes
        call_args = self.mock_orchestrator_service.select_best_node.call_args
        self.assertEqual(call_args.kwargs["available_nodes"], self.test_nodes)
        self.assertEqual(result, "selected_node")

    def test_process_with_registry_fallback(self):
        """Test process method falls back to node registry."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        agent.node_registry = self.test_nodes

        inputs = {"request": "authenticate user"}  # No available_nodes

        result = agent.process(inputs)

        # Verify service was called with registry nodes
        call_args = self.mock_orchestrator_service.select_best_node.call_args
        self.assertEqual(call_args.kwargs["available_nodes"], self.test_nodes)
        self.assertEqual(result, "selected_node")

    def test_process_without_orchestrator_service(self):
        """Test process method handles missing orchestrator service."""
        agent = OrchestratorAgent(
            name="test_agent",
            prompt="test prompt",
            logger=self.mock_logger,
            # No orchestrator_service provided
        )

        inputs = {"request": "test request", "available_nodes": self.test_nodes}

        result = agent.process(inputs)

        # Should return error message
        self.assertIn("OrchestratorService not configured", result)

    def test_process_with_service_error(self):
        """Test process method handles service errors gracefully."""
        agent = self.create_orchestrator_agent()

        # Configure service to raise error
        self.mock_orchestrator_service.select_best_node.side_effect = Exception(
            "Service Error"
        )

        inputs = {"request": "test request", "available_nodes": self.test_nodes}

        result = agent.process(inputs)

        # Should handle error gracefully
        self.assertIn("Service Error", result)

    def test_process_with_default_target_fallback(self):
        """Test process method uses default target on service error."""
        agent = self.create_orchestrator_agent(default_target="fallback_node")

        # Configure service to raise error
        self.mock_orchestrator_service.select_best_node.side_effect = Exception(
            "Service Error"
        )

        inputs = {"request": "test request", "available_nodes": self.test_nodes}

        result = agent.process(inputs)

        # Should return default target
        self.assertEqual(result, "fallback_node")

    # =============================================================================
    # 5. State Management Tests
    # =============================================================================

    @patch("agentmap.agents.builtins.orchestrator_agent.StateAdapterService.set_value")
    def test_post_process_sets_next_node(self, mock_set_value):
        """Test post-process sets __next_node in state."""
        agent = self.create_orchestrator_agent()

        test_state = {"current_field": "value"}
        inputs = {"request": "test"}
        output = "selected_node"

        # Configure mock to return updated state
        updated_state = test_state.copy()
        updated_state["__next_node"] = "selected_node"
        mock_set_value.return_value = updated_state

        result_state, result_output = agent._post_process(test_state, inputs, output)

        # Verify static method was called
        mock_set_value.assert_called_once_with(
            test_state, "__next_node", "selected_node"
        )

        # Verify output is returned unchanged
        self.assertEqual(result_output, output)

    @patch("agentmap.agents.builtins.orchestrator_agent.StateAdapterService.set_value")
    def test_post_process_extracts_node_from_dict(self, mock_set_value):
        """Test post-process extracts selectedNode from dictionary output."""
        agent = self.create_orchestrator_agent()

        test_state = {"current_field": "value"}
        inputs = {"request": "test"}
        output = {"selectedNode": "extracted_node", "confidence": 0.9}

        # Configure mock to return updated state
        updated_state = test_state.copy()
        updated_state["__next_node"] = "extracted_node"
        mock_set_value.return_value = updated_state

        result_state, result_output = agent._post_process(test_state, inputs, output)

        # Verify extracted node was used
        mock_set_value.assert_called_once_with(
            test_state, "__next_node", "extracted_node"
        )

    # =============================================================================
    # 6. Integration Tests
    # =============================================================================

    def test_run_method_integration_with_algorithm_strategy(self):
        """Test the inherited run method works with algorithm strategy."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")

        # Configure state adapter behavior
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        # Test state
        test_state = {
            "request": "authenticate user",
            "available_nodes": self.test_nodes,
            "other_field": "preserved",
        }

        # Execute run method
        result_state = agent.run(test_state)

        # Verify orchestrator service was called
        self.mock_orchestrator_service.select_best_node.assert_called_once()

        # Verify state was updated with selected node
        self.assertIn("selected_node", result_state)
        self.assertEqual(result_state["selected_node"], "selected_node")

        # Original fields are NOT in result - only output field
        self.assertNotIn("other_field", result_state)
        self.assertEqual(len(result_state), 1)  # Only output field

        # Verify tracking service methods were called
        self.mock_execution_tracking_service.record_node_start.assert_called_once()
        self.mock_execution_tracking_service.record_node_result.assert_called_once()

    def test_run_method_integration_with_llm_strategy(self):
        """Test the inherited run method works with LLM strategy."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")
        agent.configure_llm_service(self.mock_llm_service)

        # Configure state adapter and tracker (same as above)
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        test_state = {"request": "process payment", "available_nodes": self.test_nodes}

        result_state = agent.run(test_state)

        # Verify orchestrator service was called with LLM strategy
        call_args = self.mock_orchestrator_service.select_best_node.call_args
        self.assertEqual(call_args.kwargs["strategy"], "llm")

        # Verify state was updated
        self.assertIn("selected_node", result_state)
        self.assertEqual(result_state["selected_node"], "selected_node")

    # =============================================================================
    # 7. Service Information Tests
    # =============================================================================

    def test_get_service_info_includes_orchestration_config(self):
        """Test service information includes orchestration configuration."""
        agent = self.create_orchestrator_agent(
            matching_strategy="tiered",
            confidence_threshold=0.9,
            llm_type="claude",
            temperature=0.3,
        )

        service_info = agent.get_service_info()

        # Verify orchestration configuration is included
        orchestration_config = service_info["orchestration_config"]
        self.assertEqual(orchestration_config["matching_strategy"], "tiered")
        self.assertEqual(orchestration_config["confidence_threshold"], 0.9)
        self.assertEqual(orchestration_config["llm_type"], "claude")
        self.assertEqual(orchestration_config["temperature"], 0.3)

        # Verify service status
        self.assertTrue(service_info["orchestrator_service_configured"])

        # Verify protocol implementation
        protocols = service_info["protocols"]
        self.assertTrue(protocols["implements_llm_capable"])

    def test_get_service_info_without_orchestrator_service(self):
        """Test service information when orchestrator service not configured."""
        agent = OrchestratorAgent(
            name="test_agent",
            prompt="test prompt",
            # No orchestrator_service
        )

        service_info = agent.get_service_info()

        # Should indicate service not configured
        self.assertFalse(service_info["orchestrator_service_configured"])

    # =============================================================================
    # 8. Logging Integration Tests
    # =============================================================================

    def test_logging_integration_service_delegation(self):
        """Test logging for service delegation."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")

        inputs = {"request": "process payment", "available_nodes": self.test_nodes}

        agent.process(inputs)

        # Verify relevant information is logged
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        info_calls = [call for call in logger_calls if call[0] == "info"]

        # Should log input text
        debug_messages = [call[1] for call in debug_calls]
        input_logged = any(
            "Input text" in msg and "process payment" in msg for msg in debug_messages
        )
        self.assertTrue(input_logged, f"Expected input logged, got: {debug_messages}")

        # Should log selected node
        info_messages = [call[1] for call in info_calls]
        selection_logged = any("Selected node" in msg for msg in info_messages)
        self.assertTrue(
            selection_logged, f"Expected selection logged, got: {info_messages}"
        )

    def test_logging_integration_error_handling(self):
        """Test logging for error scenarios."""
        agent = self.create_orchestrator_agent()

        # Configure service to raise error
        self.mock_orchestrator_service.select_best_node.side_effect = Exception(
            "Test Error"
        )

        inputs = {"request": "test request", "available_nodes": self.test_nodes}

        agent.process(inputs)

        # Verify error logging
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]

        self.assertTrue(len(error_calls) > 0)
        error_messages = [call[1] for call in error_calls]
        error_logged = any("Error in orchestration" in msg for msg in error_messages)
        self.assertTrue(error_logged, f"Expected error logged, got: {error_messages}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
