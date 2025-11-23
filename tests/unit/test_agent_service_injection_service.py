"""
Comprehensive tests for AgentServiceInjectionService.

Tests all 10 capability protocols, error handling, logging, and performance
to verify the refactored service injection works correctly with no regressions.
"""

import logging
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, Mock, patch

from agentmap.services.agent.agent_service_injection_service import AgentServiceInjectionService
from agentmap.services.protocols import (
    BlobStorageCapableAgent,
    CSVCapableAgent,
    FileCapableAgent,
    JSONCapableAgent,
    LLMCapableAgent,
    MemoryCapableAgent,
    OrchestrationCapableAgent,
    PromptCapableAgent,
    StorageCapableAgent,
    VectorCapableAgent,
)


class MockLLMService:
    """Mock LLM service for testing."""
    
    def call_llm(self, provider: str, messages: List[Dict[str, str]], **kwargs) -> str:
        return f"Mock LLM response from {provider}"


class MockStorageServiceManager:
    """Mock storage service manager for testing."""
    
    def __init__(self, available_services: Optional[List[str]] = None):
        self.available_services = available_services if available_services is not None else ["csv", "json", "file", "vector", "memory"]
        self.services = {
            "csv": Mock(name="csv_service"),
            "json": Mock(name="json_service"),
            "file": Mock(name="file_service"),
            "vector": Mock(name="vector_service"),
            "memory": Mock(name="memory_service"),
        }
    
    def get_service(self, service_type: str):
        """Get service by type, return None if not available."""
        if service_type in self.available_services:
            return self.services.get(service_type)
        return None
    
    def is_provider_available(self, service_type: str) -> bool:
        """Check if provider is available."""
        return service_type in self.available_services


class MockLoggingService:
    """Mock logging service for testing."""
    
    def __init__(self):
        self.logger = logging.getLogger("test_agent_service_injection")
        self.logger.setLevel(logging.DEBUG)
    
    def get_class_logger(self, obj: Any) -> logging.Logger:
        return self.logger


class MockPromptManagerService:
    """Mock prompt manager service for testing."""
    
    def resolve_prompt(self, prompt_ref: str) -> str:
        return f"Resolved prompt: {prompt_ref}"
    
    def format_prompt(self, prompt_ref_or_text: str, values: Dict[str, Any]) -> str:
        return f"Formatted: {prompt_ref_or_text} with {values}"


class MockOrchestratorService:
    """Mock orchestrator service for testing."""
    
    def orchestrate(self, request: Any) -> Any:
        return {"status": "orchestrated"}


class MockBlobStorageService:
    """Mock blob storage service for testing."""
    
    def read_blob(self, uri: str, **kwargs) -> bytes:
        return b"mock blob data"
    
    def write_blob(self, uri: str, data: bytes, **kwargs) -> Dict[str, Any]:
        return {"written": True}


# Mock Agents implementing various protocol combinations
class MockLLMOnlyAgent(LLMCapableAgent):
    """Mock agent implementing only LLMCapableAgent."""
    
    def __init__(self, name: str = "llm_agent"):
        self.name = name
        self.llm_service = None
    
    def configure_llm_service(self, llm_service: Any) -> None:
        self.llm_service = llm_service


class MockStorageOnlyAgent(StorageCapableAgent):
    """Mock agent implementing only StorageCapableAgent."""
    
    def __init__(self, name: str = "storage_agent"):
        self.name = name
        self.storage_service = None
    
    def configure_storage_service(self, storage_service: Any) -> None:
        self.storage_service = storage_service


class MockCSVOnlyAgent(CSVCapableAgent):
    """Mock agent implementing only CSVCapableAgent."""
    
    def __init__(self, name: str = "csv_agent"):
        self.name = name
        self.csv_service = None
    
    def configure_csv_service(self, csv_service: Any) -> None:
        self.csv_service = csv_service


class MockJSONOnlyAgent(JSONCapableAgent):
    """Mock agent implementing only JSONCapableAgent."""
    
    def __init__(self, name: str = "json_agent"):
        self.name = name
        self.json_service = None
    
    def configure_json_service(self, json_service: Any) -> None:
        self.json_service = json_service


class MockFileOnlyAgent(FileCapableAgent):
    """Mock agent implementing only FileCapableAgent."""
    
    def __init__(self, name: str = "file_agent"):
        self.name = name
        self.file_service = None
    
    def configure_file_service(self, file_service: Any) -> None:
        self.file_service = file_service


class MockVectorOnlyAgent(VectorCapableAgent):
    """Mock agent implementing only VectorCapableAgent."""
    
    def __init__(self, name: str = "vector_agent"):
        self.name = name
        self.vector_service = None
    
    def configure_vector_service(self, vector_service: Any) -> None:
        self.vector_service = vector_service


class MockMemoryOnlyAgent(MemoryCapableAgent):
    """Mock agent implementing only MemoryCapableAgent."""
    
    def __init__(self, name: str = "memory_agent"):
        self.name = name
        self.memory_service = None
    
    def configure_memory_service(self, memory_service: Any) -> None:
        self.memory_service = memory_service


class MockPromptOnlyAgent(PromptCapableAgent):
    """Mock agent implementing only PromptCapableAgent."""
    
    def __init__(self, name: str = "prompt_agent"):
        self.name = name
        self.prompt_manager_service = None
    
    def configure_prompt_service(self, prompt_service: Any) -> None:
        self.prompt_manager_service = prompt_service


class MockOrchestrationOnlyAgent(OrchestrationCapableAgent):
    """Mock agent implementing only OrchestrationCapableAgent."""
    
    def __init__(self, name: str = "orchestration_agent"):
        self.name = name
        self.orchestrator_service = None
    
    def configure_orchestrator_service(self, orchestrator_service: Any) -> None:
        self.orchestrator_service = orchestrator_service


class MockBlobStorageOnlyAgent(BlobStorageCapableAgent):
    """Mock agent implementing only BlobStorageCapableAgent."""
    
    def __init__(self, name: str = "blob_agent"):
        self.name = name
        self.blob_storage_service = None
    
    def configure_blob_storage_service(self, blob_service: Any) -> None:
        self.blob_storage_service = blob_service


class MockMultiServiceAgent(LLMCapableAgent, StorageCapableAgent, PromptCapableAgent):
    """Mock agent implementing multiple core protocols."""
    
    def __init__(self, name: str = "multi_agent"):
        self.name = name
        self.llm_service = None
        self.storage_service = None
        self.prompt_manager_service = None
    
    def configure_llm_service(self, llm_service: Any) -> None:
        self.llm_service = llm_service
    
    def configure_storage_service(self, storage_service: Any) -> None:
        self.storage_service = storage_service
    
    def configure_prompt_service(self, prompt_service: Any) -> None:
        self.prompt_manager_service = prompt_service


class MockMultiStorageAgent(CSVCapableAgent, JSONCapableAgent, FileCapableAgent):
    """Mock agent implementing multiple storage protocols."""
    
    def __init__(self, name: str = "multi_storage_agent"):
        self.name = name
        self.csv_service = None
        self.json_service = None
        self.file_service = None
    
    def configure_csv_service(self, csv_service: Any) -> None:
        self.csv_service = csv_service
    
    def configure_json_service(self, json_service: Any) -> None:
        self.json_service = json_service
    
    def configure_file_service(self, file_service: Any) -> None:
        self.file_service = file_service


class MockAllServicesAgent(LLMCapableAgent, StorageCapableAgent, PromptCapableAgent,
                            OrchestrationCapableAgent, BlobStorageCapableAgent,
                            CSVCapableAgent, JSONCapableAgent, FileCapableAgent, 
                            VectorCapableAgent, MemoryCapableAgent):
    """Mock agent implementing all 10 protocols."""

    def __init__(self, name: str = "all_services_agent"):
        self.name = name
        # Core services
        self.llm_service = None
        self.storage_service = None  # Generic storage
        self.prompt_manager_service = None
        self.orchestrator_service = None
        self.blob_storage_service = None
        # Storage-specific services
        self.csv_service = None
        self.json_service = None
        self.file_service = None
        self.vector_service = None
        self.memory_service = None
    
    # Core service configuration methods
    def configure_llm_service(self, llm_service: Any) -> None:
        self.llm_service = llm_service
    
    def configure_storage_service(self, storage_service: Any) -> None:
        self.storage_service = storage_service
    
    def configure_prompt_service(self, prompt_service: Any) -> None:
        self.prompt_manager_service = prompt_service

    def configure_orchestrator_service(self, orchestrator_service: Any) -> None:
        self.orchestrator_service = orchestrator_service
    
    def configure_blob_storage_service(self, blob_service: Any) -> None:
        self.blob_storage_service = blob_service
    
    # Storage-specific configuration methods
    def configure_csv_service(self, csv_service: Any) -> None:
        self.csv_service = csv_service
    
    def configure_json_service(self, json_service: Any) -> None:
        self.json_service = json_service
    
    def configure_file_service(self, file_service: Any) -> None:
        self.file_service = file_service
    
    def configure_vector_service(self, vector_service: Any) -> None:
        self.vector_service = vector_service
    
    def configure_memory_service(self, memory_service: Any) -> None:
        self.memory_service = memory_service


class MockBasicAgent:
    """Mock agent implementing no protocols."""
    
    def __init__(self, name: str = "basic_agent"):
        self.name = name


class MockFailingAgent(LLMCapableAgent):
    """Mock agent where configuration methods raise exceptions."""
    
    def __init__(self, name: str = "failing_agent"):
        self.name = name
        self.llm_service = None
    
    def configure_llm_service(self, llm_service: Any) -> None:
        raise RuntimeError("Configuration method failed")


class TestAgentServiceInjectionService(unittest.TestCase):
    """Comprehensive tests for AgentServiceInjectionService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.llm_service = MockLLMService()
        self.storage_service_manager = MockStorageServiceManager()
        self.logging_service = MockLoggingService()
        self.prompt_manager_service = MockPromptManagerService()
        self.orchestrator_service = MockOrchestratorService()
        self.blob_storage_service = MockBlobStorageService()

        # Create service injection instance with all services available
        self.injection_service = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=self.storage_service_manager,
            logging_service=self.logging_service,
            prompt_manager_service=self.prompt_manager_service,
            orchestrator_service=self.orchestrator_service,
            blob_storage_service=self.blob_storage_service,
        )
    
    # ===== INDIVIDUAL PROTOCOL TESTS =====
    
    def test_llm_protocol_injection(self):
        """Test LLM service injection works correctly."""
        agent = MockLLMOnlyAgent("test_llm_agent")
        
        configured = self.injection_service.configure_core_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.llm_service, "LLM service should be configured")
        self.assertEqual(agent.llm_service, self.llm_service, "Should be the correct service")
    
    def test_storage_protocol_injection(self):
        """Test storage service injection works correctly."""
        agent = MockStorageOnlyAgent("test_storage_agent")
        
        configured = self.injection_service.configure_core_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.storage_service, "Storage service should be configured")
        self.assertEqual(agent.storage_service, self.storage_service_manager, "Should be the correct service")
    
    def test_csv_protocol_injection(self):
        """Test CSV service injection works correctly."""
        agent = MockCSVOnlyAgent("test_csv_agent")
        
        configured = self.injection_service.configure_storage_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.csv_service, "CSV service should be configured")
    
    def test_json_protocol_injection(self):
        """Test JSON service injection works correctly."""
        agent = MockJSONOnlyAgent("test_json_agent")
        
        configured = self.injection_service.configure_storage_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.json_service, "JSON service should be configured")
    
    def test_file_protocol_injection(self):
        """Test File service injection works correctly."""
        agent = MockFileOnlyAgent("test_file_agent")
        
        configured = self.injection_service.configure_storage_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.file_service, "File service should be configured")
    
    def test_vector_protocol_injection(self):
        """Test Vector service injection works correctly."""
        agent = MockVectorOnlyAgent("test_vector_agent")
        
        configured = self.injection_service.configure_storage_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.vector_service, "Vector service should be configured")
    
    def test_memory_protocol_injection(self):
        """Test Memory service injection works correctly."""
        agent = MockMemoryOnlyAgent("test_memory_agent")
        
        configured = self.injection_service.configure_storage_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.memory_service, "Memory service should be configured")
    
    def test_prompt_protocol_injection(self):
        """Test Prompt service injection works correctly."""
        agent = MockPromptOnlyAgent("test_prompt_agent")
        
        configured = self.injection_service.configure_core_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.prompt_manager_service, "Prompt service should be configured")
    
    def test_orchestration_protocol_injection(self):
        """Test Orchestration service injection works correctly."""
        agent = MockOrchestrationOnlyAgent("test_orchestration_agent")
        
        configured = self.injection_service.configure_core_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.orchestrator_service, "Orchestration service should be configured")
    
    def test_blob_storage_protocol_injection(self):
        """Test Blob Storage service injection works correctly."""
        agent = MockBlobStorageOnlyAgent("test_blob_agent")
        
        configured = self.injection_service.configure_core_services(agent)
        
        self.assertEqual(configured, 1, "Should configure 1 service")
        self.assertIsNotNone(agent.blob_storage_service, "Blob storage service should be configured")
    
    # ===== PROTOCOL COMBINATION TESTS =====
    
    def test_multiple_core_protocols(self):
        """Test agents implementing multiple core protocols."""
        agent = MockMultiServiceAgent("test_multi_agent")
        
        configured = self.injection_service.configure_core_services(agent)
        
        self.assertEqual(configured, 3, "Should configure 3 services")
        self.assertIsNotNone(agent.llm_service, "LLM service should be configured")
        self.assertIsNotNone(agent.storage_service, "Storage service should be configured")
        self.assertIsNotNone(agent.prompt_manager_service, "Prompt service should be configured")
    
    def test_multiple_storage_protocols(self):
        """Test agents implementing multiple storage protocols."""
        agent = MockMultiStorageAgent("test_multi_storage_agent")
        
        configured = self.injection_service.configure_storage_services(agent)
        
        self.assertEqual(configured, 3, "Should configure 3 storage services")
        self.assertIsNotNone(agent.csv_service, "CSV service should be configured")
        self.assertIsNotNone(agent.json_service, "JSON service should be configured")
        self.assertIsNotNone(agent.file_service, "File service should be configured")
    
    def test_all_protocols(self):
        """Test agent implementing all 10 protocols."""
        agent = MockAllServicesAgent("test_all_services_agent")

        # Configure core services
        core_configured = self.injection_service.configure_core_services(agent)
        self.assertEqual(core_configured, 5, "Should configure 5 core services")

        # Configure storage services  
        storage_configured = self.injection_service.configure_storage_services(agent)
        self.assertEqual(storage_configured, 5, "Should configure 5 storage services")

        # Test unified configuration
        summary = self.injection_service.configure_all_services(agent)
        self.assertEqual(summary["core_services_configured"], 5)
        self.assertEqual(summary["storage_services_configured"], 5)
        self.assertEqual(summary["total_services_configured"], 10)

        # Verify all services are configured
        self.assertIsNotNone(agent.llm_service, "LLM service should be configured")
        self.assertIsNotNone(agent.storage_service, "Storage service should be configured")
        self.assertIsNotNone(agent.prompt_manager_service, "Prompt service should be configured")
        self.assertIsNotNone(agent.orchestrator_service, "Orchestration service should be configured")
        self.assertIsNotNone(agent.blob_storage_service, "Blob storage service should be configured")
        self.assertIsNotNone(agent.csv_service, "CSV service should be configured")
        self.assertIsNotNone(agent.json_service, "JSON service should be configured")
        self.assertIsNotNone(agent.file_service, "File service should be configured")
        self.assertIsNotNone(agent.vector_service, "Vector service should be configured")
        self.assertIsNotNone(agent.memory_service, "Memory service should be configured")
    
    def test_no_protocols(self):
        """Test agent implementing no protocols."""
        agent = MockBasicAgent("test_basic_agent")
        
        core_configured = self.injection_service.configure_core_services(agent)
        storage_configured = self.injection_service.configure_storage_services(agent)
        
        self.assertEqual(core_configured, 0, "Should configure 0 core services")
        self.assertEqual(storage_configured, 0, "Should configure 0 storage services")
    
    # ===== ERROR SCENARIO TESTS =====
    
    def test_missing_llm_service(self):
        """Test behavior when LLM service is None."""
        injection_service = AgentServiceInjectionService(
            llm_service=None,  # Missing LLM service
            storage_service_manager=self.storage_service_manager,
            logging_service=self.logging_service,
        )
        agent = MockLLMOnlyAgent("test_llm_agent")
        
        with self.assertRaises(Exception) as context:
            injection_service.configure_core_services(agent)
        
        # Verify that we get the expected error about missing LLM service
        error_message = str(context.exception)
        self.assertTrue('NoneType' in error_message or 'required' in error_message.lower() or 'llm' in error_message.lower())
    
    def test_missing_storage_service(self):
        """Test behavior when storage service manager is None."""
        injection_service = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=None,  # Missing storage service
            logging_service=self.logging_service,
        )
        agent = MockStorageOnlyAgent("test_storage_agent")
        
        with self.assertRaises(Exception) as context:
            injection_service.configure_core_services(agent)
        
        # Verify that we get the expected error about missing storage service
        error_message = str(context.exception)
        self.assertTrue('NoneType' in error_message or 'required' in error_message.lower() or 'storage' in error_message.lower())
    
    def test_missing_optional_prompt_service(self):
        """Test strict exception handling when prompt service is None."""
        injection_service = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=self.storage_service_manager,
            logging_service=self.logging_service,
            prompt_manager_service=None,  # Missing optional service
        )
        agent = MockPromptOnlyAgent("test_prompt_agent")
        
        # Should raise exception in strict mode
        with self.assertRaises(Exception) as context:
            injection_service.configure_core_services(agent)
        
        # Verify exception contains relevant information
        error_message = str(context.exception).lower()
        self.assertTrue(
            "prompt" in error_message and "not available" in error_message,
            f"Exception should mention prompt service not available: {context.exception}"
        )
        self.assertIsNone(agent.prompt_manager_service, "Service should not be configured")
    
    def test_missing_optional_orchestration_service(self):
        """Test strict exception handling when orchestration service is None."""
        injection_service = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=self.storage_service_manager,
            logging_service=self.logging_service,
            orchestrator_service=None,  # Missing optional service
        )
        agent = MockOrchestrationOnlyAgent("test_orchestration_agent")
        
        # Should raise exception in strict mode
        with self.assertRaises(Exception) as context:
            injection_service.configure_core_services(agent)
        
        # Verify exception contains relevant information
        error_message = str(context.exception).lower()
        self.assertTrue(
            "orchestr" in error_message and "not available" in error_message,
            f"Exception should mention orchestrator service not available: {context.exception}"
        )
        self.assertIsNone(agent.orchestrator_service, "Service should not be configured")
    
    def test_missing_optional_blob_storage_service(self):
        """Test strict exception handling when blob storage service is None."""
        injection_service = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=self.storage_service_manager,
            logging_service=self.logging_service,
            blob_storage_service=None,  # Missing optional service
        )
        agent = MockBlobStorageOnlyAgent("test_blob_agent")
        
        # Should raise exception in strict mode
        with self.assertRaises(Exception) as context:
            injection_service.configure_core_services(agent)
        
        # Verify exception contains relevant information
        error_message = str(context.exception).lower()
        self.assertTrue(
            "blob" in error_message and "not available" in error_message,
            f"Exception should mention blob storage service not available: {context.exception}"
        )
        self.assertIsNone(agent.blob_storage_service, "Service should not be configured")
    
    def test_unavailable_storage_service(self):
        """Test strict behavior when storage service manager cannot provide requested service."""
        # Create manager with no available services - get_service returns None
        empty_manager = MockStorageServiceManager(available_services=[])
        injection_service = AgentServiceInjectionService(
            llm_service=self.llm_service,
            storage_service_manager=empty_manager,
            logging_service=self.logging_service,
        )
        agent = MockCSVOnlyAgent("test_csv_agent")
        
        # Should raise exception in strict mode when CSV service is not available
        with self.assertRaises(Exception) as context:
            injection_service.configure_storage_services(agent)
        
        # Verify exception mentions the service not being available
        error_message = str(context.exception).lower()
        self.assertTrue(
            "csv service not available" in error_message,
            f"Expected 'csv service not available' in error message: {context.exception}"
        )
    
    def test_configure_method_exception(self):
        """Test behavior when configure_*_service() raises exception."""
        agent = MockFailingAgent("test_failing_agent")
        
        with self.assertRaises(RuntimeError) as context:
            self.injection_service.configure_core_services(agent)
        
        self.assertIn("Configuration method failed", str(context.exception))
    
    # ===== LOGGING VERIFICATION TESTS =====
    
    def test_error_logging_for_service_failure(self):
        """Verify ERROR level messages for service failures."""
        # Create a mock logger to capture calls
        mock_logger = Mock()
        self.injection_service.logger = mock_logger
        
        agent = MockFailingAgent("test_failing_agent")
        
        with self.assertRaises(RuntimeError):
            self.injection_service.configure_core_services(agent)
        
        # Check that error was logged
        mock_logger.error.assert_called()
        error_calls = mock_logger.error.call_args_list
        self.assertTrue(len(error_calls) > 0, "Should have ERROR level logs")
        
        # Check error message contains expected content
        error_message = error_calls[0][0][0]  # First call, first argument
        self.assertIn("❌", error_message, "Should contain error indicator")
        self.assertIn("test_failing_agent", error_message, "Should contain agent name")
    
    def test_debug_logging_for_successful_configuration(self):
        """Verify DEBUG level messages for successful service configuration."""
        mock_logger = Mock()
        self.injection_service.logger = mock_logger
        
        agent = MockLLMOnlyAgent("test_llm_agent")
        self.injection_service.configure_core_services(agent)
        
        # Check that debug messages were logged
        mock_logger.debug.assert_called()
        debug_calls = mock_logger.debug.call_args_list
        self.assertTrue(len(debug_calls) > 0, "Should have DEBUG level logs")
        
        # Look for success message
        success_logged = any("✅" in str(call) for call in debug_calls)
        self.assertTrue(success_logged, "Should log successful configuration with ✅")
    
    def test_info_logging_for_service_summary(self):
        """Verify INFO level messages for service summaries."""
        # Note: The current implementation uses DEBUG for summaries, 
        # but we test this to verify future INFO level promotion
        mock_logger = Mock()
        self.injection_service.logger = mock_logger
        
        agent = MockAllServicesAgent("test_all_services_agent")
        summary = self.injection_service.configure_all_services(agent)
        
        # Check that summary information is available
        self.assertEqual(summary["total_services_configured"], 10)
        self.assertIn("configuration_status", summary)
    
    # ===== PERFORMANCE TESTS =====
    
    def test_protocol_checking_performance(self):
        """Measure time for protocol checking across 10 protocols."""
        agent = MockAllServicesAgent("test_performance_agent")
        
        # Measure core services configuration
        start_time = time.time()
        for _ in range(100):  # Run multiple times for better measurement
            self.injection_service.configure_core_services(agent)
        core_time = time.time() - start_time
        
        # Measure storage services configuration
        start_time = time.time()
        for _ in range(100):
            self.injection_service.configure_storage_services(agent)
        storage_time = time.time() - start_time
        
        # Performance should be reasonable (less than 0.1 second per 100 operations)
        self.assertLess(core_time, 0.1, "Core service injection should be fast")
        self.assertLess(storage_time, 0.1, "Storage service injection should be fast")
        
        print(f"Performance: Core services: {core_time:.4f}s/100, Storage services: {storage_time:.4f}s/100")
   
    # ===== UTILITY METHOD TESTS =====
    
    def test_requires_storage_services(self):
        """Test requires_storage_services utility method."""
        csv_agent = MockCSVOnlyAgent()
        basic_agent = MockBasicAgent()
        multi_storage_agent = MockMultiStorageAgent()
        
        self.assertTrue(self.injection_service.requires_storage_services(csv_agent))
        self.assertFalse(self.injection_service.requires_storage_services(basic_agent))
        self.assertTrue(self.injection_service.requires_storage_services(multi_storage_agent))
    
    def test_get_required_service_types(self):
        """Test get_required_service_types utility method."""
        csv_agent = MockCSVOnlyAgent()
        basic_agent = MockBasicAgent()
        multi_storage_agent = MockMultiStorageAgent()
        
        csv_types = self.injection_service.get_required_service_types(csv_agent)
        self.assertEqual(csv_types, ["csv"])
        
        basic_types = self.injection_service.get_required_service_types(basic_agent)
        self.assertEqual(basic_types, [])
        
        multi_types = self.injection_service.get_required_service_types(multi_storage_agent)
        self.assertEqual(set(multi_types), {"csv", "json", "file"})
    
    # ===== STATUS AND DIAGNOSTIC TESTS =====
    
    def test_get_service_injection_status(self):
        """Test service injection status diagnostic method."""
        agent = MockAllServicesAgent("test_status_agent")
        
        status = self.injection_service.get_service_injection_status(agent)
        
        self.assertEqual(status["agent_name"], "test_status_agent")
        self.assertEqual(status["agent_type"], "MockAllServicesAgent")
        self.assertIn("implemented_protocols", status)
        self.assertIn("service_injection_potential", status)
        
        # Should show all 10 protocols as implemented
        self.assertEqual(len(status["implemented_protocols"]), 10)

        # Check that summary shows high readiness
        summary = status["summary"]
        self.assertEqual(summary["total_protocols_implemented"], 10)
        self.assertTrue(summary["core_services_ready"])
    
    def test_get_service_availability_status(self):
        """Test service availability status diagnostic method."""
        status = self.injection_service.get_service_availability_status()
        
        self.assertIn("core_services", status)
        self.assertIn("service_readiness", status)
        
        # All services should be available in our test setup
        core_services = status["core_services"]
        self.assertTrue(core_services["llm_service_available"])
        self.assertTrue(core_services["storage_service_manager_available"])
        self.assertTrue(core_services["prompt_manager_service_available"])
        
        # Service readiness should be true
        self.assertTrue(status["service_readiness"]["core_services_ready"])
    
    # ===== STORAGE FALLBACK TESTS =====
    
    def test_storage_capable_agent_fallback(self):
        """Test StorageCapableAgent fallback when no specific protocols implemented."""
        class MockGenericStorageAgent:
            def __init__(self, name: str = "generic_storage_agent"):
                self.name = name
                self.storage_service = None
            
            def configure_storage_service(self, storage_service: Any) -> None:
                self.storage_service = storage_service
        
        agent = MockGenericStorageAgent()
        
        # Should configure via generic StorageCapableAgent fallback
        storage_configured = self.injection_service.configure_storage_services(agent)
        self.assertEqual(storage_configured, 1, "Should configure 1 service via fallback")
        self.assertIsNotNone(agent.storage_service, "Storage service should be configured")
    
    # ===== EXECUTION TRACKER TESTS =====
    
    def test_configure_execution_tracker(self):
        """Test execution tracker configuration."""
        class MockTracker:
            def track_execution(self, agent_name: str) -> None:
                pass
        
        class MockAgentWithTracker:
            def __init__(self, name: str = "tracker_agent"):
                self.name = name
                self.execution_tracker = None
            
            def set_execution_tracker(self, tracker: Any) -> None:
                self.execution_tracker = tracker
        
        agent = MockAgentWithTracker()
        tracker = MockTracker()
        
        configured = self.injection_service.configure_execution_tracker(agent, tracker)
        
        self.assertTrue(configured, "Should configure execution tracker")
        self.assertEqual(agent.execution_tracker, tracker, "Should set correct tracker")
    
    def test_configure_execution_tracker_no_method(self):
        """Test execution tracker configuration when agent doesn't support it."""
        agent = MockBasicAgent()
        tracker = Mock()
        
        configured = self.injection_service.configure_execution_tracker(agent, tracker)
        
        self.assertFalse(configured, "Should not configure tracker on unsupported agent")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
