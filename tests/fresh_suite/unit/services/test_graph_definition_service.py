"""
Unit tests for GraphDefinitionService.

These tests validate the GraphDefinitionService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock
from pathlib import Path
from typing import Dict, Any, Optional

from agentmap.services.graph_definition_service import GraphDefinitionService
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphDefinitionService(unittest.TestCase):
    """Unit tests for GraphDefinitionService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create all 4 mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        self.mock_csv_parser_service = MockServiceFactory.create_mock_csv_graph_parser_service()
        self.mock_graph_factory = MockServiceFactory.create_mock_graph_factory_service()
        
        # Initialize GraphDefinitionService with all mocked dependencies
        self.service = GraphDefinitionService(
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config_service,
            csv_parser=self.mock_csv_parser_service,
            graph_factory=self.mock_graph_factory
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
        self.assertEqual(self.service.csv_parser, self.mock_csv_parser_service)
        
        # Verify logger is configured (test actual behavior, not object identity)
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, 'GraphDefinitionService')
        
        # Verify get_class_logger was called during initialization
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)
        
        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == '[GraphDefinitionService] Initialized' 
                          for call in logger_calls if call[0] == 'info'))
    
    def test_service_logs_status(self):
        """Test that service status logging works correctly."""
        # Verify initialization logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == 'info']
        self.assertTrue(any('[GraphDefinitionService] Initialized' in call[1] 
                          for call in info_calls))
    
    # =============================================================================
    # 2. Core Business Logic Tests
    # =============================================================================
    
    def test_build_from_csv_single_graph(self):
        """Test build_from_csv() returns single specified graph."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        from agentmap.models.graph import Graph
        
        # Configure mock to return multi-graph spec
        node_spec_1 = Mock(spec=NodeSpec)
        node_spec_1.name = 'node1'
        node_spec_1.graph_name = 'graph1'
        
        node_spec_2 = Mock(spec=NodeSpec) 
        node_spec_2.name = 'node2'
        node_spec_2.graph_name = 'graph2'
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['graph1', 'graph2']
        mock_graph_spec.get_nodes_for_graph.side_effect = lambda name: {
            'graph1': [node_spec_1],
            'graph2': [node_spec_2]
        }[name]
        
        # Reset the side_effect and set return_value to override factory defaults
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock internal methods to focus on coordination logic
        mock_graph_1 = Mock(spec=Graph)
        mock_graph_1.name = 'graph1'
        
        mock_graph_2 = Mock(spec=Graph)
        mock_graph_2.name = 'graph2'
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value={'node1': Mock()}), \
             unittest.mock.patch.object(self.service, '_connect_nodes_from_specs'), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes') as mock_convert:
            
            mock_convert.side_effect = lambda name, nodes: mock_graph_1 if name == 'graph1' else mock_graph_2
            
            # Execute test - request specific graph
            result = self.service.build_from_csv(Path('test.csv'), 'graph1')
            
            # Verify CSV parser was called
            self.mock_csv_parser_service.parse_csv_to_graph_spec.assert_called_once_with(Path('test.csv'))
            
            # Verify correct graph returned
            self.assertEqual(result, mock_graph_1)
            self.assertEqual(result.name, 'graph1')
    
    def test_build_from_csv_first_graph_fallback(self):
        """Test build_from_csv() returns first graph when name not specified."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        from agentmap.models.graph import Graph
        
        # Configure mock to return multi-graph spec
        node_spec_1 = Mock(spec=NodeSpec)
        node_spec_1.name = 'node1' 
        node_spec_1.graph_name = 'first_graph'
        
        node_spec_2 = Mock(spec=NodeSpec)
        node_spec_2.name = 'node2'
        node_spec_2.graph_name = 'second_graph'
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['first_graph', 'second_graph']
        mock_graph_spec.get_nodes_for_graph.side_effect = lambda name: {
            'first_graph': [node_spec_1],
            'second_graph': [node_spec_2]
        }[name]
        
        # Reset the side_effect and set return_value to override factory defaults
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock internal methods
        mock_first_graph = Mock(spec=Graph)
        mock_first_graph.name = 'first_graph'
        
        mock_second_graph = Mock(spec=Graph)
        mock_second_graph.name = 'second_graph'
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value={'node1': Mock()}), \
             unittest.mock.patch.object(self.service, '_connect_nodes_from_specs'), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes') as mock_convert:
            
            mock_convert.side_effect = lambda name, nodes: mock_first_graph if name == 'first_graph' else mock_second_graph
            
            # Execute test - no specific graph requested, should return first
            result = self.service.build_from_csv(Path('test.csv'))
            
            # Verify CSV parser was called
            self.mock_csv_parser_service.parse_csv_to_graph_spec.assert_called_once_with(Path('test.csv'))
            
            # Verify first graph returned
            self.assertEqual(result, mock_first_graph)
            self.assertEqual(result.name, 'first_graph')
    
    def test_build_from_csv_graph_not_found_error(self):
        """Test build_from_csv() raises error when requested graph not found."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        
        # Configure mock to return limited graph spec
        node_spec_1 = Mock(spec=NodeSpec)
        node_spec_1.name = 'node1'
        node_spec_1.graph_name = 'available_graph'
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['available_graph']
        mock_graph_spec.get_nodes_for_graph.return_value = [node_spec_1]
        
        # Reset the side_effect and set return_value to override factory defaults
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs'), \
             unittest.mock.patch.object(self.service, '_connect_nodes_from_specs'), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes'):
            
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
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        from agentmap.models.graph import Graph
        
        # Configure mock to return multi-graph spec
        node_spec_1 = Mock(spec=NodeSpec)
        node_spec_1.name = 'node1'
        node_spec_1.graph_name = 'graph_alpha'
        
        node_spec_2 = Mock(spec=NodeSpec)
        node_spec_2.name = 'node2' 
        node_spec_2.graph_name = 'graph_beta'
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['graph_alpha', 'graph_beta']
        mock_graph_spec.get_nodes_for_graph.side_effect = lambda name: {
            'graph_alpha': [node_spec_1],
            'graph_beta': [node_spec_2]
        }[name]
        
        # Reset the side_effect and set return_value to override factory defaults
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock internal methods
        mock_graph_alpha = Mock(spec=Graph)
        mock_graph_alpha.name = 'graph_alpha'
        
        mock_graph_beta = Mock(spec=Graph)
        mock_graph_beta.name = 'graph_beta'
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value={'node': Mock()}), \
             unittest.mock.patch.object(self.service, '_connect_nodes_from_specs'), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes') as mock_convert:
            
            mock_convert.side_effect = lambda name, nodes: {
                'graph_alpha': mock_graph_alpha,
                'graph_beta': mock_graph_beta
            }[name]
            
            # Execute test
            result = self.service.build_all_from_csv(Path('test.csv'))
            
            # Verify CSV parser was called
            self.mock_csv_parser_service.parse_csv_to_graph_spec.assert_called_once_with(Path('test.csv'))
            
            # Verify all graphs returned in dictionary
            self.assertEqual(len(result), 2)
            self.assertIn('graph_alpha', result)
            self.assertIn('graph_beta', result)
            self.assertEqual(result['graph_alpha'], mock_graph_alpha)
            self.assertEqual(result['graph_beta'], mock_graph_beta)
    
    def test_build_from_graph_spec_conversion(self):
        """Test build_from_graph_spec() converts GraphSpec to Graph domain models."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        from agentmap.models.graph import Graph
        
        # Configure GraphSpec mock with test graph
        node_spec_1 = Mock(spec=NodeSpec)
        node_spec_1.name = 'start_node'
        node_spec_1.graph_name = 'test_graph'
        
        node_spec_2 = Mock(spec=NodeSpec)
        node_spec_2.name = 'end_node'
        node_spec_2.graph_name = 'test_graph'
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['test_graph']
        mock_graph_spec.get_nodes_for_graph.return_value = [node_spec_1, node_spec_2]
        
        # Mock internal methods and domain models
        mock_nodes_dict = {'start_node': Mock(), 'end_node': Mock()}
        mock_graph = Mock(spec=Graph)
        mock_graph.name = 'test_graph'
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value=mock_nodes_dict) as mock_create, \
             unittest.mock.patch.object(self.service, '_connect_nodes_from_specs') as mock_connect, \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes', return_value=mock_graph) as mock_convert:
            
            # Execute test
            result = self.service.build_from_graph_spec(mock_graph_spec)
            
            # Verify proper delegation to internal methods
            mock_create.assert_called_once_with([node_spec_1, node_spec_2], 'test_graph')
            mock_connect.assert_called_once_with(mock_nodes_dict, [node_spec_1, node_spec_2], 'test_graph')
            mock_convert.assert_called_once_with('test_graph', mock_nodes_dict)
            
            # Verify correct return structure
            self.assertEqual(len(result), 1)
            self.assertIn('test_graph', result)
            self.assertEqual(result['test_graph'], mock_graph)
    
    def test_build_graph_from_csv_alias_method(self):
        """Test build_graph_from_csv() delegates to build_from_csv()."""
        import unittest.mock
        from agentmap.models.graph import Graph
        
        # Mock the build_from_csv method
        mock_graph = Mock(spec=Graph)
        mock_graph.name = 'test_graph'
        
        with unittest.mock.patch.object(self.service, 'build_from_csv', return_value=mock_graph) as mock_build:
            # Execute test
            result = self.service.build_graph_from_csv(Path('test.csv'), 'specific_graph')
            
            # Verify delegation
            mock_build.assert_called_once_with(Path('test.csv'), 'specific_graph')
            self.assertEqual(result, mock_graph)
    
    # =============================================================================
    # 3. CSV Validation and File Operation Tests
    # =============================================================================
    
    def test_validate_csv_before_building_success(self):
        """Test validate_csv_before_building() with valid CSV."""
        from agentmap.models.validation.validation_models import ValidationResult
        
        # Configure mock to return valid ValidationResult
        mock_validation_result = Mock(spec=ValidationResult)
        mock_validation_result.is_valid = True
        mock_validation_result.errors = []
        mock_validation_result.warnings = []
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.validate_csv_structure.side_effect = None
        self.mock_csv_parser_service.validate_csv_structure.return_value = mock_validation_result
        
        # Execute test
        csv_path = Path('valid.csv')
        errors = self.service.validate_csv_before_building(csv_path)
        
        # Verify delegation and result conversion
        self.mock_csv_parser_service.validate_csv_structure.assert_called_once_with(csv_path)
        self.assertEqual(errors, [])
    
    def test_validate_csv_before_building_with_errors(self):
        """Test validate_csv_before_building() with validation errors."""
        from agentmap.models.validation.validation_models import ValidationResult, ValidationError
        
        # Configure mock with errors and warnings
        mock_error = Mock(spec=ValidationError)
        mock_error.__str__ = Mock(return_value='Test error message')
        
        mock_warning = Mock(spec=ValidationError)
        mock_warning.__str__ = Mock(return_value='Test warning message')
        
        mock_validation_result = Mock(spec=ValidationResult)
        mock_validation_result.is_valid = False
        mock_validation_result.errors = [mock_error]
        mock_validation_result.warnings = [mock_warning]
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.validate_csv_structure.side_effect = None
        self.mock_csv_parser_service.validate_csv_structure.return_value = mock_validation_result
        
        # Execute and verify error conversion
        errors = self.service.validate_csv_before_building(Path('invalid.csv'))
        
        # Verify both errors and warnings are included
        self.assertIn('Test error message', errors)
        self.assertIn('Warning: Test warning message', errors)
        self.assertEqual(len(errors), 2)  # One error + one warning
    
    def test_validate_csv_before_building_warnings_only(self):
        """Test validate_csv_before_building() with warnings but no errors."""
        from agentmap.models.validation.validation_models import ValidationResult, ValidationError
        
        # Configure mock with warnings only
        mock_warning1 = Mock(spec=ValidationError)
        mock_warning1.__str__ = Mock(return_value='First warning')
        
        mock_warning2 = Mock(spec=ValidationError)
        mock_warning2.__str__ = Mock(return_value='Second warning')
        
        mock_validation_result = Mock(spec=ValidationResult)
        mock_validation_result.is_valid = True  # Still valid with just warnings
        mock_validation_result.errors = []
        mock_validation_result.warnings = [mock_warning1, mock_warning2]
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.validate_csv_structure.side_effect = None
        self.mock_csv_parser_service.validate_csv_structure.return_value = mock_validation_result
        
        # Execute and verify warning conversion
        errors = self.service.validate_csv_before_building(Path('warnings.csv'))
        
        # Verify warnings are converted to error list with "Warning:" prefix
        self.assertIn('Warning: First warning', errors)
        self.assertIn('Warning: Second warning', errors)
        self.assertEqual(len(errors), 2)
    
    def test_build_from_csv_file_not_found(self):
        """Test build_from_csv() handles FileNotFoundError properly."""
        # Configure CSV parser to raise FileNotFoundError
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = FileNotFoundError('File not found: test.csv')
        
        # Execute and verify exception propagation
        with self.assertRaises(FileNotFoundError) as context:
            self.service.build_from_csv(Path('nonexistent.csv'))
        
        # Verify exception message
        self.assertIn('File not found: test.csv', str(context.exception))
        
        # Verify CSV parser was called before failing
        self.mock_csv_parser_service.parse_csv_to_graph_spec.assert_called_once_with(Path('nonexistent.csv'))
    
    def test_build_all_from_csv_file_not_found(self):
        """Test build_all_from_csv() handles FileNotFoundError properly."""
        # Configure CSV parser to raise FileNotFoundError
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = FileNotFoundError('No such file or directory')
        
        # Execute and verify exception propagation
        with self.assertRaises(FileNotFoundError) as context:
            self.service.build_all_from_csv(Path('missing.csv'))
        
        # Verify exception message
        self.assertIn('No such file or directory', str(context.exception))
    
    def test_validate_csv_before_building_file_not_found(self):
        """Test validate_csv_before_building() handles FileNotFoundError properly."""
        # Configure CSV parser to raise FileNotFoundError
        self.mock_csv_parser_service.validate_csv_structure.side_effect = FileNotFoundError('CSV file not found')
        
        # Execute and verify exception propagation
        with self.assertRaises(FileNotFoundError) as context:
            self.service.validate_csv_before_building(Path('missing.csv'))
        
        # Verify exception message
        self.assertIn('CSV file not found', str(context.exception))
    
    def test_build_from_csv_with_path_exists_check(self):
        """Test build_from_csv() behavior with file existence scenarios."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        from agentmap.models.graph import Graph
        
        # Configure mock graph spec
        node_spec = Mock(spec=NodeSpec)
        node_spec.name = 'test_node'
        node_spec.graph_name = 'test_graph'
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['test_graph']
        mock_graph_spec.get_nodes_for_graph.return_value = [node_spec]
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock internal methods
        mock_graph = Mock(spec=Graph)
        mock_graph.name = 'test_graph'
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value={'test_node': Mock()}), \
             unittest.mock.patch.object(self.service, '_connect_nodes_from_specs'), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes', return_value=mock_graph):
            
            # Test when file exists
            with unittest.mock.patch('pathlib.Path.exists', return_value=True):
                result = self.service.build_from_csv(Path('existing.csv'))
                self.assertEqual(result, mock_graph)
                
                # Verify CSV parser was called (file existence doesn't affect parsing)
                self.mock_csv_parser_service.parse_csv_to_graph_spec.assert_called_with(Path('existing.csv'))
            
            # Reset mock for next test
            self.mock_csv_parser_service.parse_csv_to_graph_spec.reset_mock()
            
            # Test when file doesn't exist - service will still try to parse (delegating to CSV parser)
            with unittest.mock.patch('pathlib.Path.exists', return_value=False):
                # The service itself doesn't check file existence - it delegates to CSV parser
                # CSV parser would raise FileNotFoundError, but we're mocking its response
                result = self.service.build_from_csv(Path('nonexistent.csv'))
                self.assertEqual(result, mock_graph)
                
                # Verify CSV parser was still called
                self.mock_csv_parser_service.parse_csv_to_graph_spec.assert_called_with(Path('nonexistent.csv'))
    
    # =============================================================================
    # 4. Error Handling and Edge Case Tests
    # =============================================================================
    
    def test_build_from_csv_invalid_graph_name(self):
        """Test build_from_csv() raises ValueError for invalid graph name."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        
        # Configure mock to return spec without requested graph
        node_spec_1 = Mock(spec=NodeSpec)
        node_spec_1.name = 'node1'
        node_spec_1.graph_name = 'existing_graph'
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['existing_graph']
        mock_graph_spec.get_nodes_for_graph.return_value = [node_spec_1]
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock internal methods to reach the validation logic
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value={'node1': Mock()}), \
             unittest.mock.patch.object(self.service, '_connect_nodes_from_specs'), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes', return_value=Mock()):
            
            # Execute and verify ValueError with proper message
            with self.assertRaises(ValueError) as context:
                self.service.build_from_csv(Path('test.csv'), 'nonexistent_graph')
            
            error_message = str(context.exception)
            self.assertIn('nonexistent_graph', error_message)
            self.assertIn('existing_graph', error_message)
            self.assertIn('not found in CSV', error_message)
    
    def test_build_from_csv_empty_graphs(self):
        """Test build_from_csv() handles empty GraphSpec gracefully."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec
        
        # Configure mock to return empty spec
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = []
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock internal methods to reach the validation logic
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs'), \
             unittest.mock.patch.object(self.service, '_connect_nodes_from_specs'), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes'):
            
            # Execute and verify ValueError
            with self.assertRaises(ValueError) as context:
                self.service.build_from_csv(Path('empty.csv'))
            
            self.assertIn('No graphs found', str(context.exception))
            self.assertIn('empty.csv', str(context.exception))
    
    def test_edge_connection_conflict_error(self):
        """Test InvalidEdgeDefinitionError for conflicting edge definitions."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        from agentmap.exceptions.graph_exceptions import InvalidEdgeDefinitionError
        
        # Create a NodeSpec with conflicting edge definitions
        conflicting_node_spec = Mock(spec=NodeSpec)
        conflicting_node_spec.name = 'conflicting_node'
        conflicting_node_spec.graph_name = 'test_graph'
        conflicting_node_spec.edge = 'next_node'  # Direct edge
        conflicting_node_spec.success_next = 'success_node'  # AND success edge (conflict!)
        conflicting_node_spec.failure_next = None
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['test_graph']
        mock_graph_spec.get_nodes_for_graph.return_value = [conflicting_node_spec]
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock nodes creation but let connect_nodes_from_specs run real logic
        nodes_dict = {'conflicting_node': Mock(), 'next_node': Mock(), 'success_node': Mock()}
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value=nodes_dict), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes'):
            
            # Execute and verify InvalidEdgeDefinitionError
            with self.assertRaises(InvalidEdgeDefinitionError) as context:
                self.service.build_from_graph_spec(mock_graph_spec)
            
            error_message = str(context.exception)
            self.assertIn('conflicting_node', error_message)
            self.assertIn('both Edge and Success/Failure defined', error_message)
    
    def test_edge_connection_target_not_found_error(self):
        """Test ValueError when edge target node doesn't exist."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        
        # Create a NodeSpec with edge pointing to non-existent node
        node_spec_with_invalid_edge = Mock(spec=NodeSpec)
        node_spec_with_invalid_edge.name = 'source_node'
        node_spec_with_invalid_edge.graph_name = 'test_graph'
        node_spec_with_invalid_edge.edge = 'nonexistent_target'  # Points to non-existent node
        node_spec_with_invalid_edge.success_next = None
        node_spec_with_invalid_edge.failure_next = None
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['test_graph']
        mock_graph_spec.get_nodes_for_graph.return_value = [node_spec_with_invalid_edge]
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock nodes creation but target node doesn't exist in nodes_dict
        nodes_dict = {'source_node': Mock()}  # Missing 'nonexistent_target'
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value=nodes_dict), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes'):
            
            # Execute and verify ValueError for missing edge target
            with self.assertRaises(ValueError) as context:
                self.service.build_from_graph_spec(mock_graph_spec)
            
            error_message = str(context.exception)
            self.assertIn('nonexistent_target', error_message)
            self.assertIn('not defined as a node', error_message)
            self.assertIn('test_graph', error_message)
    
    def test_build_from_config_not_implemented(self):
        """Test build_from_config() raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as context:
            self.service.build_from_config({'test': 'config'})
        
        self.assertIn('build_from_config not yet implemented', str(context.exception))
    
    def test_service_initialization_with_missing_dependencies(self):
        """Test service handles missing dependencies gracefully."""
        from agentmap.services.graph_definition_service import GraphDefinitionService
        
        # Test missing logging service - will raise AttributeError when trying to call get_class_logger on None
        with self.assertRaises(AttributeError) as context:
            GraphDefinitionService(
                logging_service=None,
                app_config_service=self.mock_app_config_service,
                csv_parser=self.mock_csv_parser_service,
                graph_factory=self.mock_graph_factory
            )
        self.assertIn("'NoneType' object has no attribute 'get_class_logger'", str(context.exception))
        
        # Test missing config service - initialization succeeds since config is not used in current implementation
        service_with_none_config = GraphDefinitionService(
            logging_service=self.mock_logging_service,
            app_config_service=None,
            csv_parser=self.mock_csv_parser_service,
            graph_factory=self.mock_graph_factory
        )
        # Verify service was created successfully (config is stored but not used)
        self.assertIsNone(service_with_none_config.config)
        self.assertIsNotNone(service_with_none_config.logger)
        self.assertIsNotNone(service_with_none_config.csv_parser)
        
        # Test missing CSV parser service - initialization succeeds but methods will fail when parser is used
        service_with_none_parser = GraphDefinitionService(
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config_service,
            csv_parser=None,
            graph_factory=self.mock_graph_factory
        )
        # Verify service was created but csv_parser is None
        self.assertIsNone(service_with_none_parser.csv_parser)
        
        # Test that CSV methods fail when csv_parser is None
        with self.assertRaises(AttributeError) as context:
            service_with_none_parser.build_from_csv(Path('test.csv'))
        self.assertIn("'NoneType' object has no attribute", str(context.exception))
        
        with self.assertRaises(AttributeError) as context:
            service_with_none_parser.validate_csv_before_building(Path('test.csv'))
        self.assertIn("'NoneType' object has no attribute", str(context.exception))
    
    def test_service_initialization_with_completely_missing_arguments(self):
        """Test service handles completely missing arguments (TypeError)."""
        from agentmap.services.graph_definition_service import GraphDefinitionService
        
        # Test with no arguments at all - should raise TypeError for missing required arguments
        with self.assertRaises(TypeError) as context:
            GraphDefinitionService()
        
        # Should mention missing required positional arguments
        error_msg = str(context.exception)
        self.assertTrue(
            "missing" in error_msg and "required" in error_msg,
            f"Expected error about missing required arguments, got: {error_msg}"
        )
    
    def test_build_all_from_csv_empty_graphs(self):
        """Test build_all_from_csv() handles empty GraphSpec."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec
        
        # Configure mock to return empty spec
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = []
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Execute test
        result = self.service.build_all_from_csv(Path('empty.csv'))
        
        # Should return empty dictionary for empty GraphSpec
        self.assertEqual(result, {})
        
        # Verify CSV parser was called
        self.mock_csv_parser_service.parse_csv_to_graph_spec.assert_called_once_with(Path('empty.csv'))
    
    def test_build_from_csv_malformed_graph_spec(self):
        """Test build_from_csv() handles malformed GraphSpec objects."""
        import unittest.mock
        
        # Configure CSV parser to return malformed spec (missing required methods)
        malformed_spec = Mock()
        # Deliberately missing get_graph_names method to simulate malformed object
        malformed_spec.get_graph_names.side_effect = AttributeError('Malformed GraphSpec')
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = malformed_spec
        
        # Execute and verify AttributeError propagation
        with self.assertRaises(AttributeError) as context:
            self.service.build_from_csv(Path('malformed.csv'))
        
        self.assertIn('Malformed GraphSpec', str(context.exception))
    
    def test_validate_csv_before_building_malformed_validation_result(self):
        """Test validate_csv_before_building() handles malformed ValidationResult."""
        # Test scenario 1: errors is None but is_valid is False (so it tries to iterate over None)
        malformed_result_errors_none = Mock()
        malformed_result_errors_none.is_valid = False  # This will make it try to iterate over errors
        malformed_result_errors_none.errors = None  # Should be list, will cause TypeError
        malformed_result_errors_none.warnings = []
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.validate_csv_structure.side_effect = None
        self.mock_csv_parser_service.validate_csv_structure.return_value = malformed_result_errors_none
        
        # Execute and verify it handles None errors list gracefully
        with self.assertRaises(TypeError):  # Should fail when trying to iterate None
            self.service.validate_csv_before_building(Path('malformed.csv'))
        
        # Test scenario 2: warnings is None (always gets iterated)
        malformed_result_warnings_none = Mock()
        malformed_result_warnings_none.is_valid = True  # Valid, so no errors iteration
        malformed_result_warnings_none.errors = []
        malformed_result_warnings_none.warnings = None  # Should be list, will cause TypeError
        
        # Reset and set new return value
        self.mock_csv_parser_service.validate_csv_structure.return_value = malformed_result_warnings_none
        
        # Execute and verify it handles None warnings list
        with self.assertRaises(TypeError):  # Should fail when trying to iterate None warnings
            self.service.validate_csv_before_building(Path('malformed2.csv'))
    
    def test_build_from_csv_success_edge_target_not_found(self):
        """Test ValueError when success_next target node doesn't exist."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        
        # Create a NodeSpec with success_next pointing to non-existent node
        node_spec_with_invalid_success = Mock(spec=NodeSpec)
        node_spec_with_invalid_success.name = 'source_node'
        node_spec_with_invalid_success.graph_name = 'test_graph'
        node_spec_with_invalid_success.edge = None
        node_spec_with_invalid_success.success_next = 'nonexistent_success_target'
        node_spec_with_invalid_success.failure_next = None
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['test_graph']
        mock_graph_spec.get_nodes_for_graph.return_value = [node_spec_with_invalid_success]
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock nodes creation but success target doesn't exist
        nodes_dict = {'source_node': Mock()}  # Missing 'nonexistent_success_target'
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value=nodes_dict), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes'):
            
            # Execute and verify ValueError for missing success target
            with self.assertRaises(ValueError) as context:
                self.service.build_from_graph_spec(mock_graph_spec)
            
            error_message = str(context.exception)
            self.assertIn('nonexistent_success_target', error_message)
            self.assertIn('not defined as a node', error_message)
    
    def test_build_from_csv_failure_edge_target_not_found(self):
        """Test ValueError when failure_next target node doesn't exist."""
        import unittest.mock
        from agentmap.models.graph_spec import GraphSpec, NodeSpec
        
        # Create a NodeSpec with failure_next pointing to non-existent node
        node_spec_with_invalid_failure = Mock(spec=NodeSpec)
        node_spec_with_invalid_failure.name = 'source_node'
        node_spec_with_invalid_failure.graph_name = 'test_graph'
        node_spec_with_invalid_failure.edge = None
        node_spec_with_invalid_failure.success_next = None
        node_spec_with_invalid_failure.failure_next = 'nonexistent_failure_target'
        
        mock_graph_spec = Mock(spec=GraphSpec)
        mock_graph_spec.get_graph_names.return_value = ['test_graph']
        mock_graph_spec.get_nodes_for_graph.return_value = [node_spec_with_invalid_failure]
        
        # Reset side_effect and set return_value
        self.mock_csv_parser_service.parse_csv_to_graph_spec.side_effect = None
        self.mock_csv_parser_service.parse_csv_to_graph_spec.return_value = mock_graph_spec
        
        # Mock nodes creation but failure target doesn't exist
        nodes_dict = {'source_node': Mock()}  # Missing 'nonexistent_failure_target'
        
        with unittest.mock.patch.object(self.service, '_create_nodes_from_specs', return_value=nodes_dict), \
             unittest.mock.patch.object(self.service.graph_factory, 'create_graph_from_nodes'):
            
            # Execute and verify ValueError for missing failure target
            with self.assertRaises(ValueError) as context:
                self.service.build_from_graph_spec(mock_graph_spec)
            
            error_message = str(context.exception)
            self.assertIn('nonexistent_failure_target', error_message)
            self.assertIn('not defined as a node', error_message)


if __name__ == '__main__':
    unittest.main()
