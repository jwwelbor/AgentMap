"""
Test for path mocking utilities to ensure they work correctly.

This test validates the new utilities and serves as documentation.
"""

import unittest
from pathlib import Path
from unittest.mock import Mock

from tests.utils.path_mocking_utils import (
    PathOperationsMocker,
    mock_path_exists,
    mock_path_stat,
    mock_compilation_currency,
    mock_time_progression,
    MockServiceConfigHelper
)


class TestPathMockingUtilities(unittest.TestCase):
    """Test the path mocking utilities themselves."""
    
    def test_path_exists_mocker(self):
        """Test PathExistsMocker works correctly."""
        # Use Windows-compatible paths or test with actual Path objects
        existing_path = Path("existing/file.txt")
        missing_path = Path("missing/file.txt")
        
        with mock_path_exists({
            existing_path: True,
            missing_path: False
        }):
            # Test existing file
            self.assertTrue(existing_path.exists())
            
            # Test missing file
            self.assertFalse(missing_path.exists())
            
            # Test default behavior (should be False)
            self.assertFalse(Path("unknown/file.txt").exists())
    
    def test_path_stat_mocker(self):
        """Test PathStatMocker works correctly."""
        newer_path = Path("newer/file.txt")
        older_path = Path("older/file.txt")
        
        with mock_path_stat({
            newer_path: 1642000000,
            older_path: 1641000000
        }):
            # Test newer file
            newer_stat = newer_path.stat()
            self.assertEqual(newer_stat.st_mtime, 1642000000)
            
            # Test older file
            older_stat = older_path.stat()
            self.assertEqual(older_stat.st_mtime, 1641000000)
            
            # Test file comparison
            self.assertGreater(newer_stat.st_mtime, older_stat.st_mtime)
    
    def test_path_operations_mocker_fluent_interface(self):
        """Test PathOperationsMocker fluent interface."""
        output_path = Path("compiled/graph.pkl")
        csv_path = Path("graphs/workflow.csv")
        
        with PathOperationsMocker() as path_mock:
            # Test fluent interface chaining
            (path_mock
             .set_exists(output_path, True)
             .set_exists(csv_path, True)
             .set_stat(output_path, 1642000000)
             .set_stat(csv_path, 1641000000))
            
            # Verify existence
            self.assertTrue(output_path.exists())
            self.assertTrue(csv_path.exists())
            
            # Verify timestamps
            self.assertEqual(output_path.stat().st_mtime, 1642000000)
            self.assertEqual(csv_path.stat().st_mtime, 1641000000)
            
            # Verify comparison
            self.assertGreater(output_path.stat().st_mtime, csv_path.stat().st_mtime)
    
    def test_compilation_currency_convenience(self):
        """Test compilation currency convenience function."""
        output_path = Path("compiled/current_graph.pkl")
        csv_path = Path("graphs/workflow.csv")
        
        # Test current compilation (compiled newer than CSV)
        with mock_compilation_currency(output_path, csv_path, is_current=True):
            self.assertTrue(output_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertGreater(output_path.stat().st_mtime, csv_path.stat().st_mtime)
        
        # Test outdated compilation (CSV newer than compiled)
        with mock_compilation_currency(output_path, csv_path, is_current=False):
            self.assertTrue(output_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertLess(output_path.stat().st_mtime, csv_path.stat().st_mtime)
    
    def test_compilation_scenario_helper(self):
        """Test compilation scenario helper method."""
        output_path = Path("compiled/test.pkl")
        csv_path = Path("graphs/test.csv")
        
        with PathOperationsMocker() as path_mock:
            # Test current scenario
            path_mock.set_compilation_scenario(output_path, csv_path, is_current=True)
            
            self.assertTrue(output_path.exists())
            self.assertTrue(csv_path.exists())
            self.assertGreater(output_path.stat().st_mtime, csv_path.stat().st_mtime)
    
    def test_time_progression(self):
        """Test time progression mocking."""
        import time
        
        with mock_time_progression(start_time=100.0, increment=0.5) as time_mock:
            # First call
            time1 = time.time()
            self.assertEqual(time1, 100.0)
            
            # Second call  
            time2 = time.time()
            self.assertEqual(time2, 100.5)
            
            # Third call
            time3 = time.time()
            self.assertEqual(time3, 101.0)
            
            # Verify progression
            self.assertGreater(time3, time2)
            self.assertGreater(time2, time1)
    
    def test_mock_service_config_helper(self):
        """Test MockServiceConfigHelper for app config services."""
        # Create a basic mock object
        mock_service = Mock()
        
        # Configure it with the helper
        MockServiceConfigHelper.configure_app_config_service(
            mock_service,
            {
                "csv_path": "graphs/workflow.csv",
                "compiled_graphs_path": "compiled",
                "functions_path": "functions"
            }
        )
        
        # Verify method access works
        self.assertEqual(mock_service.get_csv_path(), Path("graphs/workflow.csv"))
        self.assertEqual(mock_service.get_compiled_graphs_path(), Path("compiled"))
        
        # Verify property access works
        self.assertEqual(mock_service.csv_path, Path("graphs/workflow.csv"))
        self.assertEqual(mock_service.compiled_graphs_path, Path("compiled"))
        self.assertEqual(mock_service.functions_path, Path("functions"))
    
    def test_file_newer_than_helper(self):
        """Test file_newer_than helper method."""
        newer_file = Path("newer.txt")
        older_file = Path("older.txt")
        
        with PathOperationsMocker() as path_mock:
            path_mock.set_file_newer_than(newer_file, older_file, 2000, 1000)
            
            # Both files should exist
            self.assertTrue(newer_file.exists())
            self.assertTrue(older_file.exists())
            
            # Newer file should have later timestamp
            self.assertEqual(newer_file.stat().st_mtime, 2000)
            self.assertEqual(older_file.stat().st_mtime, 1000)
            self.assertGreater(newer_file.stat().st_mtime, older_file.stat().st_mtime)


if __name__ == '__main__':
    unittest.main()
