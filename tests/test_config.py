# test_config.py
import os
from pathlib import Path

import pytest

from agentmap.config import get_csv_path, load_config
from agentmap.di import init_for_cli

def test_config_loading():
    """Test that the config system loads properly."""
    init_for_cli()

    config = load_config("./agentmap_config.yaml")
    assert isinstance(config, dict)
    assert "csv_path" in config
    assert "paths" in config
    
def test_get_csv_path():
    """Test that get_csv_path returns a Path object."""
    init_for_cli()

    path = get_csv_path("./agentmap_config.yaml")
    assert isinstance(path, Path)