"""
Unit tests for modernized VectorWriterAgent.

This test suite verifies that VectorWriterAgent works correctly after
removing WriterOperationsMixin, ensuring clean architecture and
proper service delegation with correct result formatting.
"""
import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any

from agentmap.agents.builtins.storage.vector.writer import VectorWriterAgent
from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent
from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent
from agentmap.services.protocols import VectorCapableAgent
from agentmap.models.storage import WriteMode, DocumentResult
from tests.utils.mock_service_factory import MockServiceFactory


class TestModernizedVectorWriterAgent(unittest.TestCase):
    """Test suite for modernized VectorWriterAgent."""
    
    def setUp(self):
        """Set up test fixtures with mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(VectorWriterAgent)
        
        # Create mock vector service with realistic write response
        self.mock_vector_service = Mock()
        self.mock_write_result = Mock()
        self.mock_write_result.success = True
        self.mock_write_result.total_affected = 3
        self.mock_write_result.ids = ["doc_1", "doc_2", "doc_3"]
        self.mock_write_result.persist_directory = "/path/to/vector/store"
        self.mock_vector_service.write.return_value = self.mock_write_result
    
    def create_vector_writer_agent(self, **context_overrides):
        """Helper to create vector writer agent with common configuration."""
        context = {
            "input_fields": ["docs"],
            "output_field": "vector_result",
            "description": "Test vector writer agent",
            "should_persist": True,
            "k": 4,
            **context_overrides
        }
        
        return VectorWriterAgent(
            name="test_vector_writer",
            prompt="Store documents in vector database",
            context=context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
    
    # =============================================================================
    # 1. Agent Modernization Tests
    # =============================================================================
    
    def test_agent_inheritance_is_clean(self):
        """Test that agent inherits only from VectorAgent (no mixins)."""
        agent = self.create_vector_writer_agent()
        
        # Verify inheritance chain
        self.assertIsInstance(agent, VectorWriterAgent)
        self.assertIsInstance(agent, VectorAgent)
        self.assertIsInstance(agent, BaseStorageAgent)
        self.assertIsInstance(agent, VectorCapableAgent)
        
        # Check that no mixin classes are in the MRO
        mro_class_names = [cls.__name__ for cls in agent.__class__.__mro__]
        
        # Should NOT contain any mixin classes
        self.assertNotIn("WriterOperationsMixin", mro_class_names)
        self.assertNotIn("ReaderOperationsMixin", mro_class_names)
        self.assertNotIn("StorageErrorHandlerMixin", mro_class_names)
        
        # Should contain expected base classes
        self.assertIn("VectorWriterAgent", mro_class_names)
        self.assertIn("VectorAgent", mro_class_names)
        self.assertIn("BaseStorageAgent", mro_class_names)
        self.assertIn("VectorCapableAgent", mro_class_names)
    
    def test_agent_instantiation_without_errors(self):
        """Test that agent can be instantiated without errors."""
        try:
            agent = self.create_vector_writer_agent()
            self.assertIsNotNone(agent)
            self.assertEqual(agent.name, "test_vector_writer")
            self.assertEqual(agent.prompt, "Store documents in vector database")
            
            # Verify configuration was set correctly
            self.assertTrue(agent.should_persist)
            self.assertEqual(agent.input_fields, ["docs"])
            self.assertEqual(agent.output_field, "vector_result")
            self.assertEqual(agent.k, 4)
        except Exception as e:
            self.fail(f"Agent instantiation failed: {e}")
    
    def test_agent_has_required_methods(self):
        """Test that agent has all required methods after mixin removal."""
        agent = self.create_vector_writer_agent()
        
        # Core BaseStorageAgent methods should be available
        self.assertTrue(hasattr(agent, 'process'))
        self.assertTrue(hasattr(agent, '_execute_operation'))
        self.assertTrue(hasattr(agent, '_validate_inputs'))
        self.assertTrue(hasattr(agent, '_log_operation_start'))
        self.assertTrue(hasattr(agent, '_handle_operation_error'))
        
        # VectorAgent specific methods
        self.assertTrue(hasattr(agent, 'configure_vector_service'))
        
        # Test vector_service property works after configuration
        agent.configure_vector_service(self.mock_vector_service)
        self.assertTrue(hasattr(agent, 'vector_service'))
        
        # Should NOT have mixin-specific methods
        self.assertFalse(hasattr(agent, '_validate_writer_inputs'))
        self.assertFalse(hasattr(agent, '_log_write_operation'))
    
    # =============================================================================
    # 2. Service Delegation Tests  
    # =============================================================================
    
    def test_service_delegation_setup(self):
        """Test that service delegation is properly set up via protocol."""
        agent = self.create_vector_writer_agent()
        
        # Configure vector service via protocol
        agent.configure_vector_service(self.mock_vector_service)
        
        # Verify the service is accessible
        self.assertEqual(agent.vector_service, self.mock_vector_service)
    
    def test_vector_service_not_configured_error(self):
        """Test that accessing vector_service without configuration raises clear error."""
        agent = self.create_vector_writer_agent()
        
        with self.assertRaises(ValueError) as cm:
            _ = agent.vector_service
        
        self.assertIn("Vector service not configured", str(cm.exception))
        self.assertIn("test_vector_writer", str(cm.exception))
    
    def test_execute_operation_calls_vector_service(self):
        """Test that _execute_operation properly delegates to vector_service."""
        agent = self.create_vector_writer_agent()
        agent.configure_vector_service(self.mock_vector_service)
        
        # Test inputs
        collection = "test_documents"
        docs = [
            {"text": "Document 1 content", "metadata": {"source": "file1.txt"}},
            {"text": "Document 2 content", "metadata": {"source": "file2.txt"}},
            {"text": "Document 3 content", "metadata": {"source": "file3.txt"}}
        ]
        inputs = {
            "docs": docs,
            "should_persist": False
        }
        
        # Execute operation
        result = agent._execute_operation(collection, inputs)
        
        # Verify vector_service.write was called with correct parameters
        self.mock_vector_service.write.assert_called_once_with(
            collection=collection,
            data=docs,
            mode=WriteMode.APPEND,
            should_persist=False
        )
        
        # Verify result formatting
        expected_result = {
            "status": "success",
            "stored_count": 3,
            "ids": ["doc_1", "doc_2", "doc_3"],
            "persist_directory": "/path/to/vector/store"
        }
        self.assertEqual(result, expected_result)
    
    def test_execute_operation_with_default_persist(self):
        """Test _execute_operation with default persist setting."""
        agent = self.create_vector_writer_agent(should_persist=True)
        agent.configure_vector_service(self.mock_vector_service)
        
        collection = "test_collection"
        docs = [{"text": "Test document"}]
        inputs = {"docs": docs}  # No explicit should_persist
        
        result = agent._execute_operation(collection, inputs)
        
        # Verify service called with agent's default should_persist
        self.mock_vector_service.write.assert_called_once_with(
            collection=collection,
            data=docs,
            mode=WriteMode.APPEND,
            should_persist=True  # Should use agent's default
        )
    
    def test_execute_operation_no_documents(self):
        """Test _execute_operation with no documents returns error."""
        agent = self.create_vector_writer_agent()
        agent.configure_vector_service(self.mock_vector_service)
        
        collection = "test_collection"
        inputs = {"docs": None}  # No documents
        
        result = agent._execute_operation(collection, inputs)
        
        # Should return error without calling service
        self.mock_vector_service.write.assert_not_called()
        expected_result = {
            "status": "error",
            "error": "No documents provided"
        }
        self.assertEqual(result, expected_result)
    
    def test_execute_operation_service_failure(self):
        """Test _execute_operation handles service failure correctly."""
        agent = self.create_vector_writer_agent()
        agent.configure_vector_service(self.mock_vector_service)
        
        # Configure service to return failure
        fail_result = Mock()
        fail_result.success = False
        fail_result.error = "Vector database connection failed"
        self.mock_vector_service.write.return_value = fail_result
        
        collection = "test_collection"
        docs = [{"text": "Test document"}]
        inputs = {"docs": docs}
        
        result = agent._execute_operation(collection, inputs)
        
        # Should return formatted error result
        expected_result = {
            "status": "error",
            "error": "Vector database connection failed"
        }
        self.assertEqual(result, expected_result)
    
    # =============================================================================
    # 3. Validation Tests
    # =============================================================================
    
    def test_document_validation_success(self):
        """Test that document validation passes with valid documents."""
        agent = self.create_vector_writer_agent()
        
        inputs = {
            "docs": [
                {"text": "Document 1"},
                {"text": "Document 2"}
            ]
        }
        
        # Should not raise any exceptions
        try:
            agent._validate_inputs(inputs)
        except Exception as e:
            self.fail(f"Validation failed unexpectedly: {e}")
    
    def test_document_validation_missing_docs(self):
        """Test that validation fails when documents are missing."""
        agent = self.create_vector_writer_agent()
        
        inputs = {}  # Missing docs field
        
        with self.assertRaises(ValueError) as cm:
            agent._validate_inputs(inputs)
        
        self.assertIn("No documents provided in 'docs' field", str(cm.exception))
    
    def test_document_validation_null_docs(self):
        """Test that validation fails when documents are null."""
        agent = self.create_vector_writer_agent()
        
        inputs = {"docs": None}
        
        with self.assertRaises(ValueError) as cm:
            agent._validate_inputs(inputs)
        
        self.assertIn("No documents provided in 'docs' field", str(cm.exception))
    
    def test_custom_input_field_validation(self):
        """Test validation with custom input field name."""
        agent = self.create_vector_writer_agent(input_fields=["documents"])
        
        # Should validate using custom field name
        inputs = {"documents": [{"text": "Test doc"}]}
        
        try:
            agent._validate_inputs(inputs)
        except Exception as e:
            self.fail(f"Validation failed unexpectedly: {e}")
        
        # Should fail when custom field is missing
        with self.assertRaises(ValueError) as cm:
            agent._validate_inputs({"docs": [{"text": "Test doc"}]})  # Wrong field name
        
        self.assertIn("No documents provided in 'documents' field", str(cm.exception))
    
    # =============================================================================
    # 4. Error Handling Tests
    # =============================================================================
    
    def test_error_handling_works_correctly(self):
        """Test that error handling works correctly and returns DocumentResult."""
        agent = self.create_vector_writer_agent()
        
        test_error = RuntimeError("Vector operation failed")
        collection = "test_collection"
        inputs = {"docs": [{"text": "Test"}]}
        
        # Call the error handler
        result = agent._handle_operation_error(test_error, collection, inputs)
        
        # Verify result format (should be DocumentResult from base class)
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn("Vector operation failed", result.error)
        self.assertEqual(result.file_path, collection)
    
    # =============================================================================
    # 5. Logging Tests
    # =============================================================================
    
    def test_logging_operation_start(self):
        """Test that operation start logging works correctly."""
        agent = self.create_vector_writer_agent()
        
        collection = "test_collection"
        inputs = {
            "docs": [
                {"text": "Doc 1"},
                {"text": "Doc 2"},
                {"text": "Doc 3"}
            ]
        }
        
        # Call log operation start
        agent._log_operation_start(collection, inputs)
        
        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        
        # Should have logged the vector storage operation with document count
        logged_messages = [call[1] for call in debug_calls]
        storage_logged = any("Starting vector storage with 3 document(s)" in msg for msg in logged_messages)
        self.assertTrue(storage_logged, f"Expected vector storage operation logged, got: {logged_messages}")
    
    def test_logging_single_document(self):
        """Test logging with single document."""
        agent = self.create_vector_writer_agent()
        
        collection = "test_collection"
        inputs = {"docs": {"text": "Single document"}}  # Single doc, not list
        
        agent._log_operation_start(collection, inputs)
        
        # Verify single document is logged correctly
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        logged_messages = [call[1] for call in debug_calls]
        storage_logged = any("Starting vector storage with 1 document(s)" in msg for msg in logged_messages)
        self.assertTrue(storage_logged, f"Expected single document logged, got: {logged_messages}")
    
    def test_logging_no_documents(self):
        """Test logging with no documents."""
        agent = self.create_vector_writer_agent()
        
        collection = "test_collection"
        inputs = {"docs": None}
        
        agent._log_operation_start(collection, inputs)
        
        # Verify no documents is logged correctly
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        logged_messages = [call[1] for call in debug_calls]
        storage_logged = any("Starting vector storage with 0 document(s)" in msg for msg in logged_messages)
        self.assertTrue(storage_logged, f"Expected zero documents logged, got: {logged_messages}")
    
    # =============================================================================
    # 6. Integration Tests
    # =============================================================================
    
    def test_service_configuration_via_protocol(self):
        """Test that vector service can be configured via VectorCapableAgent protocol."""
        agent = self.create_vector_writer_agent()
        
        # Verify agent implements the protocol
        self.assertIsInstance(agent, VectorCapableAgent)
        
        # Configure service
        agent.configure_vector_service(self.mock_vector_service)
        
        # Verify configuration worked
        self.assertEqual(agent.vector_service, self.mock_vector_service)
        self.assertEqual(agent._client, self.mock_vector_service)  # Should also set as main client
    
    def test_full_operation_workflow(self):
        """Test complete vector write operation workflow."""
        agent = self.create_vector_writer_agent()
        agent.configure_vector_service(self.mock_vector_service)
        
        # Test inputs
        collection = "documents"
        docs = [
            {"text": "First document", "metadata": {"type": "article"}},
            {"text": "Second document", "metadata": {"type": "blog"}}
        ]
        inputs = {
            "docs": docs,
            "should_persist": True
        }
        
        # Execute full workflow
        agent._validate_inputs(inputs)
        agent._log_operation_start(collection, inputs)
        result = agent._execute_operation(collection, inputs)
        
        # Verify service was called correctly
        self.mock_vector_service.write.assert_called_once_with(
            collection=collection,
            data=docs,
            mode=WriteMode.APPEND,
            should_persist=True
        )
        
        # Verify result formatting
        expected_result = {
            "status": "success",
            "stored_count": 3,
            "ids": ["doc_1", "doc_2", "doc_3"],
            "persist_directory": "/path/to/vector/store"
        }
        self.assertEqual(result, expected_result)
    
    def test_configuration_properties_preserved(self):
        """Test that vector processing configuration is preserved after modernization."""
        custom_config = {
            "input_fields": ["documents"],
            "output_field": "storage_result",
            "should_persist": False,
            "k": 10,
            "metadata_keys": ["source", "category"]
        }
        
        agent = self.create_vector_writer_agent(**custom_config)
        
        # Verify configuration was preserved
        self.assertEqual(agent.input_fields, ["documents"])
        self.assertEqual(agent.output_field, "storage_result")
        self.assertFalse(agent.should_persist)
        self.assertEqual(agent.k, 10)
        self.assertEqual(agent.metadata_keys, ["source", "category"])
    
    def test_result_formatting_with_missing_attributes(self):
        """Test result formatting when service result has missing attributes."""
        agent = self.create_vector_writer_agent()
        agent.configure_vector_service(self.mock_vector_service)
        
        # Create a simple class that simulates missing attributes
        class MinimalResult:
            def __init__(self):
                self.success = True
                # Don't set total_affected, ids, or persist_directory
        
        minimal_result = MinimalResult()
        self.mock_vector_service.write.return_value = minimal_result
        
        collection = "test_collection"
        docs = [{"text": "Test document"}]
        inputs = {"docs": docs}
        
        result = agent._execute_operation(collection, inputs)
        
        # Should handle missing attributes gracefully
        expected_result = {
            "status": "success",
            "stored_count": 0,  # Default when total_affected not present
            "ids": [],         # Default when ids not present
            "persist_directory": None  # Default when persist_directory not present
        }
        self.assertEqual(result, expected_result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
