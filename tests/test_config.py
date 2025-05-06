# test_config.py
import os
from pathlib import Path

import pytest

from agentmap.config import get_csv_path, load_config


def test_config_loading():
    """Test that the config system loads properly."""
    config = load_config()
    assert isinstance(config, dict)
    assert "csv_path" in config
    assert "paths" in config
    
def test_get_csv_path():
    """Test that get_csv_path returns a Path object."""
    path = get_csv_path()
    assert isinstance(path, Path)