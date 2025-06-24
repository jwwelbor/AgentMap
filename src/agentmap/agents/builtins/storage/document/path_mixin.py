"""
Document path manipulation utilities.

This module provides utilities for working with JSON-path style dot notation
to access and modify nested data in document structures.

Examples:
    - "users.0.name" -> users array, first element, name field
    - "settings.theme.color" -> settings object, theme field, color field
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


class DocumentPathMixin:
    """
    Mixin providing document path manipulation functionality.

    This mixin contains methods for working with JSON-path style dot notation
    to access and modify nested data in document structures.
    """

    def _parse_path(self, path: str) -> List[str]:
        """
        Parse a document path into individual components.

        Args:
            path: Document path in dot notation

        Returns:
            List of path components
        """
        if not path or path == "$":
            return []

        return path.lstrip("$.").split(".")

    def _apply_path(self, data: Any, path: str) -> Any:
        """
        Extract data from a specific path within a document.

        Args:
            data: Document data
            path: Path expression (e.g. "users.0.name")

        Returns:
            Data at specified path or None if path doesn't exist
        """
        if not path or path == "$":
            return data

        parts = self._parse_path(path)
        current = data

        try:
            for part in parts:
                if isinstance(current, dict):
                    # Dictionary access
                    if part not in current:
                        return None
                    current = current[part]
                elif isinstance(current, list) and part.isdigit():
                    # List index access
                    index = int(part)
                    if not (0 <= index < len(current)):
                        return None
                    current = current[index]
                else:
                    # Can't traverse further
                    return None

                if current is None:
                    return None

            return current
        except Exception as e:
            self.log_debug(f"Error applying path '{path}': {str(e)}")
            return None

    def _update_path(self, data: Any, path: str, value: Any) -> Any:
        """
        Update data at a specific path within a document.

        Args:
            data: Document data
            path: Path expression (e.g. "users.0.name")
            value: New value to set

        Returns:
            Updated document with value set at path
        """
        if not path or path == "$":
            return value

        # Create a deep copy to avoid modifying the original
        result = self._deep_copy(data)
        parts = self._parse_path(path)

        # Handle top-level assignment
        if len(parts) == 1:
            return self._set_path_value(result, parts[0], value)

        # Handle nested assignment
        current = result
        for i, part in enumerate(parts[:-1]):
            next_part = parts[i + 1] if i + 1 < len(parts) else None

            # Create or navigate to the next level container
            current = self._navigate_container(current, part, next_part)
            if current is None:
                # If navigation failed, return original data
                self.log_debug(
                    f"Cannot update path {path}: navigation failed at part {part}"
                )
                return result

        # Set the value in the final container
        last_part = parts[-1]
        if isinstance(current, dict):
            current[last_part] = value
        elif isinstance(current, list) and last_part.isdigit():
            index = int(last_part)
            # Ensure list is long enough
            while len(current) <= index:
                current.append(None)
            current[index] = value

        return result

    def _navigate_container(
        self, current: Any, part: str, next_part: Optional[str]
    ) -> Any:
        """
        Navigate to or create the next level container.

        Args:
            current: Current container (dict or list)
            part: Current path part
            next_part: Next path part (for determining container type)

        Returns:
            Next level container or None if navigation failed
        """
        if isinstance(current, dict):
            # Create missing dict/list if needed
            if part not in current:
                current[part] = [] if next_part and next_part.isdigit() else {}
            return current[part]

        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            # Ensure list is long enough
            while len(current) <= index:
                current.append({})

            # Create missing dict/list if needed
            if not isinstance(current[index], (dict, list)):
                current[index] = [] if next_part and next_part.isdigit() else {}

            return current[index]

        return None

    def _set_path_value(self, container: Any, part: str, value: Any) -> Any:
        """
        Set value at a specific part within a container.

        Args:
            container: Dict or list container
            part: Key or index
            value: Value to set

        Returns:
            Updated container
        """
        if isinstance(container, dict):
            container[part] = value
            return container
        elif isinstance(container, list) and part.isdigit():
            index = int(part)
            # Ensure list is long enough
            while len(container) <= index:
                container.append(None)
            container[index] = value
            return container
        else:
            # Create new dict if can't set directly
            return {part: value}

    def _delete_path(self, data: Any, path: str) -> Any:
        """
        Delete data at a specific path within a document.

        Args:
            data: Document data
            path: Path expression (e.g. "users.0.name")

        Returns:
            Updated document with value at path removed
        """
        if not path or path == "$":
            # Delete everything - return empty structure matching original type
            if isinstance(data, dict):
                return {}
            elif isinstance(data, list):
                return []
            return None

        # Create a deep copy to avoid modifying the original
        result = self._deep_copy(data)
        parts = self._parse_path(path)

        # Handle top-level deletion
        if len(parts) == 1:
            return self._delete_path_value(result, parts[0])

        # Navigate to parent of the field to delete
        current = result
        for part in parts[:-1]:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    # Path doesn't exist, nothing to delete
                    return result
            else:
                # Path doesn't exist, nothing to delete
                return result

        # Delete from final container
        last_part = parts[-1]
        self._delete_path_value(current, last_part)

        return result

    def _delete_path_value(self, container: Any, part: str) -> Any:
        """
        Delete value at a specific part within a container.

        Args:
            container: Dict or list container
            part: Key or index

        Returns:
            Updated container
        """
        if isinstance(container, dict) and part in container:
            del container[part]
        elif isinstance(container, list) and part.isdigit():
            index = int(part)
            if 0 <= index < len(container):
                container.pop(index)
        return container

    def _deep_copy(self, data: Any) -> Any:
        """
        Create a deep copy of data structures.

        Args:
            data: Data to copy

        Returns:
            Deep copy of data
        """
        # Use Python's built-in copy module for deep copies
        return copy.deepcopy(data)

    def _merge_documents(
        self, dict1: Dict[Any, Any], dict2: Dict[Any, Any]
    ) -> Dict[Any, Any]:
        """
        Deep merge two dictionaries.

        Args:
            dict1: First dictionary
            dict2: Second dictionary (takes precedence)

        Returns:
            Merged dictionary
        """
        # Create a copy of the first dictionary
        result = self._deep_copy(dict1)

        # Merge in values from the second dictionary
        for key, value in dict2.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge dictionaries
                result[key] = self._merge_documents(result[key], value)
            else:
                # Override or add value
                result[key] = self._deep_copy(value)

        return result
