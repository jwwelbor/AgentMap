"""
Unit tests for modernized VectorReaderAgent.

This test suite verifies that VectorReaderAgent works correctly after
mixin removal, ensuring clean architecture, proper service delegation,
and preserved result formatting.
"""

import unittest
from typing import Any, Dict
from unittest.mock import Mock, patch

from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent
from agentmap.agents.builtins.storage.vector.reader import VectorReaderAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestModernizedVectorReaderAgent(unittest.TestCase):
    """Test suite for modernized VectorReaderAgent."""

    def setUp(self):
        """Set up test fixtures with mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )

        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(VectorReaderAgent)

        # Create mock vector service with realistic results
        self.mock_vector_service = Mock()
        self.mock_vector_service.read.return_value = [
            {"content": "Test document 1", "metadata": {"score": 0.95}},
            {"content": "Test document 2", "metadata": {"score": 0.87}},
            {"content": "Test document 3", "metadata": {"score": 0.76}},
        ]

    def create_vector_reader_agent(self, **context_overrides):
        """Helper to create vector reader agent with common configuration."""
        context = {
            "input_fields": ["query"],
            "output_field": "search_results",
            "description": "Test vector reader agent",
            "k": 5,
            "metadata_keys": ["score", "source"],
            **context_overrides,
        }

        return VectorReaderAgent(
            name="test_vector_reader",
            prompt="test_collection",
            context=context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

    # =============================================================================
    # 1. Agent Modernization Tests
    # =============================================================================

    def test_agent_inheritance_is_clean(self):
        """Test that agent inherits only from VectorAgent (no mixins)."""
        agent = self.create_vector_reader_agent()

        # Verify inheritance chain
        self.assertIsInstance(agent, VectorReaderAgent)
        self.assertIsInstance(agent, VectorAgent)

        # Check that no mixin classes are in the MRO
        mro_class_names = [cls.__name__ for cls in agent.__class__.__mro__]

        # Should NOT contain any mixin classes
        self.assertNotIn("ReaderOperationsMixin", mro_class_names)
        self.assertNotIn("StorageErrorHandlerMixin", mro_class_names)
        self.assertNotIn("WriterOperationsMixin", mro_class_names)

        # Should contain expected base classes
        self.assertIn("VectorReaderAgent", mro_class_names)
        self.assertIn("VectorAgent", mro_class_names)
        self.assertIn("BaseStorageAgent", mro_class_names)

    def test_agent_instantiation_without_errors(self):
        """Test that agent can be instantiated without errors."""
        try:
            agent = self.create_vector_reader_agent()
            self.assertIsNotNone(agent)
            self.assertEqual(agent.name, "test_vector_reader")
            self.assertEqual(agent.prompt, "test_collection")

            # Verify vector-specific configuration (inherited from VectorAgent)
            self.assertEqual(agent.k, 5)
            self.assertEqual(agent.metadata_keys, ["score", "source"])
        except Exception as e:
            self.fail(f"Agent instantiation failed: {e}")

    def test_agent_has_required_methods(self):
        """Test that agent has all required methods after mixin removal."""
        agent = self.create_vector_reader_agent()

        # Core BaseStorageAgent methods should be available
        self.assertTrue(hasattr(agent, "process"))
        self.assertTrue(hasattr(agent, "_execute_operation"))
        self.assertTrue(hasattr(agent, "_validate_inputs"))
        self.assertTrue(hasattr(agent, "_log_operation_start"))

        # Should NOT have mixin-specific methods
        self.assertFalse(hasattr(agent, "_validate_reader_inputs"))
        self.assertFalse(hasattr(agent, "_handle_storage_error"))

    # =============================================================================
    # 2. Service Delegation Tests
    # =============================================================================

    def test_service_delegation_setup(self):
        """Test that service delegation is properly set up."""
        agent = self.create_vector_reader_agent()

        # Configure the vector service (simulating dependency injection)
        agent.configure_vector_service(self.mock_vector_service)

        # Verify the service is accessible
        self.assertEqual(agent.vector_service, self.mock_vector_service)

    def test_vector_service_configuration(self):
        """Test that configure_vector_service properly sets up the service."""
        agent = self.create_vector_reader_agent()

        # Initially should raise error if accessed
        with self.assertRaises(ValueError) as cm:
            _ = agent.vector_service
        self.assertIn("Vector service not configured", str(cm.exception))

        # After configuration should be set
        agent.configure_vector_service(self.mock_vector_service)
        self.assertIsNotNone(agent.vector_service)
        self.assertEqual(agent.vector_service, self.mock_vector_service)
        self.assertEqual(agent._client, self.mock_vector_service)

    def test_execute_operation_calls_vector_service(self):
        """Test that _execute_operation properly delegates to vector_service."""
        agent = self.create_vector_reader_agent()
        agent.configure_vector_service(self.mock_vector_service)

        # Test inputs
        collection = "documents_index"
        inputs = {
            "query": "artificial intelligence machine learning",
            "k": 3,
            "metadata_keys": ["source", "timestamp"],
        }

        # Execute operation
        result = agent._execute_operation(collection, inputs)

        # Verify vector_service.read was called with correct parameters
        self.mock_vector_service.read.assert_called_once_with(
            collection=collection,
            query={"text": "artificial intelligence machine learning"},
            k=3,
            metadata_keys=["source", "timestamp"],
        )

        # Verify result structure is preserved (key feature of VectorReaderAgent)
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
        self.assertIn("query", result)
        self.assertIn("results", result)
        self.assertIn("count", result)

        # Verify result values
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["query"], "artificial intelligence machine learning")
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["results"]), 3)

    def test_execute_operation_with_defaults(self):
        """Test _execute_operation uses agent defaults for k and metadata_keys."""
        agent = self.create_vector_reader_agent(k=10, metadata_keys=["score"])
        agent.configure_vector_service(self.mock_vector_service)

        collection = "test_collection"
        inputs = {
            "query": "test search query"
            # No k or metadata_keys specified - should use agent defaults
        }

        result = agent._execute_operation(collection, inputs)

        # Verify service called with agent defaults
        self.mock_vector_service.read.assert_called_once_with(
            collection=collection,
            query={"text": "test search query"},
            k=10,  # Agent default
            metadata_keys=["score"],  # Agent default
        )

    def test_execute_operation_missing_query_error(self):
        """Test _execute_operation handles missing query gracefully."""
        agent = self.create_vector_reader_agent()
        agent.configure_vector_service(self.mock_vector_service)

        collection = "test_collection"
        inputs = {}  # No query provided

        result = agent._execute_operation(collection, inputs)

        # Should return error result
        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "error")
        self.assertIn("No query provided", result["error"])

        # Vector service should not be called
        self.mock_vector_service.read.assert_not_called()

    def test_execute_operation_vector_service_failure(self):
        """Test _execute_operation handles vector service failure."""
        agent = self.create_vector_reader_agent()
        agent.configure_vector_service(self.mock_vector_service)

        # Configure vector service to return None (failure)
        self.mock_vector_service.read.return_value = None

        collection = "test_collection"
        inputs = {"query": "test query"}

        result = agent._execute_operation(collection, inputs)

        # Should return error result
        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "error")
        self.assertIn("Vector search failed", result["error"])

    # =============================================================================
    # 3. Result Formatting Tests (Critical for VectorReaderAgent)
    # =============================================================================

    def test_result_formatting_structure(self):
        """Test that result formatting structure is preserved."""
        agent = self.create_vector_reader_agent()
        agent.configure_vector_service(self.mock_vector_service)

        collection = "docs"
        inputs = {"query": "machine learning"}

        result = agent._execute_operation(collection, inputs)

        # Verify exact result structure
        expected_keys = {"status", "query", "results", "count"}
        self.assertEqual(set(result.keys()), expected_keys)

        # Verify types
        self.assertIsInstance(result["status"], str)
        self.assertIsInstance(result["query"], str)
        self.assertIsInstance(result["results"], list)
        self.assertIsInstance(result["count"], int)

    def test_result_count_accuracy(self):
        """Test that result count matches actual results length."""
        agent = self.create_vector_reader_agent()
        agent.configure_vector_service(self.mock_vector_service)

        # Configure different result sizes
        test_results = [
            [],  # Empty results
            [{"content": "single result"}],  # Single result
            [{"content": f"result {i}"} for i in range(5)],  # Multiple results
        ]

        for expected_results in test_results:
            with self.subTest(result_count=len(expected_results)):
                self.mock_vector_service.read.return_value = expected_results

                result = agent._execute_operation("test", {"query": "test"})

                self.assertEqual(result["count"], len(expected_results))
                self.assertEqual(len(result["results"]), len(expected_results))
                self.assertEqual(result["results"], expected_results)

    # =============================================================================
    # 4. Integration Tests
    # =============================================================================

    def test_logging_integration(self):
        """Test that logging works correctly after mixin removal."""
        agent = self.create_vector_reader_agent()

        collection = "test_docs"
        inputs = {"query": "artificial intelligence and machine learning algorithms"}

        # Call log operation start
        agent._log_operation_start(collection, inputs)

        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]

        # Should have logged the search operation with query preview
        logged_messages = [call[1] for call in debug_calls]
        search_logged = any(
            "Starting vector search with query" in msg for msg in logged_messages
        )
        self.assertTrue(
            search_logged, f"Expected vector search logged, got: {logged_messages}"
        )

        # Verify query preview truncation for long queries
        truncated_logged = any(
            "artificial intelligence and ma..." in msg for msg in logged_messages
        )
        self.assertTrue(truncated_logged, "Expected query to be truncated in log")

    def test_input_fields_configuration(self):
        """Test that input_fields configuration works correctly."""
        custom_input_fields = ["search_text", "user_query"]
        agent = self.create_vector_reader_agent(input_fields=custom_input_fields)
        agent.configure_vector_service(self.mock_vector_service)

        # Verify input_fields were set correctly
        self.assertEqual(agent.input_fields, custom_input_fields)

        # Test with custom input field
        collection = "docs"
        inputs = {
            "search_text": "custom field query"
        }  # Using first field from custom input_fields

        result = agent._execute_operation(collection, inputs)

        # Should use the custom input field
        self.mock_vector_service.read.assert_called_once()
        call_args = self.mock_vector_service.read.call_args
        self.assertEqual(call_args.kwargs["query"]["text"], "custom field query")

    def test_validation_integration(self):
        """Test that validation works correctly with custom _validate_inputs."""
        agent = self.create_vector_reader_agent()

        # Mock get_collection to return test collection
        with patch.object(agent, "get_collection", return_value="test_collection"):
            inputs = {"query": "valid query"}

            # Should not raise any exceptions
            try:
                agent._validate_inputs(inputs)
            except Exception as e:
                self.fail(f"Validation failed unexpectedly: {e}")

    def test_vector_agent_inheritance_preserved(self):
        """Test that VectorAgent functionality is preserved."""
        agent = self.create_vector_reader_agent(k=7, metadata_keys=["custom_key"])

        # Verify VectorAgent properties are accessible
        self.assertEqual(agent.k, 7)
        self.assertEqual(agent.metadata_keys, ["custom_key"])

        # Verify input_fields default from context (not hardcoded)
        self.assertEqual(agent.input_fields, ["query"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
