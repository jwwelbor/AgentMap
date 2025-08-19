"""
Tests for bundle-based flow in GraphRunnerService.

Tests for the new metadata bundle functionality that replaces compilation-based flow.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any

from agentmap.services.graph.graph_runner_service import GraphRunnerService, RunOptions
from agentmap.models.execution_result import ExecutionResult
from agentmap.models.graph_bundle import GraphBundle
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphRunnerServiceBundleFlow(unittest.TestCase):
    """Tests for bundle-based flow in GraphRunnerService."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create all mock services using MockServiceFactory
        self.mock_graph_definition_service = MockServiceFactory.create_mock_graph_definition_service()
        self.mock_graph_execution_service = MockServiceFactory.create_mock_graph_execution_service()
        self.mock_compilation_service = MockServiceFactory.create_mock_compilation_service()
        self.mock_graph_bundle_service = MockServiceFactory.create_mock_graph_bundle_service()
        self.mock_agent_factory_service = Mock()
        self.mock_llm_service = MockServiceFactory.create_mock_llm_service()
        self.mock_storage_service_manager = MockServiceFactory.create_mock_storage_service_manager()
        self.mock_node_registry_service = MockServiceFactory.create_mock_node_registry_service()
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "autocompile": False,
            "csv_path": "graphs/test.csv",
            "compiled_graphs_path": "compiled",
            "metadata_bundles_path": "bundles",
            "execution": {"track_execution": True},
            "bypass_bundling": True  # Enable bundle-based flow for tests
        })
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_execution_policy_service = MockServiceFactory.create_mock_execution_policy_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        self.mock_dependency_checker_service = MockServiceFactory.create_mock_dependency_checker_service()
        self.mock_graph_assembly_service = MockServiceFactory.create_mock_graph_assembly_service()
        
        # Add metadata_bundles_path method to config service
        self.mock_app_config_service.get_metadata_bundles_path = Mock(return_value=Path("bundles"))
        
        # Initialize GraphRunnerService with all mocked dependencies
        self.service = GraphRunnerService(
            graph_definition_service=self.mock_graph_definition_service,
            graph_execution_service=self.mock_graph_execution_service,
            compilation_service=self.mock_compilation_service,
            graph_bundle_service=self.mock_graph_bundle_service,
            agent_factory_service=self.mock_agent_factory_service,
            llm_service=self.mock_llm_service,
            storage_service_manager=self.mock_storage_service_manager,
            node_registry_service=self.mock_node_registry_service,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config_service,
            execution_tracking_service=self.mock_execution_tracking_service,
            execution_policy_service=self.mock_execution_policy_service,
            state_adapter_service=self.mock_state_adapter_service,
            dependency_checker_service=self.mock_dependency_checker_service,
            graph_assembly_service=self.mock_graph_assembly_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger

    # =============================================================================
    # Bundle Cache Detection Tests
    # =============================================================================
    
    def test_find_metadata_bundle_exists(self):
        """Test _find_metadata_bundle when bundle exists."""
        # Setup test data
        graph_name = "test_graph"
        bundle_path = Path("bundles/test_graph.json")
        
        # Mock path exists check
        with patch('pathlib.Path.exists', return_value=True):
            result = self.service._find_metadata_bundle(graph_name)
            
            self.assertEqual(result, bundle_path)
            self.mock_logger.debug.assert_any_call(
                f"[GraphRunnerService] Found metadata bundle: {bundle_path}"
            )
    
    def test_find_metadata_bundle_not_exists(self):
        """Test _find_metadata_bundle when bundle doesn't exist."""
        # Setup test data  
        graph_name = "test_graph"
        
        # Mock path exists check
        with patch('pathlib.Path.exists', return_value=False):
            result = self.service._find_metadata_bundle(graph_name)
            
            self.assertIsNone(result)
            self.mock_logger.debug.assert_any_call(
                f"[GraphRunnerService] No metadata bundle found for: {graph_name}"
            )

    # =============================================================================
    # Bundle Creation Tests
    # =============================================================================
    
    def test_create_and_cache_bundle_success(self):
        """Test _create_and_cache_bundle successful creation."""
        # Setup test data
        graph_name = "test_graph"
        csv_path = Path("graphs/test.csv")
        
        # Create mock bundle
        mock_bundle = Mock(spec=GraphBundle)
        mock_bundle.is_metadata_only = True
        mock_bundle.graph_name = graph_name
        
        # Configure bundle service
        self.mock_graph_bundle_service.create_metadata_bundle.return_value = mock_bundle
        
        # Execute test
        result = self.service._create_and_cache_bundle(graph_name, csv_path)
        
        # Verify result
        self.assertEqual(result, mock_bundle)
        
        # Verify bundle service was called correctly
        self.mock_graph_bundle_service.create_metadata_bundle.assert_called_once_with(
            csv_path, graph_name
        )
        
        # Verify bundle was saved
        expected_path = Path("bundles") / f"{graph_name}.json"
        self.mock_graph_bundle_service.save_bundle.assert_called_once_with(
            mock_bundle, expected_path
        )
        
        # Verify logging
        self.mock_logger.debug.assert_any_call(
            f"[GraphRunnerService] Creating metadata bundle for: {graph_name}"
        )
        self.mock_logger.info.assert_any_call(
            f"[GraphRunnerService] ✅ Created and cached metadata bundle: {graph_name}"
        )
    
    def test_create_and_cache_bundle_failure(self):
        """Test _create_and_cache_bundle when creation fails."""
        # Setup test data
        graph_name = "test_graph" 
        csv_path = Path("graphs/test.csv")
        
        # Configure bundle service to raise exception
        self.mock_graph_bundle_service.create_metadata_bundle.side_effect = Exception("Creation failed")
        
        # Execute test
        result = self.service._create_and_cache_bundle(graph_name, csv_path)
        
        # Verify result
        self.assertIsNone(result)
        
        # Verify error logging
        self.mock_logger.error.assert_any_call(
            f"[GraphRunnerService] Failed to create metadata bundle for {graph_name}: Creation failed"
        )

    # =============================================================================
    # Bundle Validation Tests
    # =============================================================================
    
    def test_validate_bundle_against_csv_valid(self):
        """Test bundle validation when bundle is valid."""
        # Setup test data
        mock_bundle = Mock(spec=GraphBundle)
        csv_path = Path("graphs/test.csv")
        csv_content = "node,agent_type,prompt\ntest,DefaultAgent,Hello"
        
        # Configure validation
        self.mock_graph_bundle_service.validate_bundle.return_value = True
        
        # Mock file reading
        with patch('pathlib.Path.read_text', return_value=csv_content):
            result = self.service._validate_bundle_against_csv(mock_bundle, csv_path)
            
            # Verify result
            self.assertTrue(result)
            
            # Verify bundle service was called
            self.mock_graph_bundle_service.validate_bundle.assert_called_once_with(
                mock_bundle, csv_content
            )
    
    def test_validate_bundle_against_csv_invalid(self):
        """Test bundle validation when bundle is invalid."""
        # Setup test data
        mock_bundle = Mock(spec=GraphBundle)
        csv_path = Path("graphs/test.csv")
        csv_content = "node,agent_type,prompt\ntest,DefaultAgent,Hello"
        
        # Configure validation
        self.mock_graph_bundle_service.validate_bundle.return_value = False
        
        # Mock file reading
        with patch('pathlib.Path.read_text', return_value=csv_content):
            result = self.service._validate_bundle_against_csv(mock_bundle, csv_path)
            
            # Verify result
            self.assertFalse(result)

    # =============================================================================
    # Bundle-based Resolution Tests
    # =============================================================================
    
    def test_resolve_graph_with_valid_cached_bundle(self):
        """Test _resolve_graph_for_execution with valid cached bundle."""
        # Setup test data
        graph_name = "test_graph"
        options = RunOptions(csv_path=Path("graphs/test.csv"))
        
        # Create mock bundle
        mock_bundle = Mock(spec=GraphBundle)
        mock_bundle.is_metadata_only = True
        
        # Configure bundle finding and validation
        bundle_path = Path("bundles/test_graph.json")
        
        # Manually mock the _find_metadata_bundle method to return the expected path
        with patch.object(self.service, '_find_metadata_bundle', return_value=bundle_path):
            # Configure the bundle service to return our mock bundle
            self.mock_graph_bundle_service.load_bundle.return_value = mock_bundle
            
            # Mock validation to return True
            with patch.object(self.service, '_validate_bundle_against_csv', return_value=True):
                result = self.service._resolve_graph_for_execution(graph_name, options)
                
                # Verify result
                self.assertEqual(result["type"], "bundle")
                # Check that the bundle in the result is our mock bundle
                self.assertIs(result["bundle"], mock_bundle)
                
                # Verify bundle was loaded
                self.mock_graph_bundle_service.load_bundle.assert_called_once_with(bundle_path)
                
                # Verify logging
                self.mock_logger.debug.assert_any_call(
                    f"[GraphRunnerService] Found valid cached metadata bundle: {bundle_path}"
                )
    
    def test_resolve_graph_with_invalid_cached_bundle_creates_new(self):
        """Test _resolve_graph_for_execution with invalid cached bundle - creates new."""
        # Setup test data
        graph_name = "test_graph"
        options = RunOptions(csv_path=Path("graphs/test.csv"))
        
        # Create old and new mock bundles
        old_bundle = Mock(spec=GraphBundle)
        new_bundle = Mock(spec=GraphBundle)
        new_bundle.is_metadata_only = True
        
        # Configure bundle finding and validation
        bundle_path = Path("bundles/test_graph.json")
        with patch('pathlib.Path.exists', return_value=True):
            self.mock_graph_bundle_service.load_bundle.return_value = old_bundle
            
            # Mock validation to return False (invalid), then creation to succeed
            with patch.object(self.service, '_validate_bundle_against_csv', return_value=False):
                with patch.object(self.service, '_create_and_cache_bundle', return_value=new_bundle):
                    result = self.service._resolve_graph_for_execution(graph_name, options)
                    
                    # Verify result uses new bundle
                    self.assertEqual(result["type"], "bundle")
                    self.assertEqual(result["bundle"], new_bundle)
                    
                    # Verify warning about invalid bundle
                    self.mock_logger.warning.assert_any_call(
                        f"[GraphRunnerService] Cached bundle invalid, creating new bundle: {graph_name}"
                    )
    
    def test_resolve_graph_no_cached_bundle_creates_new(self):
        """Test _resolve_graph_for_execution with no cached bundle - creates new."""
        # Setup test data
        graph_name = "test_graph"
        options = RunOptions(csv_path=Path("graphs/test.csv"))
        
        # Create new mock bundle
        new_bundle = Mock(spec=GraphBundle)
        new_bundle.is_metadata_only = True
        
        # Configure no existing bundle
        with patch('pathlib.Path.exists', return_value=False):
            with patch.object(self.service, '_create_and_cache_bundle', return_value=new_bundle):
                result = self.service._resolve_graph_for_execution(graph_name, options)
                
                # Verify result
                self.assertEqual(result["type"], "bundle")
                self.assertEqual(result["bundle"], new_bundle)

    # =============================================================================
    # Main Execution Flow Tests 
    # =============================================================================
    
    def test_run_graph_with_bundle_flow(self):
        """Test run_graph using bundle-based flow."""
        # Setup test data
        graph_name = "test_graph"
        options = RunOptions()
        initial_state = {"key": "value"}
        
        # Create mock bundle and execution result
        mock_bundle = Mock(spec=GraphBundle)
        mock_bundle.is_metadata_only = True
        
        mock_execution_result = ExecutionResult(
            graph_name=graph_name,
            success=True,
            final_state={"key": "updated_value"},
            execution_summary=None,
            total_duration=1.0,
            compiled_from="bundle",
            error=None
        )
        
        # Configure resolution to return bundle
        with patch.object(self.service, '_resolve_graph_for_execution') as mock_resolve:
            mock_resolve.return_value = {"type": "bundle", "bundle": mock_bundle}
            
            # Configure execution service
            self.mock_graph_execution_service.execute_with_bundle.return_value = mock_execution_result
            
            # Execute test
            result = self.service.run_graph(graph_name, options)
            
            # Verify result
            self.assertEqual(result, mock_execution_result)
            
            # Verify execution service was called with bundle
            self.mock_graph_execution_service.execute_with_bundle.assert_called_once_with(
                bundle=mock_bundle,
                state={}  # default empty state
            )
            
            # Verify resolution was called
            mock_resolve.assert_called_once_with(graph_name, options)
            
            # Verify logging
            self.mock_logger.debug.assert_any_call(
                "[GraphRunnerService] Delegating bundle graph execution"
            )

    # =============================================================================
    # Backwards Compatibility Tests
    # =============================================================================
    
    
    def test_backwards_compatibility_definition_execution_still_works(self):
        """Test that definition-based execution still works."""
        # Setup test data
        graph_name = "test_graph"
        options = RunOptions()
        
        mock_graph_def = {"node1": Mock()}
        mock_execution_result = ExecutionResult(
            graph_name=graph_name,
            success=True,
            final_state={"key": "updated_value"},
            execution_summary=None,
            total_duration=1.0,
            compiled_from="memory",
            error=None
        )
        
        # Disable bundle-based flow and ensure no compiled graphs
        def mock_get_value(key, default=None):
            if key == "bypass_bundling":
                return False  # Disable bundle flow
            elif key == "autocompile":
                return False
            else:
                return default
        self.mock_app_config_service.get_value.side_effect = mock_get_value
        
        # Configure no compiled graphs and load definition
        with patch.object(self.service, '_find_compiled_graph', return_value=None):
            with patch.object(self.service, '_load_graph_definition_for_execution', return_value=(mock_graph_def, graph_name)):
                # Configure execution service
                self.mock_graph_execution_service.execute_from_definition.return_value = mock_execution_result
                
                # Execute test
                result = self.service.run_graph(graph_name, options)
                
                # Verify result
                self.assertEqual(result, mock_execution_result)
                
                # Verify execution service was called with definition
                self.mock_graph_execution_service.execute_from_definition.assert_called_once_with(
                    graph_def=mock_graph_def,
                    state={},  # default empty state
                    graph_name=graph_name
                )


    # =============================================================================
    # Error Handling Tests
    # =============================================================================
    
    def test_bundle_creation_failure_fallback_to_definition(self):
        """Test fallback to definition execution when bundle creation fails."""
        # Setup test data
        graph_name = "test_graph"
        options = RunOptions(csv_path=Path("graphs/test.csv"))
        
        mock_graph_def = {"node1": Mock()}
        
        # Configure no cached bundle and failed creation
        with patch('pathlib.Path.exists', return_value=False):
            with patch.object(self.service, '_create_and_cache_bundle', return_value=None):
                with patch.object(self.service, '_load_graph_definition_for_execution', return_value=(mock_graph_def, graph_name)):
                    result = self.service._resolve_graph_for_execution(graph_name, options)
                    
                    # Verify fallback to definition
                    self.assertEqual(result["type"], "definition")
                    self.assertEqual(result["graph_def"], mock_graph_def)
                    
                    # Verify warning about fallback
                    self.mock_logger.warning.assert_any_call(
                        f"[GraphRunnerService] Bundle creation failed, falling back to definition execution: {graph_name}"
                    )


if __name__ == '__main__':
    unittest.main()
