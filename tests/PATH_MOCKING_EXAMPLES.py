"""
Example: Refactoring test_compilation_service.py with new Path Mocking Utilities

This file shows before/after examples of how to use the new utilities.
"""

# BEFORE: Complex manual mocking (from our recent fixes)
def test_get_compilation_status_compiled_current_OLD(self):
    """Test get_compilation_status() for compiled and current graph - OLD APPROACH."""
    # Prepare test data
    graph_name = "status_test_graph"
    csv_path = Path("graphs/test.csv")
    
    # Mock path operations and file stats
    with patch.object(self.service, '_get_output_path') as mock_get_output, \
         patch.object(self.service, '_is_compilation_current') as mock_is_current, \
         patch('pathlib.Path.stat') as mock_stat:
        
        # Configure output path
        output_path = Path("compiled/status_test_graph.pkl")
        mock_get_output.return_value = output_path
        
        # Configure file existence and currency using proper global patching
        def mock_exists(self):
            if str(self) == str(output_path) or str(self) == str(csv_path):
                return True
            return False
        
        with patch('pathlib.Path.exists', mock_exists):
            mock_is_current.return_value = True
            
            # Configure file modification times
            mock_stat.return_value.st_mtime = 1642000000  # Mock timestamp
            
            # Execute test
            status = self.service.get_compilation_status(graph_name, csv_path)
            
            # Verify status
            self.assertEqual(status["graph_name"], graph_name)
            self.assertTrue(status["compiled"])
            self.assertTrue(status["current"])


# AFTER: Clean utility usage
def test_get_compilation_status_compiled_current_NEW(self):
    """Test get_compilation_status() for compiled and current graph - NEW APPROACH."""
    from tests.utils.path_mocking_utils import mock_compilation_currency
    
    # Prepare test data  
    graph_name = "status_test_graph"
    csv_path = Path("graphs/test.csv")
    output_path = Path("compiled/status_test_graph.pkl")
    
    with patch.object(self.service, '_get_output_path', return_value=output_path), \
         patch.object(self.service, '_is_compilation_current', return_value=True), \
         patch('pathlib.Path.stat', return_value=Mock(st_mtime=1642000000)), \
         mock_compilation_currency(output_path, csv_path, is_current=True):
        
        # Execute test
        status = self.service.get_compilation_status(graph_name, csv_path)
        
        # Verify status
        self.assertEqual(status["graph_name"], graph_name)
        self.assertTrue(status["compiled"])
        self.assertTrue(status["current"])


# EVEN BETTER: Using the fluent interface for complex scenarios
def test_get_compilation_status_compiled_outdated_FLUENT(self):
    """Test get_compilation_status() for compiled but outdated graph - FLUENT APPROACH."""
    from tests.utils.path_mocking_utils import PathOperationsMocker
    
    # Prepare test data
    graph_name = "outdated_graph"
    csv_path = Path("graphs/updated.csv")
    output_path = Path("compiled/outdated_graph.pkl")
    
    with patch.object(self.service, '_get_output_path', return_value=output_path), \
         patch.object(self.service, '_is_compilation_current', return_value=False), \
         PathOperationsMocker() as path_mock:
        
        # Configure paths with fluent interface - CSV newer than compiled file
        (path_mock
         .set_exists(output_path, True)
         .set_exists(csv_path, True)
         .set_stat(output_path, 1641000000)  # Older compiled file
         .set_stat(csv_path, 1642000000))    # Newer CSV file
        
        # Execute test
        status = self.service.get_compilation_status(graph_name, csv_path)
        
        # Verify status shows outdated
        self.assertEqual(status["graph_name"], graph_name)
        self.assertTrue(status["compiled"])
        self.assertFalse(status["current"])  # Outdated
        self.assertEqual(status["compiled_time"], 1641000000)
        self.assertEqual(status["csv_modified_time"], 1642000000)


# DEMONSTRATION: Multiple scenarios in one test
def test_compilation_scenarios_COMPREHENSIVE(self):
    """Demonstrate testing multiple compilation scenarios easily."""
    from tests.utils.path_mocking_utils import PathOperationsMocker
    
    output_path = Path("compiled/test_graph.pkl")
    csv_path = Path("graphs/test.csv")
    
    # Scenario 1: Current compilation
    with PathOperationsMocker() as path_mock:
        path_mock.set_compilation_scenario(output_path, csv_path, is_current=True)
        
        with patch.object(self.service, '_get_output_path', return_value=output_path):
            result = self.service._is_compilation_current("test_graph", csv_path)
            self.assertTrue(result, "Should be current when compiled file is newer")
    
    # Scenario 2: Outdated compilation  
    with PathOperationsMocker() as path_mock:
        path_mock.set_compilation_scenario(output_path, csv_path, is_current=False)
        
        with patch.object(self.service, '_get_output_path', return_value=output_path):
            result = self.service._is_compilation_current("test_graph", csv_path)
            self.assertFalse(result, "Should be outdated when CSV is newer")
    
    # Scenario 3: Missing compiled file
    with PathOperationsMocker() as path_mock:
        path_mock.set_exists(output_path, False).set_exists(csv_path, True)
        
        with patch.object(self.service, '_get_output_path', return_value=output_path):
            result = self.service._is_compilation_current("test_graph", csv_path)
            self.assertFalse(result, "Should be outdated when compiled file missing")


# TIMING EXAMPLE: Clean time mocking
def test_compile_graph_timing_NEW(self):
    """Test compilation timing with clean time mocking."""
    from tests.utils.path_mocking_utils import mock_time_progression
    
    graph_name = "timed_graph"
    
    # Configure mocks as usual...
    mock_graph = Mock()
    mock_graph.nodes = {"node1": Mock(name="node1")}
    self.mock_graph_definition_service.build_from_csv.return_value = mock_graph
    
    # Mock timing with automatic progression
    with mock_time_progression(start_time=0.0, increment=0.1), \
         patch('os.makedirs'), \
         patch('builtins.open', unittest.mock.mock_open(read_data="test,csv")), \
         patch.object(self.service, '_is_compilation_current', return_value=False):
        
        result = self.service.compile_graph(graph_name)
        
        # Timing will be 0.1 (end_time - start_time)
        self.assertEqual(result.compilation_time, 0.1)
        self.assertGreater(result.compilation_time, 0)
