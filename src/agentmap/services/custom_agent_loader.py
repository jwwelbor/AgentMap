"""
Custom Agent Dynamic Loading Service.

This service handles dynamic loading of custom agents from the data directory,
allowing agents to be scaffolded and loaded from outside the package structure.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Dict, Optional, Type

from agentmap.services.logging_service import LoggingService


class CustomAgentLoader:
    """
    Service for dynamically loading custom agents from the data directory.

    Handles importing Python modules from the custom_agents directory that
    exists outside the main package structure, enabling dynamic agent loading
    for scaffolded agents.
    """

    def __init__(self, custom_agents_path: Path, logging_service: LoggingService):
        """
        Initialize the custom agent loader.

        Args:
            custom_agents_path: Path to the custom agents directory
            logging_service: Logging service for error reporting
        """
        self.custom_agents_path = Path(custom_agents_path)
        self.logger = logging_service.get_class_logger(self)
        self._loaded_modules: Dict[str, any] = {}
        self._ensure_path_in_sys_path()

    def _ensure_path_in_sys_path(self):
        """Ensure the custom agents directory is in sys.path for imports."""
        path_str = str(self.custom_agents_path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            self.logger.debug(f"Added custom agents path to sys.path: {path_str}")

    def load_agent_class(self, class_path: str) -> Optional[Type]:
        """
        Load a custom agent class from its path.

        Args:
            class_path: Class path like "wrapup_agent.WrapupAgent" or full path

        Returns:
            The loaded agent class or None if loading fails
        """
        try:
            # Split module and class name
            if "." in class_path:
                module_name, class_name = class_path.rsplit(".", 1)
            else:
                # Assume the class name matches the module name
                module_name = class_path
                class_name = class_path.replace("_agent", "Agent").replace("_", "")

            # Check if already loaded
            if module_name in self._loaded_modules:
                module = self._loaded_modules[module_name]
            else:
                # Load the module
                module = self._load_module(module_name)
                if module:
                    self._loaded_modules[module_name] = module
                else:
                    return None

            # Get the class from the module
            if hasattr(module, class_name):
                agent_class = getattr(module, class_name)
                self.logger.debug(f"Successfully loaded custom agent: {class_path}")
                return agent_class
            else:
                self.logger.error(
                    f"Class {class_name} not found in module {module_name}"
                )
                return None

        except Exception as e:
            self.logger.error(f"Failed to load custom agent {class_path}: {e}")
            return None

    def _load_module(self, module_name: str):
        """
        Load a Python module from the custom agents directory.

        Args:
            module_name: Name of the module (without .py extension)

        Returns:
            Loaded module or None if loading fails
        """
        try:
            # Construct the file path
            module_file = self.custom_agents_path / f"{module_name}.py"

            if not module_file.exists():
                self.logger.error(f"Module file not found: {module_file}")
                return None

            # Create module spec
            spec = importlib.util.spec_from_file_location(
                f"custom_agents.{module_name}", module_file
            )

            if spec is None:
                self.logger.error(f"Could not create spec for module: {module_name}")
                return None

            # Load the module
            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules to make it importable
            sys.modules[f"custom_agents.{module_name}"] = module

            # Execute the module
            spec.loader.exec_module(module)

            self.logger.debug(f"Successfully loaded module: {module_name}")
            return module

        except Exception as e:
            self.logger.error(f"Failed to load module {module_name}: {e}")
            return None

    def get_available_agents(self) -> Dict[str, str]:
        """
        Get a list of available custom agents in the directory.

        Returns:
            Dictionary mapping agent names to their file paths
        """
        agents = {}

        if not self.custom_agents_path.exists():
            self.logger.warning(
                f"Custom agents directory not found: {self.custom_agents_path}"
            )
            return agents

        # Find all Python files in the directory
        for py_file in self.custom_agents_path.glob("*_agent.py"):
            module_name = py_file.stem
            # Derive agent name from file name
            agent_name = module_name.replace("_agent", "").replace("_", "")
            agents[agent_name] = str(py_file)

        self.logger.debug(f"Found {len(agents)} custom agents")
        return agents

    def validate_agent_class(self, agent_class: Type) -> bool:
        """
        Validate that a loaded class is a valid agent.

        Args:
            agent_class: Class to validate

        Returns:
            True if the class is a valid agent
        """
        try:
            # Check if it has required agent methods
            if not hasattr(agent_class, "run"):
                self.logger.error(
                    f"Agent class {agent_class.__name__} missing 'run' method"
                )
                return False

            if not hasattr(agent_class, "process"):
                self.logger.error(
                    f"Agent class {agent_class.__name__} missing 'process' method"
                )
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating agent class: {e}")
            return False
