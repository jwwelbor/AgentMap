"""
Path Navigator for AgentMap Memory Storage.

This module provides path-based navigation and updates for nested data structures
using dot notation (e.g., "user.profile.name").
"""

from typing import Any


class PathNavigator:
    """
    Path-based navigation and updates for nested data structures.

    Supports dot notation for accessing and modifying nested dictionaries and lists.
    """

    @staticmethod
    def apply_path(data: Any, path: str) -> Any:
        """
        Extract data from nested structure using dot notation.

        Args:
            data: Data structure to traverse
            path: Dot-notation path (e.g., "user.address.city")

        Returns:
            Value at the specified path or None if not found
        """
        if not path:
            return data

        components = path.split(".")
        current = data

        for component in components:
            if current is None:
                return None

            # Handle arrays with numeric indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            # Handle dictionaries
            elif isinstance(current, dict):
                current = current.get(component)
            else:
                return None

        return current

    @staticmethod
    def update_path(data: Any, path: str, value: Any) -> Any:
        """
        Update data at a specified path.

        Args:
            data: Data structure to modify
            path: Dot-notation path
            value: New value to set

        Returns:
            Updated data structure
        """
        if not path:
            return value

        # Make a copy to avoid modifying original
        if isinstance(data, dict):
            result = data.copy()
        elif isinstance(data, list):
            result = data.copy()
        else:
            # If data is not a container, start with empty dict
            result = {}

        components = path.split(".")
        current = result

        # Navigate to the parent of the target
        for i, component in enumerate(components[:-1]):
            # Handle array indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                # Extend the list if needed
                while len(current) <= index:
                    current.append({})

                if current[index] is None:
                    if i < len(components) - 2 and components[i + 1].isdigit():
                        current[index] = []
                    else:
                        current[index] = {}

                current = current[index]

            # Handle dictionary keys
            else:
                if not isinstance(current, dict):
                    raise TypeError(
                        f"Cannot traverse path: expected dict at '{component}', "
                        f"but found {type(current).__name__}"
                    )

                if component not in current:
                    if i < len(components) - 2 and components[i + 1].isdigit():
                        current[component] = []
                    else:
                        current[component] = {}

                current = current[component]

        # Set the value at the final path component
        last_component = components[-1]

        if last_component.isdigit() and isinstance(current, list):
            index = int(last_component)
            while len(current) <= index:
                current.append(None)
            current[index] = value
        elif isinstance(current, dict):
            current[last_component] = value

        return result

    @staticmethod
    def delete_path(data: Any, path: str) -> bool:
        """
        Delete a value at a specified path.

        Args:
            data: Data structure to modify
            path: Dot-notation path

        Returns:
            True if deletion was successful, False otherwise
        """
        if not path or data is None:
            return False

        # Handle simple path deletion (no dots)
        if "." not in path:
            if isinstance(data, dict) and path in data:
                del data[path]
                return True
            elif isinstance(data, list) and path.isdigit():
                index = int(path)
                if 0 <= index < len(data):
                    data.pop(index)
                    return True
            return False

        # Handle nested paths
        components = path.split(".")
        current = data

        # Navigate to the parent of the target
        for component in components[:-1]:
            if current is None:
                return False

            # Handle arrays with numeric indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return False
            # Handle dictionaries
            elif isinstance(current, dict):
                if component not in current:
                    return False
                current = current[component]
            else:
                return False

        # Delete the final component
        last_component = components[-1]
        if isinstance(current, dict) and last_component in current:
            del current[last_component]
            return True
        elif isinstance(current, list) and last_component.isdigit():
            index = int(last_component)
            if 0 <= index < len(current):
                current.pop(index)
                return True

        return False
