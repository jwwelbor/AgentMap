"""
Unit tests for modernized JSONDocumentReaderAgent.

This test suite verifies that JSONDocumentReaderAgent works correctly after
mixin removal, ensuring clean architecture and proper service delegation.
"""

import unittest
from typing import Any, Dict
from unittest.mock import Mock, patch

from agentmap.agents.builtins.storage.json.base_agent import JSONDocumentAgent
from agentmap.agents.builtins.storage.json.reader import JSONDocumentReaderAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestModernizedJSONDocumentReaderAgent(unittest.TestCase):
    """Test suite for modernized JSONDocumentReaderAgent."""

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
        self.mock_logger = self.mock_logging_service.get_class_logger(
            JSONDocumentReaderAgent
        )

        # Create mock JSON service
        self.mock_json_service = Mock()
        self.mock_json_service.read.return_value = {"test": "data", "items": [1, 2, 3]}

    def create_json_reader_agent(self, **context_overrides):
        """Helper to create JSON reader agent with common configuration."""
        context = {
            "input_fields": ["collection", "query"],
            "output_field": "json_data",
            "description": "Test JSON reader agent",
            **context_overrides,
        }

        return JSONDocumentReaderAgent(
            name="test_json_reader",
            prompt="test_file.json",
            context=context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

    # =============================================================================
    # 1. Agent Modernization Tests
    # =============================================================================

    def test_agent_inheritance_is_clean(self):
        """Test that agent inherits only from JSONDocumentAgent (no mixins)."""
        agent = self.create_json_reader_agent()

        # Verify inheritance chain
        self.assertIsInstance(agent, JSONDocumentReaderAgent)
        self.assertIsInstance(agent, JSONDocumentAgent)

        # Check that no mixin classes are in the MRO
        mro_class_names = [cls.__name__ for cls in agent.__class__.__mro__]

        # Should NOT contain any mixin classes
        self.assertNotIn("ReaderOperationsMixin", mro_class_names)
        self.assertNotIn("StorageErrorHandlerMixin", mro_class_names)
        self.assertNotIn("WriterOperationsMixin", mro_class_names)

        # Should contain expected base classes
        self.assertIn("JSONDocumentReaderAgent", mro_class_names)
        self.assertIn("JSONDocumentAgent", mro_class_names)
        self.assertIn("BaseStorageAgent", mro_class_names)

    def test_agent_instantiation_without_errors(self):
        """Test that agent can be instantiated without errors."""
        try:
            agent = self.create_json_reader_agent()
            self.assertIsNotNone(agent)
            self.assertEqual(agent.name, "test_json_reader")
            self.assertEqual(agent.prompt, "test_file.json")
        except Exception as e:
            self.fail(f"Agent instantiation failed: {e}")

    def test_agent_has_required_methods(self):
        """Test that agent has all required methods after mixin removal."""
        agent = self.create_json_reader_agent()

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
        agent = self.create_json_reader_agent()

        # Configure the JSON service (simulating dependency injection)
        agent.configure_json_service(self.mock_json_service)

        # Verify the service is accessible
        self.assertEqual(agent.json_service, self.mock_json_service)

    def test_json_service_configuration(self):
        """Test that configure_json_service properly sets up the service."""
        agent = self.create_json_reader_agent()

        # Initially should raise error if accessed
        with self.assertRaises(ValueError) as cm:
            _ = agent.json_service
        self.assertIn("JSON service not configured", str(cm.exception))

        # After configuration should be set
        agent.configure_json_service(self.mock_json_service)
        self.assertIsNotNone(agent.json_service)
        self.assertEqual(agent.json_service, self.mock_json_service)
        self.assertEqual(agent._client, self.mock_json_service)

    def test_execute_operation_calls_json_service(self):
        """Test that _execute_operation properly delegates to json_service."""
        agent = self.create_json_reader_agent()
        agent.configure_json_service(self.mock_json_service)

        # Test inputs
        collection = "test_data.json"
        inputs = {
            "document_id": "doc_123",
            "query": {"field": "value"},
            "path": "data.items",
            "format": "records",
            "id_field": "uid",
            "use_envelope": False,
        }

        # Execute operation
        result = agent._execute_operation(collection, inputs)

        # Verify json_service.read was called with correct parameters
        self.mock_json_service.read.assert_called_once_with(
            collection=collection,
            document_id="doc_123",
            query={"field": "value"},
            path="data.items",
            format="records",
            id_field="uid",
        )

        # Verify result
        self.assertEqual(result, {"test": "data", "items": [1, 2, 3]})

    def test_execute_operation_with_envelope_format(self):
        """Test envelope format backward compatibility."""
        agent = self.create_json_reader_agent()
        agent.configure_json_service(self.mock_json_service)

        collection = "test_data.json"
        inputs = {"document_id": "doc_123", "use_envelope": True}

        result = agent._execute_operation(collection, inputs)

        # Should return envelope format
        expected_envelope = {
            "success": True,
            "document_id": "doc_123",
            "data": {"test": "data", "items": [1, 2, 3]},
            "is_collection": True,  # Because result is a dict
        }

        self.assertEqual(result, expected_envelope)

    def test_execute_operation_with_defaults(self):
        """Test _execute_operation with default parameters."""
        agent = self.create_json_reader_agent()
        agent.configure_json_service(self.mock_json_service)

        collection = "simple.json"
        inputs = {}  # Minimal inputs

        result = agent._execute_operation(collection, inputs)

        # Verify service called with defaults
        self.mock_json_service.read.assert_called_once_with(
            collection=collection,
            document_id=None,
            query=None,
            path=None,
            format="raw",  # Default format
            id_field="id",  # Default id_field
        )

    # =============================================================================
    # 3. Integration Tests
    # =============================================================================

    def test_basic_process_flow_integration(self):
        """Test basic process flow works correctly."""
        agent = self.create_json_reader_agent()
        agent.configure_json_service(self.mock_json_service)

        # Mock get_collection method to return test file
        with patch.object(agent, "get_collection", return_value="test.json"):
            inputs = {"query": {"status": "active"}, "format": "records"}

            # This should not raise any exceptions
            try:
                result = agent._execute_operation("test.json", inputs)
                self.assertIsNotNone(result)
            except Exception as e:
                self.fail(f"Basic process flow failed: {e}")

    def test_logging_integration(self):
        """Test that logging works correctly after mixin removal."""
        agent = self.create_json_reader_agent()
        agent.configure_json_service(self.mock_json_service)

        collection = "test.json"
        inputs = {"format": "records"}

        # Execute operation
        agent._execute_operation(collection, inputs)

        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]

        # Should have logged the read operation
        logged_messages = [call[1] for call in info_calls]
        read_logged = any("Reading from" in msg for msg in logged_messages)
        self.assertTrue(
            read_logged, f"Expected read operation logged, got: {logged_messages}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
