"""
Tests for the init command (formerly init-config).

Following TDD approach:
1. RED: Write failing test
2. Verify it fails correctly
3. GREEN: Write minimal code to pass
4. REFACTOR: Clean up
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from agentmap.deployment.cli.main_cli import app


class TestInitCommand(unittest.TestCase):
    """Test the init command functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temp directory
        import shutil

        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_init_creates_folder_structure(self):
        """Test that init command creates the expected folder structure."""
        with self.runner.isolated_filesystem(temp_dir=self.temp_dir):
            # Run the init command
            result = self.runner.invoke(app, ["init"])

            # Verify command succeeded
            self.assertEqual(result.exit_code, 0, f"Command failed: {result.output}")

            # Verify folder structure was created
            self.assertTrue(
                Path("agentmap_data").exists(), "agentmap_data directory not created"
            )
            self.assertTrue(
                Path("agentmap_data/workflows").exists(),
                "workflows directory not created",
            )
            self.assertTrue(
                Path("agentmap_data/custom_agents").exists(),
                "custom_agents directory not created",
            )
            self.assertTrue(
                Path("agentmap_data/custom_functions").exists(),
                "custom_functions directory not created",
            )
            self.assertTrue(
                Path("agentmap_data/custom_tools").exists(),
                "custom_tools directory not created",
            )

    def test_init_copies_config_files(self):
        """Test that init command copies configuration files."""
        with self.runner.isolated_filesystem(temp_dir=self.temp_dir):
            # Run the init command
            result = self.runner.invoke(app, ["init"])

            # Verify command succeeded
            self.assertEqual(result.exit_code, 0, f"Command failed: {result.output}")

            # Verify config files were copied
            self.assertTrue(
                Path("agentmap_config.yaml").exists(),
                "agentmap_config.yaml not created",
            )
            self.assertTrue(
                Path("agentmap_config_storage.yaml").exists(),
                "agentmap_config_storage.yaml not created",
            )

    def test_init_copies_sample_workflow_to_workflows_folder(self):
        """Test that init command copies sample workflow to workflows folder."""
        with self.runner.isolated_filesystem(temp_dir=self.temp_dir):
            # Run the init command
            result = self.runner.invoke(app, ["init"])

            # Verify command succeeded
            self.assertEqual(result.exit_code, 0, f"Command failed: {result.output}")

            # Verify sample workflow was copied to workflows folder
            workflow_path = Path("agentmap_data/workflows/hello_world.csv")
            self.assertTrue(
                workflow_path.exists(),
                "hello_world.csv not copied to workflows folder",
            )

            # Verify the content is correct
            content = workflow_path.read_text()
            self.assertIn("HelloWorld", content, "Workflow content is incorrect")

    def test_init_with_force_overwrites_existing_files(self):
        """Test that init --force overwrites existing files."""
        with self.runner.isolated_filesystem(temp_dir=self.temp_dir):
            # Create existing config file
            Path("agentmap_config.yaml").write_text("existing content")

            # Run init with force flag
            result = self.runner.invoke(app, ["init", "--force"])

            # Verify command succeeded
            self.assertEqual(result.exit_code, 0, f"Command failed: {result.output}")

            # Verify file was overwritten
            content = Path("agentmap_config.yaml").read_text()
            self.assertIn("storage_config_path", content, "File not overwritten")
            self.assertNotIn("existing content", content, "Old content still present")

    def test_init_fails_without_force_when_files_exist(self):
        """Test that init fails when files exist and --force is not used."""
        with self.runner.isolated_filesystem(temp_dir=self.temp_dir):
            # Create existing config file
            Path("agentmap_config.yaml").write_text("existing content")

            # Run init without force flag
            result = self.runner.invoke(app, ["init"])

            # Verify command failed
            self.assertNotEqual(result.exit_code, 0, "Command should have failed")
            self.assertIn("already exist", result.output, "Error message incorrect")

    def test_init_creates_readme_files_in_empty_directories(self):
        """Test that init creates README.md files in empty directories."""
        with self.runner.isolated_filesystem(temp_dir=self.temp_dir):
            # Run the init command
            result = self.runner.invoke(app, ["init"])

            # Verify command succeeded
            self.assertEqual(result.exit_code, 0, f"Command failed: {result.output}")

            # Verify README.md files were created in empty directories
            custom_agents_readme = Path("agentmap_data/custom_agents/README.md")
            custom_functions_readme = Path("agentmap_data/custom_functions/README.md")
            custom_tools_readme = Path("agentmap_data/custom_tools/README.md")

            self.assertTrue(
                custom_agents_readme.exists(),
                "README.md not created in custom_agents",
            )
            self.assertTrue(
                custom_functions_readme.exists(),
                "README.md not created in custom_functions",
            )
            self.assertTrue(
                custom_tools_readme.exists(),
                "README.md not created in custom_tools",
            )

            # Verify README content
            agents_content = custom_agents_readme.read_text()
            self.assertIn(
                "AgentMap custom agents go in this folder",
                agents_content,
                "README.md content incorrect for custom_agents",
            )
            self.assertIn(
                "documentation online",
                agents_content,
                "README.md should reference documentation",
            )

            functions_content = custom_functions_readme.read_text()
            self.assertIn(
                "AgentMap custom functions go in this folder",
                functions_content,
                "README.md content incorrect for custom_functions",
            )
            self.assertIn(
                "documentation online",
                functions_content,
                "README.md should reference documentation",
            )

            tools_content = custom_tools_readme.read_text()
            self.assertIn(
                "AgentMap custom tools go in this folder",
                tools_content,
                "README.md content incorrect for custom_tools",
            )
            self.assertIn(
                "documentation online",
                tools_content,
                "README.md should reference documentation",
            )


if __name__ == "__main__":
    unittest.main()
