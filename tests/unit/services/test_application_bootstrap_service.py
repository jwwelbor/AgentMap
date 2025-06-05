"""
Unit tests for ApplicationBootstrapService.

These tests mock all dependencies and focus on testing the service logic
in isolation, following the existing test patterns in AgentMap.
"""

import unittest
from unittest.mock import Mock, patch, call

from agentmap.services.application_bootstrap_service import ApplicationBootstrapService
from agentmap.services.agent_registry_service import AgentRegistryService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.dependency_checker_service import DependencyCheckerService
from agentmap.migration_utils import MockLoggingService


class TestApplicationBootstrapService(unittest.TestCase):
    """Unit tests for ApplicationBootstrapService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use migration-safe mock implementations
        self.mock_logging_service = MockLoggingService()
        
        # Create mock services for all dependencies
        self.mock_agent_registry_service = Mock(spec=AgentRegistryService)
        self.mock_features_registry_service = Mock(spec=FeaturesRegistryService)
        self.mock_dependency_checker_service = Mock(spec=DependencyCheckerService)
        
        # Create service instance with mocked dependencies
        self.service = ApplicationBootstrapService(
            agent_registry_service=self.mock_agent_registry_service,
            features_registry_service=self.mock_features_registry_service,
            dependency_checker_service=self.mock_dependency_checker_service,
            logging_service=self.mock_logging_service
        )
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.agent_registry, self.mock_agent_registry_service)
        self.assertEqual(self.service.features_registry, self.mock_features_registry_service)
        self.assertEqual(self.service.dependency_checker, self.mock_dependency_checker_service)
        self.assertEqual(self.service.logger.name, "ApplicationBootstrapService")
        
        # Verify initialization log message
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[ApplicationBootstrapService] Initialized with all dependencies" 
                          for call in logger_calls if call[0] == "info"))
    
    def test_bootstrap_application_success(self):
        """Test successful complete bootstrap process."""
        # Mock all internal methods
        with patch.object(self.service, 'register_core_agents') as mock_core, \
             patch.object(self.service, 'discover_and_register_llm_agents') as mock_llm, \
             patch.object(self.service, 'discover_and_register_storage_agents') as mock_storage, \
             patch.object(self.service, 'register_mixed_dependency_agents') as mock_mixed, \
             patch.object(self.service, '_log_startup_summary') as mock_log_summary:
            
            # Execute bootstrap
            self.service.bootstrap_application()
            
            # Verify all methods were called in correct order
            mock_core.assert_called_once()
            mock_llm.assert_called_once()
            mock_storage.assert_called_once()
            mock_mixed.assert_called_once()
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
        for i in range(7):  # 7 core agents
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
            call("graph", mock_agent_classes[6])
        ]
        self.mock_agent_registry_service.register_agent.assert_has_calls(expected_calls)
        
        # Verify success logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Registered 7/7 core agents" in call[1] 
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
        self.assertTrue(any("Registered 2/7 core agents" in call[1] 
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
        # Mock get_bootstrap_summary
        mock_summary = {
            "total_agents_registered": 10,
            "agent_breakdown": {
                "core_agents": 7,
                "llm_agents": 2,
                "storage_agents": 1,
                "mixed_agents": 0
            },
            "features": {
                "available_llm_providers": ["openai"],
                "available_storage_providers": ["csv"]
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
            self.assertTrue(any("Core agents: 7" in call[1] 
                              for call in logger_calls if call[0] == "info"))
            self.assertTrue(any("Available LLM providers: ['openai']" in call[1] 
                              for call in logger_calls if call[0] == "info"))


if __name__ == '__main__':
    unittest.main()
