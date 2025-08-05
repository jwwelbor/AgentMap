"""
Unit tests for CSV Agent auto-creation functionality.

This test suite verifies that the CSV auto-creation fix works correctly,
specifically testing the override of _validate_inputs() in CSVAgent to support
auto-creation when auto_create_files: true and file doesn't exist.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any
import os

from agentmap.agents.builtins.storage.csv.base_agent import CSVAgent
from agentmap.agents.builtins.storage.csv.writer import CSVWriterAgent
from agentmap.agents.builtins.storage.csv.reader import CSVReaderAgent
from agentmap.models.storage import DocumentResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestCSVAgentAutoCreation(unittest.TestCase):
    """Test suite for CSV Agent auto-creation functionality."""
    
    def setUp(self):
        """Set up test fixtures with mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(CSVAgent)
        
        # Create mock CSV service with configuration
        self.mock_csv_service = Mock()
        self.mock_csv_configuration = Mock()
        self.mock_csv_service.configuration = self.mock_csv_configuration
        
        # Default configuration behavior
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = False
        self.mock_csv_service._get_file_path.return_value = "/full/path/to/test.csv"
    
    def create_csv_writer_agent(self, **context_overrides):
        """Helper to create CSV writer agent with common configuration."""
        context = {
            "input_fields": ["file_path", "data"],
            "output_field": "write_result",
            "description": "Test CSV writer agent",
            **context_overrides
        }
        
        return CSVWriterAgent(
            name="test_csv_writer",
            prompt="Write to test.csv",
            context=context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
    
    def create_csv_reader_agent(self, **context_overrides):
        """Helper to create CSV reader agent with common configuration."""
        context = {
            "input_fields": ["file_path", "query"],
            "output_field": "read_result",
            "description": "Test CSV reader agent",
            **context_overrides
        }
        
        return CSVReaderAgent(
            name="test_csv_reader",
            prompt="Read from test.csv",
            context=context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )

    # =============================================================================
    # 1. Auto-Creation Support Tests
    # =============================================================================
    
    def test_write_operation_with_auto_creation_enabled_skips_validation(self):
        """Test that write operations with auto-creation enabled skip file existence validation."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Enable auto-creation
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = True
        
        # Mock get_collection to return non-existent file
        with patch.object(agent, 'get_collection', return_value='nonexistent.csv'):
            with patch('os.path.exists', return_value=False):
                inputs = {
                    "file_path": "nonexistent.csv",
                    "data": [{"name": "John", "age": 25}]
                }
                
                # Should NOT raise FileNotFoundError because validation is skipped
                try:
                    agent._validate_inputs(inputs)
                except FileNotFoundError:
                    self.fail("Validation should have been skipped for write operation with auto-creation enabled")
                
                # Verify debug log about skipping validation
                logger_calls = self.mock_logger.calls
                debug_calls = [call for call in logger_calls if call[0] == "debug"]
                skip_logged = any("Skipping file existence validation" in call[1] for call in debug_calls)
                self.assertTrue(skip_logged, "Expected skip validation log message")

    def test_write_operation_with_auto_creation_disabled_uses_strict_validation(self):
        """Test that write operations with auto-creation disabled use strict validation."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Disable auto-creation (default)
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = False
        
        # Mock get_collection to return non-existent file
        with patch.object(agent, 'get_collection', return_value='nonexistent.csv'):
            with patch('os.path.exists', return_value=False):
                inputs = {
                    "file_path": "nonexistent.csv", 
                    "data": [{"name": "John", "age": 25}]
                }
                
                # Should raise FileNotFoundError because strict validation is used
                with self.assertRaises(FileNotFoundError):
                    agent._validate_inputs(inputs)
                
                # Verify debug log about using strict validation
                logger_calls = self.mock_logger.calls
                debug_calls = [call for call in logger_calls if call[0] == "debug"]
                strict_logged = any("Using strict validation (auto-creation disabled)" in call[1] for call in debug_calls)
                self.assertTrue(strict_logged, "Expected strict validation log message")

    def test_read_operation_always_uses_strict_validation(self):
        """Test that read operations always use strict validation regardless of auto-creation setting."""
        agent = self.create_csv_reader_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Enable auto-creation
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = True
        
        # Mock get_collection to return non-existent file
        with patch.object(agent, 'get_collection', return_value='nonexistent.csv'):
            with patch('os.path.exists', return_value=False):
                inputs = {"file_path": "nonexistent.csv"}  # No 'data' field = read operation
                
                # Should raise FileNotFoundError even with auto-creation enabled
                with self.assertRaises(FileNotFoundError):
                    agent._validate_inputs(inputs)
                
                # Verify debug log about strict validation for read
                logger_calls = self.mock_logger.calls
                debug_calls = [call for call in logger_calls if call[0] == "debug"]
                strict_logged = any("Using strict validation for read operation" in call[1] for call in debug_calls)
                self.assertTrue(strict_logged, "Expected strict validation for read operation log")

    def test_auto_creation_validation_with_existing_file(self):
        """Test that validation works normally when file exists, regardless of auto-creation setting."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Enable auto-creation
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = True
        
        # Mock get_collection to return existing file
        with patch.object(agent, 'get_collection', return_value='existing.csv'):
            with patch('os.path.exists', return_value=True):
                inputs = {
                    "file_path": "existing.csv",
                    "data": [{"name": "John", "age": 25}]
                }
                
                # Should pass validation without issues
                try:
                    agent._validate_inputs(inputs)
                except Exception as e:
                    self.fail(f"Validation failed unexpectedly for existing file: {e}")

    def test_missing_collection_parameter_still_raises_error(self):
        """Test that missing collection parameter still raises ValueError with auto-creation enabled."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Enable auto-creation
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = True
        
        # Mock get_collection to return None (missing)
        with patch.object(agent, 'get_collection', return_value=None):
            inputs = {"data": [{"name": "John", "age": 25}]}  # Missing collection
            
            # Should still raise ValueError for missing collection
            with self.assertRaises(ValueError) as cm:
                agent._validate_inputs(inputs)
            
            self.assertIn("Missing required 'collection' parameter", str(cm.exception))

    # =============================================================================
    # 2. Helper Method Tests
    # =============================================================================
    
    def test_is_auto_creation_enabled_with_configured_service(self):
        """Test _is_auto_creation_enabled returns correct value when service is configured."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Test enabled
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = True
        self.assertTrue(agent._is_auto_creation_enabled())
        
        # Test disabled
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = False
        self.assertFalse(agent._is_auto_creation_enabled())

    def test_is_auto_creation_enabled_without_configured_service(self):
        """Test _is_auto_creation_enabled returns False when service is not configured."""
        agent = self.create_csv_writer_agent()
        # Don't configure CSV service
        
        result = agent._is_auto_creation_enabled()
        self.assertFalse(result)
        
        # Verify debug log about service not configured
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        not_configured_logged = any("CSV service not yet configured" in call[1] for call in debug_calls)
        self.assertTrue(not_configured_logged, "Expected service not configured log message")

    def test_is_auto_creation_enabled_handles_exceptions(self):
        """Test _is_auto_creation_enabled handles exceptions gracefully."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Make configuration method raise exception
        self.mock_csv_configuration.is_csv_auto_create_enabled.side_effect = Exception("Config error")
        
        result = agent._is_auto_creation_enabled()
        self.assertFalse(result)
        
        # Verify debug log about error
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        error_logged = any("Could not check auto-creation setting" in call[1] for call in debug_calls)
        self.assertTrue(error_logged, "Expected auto-creation check error log message")

    def test_is_write_operation_with_data_field(self):
        """Test _is_write_operation returns True when 'data' field is present."""
        agent = self.create_csv_writer_agent()
        
        inputs = {"data": [{"name": "John", "age": 25}]}
        self.assertTrue(agent._is_write_operation(inputs))

    def test_is_write_operation_without_data_field(self):
        """Test _is_write_operation returns False when 'data' field is not present."""
        agent = self.create_csv_writer_agent()
        
        inputs = {"file_path": "test.csv", "query": {"name": "John"}}
        self.assertFalse(agent._is_write_operation(inputs))

    def test_is_write_operation_with_empty_inputs(self):
        """Test _is_write_operation returns False with empty inputs."""
        agent = self.create_csv_writer_agent()
        
        inputs = {}
        self.assertFalse(agent._is_write_operation(inputs))

    # =============================================================================
    # 3. Error Handling Enhancement Tests
    # =============================================================================
    
    def test_get_full_file_path_with_configured_service(self):
        """Test _get_full_file_path returns resolved path when service is configured."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Mock service to return full path
        self.mock_csv_service._get_file_path.return_value = "/full/path/to/data.csv"
        
        result = agent._get_full_file_path("data.csv")
        self.assertEqual(result, "/full/path/to/data.csv")
        self.mock_csv_service._get_file_path.assert_called_once_with("data.csv")

    def test_get_full_file_path_without_configured_service(self):
        """Test _get_full_file_path returns original collection when service is not configured."""
        agent = self.create_csv_writer_agent()
        # Don't configure CSV service
        
        result = agent._get_full_file_path("data.csv")
        self.assertEqual(result, "data.csv")

    def test_get_full_file_path_handles_exceptions(self):
        """Test _get_full_file_path handles exceptions gracefully."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Make service method raise exception
        self.mock_csv_service._get_file_path.side_effect = Exception("Path resolution error")
        
        result = agent._get_full_file_path("data.csv")
        self.assertEqual(result, "data.csv")  # Should fallback to original
        
        # Verify debug log about error
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        error_logged = any("Could not resolve full file path" in call[1] for call in debug_calls)
        self.assertTrue(error_logged, "Expected path resolution error log message")

    def test_get_auto_creation_context_when_enabled(self):
        """Test _get_auto_creation_context when auto-creation is enabled."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Enable auto-creation
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = True
        
        result = agent._get_auto_creation_context()
        self.assertEqual(result, "Auto-creation is enabled but failed")

    def test_get_auto_creation_context_when_disabled(self):
        """Test _get_auto_creation_context when auto-creation is disabled."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Disable auto-creation
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = False
        
        result = agent._get_auto_creation_context()
        expected = "Auto-creation is disabled. Enable with 'auto_create_files: true' in CSV config"
        self.assertEqual(result, expected)

    def test_get_auto_creation_context_handles_exceptions(self):
        """Test _get_auto_creation_context handles exceptions gracefully."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Make is_auto_creation_enabled raise exception  
        with patch.object(agent, '_is_auto_creation_enabled', side_effect=Exception("Config error")):
            result = agent._get_auto_creation_context()
            self.assertEqual(result, "Could not determine auto-creation settings")

    def test_enhanced_file_not_found_error_handling(self):
        """Test enhanced FileNotFoundError handling with full paths and auto-creation context."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Setup mocks
        self.mock_csv_service._get_file_path.return_value = "/full/path/to/nonexistent.csv"
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = False
        
        # Create FileNotFoundError
        error = FileNotFoundError("File not found")
        collection = "nonexistent.csv"
        inputs = {"data": [{"name": "John"}]}  # Write operation
        
        # Handle the error
        result = agent._handle_operation_error(error, collection, inputs)
        
        # Verify result
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertEqual(result.file_path, "/full/path/to/nonexistent.csv")  # Should use full path
        
        # Verify error message contains all expected elements
        expected_elements = [
            "CSV file not found: 'nonexistent.csv'",
            "resolved to: '/full/path/to/nonexistent.csv'",
            "Auto-creation is disabled",
            "Enable with 'auto_create_files: true'",
            "For write operations, consider enabling auto-creation"
        ]
        
        for element in expected_elements:
            self.assertIn(element, result.error, f"Expected '{element}' in error message: {result.error}")

    def test_enhanced_file_not_found_error_for_read_operation(self):
        """Test enhanced FileNotFoundError handling for read operations."""
        agent = self.create_csv_reader_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Setup mocks
        self.mock_csv_service._get_file_path.return_value = "/full/path/to/missing.csv"
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = True  # Even when enabled
        
        # Create FileNotFoundError
        error = FileNotFoundError("File not found")
        collection = "missing.csv"
        inputs = {"query": {"name": "John"}}  # Read operation (no 'data' field)
        
        # Handle the error
        result = agent._handle_operation_error(error, collection, inputs)
        
        # Verify result
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        
        # Verify error message for read operation
        expected_elements = [
            "CSV file not found: 'missing.csv'",
            "File must exist for read operations"
        ]
        
        for element in expected_elements:
            self.assertIn(element, result.error, f"Expected '{element}' in error message: {result.error}")

    def test_enhanced_error_handling_for_other_errors(self):
        """Test enhanced error handling for non-FileNotFoundError exceptions."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Setup mocks
        self.mock_csv_service._get_file_path.return_value = "/full/path/to/protected.csv"
        
        # Create PermissionError
        error = PermissionError("Permission denied")
        collection = "protected.csv"
        inputs = {"data": [{"name": "John"}]}
        
        # Mock the base class error handler
        base_result = DocumentResult(
            success=False,
            file_path="protected.csv",
            error="Permission denied accessing protected.csv"
        )
        
        with patch('agentmap.agents.builtins.storage.base_storage_agent.BaseStorageAgent._handle_operation_error', 
                   return_value=base_result):
            result = agent._handle_operation_error(error, collection, inputs)
            
            # Should enhance the error with full path
            self.assertIsInstance(result, DocumentResult)
            self.assertFalse(result.success)
            self.assertEqual(result.file_path, "/full/path/to/protected.csv")  # Enhanced with full path
            self.assertIn("resolved to: /full/path/to/protected.csv", result.error)

    # =============================================================================
    # 4. Integration Tests
    # =============================================================================
    
    def test_auto_creation_scenario_end_to_end(self):
        """Test the complete auto-creation scenario that was failing before the fix."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Enable auto-creation
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = True
        
        # Test scenario: file doesn't exist, auto-creation enabled, write operation
        collection = "personal_goals.csv"
        inputs = {
            "file_path": "personal_goals.csv",
            "data": [
                {"goal": "Learn Python", "status": "in_progress"},
                {"goal": "Exercise daily", "status": "active"}
            ]
        }
        
        with patch.object(agent, 'get_collection', return_value=collection):
            with patch('os.path.exists', return_value=False):  # File doesn't exist
                
                # This should NOT raise FileNotFoundError (the original issue)
                try:
                    agent._validate_inputs(inputs)
                    # If we get here, the fix worked!
                    validation_passed = True
                except FileNotFoundError:
                    validation_passed = False
                    self.fail("Auto-creation fix failed: FileNotFoundError was raised when it should have been skipped")
                
                self.assertTrue(validation_passed, "Validation should have passed for auto-creation scenario")
                
                # Verify the right log messages were generated
                logger_calls = self.mock_logger.calls  
                debug_calls = [call[1] for call in logger_calls if call[0] == "debug"]
                
                skip_validation_logged = any("Skipping file existence validation" in msg for msg in debug_calls)
                self.assertTrue(skip_validation_logged, 
                              "Expected 'Skipping file existence validation' log message")

    def test_backward_compatibility_with_existing_functionality(self):
        """Test that existing functionality still works (no regression)."""
        agent = self.create_csv_reader_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Disable auto-creation (typical existing setup)
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = False
        
        # Test existing file read scenario
        collection = "existing_data.csv"
        inputs = {"file_path": "existing_data.csv", "query": {"status": "active"}}
        
        with patch.object(agent, 'get_collection', return_value=collection):
            with patch('os.path.exists', return_value=True):  # File exists
                
                # Should pass validation normally
                try:
                    agent._validate_inputs(inputs)
                except Exception as e:
                    self.fail(f"Existing functionality broken: {e}")
        
        # Test non-existent file read scenario (should still fail)
        with patch.object(agent, 'get_collection', return_value='missing.csv'):
            with patch('os.path.exists', return_value=False):  # File missing
                inputs_missing = {"file_path": "missing.csv"}
                
                # Should still raise FileNotFoundError for missing files
                with self.assertRaises(FileNotFoundError):
                    agent._validate_inputs(inputs_missing)

    def test_csv_extension_warning_still_works(self):
        """Test that CSV extension warning functionality is preserved."""
        agent = self.create_csv_writer_agent()
        agent.configure_csv_service(self.mock_csv_service)
        
        # Enable auto-creation
        self.mock_csv_configuration.is_csv_auto_create_enabled.return_value = True
        
        # Test with non-CSV extension
        collection = "data.txt"  # Not .csv extension
        inputs = {"data": [{"name": "John"}]}
        
        with patch.object(agent, 'get_collection', return_value=collection):
            with patch('os.path.exists', return_value=False):
                
                # Should not raise exception but should log warning
                try:
                    agent._validate_inputs(inputs)
                except Exception as e:
                    self.fail(f"Validation failed unexpectedly: {e}")
                
                # Check that warning was logged
                logger_calls = self.mock_logger.calls
                warning_calls = [call for call in logger_calls if call[0] == "warning"]
                extension_warning = any("does not end with .csv" in call[1] for call in warning_calls)
                self.assertTrue(extension_warning, "Expected CSV extension warning to be logged")


if __name__ == '__main__':
    unittest.main(verbosity=2)
