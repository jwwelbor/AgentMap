"""
CLI Main Workflow Commands Tests - Simplified and Working.

Tests for the primary CLI workflow commands:
- run: Execute graphs
- compile: Compile graphs to optimized format
- scaffold: Generate agent and function templates
- export: Export graphs in various formats
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from agentmap.core.cli.main_cli import app


class SimpleCLITestBase(unittest.TestCase):
    """Simplified base class for CLI testing without complex mixins."""
    
    def setUp(self):
        """Set up CLI test environment."""
        self.runner = CliRunner()
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.csv_dir = self.temp_path / "csv_data"
        self.config_dir = self.temp_path / "config"
        self.output_dir = self.temp_path / "output"
        
        for directory in [self.csv_dir, self.config_dir, self.output_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Create mock services with simple, realistic defaults
        self.mock_graph_runner_service = Mock()
        self.mock_compilation_service = Mock()
        self.mock_scaffold_service = Mock()
        self.mock_export_service = Mock()
        self.mock_validation_service = Mock()
        self.mock_app_config_service = Mock()
        self.setup_service_defaults()
    
    def setup_service_defaults(self):
        """Configure realistic service defaults."""
        # Graph runner service
        success_result = Mock()
        success_result.success = True
        success_result.final_state = {"result": "completed"}
        success_result.error = None
        self.mock_graph_runner_service.run_graph.return_value = success_result
        
        # Compilation service
        compile_result = Mock()
        compile_result.success = True
        compile_result.compiled_graphs = ["test_graph"]
        compile_result.errors = []
        self.mock_compilation_service.compile_graph.return_value = compile_result
        self.mock_compilation_service.compile_all_graphs.return_value = compile_result
        
        # Scaffold service
        scaffold_result = Mock()
        scaffold_result.scaffolded_count = 2
        scaffold_result.errors = []
        scaffold_result.created_files = [Path("agent1.py"), Path("agent2.py")]
        # Provide proper service_stats dict instead of Mock
        scaffold_result.service_stats = {
            "with_services": 1,
            "without_services": 1
        }
        self.mock_scaffold_service.scaffold_agents_from_csv.return_value = scaffold_result
        
        # Export service
        self.mock_export_service.export_graph.return_value = {"status": "exported"}
        
        # Validation service
        validation_result = Mock()
        validation_result.has_errors = False
        validation_result.has_warnings = False
        self.mock_validation_service.validate_csv_for_compilation.return_value = None
        
        # App config service
        self.mock_app_config_service.get_csv_path.return_value = self.csv_dir / "test.csv"
    
    def create_test_csv(self, filename="test.csv"):
        """Create a test CSV file."""
        content = '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
test_graph,start,Default,Start node,Description,input,output,end
test_graph,end,Default,End node,Description,output,result,
'''
        csv_path = self.csv_dir / filename
        csv_path.write_text(content)
        return csv_path
    
    def create_test_config(self, filename="config.yaml"):
        """Create a test config file."""
        content = '''logging:
  level: INFO
execution:
  timeout: 30
'''
        config_path = self.config_dir / filename
        config_path.write_text(content)
        return config_path
    
    def run_command(self, args):
        """Run CLI command with proper container mocking."""
        mock_container = Mock()
        mock_container.graph_runner_service.return_value = self.mock_graph_runner_service
        mock_container.graph_compilation_service.return_value = self.mock_compilation_service
        mock_container.graph_scaffold_service.return_value = self.mock_scaffold_service
        mock_container.graph_output_service.return_value = self.mock_export_service
        mock_container.app_config_service.return_value = self.mock_app_config_service
        
        # Mock the validation service directly for run commands (accessed as attribute)
        mock_container.validation_service = self.mock_validation_service
        
        # Add logging service mock for scaffold command
        mock_logging_service = Mock()
        mock_logger = Mock()
        mock_logging_service.get_logger.return_value = mock_logger
        mock_container.logging_service.return_value = mock_logging_service
        
        # Create mock adapter for run commands
        mock_adapter = Mock()
        
        mock_adapter.initialize_services.return_value = (
            self.mock_graph_runner_service,
            self.mock_app_config_service, 
            mock_logging_service  # Use the same logging service mock
        )
        mock_adapter.create_run_options.return_value = {}
        mock_adapter.extract_result_state.return_value = {"final_state": "test_result"}
        mock_adapter.handle_execution_error.return_value = {"error": "test_error"}
        
        # Mock both possible import paths
        patches = [
            patch('agentmap.core.cli.run_commands.initialize_di', return_value=mock_container),
            patch('agentmap.core.cli.run_commands.initialize_application', return_value=mock_container),
            patch('agentmap.core.cli.run_commands.create_service_adapter', return_value=mock_adapter),
            patch('agentmap.core.cli.run_commands.validate_run_parameters', return_value=None),
        ]
        
        # Start all patches
        for p in patches:
            p.start()
        
        try:
            return self.runner.invoke(app, args, catch_exceptions=True)
        finally:
            # Stop all patches
            for p in patches:
                try:
                    p.stop()
                except RuntimeError:
                    pass  # Patch was already stopped
    
    def assert_success(self, result, expected_text=None):
        """Assert command succeeded."""
        self.assertEqual(result.exit_code, 0, f"Command failed: {result.stdout}")
        if expected_text:
            self.assertIn(expected_text, result.stdout)
    
    def assert_failure(self, result, expected_text=None):
        """Assert command failed."""
        self.assertNotEqual(result.exit_code, 0, f"Command should have failed: {result.stdout}")
        if expected_text:
            self.assertIn(expected_text, result.stdout)
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestRunCommand(SimpleCLITestBase):
    """Test run command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["run", "--help"])
        self.assert_success(result)
        self.assertIn("run", result.stdout.lower())
    
    def test_basic_run(self):
        """Test basic graph execution."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["run", "--graph", "test_graph"])
        
        self.assert_success(result)
        self.assertIn("✅", result.stdout)
    
    def test_run_with_csv_file(self):
        """Test run with specific CSV file."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["run", "--graph", "test_graph", "--csv", str(csv_file)])
        
        self.assert_success(result)
    
    def test_run_with_validation(self):
        """Test run with validation enabled."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["run", "--graph", "test_graph", "--validate"])
        
        self.assert_success(result)
        # Verify validation service was called
        self.mock_validation_service.validate_csv_for_compilation.assert_called()
    
    def test_run_with_execution_failure(self):
        """Test run command when graph execution fails."""
        csv_file = self.create_test_csv()
        
        # Configure graph runner to return failure
        failure_result = Mock()
        failure_result.success = False
        failure_result.error = "Graph execution failed"
        self.mock_graph_runner_service.run_graph.return_value = failure_result
        
        result = self.run_command(["run", "--graph", "test_graph"])
        
        self.assert_failure(result)


class TestCompileCommand(SimpleCLITestBase):
    """Test compile command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["compile", "--help"])
        self.assert_success(result)
        self.assertIn("compile", result.stdout.lower())
    
    def test_compile_specific_graph(self):
        """Test compiling a specific graph."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["compile", "--graph", "test_graph"])
        
        self.assert_success(result)
        self.assertIn("✅", result.stdout)
        self.mock_compilation_service.compile_graph.assert_called_once()
    
    def test_compile_all_graphs(self):
        """Test compiling all graphs."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["compile"])
        
        self.assert_success(result)
        self.mock_compilation_service.compile_all_graphs.assert_called_once()
    
    def test_compile_with_output_directory(self):
        """Test compile with custom output directory."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["compile", "--graph", "test_graph", "--output", str(self.output_dir)])
        
        self.assert_success(result)
    
    def test_compile_with_errors(self):
        """Test compile command when compilation fails."""
        csv_file = self.create_test_csv()
        
        # Configure compilation to fail
        error_result = Mock()
        error_result.success = False
        error_result.errors = ["Compilation failed"]
        self.mock_compilation_service.compile_graph.return_value = error_result
        
        result = self.run_command(["compile", "--graph", "test_graph"])
        
        self.assert_failure(result)


class TestScaffoldCommand(SimpleCLITestBase):
    """Test scaffold command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["scaffold", "--help"])
        self.assert_success(result)
        self.assertIn("scaffold", result.stdout.lower())
    
    def test_scaffold_all_agents(self):
        """Test scaffolding all agents."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["scaffold"])
        
        self.assert_success(result)
        self.assertIn("✅", result.stdout)
        self.assertIn("Scaffolded 2", result.stdout)
        self.mock_scaffold_service.scaffold_agents_from_csv.assert_called_once()
    
    def test_scaffold_specific_graph(self):
        """Test scaffolding for specific graph."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["scaffold", "--graph", "test_graph"])
        
        self.assert_success(result)
    
    def test_scaffold_with_output_directory(self):
        """Test scaffold with custom output directory."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["scaffold", "--output", str(self.output_dir)])
        
        self.assert_success(result)
    
    def test_scaffold_no_agents_found(self):
        """Test scaffold when no agents need scaffolding."""
        csv_file = self.create_test_csv()
        
        # Configure scaffold to find no agents
        no_agents_result = Mock()
        no_agents_result.scaffolded_count = 0
        no_agents_result.errors = []
        no_agents_result.created_files = []
        # Provide proper service_stats dict instead of Mock
        no_agents_result.service_stats = {
            "with_services": 0,
            "without_services": 0
        }
        self.mock_scaffold_service.scaffold_agents_from_csv.return_value = no_agents_result
        
        result = self.run_command(["scaffold"])
        
        self.assert_success(result)
        self.assertIn("No unknown agents", result.stdout)


class TestExportCommand(SimpleCLITestBase):
    """Test export command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["export", "--help"])
        self.assert_success(result)
        self.assertIn("export", result.stdout.lower())
    
    def test_export_basic(self):
        """Test basic export functionality."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["export", "--graph", "test_graph"])
        
        self.assert_success(result)
        self.assertIn("✅", result.stdout)
        self.mock_export_service.export_graph.assert_called_once()
    
    def test_export_with_format(self):
        """Test export with specific format."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["export", "--graph", "test_graph", "--format", "pickle"])
        
        self.assert_success(result)
    
    def test_export_with_output_file(self):
        """Test export with custom output file."""
        csv_file = self.create_test_csv()
        output_file = self.output_dir / "exported.pkl"
        
        result = self.run_command(["export", "--graph", "test_graph", "--output", str(output_file)])
        
        self.assert_success(result)
    
    def test_export_failure(self):
        """Test export when service fails."""
        csv_file = self.create_test_csv()
        
        # Configure export to fail
        self.mock_export_service.export_graph.side_effect = Exception("Export failed")
        
        result = self.run_command(["export", "--graph", "test_graph"])
        
        self.assert_failure(result)


class TestWorkflowCommandsIntegration(SimpleCLITestBase):
    """Test integration scenarios across workflow commands."""
    
    def test_complete_workflow(self):
        """Test complete workflow: scaffold -> compile -> run."""
        csv_file = self.create_test_csv()
        
        # Step 1: Scaffold
        scaffold_result = self.run_command(["scaffold"])
        self.assert_success(scaffold_result)
        
        # Step 2: Compile
        compile_result = self.run_command(["compile", "--graph", "test_graph"])
        self.assert_success(compile_result)
        
        # Step 3: Run
        run_result = self.run_command(["run", "--graph", "test_graph"])
        self.assert_success(run_result)
        
        # Verify all services were called
        self.mock_scaffold_service.scaffold_agents_from_csv.assert_called()
        self.mock_compilation_service.compile_graph.assert_called()
        self.mock_graph_runner_service.run_graph.assert_called()
    
    def test_export_after_compile(self):
        """Test export after compilation."""
        csv_file = self.create_test_csv()
        
        # Compile first
        compile_result = self.run_command(["compile", "--graph", "test_graph"])
        self.assert_success(compile_result)
        
        # Then export
        export_result = self.run_command(["export", "--graph", "test_graph"])
        self.assert_success(export_result)


if __name__ == '__main__':
    unittest.main()
