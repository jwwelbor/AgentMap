"""
Unit tests for CSVWriterAgent direct field mapping enhancement.

Tests that CSVWriterAgent can use input fields directly as CSV columns
without requiring a 'data' wrapper field.
"""

import unittest
from unittest.mock import Mock

from agentmap.agents.builtins.storage.csv.writer import CSVWriterAgent
from agentmap.models.storage import DocumentResult, WriteMode
from tests.utils.mock_service_factory import MockServiceFactory


class TestCSVWriterDirectFieldMapping(unittest.TestCase):
    """Test suite for CSVWriterAgent direct field mapping feature."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock services
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )

        # Get mock logger
        self.mock_logger = self.mock_logging_service.get_class_logger(CSVWriterAgent)

        # Create mock CSV service
        self.mock_csv_service = Mock()
        self.write_calls = []

        def capture_write(collection, data, **kwargs):
            """Capture write calls for verification."""
            self.write_calls.append(
                {"collection": collection, "data": data, "kwargs": kwargs}
            )
            return DocumentResult(
                success=True,
                file_path=collection,
                data={"rows_written": 1 if isinstance(data, dict) else len(data)},
            )

        self.mock_csv_service.write = Mock(side_effect=capture_write)

    def create_csv_writer_agent(self, **context_overrides):
        """Helper to create CSV writer agent."""
        context = {"output_field": "write_result", **context_overrides}

        agent = CSVWriterAgent(
            name="test_csv_writer",
            prompt="test.csv",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        # Configure CSV service
        agent.configure_csv_service(self.mock_csv_service)

        return agent

    def test_direct_field_mapping_single_row(self):
        """Test that input fields are used directly as CSV columns for single row."""
        agent = self.create_csv_writer_agent()

        # Input fields that should become CSV columns
        inputs = {
            "customer_name": "Alice Johnson",
            "account_number": "ACC-12345",
            "balance": 1500.50,
            "status": "active",
        }

        # Execute operation
        result = agent._execute_operation("accounts.csv", inputs)

        # Verify success
        self.assertTrue(result.success)

        # Verify CSV service was called with correct data
        self.assertEqual(len(self.write_calls), 1)
        write_call = self.write_calls[0]

        # All input fields should be in data
        self.assertEqual(write_call["data"], inputs)
        self.assertEqual(write_call["collection"], "accounts.csv")

    def test_control_fields_excluded_from_data(self):
        """Test that control fields are not included in CSV data."""
        agent = self.create_csv_writer_agent()

        inputs = {
            # Data fields
            "product_id": "PRD-001",
            "product_name": "Widget Pro",
            "price": 49.99,
            # Control fields
            "mode": "append",
            "document_id": "PRD-001",
            "id_field": "product_id",
        }

        # Execute operation
        result = agent._execute_operation("products.csv", inputs)

        # Verify success
        self.assertTrue(result.success)

        # Check what was written
        write_call = self.write_calls[0]

        # Data should only contain non-control fields
        expected_data = {
            "product_id": "PRD-001",
            "product_name": "Widget Pro",
            "price": 49.99,
        }
        self.assertEqual(write_call["data"], expected_data)

        # Control fields should be in kwargs
        self.assertEqual(write_call["kwargs"]["mode"], WriteMode.APPEND)
        self.assertEqual(write_call["kwargs"]["document_id"], "PRD-001")
        self.assertEqual(write_call["kwargs"]["id_field"], "product_id")

    def test_backward_compatibility_with_data_field(self):
        """Test that 'data' field still works for backward compatibility."""
        agent = self.create_csv_writer_agent()

        # Traditional format with 'data' field
        inputs = {
            "data": {"order_id": "ORD-789", "customer": "Bob Smith", "total": 299.99},
            "mode": "write",
        }

        # Execute operation
        result = agent._execute_operation("orders.csv", inputs)

        # Verify success
        self.assertTrue(result.success)

        # Check that data field was used
        write_call = self.write_calls[0]
        self.assertEqual(write_call["data"], inputs["data"])
        self.assertEqual(write_call["kwargs"]["mode"], WriteMode.WRITE)

    def test_data_field_takes_precedence(self):
        """Test that 'data' field takes precedence when both patterns exist."""
        agent = self.create_csv_writer_agent()

        inputs = {
            # These should be ignored
            "name": "Should be ignored",
            "value": "Also ignored",
            # This should be used
            "data": {"actual_name": "John", "actual_value": 100},
        }

        # Execute operation
        result = agent._execute_operation("test.csv", inputs)

        # Verify success
        self.assertTrue(result.success)

        # Only 'data' field content should be written
        write_call = self.write_calls[0]
        self.assertEqual(write_call["data"], inputs["data"])
        self.assertNotIn("name", write_call["data"])
        self.assertNotIn("value", write_call["data"])

    def test_empty_data_returns_error(self):
        """Test that empty data (only control fields) returns an error."""
        agent = self.create_csv_writer_agent()

        # Only control fields, no actual data
        inputs = {"mode": "write", "document_id": "123", "path": None, "id_field": "id"}

        # Execute operation
        result = agent._execute_operation("empty.csv", inputs)

        # Should fail
        self.assertFalse(result.success)
        self.assertIn("No data provided", result.error)

        # CSV service should not be called
        self.assertEqual(len(self.write_calls), 0)

    def test_mixed_data_types_handled(self):
        """Test that various data types are handled correctly."""
        agent = self.create_csv_writer_agent()

        inputs = {
            "string_val": "text",
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
            "none_val": None,
            "list_val": [1, 2, 3],  # Will be converted to string by pandas
            "dict_val": {"nested": "data"},  # Will be converted to string
        }

        # Execute operation
        result = agent._execute_operation("mixed_types.csv", inputs)

        # Should succeed
        self.assertTrue(result.success)

        # All fields should be passed to CSV service
        write_call = self.write_calls[0]
        self.assertEqual(write_call["data"], inputs)

    def test_write_modes_work_correctly(self):
        """Test that different write modes are handled correctly."""
        agent = self.create_csv_writer_agent()

        # Test WRITE mode
        inputs_write = {"data": {"test": "write"}, "mode": "write"}
        result = agent._execute_operation("test.csv", inputs_write)
        self.assertTrue(result.success)
        self.assertEqual(self.write_calls[-1]["kwargs"]["mode"], WriteMode.WRITE)

        # Test APPEND mode
        inputs_append = {"data": {"test": "append"}, "mode": "append"}
        result = agent._execute_operation("test.csv", inputs_append)
        self.assertTrue(result.success)
        self.assertEqual(self.write_calls[-1]["kwargs"]["mode"], WriteMode.APPEND)

        # Test UPDATE mode
        inputs_update = {
            "data": {"test": "update"},
            "mode": "update",
            "document_id": "test_id",
        }
        result = agent._execute_operation("test.csv", inputs_update)
        self.assertTrue(result.success)
        self.assertEqual(self.write_calls[-1]["kwargs"]["mode"], WriteMode.UPDATE)

    def test_alternative_file_path_fields_excluded(self):
        """Test that alternative file path fields are excluded from data."""
        agent = self.create_csv_writer_agent()

        inputs = {
            "name": "Test User",
            "email": "test@example.com",
            "file_path": "should_be_excluded.csv",  # Control field
            "csv_file": "also_excluded.csv",  # Control field
            "collection": "excluded_too.csv",  # Control field
        }

        # Execute operation
        result = agent._execute_operation("users.csv", inputs)

        # Verify success
        self.assertTrue(result.success)

        # Check that file path fields were excluded
        write_call = self.write_calls[0]
        expected_data = {"name": "Test User", "email": "test@example.com"}
        self.assertEqual(write_call["data"], expected_data)
        self.assertNotIn("file_path", write_call["data"])
        self.assertNotIn("csv_file", write_call["data"])
        self.assertNotIn("collection", write_call["data"])

    def test_list_data_in_data_field(self):
        """Test that list of dicts in 'data' field works for multiple rows."""
        agent = self.create_csv_writer_agent()

        inputs = {
            "data": [
                {"id": 1, "name": "Item 1", "qty": 10},
                {"id": 2, "name": "Item 2", "qty": 20},
                {"id": 3, "name": "Item 3", "qty": 30},
            ],
            "mode": "write",
        }

        # Execute operation
        result = agent._execute_operation("inventory.csv", inputs)

        # Verify success
        self.assertTrue(result.success)

        # Check that list was passed correctly
        write_call = self.write_calls[0]
        self.assertEqual(write_call["data"], inputs["data"])
        self.assertIsInstance(write_call["data"], list)
        self.assertEqual(len(write_call["data"]), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
