# tests/utils/mock_factory.py
"""
Central mock factory for creating consistent service mocks across all tests.

This factory ensures that all tests use the same mock patterns and makes
it easy to maintain consistent behavior across the test suite.
"""
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, Optional, Union
from pathlib import Path
import logging


class MockServiceFactory:
    """
    Factory for creating consistent mock services.
    
    This centralizes all service mocking logic and ensures that tests
    use consistent mock behavior patterns.
    """
    
    @staticmethod
    def create_config_service(
        config_data: Optional[Dict[str, Any]] = None
    ) -> Mock:
        """Create a mock ConfigService with standard behavior."""
        mock = Mock()
        
        # Default config data
        default_config = {
            "logging": {
                "level": "DEBUG",
                "format": "[%(levelname)s] %(name)s: %(message)s"
            },
            "llm": {
                "openai": {
                    "api_key": "test_key",
                    "model": "gpt-3.5-turbo",
                    "temperature": 0.7
                },
                "anthropic": {
                    "api_key": "test_key", 
                    "model": "claude-3-sonnet-20240229",
                    "temperature": 0.7
                }
            },
            "execution": {
                "max_retries": 3,
                "timeout": 30
            }
        }
        
        # Merge with provided config
        if config_data:
            default_config.update(config_data)
        
        mock.load_config.return_value = default_config
        mock.get_config.return_value = default_config
        mock.validate_config.return_value = True
        mock.replace_logger = Mock()
        
        return mock
    
    @staticmethod
    def create_app_config_service(
        config_data: Optional[Dict[str, Any]] = None
    ) -> Mock:
        """Create a mock AppConfigService with standard behavior."""
        mock = Mock()
        
        # Standard methods
        mock.get_logging_config.return_value = {
            "level": "DEBUG",
            "format": "[%(levelname)s] %(name)s: %(message)s"
        }
        
        mock.get_llm_config.return_value = {
            "openai": {
                "api_key": "test_key",
                "model": "gpt-3.5-turbo", 
                "temperature": 0.7
            },
            "anthropic": {
                "api_key": "test_key",
                "model": "claude-3-sonnet-20240229",
                "temperature": 0.7
            }
        }
        
        mock.get_execution_config.return_value = {
            "max_retries": 3,
            "timeout": 30
        }
        
        mock.get_prompts_config.return_value = {
            "templates_dir": "prompts/templates",
            "default_language": "en"
        }
        
        mock.get_storage_config_path.return_value = Path("/tmp/storage_config.yaml")
        mock.replace_logger = Mock()
        
        # Allow overrides
        if config_data:
            for key, value in config_data.items():
                getattr(mock, f"get_{key}_config").return_value = value
        
        return mock
    
    @staticmethod
    def create_logging_service(logger_name: str = "test") -> Mock:
        """Create a mock LoggingService with real logger behavior."""
        mock = Mock()
        
        # Create real loggers for better test debugging
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        
        mock.get_logger.return_value = logger
        mock.get_class_logger.return_value = logger
        mock.initialize.return_value = None
        mock.is_initialized.return_value = True
        mock.reset.return_value = None
        
        return mock
    
    @staticmethod
    def create_llm_service(
        provider_configs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Mock:
        """Create a mock LLMService with standard behavior."""
        mock = Mock()
        
        # Default provider configurations
        default_providers = {
            "openai": {
                "api_key": "test_key",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7
            },
            "anthropic": {
                "api_key": "test_key",
                "model": "claude-3-sonnet-20240229", 
                "temperature": 0.7
            }
        }
        
        if provider_configs:
            default_providers.update(provider_configs)
        
        # Mock methods
        mock.get_provider_config.side_effect = lambda provider: default_providers.get(provider, {})
        mock.is_provider_available.return_value = True
        mock.get_available_providers.return_value = list(default_providers.keys())
        
        # Mock LLM calls with realistic responses
        mock.generate.return_value = "Mock LLM response"
        mock.chat.return_value = "Mock chat response"
        
        return mock
    
    @staticmethod
    def create_llm_routing_service() -> Mock:
        """Create a mock LLMRoutingService with standard behavior."""
        mock = Mock()
        
        mock.route_request.return_value = "openai"  # Default to openai
        mock.get_routing_strategy.return_value = "round_robin"
        mock.is_provider_available.return_value = True
        
        return mock
    
    @staticmethod
    def create_node_registry_service() -> Mock:
        """Create a mock NodeRegistryService with standard behavior."""
        mock = Mock()
        
        mock.register_node.return_value = None
        mock.get_node.return_value = Mock()
        mock.list_nodes.return_value = []
        mock.unregister_node.return_value = None
        mock.clear_registry.return_value = None
        
        return mock
    
    @staticmethod
    def create_execution_tracker() -> Mock:
        """Create a mock ExecutionTracker with standard behavior."""
        mock = Mock()
        
        mock.start_execution.return_value = "mock_execution_id"
        mock.end_execution.return_value = None
        mock.log_step.return_value = None
        mock.get_execution_stats.return_value = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0
        }
        
        return mock
    
    @staticmethod
    def create_storage_service_manager() -> Mock:
        """Create a mock StorageServiceManager with standard behavior."""
        mock = Mock()
        
        # CSV service mock
        csv_service = Mock()
        csv_service.read.return_value = []
        csv_service.write.return_value = None
        csv_service.list_collections.return_value = []
        
        # Vector service mock
        vector_service = Mock()
        vector_service.add.return_value = None
        vector_service.search.return_value = []
        vector_service.list_collections.return_value = []
        
        # KV service mock
        kv_service = Mock()
        kv_service.get.return_value = None
        kv_service.set.return_value = None
        kv_service.delete.return_value = None
        
        mock.get_csv_service.return_value = csv_service
        mock.get_vector_service.return_value = vector_service
        mock.get_kv_service.return_value = kv_service
        mock.is_available.return_value = True
        
        return mock
    
    @classmethod
    def create_mock_container(
        cls,
        config_overrides: Optional[Dict[str, Any]] = None
    ) -> Mock:
        """
        Create a complete mock DI container with all services.
        
        This is useful for tests that need a full container but don't
        want to deal with real service initialization.
        """
        container = Mock()
        
        # Create all mock services
        container.config_service.return_value = cls.create_config_service(config_overrides)
        container.app_config_service.return_value = cls.create_app_config_service(config_overrides)
        container.logging_service.return_value = cls.create_logging_service()
        container.llm_service.return_value = cls.create_llm_service()
        container.llm_routing_service.return_value = cls.create_llm_routing_service()
        container.node_registry_service.return_value = cls.create_node_registry_service()
        container.execution_tracker.return_value = cls.create_execution_tracker()
        container.storage_service_manager.return_value = cls.create_storage_service_manager()
        
        return container


class ServiceMockBuilder:
    """
    Builder pattern for creating customized service mocks.
    
    This allows tests to easily customize specific behaviors
    while keeping the rest of the mock behavior standard.
    """
    
    def __init__(self, service_type: str):
        self.service_type = service_type
        self.customizations = {}
    
    def with_config(self, config: Dict[str, Any]) -> 'ServiceMockBuilder':
        """Add custom configuration to the mock."""
        self.customizations['config'] = config
        return self
    
    def with_method_return(self, method_name: str, return_value: Any) -> 'ServiceMockBuilder':
        """Set a specific return value for a method."""
        if 'method_returns' not in self.customizations:
            self.customizations['method_returns'] = {}
        self.customizations['method_returns'][method_name] = return_value
        return self
    
    def with_side_effect(self, method_name: str, side_effect: Any) -> 'ServiceMockBuilder':
        """Set a side effect for a method."""
        if 'side_effects' not in self.customizations:
            self.customizations['side_effects'] = {}
        self.customizations['side_effects'][method_name] = side_effect
        return self
    
    def build(self) -> Mock:
        """Build the customized mock service."""
        # Create base mock
        factory_method = getattr(MockServiceFactory, f"create_{self.service_type}")
        mock = factory_method(self.customizations.get('config'))
        
        # Apply method customizations
        if 'method_returns' in self.customizations:
            for method, return_value in self.customizations['method_returns'].items():
                getattr(mock, method).return_value = return_value
        
        if 'side_effects' in self.customizations:
            for method, side_effect in self.customizations['side_effects'].items():
                getattr(mock, method).side_effect = side_effect
        
        return mock


# Convenience functions for common patterns
def mock_config_service(**kwargs) -> Mock:
    """Quick function to create a config service mock."""
    return MockServiceFactory.create_config_service(kwargs)

def mock_logging_service(logger_name: str = "test") -> Mock:
    """Quick function to create a logging service mock."""
    return MockServiceFactory.create_logging_service(logger_name)

def mock_llm_service(**provider_configs) -> Mock:
    """Quick function to create an LLM service mock."""
    return MockServiceFactory.create_llm_service(provider_configs)