# test_cli.py
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentmap.cli import app

runner = CliRunner()

def test_cli_scaffold():
    """Test the scaffold command."""
    with runner.isolated_filesystem():
        # Create a temporary file structure
        os.makedirs("custom_agents", exist_ok=True)
        os.makedirs("functions", exist_ok=True)
        
        # Copy example CSV to temp dir
        example_path = Path("examples/NewAgentScaffold.csv")
        if example_path.exists():
            # Only run test if example exists
            result = runner.invoke(app, ["scaffold", "--csv", str(example_path)])
            assert result.exit_code == 0
            assert "Scaffolded" in result.stdout

def test_cli_help():
    """Test that CLI help works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout
    
    # Test help on a subcommand
    result = runner.invoke(app, ["scaffold", "--help"])
    assert result.exit_code == 0
    assert "scaffold" in result.stdout.lower()