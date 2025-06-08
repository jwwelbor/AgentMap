"""
CLI Validation Commands Tests - Simplified and Fixed.

This module tests CLI validation commands with a cleaner, more maintainable approach
that eliminates the over-engineered mixin pattern and complex mock setup.
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from tests.utils.mock_service_factory import MockServiceFactory
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
        
        for directory in [self.csv_dir, self.config_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Create mock services with simple, realistic defaults
        self.mock_validation_service = Mock()
        self.setup_validation_service_defaults()
    
    def setup_validation_service_defaults(self):
        """Configure realistic validation service defaults."""
        # Default successful validation result
        success_result = Mock()
        success_result.has_errors = False
        success_result.has_warnings = False
        success_result.errors = []
        success_result.warnings = []
        
        self.mock_validation_service.validate_csv.return_value = success_result
        self.mock_validation_service.validate_config.return_value = success_result
        self.mock_validation_service.validate_both.return_value = (success_result, success_result)
        self.mock_validation_service.print_validation_summary.return_value = None
    
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
        mock_container.validation_service.return_value = self.mock_validation_service
        
        with patch('agentmap.core.cli.validation_commands.initialize_di', return_value=mock_container):
            return self.runner.invoke(app, args, catch_exceptions=True)
    
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


class TestValidateCSVCommand(SimpleCLITestBase):
    """Test validate-csv command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["validate-csv", "--help"])
        self.assert_success(result)
        self.assertIn("validate-csv", result.stdout)
        self.assertIn("Usage", result.stdout)
    
    def test_invalid_option(self):
        """Test invalid option shows error."""
        result = self.run_command(["validate-csv", "--invalid-option"])
        self.assert_failure(result)
        self.assertIn("No such option", result.stdout)
    
    def test_successful_validation(self):
        """Test successful CSV validation."""
        csv_file = self.create_test_csv()
        
        result = self.run_command(["validate-csv", "--csv", str(csv_file)])
        
        self.assert_success(result)
        self.assertIn("✅", result.stdout)
        
        # Verify service was called
        self.mock_validation_service.validate_csv.assert_called_once()
    
    def test_validation_with_errors(self):
        """Test CSV validation with errors."""
        csv_file = self.create_test_csv()
        
        # Configure service to return errors
        error_result = Mock()
        error_result.has_errors = True
        error_result.has_warnings = False
        error_result.errors = ["Error 1", "Error 2"]
        error_result.warnings = []
        self.mock_validation_service.validate_csv.return_value = error_result
        
        result = self.run_command(["validate-csv", "--csv", str(csv_file)])
        
        self.assert_failure(result)
        self.mock_validation_service.validate_csv.assert_called_once()
    
    def test_nonexistent_file(self):
        """Test validation with non-existent file."""
        nonexistent = self.csv_dir / "nonexistent.csv"
        
        result = self.run_command(["validate-csv", "--csv", str(nonexistent)])
        
        self.assert_failure(result)
        self.assertIn("not found", result.stdout)


class TestValidateConfigCommand(SimpleCLITestBase):
    """Test validate-config command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["validate-config", "--help"])
        self.assert_success(result)
        self.assertIn("validate-config", result.stdout)
    
    def test_successful_validation(self):
        """Test successful config validation."""
        config_file = self.create_test_config()
        
        result = self.run_command(["validate-config", "--config", str(config_file)])
        
        self.assert_success(result)
        self.assertIn("✅", result.stdout)
        self.mock_validation_service.validate_config.assert_called_once()
    
    def test_validation_with_errors(self):
        """Test config validation with errors."""
        config_file = self.create_test_config()
        
        # Configure service to return errors
        error_result = Mock()
        error_result.has_errors = True
        error_result.errors = ["Config error"]
        self.mock_validation_service.validate_config.return_value = error_result
        
        result = self.run_command(["validate-config", "--config", str(config_file)])
        
        self.assert_failure(result)


class TestValidateAllCommand(SimpleCLITestBase):
    """Test validate-all command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["validate-all", "--help"])
        self.assert_success(result)
        self.assertIn("validate-all", result.stdout)
    
    def test_successful_validation(self):
        """Test successful validation of both files."""
        csv_file = self.create_test_csv()
        config_file = self.create_test_config()
        
        result = self.run_command([
            "validate-all", 
            "--csv", str(csv_file),
            "--config", str(config_file)
        ])
        
        self.assert_success(result)
        self.assertIn("✅", result.stdout)
        self.mock_validation_service.validate_both.assert_called_once()
    
    def test_validation_with_errors(self):
        """Test validation when one file has errors."""
        csv_file = self.create_test_csv()
        config_file = self.create_test_config()
        
        # Configure CSV validation to fail
        csv_error = Mock(has_errors=True, errors=["CSV error"])
        config_success = Mock(has_errors=False, errors=[])
        self.mock_validation_service.validate_both.return_value = (csv_error, config_success)
        
        result = self.run_command([
            "validate-all",
            "--csv", str(csv_file), 
            "--config", str(config_file)
        ])
        
        self.assert_failure(result)


class TestValidationCommandsIntegration(SimpleCLITestBase):
    """Test integration scenarios across validation commands."""
    
    def test_workflow_validation_sequence(self):
        """Test running validation commands in sequence."""
        csv_file = self.create_test_csv()
        config_file = self.create_test_config()
        
        # Test CSV validation
        csv_result = self.run_command(["validate-csv", "--csv", str(csv_file)])
        self.assert_success(csv_result)
        
        # Test config validation
        config_result = self.run_command(["validate-config", "--config", str(config_file)])
        self.assert_success(config_result)
        
        # Test combined validation
        all_result = self.run_command([
            "validate-all",
            "--csv", str(csv_file),
            "--config", str(config_file)
        ])
        self.assert_success(all_result)
        
        # Verify all services were called
        self.mock_validation_service.validate_csv.assert_called()
        self.mock_validation_service.validate_config.assert_called()
        self.mock_validation_service.validate_both.assert_called()


if __name__ == '__main__':
    unittest.main()
