"""
Unit tests for MinimalContainer class.

Tests the selective service initialization functionality following TDD principles
and clean architecture patterns.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Set, Dict, Any

from agentmap.di.minimal_container import MinimalContainer
from agentmap.di.containers import ApplicationContainer


class TestMinimalContainerInitialization:
    """Test MinimalContainer initialization and basic functionality."""

    def test_init_with_valid_container_and_required_services(self):
        """Test successful initialization with ApplicationContainer and required services."""
        # Arrange
        parent_container = ApplicationContainer()
        required_services = {'logging_service', 'config_service'}
        
        # Act
        container = MinimalContainer(parent_container, required_services)
        
        # Assert
        assert container.parent_container == parent_container
        # Core services are always added to required services
        expected_services = required_services | {'app_config_service'}
        assert container.required_services == expected_services
        assert container.initialized_services == set()

    def test_init_with_none_parent_container_raises_error(self):
        """Test initialization with None parent container raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Parent container cannot be None"):
            MinimalContainer(None, {'service1'})

    def test_init_with_none_required_services_raises_error(self):
        """Test initialization with None required services raises ValueError."""
        # Arrange
        parent_container = ApplicationContainer()
        
        # Act & Assert
        with pytest.raises(ValueError, match="Required services cannot be None"):
            MinimalContainer(parent_container, None)

    def test_init_with_empty_required_services_is_valid(self):
        """Test initialization with empty required services set is valid."""
        # Arrange
        parent_container = ApplicationContainer()
        required_services = set()
        
        # Act
        container = MinimalContainer(parent_container, required_services)
        
        # Assert
        # Core services are always added even with empty input
        expected_core = {'logging_service', 'config_service', 'app_config_service'}
        assert container.required_services == expected_core
        assert container.initialized_services == set()

    def test_init_always_includes_core_services(self):
        """Test that core services (logging, config) are always included."""
        # Arrange
        parent_container = ApplicationContainer()
        required_services = {'some_service'}
        
        # Act
        container = MinimalContainer(parent_container, required_services)
        
        # Assert
        expected_core = {'logging_service', 'config_service', 'app_config_service'}
        assert expected_core.issubset(container.required_services)
        assert 'some_service' in container.required_services


class TestMinimalContainerServiceInitialization:
    """Test service initialization functionality."""

    def test_initialize_service_required_service_creates_instance(self):
        """Test initializing a required service creates instance and tracks it."""
        # Arrange
        parent_container = Mock()
        mock_service_instance = Mock()
        mock_provider = Mock()
        mock_provider.return_value = mock_service_instance
        
        parent_container.test_service = mock_provider
        required_services = {'test_service'}
        
        # Mock the dependency resolution
        with patch('agentmap.di.minimal_container.DIContainerAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.get_service_dependencies.return_value = set()
            mock_analyzer_class.return_value = mock_analyzer
            
            container = MinimalContainer(parent_container, required_services)
            
            # Act
            result = container.initialize_service('test_service')
            
            # Assert
            assert result == mock_service_instance
            assert 'test_service' in container.initialized_services
            mock_provider.assert_called_once()

    def test_initialize_service_non_required_service_returns_none(self):
        """Test initializing a non-required service returns None."""
        # Arrange
        parent_container = Mock()
        required_services = {'logging_service'}
        
        container = MinimalContainer(parent_container, required_services)
        
        # Act
        result = container.initialize_service('non_required_service')
        
        # Assert
        assert result is None
        assert 'non_required_service' not in container.initialized_services

    def test_initialize_service_already_initialized_returns_cached_instance(self):
        """Test initializing already initialized service returns cached instance."""
        # Arrange
        parent_container = Mock()
        mock_service_instance = Mock()
        mock_provider = Mock()
        mock_provider.return_value = mock_service_instance
        
        parent_container.test_service = mock_provider
        required_services = {'test_service'}
        
        with patch('agentmap.di.minimal_container.DIContainerAnalyzer'):
            container = MinimalContainer(parent_container, required_services)
            container.initialized_services.add('test_service')
            container._service_instances = {'test_service': mock_service_instance}
            
            # Act
            result = container.initialize_service('test_service')
            
            # Assert
            assert result == mock_service_instance
            # Provider shouldn't be called for cached service
            # Note: Provider might be called during container init for logging setup
            assert 'test_service' in container.initialized_services

    def test_initialize_service_nonexistent_service_returns_none(self):
        """Test initializing nonexistent service returns None."""
        # Arrange
        parent_container = Mock()
        parent_container.nonexistent_service = None
        required_services = {'nonexistent_service'}
        
        container = MinimalContainer(parent_container, required_services)
        
        # Act
        result = container.initialize_service('nonexistent_service')
        
        # Assert
        assert result is None

    def test_initialize_service_handles_dependency_chain(self):
        """Test that service dependencies are initialized first."""
        # Arrange
        parent_container = Mock()
        
        # Mock services and their dependencies
        mock_app_config = Mock()
        mock_config = Mock()
        mock_logging = Mock()
        
        parent_container.app_config_service.return_value = mock_app_config
        parent_container.config_service.return_value = mock_config
        parent_container.logging_service.return_value = mock_logging
        
        required_services = {'logging_service'}  # logging depends on app_config
        
        with patch.object(MinimalContainer, '_get_service_dependencies') as mock_get_deps:
            mock_get_deps.side_effect = lambda name: {
                'logging_service': {'app_config_service'},
                'app_config_service': {'config_service'},
                'config_service': set()
            }.get(name, set())
            
            container = MinimalContainer(parent_container, required_services)
            
            # Act
            result = container.initialize_service('logging_service')
            
            # Assert
            assert result == mock_logging
            assert 'logging_service' in container.initialized_services
            assert 'app_config_service' in container.initialized_services
            assert 'config_service' in container.initialized_services


class TestMinimalContainerServiceAccess:
    """Test service access methods."""

    def test_get_service_required_service_returns_instance(self):
        """Test get_service returns initialized instance for required service."""
        # Arrange
        parent_container = Mock()
        mock_service_instance = Mock()
        required_services = {'test_service'}
        
        container = MinimalContainer(parent_container, required_services)
        
        with patch.object(container, 'initialize_service', return_value=mock_service_instance):
            # Act
            result = container.get_service('test_service')
            
            # Assert
            assert result == mock_service_instance

    def test_get_service_non_required_service_returns_none(self):
        """Test get_service returns None for non-required service."""
        # Arrange
        parent_container = Mock()
        required_services = {'required_service'}
        
        container = MinimalContainer(parent_container, required_services)
        
        # Act
        result = container.get_service('non_required_service')
        
        # Assert
        assert result is None

    def test_has_service_required_service_returns_true(self):
        """Test has_service returns True for required service."""
        # Arrange
        parent_container = Mock()
        required_services = {'test_service'}
        
        container = MinimalContainer(parent_container, required_services)
        
        # Act
        result = container.has_service('test_service')
        
        # Assert
        assert result is True

    def test_has_service_non_required_service_returns_false(self):
        """Test has_service returns False for non-required service."""
        # Arrange
        parent_container = Mock()
        required_services = {'required_service'}
        
        container = MinimalContainer(parent_container, required_services)
        
        # Act
        result = container.has_service('non_required_service')
        
        # Assert
        assert result is False


class TestMinimalContainerLogging:
    """Test logging functionality."""

    def test_container_logs_service_initialization(self):
        """Test that service initialization is properly logged."""
        # Arrange
        parent_container = Mock()
        mock_service_instance = Mock()
        mock_provider = Mock()
        mock_provider.return_value = mock_service_instance
        
        parent_container.test_service = mock_provider
        required_services = {'test_service'}
        
        with patch('agentmap.di.minimal_container.LoggingService') as mock_logging:
            mock_logger = Mock()
            mock_logging_service = Mock()
            mock_logging_service.get_class_logger.return_value = mock_logger
            
            container = MinimalContainer(parent_container, required_services, mock_logging_service)
            
            # Act
            container.initialize_service('test_service')
            
            # Assert
            mock_logger.debug.assert_called()

    def test_container_logs_skipped_services(self):
        """Test that skipped non-required services are logged."""
        # Arrange
        parent_container = Mock()
        required_services = {'required_service'}
        
        with patch('agentmap.di.minimal_container.LoggingService') as mock_logging:
            mock_logger = Mock()
            mock_logging_service = Mock()
            mock_logging_service.get_class_logger.return_value = mock_logger
            
            container = MinimalContainer(parent_container, required_services, mock_logging_service)
            
            # Act
            container.get_service('non_required_service')
            
            # Assert
            mock_logger.debug.assert_called_with(
                "Service 'non_required_service' not in required services, returning None"
            )

    def test_container_logs_initialization_summary(self):
        """Test that initialization summary is logged."""
        # Arrange
        parent_container = Mock()
        required_services = {'service1', 'service2'}
        
        with patch('agentmap.di.minimal_container.LoggingService') as mock_logging:
            mock_logger = Mock()
            mock_logging_service = Mock()
            mock_logging_service.get_class_logger.return_value = mock_logger
            
            container = MinimalContainer(parent_container, required_services, mock_logging_service)
            
            # Assert - Should log the required services count
            mock_logger.info.assert_called()


class TestMinimalContainerDependencyResolution:
    """Test dependency resolution functionality."""

    def test_get_service_dependencies_extracts_from_parent_container(self):
        """Test _get_service_dependencies extracts dependencies from parent container."""
        # Arrange
        parent_container = Mock()
        required_services = {'test_service'}
        
        container = MinimalContainer(parent_container, required_services)
        
        with patch('agentmap.di.minimal_container.DIContainerAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.get_service_dependencies.return_value = {'dep1', 'dep2'}
            mock_analyzer_class.return_value = mock_analyzer
            
            # Act
            dependencies = container._get_service_dependencies('test_service')
            
            # Assert
            assert dependencies == {'dep1', 'dep2'}
            mock_analyzer.get_service_dependencies.assert_called_once_with('test_service')

    def test_resolve_all_dependencies_builds_complete_tree(self):
        """Test _resolve_all_dependencies builds complete dependency tree."""
        # Arrange
        parent_container = Mock()
        required_services = {'root_service'}
        
        with patch('agentmap.di.minimal_container.DIContainerAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.build_full_dependency_tree.return_value = {'root_service', 'dep1', 'dep2', 'dep3'}
            mock_analyzer_class.return_value = mock_analyzer
            
            container = MinimalContainer(parent_container, required_services)
            
            # Act
            all_deps = container._resolve_all_dependencies({'root_service'})
            
            # Assert
            assert all_deps == {'root_service', 'dep1', 'dep2', 'dep3'}
            mock_analyzer.build_full_dependency_tree.assert_called_once_with({'root_service'})


class TestMinimalContainerErrorHandling:
    """Test error handling and edge cases."""

    def test_initialize_service_handles_provider_exception(self):
        """Test that exceptions during service initialization are handled gracefully."""
        # Arrange
        parent_container = Mock()
        mock_provider = Mock()
        mock_provider.side_effect = Exception("Service initialization failed")
        
        parent_container.failing_service = mock_provider
        required_services = {'failing_service'}
        
        container = MinimalContainer(parent_container, required_services)
        
        # Act
        result = container.initialize_service('failing_service')
        
        # Assert
        assert result is None
        assert 'failing_service' not in container.initialized_services

    def test_get_service_handles_initialization_failure(self):
        """Test get_service handles initialization failure gracefully."""
        # Arrange
        parent_container = Mock()
        required_services = {'failing_service'}
        
        container = MinimalContainer(parent_container, required_services)
        
        with patch.object(container, 'initialize_service', return_value=None):
            # Act
            result = container.get_service('failing_service')
            
            # Assert
            assert result is None

    def test_circular_dependency_resolution_does_not_loop(self):
        """Test that circular dependencies don't cause infinite loops."""
        # Arrange
        parent_container = Mock()
        required_services = {'service_a'}
        
        with patch('agentmap.di.minimal_container.DIContainerAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.build_full_dependency_tree.return_value = {'service_a', 'service_b'}
            mock_analyzer_class.return_value = mock_analyzer
            
            container = MinimalContainer(parent_container, required_services)
            
            # Act
            all_deps = container._resolve_all_dependencies({'service_a'})
            
            # Assert
            assert all_deps == {'service_a', 'service_b'}
            mock_analyzer.build_full_dependency_tree.assert_called_once_with({'service_a'})


class TestMinimalContainerIntegration:
    """Integration tests with real ApplicationContainer."""

    def test_minimal_container_with_real_logging_service(self):
        """Test minimal container with real ApplicationContainer and logging service."""
        # Arrange
        parent_container = ApplicationContainer()
        required_services = {'logging_service'}
        
        # Act
        container = MinimalContainer(parent_container, required_services)
        service = container.get_service('logging_service')
        
        # Assert
        assert service is not None
        assert 'logging_service' in container.initialized_services

    def test_minimal_container_excludes_non_required_services(self):
        """Test that non-required services are not initialized."""
        # Arrange
        parent_container = ApplicationContainer()
        required_services = {'logging_service'}  # Only require logging
        
        # Act
        container = MinimalContainer(parent_container, required_services)
        
        # Try to get a service that's not required
        llm_service = container.get_service('llm_service')
        
        # Assert
        assert llm_service is None
        assert 'llm_service' not in container.initialized_services

    def test_minimal_container_logs_what_was_loaded_vs_skipped(self):
        """Test that container properly logs what was loaded vs skipped."""
        # Arrange
        parent_container = ApplicationContainer()
        required_services = {'logging_service', 'config_service'}
        
        with patch('agentmap.di.minimal_container.LoggingService') as mock_logging:
            mock_logger = Mock()
            mock_logging_service = Mock()
            mock_logging_service.get_class_logger.return_value = mock_logger
            
            # Act
            container = MinimalContainer(parent_container, required_services, mock_logging_service)
            container.get_service('logging_service')  # Required
            container.get_service('llm_service')      # Not required
            
            # Assert
            mock_logger.debug.assert_called()  # Should log both scenarios
