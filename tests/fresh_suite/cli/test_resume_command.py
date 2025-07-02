"""
Test for the resume command in the CLI.

Tests the resume functionality for human-in-the-loop workflows.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from agentmap.core.cli.main_cli import app
from agentmap.models.human_interaction import HumanInteractionResponse


class TestResumeCommand(unittest.TestCase):
    """Test cases for the resume command."""
    
    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()
        
        # Create mock services
        self.mock_container = Mock()
        self.mock_storage_manager = Mock()
        self.mock_storage_service = Mock()
        self.mock_logging_service = Mock()
        self.mock_logger = Mock()
        self.mock_cli_handler = Mock()
        
        # Configure mocks
        self.mock_container.storage_service_manager.return_value = self.mock_storage_manager
        self.mock_storage_manager.get_service.return_value = self.mock_storage_service
        self.mock_container.logging_service.return_value = self.mock_logging_service
        self.mock_logging_service.get_logger.return_value = self.mock_logger
        
        # Configure successful resume by default
        self.mock_cli_handler.resume_execution.return_value = HumanInteractionResponse(
            request_id="test-request-id",
            action="approve",
            data={}
        )
    
    def run_command(self, args):
        """Run CLI command with proper mocking."""
        with patch('agentmap.core.cli.run_commands.initialize_di', return_value=self.mock_container), \
             patch('agentmap.core.cli.run_commands.CLIInteractionHandler', return_value=self.mock_cli_handler):
            return self.runner.invoke(app, args, catch_exceptions=True)
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["resume", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Resume an interrupted workflow", result.stdout)
        self.assertIn("thread_id", result.stdout)
        self.assertIn("response", result.stdout)
    
    def test_basic_resume_approve(self):
        """Test basic resume with approve action."""
        result = self.run_command(["resume", "test-thread-id", "approve"])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Successfully resumed", result.stdout)
        
        # Verify handler was called correctly
        self.mock_cli_handler.resume_execution.assert_called_once_with(
            thread_id="test-thread-id",
            response_action="approve",
            response_data=None
        )
    
    def test_resume_with_json_data(self):
        """Test resume with JSON data."""
        data = {"choice": 1, "reason": "test reason"}
        result = self.run_command([
            "resume", 
            "test-thread-id", 
            "choose",
            "--data", json.dumps(data)
        ])
        
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Successfully resumed", result.stdout)
        
        # Verify handler was called with parsed data
        self.mock_cli_handler.resume_execution.assert_called_once_with(
            thread_id="test-thread-id",
            response_action="choose",
            response_data=data
        )
    
    def test_resume_with_data_file(self):
        """Test resume with data from file."""
        # Create temporary JSON file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            data = {"edited": "new content", "metadata": {"version": 2}}
            json.dump(data, f)
            temp_file = f.name
        
        try:
            result = self.run_command([
                "resume", 
                "test-thread-id", 
                "edit",
                "--data-file", temp_file
            ])
            
            self.assertEqual(result.exit_code, 0)
            self.assertIn("✅ Successfully resumed", result.stdout)
            
            # Verify handler was called with file data
            self.mock_cli_handler.resume_execution.assert_called_once_with(
                thread_id="test-thread-id",
                response_action="edit",
                response_data=data
            )
        finally:
            # Clean up
            Path(temp_file).unlink(missing_ok=True)
    
    def test_resume_with_invalid_json(self):
        """Test resume with invalid JSON data."""
        result = self.run_command([
            "resume", 
            "test-thread-id", 
            "respond",
            "--data", "invalid json {{"
        ])
        
        self.assertEqual(result.exit_code, 1)
        self.assertIn("❌ Invalid JSON", result.stdout)
    
    def test_resume_with_missing_data_file(self):
        """Test resume with non-existent data file."""
        result = self.run_command([
            "resume", 
            "test-thread-id", 
            "respond",
            "--data-file", "/nonexistent/file.json"
        ])
        
        self.assertEqual(result.exit_code, 1)
        self.assertIn("❌ Data file not found", result.stdout)
    
    def test_resume_thread_not_found(self):
        """Test resume when thread is not found."""
        self.mock_cli_handler.resume_execution.side_effect = ValueError("Thread 'test-thread-id' not found in storage")
        
        result = self.run_command(["resume", "test-thread-id", "approve"])
        
        self.assertEqual(result.exit_code, 1)
        self.assertIn("❌ Error:", result.stdout)
        self.assertIn("not found", result.stdout)
    
    def test_resume_storage_error(self):
        """Test resume when storage error occurs."""
        self.mock_cli_handler.resume_execution.side_effect = RuntimeError("Failed to save response")
        
        result = self.run_command(["resume", "test-thread-id", "approve"])
        
        self.assertEqual(result.exit_code, 1)
        self.assertIn("❌ Storage error:", result.stdout)
    
    def test_resume_no_storage_available(self):
        """Test resume when storage services are not available."""
        self.mock_container.storage_service_manager.return_value = None
        
        result = self.run_command(["resume", "test-thread-id", "approve"])
        
        self.assertEqual(result.exit_code, 1)
        self.assertIn("❌ Storage services are not available", result.stdout)
    
    def test_resume_with_custom_config(self):
        """Test resume with custom config file."""
        result = self.run_command([
            "resume", 
            "test-thread-id", 
            "approve",
            "--config", "/path/to/config.yaml"
        ])
        
        # Should still work (config path is passed to initialize_di)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("✅ Successfully resumed", result.stdout)
    
    def test_resume_all_action_types(self):
        """Test resume with different action types."""
        action_types = ["approve", "reject", "choose", "respond", "edit", "custom_action"]
        
        for action in action_types:
            with self.subTest(action=action):
                result = self.run_command(["resume", f"thread-{action}", action])
                
                self.assertEqual(result.exit_code, 0)
                self.assertIn("✅ Successfully resumed", result.stdout)
                
                # Verify the correct action was passed
                call_args = self.mock_cli_handler.resume_execution.call_args
                self.assertEqual(call_args[1]["response_action"], action)
    
    def test_resume_with_complex_data(self):
        """Test resume with complex nested JSON data."""
        complex_data = {
            "choice": 2,
            "metadata": {
                "timestamp": "2024-01-01T00:00:00",
                "user": "test_user",
                "tags": ["important", "review"]
            },
            "nested": {
                "level1": {
                    "level2": {
                        "value": 42
                    }
                }
            }
        }
        
        result = self.run_command([
            "resume", 
            "complex-thread-id", 
            "respond",
            "--data", json.dumps(complex_data)
        ])
        
        self.assertEqual(result.exit_code, 0)
        
        # Verify complex data was parsed correctly
        call_args = self.mock_cli_handler.resume_execution.call_args
        self.assertEqual(call_args[1]["response_data"], complex_data)


if __name__ == '__main__':
    unittest.main()