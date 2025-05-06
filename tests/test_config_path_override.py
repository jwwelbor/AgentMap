# tests/test_config_path_override.py

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from agentmap.config import get_csv_path, load_config


def test_load_config_with_override():
    """Test that config can be loaded from a custom path."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.yaml', delete=False) as temp:
        yaml_content = """
        csv_path: custom_path.csv
        autocompile: true
        paths:
          custom_agents: "custom/agents/path"
          functions: "custom/functions/path"
        """
        temp.write(yaml_content)
        temp_path = temp.name
    
    try:
        # Load config from custom path
        config = load_config(temp_path)
        
        # Check that values from custom config were loaded
        assert config["csv_path"] == "custom_path.csv"
        assert config["autocompile"] is True
        assert config["paths"]["custom_agents"] == "custom/agents/path"
        assert config["paths"]["functions"] == "custom/functions/path"
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_get_csv_path_with_override():
    """Test that get_csv_path respects config override."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.yaml', delete=False) as temp:
        yaml_content = """
        csv_path: custom_workflow.csv
        """
        temp.write(yaml_content)
        temp_path = temp.name
    
    try:
        # Get CSV path using custom config
        csv_path = get_csv_path(temp_path)
        
        # Check that the custom path was returned
        assert csv_path == Path("custom_workflow.csv")
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_config_path_falls_back_to_defaults():
    """Test that missing values in custom config fall back to defaults."""
    # Create a temporary config file with minimal settings
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.yaml', delete=False) as temp:
        yaml_content = """
        csv_path: custom_workflow.csv
        # Intentionally missing other settings
        """
        temp.write(yaml_content)
        temp_path = temp.name
    
    try:
        # Load config from custom path
        config = load_config(temp_path)
        
        # Check that custom value was loaded
        assert config["csv_path"] == "custom_workflow.csv"
        
        # Check that other values fell back to defaults
        assert "autocompile" in config
        assert "paths" in config
        assert "custom_agents" in config["paths"]
        assert "functions" in config["paths"]
        assert "llm" in config
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_nonexistent_config_path():
    """Test that nonexistent config path falls back to defaults."""
    # Path to a nonexistent config file
    nonexistent_path = "nonexistent_config_file.yaml"
    
    # Ensure the file doesn't exist
    if os.path.exists(nonexistent_path):
        os.remove(nonexistent_path)
    
    # Load config with nonexistent path
    config = load_config(nonexistent_path)
    
    # Check that default values were loaded
    assert "csv_path" in config
    assert "autocompile" in config
    assert "paths" in config
    assert "custom_agents" in config["paths"]
    assert "functions" in config["paths"]