"""
Unit tests for ApplicationBootstrapService.

These tests mock all dependencies and focus on testing the service logic
in isolation, following the existing test patterns in AgentMap.
"""

import unittest
from unittest.mock import Mock, patch, call, MagicMock
from pathlib import Path
from typing import Protocol

from agentmap.services.application_bootstrap_service import ApplicationBootstrapService
from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.features_registry_service import FeaturesRegistryService
# from agentmap.services.dependency_checker_service import DependencyCheckerService
from agentmap.services.host_service_registry import HostServiceRegistry
from tests.utils.mock_service_factory import MockServiceFactory


# Mock protocols for testing
class MockDatabaseServiceProtocol(Protocol):
    """Mock protocol for testing."""
    def connect(self) -> None:
        ...


class MockEmailServiceProtocol(Protocol):
    """Another mock protocol for testing."""
    def send_email(self, to: str, subject: str, body: str) -> None:
        ...


class TestApplicationBootstrapService(unittest.TestCase):
    """Unit tests for ApplicationBootstrapService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        
        # Create mock services for all dependencies
        self.mock_agent_registry_service = Mock(spec=AgentRegistryService)
        self.mock_features_registry_service = Mock(spec=FeaturesRegistryService)
        # self.mock_dependency_checker_service = Mock(spec=DependencyCheckerService)
        self.mock_host_service_registry = Mock(spec=HostServiceRegistry)
        
        # Create service instance with mocked dependencies
        self.service = ApplicationBootstrapService(
            agent_registry_service=self.mock_agent_registry_service,
            features_registry_service=self.mock_features_registry_service,
            dependency_checker_service=self.mock_dependency_checker_service,
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            host_service_registry=self.mock_host_service_registry
        )
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.agent_registry, self.mock_agent_registry_service)
        self.assertEqual(self.service.features_registry, self.mock_features_registry_service)
        self.assertEqual(self.service.dependency_checker, self.mock_dependency_checker_service)
        self.assertEqual(self.service.app_config, self.mock_app_config_service)
        self.assertIsNotNone(self.service.logger)
        
        # Get the logger that was created for the service
        logger = self.service.logger
        
        # Verify initialization log message
        logger_calls = logger.calls
        self.assertTrue(any("Initialized with all dependencies" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    def test_bootstrap_application_success(self):
        """Test successful complete bootstrap process."""
        # Mock all internal methods
        with patch.object(self.service, 'register_core_agents') as mock_core, \
             patch.object(self.service, 'register_custom_agents') as mock_custom, \
             patch.object(self.service, 'discover_and_register_llm_agents') as mock_llm, \
             patch.object(self.service, 'discover_and_register_storage_agents') as mock_storage, \
             patch.object(self.service, 'register_mixed_dependency_agents') as mock_mixed, \
             patch.object(self.service, 'discover_and_register_host_protocols') as mock_protocols, \
             patch.object(self.service, '_log_startup_summary') as mock_log_summary:
            
            # Execute bootstrap
            self.service.bootstrap_application()
            
            # Verify all methods were called in correct order
            mock_core.assert_called_once()
            mock_custom.assert_called_once()
            mock_llm.assert_called_once()
            mock_storage.assert_called_once()
            mock_mixed.assert_called_once()
            mock_protocols.assert_called_once()
            mock_log_summary.assert_called_once()
            
            # Verify success logging
            logger_calls = self.service.logger.calls
            self.assertTrue(any("Starting application bootstrap" in call[1] 
                              for call in logger_calls if call[0] == "info"))
            self.assertTrue(any("bootstrap completed successfully" in call[1] 
                              for call in logger_calls if call[0] == "info"))
    
    def test_bootstrap_application_with_error(self):
        """Test bootstrap process with error handling and graceful degradation."""
        # Mock methods to raise exception
        with patch.object(self.service, 'register_core_agents', side_effect=Exception("Core agent registration failed")):
            
            # Execute bootstrap - should not raise exception due to graceful degradation
            self.service.bootstrap_application()
            
            # Verify error logging and graceful degradation
            logger_calls = self.service.logger.calls
            self.assertTrue(any("Bootstrap failed" in call[1] 
                              for call in logger_calls if call[0] == "error"))
            self.assertTrue(any("Continuing with partial bootstrap" in call[1] 
                              for call in logger_calls if call[0] == "warning"))
    
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._import_agent_class')
    def test_register_core_agents_success(self, mock_import):
        """Test successful core agent registration."""
        # Mock agent class imports
        mock_agent_classes = []
        for i in range(8):  # 8 core agents (including HumanAgent)
            mock_class = Mock()
            mock_class.__name__ = f"MockAgent{i}"
            mock_agent_classes.append(mock_class)
        
        mock_import.side_effect = mock_agent_classes
        
        # Execute core agent registration
        self.service.register_core_agents()
        
        # Verify agent registry was called for each core agent
        expected_calls = [
            call("default", mock_agent_classes[0]),
            call("echo", mock_agent_classes[1]),
            call("branching", mock_agent_classes[2]),
            call("failure", mock_agent_classes[3]),
            call("success", mock_agent_classes[4]),
            call("input", mock_agent_classes[5]),
            call("graph", mock_agent_classes[6]),
            call("human", mock_agent_classes[7])
        ]
        self.mock_agent_registry_service.register_agent.assert_has_calls(expected_calls)
        
        # Verify success logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Registered 8/8 core agents" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._import_agent_class')
    def test_register_core_agents_with_failures(self, mock_import):
        """Test core agent registration with some failures."""
        # Mock some imports to fail
        def import_side_effect(class_path):
            if "default_agent" in class_path:
                return Mock()
            elif "echo_agent" in class_path:
                return Mock()
            else:
                raise ImportError(f"Cannot import {class_path}")
        
        mock_import.side_effect = import_side_effect
        
        # Execute core agent registration
        self.service.register_core_agents()
        
        # Verify only successful registrations
        self.assertEqual(self.mock_agent_registry_service.register_agent.call_count, 2)
        
        # Verify partial success logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Registered 2/8 core agents" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    def test_discover_and_register_llm_agents_success(self):
        """Test successful LLM agent discovery and registration."""
        # Mock dependency checker to return available providers
        self.mock_dependency_checker_service.discover_and_validate_providers.return_value = {
            "openai": True,
            "anthropic": True,
            "google": False
        }
        
        # Mock LLM provider agent registration
        with patch.object(self.service, '_register_llm_provider_agents', return_value=2) as mock_register_llm, \
             patch.object(self.service, '_register_base_llm_agent') as mock_register_base:
            
            # Execute LLM agent discovery
            self.service.discover_and_register_llm_agents()
            
            # Verify feature was enabled
            self.mock_features_registry_service.enable_feature.assert_called_once_with("llm")
            
            # Verify dependency checker was called
            self.mock_dependency_checker_service.discover_and_validate_providers.assert_called_once_with("llm")
            
            # Verify provider agents were registered for available providers
            mock_register_llm.assert_any_call("openai")
            mock_register_llm.assert_any_call("anthropic")
            self.assertEqual(mock_register_llm.call_count, 2)  # Only available providers
            
            # Verify base LLM agent was registered
            mock_register_base.assert_called_once()
            
            # Verify success logging
            logger_calls = self.service.logger.calls
            self.assertTrue(any("LLM agents registered for providers: ['openai', 'anthropic']" in call[1] 
                              for call in logger_calls if call[0] == "info"))
    
    def test_discover_and_register_llm_agents_no_providers(self):
        """Test LLM agent discovery with no available providers."""
        # Mock dependency checker to return no available providers
        self.mock_dependency_checker_service.discover_and_validate_providers.return_value = {
            "openai": False,
            "anthropic": False,
            "google": False
        }
        
        # Mock missing dependencies
        self.mock_features_registry_service.get_missing_dependencies.return_value = {"llm": ["langchain_openai", "langchain_anthropic"]}
        
        # Execute LLM agent discovery
        self.service.discover_and_register_llm_agents()
        
        # Verify feature was still enabled (policy decision)
        self.mock_features_registry_service.enable_feature.assert_called_once_with("llm")
        
        # Verify warning logging for no providers
        logger_calls = self.service.logger.calls
        self.assertTrue(any("No LLM providers available" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    def test_discover_and_register_storage_agents_success(self):
        """Test successful storage agent discovery and registration."""
        # Mock dependency checker to return available storage types
        self.mock_dependency_checker_service.discover_and_validate_providers.return_value = {
            "csv": True,
            "json": True,
            "vector": False
        }
        
        # Mock storage type agent registration
        with patch.object(self.service, '_register_storage_type_agents', return_value=2) as mock_register_storage:
            
            # Execute storage agent discovery
            self.service.discover_and_register_storage_agents()
            
            # Verify feature was enabled
            self.mock_features_registry_service.enable_feature.assert_called_once_with("storage")
            
            # Verify dependency checker was called
            self.mock_dependency_checker_service.discover_and_validate_providers.assert_called_once_with("storage")
            
            # Verify storage agents were registered for available types
            mock_register_storage.assert_any_call("csv")
            mock_register_storage.assert_any_call("json")
            self.assertEqual(mock_register_storage.call_count, 2)  # Only available types
            
            # Verify success logging
            logger_calls = self.service.logger.calls
            self.assertTrue(any("Storage agents registered for types: ['csv', 'json']" in call[1] 
                              for call in logger_calls if call[0] == "info"))
    
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._register_agent_if_available')
    def test_register_mixed_dependency_agents(self, mock_register_if_available):
        """Test registration of mixed-dependency agents."""
        # Mock registration to succeed for some agents
        mock_register_if_available.side_effect = [True, False]  # summary succeeds, orchestrator fails
        
        # Execute mixed dependency agent registration
        self.service.register_mixed_dependency_agents()
        
        # Verify registration attempts for both agents
        expected_calls = [
            call("summary", "agentmap.agents.builtins.summary_agent.SummaryAgent"),
            call("orchestrator", "agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent")
        ]
        mock_register_if_available.assert_has_calls(expected_calls)
        
        # Verify debug logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Registered 1/2 mixed-dependency agents" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_register_llm_provider_agents_openai(self):
        """Test registration of OpenAI provider agents."""
        # Mock agent registration
        with patch.object(self.service, '_register_agent_if_available', return_value=True) as mock_register:
            
            # Execute OpenAI provider registration
            result = self.service._register_llm_provider_agents("openai")
            
            # Verify all OpenAI agents were registered
            expected_calls = [
                call("openai", "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent"),
                call("gpt", "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent"),
                call("chatgpt", "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent")
            ]
            mock_register.assert_has_calls(expected_calls)
            
            # Verify return count
            self.assertEqual(result, 3)
    
    def test_register_llm_provider_agents_unknown_provider(self):
        """Test registration with unknown LLM provider."""
        # Execute unknown provider registration
        result = self.service._register_llm_provider_agents("unknown")
        
        # Verify no agents registered
        self.assertEqual(result, 0)
        
        # Verify warning logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Unknown LLM provider: unknown" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    def test_register_storage_type_agents_csv(self):
        """Test registration of CSV storage agents."""
        # Mock agent registration
        with patch.object(self.service, '_register_agent_if_available', return_value=True) as mock_register:
            
            # Execute CSV storage registration
            result = self.service._register_storage_type_agents("csv")
            
            # Verify CSV agents were registered
            expected_calls = [
                call("csv_reader", "agentmap.agents.builtins.storage.csv.CSVReaderAgent"),
                call("csv_writer", "agentmap.agents.builtins.storage.csv.CSVWriterAgent")
            ]
            mock_register.assert_has_calls(expected_calls)
            
            # Verify return count
            self.assertEqual(result, 2)
    
    def test_register_storage_type_agents_unknown_type(self):
        """Test registration with unknown storage type."""
        # Execute unknown storage type registration
        result = self.service._register_storage_type_agents("unknown")
        
        # Verify no agents registered
        self.assertEqual(result, 0)
        
        # Verify debug logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("No predefined agents for storage type: unknown" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._import_agent_class')
    def test_register_agent_if_available_success(self, mock_import):
        """Test successful agent registration when available."""
        # Mock successful import
        mock_agent_class = Mock()
        mock_import.return_value = mock_agent_class
        
        # Execute registration
        result = self.service._register_agent_if_available("test_agent", "test.path.TestAgent")
        
        # Verify success
        self.assertTrue(result)
        
        # Verify agent was registered
        self.mock_agent_registry_service.register_agent.assert_called_once_with("test_agent", mock_agent_class)
        
        # Verify success logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Registered agent: test_agent" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._import_agent_class')
    def test_register_agent_if_available_import_error(self, mock_import):
        """Test agent registration with import error."""
        # Mock import failure
        mock_import.side_effect = ImportError("Module not found")
        
        # Execute registration
        result = self.service._register_agent_if_available("test_agent", "test.path.TestAgent")
        
        # Verify failure
        self.assertFalse(result)
        
        # Verify no registration occurred
        self.mock_agent_registry_service.register_agent.assert_not_called()
        
        # Verify warning logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Agent test_agent not available" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._import_agent_class')
    def test_register_agent_if_available_general_error(self, mock_import):
        """Test agent registration with general error."""
        # Mock general error during registration
        mock_import.return_value = Mock()
        self.mock_agent_registry_service.register_agent.side_effect = Exception("Registration failed")
        
        # Execute registration
        result = self.service._register_agent_if_available("test_agent", "test.path.TestAgent")
        
        # Verify failure
        self.assertFalse(result)
        
        # Verify error logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Failed to register agent test_agent" in call[1] 
                          for call in logger_calls if call[0] == "error"))
    
    @patch('builtins.__import__')
    def test_import_agent_class_success(self, mock_import):
        """Test successful agent class import."""
        # Mock module and class
        mock_module = Mock()
        mock_agent_class = Mock()
        mock_module.TestAgent = mock_agent_class
        mock_import.return_value = mock_module
        
        # Execute import
        result = self.service._import_agent_class("test.module.TestAgent")
        
        # Verify result
        self.assertEqual(result, mock_agent_class)
        
        # Verify import was called correctly
        mock_import.assert_called_once_with("test.module", fromlist=["TestAgent"])
    
    @patch('builtins.__import__')
    def test_import_agent_class_import_error(self, mock_import):
        """Test agent class import with ImportError."""
        # Mock import failure
        mock_import.side_effect = ImportError("Module not found")
        
        # Execute import and expect exception
        with self.assertRaises(ImportError) as context:
            self.service._import_agent_class("test.module.TestAgent")
        
        self.assertIn("Cannot import test.module.TestAgent", str(context.exception))
    
    @patch('builtins.__import__')
    def test_import_agent_class_attribute_error(self, mock_import):
        """Test agent class import with AttributeError."""
        # Mock module without the expected class
        mock_module = Mock()
        del mock_module.TestAgent  # Remove the attribute
        mock_import.return_value = mock_module
        
        # Execute import and expect exception
        with self.assertRaises(ImportError) as context:
            self.service._import_agent_class("test.module.TestAgent")
        
        self.assertIn("Cannot import test.module.TestAgent", str(context.exception))
    
    def test_get_bootstrap_summary(self):
        """Test getting comprehensive bootstrap summary."""
        # Mock agent registry responses
        self.mock_agent_registry_service.list_agents.return_value = {
            "default": Mock(), "echo": Mock(), "openai": Mock(), "csv_reader": Mock()
        }
        self.mock_agent_registry_service.get_registered_agent_types.return_value = [
            "default", "echo", "openai", "csv_reader"
        ]
        
        # Mock features registry responses
        self.mock_features_registry_service.is_feature_enabled.side_effect = lambda feature: feature in ["llm", "storage"]
        self.mock_features_registry_service.get_available_providers.side_effect = lambda category: {
            "llm": ["openai"], "storage": ["csv"]
        }.get(category, [])
        self.mock_features_registry_service.get_missing_dependencies.return_value = {}
        
        # Mock app_config responses for host application methods
        self.mock_app_config_service.is_host_application_enabled.return_value = True
        self.mock_app_config_service.get_host_protocol_folders.return_value = []
        
        # Execute get summary
        summary = self.service.get_bootstrap_summary()
        
        # Verify summary structure
        self.assertEqual(summary["service"], "ApplicationBootstrapService")
        self.assertTrue(summary["bootstrap_completed"])
        self.assertEqual(summary["total_agents_registered"], 4)
        self.assertEqual(summary["agent_types"], ["default", "echo", "openai", "csv_reader"])
        
        # Verify features section
        features = summary["features"]
        self.assertTrue(features["llm_enabled"])
        self.assertTrue(features["storage_enabled"])
        self.assertEqual(features["available_llm_providers"], ["openai"])
        self.assertEqual(features["available_storage_providers"], ["csv"])
        
        # Verify agent breakdown
        breakdown = summary["agent_breakdown"]
        self.assertEqual(breakdown["core_agents"], 2)  # default, echo
        self.assertEqual(breakdown["llm_agents"], 1)   # openai
        self.assertEqual(breakdown["storage_agents"], 1)  # csv_reader
        self.assertEqual(breakdown["mixed_agents"], 0)  # none in test data
    
    def test_count_agents_by_prefix(self):
        """Test agent counting by prefix."""
        agent_types = ["default", "echo", "openai", "gpt", "csv_reader", "json_writer", "summary"]
        
        # Test core agent counting
        core_count = self.service._count_agents_by_prefix(agent_types, ["default", "echo", "branching"])
        self.assertEqual(core_count, 2)  # default, echo
        
        # Test LLM agent counting
        llm_count = self.service._count_agents_by_prefix(agent_types, ["openai", "gpt", "claude"])
        self.assertEqual(llm_count, 2)  # openai, gpt
        
        # Test storage agent counting
        storage_count = self.service._count_agents_by_prefix(agent_types, ["csv_", "json_"])
        self.assertEqual(storage_count, 2)  # csv_reader, json_writer
    
    def test_log_startup_summary(self):
        """Test startup summary logging."""
        # Mock get_bootstrap_summary with complete summary structure
        mock_summary = {
            "total_agents_registered": 10,
            "agent_breakdown": {
                "core_agents": 8,
                "custom_agents": 1,  # ← Add the missing custom_agents field
                "llm_agents": 2,
                "storage_agents": 1,
                "mixed_agents": 0
            },
            "features": {
                "available_llm_providers": ["openai"],
                "available_storage_providers": ["csv"],
                "host_application_enabled": True  # ← Add missing host application enabled field
            },
            "host_application": {  # ← Add missing host application section
                "enabled": True,
                "protocol_folders_configured": 2
            },
            "missing_dependencies": {
                "llm": {},
                "storage": {}
            }
        }
        
        with patch.object(self.service, 'get_bootstrap_summary', return_value=mock_summary):
            
            # Execute summary logging
            self.service._log_startup_summary()
            
            # Verify summary logging occurred
            logger_calls = self.service.logger.calls
            
            # Check for key summary information
            self.assertTrue(any("Bootstrap Summary" in call[1] 
                              for call in logger_calls if call[0] == "info"))
            self.assertTrue(any("Total agents registered: 10" in call[1] 
                              for call in logger_calls if call[0] == "info"))
            self.assertTrue(any("Core agents: 8" in call[1] 
                              for call in logger_calls if call[0] == "info"))
            self.assertTrue(any("Custom agents: 1" in call[1] 
                              for call in logger_calls if call[0] == "info"))
            self.assertTrue(any("Available LLM providers: ['openai']" in call[1] 
                              for call in logger_calls if call[0] == "info"))
            # Check for host application logging
            self.assertTrue(any("Host application enabled with 2 protocol folders" in call[1] 
                              for call in logger_calls if call[0] == "info"))


class TestHostProtocolDiscovery(unittest.TestCase):
    """Unit tests for host protocol discovery functionality."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        
        # Create mock services for all dependencies
        self.mock_agent_registry_service = Mock()
        self.mock_features_registry_service = Mock()
        self.mock_dependency_checker_service = Mock()
        self.mock_host_service_registry = Mock(spec=HostServiceRegistry)
        
        # Create service instance with mocked dependencies
        self.service = ApplicationBootstrapService(
            agent_registry_service=self.mock_agent_registry_service,
            features_registry_service=self.mock_features_registry_service,
            dependency_checker_service=self.mock_dependency_checker_service,
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            host_service_registry=self.mock_host_service_registry
        )
    
    def test_discover_and_register_host_protocols_disabled(self):
        """Test protocol discovery when host application support is disabled."""
        # Mock host application disabled
        self.mock_app_config_service.is_host_application_enabled.return_value = False
        
        # Execute protocol discovery
        self.service.discover_and_register_host_protocols()
        
        # Verify no protocol folders were requested
        self.mock_app_config_service.get_host_protocol_folders.assert_not_called()
        
        # Verify debug logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Host application support disabled" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_discover_and_register_host_protocols_no_folders(self):
        """Test protocol discovery with no configured folders."""
        # Mock host application enabled but no folders
        self.mock_app_config_service.is_host_application_enabled.return_value = True
        self.mock_app_config_service.get_host_protocol_folders.return_value = []
        
        # Execute protocol discovery
        self.service.discover_and_register_host_protocols()
        
        # Verify logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("No host protocol folders configured" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._discover_protocol_classes')
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._register_discovered_protocols')
    def test_discover_and_register_host_protocols_success(self, mock_register, mock_discover):
        """Test successful protocol discovery and registration."""
        # Mock configuration
        self.mock_app_config_service.is_host_application_enabled.return_value = True
        protocol_folders = [Path("protocols"), Path("custom_protocols")]
        self.mock_app_config_service.get_host_protocol_folders.return_value = protocol_folders
        
        # Mock discovered protocols
        discovered_protocols = [
            ("database_service", MockDatabaseServiceProtocol),
            ("email_service", MockEmailServiceProtocol)
        ]
        mock_discover.return_value = discovered_protocols
        
        # Mock successful registration
        mock_register.return_value = 2
        
        # Execute protocol discovery
        self.service.discover_and_register_host_protocols()
        
        # Verify discovery was called with correct folders
        mock_discover.assert_called_once_with(protocol_folders)
        
        # Verify registration was called with discovered protocols
        mock_register.assert_called_once_with(discovered_protocols)
        
        # Verify success logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Registered 2/2 host protocols" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._discover_protocol_classes')
    def test_discover_and_register_host_protocols_no_protocols_found(self, mock_discover):
        """Test protocol discovery when no protocols are found."""
        # Mock configuration
        self.mock_app_config_service.is_host_application_enabled.return_value = True
        protocol_folders = [Path("empty_folder")]
        self.mock_app_config_service.get_host_protocol_folders.return_value = protocol_folders
        
        # Mock no protocols discovered
        mock_discover.return_value = []
        
        # Execute protocol discovery
        self.service.discover_and_register_host_protocols()
        
        # Verify logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("No host protocol classes found" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    def test_discover_and_register_host_protocols_with_exception(self):
        """Test protocol discovery with exception handling."""
        # Mock configuration to raise exception
        self.mock_app_config_service.is_host_application_enabled.side_effect = Exception("Config error")
        
        # Execute protocol discovery - should not raise due to graceful degradation
        self.service.discover_and_register_host_protocols()
        
        # Verify error logging and graceful degradation
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Failed to discover host protocols" in call[1] 
                          for call in logger_calls if call[0] == "error"))
        self.assertTrue(any("Continuing without host protocols" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    @patch('importlib.util.spec_from_file_location')
    @patch('importlib.util.module_from_spec')
    def test_discover_protocol_classes_success(self, mock_module_from_spec, mock_spec_from_file):
        """Test successful protocol class discovery."""
        # Create mock folders with Python files
        mock_folder = Mock(spec=Path)
        mock_folder.exists.return_value = True
        mock_folder.is_dir.return_value = True
        
        # Mock Python files
        mock_py_file = Mock(spec=Path)
        mock_py_file.name = "database_protocol.py"
        mock_py_file.stem = "database_protocol"
        
        mock_folder.glob.return_value = [mock_py_file]
        
        # Mock module loading
        mock_spec = Mock()
        mock_spec.loader = Mock()
        mock_spec_from_file.return_value = mock_spec
        
        # Create mock module with protocol class
        mock_module = MagicMock()
        mock_module.__name__ = "database_protocol"
        
        # Create a mock protocol class
        mock_protocol_class = type('DatabaseServiceProtocol', (), {
            '__module__': 'database_protocol',
            '_is_protocol': True
        })
        
        # Set up module members
        mock_module.DatabaseServiceProtocol = mock_protocol_class
        mock_module_from_spec.return_value = mock_module
        
        # Mock inspect.getmembers to return our protocol
        with patch('inspect.getmembers', return_value=[
            ('DatabaseServiceProtocol', mock_protocol_class)
        ]):
            # Execute discovery
            result = self.service._discover_protocol_classes([mock_folder])
        
        # Verify result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "database_service")
        self.assertEqual(result[0][1], mock_protocol_class)
    
    def test_discover_protocol_classes_folder_not_exists(self):
        """Test protocol discovery with non-existent folder."""
        # Create mock folder that doesn't exist
        mock_folder = Mock(spec=Path)
        mock_folder.exists.return_value = False
        
        # Execute discovery
        result = self.service._discover_protocol_classes([mock_folder])
        
        # Verify empty result
        self.assertEqual(result, [])
        
        # Verify debug logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Protocol folder not found" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_is_protocol_class_valid_protocol(self):
        """Test protocol class validation with valid protocol."""
        # Create mock module
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"
        
        # Create a valid protocol class
        mock_class = type('TestProtocol', (), {
            '__module__': 'test_module',
            '__name__': 'TestProtocol',
            '_is_protocol': True
        })
        
        # Test validation
        result = self.service._is_protocol_class(mock_class, mock_module)
        self.assertTrue(result)
    
    def test_generate_protocol_name_from_class_name(self):
        """Test protocol name generation from class names."""
        # Test various class name patterns
        test_cases = [
            ('DatabaseServiceProtocol', 'database_service'),
            ('LLMCapableProtocol', 'llm_capable'),
            ('CustomHostProtocol', 'custom_host'),
            ('SimpleProtocol', 'simple'),
            ('HTTPAPIServiceProtocol', 'httpapi_service'),
            ('IOProtocol', 'io')
        ]
        
        for class_name, expected_name in test_cases:
            result = self.service._generate_protocol_name_from_class_name(class_name)
            self.assertEqual(result, expected_name)
    
    def test_register_discovered_protocols_no_registry(self):
        """Test protocol registration when host service registry is not available."""
        # Remove host service registry
        self.service.host_service_registry = None
        
        # Try to register protocols
        protocols = [("test_protocol", MockDatabaseServiceProtocol)]
        result = self.service._register_discovered_protocols(protocols)
        
        # Should return 0 and log warning
        self.assertEqual(result, 0)
        
        # Verify warning logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("HostServiceRegistry not available" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    def test_register_discovered_protocols_success(self):
        """Test successful protocol registration."""
        # Create test protocols
        protocols = [
            ("database_service", MockDatabaseServiceProtocol),
            ("email_service", MockEmailServiceProtocol)
        ]
        
        # Execute registration
        result = self.service._register_discovered_protocols(protocols)
        
        # Verify host service registry was called correctly
        self.assertEqual(self.mock_host_service_registry.register_service_provider.call_count, 2)
        
        # Verify return value
        self.assertEqual(result, 2)
        
        # Verify success logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Successfully registered 2 discovered host protocols" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    @patch('agentmap.services.application_bootstrap_service.ApplicationBootstrapService._get_discovered_protocols_summary')
    def test_register_discovered_protocols_with_summary(self, mock_get_summary):
        """Test protocol registration with summary logging."""
        # Mock summary data
        mock_get_summary.return_value = [
            {
                "name": "database_service",
                "class": "DatabaseServiceProtocol",
                "module": "protocols.database",
                "status": "pending"
            }
        ]
        
        # Create test protocol
        protocols = [("database_service", MockDatabaseServiceProtocol)]
        
        # Execute registration
        result = self.service._register_discovered_protocols(protocols)
        
        # Verify summary was retrieved
        mock_get_summary.assert_called_once()
        
        # Verify summary logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Discovered protocols awaiting implementation" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    def test_get_discovered_protocols_summary(self):
        """Test getting summary of discovered protocols."""
        # Mock host service registry responses
        self.mock_host_service_registry.list_registered_services.return_value = [
            "protocol:database_service",
            "protocol:email_service",
            "regular_service"  # Should be ignored
        ]
        
        # Mock metadata for protocol services
        def get_metadata_side_effect(service_name):
            if service_name == "protocol:database_service":
                return {
                    "type": "discovered_protocol",
                    "protocol_name": "database_service",
                    "protocol_class": "DatabaseServiceProtocol",
                    "module": "protocols.database",
                    "implementation_status": "pending"
                }
            elif service_name == "protocol:email_service":
                return {
                    "type": "discovered_protocol",
                    "protocol_name": "email_service",
                    "protocol_class": "EmailServiceProtocol",
                    "module": "protocols.email",
                    "implementation_status": "implemented"
                }
            else:
                return {}
        
        self.mock_host_service_registry.get_service_metadata.side_effect = get_metadata_side_effect
        
        # Get summary
        result = self.service._get_discovered_protocols_summary()
        
        # Verify result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "database_service")
        self.assertEqual(result[0]["class"], "DatabaseServiceProtocol")
        self.assertEqual(result[1]["name"], "email_service")
        self.assertEqual(result[1]["status"], "implemented")
    
    def test_register_storage_type_agents_blob(self):
        """Test registration of blob storage agents."""
        # Mock agent registration
        with patch.object(self.service, '_register_agent_if_available', return_value=True) as mock_register:
            
            # Execute blob storage registration
            result = self.service._register_storage_type_agents("blob")
            
            # Verify blob agents were registered
            expected_calls = [
                call("blob_reader", "agentmap.agents.builtins.storage.blob.BlobReaderAgent"),
                call("blob_writer", "agentmap.agents.builtins.storage.blob.BlobWriterAgent")
            ]
            mock_register.assert_has_calls(expected_calls)
            
            # Verify return count
            self.assertEqual(result, 2)
    
    def test_register_storage_type_agents_azure_blob(self):
        """Test registration of Azure blob storage agents."""
        # Mock agent registration
        with patch.object(self.service, '_register_agent_if_available', return_value=True) as mock_register:
            
            # Execute Azure blob storage registration
            result = self.service._register_storage_type_agents("azure_blob")
            
            # Verify blob agents were registered with correct paths
            expected_calls = [
                call("blob_reader", "agentmap.agents.builtins.storage.blob.BlobReaderAgent"),
                call("blob_writer", "agentmap.agents.builtins.storage.blob.BlobWriterAgent")
            ]
            mock_register.assert_has_calls(expected_calls)
            
            # Verify return count
            self.assertEqual(result, 2)
    
    def test_register_storage_type_agents_aws_s3(self):
        """Test registration of AWS S3 blob storage agents."""
        # Mock agent registration
        with patch.object(self.service, '_register_agent_if_available', return_value=True) as mock_register:
            
            # Execute AWS S3 storage registration
            result = self.service._register_storage_type_agents("aws_s3")
            
            # Verify blob agents were registered with correct paths
            expected_calls = [
                call("blob_reader", "agentmap.agents.builtins.storage.blob.BlobReaderAgent"),
                call("blob_writer", "agentmap.agents.builtins.storage.blob.BlobWriterAgent")
            ]
            mock_register.assert_has_calls(expected_calls)
            
            # Verify return count
            self.assertEqual(result, 2)
    
    def test_register_storage_type_agents_gcp_storage(self):
        """Test registration of Google Cloud Storage blob agents."""
        # Mock agent registration
        with patch.object(self.service, '_register_agent_if_available', return_value=True) as mock_register:
            
            # Execute GCP storage registration
            result = self.service._register_storage_type_agents("gcp_storage")
            
            # Verify blob agents were registered with correct paths
            expected_calls = [
                call("blob_reader", "agentmap.agents.builtins.storage.blob.BlobReaderAgent"),
                call("blob_writer", "agentmap.agents.builtins.storage.blob.BlobWriterAgent")
            ]
            mock_register.assert_has_calls(expected_calls)
            
            # Verify return count
            self.assertEqual(result, 2)


if __name__ == '__main__':
    unittest.main()
