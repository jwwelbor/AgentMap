"""
Unit tests for GraphRegistryService composite key functionality.

Tests validate the GraphRegistryService updated composite key implementation
using (csv_hash, graph_name) for bundle lookups while maintaining backward compatibility.
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from agentmap.services.graph.graph_registry_service import GraphRegistryService
from tests.utils.mock_service_factory import MockServiceFactory
from tests.utils.path_mocking_utils import PathOperationsMocker, mock_path_exists


class TestGraphRegistryService(unittest.TestCase):
    """Unit tests for GraphRegistryService composite key functionality."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock dependencies using MockServiceFactory
        self.mock_system_storage_manager = self._create_mock_system_storage_manager()
        self.mock_app_config = MockServiceFactory.create_mock_app_config_service()
        self.mock_logging = MockServiceFactory.create_mock_logging_service()
        
        # Configure mock behaviors
        cache_path = Path("/tmp/cache")
        self.mock_app_config.get_cache_path.return_value = cache_path
        
        # Create service instance
        self.service = GraphRegistryService(
            system_storage_manager=self.mock_system_storage_manager,
            app_config_service=self.mock_app_config,
            logging_service=self.mock_logging
        )
        
        # Get logger for verification
        self.logger = self.service.logger
        
        # Test data
        self.test_csv_hash = "abc123def456" + "0" * 52  # 64 char hash
        self.test_graph_name = "test_graph"
        self.test_bundle_path = Path("/tmp/test_bundle.pkl")
        self.test_csv_path = Path("/tmp/test.csv")
        
        # Note: Path mocking will be handled per-test using PathOperationsMocker

    def _create_mock_system_storage_manager(self):
        """Create a mock SystemStorageManager that provides JSON storage."""
        mock_service = Mock()
        
        def get_json_storage(namespace=None):
            mock_json_service = Mock()
            mock_json_service.read.return_value = None  # Default: no existing data
            mock_json_service.write.return_value = Mock(success=True, error=None)
            mock_json_service.delete.return_value = Mock(success=True, error=None)
            mock_json_service.exists.return_value = False
            return mock_json_service
        
        def get_file_storage(namespace=None):
            mock_file_service = Mock()
            mock_file_service.read.return_value = Mock(success=True, data=b"", error=None)
            mock_file_service.write.return_value = Mock(success=True, error=None)
            mock_file_service.delete.return_value = Mock(success=True, error=None)
            mock_file_service.exists.return_value = False
            return mock_file_service
        
        mock_service.get_json_storage.side_effect = get_json_storage
        mock_service.get_file_storage.side_effect = get_file_storage
        
        return mock_service
    
    # =============================================================================
    # 1. Composite Key Registration Tests
    # =============================================================================
    
    def test_register_creates_composite_key_structure(self):
        """Test that register() creates proper nested structure {csv_hash: {graph_name: entry}}."""
        with PathOperationsMocker() as path_mock:
            path_mock.set_exists(self.test_bundle_path, True)
            
            with patch('pathlib.Path.stat') as mock_stat:
                stat_result = Mock()
                stat_result.st_size = 1024
                mock_stat.return_value = stat_result
                
                # Register bundle
                self.service.register(
                    csv_hash=self.test_csv_hash,
                    graph_name=self.test_graph_name,
                    bundle_path=self.test_bundle_path,
                    csv_path=self.test_csv_path
                )
        
        # Verify nested structure was created
        self.assertIn(self.test_csv_hash, self.service._registry_cache)
        hash_entry = self.service._registry_cache[self.test_csv_hash]
        
        # Should be nested structure, not legacy direct entry
        self.assertNotIn("bundle_path", hash_entry)
        self.assertIn(self.test_graph_name, hash_entry)
        
        # Verify graph entry has proper structure
        graph_entry = hash_entry[self.test_graph_name]
        self.assertEqual(graph_entry["graph_name"], self.test_graph_name)
        self.assertEqual(graph_entry["csv_hash"], self.test_csv_hash)
        self.assertEqual(graph_entry["bundle_path"], str(self.test_bundle_path))
        self.assertEqual(graph_entry["csv_path"], str(self.test_csv_path))
        self.assertIn("created_at", graph_entry)
        self.assertIn("bundle_size", graph_entry)
    
    def test_register_multiple_graphs_same_csv(self):
        """Test registering multiple graphs from the same CSV creates separate entries."""
        bundle1_path = Path("/tmp/bundle1.pkl")
        bundle2_path = Path("/tmp/bundle2.pkl")
        
        with PathOperationsMocker() as path_mock:
            path_mock.set_exists(bundle1_path, True)
            path_mock.set_exists(bundle2_path, True)
            
            with patch('pathlib.Path.stat') as mock_stat:
                stat_result = Mock()
                stat_result.st_size = 1024
                mock_stat.return_value = stat_result
                
                # Register first graph
                self.service.register(
                    csv_hash=self.test_csv_hash,
                    graph_name="graph1",
                    bundle_path=bundle1_path,
                    csv_path=self.test_csv_path
                )
                
                # Register second graph for same CSV
                self.service.register(
                    csv_hash=self.test_csv_hash,
                    graph_name="graph2",
                    bundle_path=bundle2_path,
                    csv_path=self.test_csv_path
                )
        
        # Verify both graphs are stored under same csv_hash
        hash_entry = self.service._registry_cache[self.test_csv_hash]
        self.assertIn("graph1", hash_entry)
        self.assertIn("graph2", hash_entry)
        
        # Verify separate bundle paths (normalize for cross-platform compatibility)
        self.assertEqual(self._normalize_path(hash_entry["graph1"]["bundle_path"]), "/tmp/bundle1.pkl")
        self.assertEqual(self._normalize_path(hash_entry["graph2"]["bundle_path"]), "/tmp/bundle2.pkl")
    
    # =============================================================================
    # 2. Composite Key Lookup Tests
    # =============================================================================
    
    def test_find_bundle_with_graph_name(self):
        """Test find_bundle() with specific graph_name returns correct bundle."""
        # Register test bundle
        self._register_test_bundle()
        
        # Mock bundle file exists
        with patch.object(Path, 'exists', return_value=True):
            # Find bundle with specific graph name
            result = self.service.find_bundle(self.test_csv_hash, self.test_graph_name)
        
        self.assertIsNotNone(result)
        self.assertEqual(result, self.test_bundle_path)
    
    def test_find_bundle_without_graph_name_returns_first_available(self):
        """Test find_bundle() without graph_name returns first available bundle."""
        # Register multiple graphs for same CSV
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.stat') as mock_stat:
                stat_result = Mock()
                stat_result.st_size = 1024
                mock_stat.return_value = stat_result
                
                self.service.register(self.test_csv_hash, "graph_z", Path("/tmp/z.pkl"), self.test_csv_path)
                self.service.register(self.test_csv_hash, "graph_a", Path("/tmp/a.pkl"), self.test_csv_path)
        
        # Mock bundle files exist
        with patch.object(Path, 'exists', return_value=True):
            # Find bundle without specifying graph name
            result = self.service.find_bundle(self.test_csv_hash)
        
        # Should return first available (order may vary based on dict implementation)
        self.assertIsNotNone(result)
        # Normalize path separators for cross-platform compatibility
        self.assertIn(self._normalize_path(result), ["/tmp/z.pkl", "/tmp/a.pkl"])
    
    def test_find_bundle_nonexistent_graph_returns_none(self):
        """Test find_bundle() with nonexistent graph_name returns None."""
        # Register test bundle
        self._register_test_bundle()
        
        # Try to find bundle with wrong graph name
        result = self.service.find_bundle(self.test_csv_hash, "nonexistent_graph")
        
        self.assertIsNone(result)
    
    def test_find_bundle_nonexistent_csv_hash_returns_none(self):
        """Test find_bundle() with nonexistent csv_hash returns None."""
        result = self.service.find_bundle("nonexistent_hash", self.test_graph_name)
        self.assertIsNone(result)
    
    # =============================================================================
    # 4. Backward Compatibility Tests
    # =============================================================================
    
    def test_backward_compatibility_find_without_graph_name(self):
        """Test that find_bundle() without graph_name still works for single-graph CSVs."""
        # Register single graph
        self._register_test_bundle()
        
        # Mock bundle file exists
        with patch.object(Path, 'exists', return_value=True):
            # Find bundle without specifying graph name (legacy usage)
            result = self.service.find_bundle(self.test_csv_hash)
        
        # Should find the bundle even without graph name
        self.assertIsNotNone(result)
        self.assertEqual(result, self.test_bundle_path)
    
    def test_legacy_lookup_returns_none_for_graph_specific_request(self):
        """Test that legacy structure returns None when specific graph requested."""
        # Create legacy structure
        legacy_entry = {
            "graph_name": "different_graph",
            "bundle_path": str(self.test_bundle_path),
            "csv_hash": self.test_csv_hash
        }
        self.service._registry_cache[self.test_csv_hash] = legacy_entry
        
        # Mock bundle file exists
        with patch.object(Path, 'exists', return_value=True):
            # Request different graph name - should migrate first then look up
            result = self.service.find_bundle(self.test_csv_hash, self.test_graph_name)
        
        # Should return None since requested graph doesn't exist
        self.assertIsNone(result)
    
    # =============================================================================
    # 5. Registry Management Tests
    # =============================================================================
    
    def test_remove_entry_specific_graph(self):
        """Test removing specific graph entry from composite key registry."""
        # Register multiple graphs
        self._register_multiple_test_graphs()
        
        # Remove specific graph
        result = self.service.remove_entry(self.test_csv_hash, "graph1")
        
        self.assertTrue(result)
        
        # Verify only specific graph removed
        hash_entry = self.service._registry_cache[self.test_csv_hash]
        self.assertNotIn("graph1", hash_entry)
        self.assertIn("graph2", hash_entry)
    
    def test_remove_entry_all_graphs_for_csv(self):
        """Test removing all graphs for a CSV hash."""
        # Register multiple graphs
        self._register_multiple_test_graphs()
        
        # Remove all graphs for CSV
        result = self.service.remove_entry(self.test_csv_hash)
        
        self.assertTrue(result)
        
        # Verify entire CSV entry removed
        self.assertNotIn(self.test_csv_hash, self.service._registry_cache)
    
    def test_remove_last_graph_removes_csv_entry(self):
        """Test that removing the last graph for a CSV removes the entire CSV entry."""
        # Register single graph
        self._register_test_bundle()
        
        # Remove the only graph
        result = self.service.remove_entry(self.test_csv_hash, self.test_graph_name)
        
        self.assertTrue(result)
        
        # Verify entire CSV entry removed
        self.assertNotIn(self.test_csv_hash, self.service._registry_cache)
    
    def test_get_entry_info_returns_nested_structure(self):
        """Test get_entry_info() returns the specific graph entry for composite keys."""
        # Register multiple graphs
        self._register_multiple_test_graphs()
        
        # Get entry info for specific graph
        entry_info = self.service.get_entry_info(self.test_csv_hash, "graph1")
        
        self.assertIsNotNone(entry_info)
        self.assertEqual(entry_info["graph_name"], "graph1")
        
        # Verify separate lookup
        entry_info_2 = self.service.get_entry_info(self.test_csv_hash, "graph2")
        self.assertIsNotNone(entry_info_2)
        self.assertEqual(entry_info_2["graph_name"], "graph2")
    
    # =============================================================================
    # 6. Error Handling Tests
    # =============================================================================
    
    def test_find_bundle_missing_file_logs_warning(self):
        """Test find_bundle() logs warning when bundle file is missing."""
        # Register bundle
        self._register_test_bundle()
        
        # Mock bundle file doesn't exist
        with patch.object(Path, 'exists', return_value=False):
            result = self.service.find_bundle(self.test_csv_hash, self.test_graph_name)
        
        self.assertIsNone(result)
        
        # Verify warning was logged
        warning_calls = [call for call in self.logger.calls if call[0] == "warning"]
        self.assertTrue(any("Bundle file missing" in call[1] for call in warning_calls))
    
    def test_compute_hash_nonexistent_file_raises_error(self):
        """Test compute_hash() raises FileNotFoundError for nonexistent file."""
        nonexistent_path = Path("/tmp/nonexistent.csv")
        
        with self.assertRaises(FileNotFoundError):
            GraphRegistryService.compute_hash(nonexistent_path)
    
    def test_register_invalid_parameters_raises_error(self):
        """Test register() validates parameters and raises appropriate errors."""
        # Test invalid CSV hash
        with self.assertRaises(ValueError):
            self.service.register("short_hash", self.test_graph_name, self.test_bundle_path, self.test_csv_path)
        
        # Test empty graph name
        with self.assertRaises(ValueError):
            self.service.register(self.test_csv_hash, "", self.test_bundle_path, self.test_csv_path)
        
        # Test nonexistent bundle file
        with self.assertRaises(ValueError):
            self.service.register(self.test_csv_hash, self.test_graph_name, Path("/tmp/nonexistent.pkl"), self.test_csv_path)
    
    # =============================================================================
    # 7. Static Method Tests
    # =============================================================================
    
    def test_compute_hash_returns_valid_sha256(self):
        """Test compute_hash() returns valid 64-character SHA-256 hash."""
        test_csv_path = Path("/tmp/test.csv")
        test_content = "name,graph,agent_type\nnode1,test,default\n"
        
        # Mock file operations
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(test_content.encode())):
                result = GraphRegistryService.compute_hash(test_csv_path)
        
        # Verify hash format
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in result))
    
    # =============================================================================
    # Helper Methods
    # =============================================================================
    
    def _normalize_path(self, path):
        """Helper to normalize path separators for cross-platform compatibility."""
        return str(path).replace('\\', '/')
    
    def _register_test_bundle(self):
        """Helper to register a test bundle with proper mocking."""
        with PathOperationsMocker() as path_mock:
            path_mock.set_exists(self.test_bundle_path, True)
            
            # Create a proper stat mock with st_size attribute
            with patch('pathlib.Path.stat') as mock_stat:
                stat_result = Mock()
                stat_result.st_size = 1024
                mock_stat.return_value = stat_result
                
                self.service.register(
                    csv_hash=self.test_csv_hash,
                    graph_name=self.test_graph_name,
                    bundle_path=self.test_bundle_path,
                    csv_path=self.test_csv_path
                )
    
    def _register_multiple_test_graphs(self):
        """Helper to register multiple graphs for testing."""
        bundle1_path = Path("/tmp/bundle1.pkl")
        bundle2_path = Path("/tmp/bundle2.pkl")
        
        with PathOperationsMocker() as path_mock:
            path_mock.set_exists(bundle1_path, True)
            path_mock.set_exists(bundle2_path, True)
            
            # Use global Path.stat patching instead of instance patching
            with patch('pathlib.Path.stat') as mock_stat:
                stat_result = Mock()
                stat_result.st_size = 1024
                mock_stat.return_value = stat_result
                
                self.service.register(self.test_csv_hash, "graph1", bundle1_path, self.test_csv_path)
                self.service.register(self.test_csv_hash, "graph2", bundle2_path, self.test_csv_path)
    
    # =============================================================================
    # Integration-Style Tests
    # =============================================================================
    
    def test_full_composite_key_workflow(self):
        """Test complete workflow: register multiple graphs, lookup, and removal."""
        csv_hash = "full_test_hash" + "0" * 50
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.stat') as mock_stat:
                stat_result = Mock()
                stat_result.st_size = 1024
                mock_stat.return_value = stat_result
                
                # Register multiple graphs from same CSV
                self.service.register(csv_hash, "workflow1", Path("/tmp/wf1.pkl"), Path("/tmp/test.csv"))
                self.service.register(csv_hash, "workflow2", Path("/tmp/wf2.pkl"), Path("/tmp/test.csv"))
        
        # Verify specific lookups
        with patch.object(Path, 'exists', return_value=True):
            result1 = self.service.find_bundle(csv_hash, "workflow1")
            result2 = self.service.find_bundle(csv_hash, "workflow2")
            result_default = self.service.find_bundle(csv_hash)
        
        # Normalize path separators for cross-platform compatibility
        self.assertEqual(self._normalize_path(result1), "/tmp/wf1.pkl")
        self.assertEqual(self._normalize_path(result2), "/tmp/wf2.pkl")
        self.assertIsNotNone(result_default)  # Should return one of them
        
        # Remove one graph
        self.service.remove_entry(csv_hash, "workflow1")
        
        # Verify removal
        with patch.object(Path, 'exists', return_value=True):
            result1_after = self.service.find_bundle(csv_hash, "workflow1")
            result2_after = self.service.find_bundle(csv_hash, "workflow2")
        
        self.assertIsNone(result1_after)
        self.assertEqual(self._normalize_path(result2_after), "/tmp/wf2.pkl")


def mock_open(content):
    """Helper to create a mock file with specific content."""
    from unittest.mock import mock_open as base_mock_open
    if isinstance(content, bytes):
        return base_mock_open(read_data=content)
    else:
        return base_mock_open(read_data=content.encode())


if __name__ == '__main__':
    unittest.main()
