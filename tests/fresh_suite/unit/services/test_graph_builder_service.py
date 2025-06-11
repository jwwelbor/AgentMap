"""
Unit tests for GraphBuilderService.

These tests validate the GraphBuilderService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, mock_open
from pathlib import Path
from typing import Dict, Any, List

from agentmap.services.graph_builder_service import GraphBuilderService
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphBuilderService(unittest.TestCase):
    """Unit tests for GraphBuilderService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        
        # Initialize GraphBuilderService with mocked dependencies
        self.service = GraphBuilderService(
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertIsNotNone(self.service.logger)
        
        # Verify logger is configured correctly
        self.assertEqual(self.service.logger.name, 'GraphBuilderService')
        
        # Verify get_class_logger was called during initialization
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)
        
        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == '[GraphBuilderService] Initialized' 
                          for call in logger_calls if call[0] == 'info'))
    
    def test_service_logs_status(self):
        """Test that service status logging works correctly."""
        # Verify initialization logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == 'info']
        self.assertTrue(any('[GraphBuilderService] Initialized' in call[1] 
                          for call in info_calls))
    
    def test_service_basic_mock_setup(self):
        """Test that basic mock setup works correctly."""
        # This is a simple verification test to ensure mocking is working
        self.assertIsNotNone(self.service)
        self.assertIsNotNone(self.mock_logger)
        
        # Test that we can create and configure Mock objects
        test_mock = Mock()
        test_mock.name = "test_name"
        self.assertEqual(test_mock.name, "test_name")
        
        # Test that Path can be mocked
        import unittest.mock
        with unittest.mock.patch('pathlib.Path.exists', return_value=True) as mock_exists:
            from pathlib import Path
            result = Path('test.txt').exists()
            self.assertTrue(result)
            mock_exists.assert_called_once()
    
    # =============================================================================
    # 2. Core Business Logic Tests
    # =============================================================================
    
    def test_build_from_csv_single_graph(self):
        """Test build_from_csv() returns single specified graph."""
        import unittest.mock
        # Import here to avoid module-level import issues
        from agentmap.models.graph import Graph
        
        # Mock the internal methods to focus on coordination logic
        mock_raw_graphs = {
            "test_graph": {
                "node1": Mock(name="node1", agent_type="default"),
                "node2": Mock(name="node2", agent_type="default")
            }
        }
        
        mock_domain_graphs = {
            "test_graph": Mock(spec=Graph)
        }
        mock_domain_graphs["test_graph"].name = "test_graph"
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value=mock_raw_graphs), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges'), \
             unittest.mock.patch.object(self.service, '_convert_to_domain_models', return_value=mock_domain_graphs), \
             unittest.mock.patch('pathlib.Path.exists', return_value=True):
            
            # Execute test
            result = self.service.build_from_csv(Path('test.csv'), 'test_graph')
            
            # Verify coordination and result
            self.assertEqual(result, mock_domain_graphs["test_graph"])
            self.assertEqual(result.name, "test_graph")
            
            # Verify internal method calls
            self.service._create_nodes_from_csv.assert_called_once_with(Path('test.csv'))
            self.service._connect_nodes_with_edges.assert_called_once_with(mock_raw_graphs, Path('test.csv'))
            self.service._convert_to_domain_models.assert_called_once_with(mock_raw_graphs)
    
    def test_build_from_csv_first_graph_fallback(self):
        """Test build_from_csv() returns first graph when name not specified."""
        import unittest.mock
        from agentmap.models.graph import Graph
        
        # Mock multiple graphs
        mock_raw_graphs = {
            "first_graph": {"node1": Mock()},
            "second_graph": {"node2": Mock()}
        }
        
        mock_domain_graphs = {
            "first_graph": Mock(spec=Graph),
            "second_graph": Mock(spec=Graph)
        }
        mock_domain_graphs["first_graph"].name = "first_graph"
        mock_domain_graphs["second_graph"].name = "second_graph"
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value=mock_raw_graphs), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges'), \
             unittest.mock.patch.object(self.service, '_convert_to_domain_models', return_value=mock_domain_graphs), \
             unittest.mock.patch('pathlib.Path.exists', return_value=True):
            
            # Execute test - no specific graph requested
            result = self.service.build_from_csv(Path('test.csv'))
            
            # Verify first graph returned
            self.assertEqual(result, mock_domain_graphs["first_graph"])
            self.assertEqual(result.name, "first_graph")
    
    def test_build_from_csv_graph_not_found_error(self):
        """Test build_from_csv() raises error when requested graph not found."""
        import unittest.mock
        
        # Mock limited graphs
        mock_raw_graphs = {"available_graph": {"node1": Mock()}}
        mock_domain_graphs = {"available_graph": Mock()}
        mock_domain_graphs["available_graph"].name = "available_graph"
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value=mock_raw_graphs), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges'), \
             unittest.mock.patch.object(self.service, '_convert_to_domain_models', return_value=mock_domain_graphs), \
             unittest.mock.patch('pathlib.Path.exists', return_value=True):
            
            # Execute test - request non-existent graph
            with self.assertRaises(ValueError) as context:
                self.service.build_from_csv(Path('test.csv'), 'non_existent_graph')
            
            # Verify error message includes available graphs
            error_msg = str(context.exception)
            self.assertIn("Graph 'non_existent_graph' not found", error_msg)
            self.assertIn("Available graphs: ['available_graph']", error_msg)
    
    def test_build_all_from_csv_multiple_graphs(self):
        """Test build_all_from_csv() returns dictionary of all graphs."""
        import unittest.mock
        from agentmap.models.graph import Graph
        
        # Mock multiple graphs
        mock_raw_graphs = {
            "graph_alpha": {"node1": Mock()},
            "graph_beta": {"node2": Mock()}
        }
        
        mock_domain_graphs = {
            "graph_alpha": Mock(spec=Graph),
            "graph_beta": Mock(spec=Graph)
        }
        mock_domain_graphs["graph_alpha"].name = "graph_alpha"
        mock_domain_graphs["graph_beta"].name = "graph_beta"
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value=mock_raw_graphs), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges'), \
             unittest.mock.patch.object(self.service, '_convert_to_domain_models', return_value=mock_domain_graphs), \
             unittest.mock.patch('pathlib.Path.exists', return_value=True):
            
            # Execute test
            result = self.service.build_all_from_csv(Path('test.csv'))
            
            # Verify all graphs returned
            self.assertEqual(len(result), 2)
            self.assertIn('graph_alpha', result)
            self.assertIn('graph_beta', result)
            self.assertEqual(result['graph_alpha'], mock_domain_graphs['graph_alpha'])
            self.assertEqual(result['graph_beta'], mock_domain_graphs['graph_beta'])
    
    def test_build_all_from_csv_empty_graphs(self):
        """Test build_all_from_csv() handles empty results gracefully."""
        import unittest.mock
        
        # Mock empty graphs
        mock_raw_graphs = {}
        mock_domain_graphs = {}
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value=mock_raw_graphs), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges'), \
             unittest.mock.patch.object(self.service, '_convert_to_domain_models', return_value=mock_domain_graphs), \
             unittest.mock.patch('pathlib.Path.exists', return_value=True):
            
            # Execute test
            result = self.service.build_all_from_csv(Path('empty.csv'))
            
            # Should return empty dictionary
            self.assertEqual(result, {})
    
    # =============================================================================
    # 3. CSV Validation Tests
    # =============================================================================
    
    def test_validate_csv_before_building_success(self):
        """Test validate_csv_before_building() with valid CSV."""
        import unittest.mock
        
        # Mock valid CSV content
        csv_content = "GraphName,Node,AgentType\ntest_graph,node1,default\n"
        
        # Create a proper mock context manager using mock_open
        mock_file = mock_open(read_data=csv_content)
        
        # Create a mock Path that behaves properly
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.open = mock_file
        
        # Create a mock Path class that always returns the same mock_path instance
        def mock_path_constructor(*args, **kwargs):
            return mock_path
        
        # Patch Path in the service module where it's imported
        with unittest.mock.patch('agentmap.services.graph_builder_service.Path', side_effect=mock_path_constructor):
            # Execute test
            errors = self.service.validate_csv_before_building(Path('valid.csv'))
            
            # Should return no errors for valid CSV
            self.assertEqual(errors, [])
    
    def test_validate_csv_before_building_missing_file(self):
        """Test validate_csv_before_building() with missing file."""
        import unittest.mock
        
        # Create a mock Path that doesn't exist
        mock_path = Mock()
        mock_path.exists.return_value = False
        
        # Create a mock Path class that always returns the same mock_path instance
        def mock_path_constructor(*args, **kwargs):
            return mock_path
        
        # Patch Path in the service module where it's imported
        with unittest.mock.patch('agentmap.services.graph_builder_service.Path', side_effect=mock_path_constructor):
            # Execute test
            errors = self.service.validate_csv_before_building(Path('missing.csv'))
            
            # Should detect missing file
            self.assertEqual(len(errors), 1)
            self.assertIn("CSV file not found", errors[0])
    
    def test_validate_csv_before_building_missing_columns(self):
        """Test validate_csv_before_building() with missing required columns."""
        import unittest.mock
        
        # Mock CSV missing required columns
        csv_content = "WrongColumn,AnotherWrong\nvalue1,value2\n"
        
        # Create a proper mock context manager using mock_open
        mock_file = mock_open(read_data=csv_content)
        
        # Create a mock Path that behaves properly
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.open = mock_file
        
        # Create a mock Path class that always returns the same mock_path instance
        def mock_path_constructor(*args, **kwargs):
            return mock_path
        
        # Patch Path in the service module where it's imported
        with unittest.mock.patch('agentmap.services.graph_builder_service.Path', side_effect=mock_path_constructor):
            # Execute test
            errors = self.service.validate_csv_before_building(Path('invalid.csv'))
            
            # Should detect missing required columns
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any("Missing required columns" in error for error in errors))
    
    def test_validate_csv_before_building_empty_data(self):
        """Test validate_csv_before_building() with empty data."""
        import unittest.mock
        
        # Mock CSV with headers but no data
        csv_content = "GraphName,Node,AgentType\n"
        
        # Create a proper mock context manager using mock_open
        mock_file = mock_open(read_data=csv_content)
        
        # Create a mock Path that behaves properly
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.open = mock_file
        
        # Create a mock Path class that always returns the same mock_path instance
        def mock_path_constructor(*args, **kwargs):
            return mock_path
        
        # Patch Path in the service module where it's imported
        with unittest.mock.patch('agentmap.services.graph_builder_service.Path', side_effect=mock_path_constructor):
            # Execute test
            errors = self.service.validate_csv_before_building(Path('empty.csv'))
            
            # Should detect empty data
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any("empty or contains no data rows" in error for error in errors))
    
    def test_validate_csv_before_building_missing_values(self):
        """Test validate_csv_before_building() with missing required values."""
        import unittest.mock
        
        # Mock CSV with missing GraphName and Node values
        csv_content = "GraphName,Node,AgentType\n,node1,default\ntest_graph,,default\n"
        
        # Create a proper mock context manager using mock_open
        mock_file = mock_open(read_data=csv_content)
        
        # Create a mock Path that behaves properly
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.open = mock_file
        
        # Create a mock Path class that always returns the same mock_path instance
        def mock_path_constructor(*args, **kwargs):
            return mock_path
        
        # Patch Path in the service module where it's imported
        with unittest.mock.patch('agentmap.services.graph_builder_service.Path', side_effect=mock_path_constructor):
            # Execute test
            errors = self.service.validate_csv_before_building(Path('invalid.csv'))
            
            # Should detect missing values
            self.assertTrue(len(errors) >= 2)
            self.assertTrue(any("Missing GraphName" in error for error in errors))
            self.assertTrue(any("Missing Node name" in error for error in errors))
    
    # =============================================================================
    # 4. Error Handling Tests
    # =============================================================================
    
    def test_build_from_csv_file_not_found(self):
        """Test build_from_csv() handles FileNotFoundError properly."""
        with unittest.mock.patch('pathlib.Path.exists', return_value=False):
            
            # Execute and verify FileNotFoundError
            with self.assertRaises(FileNotFoundError) as context:
                self.service.build_from_csv(Path('nonexistent.csv'))
            
            # Verify error message
            self.assertIn('CSV file not found', str(context.exception))
    
    def test_build_all_from_csv_file_not_found(self):
        """Test build_all_from_csv() handles FileNotFoundError properly."""
        with unittest.mock.patch('pathlib.Path.exists', return_value=False):
            
            # Execute and verify FileNotFoundError
            with self.assertRaises(FileNotFoundError) as context:
                self.service.build_all_from_csv(Path('missing.csv'))
            
            # Verify error message
            self.assertIn('CSV file not found', str(context.exception))
    
    def test_build_from_csv_no_graphs_error(self):
        """Test build_from_csv() raises error when no graphs found."""
        import unittest.mock
        
        # Mock empty raw graphs
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value={}), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges'), \
             unittest.mock.patch.object(self.service, '_convert_to_domain_models', return_value={}), \
             unittest.mock.patch('pathlib.Path.exists', return_value=True):
            
            # Execute and verify ValueError
            with self.assertRaises(ValueError) as context:
                self.service.build_from_csv(Path('empty.csv'))
            
            self.assertIn('No graphs found', str(context.exception))
    
    def test_edge_connection_conflict_error(self):
        """Test InvalidEdgeDefinitionError for conflicting edge definitions."""
        import unittest.mock
        from agentmap.exceptions.graph_exceptions import InvalidEdgeDefinitionError
        
        # Mock raw graphs that will pass to edge connection
        mock_raw_graphs = {"test_graph": {"node1": Mock()}}
        
        # Mock edge connection to raise conflict error
        def mock_connect_edges(graphs, csv_path):
            raise InvalidEdgeDefinitionError("Node has both Edge and Success/Failure defined")
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value=mock_raw_graphs), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges', side_effect=mock_connect_edges), \
             unittest.mock.patch('pathlib.Path.exists', return_value=True):
            
            # Execute and verify InvalidEdgeDefinitionError
            with self.assertRaises(InvalidEdgeDefinitionError) as context:
                self.service.build_from_csv(Path('conflict.csv'))
            
            self.assertIn('both Edge and Success/Failure defined', str(context.exception))
    
    def test_edge_target_not_found_error(self):
        """Test ValueError when edge target node doesn't exist."""
        import unittest.mock
        
        # Mock raw graphs that will pass to edge connection
        mock_raw_graphs = {"test_graph": {"source_node": Mock()}}
        
        # Mock edge connection to raise target not found error
        def mock_connect_edges(graphs, csv_path):
            raise ValueError("Edge target 'nonexistent_target' is not defined as a node")
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value=mock_raw_graphs), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges', side_effect=mock_connect_edges), \
             unittest.mock.patch('pathlib.Path.exists', return_value=True):
            
            # Execute and verify ValueError
            with self.assertRaises(ValueError) as context:
                self.service.build_from_csv(Path('invalid_edge.csv'))
            
            self.assertIn('not defined as a node', str(context.exception))
    
    # =============================================================================
    # 5. File Operation Tests
    # =============================================================================
    
    def test_build_from_csv_with_path_exists_scenarios(self):
        """Test build_from_csv() behavior with different file existence scenarios."""
        import unittest.mock
        
        # Mock successful processing
        mock_raw_graphs = {"test_graph": {"node1": Mock()}}
        mock_domain_graphs = {"test_graph": Mock()}
        mock_domain_graphs["test_graph"].name = "test_graph"
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value=mock_raw_graphs), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges'), \
             unittest.mock.patch.object(self.service, '_convert_to_domain_models', return_value=mock_domain_graphs):
            
            # Test when file exists
            with unittest.mock.patch('pathlib.Path.exists', return_value=True):
                result = self.service.build_from_csv(Path('existing.csv'))
                self.assertEqual(result, mock_domain_graphs["test_graph"])
            
            # Test when file doesn't exist
            with unittest.mock.patch('pathlib.Path.exists', return_value=False):
                with self.assertRaises(FileNotFoundError):
                    self.service.build_from_csv(Path('nonexistent.csv'))
    
    def test_validate_csv_with_file_read_error(self):
        """Test validate_csv_before_building() handles file read errors."""
        import unittest.mock
        
        # Create a mock Path that raises an error on open
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.open.side_effect = IOError("Permission denied")
        
        # Create a mock Path class that always returns the same mock_path instance
        def mock_path_constructor(*args, **kwargs):
            return mock_path
        
        # Patch Path in the service module where it's imported
        with unittest.mock.patch('agentmap.services.graph_builder_service.Path', side_effect=mock_path_constructor):
            # Execute test
            errors = self.service.validate_csv_before_building(Path('error.csv'))
            
            # Should handle error gracefully
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any("Error reading CSV file" in error for error in errors))
    
    def test_build_with_path_operations_logging(self):
        """Test that path operations are properly logged."""
        import unittest.mock
        
        # Mock processing steps
        mock_raw_graphs = {"test_graph": {"node1": Mock()}}
        mock_domain_graphs = {"test_graph": Mock(name="test_graph")}
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_csv', return_value=mock_raw_graphs), \
             unittest.mock.patch.object(self.service, '_connect_nodes_with_edges'), \
             unittest.mock.patch.object(self.service, '_convert_to_domain_models', return_value=mock_domain_graphs), \
             unittest.mock.patch('pathlib.Path.exists', return_value=True):
            
            # Execute test
            result = self.service.build_from_csv(Path('test.csv'))
            
            # Verify logging of file operations
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == 'info']
            
            # Should log building operation
            self.assertTrue(any('Building single graph from' in call[1] for call in info_calls))
            self.assertTrue(any('Successfully built' in call[1] for call in info_calls))
    
    def test_service_error_logging(self):
        """Test that service properly logs errors during operations."""
        import unittest.mock
        
        # Mock file not found to trigger error logging
        with unittest.mock.patch('pathlib.Path.exists', return_value=False):
            
            # Execute test that should log error
            with self.assertRaises(FileNotFoundError):
                self.service.build_from_csv(Path('missing.csv'))
            
            # Verify error logging
            logger_calls = self.mock_logger.calls
            error_calls = [call for call in logger_calls if call[0] == 'error']
            
            # Should log the error
            self.assertTrue(any('CSV file not found' in call[1] for call in error_calls))


if __name__ == '__main__':
    unittest.main()
