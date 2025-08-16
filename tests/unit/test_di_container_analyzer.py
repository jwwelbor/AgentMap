"""
Unit tests for DIContainerAnalyzer service.

Tests the dependency extraction and analysis functionality for DI containers
following TDD principles and clean architecture patterns.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Set, List
from dependency_injector import providers

from agentmap.services.di_container_analyzer import DIContainerAnalyzer
from agentmap.di.containers import ApplicationContainer


class TestDIContainerAnalyzerInitialization:
    """Test DIContainerAnalyzer initialization and basic functionality."""

    def test_init_with_valid_container(self):
        """Test successful initialization with ApplicationContainer."""
        # Arrange
        container = ApplicationContainer()
        
        # Act
        analyzer = DIContainerAnalyzer(container)
        
        # Assert
        assert analyzer.container == container
        assert analyzer.logger is not None

    def test_init_with_none_container_raises_error(self):
        """Test initialization with None container raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Container cannot be None"):
            DIContainerAnalyzer(None)


class TestDIContainerAnalyzerServiceDependencies:
    """Test extracting dependencies from individual services."""

    def test_get_service_dependencies_with_singleton_provider(self):
        """Test extracting dependencies from Singleton provider."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Mock a service with known dependencies
        mock_provider = Mock(spec=providers.Singleton)
        mock_provider.dependencies = ['logging_service', 'app_config_service']
        
        with patch.object(analyzer, '_get_provider', return_value=mock_provider):
            # Act
            dependencies = analyzer.get_service_dependencies('test_service')
            
            # Assert
            assert dependencies == {'logging_service', 'app_config_service'}

    def test_get_service_dependencies_with_factory_provider(self):
        """Test extracting dependencies from Factory provider."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Mock a factory provider
        mock_provider = Mock(spec=providers.Factory)
        mock_provider.dependencies = ['dependency1', 'dependency2']
        
        with patch.object(analyzer, '_get_provider', return_value=mock_provider):
            # Act
            dependencies = analyzer.get_service_dependencies('factory_service')
            
            # Assert
            assert dependencies == {'dependency1', 'dependency2'}

    def test_get_service_dependencies_nonexistent_service(self):
        """Test getting dependencies for nonexistent service returns empty set."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        with patch.object(analyzer, '_get_provider', return_value=None):
            # Act
            dependencies = analyzer.get_service_dependencies('nonexistent_service')
            
            # Assert
            assert dependencies == set()

    def test_get_service_dependencies_with_provider_args(self):
        """Test extracting dependencies from provider args when no dependencies attribute."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Create mock provider with args containing other providers
        mock_dep1 = Mock(spec=providers.Provider)
        mock_dep2 = Mock(spec=providers.Provider)
        
        mock_provider = Mock()
        mock_provider.dependencies = None  # No dependencies attribute
        mock_provider.args = [mock_dep1, mock_dep2]
        mock_provider.kwargs = {}
        
        # Mock the _extract_provider_name method
        with patch.object(analyzer, '_get_provider', return_value=mock_provider), \
             patch.object(analyzer, '_extract_provider_name', side_effect=['dep1', 'dep2']):
            
            # Act
            dependencies = analyzer.get_service_dependencies('test_service')
            
            # Assert
            assert dependencies == {'dep1', 'dep2'}

    def test_get_service_dependencies_with_provider_kwargs(self):
        """Test extracting dependencies from provider kwargs."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Create mock provider with kwargs containing other providers
        mock_dep1 = Mock(spec=providers.Provider)
        mock_dep2 = Mock(spec=providers.Provider)
        
        mock_provider = Mock()
        mock_provider.dependencies = None
        mock_provider.args = []
        mock_provider.kwargs = {'config': mock_dep1, 'logger': mock_dep2}
        
        with patch.object(analyzer, '_get_provider', return_value=mock_provider), \
             patch.object(analyzer, '_extract_provider_name', side_effect=['config_service', 'logging_service']):
            
            # Act
            dependencies = analyzer.get_service_dependencies('test_service')
            
            # Assert
            assert dependencies == {'config_service', 'logging_service'}


class TestDIContainerAnalyzerDependencyTree:
    """Test building complete dependency trees."""

    def test_build_full_dependency_tree_single_service(self):
        """Test building dependency tree for service with no dependencies."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        with patch.object(analyzer, 'get_service_dependencies', return_value=set()):
            # Act
            result = analyzer.build_full_dependency_tree({'standalone_service'})
            
            # Assert
            assert result == {'standalone_service'}

    def test_build_full_dependency_tree_with_dependencies(self):
        """Test building dependency tree with multiple levels."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Mock dependency relationships
        def mock_get_dependencies(service_name):
            deps = {
                'service_a': {'service_b', 'service_c'},
                'service_b': {'service_d'},
                'service_c': {'service_d'},
                'service_d': set()
            }
            return deps.get(service_name, set())
        
        with patch.object(analyzer, 'get_service_dependencies', side_effect=mock_get_dependencies):
            # Act
            result = analyzer.build_full_dependency_tree({'service_a'})
            
            # Assert
            assert result == {'service_a', 'service_b', 'service_c', 'service_d'}

    def test_build_full_dependency_tree_multiple_roots(self):
        """Test building dependency tree with multiple root services."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        def mock_get_dependencies(service_name):
            deps = {
                'root1': {'shared_dep'},
                'root2': {'shared_dep', 'unique_dep'},
                'shared_dep': set(),
                'unique_dep': set()
            }
            return deps.get(service_name, set())
        
        with patch.object(analyzer, 'get_service_dependencies', side_effect=mock_get_dependencies):
            # Act
            result = analyzer.build_full_dependency_tree({'root1', 'root2'})
            
            # Assert
            assert result == {'root1', 'root2', 'shared_dep', 'unique_dep'}

    def test_build_full_dependency_tree_handles_circular_dependencies(self):
        """Test that circular dependencies don't cause infinite loops."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        def mock_get_dependencies(service_name):
            deps = {
                'service_a': {'service_b'},
                'service_b': {'service_c'},
                'service_c': {'service_a'}  # Circular dependency
            }
            return deps.get(service_name, set())
        
        with patch.object(analyzer, 'get_service_dependencies', side_effect=mock_get_dependencies):
            # Act
            result = analyzer.build_full_dependency_tree({'service_a'})
            
            # Assert
            assert result == {'service_a', 'service_b', 'service_c'}

    def test_build_full_dependency_tree_empty_input(self):
        """Test building dependency tree with empty root services."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Act
        result = analyzer.build_full_dependency_tree(set())
        
        # Assert
        assert result == set()


class TestDIContainerAnalyzerHelperMethods:
    """Test helper methods for provider analysis."""

    def test_get_provider_existing_service(self):
        """Test _get_provider returns provider for existing service."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Act
        provider = analyzer._get_provider('logging_service')
        
        # Assert
        assert provider is not None
        assert hasattr(provider, '__call__')  # Provider should be callable

    def test_get_provider_nonexistent_service(self):
        """Test _get_provider returns None for nonexistent service."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Act
        provider = analyzer._get_provider('nonexistent_service')
        
        # Assert
        assert provider is None

    def test_extract_provider_name_from_provider_instance(self):
        """Test extracting service name from provider instance."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Create a mock provider that matches container pattern
        mock_provider = Mock()
        mock_provider._original_provider = Mock()
        
        # Mock the container's providers to return our mock
        with patch.object(container, 'providers', {'test_service': mock_provider}):
            # Act
            name = analyzer._extract_provider_name(mock_provider)
            
            # Assert
            assert name == 'test_service'

    def test_extract_provider_name_unknown_provider(self):
        """Test extracting name from unknown provider returns None."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        unknown_provider = Mock()
        
        # Act
        name = analyzer._extract_provider_name(unknown_provider)
        
        # Assert
        assert name is None

    def test_is_provider_instance_true(self):
        """Test _is_provider_instance correctly identifies providers."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        provider = Mock(spec=providers.Provider)
        
        # Act
        result = analyzer._is_provider_instance(provider)
        
        # Assert
        assert result is True

    def test_is_provider_instance_false(self):
        """Test _is_provider_instance correctly identifies non-providers."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        not_provider = "just a string"
        
        # Act
        result = analyzer._is_provider_instance(not_provider)
        
        # Assert
        assert result is False


class TestDIContainerAnalyzerErrorHandling:
    """Test error handling and edge cases."""

    def test_get_service_dependencies_handles_provider_without_dependencies(self):
        """Test handling providers that don't have dependencies attribute."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Mock provider without dependencies attribute
        mock_provider = Mock()
        del mock_provider.dependencies  # Ensure no dependencies attribute
        mock_provider.args = []
        mock_provider.kwargs = {}
        
        with patch.object(analyzer, '_get_provider', return_value=mock_provider):
            # Act
            dependencies = analyzer.get_service_dependencies('test_service')
            
            # Assert
            assert dependencies == set()

    def test_get_service_dependencies_handles_exception(self):
        """Test that exceptions during dependency extraction are handled gracefully."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        with patch.object(analyzer, '_get_provider', side_effect=Exception("Test error")):
            # Act
            dependencies = analyzer.get_service_dependencies('test_service')
            
            # Assert
            assert dependencies == set()

    def test_build_full_dependency_tree_handles_max_depth(self):
        """Test that deeply nested dependencies don't cause stack overflow."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Create a very deep dependency chain
        def mock_get_dependencies(service_name):
            if service_name.startswith('service_'):
                num = int(service_name.split('_')[1])
                if num < 1000:  # Very deep
                    return {f'service_{num + 1}'}
            return set()
        
        with patch.object(analyzer, 'get_service_dependencies', side_effect=mock_get_dependencies):
            # Act
            result = analyzer.build_full_dependency_tree({'service_1'})
            
            # Assert - Should complete without stack overflow
            assert 'service_1' in result
            assert len(result) > 10  # Should have found many dependencies


class TestDIContainerAnalyzerIntegration:
    """Integration tests with real ApplicationContainer."""

    def test_analyze_real_logging_service_dependencies(self):
        """Test analyzing dependencies of real logging service."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Act
        dependencies = analyzer.get_service_dependencies('logging_service')
        
        # Assert - logging_service should depend on app_config_service
        assert 'app_config_service' in dependencies

    def test_analyze_real_app_config_service_dependencies(self):
        """Test analyzing dependencies of real app config service."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Act
        dependencies = analyzer.get_service_dependencies('app_config_service')
        
        # Assert - app_config_service should have config_service dependency
        assert 'config_service' in dependencies

    def test_build_dependency_tree_for_graph_runner_service(self):
        """Test building complete dependency tree for graph_runner_service."""
        # Arrange
        container = ApplicationContainer()
        analyzer = DIContainerAnalyzer(container)
        
        # Act
        all_dependencies = analyzer.build_full_dependency_tree({'graph_runner_service'})
        
        # Assert - Should include core dependencies
        assert 'graph_runner_service' in all_dependencies
        assert 'logging_service' in all_dependencies
        assert 'app_config_service' in all_dependencies
        assert len(all_dependencies) > 5  # Should have many transitive dependencies


class TestDIContainerAnalyzerLogging:
    """Test logging functionality."""

    def test_analyzer_logs_dependency_analysis(self):
        """Test that dependency analysis is properly logged."""
        # Arrange
        container = ApplicationContainer()
        
        with patch('agentmap.services.di_container_analyzer.LoggingService') as mock_logging:
            mock_logger = Mock()
            mock_logging_service = Mock()
            mock_logging_service.get_class_logger.return_value = mock_logger
            
            analyzer = DIContainerAnalyzer(container, mock_logging_service)
            
            # Act
            analyzer.get_service_dependencies('test_service')
            
            # Assert
            mock_logger.debug.assert_called()

    def test_analyzer_logs_circular_dependency_detection(self):
        """Test that circular dependencies are logged."""
        # Arrange
        container = ApplicationContainer()
        
        with patch('agentmap.services.di_container_analyzer.LoggingService') as mock_logging:
            mock_logger = Mock()
            mock_logging_service = Mock()
            mock_logging_service.get_class_logger.return_value = mock_logger
            
            analyzer = DIContainerAnalyzer(container, mock_logging_service)
            
            # Setup circular dependency
            def mock_get_dependencies(service_name):
                return {'service_a': {'service_b'}, 'service_b': {'service_a'}}.get(service_name, set())
            
            with patch.object(analyzer, 'get_service_dependencies', side_effect=mock_get_dependencies):
                # Act
                analyzer.build_full_dependency_tree({'service_a'})
                
                # Assert - Should log about circular dependency handling
                mock_logger.debug.assert_called()
