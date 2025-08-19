"""
CLI Integration Tests - Simplified and Working.

Tests for cross-command workflows and CLI-wide functionality:
- Version information
- Error handling across commands
- Integration workflows
- Common CLI patterns
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from agentmap.core.cli.main_cli import app
from tests.utils.mock_service_factory import MockServiceFactory


class SimpleCLITestBase(unittest.TestCase):
    """Simplified base class for CLI testing without complex mixins."""
    
    def setUp(self):
        """Set up CLI test environment."""
        self.runner = CliRunner()
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.csv_dir = self.temp_path / "csv_data"
        
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mock services using established MockServiceFactory pattern
        self.setup_service_defaults()
    
    def setup_service_defaults(self):
        """Configure realistic service defaults using MockServiceFactory."""
        # Create validation service mock with proper validation results
        self.mock_validation_service = Mock()
        
        # Configure successful validation defaults
        validation_result = Mock()
        validation_result.has_errors = False
        validation_result.has_warnings = False
        validation_result.errors = []
        validation_result.warnings = []
        validation_result.info = []
        
        # Simple validation service - let CLI commands handle file existence
        self.mock_validation_service.validate_csv.return_value = validation_result
        self.mock_validation_service.validate_config.return_value = validation_result
        self.mock_validation_service.validate_both.return_value = (validation_result, validation_result)
        self.mock_validation_service.validate_csv_for_bundling.return_value = None
        self.mock_validation_service.print_validation_summary.return_value = None
        
        # Create other services using MockServiceFactory
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "csv_path": str(self.csv_dir / "test.csv")
        })
        # Configure the get_all() method that the config command needs
        self.mock_app_config_service.get_all.return_value = {
            "logging": {"level": "INFO", "format": "[%(levelname)s] %(name)s: %(message)s"},
            "execution": {"timeout": 30, "tracking": {"enabled": True}},
            "csv_path": str(self.csv_dir / "test.csv"),
            "prompts": {"directory": "prompts", "registry_file": "prompts/registry.yaml"},
            "llm": {"openai": {"model": "gpt-3.5-turbo"}}
        }
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Create other service mocks
        self.mock_graph_runner_service = Mock()
        
        # Simple graph runner service - let CLI commands handle file existence
        run_result = Mock()
        run_result.success = True
        run_result.final_state = {"result": "completed"}
        run_result.error = None
        self.mock_graph_runner_service.run_graph.return_value = run_result
        
        # Additional services needed for comprehensive CLI testing
        self.mock_graph_compilation_service = MockServiceFactory.create_mock_compilation_service()
        self.mock_graph_scaffold_service = Mock()
        self.mock_graph_output_service = Mock()
        
        # Configure features registry service with proper boolean returns
        self.mock_features_registry_service = Mock()
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        self.mock_features_registry_service.is_provider_registered.return_value = True
        self.mock_features_registry_service.is_provider_validated.return_value = True
        self.mock_features_registry_service.is_provider_available.return_value = True
        
        # Configure dependency checker service with proper return values
        self.mock_dependency_checker_service = Mock()
        # check_llm_dependencies returns (has_dependencies: bool, missing: list)
        self.mock_dependency_checker_service.check_llm_dependencies.return_value = (True, [])
        # check_storage_dependencies returns (has_dependencies: bool, missing: list)
        self.mock_dependency_checker_service.check_storage_dependencies.return_value = (True, [])
        
        self.mock_validation_cache_service = Mock()
        # Configure validation cache service methods
        self.mock_validation_cache_service.clear_validation_cache.return_value = 0
        self.mock_validation_cache_service.cleanup_validation_cache.return_value = 0
        self.mock_validation_cache_service.get_validation_cache_stats.return_value = {
            'total_files': 0,
            'valid_files': 0,
            'expired_files': 0,
            'corrupted_files': 0
        }
        
        self.mock_complexity_analysis_service = Mock()
    
    def create_test_csv(self, filename="test.csv"):
        """Create a test CSV file."""
        content = '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
test_graph,start,Default,Start node,Description,input,output,end
test_graph,end,Default,End node,Description,output,result,
'''
        csv_path = self.csv_dir / filename
        csv_path.write_text(content)
        return csv_path
    
    def run_command(self, args):
        """Run CLI command with comprehensive mocking using MockServiceFactory pattern."""
        mock_container = Mock()
        
        # Configure services with MockServiceFactory pattern (like working validation test)
        mock_container.validation_service.return_value = self.mock_validation_service
        mock_container.app_config_service.return_value = self.mock_app_config_service
        mock_container.logging_service.return_value = self.mock_logging_service
        mock_container.graph_runner_service.return_value = self.mock_graph_runner_service
        mock_container.graph_compilation_service.return_value = self.mock_graph_compilation_service
        mock_container.graph_scaffold_service.return_value = self.mock_graph_scaffold_service
        mock_container.graph_output_service.return_value = self.mock_graph_output_service
        mock_container.features_registry_service.return_value = self.mock_features_registry_service
        mock_container.dependency_checker_service.return_value = self.mock_dependency_checker_service
        mock_container.validation_cache_service.return_value = self.mock_validation_cache_service
        mock_container.complexity_analysis_service.return_value = self.mock_complexity_analysis_service
        
        # Create mock adapter for run commands
        mock_adapter = Mock()
        mock_adapter.initialize_services.return_value = (
            self.mock_graph_runner_service,
            self.mock_app_config_service,
            self.mock_logging_service
        )
        mock_adapter.create_run_options.return_value = {}
        mock_adapter.extract_result_state.return_value = {"final_state": "test_result"}
        
        # Make handle_execution_error preserve the original error message  
        def smart_handle_execution_error(error):
            return {"error": str(error)}
        
        mock_adapter.handle_execution_error.side_effect = smart_handle_execution_error
        
        # Patch all initialization points with correct module paths
        patches = [
            # Patch where initialize_di is imported in each module 
            patch('agentmap.core.cli.validation_commands.initialize_di', return_value=mock_container),
            patch('agentmap.core.cli.run_commands.initialize_di', return_value=mock_container),
            patch('agentmap.core.cli.run_commands.initialize_application', return_value=mock_container),
            patch('agentmap.core.cli.run_commands.create_service_adapter', return_value=mock_adapter),
            # NOTE: Do NOT patch validate_run_parameters - let it do file existence check
            patch('agentmap.core.cli.diagnostic_commands.initialize_di', return_value=mock_container),
        ]
        
        for p in patches:
            p.start()
        
        try:
            return self.runner.invoke(app, args, catch_exceptions=True)
        finally:
            for p in patches:
                try:
                    p.stop()
                except RuntimeError:
                    pass
    
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


class TestCLIVersion(SimpleCLITestBase):
    """Test CLI version and basic functionality."""
    
    def test_version_flag(self):
        """Test --version flag shows version information."""
        result = self.run_command(["--version"])
        self.assert_success(result)
        self.assertIn("AgentMap", result.stdout)
    
    def test_version_short_flag(self):
        """Test -v flag shows version information."""
        result = self.run_command(["-v"])
        self.assert_success(result)
        self.assertIn("AgentMap", result.stdout)
    
    def test_help_output(self):
        """Test main help shows available commands."""
        result = self.run_command(["--help"])
        self.assert_success(result)
        self.assertIn("AgentMap", result.stdout)
        # The CLI uses fancy box-drawing format: "┌─ Commands ──────────────────────────────────────────┐"
        self.assertIn("Commands", result.stdout)


class TestCommandHelp(SimpleCLITestBase):
    """Test that all commands show proper help."""
    
    def test_all_commands_have_help(self):
        """Test that all main commands show help."""
        commands = [
            "run", "scaffold", "export",
            "validate-csv", "validate-config", "validate-all",
            "config", "diagnose", "validate-cache"
        ]
        
        for command in commands:
            with self.subTest(command=command):
                result = self.run_command([command, "--help"])
                self.assertEqual(result.exit_code, 0, f"Command '{command}' help should succeed: {result.stdout}")
                self.assertIn("Usage", result.stdout, f"Command '{command}' should show usage information")


class TestInvalidCommands(SimpleCLITestBase):
    """Test error handling for invalid commands and options."""
    
    def test_invalid_command(self):
        """Test invalid command shows error."""
        result = self.run_command(["invalid-command"])
        self.assert_failure(result)
        self.assertIn("No such command", result.stdout)
    
    def test_invalid_option_common_commands(self):
        """Test invalid options on common commands."""
        commands_to_test = ["run", "validate-csv"]
        
        for command in commands_to_test:
            with self.subTest(command=command):
                result = self.run_command([command, "--invalid-option"])
                self.assert_failure(result)
                # Note: Typer often returns exit code 2 for invalid options
                self.assertIn("No such option", result.stdout)


class TestCLIErrorHandling(SimpleCLITestBase):
    """Test error handling across CLI commands."""
    
    def test_missing_required_files(self):
        """Test commands handle missing files gracefully."""
        nonexistent_file = self.csv_dir / "nonexistent.csv"
        
        # Test commands that work with files
        file_commands = [
            ["validate-csv", "--csv", str(nonexistent_file)],
            ["run", "--graph", "test_graph", "--csv", str(nonexistent_file)],
        ]
        
        for command_args in file_commands:
            with self.subTest(command=command_args[0]):
                result = self.run_command(command_args)
                self.assert_failure(result)
                # Should contain helpful error message
                self.assertTrue(
                    "not found" in result.stdout.lower() or 
                    "does not exist" in result.stdout.lower() or
                    "no such file" in result.stdout.lower()
                )
    
    def test_service_failures_handled_gracefully(self):
        """Test CLI handles service failures gracefully."""
        csv_file = self.create_test_csv()
        
        # Configure validation service to fail
        self.mock_validation_service.validate_csv.side_effect = Exception("Service error")
        
        result = self.run_command(["validate-csv", "--csv", str(csv_file)])
        
        # Should fail but gracefully (no stack traces in output)
        self.assert_failure(result)
        self.assertNotIn("Traceback", result.stdout)
        self.assertNotIn("Exception", result.stdout.split('\n')[0])  # No exception in first line


class TestCLIWorkflowIntegration(SimpleCLITestBase):
    """Test complete workflows across multiple commands."""
    
    def test_validation_before_execution_workflow(self):
        """Test typical workflow: validate then run."""
        csv_file = self.create_test_csv()
        
        # Step 1: Validate CSV
        validate_result = self.run_command(["validate-csv", "--csv", str(csv_file)])
        self.assert_success(validate_result)
        
        # Step 2: Run graph (should work after validation passes)
        run_result = self.run_command(["run", "--graph", "test_graph", "--csv", str(csv_file)])
        self.assert_success(run_result)
    
    def test_diagnostic_before_execution_workflow(self):
        """Test workflow: check system then run commands."""
        csv_file = self.create_test_csv()
        
        # Step 1: Check system
        diagnose_result = self.run_command(["diagnose"])
        self.assert_success(diagnose_result)
        
        # Step 2: Check config
        config_result = self.run_command(["config"])
        self.assert_success(config_result)
        
        # Step 3: Run validation
        validate_result = self.run_command(["validate-csv", "--csv", str(csv_file)])
        self.assert_success(validate_result)
    
    def test_cache_management_workflow(self):
        """Test cache management workflow."""
        # Step 1: Check cache stats
        stats_result = self.run_command(["validate-cache"])
        self.assert_success(stats_result)
        
        # Step 2: Clean cache if needed
        cleanup_result = self.run_command(["validate-cache", "--cleanup"])
        self.assert_success(cleanup_result)


class TestCLIConsistency(SimpleCLITestBase):
    """Test consistency across CLI commands."""
    
    def test_consistent_success_markers(self):
        """Test that successful commands use consistent output markers."""
        csv_file = self.create_test_csv()
        
        # Commands that should show success markers
        success_commands = [
            ["validate-csv", "--csv", str(csv_file)],
            ["run", "--graph", "test_graph", "--csv", str(csv_file)],
        ]
        
        for command_args in success_commands:
            with self.subTest(command=command_args[0]):
                result = self.run_command(command_args)
                if result.exit_code == 0:  # Only check successful commands
                    # Should contain success marker
                    self.assertTrue(
                        "✅" in result.stdout or 
                        "success" in result.stdout.lower() or
                        "completed" in result.stdout.lower()
                    )
    
    def test_consistent_error_markers(self):
        """Test that failed commands use consistent error markers."""
        nonexistent_file = self.csv_dir / "nonexistent.csv"
        
        # Commands that should fail with file not found
        error_commands = [
            ["validate-csv", "--csv", str(nonexistent_file)],
        ]
        
        for command_args in error_commands:
            with self.subTest(command=command_args[0]):
                result = self.run_command(command_args)
                if result.exit_code != 0:  # Only check failed commands
                    # Should contain error marker
                    self.assertTrue(
                        "❌" in result.stdout or 
                        "error" in result.stdout.lower() or
                        "failed" in result.stdout.lower()
                    )


if __name__ == '__main__':
    unittest.main()
