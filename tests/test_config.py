# test_config.py
import os
from pathlib import Path

import pytest

from agentmap.config import get_csv_path, load_config
from agentmap.di import initialize_di

def test_config_loading():
    """Test that the config system loads properly."""
    initialize_di()

    config = load_config("./agentmap_config.yaml")
    assert isinstance(config, dict)
    assert "csv_path" in config
    assert "paths" in config
    
def test_get_csv_path():
    """Test that get_csv_path returns a Path object."""
    initialize_di()

    path = get_csv_path("./agentmap_config.yaml")
    assert isinstance(path, Path)