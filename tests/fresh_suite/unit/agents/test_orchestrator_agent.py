"""
Unit tests for OrchestratorAgent using pure Mock objects and established testing patterns.

This test suite validates the orchestrator's complex business logic including
node selection strategies, LLM integration, and orchestration workflows.
"""
import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory


class TestOrchestratorAgent(unittest.TestCase):
    """Unit tests for OrchestratorAgent using pure Mock objects."""
    
    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Create LLM service mock
        self.mock_llm_service = Mock(spec=LLMServiceProtocol)
        self.mock_llm_service.call_llm.return_value = "selected_node_2"
        
        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()
        
        # Sample node list for testing
        self.test_nodes = {
            "node_1": {"name": "node_1", "description": "Handle user authentication"},
            "node_2": {"name": "node_2", "description": "Process payment transactions"},
            "node_3": {"name": "node_3", "description": "Send notification emails"},
            "selected_node_2": {"name": "selected_node_2", "description": "Selected payment processor"}
        }
        
        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(OrchestratorAgent)
    
    def create_orchestrator_agent(self, matching_strategy="algorithm", **context_overrides):
        """Helper to create orchestrator agent with common configuration."""
        context = {
            "input_fields": ["request", "available_nodes"],
            "output_field": "selected_node",
            "description": "Test orchestrator agent",
            "matching_strategy": matching_strategy,
            "selection_criteria": ["capability", "load", "availability"],
            **context_overrides
        }
        
        return OrchestratorAgent(
            name="test_orchestrator",
            prompt="Select the best node for the given request",
            context=context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_tracker,
            state_adapter_service=self.mock_state_adapter_service
        )
    
    # =============================================================================
    # 1. Agent Initialization and Protocol Compliance Tests
    # =============================================================================
    
    def test_agent_initialization_with_algorithm_strategy(self):
        """Test orchestrator initialization with algorithm matching strategy."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        # Verify basic configuration
        self.assertEqual(agent.name, "test_orchestrator")
        self.assertEqual(agent.prompt, "Select the best node for the given request")
        self.assertEqual(agent.matching_strategy, "algorithm")
        self.assertEqual(agent.selection_criteria, ["capability", "load", "availability"])
        
        # Algorithm strategy doesn't require LLM service
        self.assertFalse(agent.requires_llm)
        
        # Verify infrastructure services are available
        self.assertIsNotNone(agent.logger)
        self.assertIsNotNone(agent.execution_tracker_service)
        self.assertIsNotNone(agent.state_adapter_service)
    
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
        
        # Should default to tiered strategy (then potentially downgrade if LLM not available)
        self.assertEqual(agent.matching_strategy, "tiered")
        self.assertTrue(agent.requires_llm)
    
    def test_agent_initialization_with_minimal_context(self):
        """Test orchestrator with minimal configuration."""
        minimal_agent = OrchestratorAgent(
            name="minimal_orchestrator",
            prompt="Simple orchestration"
        )
        
        # Verify defaults
        self.assertEqual(minimal_agent.name, "minimal_orchestrator")
        self.assertEqual(minimal_agent.matching_strategy, "tiered")  # Actual default
        self.assertEqual(minimal_agent.selection_criteria, [])  # Default empty
        self.assertTrue(minimal_agent.requires_llm)  # Tiered strategy requires LLM
    
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
        
        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        llm_configured = any("LLM service configured" in call[1] for call in debug_calls)
        self.assertTrue(llm_configured, f"Expected LLM service log, got: {debug_calls}")
    
    def test_llm_service_not_required_for_algorithm_strategy(self):
        """Test that algorithm strategy doesn't require LLM service."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        # Should be able to process without LLM service
        inputs = {
            "request": "process payment",
            "available_nodes": self.test_nodes
        }
        
        # Should not raise error about missing LLM service
        result = agent.process(inputs)
        self.assertIsNotNone(result)
    
    # =============================================================================
    # 3. Algorithm-Based Orchestration Tests
    # =============================================================================
    
    def test_algorithm_orchestration_with_simple_matching(self):
        """Test algorithm-based node selection with simple keyword matching."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        inputs = {
            "request": "I need to process a payment transaction",
            "available_nodes": self.test_nodes
        }
        
        result = agent.process(inputs)
        
        # Should select node_2 (payment processing)
        self.assertIn("node_2", result)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(any("algorithm-based" in call[1] for call in info_calls))
    
    def test_algorithm_orchestration_with_no_matches(self):
        """Test algorithm orchestration when no nodes match the request."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        inputs = {
            "request": "I need to analyze quantum physics data",
            "available_nodes": self.test_nodes
        }
        
        result = agent.process(inputs)
        
        # Should return first available node as fallback
        self.assertIn("node_1", result)
        
        # Verify fallback logging
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("No specific match found" in call[1] for call in warning_calls))
    
    def test_algorithm_orchestration_with_multiple_matches(self):
        """Test algorithm orchestration with multiple potential matches."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        # Add nodes with overlapping keywords
        extended_nodes = {
            **self.test_nodes,
            "payment_validator": {"name": "payment_validator", "description": "Validate payment information"},
            "payment_processor": {"name": "payment_processor", "description": "Advanced payment processing"}
        }
        
        inputs = {
            "request": "handle payment processing",
            "available_nodes": extended_nodes
        }
        
        result = agent.process(inputs)
        
        # Should select one of the payment-related nodes
        payment_nodes = ["node_2", "payment_validator", "payment_processor"]
        self.assertTrue(any(node in result for node in payment_nodes))
    
    def test_algorithm_orchestration_with_no_csv_nodes(self):
        """Test algorithm orchestration when no nodes provided in CSV (should use registry)."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        # Simulate having a registry available
        agent.node_registry = self.test_nodes
        
        inputs = {
            "request": "process payment"
            # No available_nodes field - should fall back to registry
        }
        
        result = agent.process(inputs)
        
        # Should use registry nodes and select node_2 (payment processing)
        self.assertIn("node_2", result)
    
    # =============================================================================
    # 4. LLM-Based Orchestration Tests
    # =============================================================================
    
    def test_llm_orchestration_with_service_configured(self):
        """Test LLM-based node selection with properly configured service."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")
        agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {
            "request": "I need to process a payment",
            "available_nodes": self.test_nodes
        }
        
        result = agent.process(inputs)
        
        # Verify LLM service was called
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args
        
        # Verify call parameters
        kwargs = call_args.kwargs
        self.assertIn("messages", kwargs)
        
        # Verify messages include request and node information
        messages = kwargs["messages"]
        self.assertTrue(len(messages) >= 1)  # At least 1 user message
        
        # Check user message contains request and node list
        user_msg = messages[0]  # First (and likely only) message
        self.assertEqual(user_msg["role"], "user")
        self.assertIn("process a payment", user_msg["content"])
        self.assertIn("node_1", user_msg["content"])
        self.assertIn("node_2", user_msg["content"])
        
        # Verify result contains LLM response
        self.assertEqual(result, "selected_node_2")
    
    def test_llm_orchestration_without_service_configured(self):
        """Test LLM orchestration fails gracefully without service."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")
        
        inputs = {
            "request": "process payment",
            "available_nodes": self.test_nodes
        }
        
        with self.assertRaises(ValueError) as cm:
            agent.process(inputs)
        
        self.assertIn("LLM service not configured", str(cm.exception))
    
    def test_llm_orchestration_with_llm_error(self):
        """Test LLM orchestration handles LLM service errors."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")
        
        # Configure LLM service to raise an error
        self.mock_llm_service.call_llm.side_effect = Exception("LLM API Error")
        agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {
            "request": "process payment",
            "available_nodes": self.test_nodes
        }
        
        # Should raise the LLM error
        with self.assertRaises(Exception) as cm:
            agent.process(inputs)
        
        self.assertIn("LLM API Error", str(cm.exception))
    
    def test_llm_orchestration_with_complex_request(self):
        """Test LLM orchestration with complex, multi-part request."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")
        agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {
            "request": "I need to authenticate the user, then process their payment, and finally send a confirmation email",
            "available_nodes": self.test_nodes,
            "routing_context": "This is a high-priority VIP customer transaction"
        }
        
        result = agent.process(inputs)
        
        # Verify LLM was called with complex context
        call_args = self.mock_llm_service.call_llm.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[0]  # First message
        
        # Should include the complex request
        self.assertIn("authenticate the user", user_msg["content"])
        self.assertIn("process their payment", user_msg["content"])
        self.assertIn("confirmation email", user_msg["content"])
        self.assertIn("high-priority VIP", user_msg["content"])
        
        # Verify result
        self.assertEqual(result, "selected_node_2")
    
    # =============================================================================
    # 5. Selection Criteria and Scoring Tests
    # =============================================================================
    
    def test_algorithm_scoring_with_selection_criteria(self):
        """Test algorithm scoring considers selection criteria."""
        agent = self.create_orchestrator_agent(
            matching_strategy="algorithm",
            selection_criteria=["capability", "load", "performance"]
        )
        
        # Nodes with capability scores
        scored_nodes = {
            "node_1": {"name": "node_1", "description": "Basic authentication", "capability_score": 0.6},
            "node_2": {"name": "node_2", "description": "Advanced payment processing", "capability_score": 0.9},
            "node_3": {"name": "node_3", "description": "Email notifications", "capability_score": 0.7}
        }
        
        inputs = {
            "request": "process complex payment with fraud detection",
            "available_nodes": scored_nodes
        }
        
        result = agent.process(inputs)
        
        # Should prefer node_2 due to higher capability score and payment matching
        self.assertIn("node_2", result)
    
    def test_algorithm_keyword_matching_priority(self):
        """Test algorithm prioritizes keyword matching over other factors."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        inputs = {
            "request": "send urgent email notification",
            "available_nodes": self.test_nodes
        }
        
        result = agent.process(inputs)
        
        # Should select node_3 (email notifications) despite lower position
        self.assertIn("node_3", result)
    
    # =============================================================================
    # 6. Error Handling and Edge Cases Tests
    # =============================================================================
    
    def test_process_with_missing_required_inputs(self):
        """Test process handles missing required inputs gracefully."""
        agent = self.create_orchestrator_agent()
        
        # Missing available_nodes
        inputs = {"request": "process payment"}
        
        result = agent.process(inputs)
        
        # Should return error message
        self.assertIn("No nodes available", result)
        
        # Missing request
        inputs = {"available_nodes": self.test_nodes}
        
        result = agent.process(inputs)
        
        # Should handle gracefully
        self.assertIsNotNone(result)
    
    def test_process_with_invalid_node_format(self):
        """Test process handles invalid node formats gracefully."""
        agent = self.create_orchestrator_agent()
        
        # Nodes without required fields
        invalid_nodes = {
            "node_1": {"name": "node_1"},  # Missing description
            "incomplete_node": {"description": "No name"},  # Missing name
            "string_node": "invalid_string_node"  # Not a dict
        }
        
        inputs = {
            "request": "process payment",
            "available_nodes": invalid_nodes
        }
        
        result = agent.process(inputs)
        
        # Should handle gracefully and not crash
        self.assertIsNotNone(result)
    
    def test_process_with_none_inputs(self):
        """Test process handles None inputs gracefully."""
        agent = self.create_orchestrator_agent()
        
        inputs = {
            "request": None,
            "available_nodes": None
        }
        
        result = agent.process(inputs)
        
        # Should return appropriate error message
        self.assertIn("No nodes available", result)
    
    # =============================================================================
    # 7. Integration Tests
    # =============================================================================
    
    def test_run_method_integration_with_algorithm_strategy(self):
        """Test the inherited run method works with algorithm strategy."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        # Configure state adapter behavior
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}
        
        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state
        
        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # Configure execution tracker methods
        self.mock_tracker.record_node_start = Mock(return_value=None)
        self.mock_tracker.record_node_result = Mock(return_value=None)
        
        # Test state
        test_state = {
            "request": "authenticate user",
            "available_nodes": self.test_nodes,
            "other_field": "preserved"
        }
        
        # Execute run method
        result_state = agent.run(test_state)
        
        # Verify state was updated with selected node
        self.assertIn("selected_node", result_state)
        self.assertIn("node_1", result_state["selected_node"])  # Should match authentication
        
        # Verify original fields are preserved
        self.assertEqual(result_state["other_field"], "preserved")
        
        # Verify tracking calls
        self.mock_tracker.record_node_start.assert_called_once()
        self.mock_tracker.record_node_result.assert_called_once()
    
    def test_run_method_integration_with_llm_strategy(self):
        """Test the inherited run method works with LLM strategy."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")
        agent.configure_llm_service(self.mock_llm_service)
        
        # Configure state adapter and tracker (same as above)
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}
        
        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state
        
        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        self.mock_tracker.record_node_start = Mock(return_value=None)
        self.mock_tracker.record_node_result = Mock(return_value=None)
        
        test_state = {
            "request": "process payment",
            "available_nodes": self.test_nodes
        }
        
        result_state = agent.run(test_state)
        
        # Verify LLM was called
        self.mock_llm_service.call_llm.assert_called_once()
        
        # Verify state was updated with LLM response
        self.assertIn("selected_node", result_state)
        self.assertEqual(result_state["selected_node"], "selected_node_2")
    
    # =============================================================================
    # 8. Logging and Service Information Tests
    # =============================================================================
    
    def test_logging_integration_algorithm_strategy(self):
        """Test logging for algorithm-based orchestration."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        inputs = {
            "request": "process payment",
            "available_nodes": self.test_nodes
        }
        
        agent.process(inputs)
        
        # Verify relevant information is logged
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        
        # Should log strategy and request
        log_messages = [call[1] for call in info_calls]
        strategy_logged = any("algorithm-based" in msg for msg in log_messages)
        request_logged = any("process payment" in msg for msg in log_messages)
        
        self.assertTrue(strategy_logged, f"Expected strategy logged, got: {log_messages}")
        self.assertTrue(request_logged, f"Expected request logged, got: {log_messages}")
    
    def test_logging_integration_llm_strategy(self):
        """Test logging for LLM-based orchestration."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")
        agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {
            "request": "authenticate user",
            "available_nodes": self.test_nodes
        }
        
        agent.process(inputs)
        
        # Verify LLM strategy is logged
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        log_messages = [call[1] for call in info_calls]
        
        llm_strategy_logged = any("LLM-based" in msg for msg in log_messages)
        self.assertTrue(llm_strategy_logged, f"Expected LLM strategy logged, got: {log_messages}")
    
    def test_get_service_info_algorithm_strategy(self):
        """Test service information for algorithm strategy."""
        agent = self.create_orchestrator_agent(matching_strategy="algorithm")
        
        service_info = agent.get_service_info()
        
        # Verify protocol implementation
        protocols = service_info["protocols"]
        self.assertTrue(protocols["implements_llm_capable"])  # Still implements protocol
        self.assertFalse(protocols["implements_storage_capable"])
        
        # Verify service configuration
        services = service_info["services"]
        self.assertFalse(services["llm_service_configured"])  # Not configured for algorithm
    
    def test_get_service_info_llm_strategy(self):
        """Test service information for LLM strategy."""
        agent = self.create_orchestrator_agent(matching_strategy="llm")
        agent.configure_llm_service(self.mock_llm_service)
        
        service_info = agent.get_service_info()
        
        # Verify service configuration
        services = service_info["services"]
        self.assertTrue(services["llm_service_configured"])  # Configured for LLM strategy


if __name__ == '__main__':
    unittest.main(verbosity=2)
