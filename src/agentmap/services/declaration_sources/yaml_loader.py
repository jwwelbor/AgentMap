"""Shared YAML file loading utility for declaration sources."""

import logging
from pathlib import Path
from typing import Any, Dict


def load_yaml_file(path: Path, logger: logging.Logger) -> Dict[str, Any]:
    """
    Load and parse a YAML file with graceful error handling.

    Args:
        path: Path to YAML file to load
        logger: Logger instance for error reporting

    Returns:
        Parsed YAML data as dictionary, or empty dict if file missing/invalid
    """
    if not path.exists():
        logger.debug(f"YAML declaration file not found: {path}")
        return {}

    if not path.is_file():
        logger.warning(f"YAML declaration path is not a file: {path}")
        return {}

    try:
        import yaml

        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        if not isinstance(data, dict):
            logger.warning(f"YAML file does not contain valid dictionary: {path}")
            return {}

        logger.debug(f"Successfully loaded YAML file: {path}")
        return data

    except ImportError:
        logger.error("PyYAML not available - cannot load YAML declaration files")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML file '{path}': {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load YAML file '{path}': {e}")
        return {}
